# Using cryptozavr with Cursor

Cursor reads the same `.mcp.json`. Install:

1. Clone to a directory Cursor watches: `gh repo clone evgenygurin/cryptozavr ~/.cursor/plugins/cryptozavr`
2. Open the folder in Cursor. Confirm the MCP server registers in Settings → MCP.
3. Slash-commands surface as Cursor Commands.

Limitations (Cursor parity is partial):
- Skills are read for Agent system prompts but not searchable via a dedicated UI.
- The SessionStart hook doesn't fire in Cursor — run `/cryptozavr:health` manually after install.
