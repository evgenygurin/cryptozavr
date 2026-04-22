# cryptozavr — Claude Code project instructions

## Plugin reload workflow — **ОБЯЗАТЕЛЬНО**

**После редактирования любого компонента плагина — до того как использовать или проверять его — запустить `/reload-plugins`.**

### Что подхватит `/reload-plugins` (без restart сессии)
- `commands/*.md` — slash-команды
- `agents/*.md` — subagents
- `skills/**/SKILL.md` — skills
- `hooks/hooks.json` + `hooks/*.sh`
- `.claude-plugin/plugin.json` — manifest
- `.claude-plugin/marketplace.json` — marketplace registry

### Что требует restart сессии (MCP subprocess не hot-reload)
- `src/cryptozavr/**/*.py` — Python server code
- `.mcp.json` — MCP launch command
- `.env` — environment variables
- `pyproject.toml` / deps — также `uv sync --all-extras` сначала

**Решающий признак:** если файл markdown/JSON внутри плагина — `/reload-plugins`. Если Python/env — выход из сессии + новый `claude`.

## Editing workflow — import placement

**Правило:** импорты Python добавлять ТОЛЬКО вместе с использующим их кодом (одним `Write`/`Edit`) или ПОСЛЕ него — никогда «заранее».

**Почему:** `ruff` + `ruff-format` (pre-commit + PostToolUse hook) удаляют импорты, считаемые неиспользованными, **между Edit'ами**. Если сначала добавить импорт, а потом код его использующий — formatter срежет импорт, и следующий Edit упадёт с `NameError`.

**Как применять:**
- Новый импорт + новый код → один `Write` (полный файл) или один `Edit` (компактный блок)
- Существующий файл → сначала добавить использование (Edit), потом импорт (Edit) — formatter его сохранит
- После PostToolUse hook всегда проверять `grep -n <Symbol> file.py`, чтобы убедиться что импорт на месте

## Tests

```bash
uv run pytest tests/unit tests/contract -m "not integration" -q   # 288 unit + 5 contract (~3s)
uv run pytest tests/integration -v                                # 14 live tests vs cloud Supabase (~40s, needs .env)
```

## Lint / typecheck

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Все pre-commit hooks активны — они стреляют на каждом `git commit` (ruff / format / mypy / pre-commit-hooks).

## Live plugin test без `install`

Session-only загрузка (изменения применяются при каждом запуске `claude`):
```bash
claude --plugin-dir /Users/laptop/dev/cryptozavr --debug plugins,mcp
```

Non-interactive одной командой:
```bash
echo "/cryptozavr:health" | claude -p --model claude-sonnet-4-6 --plugin-dir /Users/laptop/dev/cryptozavr
```

## Plan docs

Все implementation plans — `docs/superpowers/plans/YYYY-MM-DD-*.md`. Читать свежий перед тем как стартовать связанную работу.

## Commits

- Сообщения через файл `/tmp/commit-msg.txt` + `git commit -F ...` (не HEREDOC — ломается STDIN через Bash tool)
- Conventional commits (`feat(scope)`, `fix(scope)`, `docs`, `test`, `chore`) — detail в `~/.claude/rules/git.md`
- Атомарные коммиты: одна логическая единица = один коммит
- Никогда `git add .` / `-A` (может захватить `.env`, кэш) — только явные файлы

## Plugin CLI reference

Full CLI cheatsheet — `docs/plugin-cli-reference.md`. Там:
- `claude plugin {install,uninstall,enable,disable,update,validate,list}`
- `claude plugin marketplace {add,list,update,remove}`
- Flags: `--plugin-dir`, `--debug plugins,mcp`, `--bare`
- On-disk layout `~/.claude/plugins/{cache,marketplaces}`
- `settings.json` format (`enabledPlugins` + `extraKnownMarketplaces`)

## Architecture TL;DR

- **L3 Domain**: `src/cryptozavr/domain/` — frozen dataclasses (Ticker, OHLCVSeries, OrderBookSnapshot, TradeTick)
- **L2 Infra**: `src/cryptozavr/infrastructure/` — CCXT adapter, CoinGecko HTTP, Supabase gateway, 4 decorators (Retry/RateLimit/Cache/Logging), 5-handler Chain of Responsibility, Realtime subscriber
- **L4 Application**: `src/cryptozavr/application/services/` — TickerService, OhlcvService, OrderBookService, TradesService
- **L5 MCP**: `src/cryptozavr/mcp/` — FastMCP v3 server with lifespan, 4 tools, DTO layer

14 GoF patterns: Template Method, Adapter, Bridge, Decorator (×4), Chain of Responsibility (×5 handlers), State (VenueState), Factory Method, Singleton via DI, Flyweight (SymbolRegistry), Facade (SupabaseGateway).

Полная спецификация — `docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md`.
