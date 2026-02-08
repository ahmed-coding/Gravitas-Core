"""
Terminal Execution Engine — ground-truth execution feedback.

Execute shell commands with timeouts, working directory isolation;
capture STDOUT, STDERR, exit codes; background process management.
Allowlist/denylist support; automatic termination of runaway processes.
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
import time
from pathlib import Path
from typing import Any

from .memory import _tool_result

DEFAULT_TIMEOUT_SEC = 60
MAX_OUTPUT_BYTES = 512 * 1024  # 512 KiB


class TerminalEngine:
    """
    Async terminal execution with allowlist/denylist and timeout.
    """

    def __init__(
        self,
        project_root: str | Path | None = None,
        allowlist_patterns: list[str] | None = None,
        denylist_patterns: list[str] | None = None,
        default_timeout: int = DEFAULT_TIMEOUT_SEC,
    ):
        self._root = Path(project_root or os.getcwd()).resolve()
        self._allowlist = allowlist_patterns or []  # regex; if non-empty, command must match one
        self._denylist = denylist_patterns or [
            r"\brm\s+-rf\s+/",
            r"\brm\s+-rf\s+\*",
            r">\s*/dev/sd",
            r"mkfs\.|dd\s+if=.*of=/dev",
            r"chmod\s+-R\s+777",
            r":(){ :|:& };:",  # fork bomb
        ]
        self._default_timeout = default_timeout
        self._background_procs: dict[str, asyncio.subprocess.Process] = {}

    def get_project_root(self) -> Path:
        return self._root

    def _check_policy(self, command: str) -> tuple[bool, str | None]:
        """Return (allowed, error_message)."""
        cmd_stripped = command.strip()
        for pat in self._denylist:
            if re.search(pat, cmd_stripped):
                return False, f"Command denied by policy (denylist): {pat}"
        if self._allowlist:
            if not any(re.search(p, cmd_stripped) for p in self._allowlist):
                return False, "Command not in allowlist."
        return True, None

    async def execute(
        self,
        command: str,
        cwd: str | Path | None = None,
        timeout_sec: int | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a shell command with timeout and working directory isolation.
        Returns tool contract: status, observations (stdout, stderr, exit_code, duration), errors, next_recommended_action.
        """
        allowed, err = self._check_policy(command)
        if not allowed:
            return _tool_result(
                "failure",
                errors=[err or "Command not allowed"],
                next_recommended_action="Use an allowed command or adjust policy.",
            )
        work_dir = Path(cwd or self._root).resolve()
        if not work_dir.is_dir():
            return _tool_result(
                "failure",
                errors=[f"Working directory does not exist: {work_dir}"],
                next_recommended_action="Use a valid project path.",
            )
        timeout = timeout_sec if timeout_sec is not None else self._default_timeout
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(work_dir),
                env=run_env,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return _tool_result(
                    "failure",
                    observations={
                        "exit_code": None,
                        "timed_out": True,
                        "duration_sec": round(time.monotonic() - start, 2),
                    },
                    errors=[f"Command timed out after {timeout}s"],
                    next_recommended_action="Simplify command or increase timeout.",
                )
            duration = time.monotonic() - start
            out_decoded = stdout_b.decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES]
            err_decoded = stderr_b.decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES]
            return _tool_result(
                "success" if proc.returncode == 0 else "failure",
                observations={
                    "stdout": out_decoded,
                    "stderr": err_decoded,
                    "exit_code": proc.returncode,
                    "duration_sec": round(duration, 2),
                    "cwd": str(work_dir),
                },
                errors=[] if proc.returncode == 0 else [f"Exit code: {proc.returncode}"],
                next_recommended_action="Inspect stdout/stderr and fix command or code." if proc.returncode != 0 else "Proceed with verification.",
            )
        except Exception as e:
            return _tool_result(
                "failure",
                errors=[str(e)],
                next_recommended_action="Check command syntax and environment.",
            )

    async def start_background(
        self,
        command: str,
        process_id: str,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Start a background process; store by process_id for later stop."""
        allowed, err = self._check_policy(command)
        if not allowed:
            return _tool_result("failure", errors=[err or "Command not allowed"], next_recommended_action="Use an allowed command.")
        work_dir = Path(cwd or self._root).resolve()
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=str(work_dir),
                env=run_env,
            )
            self._background_procs[process_id] = proc
            return _tool_result(
                "success",
                observations={"process_id": process_id, "pid": proc.pid, "cwd": str(work_dir)},
                next_recommended_action="Call stop_background(process_id) when done.",
            )
        except Exception as e:
            return _tool_result("failure", errors=[str(e)], next_recommended_action="Check command and path.")

    async def stop_background(self, process_id: str) -> dict[str, Any]:
        """Terminate a background process by process_id."""
        proc = self._background_procs.pop(process_id, None)
        if not proc:
            return _tool_result(
                "failure",
                errors=[f"Unknown process_id: {process_id}"],
                next_recommended_action="List background processes or use correct id.",
            )
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
        return _tool_result(
            "success",
            observations={"process_id": process_id, "stopped": True},
            next_recommended_action="Proceed.",
        )

    async def list_background(self) -> dict[str, Any]:
        """List active background process ids."""
        pids = {k: (p.pid if p.returncode is None else None) for k, p in list(self._background_procs.items())}
        # drop already-finished
        self._background_procs = {k: p for k, p in self._background_procs.items() if p.returncode is None}
        return _tool_result(
            "success",
            observations={"process_ids": list(self._background_procs.keys()), "pids": pids},
            next_recommended_action="Call stop_background(process_id) to stop.",
        )
