# Installing cryptozavr in Claude Code

## One-line install (marketplace)

    /plugin marketplace add https://github.com/evgenygurin/cryptozavr
    /plugin install cryptozavr@cryptozavr-marketplace

## Local-dev install

    gh repo clone evgenygurin/cryptozavr ~/dev/cryptozavr
    cd ~/dev/cryptozavr
    uv sync --all-extras
    cp .env.example .env   # then fill in SUPABASE_* values — see main README

Then in Claude Code:

    /plugin marketplace add ~/dev/cryptozavr
    /plugin install cryptozavr@cryptozavr-marketplace

## Verification

After install, in a new Claude Code session:
1. `/cryptozavr:health` should confirm the MCP server is reachable and show the tool list.
2. `/cryptozavr:ticker kucoin BTC-USDT` should return a price + reason_codes.

## Troubleshooting

- **Tools not listed:** `/plugin marketplace update` then restart Claude Code.
- **`Missing env vars`:** `.env` must have `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`. See main README "Env setup".
- **`ProviderUnavailableError`:** the upstream exchange (KuCoin or CoinGecko) is rate-limiting or offline. Retry in ~30s.
- **Slow first call:** cold cache. Subsequent calls hit Supabase.
