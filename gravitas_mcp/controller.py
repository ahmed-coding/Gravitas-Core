"""
Cognitive Control Layer — how the agent thinks and progresses.

Enforces deterministic Task State Machine, retries, rollbacks, escalation.
Prevents infinite loops and uncontrolled tool usage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .memory import Memory, _tool_result

# Required states per PRD
class TaskState(str, Enum):
    PLANNING = "PLANNING"
    CODING = "CODING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    FAILED_RETRY = "FAILED_RETRY"
    ROLLBACK = "ROLLBACK"
    COMPLETED = "COMPLETED"


@dataclass
class RetryPolicy:
    """Per-step retry limits and rollback triggers."""

    max_retries_per_step: int = 3
    identical_failure_threshold: int = 2  # trigger rollback after N identical failures
    hard_stop_on_repeated_failure: bool = True


@dataclass
class TaskContext:
    """Current task execution context."""

    task_id: str
    goal: str
    state: TaskState
    step_retry_count: int = 0
    last_failure_reason: str | None = None
    identical_failure_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# Default policy
DEFAULT_POLICY = RetryPolicy()


class Controller:
    """
    Deterministic control plane: state transitions, retries, rollbacks.
    """

    def __init__(self, memory: Memory, policy: RetryPolicy | None = None):
        self._memory = memory
        self._policy = policy or DEFAULT_POLICY
        self._context: TaskContext | None = None

    def create_task(self, goal: str, task_id: str | None = None) -> dict[str, Any]:
        """Create a new task and set state to PLANNING."""
        import time
        import os
        tid = task_id or f"task_{int(time.time() * 1000)}_{os.urandom(4).hex()}"
        self._memory.upsert_task(tid, goal, TaskState.PLANNING.value)
        self._context = TaskContext(task_id=tid, goal=goal, state=TaskState.PLANNING)
        return _tool_result(
            "success",
            observations={
                "task_id": tid,
                "goal": goal,
                "state": TaskState.PLANNING.value,
            },
            next_recommended_action="Proceed with planning; then transition to CODING.",
        )

    def transition(self, task_id: str, new_state: str) -> dict[str, Any]:
        """Transition task to new state if valid."""
        valid = {s.value for s in TaskState}
        if new_state not in valid:
            return _tool_result(
                "failure",
                errors=[f"Invalid state: {new_state}. Valid: {list(valid)}"],
                next_recommended_action="Use one of the required states.",
            )
        task = self._memory.get_task(task_id)
        goal = (task.get("goal") or "") if task else ""
        self._memory.upsert_task(task_id, goal, new_state)
        if self._context and self._context.task_id == task_id:
            self._context.state = TaskState(new_state)
            if new_state in (TaskState.COMPLETED.value, TaskState.ROLLBACK.value):
                self._context.step_retry_count = 0
                self._context.identical_failure_count = 0
        return _tool_result(
            "success",
            observations={"task_id": task_id, "state": new_state},
            next_recommended_action=_next_action_for_state(new_state),
        )

    def record_step_failure(self, task_id: str, reason: str) -> dict[str, Any]:
        """Record a step failure; may trigger FAILED_RETRY or ROLLBACK."""
        if not self._context or self._context.task_id != task_id:
            self._context = TaskContext(task_id=task_id, goal="", state=TaskState.FAILED_RETRY)
        self._context.step_retry_count += 1
        if reason == self._context.last_failure_reason:
            self._context.identical_failure_count += 1
        else:
            self._context.last_failure_reason = reason
            self._context.identical_failure_count = 1

        if self._context.identical_failure_count >= self._policy.identical_failure_threshold:
            self._memory.upsert_task(task_id, self._context.goal or "", TaskState.ROLLBACK.value)
            return _tool_result(
                "success",
                observations={
                    "task_id": task_id,
                    "state": TaskState.ROLLBACK.value,
                    "reason": "Repeated identical failure; mandatory rollback.",
                },
                next_recommended_action="Perform rollback using canonical state; then re-plan.",
            )
        if self._context.step_retry_count >= self._policy.max_retries_per_step:
            self._memory.upsert_task(task_id, self._context.goal or "", TaskState.FAILED_RETRY.value)
            return _tool_result(
                "success",
                observations={
                    "task_id": task_id,
                    "state": TaskState.FAILED_RETRY.value,
                    "reason": "Max retries per step exceeded.",
                },
                next_recommended_action="Escalate or rollback; do not retry same step again.",
            )
        self._memory.upsert_task(task_id, self._context.goal or "", TaskState.FAILED_RETRY.value)
        return _tool_result(
            "success",
            observations={
                "task_id": task_id,
                "state": TaskState.FAILED_RETRY.value,
                "retry_count": self._context.step_retry_count,
            },
            next_recommended_action="Retry with a different approach; avoid repeating same failure.",
        )

    def get_state(self, task_id: str) -> dict[str, Any]:
        """Return current task state and policy info."""
        last = self._memory.get_last_state()
        tasks = last.get("observations", {}).get("active_task") or last.get("observations", {}).get("last_snapshot")
        # Prefer explicit task lookup via resume
        resume = self._memory.resume_task(task_id)
        if resume.get("status") != "success":
            return resume
        task = resume["observations"].get("task")
        if not task:
            return _tool_result("failure", errors=["Task not found"], next_recommended_action="Create or list tasks.")
        return _tool_result(
            "success",
            observations={
                "task_id": task_id,
                "state": task["state"],
                "goal": task["goal"],
                "policy": {
                    "max_retries_per_step": self._policy.max_retries_per_step,
                    "identical_failure_threshold": self._policy.identical_failure_threshold,
                },
            },
            next_recommended_action=_next_action_for_state(task["state"]),
        )

    def is_complete(self, task_id: str) -> bool:
        """Return True if task is COMPLETED or ROLLBACK (terminal)."""
        resume = self._memory.resume_task(task_id)
        if resume.get("status") != "success":
            return False
        state = (resume.get("observations") or {}).get("task", {}).get("state")
        return state in (TaskState.COMPLETED.value, TaskState.ROLLBACK.value)


def _next_action_for_state(state: str) -> str:
    """Recommended next action per state."""
    actions = {
        TaskState.PLANNING.value: "Complete plan; transition to CODING.",
        TaskState.CODING.value: "Apply code changes; transition to EXECUTING.",
        TaskState.EXECUTING.value: "Run commands/tests; transition to VERIFYING.",
        TaskState.VERIFYING.value: "Verify via terminal/browser; then COMPLETED or retry.",
        TaskState.FAILED_RETRY.value: "Retry with different approach or escalate.",
        TaskState.ROLLBACK.value: "Restore from canonical state; re-plan.",
        TaskState.COMPLETED.value: "Task done; no further action.",
    }
    return actions.get(state, "Check state and proceed.")
