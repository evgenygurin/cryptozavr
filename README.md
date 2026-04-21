# cryptozavr

Risk-first crypto market research plugin for Claude Code. Provides disciplined, declarative, and explainable market data tools through a FastMCP v3+ server with Supabase-backed cache and audit trail.

**Status:** M1 Bootstrap complete. Data-layer and real tools arrive in M2+.

See [docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md](docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md) for the full MVP design.

## Philosophy

1. **Risk-first, not signal-first.** Risk architecture precedes trading features.
2. **Calm execution.** No FOMO, no panic. Dispassionate, institutional-minded.
3. **Declarative over ad-hoc.** Strategies, risk policies, execution policies as Pydantic specs.
4. **Explainability and auditability.** Every answer contains `data`, `quality`, `reasoning`.
5. **Safe agent design.** LLM proposes; human approves; deterministic code executes.

## Quickstart

### Prerequisites

- Python 3.12 (`.python-version` pinned)
- [uv](https://docs.astral.sh/uv/) for Python package management
- [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started) for local DB stack
- [Claude Code](https://www.anthropic.com/claude-code) for plugin integration
- Docker Desktop (runs Supabase locally)

### Install

```bash
git clone <repo-url> cryptozavr
cd cryptozavr
uv sync --all-extras
cp .env.example .env
./scripts/bootstrap-supabase.sh   # starts local Supabase stack
```

### Link plugin in Claude Code

```text
/plugin link /absolute/path/to/cryptozavr
```

Verify:
```text
/plugins                                  # cryptozavr should be connected
# Then ask Claude: "Use the echo tool with message 'test'"
```

## Development

Run tests:
```bash
uv run pytest tests/unit -v
```

Lint + typecheck:
```bash
uv run ruff check .
uv run ruff format .
uv run mypy src
```

Validate plugin artefacts:
```bash
uv run python scripts/validate-plugin.py
```

Run MCP server locally for debugging:
```bash
uv run fastmcp dev fastmcp.json
```

## Architecture

Layered onion: `domain/` (pure) → `application/` (use cases) → `infrastructure/` (providers + Supabase) → `mcp/` (FastMCP facade). See [design doc](docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md) for details.

## Roadmap

- **M1 Bootstrap** ✅ — repo, tooling, FastMCP skeleton with echo tool, CI.
- **M2 Data layer** — Domain + Providers (KuCoin CCXT, CoinGecko) + Supabase schema + first real tool.
- **M3 Full MCP surface** — all 17 tools, 8 resources, 2 prompts, Application services.
- **M4 Plugin integration** — skills, slash-commands, E2E tests, v0.1.0 release.

Post-MVP: strategy engine (phase 2), risk engine (phase 3), paper trading (phase 4), approval-gated live (phase 5), multi-exchange (phase 6+).

## License

MIT
