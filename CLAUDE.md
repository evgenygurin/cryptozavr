# cryptozavr — Claude Code project instructions

## ⚡ Dev Workflow Contract (READ FIRST)

**Для любой session'и которая пишет/ревьюит код:**

1. Прочитать [`docs/dev-workflow-contract.md`](docs/dev-workflow-contract.md) — жёсткие правила, приоритетны над дефолтным поведением
2. Прочитать [`docs/superpowers/plans/2026-04-22-phase-2d-to-phase-5-master-plan.md`](docs/superpowers/plans/2026-04-22-phase-2d-to-phase-5-master-plan.md) — master-план оставшегося MVP scope с чекбоксами
3. Определить next pending phase → проверить blocking gate (phase 3/4/5 требуют brainstorming с user до старта)

**Ключевое отличие от старого режима:**
- Крупные unit'ы (3-5 на фазу), не 14 bite-sized задач
- Один subagent на unit, один light review на unit
- Heavy review только per group (раз на PR)
- ~10-15× экономия токенов vs старый subagent-driven

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
uv run pytest tests/unit tests/contract -m "not integration" -q   # 440 unit + contract (~4s)
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

## Live-plugin dev workflow — версия и кеш

**Перед любой live MCP-проверкой** сравни `echo().version` с `cryptozavr.__version__`. Если не сходится — cache плагина stale:

```bash
claude plugin list | grep cryptozavr            # видимая версия
claude plugin marketplace update cryptozavr-marketplace
claude plugin update cryptozavr@cryptozavr-marketplace   # tag → cache
```

**Если `claude` уже запущен** — он держит `--plugin-dir .../cryptozavr/<старая>` в argv; `plugin update` добавляет `/<новая>/` *рядом*, subprocess не перенаправляется. В текущей сессии:

```bash
cd ~/.claude/plugins/cache/cryptozavr-marketplace/cryptozavr
mv <stale> <stale>.backup && ln -s <new> <stale>     # symlink на новую
pkill -f "python.*-m cryptozavr\.mcp\.server"   # Claude respawn'ит
```

**Live-sync code edits** (без bump версии): `cp <edited-file> ~/.claude/plugins/cache/cryptozavr-marketplace/cryptozavr/<current>/<same-path>` затем `pkill` subprocess. Чище — выйти из сессии и заново `claude --plugin-dir /Users/laptop/dev/cryptozavr`.

**Sanity check PID цепочки:** `ps -ef | grep "cryptozavr-marketplace" | grep -v grep` — цепочка `sh → uv run → python`. Родительский `claude` (pid с `--plugin-dir`) НЕ трогать.

## MCP resources vs tools — escape rule

`@mcp.resource` → wire format `TextResourceContents.text: str`, любой вложенный JSON экранируется (`\"`) в raw client output. Для interactive views возвращай через `@mcp.tool` с Pydantic-DTO — FastMCP v3 наполняет `CallToolResult.structuredContent` native JSON-объектом. См. `src/cryptozavr/mcp/tools/catalog.py` как reference.

Для resources: используй `ResourceResult(ResourceContent(content=json.dumps(...), mime_type="application/json"))` — это фиксит и MIME-drop на URI-template resources.

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
- **L2 Infra**: `src/cryptozavr/infrastructure/` — CCXT adapter (with `trades_to_domain` + `_snap_order_book_depth`), CoinGecko HTTP (with `id→category_id` mapping), Supabase gateway, **5 decorators** (Retry/RateLimit/Cache/Logging/**Metrics**), 5-handler Chain of Responsibility, Realtime subscriber, `MetricsRegistry` (Prometheus-compatible).
- **L4 Application**: `src/cryptozavr/application/services/` — TickerService, OhlcvService, OrderBookService, TradesService, AnalyticsService (Strategy), SymbolResolver, DiscoveryService, plus Phase 1.5 background tasks: `HealthMonitor` (probes venues, updates VenueState.last_checked_at_ms), `TickerSyncWorker` (force-refreshes subscribed symbols), `CacheInvalidator` (Supabase Realtime → `provider.invalidate_tickers()`).
- **L5 MCP**: `src/cryptozavr/mcp/` — FastMCP v3 server with dict-lifespan, **16 tools** (5 market-data, 1 discovery, 4 analytics, 1 history, 5 catalog with `structuredContent`), **4 resources + 1 URI-template**, **2 prompts**, DTO layer with `VenuesListDTO`/`SymbolsListDTO`/etc.

**15 GoF patterns** applied: Template Method, Adapter, Bridge, **Decorator (×5, incl. MetricsDecorator)**, Chain of Responsibility (×5 handlers), State (VenueState), Factory Method, Singleton via DI, Flyweight (SymbolRegistry), Facade (SupabaseGateway), Iterator (OHLCVPaginator with `_clip_to_window`), Strategy (MarketAnalyzer), **Observer** (Supabase Realtime → `CacheInvalidator`).

Полная спецификация — `docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md`.
