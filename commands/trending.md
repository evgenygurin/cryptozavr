---
description: Read cryptozavr://trending and cryptozavr://categories — CoinGecko trending assets + category stats.
argument-hint: ""
---

Read both discovery resources from the cryptozavr plugin:
1. `cryptozavr://trending` — top trending crypto assets (ranked).
2. `cryptozavr://categories` — sector-level market cap + 24h change.

Present a compact two-section report:

### Trending (top 10)
`rank | code | name | market_cap_rank | categories`

### Categories movement
`name | market_cap | 24h_change_%`

Warn the user if either resource returned an error payload (`error` field present) — that means upstream CoinGecko is unreachable and data is stale.
