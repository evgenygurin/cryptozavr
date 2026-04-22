# Phase 3 — RiskEngine + declarative policies (design spec)

**Status:** approved (2026-04-22, blanket approval from user)
**Predecessor:** Phase 2 closure merged in PR #8 (main @ `e61202e`)
**Master plan:** `docs/superpowers/plans/2026-04-22-phase-2d-to-phase-5-master-plan.md` § Phase 3
**MVP design ref:** `docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md` § 11.3

## Goal

Deterministic risk layer that evaluates every `TradeIntent` **before** execution. Produces an `OK | WARN | DENY` verdict plus a structured list of violations. Phase 3 ships only the evaluation surface — no paper/live execution yet. Must be forward-compatible with Phase 4 (paper) and Phase 5 (live + approval flow).

## Brainstorming decisions

1. **Scope (option B)** — one `RiskPolicy` DSL with **5 limits**, 1-to-1 with the 5 handlers from MVP spec § 11.3: `max_leverage` / `max_position_pct` / `max_daily_loss_pct` / `cooldown_after_n_losses` / `min_balance_buffer`. No separate ExecutionPolicy / PortfolioPolicy DSL in MVP.
2. **Storage (option C)** — persisted through a new `cryptozavr.risk_policies` table; insert-only with one active row at a time (partial unique index on `is_active=true`). MCP CRUD mirrors the Phase 2 StrategySpecRepository pattern. Policy is **global** — no per-strategy override in Phase 3.
3. **Semantics (option B)** — ternary `Decision { OK | WARN | DENY }`. Each limit carries a `severity: "warn" | "deny"` config (default `"deny"`). Forward-compat: Phase 5 will add `"require_approval"` as a fourth severity without breaking the ternary DecisionStatus — a `REQUIRE_APPROVAL` Decision status becomes a 4th variant.

## Hard red lines (inherited from MVP spec § 12)

- **No LLM autonomy.** RiskEngine evaluation is fully deterministic Python. The MCP tool surface is read-only — `evaluate_trade_intent`, `simulate_risk_check`, `list_risk_policy_history` return verdicts but never execute.
- **No live or paper ordering.** RiskEngine produces decisions; it does not orchestrate execution. That lives in Phase 4/5.
- **No policy bypass.** KillSwitch *blocks* intents; it never grants overrides.

## Domain model (`src/cryptozavr/domain/risk.py` — new file)

```python
class RiskStatus(StrEnum):        # verdict of RiskEngine.evaluate()
    OK = "ok"
    WARN = "warn"
    DENY = "deny"

class Severity(StrEnum):          # per-limit config AND per-violation tag
    WARN = "warn"
    DENY = "deny"

@dataclass(frozen=True, slots=True)
class TradeIntent:
    """Neutral trade request. Backtest emits it; live will too (Phase 5)."""

    venue: VenueId
    symbol: Symbol
    side: StrategySide
    size: Decimal                 # notional in quote ccy (e.g. USDT)
    leverage: Decimal = Decimal(1)
    reason: str = ""              # human trace (strategy name, bar idx, etc.)

    # Context the handlers consume (populated by caller — BacktestEngine
    # or the MCP tool, not by RiskEngine itself):
    recent_losses: int = 0
    current_balance: Decimal | None = None
    current_exposure_pct: Decimal | None = None

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValidationError("TradeIntent.size must be > 0")
        if self.leverage < 1:
            raise ValidationError("TradeIntent.leverage must be >= 1 (no sub-1x)")
        if self.recent_losses < 0:
            raise ValidationError("TradeIntent.recent_losses must be >= 0")

@dataclass(frozen=True, slots=True)
class Violation:
    handler_name: str             # "Exposure"
    policy_field: str             # "max_position_pct"
    severity: Severity
    message: str                  # "exposure 32.1% exceeds limit 25.0%"
    observed: Decimal | int
    limit: Decimal | int

@dataclass(frozen=True, slots=True)
class RiskDecision:
    status: RiskStatus
    violations: tuple[Violation, ...]
    evaluated_at_ms: int

    def __post_init__(self) -> None:
        if self.status == RiskStatus.OK and self.violations:
            raise ValidationError(
                "RiskDecision: OK status requires empty violations",
            )
        if self.status == RiskStatus.DENY and not any(
            v.severity == Severity.DENY for v in self.violations
        ):
            raise ValidationError(
                "RiskDecision: DENY status requires >= 1 DENY-severity violation",
            )
        if self.status == RiskStatus.WARN:
            if not self.violations:
                raise ValidationError("WARN status requires >= 1 violation")
            if any(v.severity == Severity.DENY for v in self.violations):
                raise ValidationError(
                    "WARN status cannot contain DENY-severity violations",
                )
```

## Application layer

### RiskPolicy DSL (`src/cryptozavr/application/risk/risk_policy.py`)

Pydantic DSL. Frozen models, validators enforce bounds.

```python
class LimitDecimal(BaseModel):
    model_config = ConfigDict(frozen=True)
    value: Decimal = Field(gt=0)
    severity: Severity = Severity.DENY

class LimitInt(BaseModel):
    model_config = ConfigDict(frozen=True)
    value: int = Field(gt=0)
    severity: Severity = Severity.DENY

class RiskPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_leverage: LimitDecimal
    max_position_pct: LimitDecimal
    max_daily_loss_pct: LimitDecimal
    cooldown_after_n_losses: LimitInt
    min_balance_buffer: LimitDecimal

    @model_validator(mode="after")
    def _pct_bounds(self) -> RiskPolicy:
        for name in ("max_position_pct", "max_daily_loss_pct"):
            lim: LimitDecimal = getattr(self, name)
            if lim.value > 1:
                raise ValueError(f"{name}.value must be in (0, 1] (got {lim.value})")
        if self.max_leverage.value < 1:
            raise ValueError("max_leverage.value must be >= 1 (no sub-1x limits)")
        return self
```

### KillSwitch runtime singleton (`src/cryptozavr/application/risk/kill_switch.py`)

Not persisted in MVP — restart resets to disengaged. Phase 5 will persist the engage state.

```python
@dataclass
class KillSwitchStatus:
    engaged: bool
    engaged_at_ms: int | None
    reason: str | None

class KillSwitch:
    def __init__(self) -> None:
        self._engaged = False
        self._engaged_at_ms: int | None = None
        self._reason: str | None = None
        self._lock = threading.Lock()

    def engage(self, *, reason: str) -> KillSwitchStatus: ...
    def disengage(self) -> KillSwitchStatus: ...
    def status(self) -> KillSwitchStatus: ...
    def is_engaged(self) -> bool: ...
```

### Handler protocol + 5 concrete handlers (`src/cryptozavr/application/risk/handlers/`)

Chain of Responsibility, each handler returns `Violation | None`:

```python
class RiskHandler(Protocol):
    name: ClassVar[str]

    def evaluate(
        self,
        intent: TradeIntent,
        policy: RiskPolicy,
        kill_switch: KillSwitch,
    ) -> Violation | None: ...
```

Concrete handlers (`handlers.py` — one file, 5 classes ≈ 150 LOC):

1. **RiskPolicyHandler** — `intent.leverage > policy.max_leverage.value` → Violation with observed/limit.
2. **ExposureHandler** — requires `current_balance` (else skip with no violation); computes `size / current_balance`, compares to `policy.max_position_pct.value`.
3. **LiquidityHandler** — requires `current_balance`; checks `current_balance - size >= policy.min_balance_buffer.value` (reject if post-trade balance would dip below buffer).
4. **CooldownHandler** — `intent.recent_losses >= policy.cooldown_after_n_losses.value` → Violation. Stateless; caller supplies `recent_losses` count.
5. **KillSwitchHandler** — `kill_switch.is_engaged()` → always DENY regardless of severity config (kill switch is non-negotiable).

Handlers that require context fields (`ExposureHandler` / `LiquidityHandler`) **skip silently with no violation** when the caller did not populate `current_balance`. Rationale: a backtest at the first bar has no balance yet; treating "no data" as a violation would make every first-bar intent fail. The MCP tool docstring makes this explicit; tests cover both paths.

### RiskEngine (`src/cryptozavr/application/risk/engine.py`)

```python
class RiskEngine:
    def __init__(
        self,
        handlers: Sequence[RiskHandler],
        kill_switch: KillSwitch,
    ) -> None:
        self._handlers = tuple(handlers)
        self._kill_switch = kill_switch

    def evaluate(
        self,
        intent: TradeIntent,
        policy: RiskPolicy,
    ) -> RiskDecision:
        violations: list[Violation] = []
        for h in self._handlers:
            v = h.evaluate(intent, policy, self._kill_switch)
            if v is not None:
                violations.append(v)
        return RiskDecision(
            status=_aggregate_status(violations),
            violations=tuple(violations),
            evaluated_at_ms=_now_ms(),
        )

def _aggregate_status(violations: list[Violation]) -> RiskStatus:
    if any(v.severity == Severity.DENY for v in violations):
        return RiskStatus.DENY
    if violations:
        return RiskStatus.WARN
    return RiskStatus.OK
```

RiskEngine is sync + stateless (except for the injected KillSwitch singleton). The handlers list is constructed once at bootstrap time with the canonical 5-handler order from MVP spec § 11.3.

## Infrastructure

### Supabase migration (`supabase/migrations/00000000000080_risk_policies.sql`)

```sql
create table cryptozavr.risk_policies (
  id           uuid primary key default gen_random_uuid(),
  policy_json  jsonb not null,
  content_hash text not null unique,            -- BLAKE2b of canonical JSON
  is_active    boolean not null default false,
  created_at   timestamptz not null default now(),
  activated_at timestamptz
);

-- Exactly one active row at any time.
create unique index risk_policies_one_active
  on cryptozavr.risk_policies (is_active)
  where is_active = true;

create index risk_policies_created_desc
  on cryptozavr.risk_policies (created_at desc);

alter table cryptozavr.risk_policies enable row level security;
create policy service_role_all on cryptozavr.risk_policies
  for all to service_role using (true) with check (true);
```

Canonical JSON + content_hash deduplicate repeat saves, exactly as in `strategy_specs` (Phase 2E-1).

### Repository (`src/cryptozavr/infrastructure/persistence/risk_policy_repo.py`)

```python
@dataclass(frozen=True, slots=True)
class RiskPolicyRow:
    id: UUID
    policy: RiskPolicy          # already parsed
    is_active: bool
    created_at_ms: int
    activated_at_ms: int | None

class RiskPolicyRepository:
    def __init__(self, pool: asyncpg.Pool) -> None: ...

    async def save(self, policy: RiskPolicy) -> UUID:
        """Insert (is_active=false). Upsert on content_hash returns existing id."""

    async def activate(self, policy_id: UUID) -> None:
        """Transaction: UPDATE is_active=false WHERE is_active; UPDATE is_active=true WHERE id=$1."""

    async def get_active(self) -> RiskPolicyRow | None: ...

    async def list_history(self, *, limit: int = 50) -> list[RiskPolicyRow]: ...
```

Shares the existing asyncpg pool wired in `bootstrap.py`.

### Lifespan wiring

- Add `LIFESPAN_KEYS.risk_policy_repo`, `LIFESPAN_KEYS.risk_engine`, `LIFESPAN_KEYS.kill_switch`.
- `bootstrap.py` constructs the 5 handlers + KillSwitch + RiskEngine once; they all share the DI pool.

## MCP surface — 6 new tools

All tools tagged `{"risk", "phase-3"}`. `evaluate_trade_intent` and `simulate_risk_check` are read-only. `set_risk_policy` / `activate_risk_policy` / `engage_kill_switch` / `disengage_kill_switch` mutate persisted or runtime state.

| # | Tool | Shape | Persisted? |
|---|------|-------|-----------|
| 1 | `set_risk_policy(payload)` | Insert policy, auto-activate. Returns UUID + status. | Yes (DB) |
| 2 | `get_risk_policy()` | Current active policy or null. | — |
| 3 | `evaluate_trade_intent(intent_payload)` | Run chain against active policy. Returns `RiskDecisionDTO`. | Logged via `ctx.info`; not persisted in MVP |
| 4 | `simulate_risk_check(intent_payload, policy_override?)` | Same as #3 but with optional override policy. Override is **never saved**. | — |
| 5 | `engage_kill_switch(reason)` | Engage runtime singleton. | No (runtime; restart resets) |
| 6 | `disengage_kill_switch()` | Disengage runtime singleton. | No |

**Tool count.** Master plan listed `set / get / evaluate / simulate / list_violations / reset_cooldown`. Design refines the last two:
- `list_violations` is dropped for MVP — per-evaluation history would require an audit_log table (Phase 5 scope where live decisions demand it). For Phase 3, clients can inspect returned `RiskDecision.violations` directly.
- `reset_cooldown` is superseded by `engage_kill_switch` + `disengage_kill_switch`. Cooldown is stateless inside CooldownHandler (reads `intent.recent_losses` from caller); there's no counter to reset at the handler level.

Ability set stays at 6 tools; names reflect reality.

### DTOs (`src/cryptozavr/mcp/tools/risk_dtos.py` — new)

- `LimitDecimalPayload`, `LimitIntPayload`, `RiskPolicyPayload` — wire-format Pydantic with `to_domain()` converters, mirroring the `strategy_dtos.py` pattern.
- `TradeIntentPayload` — primitive-typed wire mirror of domain `TradeIntent`; `to_domain()` constructs the frozen dataclass via `SymbolRegistry.get(...)`.
- `ViolationDTO`, `RiskDecisionDTO` — `from_domain()` classmethods.
- Response DTOs: `SetRiskPolicyResponse`, `GetRiskPolicyResponse`, `EvaluateTradeIntentResponse`, `SimulateRiskCheckResponse`, `KillSwitchStatusResponse`. Each carries coherence validators where a success/error envelope applies (matching Phase 2 pattern).

### Tool registration module (`src/cryptozavr/mcp/tools/risk_tools.py`)

Single module with `register_risk_tools(mcp)` wiring all 6 tools. Depends injections: `_RISK_ENGINE`, `_KILL_SWITCH`, `_RISK_POLICY_REPO`. Timeouts: mutating tools 30s, evaluate/simulate 10s.

## Testing strategy

### Unit tests (~60 new)

- `tests/unit/domain/test_risk.py` — TradeIntent / Violation / RiskDecision invariants (~15)
- `tests/unit/application/risk/test_risk_policy.py` — DSL field bounds (~8)
- `tests/unit/application/risk/test_kill_switch.py` — engage / disengage / status / thread safety smoke (~6)
- `tests/unit/application/risk/test_handlers.py` — each handler in isolation, happy + violation + skip-on-missing-context paths (~20)
- `tests/unit/application/risk/test_engine.py` — full chain scenarios: all OK / single WARN / single DENY / multi-violation aggregation / KillSwitch overrides everything (~10)
- `tests/unit/infrastructure/persistence/test_risk_policy_repo.py` — AsyncMock pool, save / activate / get_active / list_history / idempotent save (~10)
- `tests/unit/mcp/tools/test_risk_tools.py` — 6 tools + DTO round-trips + coherence validators (~20)

### Integration tests (~3, skip-if-unreachable)

- `tests/integration/supabase/test_risk_policies_roundtrip.py` — save → activate → get_active → list_history + idempotent content_hash collision.

### Contract tests

- Update `tests/contract/test_mcp_server_contract.py` if it exists to register the 6 new tool names. Extend the venue_health / tool_count contract check to 30 (24 existing + 6 new).

## Forward-compatibility notes

- **Phase 4 (paper):** `TradeIntent` is already Phase-4 ready. Paper execution planner consumes `RiskDecision` to gate orders. No schema changes.
- **Phase 5 (live + approval):**
  - Add `Severity.REQUIRE_APPROVAL` variant; add `RiskStatus.REQUIRE_APPROVAL`. The aggregation function gets a new clause; existing handlers unaffected.
  - Add `cryptozavr.risk_evaluations` audit log table + persist every evaluate call (Phase 5 security requirement).
  - Persist KillSwitch state so restart doesn't reset a live-trading halt.

## Scope guard — what Phase 3 does NOT do

- No audit log table (runtime-only decisions).
- No per-strategy policy override (StrategySpec untouched).
- No approval flow / approval provider.
- No execution integration — BacktestEngine does NOT call RiskEngine automatically. Users explicitly pass intents to `evaluate_trade_intent`. Auto-integration lands in Phase 4.
- No `EVALUATE_RISK` capability in ModeGuard (deferred — MVP Mode.RESEARCH_ONLY already exposes these tools).

## Unit decomposition (deferred to writing-plans)

Master plan pre-allocated 3 units:
1. **Unit 3-1** — Policy DSL + TradeIntent/Decision/Violation domain
2. **Unit 3-2** — 5 handlers + RiskEngine + KillSwitch
3. **Unit 3-3** — Migration + Repository + 6 MCP tools + DTOs

Plus Phase 3 closure (heavy review + PR + merge).

## Budget estimate (unchanged from master plan)

| Item | Subagent dispatches |
|------|---:|
| Unit 3-1 impl + light review | 2 |
| Unit 3-2 impl + light review | 2 |
| Unit 3-3 impl + light review | 2 |
| Heavy review | 1 |
| **Total** | **7** |

Controller-side edits (commit master plan checkboxes, polish fixes, PR open) do not count against subagent budget.
