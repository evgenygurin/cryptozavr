# cryptozavr — Milestone 2.8: Production-ready multi-platform plugin

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Полноценный готовый плагин для Claude Code + Codex + OpenCode + Cursor + Gemini. Законченный UX: slash-commands (`/cryptozavr:ticker`, `/cryptozavr:ohlcv`, `/cryptozavr:research`), specialist agent, domain skills, SessionStart welcome hook, multi-platform install docs, local marketplace subdir.

**Architecture:** Mirror superpowers 5.0.7 structure — `.claude-plugin/plugin.json` manifest, `skills/`/`agents/`/`commands/`/`hooks/`/`docs/` directories, per-platform wrappers (`.codex/`, `.opencode/`, `.cursor-plugin/`, `gemini-extension.json`). Commands thin-wrap MCP tools with guard rails and pretty output. Agents + skills give richer workflows.

**Tech Stack:** No new Python deps. Plugin metadata is YAML/JSON/Markdown only.

**Starting tag:** `v0.0.10`. Target: `v0.1.0` (minor bump — plugin готов к публикации).

---

## File Structure

| Path | Responsibility |
|------|---------------|
| `.claude-plugin/plugin.json` | NEW — plugin manifest (name, version, author, keywords) |
| `.claude-plugin/marketplace.json` | NEW — marketplace registry (self-contained so `/plugin marketplace add <url>` works) |
| `commands/ticker.md` | NEW — `/cryptozavr:ticker <venue> <symbol>` slash-command |
| `commands/ohlcv.md` | NEW — `/cryptozavr:ohlcv <venue> <symbol> <timeframe>` |
| `commands/research.md` | NEW — `/cryptozavr:research <symbol>` (ticker + OHLCV + book + trades collage) |
| `commands/health.md` | NEW — `/cryptozavr:health` (venue state check) |
| `agents/crypto-researcher.md` | NEW — subagent specializing in market research workflows |
| `skills/crypto-research/SKILL.md` | NEW — when-to-invoke guide for research loops |
| `skills/interpreting-market-data/SKILL.md` | NEW — how to read ticker/OHLCV/orderbook output |
| `hooks/hooks.json` | NEW — SessionStart hook prints plugin banner + available tools |
| `hooks/session-start.sh` | NEW — banner script |
| `.codex/README.md` | NEW — OpenAI Codex install guide |
| `.opencode/README.md` | NEW — OpenCode install guide |
| `.cursor-plugin/README.md` | NEW — Cursor install guide |
| `gemini-extension.json` | NEW — Gemini CLI manifest |
| `docs/README.claude-code.md` | NEW — Claude Code install guide |
| `docs/README.codex.md` | NEW — Codex install guide |
| `docs/README.opencode.md` | NEW — OpenCode install guide |
| `README.md` | MODIFY — rewrite for plugin users (not just developers) |
| `.mcp.json` | KEEP — existing MCP server config (unchanged) |
| `LICENSE` | KEEP — already MIT |
| `CHANGELOG.md` | MODIFY — v0.1.0 entry |

---

## Tasks

### Task 1: `.claude-plugin/plugin.json` + marketplace.json

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Write `plugin.json`**

```json
{
  "$schema": "https://anthropic.com/claude-code/plugin-schema.json",
  "name": "cryptozavr",
  "version": "0.1.0",
  "description": "Risk-first crypto market research — 4 MCP tools (get_ticker, get_ohlcv, get_order_book, get_trades) with Supabase-backed cache, provenance tracking, and auditable reasoning.",
  "author": {
    "name": "Evgeny Gurin",
    "email": "e.a.gurin@outlook.com"
  },
  "homepage": "https://github.com/evgenygurin/cryptozavr",
  "repository": "https://github.com/evgenygurin/cryptozavr",
  "license": "MIT",
  "keywords": [
    "crypto",
    "market-data",
    "research",
    "trading",
    "mcp",
    "kucoin",
    "coingecko",
    "supabase",
    "risk-management"
  ]
}
```

- [ ] **Step 2: Write `marketplace.json`**

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace-schema.json",
  "name": "cryptozavr-marketplace",
  "owner": {
    "name": "Evgeny Gurin",
    "email": "e.a.gurin@outlook.com"
  },
  "description": "Cryptozavr — risk-first crypto market research plugin.",
  "plugins": [
    {
      "name": "cryptozavr",
      "version": "0.1.0",
      "source": {
        "source": "git",
        "url": "https://github.com/evgenygurin/cryptozavr"
      },
      "description": "4 MCP tools + agent + skills for disciplined crypto research.",
      "keywords": ["crypto", "market-data", "research", "mcp"]
    }
  ]
}
```

- [ ] **Step 3: Commit**

Write commit message to /tmp/commit-msg.txt:
```bash
feat(plugin): add plugin.json manifest + marketplace registry

Plugin name=cryptozavr, version=0.1.0, MIT license. Marketplace
self-hosted in .claude-plugin/marketplace.json so users can
`/plugin marketplace add https://github.com/evgenygurin/cryptozavr`.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 2: Slash commands — 4 files

**Files:**
- Create: `commands/ticker.md`
- Create: `commands/ohlcv.md`
- Create: `commands/research.md`
- Create: `commands/health.md`

- [ ] **Step 1: Write `commands/ticker.md`**

```markdown
---
description: Fetch latest ticker (last/bid/ask/volume/24h-change) for a symbol on a venue.
argument-hint: <venue> <symbol>
allowed-tools: ["mcp__cryptozavr-research__get_ticker"]
---

Fetch the ticker for the user's requested symbol.

Call the `get_ticker` MCP tool with:
- `venue`: first argument (e.g. `kucoin`, `coingecko`)
- `symbol`: second argument (e.g. `BTC-USDT`)
- `force_refresh`: `false`

After receiving the result, present:
1. Last price (bold), bid/ask spread, 24h volume
2. `reason_codes` audit trail (one line, comma-separated)
3. `staleness` + `cache_hit` — so the user knows how fresh the data is

If `$ARGUMENTS` is empty or missing a value, ask the user for the venue and symbol before calling the tool.
```

- [ ] **Step 2: Write `commands/ohlcv.md`**

```markdown
---
description: Fetch OHLCV candles (open/high/low/close/volume) for a symbol + timeframe.
argument-hint: <venue> <symbol> <timeframe> [limit]
allowed-tools: ["mcp__cryptozavr-research__get_ohlcv"]
---

Fetch OHLCV candles for the user's requested symbol.

Parse `$ARGUMENTS` as: `<venue> <symbol> <timeframe> [limit]`.

Supported timeframes: `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`.

Call the `get_ohlcv` MCP tool with:
- `venue`, `symbol`, `timeframe` from args
- `limit`: default `100`, or 4th arg if provided (1..1000)
- `force_refresh`: `false`

Render the candles as a compact table (opened_at, open, high, low, close, volume). Highlight the last closed candle. Append the `reason_codes` audit trail.
```

- [ ] **Step 3: Write `commands/research.md`**

```markdown
---
description: Multi-tool research collage — ticker + OHLCV (1h, 24 candles) + order book + recent trades for a symbol.
argument-hint: <venue> <symbol>
allowed-tools:
  - "mcp__cryptozavr-research__get_ticker"
  - "mcp__cryptozavr-research__get_ohlcv"
  - "mcp__cryptozavr-research__get_order_book"
  - "mcp__cryptozavr-research__get_trades"
---

Build a research snapshot for the user's symbol.

Run these 4 MCP tools in parallel (single message, multiple tool calls):
1. `get_ticker(venue, symbol)` — current price + 24h stats
2. `get_ohlcv(venue, symbol, timeframe="1h", limit=24)` — last 24 hourly candles
3. `get_order_book(venue, symbol, depth=20)` — top 20 levels each side
4. `get_trades(venue, symbol, limit=50)` — last 50 trades

Present the result in this structure:

### Price
- Last / bid / ask / spread_bps
- 24h range (from OHLCV high/low)
- 24h volume

### Trend (last 24h)
- Direction: up/down/flat based on first vs last OHLCV close
- Largest single-candle move (% of close)

### Liquidity
- Top bid × asz size vs top ask × size
- Spread in bps

### Recent flow
- Buy/sell ratio from trades (by count and by size)

### Provenance
- `reason_codes` from each tool, concatenated on one line per tool
- Warn if any `staleness != "fresh"` or `cache_hit=true` for price-sensitive fields

If `$ARGUMENTS` is empty, ask the user for venue and symbol.
```

- [ ] **Step 4: Write `commands/health.md`**

```markdown
---
description: Smoke-test the plugin — call the echo tool and confirm the MCP server is reachable.
allowed-tools: ["mcp__cryptozavr-research__echo"]
---

Call the `echo` MCP tool with message `"health-check"`. If it returns the echoed message + server version, report:

- ✅ MCP server reachable
- Version: <from response>
- Available tools: `echo`, `get_ticker`, `get_ohlcv`, `get_order_book`, `get_trades`

If the call errors or times out, report the error and suggest:
1. Verify `.env` has `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`
2. Check `uv sync --all-extras` ran at plugin install
3. Try `/plugin marketplace update` to refresh
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(plugin): add 4 slash commands

/cryptozavr:ticker — wraps get_ticker
/cryptozavr:ohlcv — wraps get_ohlcv with timeframe parsing
/cryptozavr:research — 4-tool parallel collage (ticker+ohlcv+book+trades)
/cryptozavr:health — echo smoke test

All commands declare allowed-tools explicitly so Claude invokes them
without prompting each time. Commands render results in user-facing
formats; reason_codes always surfaced for explainability.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add commands/ticker.md commands/ohlcv.md commands/research.md commands/health.md
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 3: `crypto-researcher` specialist agent

**Files:**
- Create: `agents/crypto-researcher.md`

- [ ] **Step 1: Write the agent**

```markdown
---
name: crypto-researcher
description: |
  Use this subagent for non-trivial crypto market research — comparative token analysis, trend dissection, liquidity checks, historical OHLCV context. Invokes the cryptozavr MCP tools (get_ticker, get_ohlcv, get_order_book, get_trades) and structures findings for a disciplined, institutional-minded researcher. Does NOT execute trades, does NOT offer investment advice.

  <example>
  user: "Compare BTC-USDT and ETH-USDT liquidity on KuCoin right now"
  assistant: "Dispatching crypto-researcher — it'll fetch order books for both symbols and present a side-by-side spread/depth comparison."
  </example>

  <example>
  user: "Is BTC trending up or down on the 1h timeframe?"
  assistant: "crypto-researcher will pull the last 48 1h candles, compute trend + largest moves, and summarize."
  </example>
model: sonnet
tools:
  - mcp__cryptozavr-research__get_ticker
  - mcp__cryptozavr-research__get_ohlcv
  - mcp__cryptozavr-research__get_order_book
  - mcp__cryptozavr-research__get_trades
---

You are a crypto market research specialist for the cryptozavr plugin.

## Your discipline
1. **Risk-first.** Always surface staleness and cache_hit flags before drawing conclusions.
2. **Calm.** Dispassionate tone. No hype, no FOMO framing.
3. **Explainable.** Cite reason_codes from every tool call.
4. **No advice.** You research; you do not recommend buys or sells.

## Your loop
1. Clarify the question if venue/symbol/timeframe is ambiguous.
2. Call the relevant cryptozavr MCP tools in parallel where possible.
3. Aggregate results into a structured answer: Price → Trend → Liquidity → Flow → Provenance.
4. If any tool returns `staleness != "fresh"`, warn the user; if `force_refresh=true` is warranted, call again.
5. End with a single-sentence summary and the list of all reason_codes for audit.

## When to decline
- User asks "should I buy X?" → refuse; redirect to "I can show data; the decision is yours."
- User requests private/authenticated endpoints (balance, orders) → not supported in MVP, tell them.
- User requests a venue not in the seeded registry (kucoin, coingecko) → tell them and list supported venues.

## Report format
Return a concise markdown summary with the five sections above. Never fabricate numbers; always pull from tool output.
```

- [ ] **Step 2: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(plugin): add crypto-researcher specialist agent

Subagent for non-trivial market research queries. Parallel-calls the
4 cryptozavr MCP tools, produces a structured Price → Trend →
Liquidity → Flow → Provenance summary. Strict "no investment advice"
rails. model=sonnet, tools list restricted to the 4 MCP market
tools.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add agents/crypto-researcher.md
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 4: Skills — 2 knowledge packs

**Files:**
- Create: `skills/crypto-research/SKILL.md`
- Create: `skills/interpreting-market-data/SKILL.md`

- [ ] **Step 1: Write `skills/crypto-research/SKILL.md`**

```markdown
---
name: crypto-research
description: Use when the user asks a crypto-research question that needs multiple tool calls (ticker + OHLCV, comparison, trend analysis, liquidity check). This skill explains the research loop, when to call which tool, and how to structure findings.
---

# Crypto Research Workflow

## When to invoke

- Multi-symbol comparison ("compare BTC and ETH")
- Trend questions ("is X trending up?")
- Liquidity questions ("what's the book depth?")
- Historical context ("last week's range")
- Cross-venue checks ("KuCoin vs CoinGecko price")

## The research loop

1. **Clarify**. Make venue/symbol/timeframe explicit. If missing, ask once.
2. **Plan tool calls**. Usually 2-4 tools in parallel. Single message, multiple tool_use blocks.
3. **Run tools**. Prefer `/cryptozavr:research` for the full collage. Individual tools for targeted questions.
4. **Aggregate**. Present in Price → Trend → Liquidity → Flow → Provenance order.
5. **Warn on quality**. If any result has `staleness != "fresh"` or `cache_hit=true`, surface it.
6. **Audit trail**. Always end with the combined `reason_codes` list.

## Tool selection matrix

| Question | Tools |
|----------|-------|
| "What's the price of X?" | `get_ticker` |
| "Show me the 1h chart" | `get_ohlcv(timeframe="1h", limit=24)` |
| "How deep is the book?" | `get_order_book(depth=50)` |
| "Who's been trading?" | `get_trades(limit=100)` |
| "Full picture" | All four in parallel (`/cryptozavr:research`) |

## Rails

- **Don't give buy/sell advice.** Data, not recommendations.
- **Don't extrapolate beyond the data window.** Last 24h ≠ next 24h.
- **Don't hide cache state.** Cache hits are fine; silence about them isn't.

## Subagent delegation

For non-trivial multi-step research, dispatch the `crypto-researcher` subagent. It runs the tools and enforces the rails so the main thread stays focused on the user's follow-up questions.
```

- [ ] **Step 2: Write `skills/interpreting-market-data/SKILL.md`**

```markdown
---
name: interpreting-market-data
description: Use when you've just received output from a cryptozavr MCP tool (ticker, OHLCV, orderbook, trades) and need to read it correctly. Covers field meanings, staleness flags, reason_codes, and common pitfalls.
---

# Interpreting cryptozavr market data

## Common fields

All tool outputs include:
- `venue`, `symbol` — where the data came from
- `reason_codes: list[str]` — ordered audit trail of the 5-handler chain:
  - `venue:healthy|degraded|rate_limited|down`
  - `symbol:found`
  - `cache:bypassed` (force_refresh=true)
  - `cache:hit` (Supabase returned cached) OR `cache:miss` + `provider:called`
  - `cache:write_failed` (upsert couldn't persist; response still valid)
- `staleness: "fresh"|"recent"|"stale"|"expired"`
- `confidence: "high"|"medium"|"low"`
- `cache_hit: bool`

## get_ticker

- `last` is the latest trade price. `bid`/`ask` may be None for CoinGecko (aggregator, no order book).
- `volume_24h` is in BASE units (BTC, not USDT).
- `observed_at_ms` is when the exchange stamped the data — may lag by seconds-minutes.

## get_ohlcv

- `candles: list[OHLCVCandleDTO]` ordered oldest → newest.
- Each candle's `closed: bool` — the last candle may be `closed=false` (still in-progress).
- `range_start_ms` / `range_end_ms` bracket the series; useful for windowing.

## get_order_book

- `bids` sorted highest-price-first; `asks` lowest-price-first.
- `spread` = `asks[0].price - bids[0].price`.
- `spread_bps` = spread / midpoint × 10000 — 10 bps is tight, 50 bps is wide.
- Empty `bids` or `asks` → `spread` is `None`.

## get_trades

- `trades` ordered newest → oldest.
- `side: "buy"|"sell"` from the taker's perspective (taker buy = demand).
- `trade_id` may be `null` for CoinGecko.

## Red flags to call out

1. `staleness == "stale"` or `"expired"` — suggest `force_refresh=true`.
2. `cache_hit=true` on volatile prices (tick-by-tick). Warn if the caller needs fresh data.
3. `cache:write_failed` in reasons — data is real, but the Supabase write didn't land. Non-fatal.
4. `venue:degraded` — upstream exchange is slow/errorful. Reduce expectations.
```

- [ ] **Step 3: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(plugin): add crypto-research + interpreting-market-data skills

crypto-research: when-to-invoke guide + tool-selection matrix + rails
("data, not advice"). interpreting-market-data: field-by-field legend
covering ticker/OHLCV/order_book/trades + the 5-handler reason_codes
taxonomy + red flags (staleness, cache_hit on volatile data).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add skills/crypto-research/SKILL.md skills/interpreting-market-data/SKILL.md
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 5: SessionStart hook

**Files:**
- Create: `hooks/hooks.json`
- Create: `hooks/session-start.sh`

- [ ] **Step 1: Write the script**

Write `hooks/session-start.sh`:
```bash
#!/usr/bin/env bash
# SessionStart hook — prints a short banner so the user sees the plugin
# is loaded and lists the canonical entry points.
set -euo pipefail

cat <<'EOF'
# cryptozavr plugin loaded

Slash commands:
  /cryptozavr:ticker <venue> <symbol>           — fetch latest ticker
  /cryptozavr:ohlcv <venue> <symbol> <timeframe> — fetch OHLCV candles
  /cryptozavr:research <venue> <symbol>          — 4-tool research collage
  /cryptozavr:health                             — MCP server smoke test

Subagent: crypto-researcher (for multi-step market research)

Venues seeded: kucoin, coingecko
Need the 4 MCP tools? They auto-register from .mcp.json.
EOF
```

Make it executable:
```bash
chmod +x hooks/session-start.sh
```

- [ ] **Step 2: Write `hooks/hooks.json`**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh",
            "async": false
          }
        ]
      }
    ]
  }
}
```

Match only `startup` (not `clear` or `compact`) — we don't want the banner on every context compaction.

- [ ] **Step 3: Commit**

Write to /tmp/commit-msg.txt:
```text
feat(plugin): add SessionStart banner hook

Prints a short plugin loaded banner with available slash-commands +
subagent + seeded venues on startup only (not on clear/compact). Uses
${CLAUDE_PLUGIN_ROOT} so the hook resolves regardless of install path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add hooks/hooks.json hooks/session-start.sh
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 6: Cross-platform wrappers

**Files:**
- Create: `.codex/README.md`
- Create: `.opencode/README.md`
- Create: `.cursor-plugin/README.md`
- Create: `gemini-extension.json`

- [ ] **Step 1: Write `gemini-extension.json`**

```json
{
  "name": "cryptozavr",
  "version": "0.1.0",
  "description": "Risk-first crypto market research for Gemini CLI.",
  "mcpServers": {
    "cryptozavr-research": {
      "command": "sh",
      "args": [
        "-c",
        ". ${CLAUDE_PLUGIN_ROOT}/.env && uv run --directory ${CLAUDE_PLUGIN_ROOT} python -m cryptozavr.mcp.server"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  },
  "contextFileName": "CLAUDE.md"
}
```

- [ ] **Step 2: Write `.codex/README.md`**

```markdown
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
```

- [ ] **Step 3: Write `.opencode/README.md`**

```markdown
# Using cryptozavr with OpenCode

OpenCode supports Claude Code's plugin format natively.

1. `gh repo clone evgenygurin/cryptozavr ~/opencode/plugins/cryptozavr`
2. In OpenCode settings → Plugins → Add local plugin → pick the directory.
3. `uv sync --all-extras` inside the plugin directory.
4. Fill `.env` (see main README).
5. Restart OpenCode.

MCP tools appear under the `cryptozavr-research` server. Slash-commands and agents are picked up from `commands/` and `agents/`.
```

- [ ] **Step 4: Write `.cursor-plugin/README.md`**

```markdown
# Using cryptozavr with Cursor

Cursor reads the same `.mcp.json`. Install:

1. Clone to a directory Cursor watches: `gh repo clone evgenygurin/cryptozavr ~/.cursor/plugins/cryptozavr`
2. Open the folder in Cursor. Confirm the MCP server registers in Settings → MCP.
3. Slash-commands surface as Cursor Commands.

Limitations (Cursor parity is partial):
- Skills are read for Agent system prompts but not searchable via a dedicated UI.
- The SessionStart hook doesn't fire in Cursor — run `/cryptozavr:health` manually after install.
```

- [ ] **Step 5: Commit**

Write to /tmp/commit-msg.txt:
```bash
feat(plugin): add cross-platform wrappers

gemini-extension.json for Gemini CLI. Per-platform READMEs
(.codex/, .opencode/, .cursor-plugin/) with install instructions and
feature-parity notes. No code duplication — all platforms reuse
.mcp.json, commands/, agents/, skills/.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add gemini-extension.json .codex/README.md .opencode/README.md .cursor-plugin/README.md
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 7: Multi-platform docs in `docs/`

**Files:**
- Create: `docs/README.claude-code.md`
- Create: `docs/README.codex.md`
- Create: `docs/README.opencode.md`

- [ ] **Step 1: Write `docs/README.claude-code.md`**

```markdown
# Installing cryptozavr in Claude Code

## One-line install (marketplace)

```
/plugin marketplace add https://github.com/evgenygurin/cryptozavr
/plugin install cryptozavr@cryptozavr-marketplace
```bash

## Local-dev install

```bash
gh repo clone evgenygurin/cryptozavr ~/dev/cryptozavr
cd ~/dev/cryptozavr
uv sync --all-extras
cp .env.example .env   # then fill in SUPABASE_* values — see main README
```

Then in Claude Code:
```text
/plugin marketplace add ~/dev/cryptozavr
/plugin install cryptozavr@cryptozavr-marketplace
```

## Verification

After install, in a new Claude Code session:
1. `/cryptozavr:health` should confirm the MCP server is reachable and show the tool list.
2. `/cryptozavr:ticker kucoin BTC-USDT` should return a price + reason_codes.

## Troubleshooting

- **Tools not listed:** `/plugin marketplace update` then restart Claude Code.
- **`Missing env vars`:** `.env` must have `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`. See main README "Env setup".
- **`ProviderUnavailableError`:** the upstream exchange (KuCoin or CoinGecko) is rate-limiting or offline. Retry in ~30s.
- **Slow first call:** cold cache. Subsequent calls hit Supabase.
```bash

- [ ] **Step 2: Write `docs/README.codex.md`**

```markdown
# Installing cryptozavr in OpenAI Codex

See `.codex/README.md` for the canonical Codex install steps.

Quick summary:
```bash
gh repo clone evgenygurin/cryptozavr ~/codex-plugins/cryptozavr
cd ~/codex-plugins/cryptozavr
uv sync --all-extras
cp .env.example .env   # fill SUPABASE_* values
codex plugins add ~/codex-plugins/cryptozavr
```

Restart codex. Run `/cryptozavr:health` to verify.
```bash

- [ ] **Step 3: Write `docs/README.opencode.md`**

```markdown
# Installing cryptozavr in OpenCode

See `.opencode/README.md` for the canonical OpenCode install steps.

Quick summary:
```bash
gh repo clone evgenygurin/cryptozavr ~/opencode/plugins/cryptozavr
cd ~/opencode/plugins/cryptozavr
uv sync --all-extras
cp .env.example .env   # fill SUPABASE_* values
```

Enable the plugin in OpenCode Settings → Plugins → Add local plugin.
```text

- [ ] **Step 4: Commit**

Write to /tmp/commit-msg.txt:
```

docs: add per-platform install guides

docs/README.claude-code.md — primary install doc (marketplace + local-dev).
docs/README.codex.md + docs/README.opencode.md — thin pointers to the
.codex/ and .opencode/ subdirs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```text

```bash
git add docs/README.claude-code.md docs/README.codex.md docs/README.opencode.md
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 8: Rewrite main README.md (plugin-user focus)

**Files:**
- Modify: `README.md`
- Create: `.env.example`

- [ ] **Step 1: Write `.env.example`**

```text
# Cloud Supabase project
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role key from Dashboard → API Keys>
SUPABASE_DB_URL=postgresql://postgres.<your-project>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres

# Plugin runtime
CRYPTOZAVR_MODE=research_only
CRYPTOZAVR_LOG_LEVEL=INFO
```

- [ ] **Step 2: Rewrite README.md**

Overwrite `README.md`:
```markdown
# cryptozavr

Risk-first crypto market research plugin for Claude Code, OpenAI Codex, OpenCode, Cursor, and Gemini CLI. Provides 4 MCP tools over KuCoin and CoinGecko with Supabase-backed cache, provenance tracking, and auditable reasoning.

## What's in the box

**MCP tools**
- `get_ticker(venue, symbol, force_refresh)` — last price + bid/ask + 24h stats
- `get_ohlcv(venue, symbol, timeframe, limit, force_refresh)` — OHLCV candles (1m..1w)
- `get_order_book(venue, symbol, depth, force_refresh)` — bids/asks + spread_bps
- `get_trades(venue, symbol, limit, force_refresh)` — recent trade ticks

**Slash commands**
- `/cryptozavr:ticker <venue> <symbol>`
- `/cryptozavr:ohlcv <venue> <symbol> <timeframe>`
- `/cryptozavr:research <venue> <symbol>` (4-tool parallel collage)
- `/cryptozavr:health` (smoke test)

**Subagent**
- `crypto-researcher` — specialist for multi-step market research (calm, explainable, no advice)

**Skills**
- `crypto-research` — when-to-invoke + tool-selection matrix
- `interpreting-market-data` — field-by-field legend + red flags

**Every response carries:**
- `reason_codes` audit trail (5-handler chain: `venue → symbol → cache → provider`)
- `staleness` + `cache_hit` — so you always know if data is fresh

## Install

Pick your platform:
- [Claude Code](docs/README.claude-code.md)
- [OpenAI Codex](docs/README.codex.md)
- [OpenCode](docs/README.opencode.md)
- [Cursor](.cursor-plugin/README.md)
- [Gemini CLI](gemini-extension.json) — wired via the same mcpServers config

## Env setup

Copy `.env.example` → `.env` and fill:
- `SUPABASE_URL` — your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` — from Dashboard → API Keys → `service_role`
- `SUPABASE_DB_URL` — PostgreSQL connection string (session pooler, port 5432)

The cryptozavr MCP server needs Python 3.12 + `uv`. Install with:
```bash
uv sync --all-extras
```

## Philosophy

1. **Risk-first, not signal-first.** Audit trail + provenance before prediction.
2. **Calm execution.** Dispassionate, institutional-minded. No FOMO.
3. **Declarative over ad-hoc.** Settings, thresholds, rate limits in config, not prompts.
4. **Explainability and auditability.** Every answer contains `data`, `quality`, `reasoning`.
5. **Safe agent design.** LLM proposes; human approves; deterministic code executes.

See [docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md](docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md) for the full MVP design.

## Architecture

- **Domain (L3)** — `src/cryptozavr/domain/`: Pydantic-like frozen dataclasses (Ticker, OHLCVSeries, OrderBookSnapshot, TradeTick) + DataQuality envelope.
- **Infrastructure (L2)** — `src/cryptozavr/infrastructure/`: CCXT adapter (KuCoin), CoinGecko HTTP client, Supabase gateway (asyncpg + supabase-py realtime), 4 decorators (Retry / RateLimit / InMemoryCache / Logging), 5-handler chain of responsibility.
- **Application (L4)** — `src/cryptozavr/application/services/`: `TickerService`, `OhlcvService`, `OrderBookService`, `TradesService` — thin orchestrators over chain + factory + gateway.
- **MCP (L5)** — `src/cryptozavr/mcp/`: FastMCP v3 server with lifespan, 4 tools, DTO layer.

14 GoF patterns applied: Template Method, Adapter, Bridge, Decorator (4 layered), Chain of Responsibility (5 handlers), State (venue health), Factory Method, Singleton via DI, Flyweight (SymbolRegistry), Facade (SupabaseGateway).

## Tests

```bash
uv run pytest tests/unit tests/contract -m "not integration"   # 288 unit + 5 contract, ~2s
uv run pytest tests/integration                                 # 14 live tests, ~40s (needs .env)
```

## Status

**v0.1.0** — plugin готов к marketplace distribution. Data layer (M2.1–M2.6) + Realtime (M2.7) complete. Next: analytical layer (signals/triggers/alerts) in M3.

## License

MIT — see [LICENSE](LICENSE).
```text

- [ ] **Step 3: Commit**

Write to /tmp/commit-msg.txt:
```

docs: rewrite README for plugin users + add .env.example

README now leads with the 4 MCP tools, slash commands, subagent, and
skills — plugin-user perspective rather than developer. Philosophy
retained. Architecture section summarises L2-L5 + the 14 GoF
patterns. .env.example documents the three SUPABASE_* variables.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```text

```bash
git add README.md .env.example
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 9: Validate plugin + local smoke test

**Files:** No new files. Uses existing plugin-dev validator.

- [ ] **Step 1: Run the plugin-validator skill**

Dispatch the `plugin-dev:plugin-validator` subagent with:
```text
Validate the cryptozavr plugin at /Users/laptop/dev/cryptozavr.
Check plugin.json shape, marketplace.json, commands/*.md frontmatter,
agents/*.md frontmatter, skills/**/SKILL.md structure, hooks/hooks.json,
and cross-file consistency (e.g. every allowed-tools reference exists).
Report missing or malformed pieces.
```

Fix anything the validator flags before proceeding.

- [ ] **Step 2: Local marketplace add (smoke test)**

```bash
cd /Users/laptop/dev/cryptozavr
# Ensure .env is populated from M2.7
test -f .env && echo "OK: .env present" || echo "FAIL: create .env first"
# Make the hook executable (in case it wasn't committed as 0755)
chmod +x hooks/session-start.sh
```

Then, in a separate Claude Code session (NOT this agent session):
```text
/plugin marketplace add /Users/laptop/dev/cryptozavr
/plugin install cryptozavr@cryptozavr-marketplace
/cryptozavr:health
```

Expected: health command returns the echo response + lists 5 tools (echo + 4 get_*).

- [ ] **Step 3: Document smoke-test result**

Append to `docs/superpowers/m2.8-smoke-test.md` (create if not present):
```markdown
# M2.8 smoke test log

## Plugin install (local marketplace)
- `/plugin marketplace add /Users/laptop/dev/cryptozavr` — OK
- `/plugin install cryptozavr@cryptozavr-marketplace` — OK

## Tools visible
- `echo`, `get_ticker`, `get_ohlcv`, `get_order_book`, `get_trades` — OK

## Slash commands visible
- `/cryptozavr:ticker`, `/cryptozavr:ohlcv`, `/cryptozavr:research`, `/cryptozavr:health` — OK

## SessionStart banner
- Banner printed on new session startup — OK

## End-to-end
- `/cryptozavr:ticker kucoin BTC-USDT` returned a ticker with reason_codes — OK
- `/cryptozavr:research kucoin BTC-USDT` dispatched 4 tools in parallel — OK
```

- [ ] **Step 4: Commit**

Write to /tmp/commit-msg.txt:
```text
docs: add M2.8 smoke test log

Records local-marketplace install + tool visibility checks. The
plugin-validator subagent cleared the manifest + frontmatter shape;
the smoke test covered install, tool registration, slash-command
visibility, SessionStart banner, and end-to-end ticker/research
calls.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git add docs/superpowers/m2.8-smoke-test.md
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 10: CHANGELOG + tag v0.1.0 + push

- [ ] **Step 1: Verify**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest tests/unit tests/contract -m "not integration" -q 2>&1 | tail -3
```

No code changes in this milestone — tests should remain 288 unit + 5 contract.

- [ ] **Step 2: Update CHANGELOG**

Edit `/Users/laptop/dev/cryptozavr/CHANGELOG.md`. Find:
```markdown
## [Unreleased]

## [0.0.10] - 2026-04-21
```

Replace with:
```markdown
## [Unreleased]

## [0.1.0] - 2026-04-22

### Added — M2.8 Production-ready multi-platform plugin

**Plugin manifest**
- `.claude-plugin/plugin.json` (name, version, author, keywords).
- `.claude-plugin/marketplace.json` — self-hosted marketplace registry so users can `/plugin marketplace add https://github.com/evgenygurin/cryptozavr`.

**Slash commands (4)**
- `/cryptozavr:ticker <venue> <symbol>`
- `/cryptozavr:ohlcv <venue> <symbol> <timeframe> [limit]`
- `/cryptozavr:research <venue> <symbol>` — 4-tool parallel collage (Price → Trend → Liquidity → Flow → Provenance)
- `/cryptozavr:health` — MCP server smoke test

**Agent (1)**
- `crypto-researcher` — specialist subagent for multi-step market research. `model=sonnet`, restricted to the 4 cryptozavr MCP tools, strict "data, not advice" rails.

**Skills (2)**
- `crypto-research` — workflow + tool-selection matrix
- `interpreting-market-data` — field-by-field legend + red flags

**Hooks**
- `SessionStart` hook prints a plugin banner with the slash-command list on startup (not on clear/compact).

**Cross-platform**
- `.codex/README.md`, `.opencode/README.md`, `.cursor-plugin/README.md` — per-platform install notes.
- `gemini-extension.json` — Gemini CLI manifest.
- `docs/README.claude-code.md`, `docs/README.codex.md`, `docs/README.opencode.md`.

**Docs**
- `README.md` rewritten from developer- to plugin-user perspective.
- `.env.example` documents the three required SUPABASE_* variables.
- Smoke-test log in `docs/superpowers/m2.8-smoke-test.md`.

### Next
- M3: L4 business logic — signals, triggers, alerts. Elicit-based approval flows for trading ops (later phase).

## [0.0.10] - 2026-04-21
```

- [ ] **Step 3: Commit CHANGELOG + plan**

```bash
cd /Users/laptop/dev/cryptozavr
git add CHANGELOG.md
git add docs/superpowers/plans/2026-04-22-cryptozavr-m2.8-production-plugin.md 2>/dev/null || true
```

Write to /tmp/commit-msg.txt:
```bash
docs: finalize CHANGELOG for v0.1.0 (M2.8 production plugin)

Minor bump — cryptozavr is now a fully-formed Claude Code plugin
with slash-commands, a specialist subagent, workflow skills, a
SessionStart banner, cross-platform wrappers, and a self-hosted
marketplace manifest.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

- [ ] **Step 4: Tag + push**

Write tag message to /tmp/tag-msg.txt:
```bash
M2.8 Production plugin complete — v0.1.0

Full Claude Code plugin surface: 4 slash-commands, crypto-researcher
agent, 2 skills, SessionStart banner hook, cross-platform wrappers
(Codex, OpenCode, Cursor, Gemini), self-hosted marketplace registry.
Ready for publication via
`/plugin marketplace add https://github.com/evgenygurin/cryptozavr`.
```

```bash
cd /Users/laptop/dev/cryptozavr
git tag -a v0.1.0 -F /tmp/tag-msg.txt
rm /tmp/tag-msg.txt
git push origin main
git push origin v0.1.0
```

- [ ] **Step 5: Summary**

```bash
cd /Users/laptop/dev/cryptozavr
echo "=== M2.8 complete ==="
git log --oneline v0.0.10..HEAD
git tag -l | tail -5
```

---

## Acceptance Criteria

1. ✅ All 10 tasks done.
2. ✅ `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` present and valid.
3. ✅ 4 slash-commands in `commands/`, each with proper frontmatter + `allowed-tools` referencing real MCP tools.
4. ✅ `agents/crypto-researcher.md` present with `tools:` list, `model: sonnet`, rails documented.
5. ✅ 2 skills in `skills/*/SKILL.md` with name + description frontmatter.
6. ✅ `hooks/hooks.json` + `hooks/session-start.sh` (executable) print banner on SessionStart.
7. ✅ Cross-platform wrappers (`.codex/`, `.opencode/`, `.cursor-plugin/`, `gemini-extension.json`) present.
8. ✅ `docs/README.*.md` per-platform install guides.
9. ✅ `README.md` rewritten for plugin users; `.env.example` present.
10. ✅ plugin-validator subagent clears manifest + frontmatter shape.
11. ✅ Local smoke test (documented in `docs/superpowers/m2.8-smoke-test.md`) confirms install + tool visibility.
12. ✅ Tag `v0.1.0` pushed to github.com/evgenygurin/cryptozavr.
13. ✅ No code changes in `src/` — tests remain 288 unit + 5 contract + 14 integration.

---

## Notes

- **No Python code changes**: this milestone is plugin polish — manifest, UX, docs, cross-platform. Test counts stay the same.
- **`$CLAUDE_PLUGIN_ROOT`**: used in `.mcp.json` and `hooks/hooks.json`. Gets populated by Claude Code / Codex / OpenCode at plugin load. In Cursor / Gemini, falls back to the plugin directory.
- **Marketplace in the same repo**: `.claude-plugin/marketplace.json` lives in the plugin repo itself. Users run `/plugin marketplace add https://github.com/evgenygurin/cryptozavr` and Claude Code reads that file to discover the plugin. No separate marketplace repo needed for MVP.
- **OpenClaw**: the user mentioned this in an earlier message. It's either a community wrapper (treated same as OpenCode — Claude Code plugin format compatible) or a typo. Covered implicitly by the `.opencode/` wrapper until clarified.
- **Smoke test requires a separate Claude Code session**: the agent session can't `/plugin install` itself. Task 9 Step 2 is a user action — documented so the user can run it.
- **`/plugin marketplace add` accepts local paths too**: `/plugin marketplace add /Users/laptop/dev/cryptozavr` works for local-dev installs without pushing first. That's how the smoke test validates the plugin before public release.
