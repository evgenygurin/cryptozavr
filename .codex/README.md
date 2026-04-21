# Using cryptozavr with OpenAI Codex

Codex-cli reads the same `.mcp.json` + skills/commands as Claude Code. Install steps:

1. `gh repo clone evgenygurin/cryptozavr ~/codex-plugins/cryptozavr`
2. Point Codex at the plugin directory: `codex plugins add ~/codex-plugins/cryptozavr`
3. Copy `.env.example` → `.env` and fill credentials (see main README).
4. `uv sync --all-extras` inside the plugin directory to install Python deps.
5. Restart codex. Slash-commands (`/cryptozavr:ticker` …) and the `crypto-researcher` agent become available.

Supported features on Codex:
- ✅ MCP tools (get_ticker, get_ohlcv, get_order_book, get_trades)
- ✅ Slash commands (commands/*.md)
- ✅ Agents (agents/*.md)
- ✅ Skills (skills/*/SKILL.md)
- ⚠️  SessionStart hook — Codex fires SessionStart; banner prints on startup.
