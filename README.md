# Gravitas-Core-MCP

**Version:** 1.1.0  
**Role:** Core System Blueprint / Autonomous AI Control Plane  
**Target Platforms:** VS Code (Cline / Claude Dev), Cursor, Windsurf, Claude Desktop

Production-grade, autonomous **Model Context Protocol (MCP) server** that elevates AI models from stateless code generators into **persistent, self-verifying software engineers**.

## Features

- **Persistent memory** — SQLite-backed task ledger, context snapshots, canonical state, failure memory, tool usage patterns
- **Cognitive control** — Deterministic task state machine (PLANNING → CODING → EXECUTING → VERIFYING → COMPLETED / FAILED_RETRY / ROLLBACK), retry policies, rollback on repeated failures
- **Terminal engine** — Shell execution with timeout, cwd isolation, allowlist/denylist, background process management
- **Browser engine** — Playwright-based navigation, DOM snapshot, screenshots, console error streaming
- **Project intelligence** — Recursive structure analysis with noise filtering (`.git`, `node_modules`, build artifacts)
- **Model handover** — Auto-generated Model Resume Package (goal, task, constraints, failures, safe/do-not-touch files) for model swap, editor restart, or crash recovery

## Requirements

- Python 3.10+
- [UV](https://docs.astral.sh/uv/) (Astral) for install/run
- **Browser:** Uses **existing Chrome or Edge** on your machine when available — **no `playwright install` required**. If you have neither, run `playwright install chromium` once.

## Installation

**No local install needed** — run directly from GitHub (see [Use it from GitHub](#use-it-from-github-direct-configuration) below):

```bash
uvx run git+https://github.com/ahmed-coding/Gravitas-Core.git
```

Or install from PyPI:

```bash
# Install and run via uvx (no global install)
uvx Gravitas-Core-MCP
```

Or install into a project:

```bash
uv add Gravitas-Core-MCP
# Then run: uv run Gravitas-Core-MCP
```

**Browser tools:** If you already have Chrome or Edge installed, nothing else is needed. Otherwise, run once: `uv run playwright install chromium`.

## Use it from GitHub (direct configuration)

Run the server **directly from this repository** with **no local installation** — UV fetches the repo and runs it. Repository: [ahmed-coding/Gravitas-Core](https://github.com/ahmed-coding/Gravitas-Core).

The repo includes a **GitHub Action** (`.github/workflows/ci.yml`) that runs tests and verifies the server starts; you can see it in the Actions tab after push.

### Run from GitHub with uvx

```bash
uvx run git+https://github.com/ahmed-coding/Gravitas-Core.git
```

Or pin a branch/tag:

```bash
uvx run "git+https://github.com/ahmed-coding/Gravitas-Core.git@main"
uvx run "git+https://github.com/ahmed-coding/Gravitas-Core.git@v1.1.0"
```

### MCP client config (GitHub direct)

Point your MCP client at the GitHub repo so it runs the server from source.

**Cursor** — e.g. `~/.cursor/mcp.json` or `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "antigravity": {
      "command": "uvx",
      "args": [
        "run",
        "git+https://github.com/ahmed-coding/Gravitas-Core.git"
      ]
    }
  }
}
```

**With a specific ref (branch or tag):**

```json
{
  "mcpServers": {
    "antigravity": {
      "command": "uvx",
      "args": [
        "run",
        "git+https://github.com/ahmed-coding/Gravitas-Core.git@main"
      ]
    }
  }
}
```

**Cloned repo (run from local path):**

```json
{
  "mcpServers": {
    "antigravity": {
      "command": "/path/to/Gravitas-Core/.venv/bin/python",
      "args": ["-m", "antigravity_mcp.server"]
    }
  }
}
```

*(Create the venv first: `cd /path/to/Gravitas-Core && uv venv && uv sync`, then use `.venv/bin/python` in `command`.)*

## MCP client configuration

### Cursor

Add to Cursor MCP settings (e.g. `~/.cursor/mcp.json` or project `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "antigravity": {
      "command": "uvx",
      "args": ["Gravitas-Core-MCP"]
    }
  }
}
```

### VS Code (Cline / Claude Dev)

Use the same `mcpServers` block in your MCP config; point `command` to `uvx` and `args` to `["Gravitas-Core-MCP"]`.

### Claude Desktop

In Claude Desktop config, add the `antigravity` server with `uvx` and `Gravitas-Core-MCP` as above.

## Repository structure

```
Gravitas-Core-MCP/
├── antigravity_mcp/
│   ├── __init__.py
│   ├── server.py      # MCP entrypoint, tool wiring
│   ├── memory.py      # SQLite persistence, task ledger, state APIs
│   ├── controller.py  # State machine, retry/rollback
│   ├── terminal.py    # Subprocess execution, allowlist/denylist
│   ├── browser.py     # Playwright automation
│   └── project_intel.py # Structure analysis, noise filtering
├── pyproject.toml
├── README.md
├── LICENSE
└── .gitignore
```

## Tool contract

All tools return deterministic JSON:

```json
{
  "status": "success | failure",
  "observations": {},
  "errors": [],
  "next_recommended_action": ""
}
```

## Mandatory tools (PRD)

| Tool | Description |
|------|-------------|
| `get_last_state` | Last known state (snapshot + active task) |
| `get_canonical_state` | Last verified immutable state (rollback/recovery) |
| `record_failure` | Record failed strategy/command |
| `resume_task` | Load task context for resumption |
| `controller_create_task` | Create task, state PLANNING |
| `controller_transition` | Move task to PLANNING/CODING/EXECUTING/VERIFYING/FAILED_RETRY/ROLLBACK/COMPLETED |
| `controller_record_step_failure` | Record step failure (may trigger rollback) |
| `terminal_execute` | Run shell command with timeout |
| `browser_navigate` / `browser_snapshot` / `browser_screenshot` | UI verification |
| `project_get_map` | Project structure with noise filtering |
| `get_model_resume_package` | Model handover package |

## Brain database

State is stored in `.antigravity_brain.db` in the project root (or cwd). Optional: add `.antigravity_brain.db` to `.gitignore` if you do not want to commit it.

## License

MIT — Local-first, user-sovereign, safe by default.
