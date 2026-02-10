# Gravitas-Core-MCP

**Version:** 1.0.0  
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

**Requires [UV](https://docs.astral.sh/uv/) to be installed and `uvx` in your PATH.** If you see `spawn uvx ENOENT`, use the [localhost config](#run-from-localhost-local-clone) below instead (no uv/uvx needed).

**Cursor** — e.g. `~/.cursor/mcp.json` or `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "gravitas-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/ahmed-coding/Gravitas-Core.git",
        "Gravitas-Core-MCP"
      ]
    }
  }
}
```

**With a specific ref (branch or tag):**

```json
{
  "mcpServers": {
    "gravitas-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/ahmed-coding/Gravitas-Core.git@main",
         "Gravitas-Core-MCP"
      ]
    }
  }
}
```

**Cloned repo (run from local path):**

```json
{
  "mcpServers": {
    "gravitas-mcp": {
      "command": "/path/to/Gravitas-Core/.venv/bin/python",
      "args": ["-m", "gravitas_mcp.server"]
    }
  }
}
```

*(Create the venv first: `cd /path/to/Gravitas-Core && uv venv && uv sync`, then use `.venv/bin/python` in `command`.)*

## Run from localhost (local clone)

Use the server from a clone on your machine so you can develop and test without GitHub.

### 1. Clone and install (one time)

```bash
git clone https://github.com/ahmed-coding/Gravitas-Core.git
cd Gravitas-Core
uv sync
```

*(If you don’t have [UV](https://docs.astral.sh/uv/): `pip install uv` or use `python -m venv .venv && .venv/bin/pip install -e .` and then use `.venv/bin/python` in the configs below.)*

### 2. Run the server in a terminal (optional)

```bash
cd /path/to/Gravitas-Core
uv run python -m gravitas_mcp.server
```
**OR with uvicorn**

```bash
cd /path/to/Gravitas-Core
uvicorn gravitas_mcp.mcp_webapp:starlette_app
```

The server uses stdio; your MCP client (Cursor, etc.) will start it automatically when configured.

### 3. MCP config for localhost

**Option A — Use this repo as the Cursor project (recommended)**  
Open the `Gravitas-Core` folder in Cursor. The project already includes `.cursor/mcp.json` so the **gravitas** MCP server runs from your local clone (no GitHub needed).

**Option B — Use from any project (user-level config)**  
Copy this into `~/.cursor/mcp.json` and replace `YOUR_PATH` with the full path to your clone (e.g. `/home/ahmed/Desktop/Gravitas-MCP-Core` or `C:\Users\You\Gravitas-Core`):

```json
{
  "mcpServers": {
    "gravitas-mcp": {
      "command": "YOUR_PATH/.venv/bin/python",
      "args": ["-m", "gravitas_mcp.server"]
    }
  }
}
```

On Windows use `YOUR_PATH\\.venv\\Scripts\\python.exe` and `"args": ["-m", "gravitas_mcp.server"]`.

**Option C — Use `uv` with project path (no venv path)**  
If Cursor runs the command with a fixed cwd, you can use:

```json
{
  "mcpServers": {
    "gravitas-mcp": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/Gravitas-Core", "python", "-m", "gravitas_mcp.server"]
    }
  }
}
```

Replace `/path/to/Gravitas-Core` with your actual clone path.

## Troubleshooting

| Error                   | Fix                                                                                                                                                                                                                                                                                                                                                      |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`spawn uvx ENOENT`**  | Cursor can’t find `uvx`. Either install [UV](https://docs.astral.sh/uv/) and ensure `uvx` is in your PATH, or **use localhost**: open this repo in Cursor (so it uses the project’s `.cursor/mcp.json`) and run `python3 -m venv .venv && .venv/bin/pip install -e .` in the project folder. The project config uses the venv’s Python, so no uv needed. |
| **Server not starting** | Ensure `.venv` exists: from the project root run `python3 -m venv .venv` then `.venv/bin/pip install -e .` (or `uv sync` if you have uv).                                                                                                                                                                                                                |

## MCP client configuration

### Blackbox / Cursor (user-level config)

Add to `~/.config/Code/User/globalStorage/blackboxapp.blackboxagent/settings/blackbox_mcp_settings.json`:

```json
{
  "mcpServers": {
    "gravitas-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/ahmed-coding/Gravitas-Core.git",
        "Gravitas-Core-MCP"
      ]
    }
  }
}
```

**With a specific ref (branch or tag):**

```json
{
  "mcpServers": {
    "gravitas-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/ahmed-coding/Gravitas-Core.git@v1.1.0",
        "Gravitas-Core-MCP"
      ]
    }
  }
}
```

**From local clone:**

```json
{
  "mcpServers": {
    "gravitas-mcp": {
      "command": "/path/to/Gravitas-Core/.venv/bin/python",
      "args": ["-m", "gravitas_mcp.server"],
      "env": {
        "PYTHONPATH": "/path/to/Gravitas-Core"
      },
      "type": "stdio"
    }
  }
}
```

### Cursor (project-level config)

Add to `.cursor/mcp.json` or `.vscode/mcp.json`:

```json
{
  "mcpServers": {
    "gravitas-mcp": {
      "command": "uvx",
      "args": ["Gravitas-Core-MCP"]
    }
  }
}
```

## Repository structure

```
Gravitas-Core-MCP/
├── gravitas_mcp/
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

| Tool                                                           | Description                                                                      |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `get_last_state`                                               | Last known state (snapshot + active task)                                        |
| `get_canonical_state`                                          | Last verified immutable state (rollback/recovery)                                |
| `record_failure`                                               | Record failed strategy/command                                                   |
| `resume_task`                                                  | Load task context for resumption                                                 |
| `controller_create_task`                                       | Create task, state PLANNING                                                      |
| `controller_transition`                                        | Move task to PLANNING/CODING/EXECUTING/VERIFYING/FAILED_RETRY/ROLLBACK/COMPLETED |
| `controller_record_step_failure`                               | Record step failure (may trigger rollback)                                       |
| `terminal_execute`                                             | Run shell command with timeout                                                   |
| `browser_navigate` / `browser_snapshot` / `browser_screenshot` | UI verification                                                                  |
| `project_get_map`                                              | Project structure with noise filtering                                           |
| `get_model_resume_package`                                     | Model handover package                                                           |

## Brain database

State is stored in `.gravitas_brain.db` in the project root (or cwd). Optional: add `.gravitas_brain.db` to `.gitignore` if you do not want to commit it.

## License

MIT — Local-first, user-sovereign, safe by default.
