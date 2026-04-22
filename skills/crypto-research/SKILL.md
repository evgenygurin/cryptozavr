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

## Narration — как говорить, а не только что звать

Разговаривай как аналитик с коллегой, не дампи JSON. Правила в каждом сообщении:

- **Перед tool call** — одно предложение на русском: ЗАЧЕМ зовёшь.
  «Сниму стакан — хочу увидеть стенки выше $79k», не «calling get_order_book».
- **После результата** — 1–3 предложения: что увидел и как это ложится
  на гипотезу. Числа — доказательства, не самоцель.
- **Никаких больших JSON в чате.** Выдерни 2–3 ключевых числа и скажи почему они важны.
- **Если меняешь план** — озвучь: «передумал, потому что…».
- **Если ждёшь** (long-poll, sleep) — один раз скажи «сижу, жду событие», не повторяй каждые N секунд.
- **Итоговая таблица/отчёт** в конце — компактный, с контекстом. Не распечатка raw-данных.

## Subagent delegation

For non-trivial multi-step research, dispatch the `crypto-researcher` subagent. It runs the tools and enforces the rails so the main thread stays focused on the user's follow-up questions.
