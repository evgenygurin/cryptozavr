# Using cryptozavr with OpenCode

OpenCode supports Claude Code's plugin format natively.

1. `gh repo clone evgenygurin/cryptozavr ~/opencode/plugins/cryptozavr`
2. In OpenCode settings → Plugins → Add local plugin → pick the directory.
3. `uv sync --all-extras` inside the plugin directory.
4. Fill `.env` (see main README).
5. Restart OpenCode.

MCP tools appear under the `cryptozavr-research` server. Slash-commands and agents are picked up from `commands/` and `agents/`.
