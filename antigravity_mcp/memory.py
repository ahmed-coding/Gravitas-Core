"""
Memory & Persistence Layer — authoritative brain of Gravitas-Core-MCP.

Tracks task ledger, context snapshots, canonical project state,
failure memory, and tool usage patterns. SQLite-backed, local-only.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DB_NAME = ".gravitas_brain.db"


@dataclass
class TaskRecord:
    """Single task or subtask in the ledger."""

    id: str
    parent_id: str | None
    goal: str
    state: str
    created_at: float
    updated_at: float
    completed_at: float | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextSnapshot:
    """Structured representation of project at a checkpoint."""

    id: str
    task_id: str
    created_at: float
    project_map: dict[str, Any]
    safe_to_edit: list[str]
    do_not_touch: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FailureRecord:
    """Record of a failed strategy or command."""

    id: str
    reason: str
    context: dict[str, Any]
    created_at: float
    task_id: str | None


@dataclass
class ToolUsageRecord:
    """Successful tool invocation pattern."""

    id: str
    tool_name: str
    arguments: dict[str, Any]
    outcome_summary: str
    created_at: float
    task_id: str | None


def _tool_result(
    status: str,
    observations: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    next_recommended_action: str = "",
) -> dict[str, Any]:
    """Standard tool contract response."""
    return {
        "status": status,
        "observations": observations or {},
        "errors": errors or [],
        "next_recommended_action": next_recommended_action,
    }


class Memory:
    """SQLite-backed persistent memory. Single writer, project-scoped."""

    def __init__(self, project_root: str | Path | None = None):
        self._root = Path(project_root or os.getcwd()).resolve()
        self._db_path = self._root / DB_NAME
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._ensure_schema()
        return self._conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                goal TEXT NOT NULL,
                state TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                completed_at REAL,
                metadata TEXT
            );
            CREATE TABLE IF NOT EXISTS context_snapshots (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                project_map TEXT NOT NULL,
                safe_to_edit TEXT,
                do_not_touch TEXT,
                metadata TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            );
            CREATE TABLE IF NOT EXISTS canonical_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                snapshot_id TEXT NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (snapshot_id) REFERENCES context_snapshots(id)
            );
            CREATE TABLE IF NOT EXISTS failures (
                id TEXT PRIMARY KEY,
                reason TEXT NOT NULL,
                context TEXT NOT NULL,
                created_at REAL NOT NULL,
                task_id TEXT
            );
            CREATE TABLE IF NOT EXISTS tool_usage (
                id TEXT PRIMARY KEY,
                tool_name TEXT NOT NULL,
                arguments TEXT NOT NULL,
                outcome_summary TEXT NOT NULL,
                created_at REAL NOT NULL,
                task_id TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);
            CREATE INDEX IF NOT EXISTS idx_failures_created ON failures(created_at);
        """)
        conn.commit()

    def get_project_root(self) -> Path:
        return self._root

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Internal: fetch task by id."""
        conn = self._connect()
        cur = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["metadata"] = json.loads(d.get("metadata") or "{}")
        return d

    def get_last_state(self) -> dict[str, Any]:
        """
        Return the last known state (most recent snapshot + active task).
        Mandatory tool: get_last_state().
        """
        try:
            conn = self._connect()
            cur = conn.execute(
                "SELECT * FROM context_snapshots ORDER BY created_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                return _tool_result(
                    "success",
                    observations={
                        "project_root": str(self._root),
                        "has_snapshot": False,
                        "active_task": None,
                        "message": "No prior state; fresh session.",
                    },
                    next_recommended_action="Initialize task and take first snapshot.",
                )

            cur2 = conn.execute(
                "SELECT * FROM tasks WHERE state NOT IN ('COMPLETED', 'ROLLBACK') ORDER BY updated_at DESC LIMIT 1"
            )
            active = cur2.fetchone()
            snapshot = dict(row)
            snapshot["project_map"] = json.loads(snapshot["project_map"] or "{}")
            snapshot["safe_to_edit"] = json.loads(snapshot["safe_to_edit"] or "[]")
            snapshot["do_not_touch"] = json.loads(snapshot["do_not_touch"] or "[]")
            snapshot["metadata"] = json.loads(snapshot["metadata"] or "{}")

            return _tool_result(
                "success",
                observations={
                    "project_root": str(self._root),
                    "has_snapshot": True,
                    "last_snapshot": snapshot,
                    "active_task": dict(active) if active else None,
                },
                next_recommended_action="Resume or create task; run verification if needed.",
            )
        except Exception as e:
            return _tool_result(
                "failure",
                errors=[str(e)],
                next_recommended_action="Check database path and permissions.",
            )

    def get_canonical_state(self) -> dict[str, Any]:
        """
        Return the last verified, immutable working state (for rollback / recovery).
        Mandatory tool: get_canonical_state().
        """
        try:
            conn = self._connect()
            cur = conn.execute("SELECT snapshot_id, updated_at FROM canonical_state WHERE id = 1")
            row = cur.fetchone()
            if not row:
                return _tool_result(
                    "success",
                    observations={
                        "project_root": str(self._root),
                        "has_canonical": False,
                        "message": "No canonical state set yet.",
                    },
                    next_recommended_action="Complete a verified run to set canonical state.",
                )

            snap_id = row["snapshot_id"]
            cur2 = conn.execute("SELECT * FROM context_snapshots WHERE id = ?", (snap_id,))
            snap_row = cur2.fetchone()
            if not snap_row:
                return _tool_result(
                    "success",
                    observations={"has_canonical": False, "message": "Canonical snapshot missing."},
                )

            snap = dict(snap_row)
            snap["project_map"] = json.loads(snap["project_map"] or "{}")
            snap["safe_to_edit"] = json.loads(snap["safe_to_edit"] or "[]")
            snap["do_not_touch"] = json.loads(snap["do_not_touch"] or "[]")
            snap["metadata"] = json.loads(snap["metadata"] or "{}")

            return _tool_result(
                "success",
                observations={
                    "project_root": str(self._root),
                    "has_canonical": True,
                    "canonical_snapshot": snap,
                    "canonical_updated_at": row["updated_at"],
                },
                next_recommended_action="Use for rollback or model handover.",
            )
        except Exception as e:
            return _tool_result(
                "failure",
                errors=[str(e)],
                next_recommended_action="Check database.",
            )

    def record_failure(self, reason: str, context: dict[str, Any]) -> dict[str, Any]:
        """
        Record a failed strategy/command to prevent repetition.
        Mandatory tool: record_failure(reason, context).
        """
        try:
            fid = f"fail_{int(time.time() * 1000)}_{os.urandom(4).hex()}"
            conn = self._connect()
            conn.execute(
                "INSERT INTO failures (id, reason, context, created_at, task_id) VALUES (?, ?, ?, ?, ?)",
                (fid, reason, json.dumps(context), time.time(), context.get("task_id")),
            )
            conn.commit()
            return _tool_result(
                "success",
                observations={"failure_id": fid, "reason": reason},
                next_recommended_action="Avoid repeating this strategy; consider rollback or new approach.",
            )
        except Exception as e:
            return _tool_result(
                "failure",
                errors=[str(e)],
                next_recommended_action="Retry record_failure or check DB.",
            )

    def resume_task(self, task_id: str) -> dict[str, Any]:
        """
        Load task and its context for resumption (model handover / restart).
        Mandatory tool: resume_task(task_id).
        """
        try:
            conn = self._connect()
            cur = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cur.fetchone()
            if not row:
                return _tool_result(
                    "failure",
                    errors=[f"Task not found: {task_id}"],
                    next_recommended_action="List tasks or create a new one.",
                )

            task = dict(row)
            task["metadata"] = json.loads(task["metadata"] or "{}")

            cur2 = conn.execute(
                "SELECT * FROM context_snapshots WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
                (task_id,),
            )
            snap_row = cur2.fetchone()
            snapshot = None
            if snap_row:
                snapshot = dict(snap_row)
                snapshot["project_map"] = json.loads(snapshot["project_map"] or "{}")
                snapshot["safe_to_edit"] = json.loads(snapshot["safe_to_edit"] or "[]")
                snapshot["do_not_touch"] = json.loads(snapshot["do_not_touch"] or "[]")

            cur3 = conn.execute(
                "SELECT id, reason, context, created_at FROM failures WHERE task_id = ? ORDER BY created_at DESC LIMIT 20",
                (task_id,),
            )
            failures = [dict(r) for r in cur3.fetchall()]
            for f in failures:
                f["context"] = json.loads(f["context"])

            return _tool_result(
                "success",
                observations={
                    "task": task,
                    "latest_snapshot": snapshot,
                    "recent_failures": failures,
                },
                next_recommended_action=f"Resume from state {task['state']}; avoid repeating recorded failures.",
            )
        except Exception as e:
            return _tool_result(
                "failure",
                errors=[str(e)],
                next_recommended_action="Check task_id and database.",
            )

    def upsert_task(
        self,
        task_id: str,
        goal: str,
        state: str,
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Internal: create or update task."""
        conn = self._connect()
        now = time.time()
        meta_json = json.dumps(metadata or {})
        conn.execute(
            """INSERT INTO tasks (id, parent_id, goal, state, created_at, updated_at, completed_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 goal=excluded.goal, state=excluded.state, updated_at=excluded.updated_at,
                 completed_at=CASE WHEN excluded.state IN ('COMPLETED','ROLLBACK') THEN excluded.updated_at ELSE completed_at END,
                 metadata=excluded.metadata""",
            (task_id, parent_id, goal, state, now, now, None if state not in ("COMPLETED", "ROLLBACK") else now, meta_json),
        )
        conn.commit()

    def save_snapshot(
        self,
        snapshot_id: str,
        task_id: str,
        project_map: dict[str, Any],
        safe_to_edit: list[str],
        do_not_touch: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Internal: save context snapshot."""
        conn = self._connect()
        now = time.time()
        conn.execute(
            """INSERT INTO context_snapshots (id, task_id, created_at, project_map, safe_to_edit, do_not_touch, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot_id,
                task_id,
                now,
                json.dumps(project_map),
                json.dumps(safe_to_edit),
                json.dumps(do_not_touch),
                json.dumps(metadata or {}),
            ),
        )
        conn.commit()

    def set_canonical_state(self, snapshot_id: str) -> None:
        """Internal: set the immutable canonical state to given snapshot."""
        conn = self._connect()
        conn.execute(
            "INSERT OR REPLACE INTO canonical_state (id, snapshot_id, updated_at) VALUES (1, ?, ?)",
            (snapshot_id, time.time()),
        )
        conn.commit()

    def record_tool_usage(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        outcome_summary: str,
        task_id: str | None = None,
    ) -> None:
        """Internal: record successful tool usage."""
        uid = f"tool_{int(time.time() * 1000)}_{os.urandom(4).hex()}"
        conn = self._connect()
        conn.execute(
            "INSERT INTO tool_usage (id, tool_name, arguments, outcome_summary, created_at, task_id) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, tool_name, json.dumps(arguments), outcome_summary, time.time(), task_id),
        )
        conn.commit()

    def get_failure_summary(self, task_id: str | None = None, limit: int = 50) -> list[dict]:
        """Return recent failures for handover package."""
        conn = self._connect()
        if task_id:
            cur = conn.execute(
                "SELECT id, reason, context, created_at FROM failures WHERE task_id = ? ORDER BY created_at DESC LIMIT ?",
                (task_id, limit),
            )
        else:
            cur = conn.execute(
                "SELECT id, reason, context, created_at FROM failures ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["context"] = json.loads(d["context"])
            out.append(d)
        return out

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
