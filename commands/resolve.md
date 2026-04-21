---
description: Resolve a user-input symbol string (fuzzy) to a canonical venue symbol.
argument-hint: <user_input> [venue]
allowed-tools: ["mcp__plugin_cryptozavr_cryptozavr-research__resolve_symbol"]
---

Resolve the user's input to a canonical symbol on the requested venue.

Parse `$ARGUMENTS` as `<user_input> [venue]`. If `venue` is omitted, default to `kucoin`.

Call `resolve_symbol` with those values. Render:
- `native_symbol` (bold)
- `base` / `quote` pair
- `market_type`

If the tool surfaces a SymbolNotFoundError, tell the user it wasn't found and suggest `/cryptozavr:trending` for discovery.
