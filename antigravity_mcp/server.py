"""
Gravitas-Core-MCP server — MCP entrypoint and tool wiring.

Exposes memory, controller, terminal, browser, project_intel tools
and Model Resume Package (handover) for model swap / restart / crash recovery.
"""

from __future__ import annotations

import anyio
import json
import os
from pathlib import Path
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .browser import BrowserEngine
from .controller import Controller
from .memory import Memory
from .project_intel import get_project_map
from .terminal import TerminalEngine


def _detect_project_root() -> Path:
    """Detect project root (cwd or first parent with pyproject.toml / .git)."""
    cwd = Path(os.getcwd()).resolve()
    for p in [cwd] + list(cwd.parents):
        if (p / "pyproject.toml").exists() or (p / ".git").exists():
            return p
    return cwd


def _content(text: str) -> list[types.ContentBlock]:
    return [types.TextContent(type="text", text=text)]


async def _run_server() -> None:
    root = _detect_project_root()
    memory = Memory(project_root=root)
    controller = Controller(memory=memory)
    terminal = TerminalEngine(project_root=root)
    browser = BrowserEngine(project_root=root)

    app = Server("Gravitas-Core-MCP")

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="get_last_state",
                description="Return the last known state (most recent snapshot + active task). Authoritative memory.",
                input_schema={"type": "object", "properties": {}, "required": []},
            ),
            types.Tool(
                name="get_canonical_state",
                description="Return the last verified, immutable working state for rollback/recovery.",
                input_schema={"type": "object", "properties": {}, "required": []},
            ),
            types.Tool(
                name="record_failure",
                description="Record a failed strategy/command to prevent repetition.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string", "description": "Failure reason"},
                        "context": {"type": "object", "description": "Context (e.g. task_id, command)"},
                    },
                    "required": ["reason", "context"],
                },
            ),
            types.Tool(
                name="resume_task",
                description="Load task and its context for resumption (model handover/restart).",
                input_schema={
                    "type": "object",
                    "properties": {"task_id": {"type": "string", "description": "Task ID"}},
                    "required": ["task_id"],
                },
            ),
            types.Tool(
                name="controller_create_task",
                description="Create a new task and set state to PLANNING.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "goal": {"type": "string", "description": "Task goal"},
                        "task_id": {"type": "string", "description": "Optional task ID"},
                    },
                    "required": ["goal"],
                },
            ),
            types.Tool(
                name="controller_transition",
                description="Transition task to a new state (PLANNING, CODING, EXECUTING, VERIFYING, FAILED_RETRY, ROLLBACK, COMPLETED).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "new_state": {"type": "string"},
                    },
                    "required": ["task_id", "new_state"],
                },
            ),
            types.Tool(
                name="controller_record_step_failure",
                description="Record a step failure; may trigger FAILED_RETRY or ROLLBACK.",
                input_schema={
                    "type": "object",
                    "properties": {"task_id": {"type": "string"}, "reason": {"type": "string"}},
                    "required": ["task_id", "reason"],
                },
            ),
            types.Tool(
                name="controller_get_state",
                description="Return current task state and policy info.",
                input_schema={
                    "type": "object",
                    "properties": {"task_id": {"type": "string"}},
                    "required": ["task_id"],
                },
            ),
            types.Tool(
                name="terminal_execute",
                description="Execute a shell command with timeout and cwd. Returns stdout, stderr, exit_code.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "cwd": {"type": "string"},
                        "timeout_sec": {"type": "integer"},
                    },
                    "required": ["command"],
                },
            ),
            types.Tool(
                name="terminal_start_background",
                description="Start a background process; use process_id to stop later.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "process_id": {"type": "string"},
                        "cwd": {"type": "string"},
                    },
                    "required": ["command", "process_id"],
                },
            ),
            types.Tool(
                name="terminal_stop_background",
                description="Terminate a background process by process_id.",
                input_schema={
                    "type": "object",
                    "properties": {"process_id": {"type": "string"}},
                    "required": ["process_id"],
                },
            ),
            types.Tool(
                name="terminal_list_background",
                description="List active background process ids.",
                input_schema={"type": "object", "properties": {}, "required": []},
            ),
            types.Tool(
                name="browser_navigate",
                description="Navigate to URL (Playwright).",
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}, "wait_until": {"type": "string"}},
                    "required": ["url"],
                },
            ),
            types.Tool(
                name="browser_snapshot",
                description="Capture DOM accessibility tree and console errors.",
                input_schema={"type": "object", "properties": {}, "required": []},
            ),
            types.Tool(
                name="browser_screenshot",
                description="Take screenshot; optional path to save file.",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": [],
                },
            ),
            types.Tool(
                name="browser_get_console_errors",
                description="Return collected JS console errors since last navigate.",
                input_schema={"type": "object", "properties": {}, "required": []},
            ),
            types.Tool(
                name="project_get_map",
                description="Recursive project structure with noise filtering.",
                input_schema={
                    "type": "object",
                    "properties": {"project_root": {"type": "string"}, "max_depth": {"type": "integer"}, "max_entries": {"type": "integer"}},
                    "required": [],
                },
            ),
            types.Tool(
                name="memory_save_snapshot",
                description="Save a context snapshot for current task (internal use).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "snapshot_id": {"type": "string"},
                        "task_id": {"type": "string"},
                        "project_map": {"type": "object"},
                        "safe_to_edit": {"type": "array", "items": {"type": "string"}},
                        "do_not_touch": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["snapshot_id", "task_id", "project_map", "safe_to_edit", "do_not_touch"],
                },
            ),
            types.Tool(
                name="memory_set_canonical",
                description="Set the canonical (immutable) state to a snapshot (after verification).",
                input_schema={
                    "type": "object",
                    "properties": {"snapshot_id": {"type": "string"}},
                    "required": ["snapshot_id"],
                },
            ),
            types.Tool(
                name="get_model_resume_package",
                description="Generate Model Resume Package for model swap/editor restart/crash recovery: goal, task, constraints, failures, safe/do-not-touch files.",
                input_schema={
                    "type": "object",
                    "properties": {"task_id": {"type": "string"}},
                    "required": [],
                },
            ),
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.ContentBlock]:
        args = arguments or {}
        result: dict[str, Any]

        if name == "get_last_state":
            result = memory.get_last_state()
        elif name == "get_canonical_state":
            result = memory.get_canonical_state()
        elif name == "record_failure":
            result = memory.record_failure(
                reason=args.get("reason", ""),
                context=args.get("context") or {},
            )
        elif name == "resume_task":
            result = memory.resume_task(args.get("task_id", ""))
        elif name == "controller_create_task":
            result = controller.create_task(goal=args.get("goal", ""), task_id=args.get("task_id"))
        elif name == "controller_transition":
            result = controller.transition(
                task_id=args.get("task_id", ""),
                new_state=args.get("new_state", ""),
            )
        elif name == "controller_record_step_failure":
            result = controller.record_step_failure(
                task_id=args.get("task_id", ""),
                reason=args.get("reason", ""),
            )
        elif name == "controller_get_state":
            result = controller.get_state(args.get("task_id", ""))
        elif name == "terminal_execute":
            result = await terminal.execute(
                command=args.get("command", ""),
                cwd=args.get("cwd"),
                timeout_sec=args.get("timeout_sec"),
            )
        elif name == "terminal_start_background":
            result = await terminal.start_background(
                command=args.get("command", ""),
                process_id=args.get("process_id", ""),
                cwd=args.get("cwd"),
            )
        elif name == "terminal_stop_background":
            result = await terminal.stop_background(args.get("process_id", ""))
        elif name == "terminal_list_background":
            result = await terminal.list_background()
        elif name == "browser_navigate":
            result = await browser.navigate(
                url=args.get("url", ""),
                wait_until=args.get("wait_until", "domcontentloaded"),
            )
        elif name == "browser_snapshot":
            result = await browser.snapshot()
        elif name == "browser_screenshot":
            result = await browser.screenshot(path=args.get("path"))
        elif name == "browser_get_console_errors":
            result = await browser.get_console_errors()
        elif name == "project_get_map":
            result = get_project_map(
                project_root=args.get("project_root") or root,
                max_depth=args.get("max_depth", 8),
                max_entries=args.get("max_entries", 2000),
            )
        elif name == "memory_save_snapshot":
            memory.save_snapshot(
                snapshot_id=args.get("snapshot_id", ""),
                task_id=args.get("task_id", ""),
                project_map=args.get("project_map") or {},
                safe_to_edit=args.get("safe_to_edit") or [],
                do_not_touch=args.get("do_not_touch") or [],
            )
            result = {"status": "success", "observations": {}, "errors": [], "next_recommended_action": "Proceed."}
        elif name == "memory_set_canonical":
            memory.set_canonical_state(args.get("snapshot_id", ""))
            result = {"status": "success", "observations": {}, "errors": [], "next_recommended_action": "Canonical state set."}
        elif name == "get_model_resume_package":
            result = _build_model_resume_package(memory, controller, args.get("task_id"))
        else:
            from .memory import _tool_result as tr
            result = tr("failure", errors=[f"Unknown tool: {name}"], next_recommended_action="Use list_tools.")

        return _content(json.dumps(result, default=str))

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def _tool_result(status: str, observations: dict | None = None, errors: list | None = None, next_recommended_action: str = "") -> dict:
    from .memory import _tool_result as tr
    return tr(status, observations, errors, next_recommended_action)


def _build_model_resume_package(memory: Memory, controller: Controller, task_id: str | None) -> dict[str, Any]:
    """Build Model Resume Package for handover."""
    last = memory.get_last_state()
    obs = last.get("observations") or {}
    canonical = memory.get_canonical_state().get("observations") or {}
    failures = memory.get_failure_summary(task_id=task_id, limit=30)
    active_task = obs.get("active_task")
    last_snapshot = obs.get("last_snapshot") or canonical.get("canonical_snapshot")
    task = None
    if task_id:
        resume = memory.resume_task(task_id)
        if resume.get("status") == "success":
            task = (resume.get("observations") or {}).get("task")
    if not task and active_task:
        task = active_task
    goal = (task.get("goal") or "") if task else ""
    state = (task.get("state") or "") if task else ""
    safe_to_edit = (last_snapshot.get("safe_to_edit") or []) if last_snapshot else []
    do_not_touch = (last_snapshot.get("do_not_touch") or []) if last_snapshot else []

    package = {
        "status": "success",
        "observations": {
            "current_goal": goal,
            "active_task_id": task.get("id") if task else task_id,
            "task_state": state,
            "known_constraints": {
                "safe_to_edit": safe_to_edit,
                "do_not_touch": do_not_touch,
            },
            "failure_memory_summary": [{"reason": f.get("reason"), "context": f.get("context")} for f in failures],
            "project_root": str(memory.get_project_root()),
        },
        "errors": [],
        "next_recommended_action": "Resume task from state; avoid repeating failures; respect safe_to_edit and do_not_touch.",
    }
    return package


def main() -> int:
    """Entrypoint for uvx / Gravitas-Core-MCP."""
    anyio.run(_run_server)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
