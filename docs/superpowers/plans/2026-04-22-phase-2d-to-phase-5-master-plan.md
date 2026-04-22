# Master Plan — Phase 2D → Phase 5 (оставшийся MVP spec)

> **Для агента в сессии:** это мастер-план от точки `main @ 4c2ee48`
> (Phase 2 Sub-project A слит) до конца MVP spec. Каждая phase разбита
> на крупные **unit'ы** (не 14 bite-sized). Один unit = один subagent
> dispatch + один light review. После группы unit'ов одной фазы —
> heavy review + PR + user-approved merge.
>
> **Правила dispatch'а subagent'ов** — см. `docs/dev-workflow-contract.md`,
> секция Subagent Economy. **Не дроби задачи мельче unit'а.**

**Текущее состояние main:**
- Phase 1 + 1.5 ✅ (market data MCP, health, cache invalidation)
- Phase 2A ✅ (StrategySpec DSL + Builder)
- Phase 2B Sub-project A ✅ (BacktestEngine hybrid, 655 tests)
- Phase 2C ✅ (Visitor analytics — 5 visitors + composer)

**Legend:**
- `[ ]` — не начато
- `[~]` — в работе (отметь когда dispatch'ишь subagent)
- `[x]` — unit shipped (коммит в ветке)
- `[✓]` — phase merged в main

---

## Blocking gates (user-approval required)

Перед **каждой** из phases 3/4/5 — обязательный brainstorming-цикл
с пользователем до writing-plans. Эти фазы меняют torgovyj contract
(risk limits, leverage, kill switch, live API keys). Нельзя просто
«исполнить по master-плану».

Gates:
- [ ] **Phase 3 gate** — user brainstorming ok ДО start
- [ ] **Phase 4 gate** — user brainstorming ok ДО start
- [ ] **Phase 5 gate** — user brainstorming ok ДО start + security pre-review

Phase 2 (D + E + skill) идёт по этому master-плану без дополнительного
brainstorming — scope уже зафиксирован в MVP spec §11.3.

---

## Phase 2 closure — 2D + 2E + skill

**Цель phase 2 в целом:** превратить сделанные backend-блоки (2A + 2B + 2C)
в **первую реально полезную вещь** — Claude через MCP-тулы прогоняет
стратегии на истории и говорит человеку результат.

**Одна feature-ветка** `feat/phase-2-closure` (2D + 2E + skill в одном PR)
ИЛИ три отдельные ветки если user захочет. Решаем в начале.

### Unit 2D-1: MCP tool DTOs + validate tool

**Scope:**
- Pydantic DTO слой для всех 8 tool request/response (StrategySpecPayload, BacktestRequest, BacktestResponse, etc.)
- `validate_strategy(spec_payload)` — первый, простейший tool: парсит StrategySpec, возвращает errors
- Тесты + MCP structured content (`@mcp.tool` + Pydantic returns)

**Files (оценочно):**
- `src/cryptozavr/mcp/tools/strategy_dtos.py`
- `src/cryptozavr/mcp/tools/validate_strategy.py`
- `tests/unit/mcp/tools/test_strategy_dtos.py`
- `tests/unit/mcp/tools/test_validate_strategy.py`
- `src/cryptozavr/mcp/server.py` — register tool

**Dispatch:** 1 subagent + 1 light review.

- [x] Unit 2D-1 done (ca02223, light review APPROVED)

### Unit 2D-2: Read-only tools (list / explain / diff)

**Scope:**
- `list_strategies()` — возвращает список сохранённых (placeholder: пусто, реальное хранилище в 2E)
- `explain_strategy(spec_payload)` — human-readable описание стратегии
- `diff_strategies(a, b)` — структурный diff двух specs

**Примечание:** `save` и `list` без 2E — стабы в памяти, сшиваются когда 2E готов.

**Dispatch:** 1 subagent + 1 light review.

- [x] Unit 2D-2 done (887f3af, light review APPROVED)

### Unit 2D-3: Compute tools (backtest / compare / stress_test / save)

**Scope:**
- `backtest_strategy(spec, symbol, timeframe, period)` — грузит OHLCV через существующий OhlcvService, прогоняет через BacktestEngine, возвращает BacktestReport + visitor results. Это **ключевой tool — он даёт проекту полезность.**
- `compare_strategies([specs], ...)` — параллельный бэктест + diff analytics
- `stress_test(spec, scenarios)` — прогон против нескольких market regimes (можно статические CSV для MVP)
- `save_strategy(spec)` — persist (в 2E; пока placeholder)

**Files:** `src/cryptozavr/mcp/tools/backtest_tools.py`, tests.

**Dispatch:** 1 subagent (большой unit, но coherent scope) + 1 light review.

- [x] Unit 2D-3 done (f04f08b, light review APPROVED; visitor ClassVar pre-existing — spawned separate task)

### Unit 2E-1: pgvector schema + service layer

**Scope:**
- Supabase migration: enable pgvector extension + `cryptozavr.strategy_specs` table (spec_json, embedding, hash, metadata) + similarity RPC
- `StrategySpecRepository` service на asyncpg + Supabase gateway
- Embedding generation — HTTP call к embedding provider (или skip для MVP, placeholder)
- Integration с `save_strategy` / `list_strategies` из 2D-2

**Files:**
- `supabase/migrations/NNNN_strategy_specs.sql`
- `src/cryptozavr/infrastructure/persistence/strategy_spec_repo.py`
- Update 2D-2 stubs → real repository

**Dispatch:** 1 subagent + 1 light review. Embedding provider choice TBD с user если нетривиально (если static — можно локальный placeholder).

- [x] Unit 2E-1 done (c9bac19 + comment fix, light review APPROVED; heavy review must run supabase-up smoke)

### Unit skill-1: `strategy-review` skill

**Scope:**
- `.claude/skills/strategy-review/SKILL.md` + frontmatter
- Workflow: user даёт StrategySpec → skill вызывает validate → backtest → compare vs baseline → explain → советы
- Trivial — mostly markdown

**Dispatch:** 1 subagent (small) + no review (markdown).

- [x] Unit skill-1 done (direct write, skill at skills/strategy-review/SKILL.md)

### Phase 2 closure — heavy review + PR + user merge

- [ ] Heavy review: full `requesting-code-review` subagent против всего diff
- [ ] Fix issues (если есть)
- [ ] `superpowers:finishing-a-development-branch` → PR → user approves merge
- [ ] **Phase 2 ✓ merged**

**Budget estimate:** 5 subagent dispatches (4 units + 1 heavy review).

---

## Phase 3 — RiskEngine + policies (gate требуется)

**Цель:** детерминированный risk layer, который **проверяет** trade intent до его исполнения. Без него весь backtest = игра в Sim City.

**BRAINSTORMING GATE** (user ok до writing-plans):
- Какие именно risk policies? Max leverage, max daily loss, max position size %, cool-down after N losses, min balance buffer.
- Где policies хранятся? (файл / БД / inline в StrategySpec?)
- Semantics при нарушении: hard reject vs warning vs approval request?

Unit'ы после утверждения scope:

### Unit 3-1: Policy DSL (Pydantic)

- `RiskPolicy` / `ExecutionPolicy` / `PortfolioPolicy` frozen Pydantic models
- Validators на пределы (max_leverage ≤ 10, max_position_pct ≤ 1, etc.)
- Tests: invariant violations

**Dispatch:** 1 subagent + 1 light review.

- [ ] Unit 3-1 done

### Unit 3-2: Chain of Responsibility (5 handlers)

- `RiskPolicyHandler → ExposureHandler → LiquidityHandler → CooldownHandler → KillSwitchHandler`
- Каждый handler принимает TradeIntent, возвращает decision (OK / DENY / REQUEST_APPROVAL)
- `RiskEngine.evaluate(intent)` запускает цепочку
- Tests: each handler in isolation + full chain scenarios

**Dispatch:** 1 subagent + 1 light review.

- [ ] Unit 3-2 done

### Unit 3-3: MCP tools (6 new)

- `set_risk_policy` / `get_risk_policy` / `evaluate_trade_intent` /
  `simulate_risk_check` / `list_violations` / `reset_cooldown`
- Integration с RiskEngine + DTO layer (pattern из 2D)

**Dispatch:** 1 subagent + 1 light review.

- [ ] Unit 3-3 done

### Phase 3 closure

- [ ] Heavy review + PR + user merge
- [ ] **Phase 3 ✓ merged**

**Budget estimate:** 4 subagent dispatches.

---

## Phase 4 — Paper Trading (gate)

**Цель:** Gym для системы без денег. Стратегия торгует на real-time OHLCV feed с симулированным portfolio. Несколько недель paper перед live — обязательно для поимки drift между backtest и реальностью.

**BRAINSTORMING GATE:**
- Где хранится PaperPortfolio state? (Supabase / in-memory snapshot?)
- Как feed OHLCV в paper mode? (WebSocket через CCXT Pro / polling через CCXTProvider / Supabase realtime?)
- Approval provider: как user approve'ит paper ордер? (MCP tool с user confirmation / auto-approve?)

Unit'ы:

### Unit 4-1: PaperPortfolio + state

- Model (positions, balance, PnL, history)
- In-memory + Supabase persistence (stateful, восстанавливается при перезапуске сервера)
- Tests: deposit, withdraw, position open/close, PnL correctness

**Dispatch:** 1 subagent + 1 light review.

- [ ] Unit 4-1 done

### Unit 4-2: ExecutionPlanner + PaperExecutionEngine

- `TradeIntent → ExecutionPlan` (как выполнять: market / limit, slippage assumption, fees)
- `PaperExecutionEngine` применяет plan к PaperPortfolio против текущей свечи из feed'а
- Tests: plan correctness, execution edge cases

**Dispatch:** 1 subagent + 1 light review.

- [ ] Unit 4-2 done

### Unit 4-3: Approval provider + MCP tools (7) + Mode activation

- `ApprovalProvider` — gate перед каждым ордером (TTL 5 мин, MCP tool user clicks)
- 7 new MCP tools: `start_paper_session` / `stop_paper_session` / `portfolio_status` / `open_position_paper` / `close_position_paper` / `approve_trade` / `get_execution_history`
- Mode `PAPER_TRADING` в runtime config (read-only до активации)

**Dispatch:** 1 subagent + 1 light review.

- [ ] Unit 4-3 done

### Phase 4 closure

- [ ] Heavy review + PR + user merge
- [ ] **Phase 4 ✓ merged**

**Budget estimate:** 4 subagent dispatches.

---

## Phase 5 — Approval-gated Live Execution (gate + security)

**Цель:** Реальные деньги, под жёсткими предохранителями. Hard cap $1000
notional первый месяц. Approval flow обязателен. KillSwitch работает.

**BRAINSTORMING GATE + SECURITY PRE-REVIEW:**
- Какая биржа первая? (KuCoin / Bybit / Binance / ...). Нужны API keys + sandbox/live флаг.
- Где хранятся API keys? Supabase Vault (encryption at rest + RLS).
- Kill switch: что именно останавливает? (новые ордера / закрывает все позиции / отключает весь mode?)
- Approval TTL: 5 минут ok? Перенастраиваемо?
- Аудит: куда пишется trail? (Supabase append-only log table)

Unit'ы — каждый критически важен, не сокращать:

### Unit 5-1: API key vault

- Supabase Vault integration (encrypt + store per venue)
- CRUD через MCP tools (user adds/removes keys, никогда не видит в явном виде)
- Tests: encryption round-trip, RLS enforcement, non-leak in logs

**Dispatch:** 1 subagent + 1 heavy review (security-critical).

- [ ] Unit 5-1 done

### Unit 5-2: LiveExecutionEngine + KillSwitch

- `LiveExecutionEngine` — Strategy pattern (Live vs Paper, один Protocol)
- Uses CCXT with real API keys from Vault
- `KillSwitch` — singleton в runtime; `halt()` блокирует новые ордера и опционально закрывает positions
- Hard cap: reject ордер если notional > $1000 (configurable)

**Dispatch:** 1 subagent + 1 heavy review.

- [ ] Unit 5-2 done

### Unit 5-3: PreToolUse hook + audit trail

- Claude Code PreToolUse hook — перехватывает `execute_live_trade` до вызова, требует approval
- Full audit trail в `cryptozavr.audit_log` (every action, approval, denial, execution)
- Append-only, immutable (RLS enforces)

**Dispatch:** 1 subagent + 1 light review.

- [ ] Unit 5-3 done

### Unit 5-4: MCP tools + Mode APPROVAL_GATED_LIVE

- MCP tools: `execute_live_trade` / `cancel_live_order` / `get_live_positions` / `activate_live_mode` / `kill_switch_activate` / etc.
- Mode `APPROVAL_GATED_LIVE` activation gate: user confirmation + explicit venue choice + hard cap confirmation
- Tests: approval flow end-to-end, kill switch activation, cap enforcement

**Dispatch:** 1 subagent + 1 light review.

- [ ] Unit 5-4 done

### Phase 5 closure

- [ ] **FULL SECURITY REVIEW** (dedicated subagent, не light) — поиск leak'ов, RLS коррекность, audit completeness, approval flow
- [ ] Staging test с sandbox API keys (если биржа даёт)
- [ ] user ok merge → **Phase 5 ✓ merged**
- [ ] Release v1.0 tag + CHANGELOG

**Budget estimate:** 5-6 subagent dispatches (4 units + heavy security review + final).

---

## Overall budget

| Phase | Unit dispatches | Reviews | Total subagent calls |
|---|---:|---:|---:|
| 2 closure (D+E+skill) | 4 | 1 | 5 |
| 3 (Risk) | 3 | 1 | 4 |
| 4 (Paper) | 3 | 1 | 4 |
| 5 (Live) | 4 | 2 (heavy) | 6 |
| **Total** | **14** | **5** | **19** |

Vs v1 режим (subagent-driven 14 tasks per phase): было бы ~200-270.
**~10-15× экономия.**

---

## Workflow per session

1. **Старт:** агент читает `docs/dev-workflow-contract.md` + этот master-plan
2. **Определяет** next pending phase → проверяет blocking gate (если phase 3/4/5)
3. **Если gate не пройден** → запускает `superpowers:brainstorming` с user'ом
4. **После approval** → писать sub-plan для фазы в `docs/superpowers/plans/`
5. **Для каждого unit в фазе:**
   - Dispatch 1 subagent с чётким контрактом (scope, границы, existing code via file paths)
   - Subagent делает TDD, commits, self-reviews
   - Dispatch 1 light reviewer
   - Если Important issues — fix + re-review
   - Mark `[x]` в master-plan (commit)
6. **После последнего unit фазы** → heavy review + PR + user finishing-a-development-branch
7. **После merge** → обновить master-plan (`[✓]`), коммит

---

## Notes

- Каждый раз когда агент хочет дёрнуть больше чем 1 subagent на unit —
  перечитать Subagent Economy в contract'е.
- Если unit получается >10 файлов / тесты >40 — разделить unit, не
  делать сам.
- Параллельные dispatches ТОЛЬКО между unit'ами без shared state
  (пример: 2E-1 и 2D-2 полностью независимы, можно в параллель).
- Master-plan обновляется **в том же git branch** что работа фазы —
  чекбоксы видны в PR.
