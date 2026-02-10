# TODO: MCP Server Fix & GitHub Workflow

## Issues Fixed:
1. **MCP Import Path Fixed** - Updated from v0.x to v1.x API
2. **Visible Browser Window** - Browser now opens in visible mode
3. **Mouse Hover Added** - New `browser_hover` tool for element interaction
4. **GitHub Workflow Created** - CI/CD for building, testing, and publishing

## Files Modified:
- `gravitas_mcp/server.py` - Fixed MCP import, added browser_hover handler
- `gravitas_mcp/browser.py` - Visible browser, added hover method
- `pyproject.toml` - Updated dependencies, added sdist config
- `.github/workflows/ci.yml` - New CI/CD workflow
- `README.md` - Added Blackbox/Cursor config examples

## GitHub Import Format:
```json
{
  "mcpServers": {
    "gravitas-mcp": {
      "command": "uvx",
      "args": [
        "run",
        "git+https://github.com/ahmed-coding/Gravitas-Core.git"
      ]
    }
  }
}
```

