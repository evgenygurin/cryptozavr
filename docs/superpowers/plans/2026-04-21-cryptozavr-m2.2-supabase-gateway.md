# cryptozavr — Milestone 2.2: Supabase schema + Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Built the Supabase data layer: 6 SQL migrations (schema + RLS + pg_cron), seed data for venues, `SupabaseGateway` Facade over `asyncpg` + `supabase-py` + `realtime-py` (realtime stubbed), and typed mappers `rows → Domain entities`. After M2.2: `SupabaseGateway.upsert_ohlcv` / `load_ohlcv` / `upsert_ticker` / `load_ticker` / `insert_query_log` round-trip works against a local Supabase stack, and unit tests on mappers have coverage ≥ 95%.

**Architecture:** Infrastructure L2. Supabase acts as durable cache + audit store. `SupabaseGateway` hides dual-client reality (asyncpg for hot-path bulk reads/writes, supabase-py for RPC/Storage/admin) behind a single Facade. Mappers are pure functions `row dict → Domain entity` (Adapter pattern). Migrations managed by Supabase CLI, not Alembic.

**Tech Stack:** Python 3.12, asyncpg>=0.29, supabase>=2.8, realtime>=2.0 (stubbed), Supabase CLI, pytest-asyncio, Docker (for `supabase start`).

**Milestone position:** M2.2 of 4 sub-milestones of M2 of 4 milestones of MVP.

**Spec reference:** `docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md` section 5 (Supabase layer).
**Prior plans:** M1 bootstrap (v0.0.1), M2.1 domain layer (v0.0.2).
**Starting tag:** `v0.0.2`. Target tag: `v0.0.3` at end of M2.2.

---

## File Structure (создаётся в M2.2)

All paths relative to `/Users/laptop/dev/cryptozavr/`.

### Migrations (SQL)

| Path | Responsibility |
|------|---------------|
| `supabase/migrations/00000000000000_extensions.sql` | Enable `vector`, `pg_cron`, `pg_net`, `pg_trgm` extensions; create `cryptozavr` schema + grants |
| `supabase/migrations/00000000000010_reference.sql` | Enums (venue_kind, venue_state_kind, market_type, timeframe) + tables (venues, assets, symbols, symbol_aliases) |
| `supabase/migrations/00000000000020_market_data.sql` | tickers_live (hot cache), ohlcv_candles (warm), orderbook_snapshots, trades + indexes |
| `supabase/migrations/00000000000030_audit.sql` | query_kind enum, query_log, provider_events tables |
| `supabase/migrations/00000000000040_rls.sql` | Enable RLS on all tables + service_role bypass policies |
| `supabase/migrations/00000000000050_cron.sql` | pg_cron jobs (prune-stale-tickers, prune-query-log) |
| `supabase/seed.sql` | Insert baseline venues (kucoin, coingecko) with capabilities |

### Python — Infrastructure layer

| Path | Responsibility |
|------|---------------|
| `src/cryptozavr/infrastructure/supabase/__init__.py` | Package marker with exports |
| `src/cryptozavr/infrastructure/supabase/pg_pool.py` | `asyncpg.Pool` factory (async context-managed pool, size 5-10) |
| `src/cryptozavr/infrastructure/supabase/mappers.py` | Pure `row dict → Domain entity` conversions: `row_to_symbol`, `row_to_ticker`, `row_to_ohlcv_candle`, `row_to_ohlcv_series` |
| `src/cryptozavr/infrastructure/supabase/realtime.py` | Stub `RealtimeSubscriber` class (fleshed out in phase 1.5) |
| `src/cryptozavr/infrastructure/supabase/storage.py` | Stub `StorageClient` class (fleshed out in phase 2+) |
| `src/cryptozavr/infrastructure/supabase/rpc.py` | Stub `RpcClient` class (fleshed out in phase 2 for pgvector) |
| `src/cryptozavr/infrastructure/supabase/gateway.py` | `SupabaseGateway` Facade: upsert_ohlcv, load_ohlcv, upsert_ticker, load_ticker, insert_query_log, subscribe_tickers (stub), close |
| `src/cryptozavr/infrastructure/repositories/__init__.py` | Package marker |
| `src/cryptozavr/infrastructure/repositories/symbols_repository.py` | Typed CRUD over `cryptozavr.symbols` |
| `src/cryptozavr/infrastructure/repositories/ohlcv_repository.py` | Typed reads/upserts for ohlcv_candles |
| `src/cryptozavr/infrastructure/repositories/tickers_repository.py` | Typed upserts/reads for tickers_live |
| `src/cryptozavr/infrastructure/repositories/query_log_repository.py` | Insert-only query log |

### Python — Tests

| Path | Responsibility |
|------|---------------|
| `tests/integration/__init__.py` | Package marker |
| `tests/integration/conftest.py` | `supabase_stack` fixture (session-scoped) + `supabase_gateway` fixture |
| `tests/unit/infrastructure/__init__.py` | Package marker |
| `tests/unit/infrastructure/supabase/__init__.py` | Package marker |
| `tests/unit/infrastructure/supabase/test_mappers.py` | Unit tests on mappers (pure functions, fixture dicts) |
| `tests/unit/infrastructure/supabase/test_pg_pool.py` | Unit tests on pool factory (connection string parsing) |
| `tests/integration/test_supabase_gateway.py` | End-to-end tests requiring local Supabase — marked `integration` |
| `tests/integration/test_ohlcv_roundtrip.py` | OHLCV upsert + load_ohlcv equality |
| `tests/integration/test_tickers_upsert.py` | Tickers upsert + cache TTL behavior |
| `tests/integration/test_migrations_apply.py` | Verifies all 6 migrations apply cleanly on clean DB |

### Modifications

| Path | Change |
|------|--------|
| `pyproject.toml` | Add `m2` optional-deps group with `asyncpg>=0.29`, `supabase>=2.8`, `realtime>=2.0`; wire into `dev` group |
| `.env.example` | Uncomment cache TTL variables; document DB connection rules |
| `.github/workflows/ci.yml` | Add `integration-tests` job (optional, behind branch filter or label) — NOT required in M2.2, flagged as follow-up |

---

## Execution Order (phases)

1. **Deps bootstrap (Task 1)** — M2 optional deps installed.
2. **Migrations (Tasks 2–7)** — 6 SQL files authored, reviewed, NOT applied yet (no DB).
3. **Seed (Task 8)** — venues baseline.
4. **Apply + verify schema (Task 9)** — `supabase start` + `supabase db push`; if Docker unavailable, mark task as skipped with instructions.
5. **Python infrastructure layer (Tasks 10–14)** — pool, mappers (TDD), stubs, gateway skeleton.
6. **Gateway write/read paths (Tasks 15–16)** — OHLCV + ticker + query log integration tests.
7. **Full verification + tag (Tasks 17–18)** — lint/mypy/coverage; v0.0.3 release notes.

---

## Tasks

### Task 1: Add M2 optional-dependencies group

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read current optional-dependencies block**

```bash
cd /Users/laptop/dev/cryptozavr
grep -A 20 "\[project.optional-dependencies\]" pyproject.toml
```

Current groups: `dev` only.

- [ ] **Step 2: Add M2 group and extend dev**

Use Edit tool to change this block:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5",
    "pytest-xdist>=3.6",
    "ruff>=0.6",
    "mypy>=1.11",
    "pre-commit>=3.8",
    "dirty-equals>=0.8",
    "hypothesis>=6.100",
    "polyfactory>=2.18",
]
```

Replace with:

```toml
[project.optional-dependencies]
m2 = [
    "asyncpg>=0.29",
    "supabase>=2.8",
    "realtime>=2.0",
]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5",
    "pytest-xdist>=3.6",
    "ruff>=0.6",
    "mypy>=1.11",
    "pre-commit>=3.8",
    "dirty-equals>=0.8",
    "hypothesis>=6.100",
    "polyfactory>=2.18",
    # M2 runtime deps also needed for dev (mappers, gateway unit tests)
    "asyncpg>=0.29",
    "supabase>=2.8",
    "realtime>=2.0",
]
```

- [ ] **Step 3: Sync deps**

```bash
cd /Users/laptop/dev/cryptozavr
uv sync --all-extras
```

Expected: `+ asyncpg==...`, `+ supabase==...`, `+ realtime==...` installed among other transitive packages.

- [ ] **Step 4: Verify imports**

```bash
cd /Users/laptop/dev/cryptozavr
uv run python -c "import asyncpg; import supabase; import realtime; print('ok')"
```

Expected: `ok`.

- [ ] **Step 5: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add pyproject.toml uv.lock
```

Write to `/tmp/commit-msg.txt`:
```bash
chore: add asyncpg + supabase + realtime as M2 deps

asyncpg for asyncpg hot-path (bulk upserts, range reads).
supabase-py (async) for RPC/Storage/admin ops.
realtime-py for postgres_changes subscriptions (stubbed in M2.2,
activated in phase 1.5).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 2: Extensions migration

**Files:**
- Create: `supabase/migrations/00000000000000_extensions.sql`

- [ ] **Step 1: Write extensions.sql**

Write to `/Users/laptop/dev/cryptozavr/supabase/migrations/00000000000000_extensions.sql`:
```sql
-- Enable required Postgres extensions and create the cryptozavr schema.
-- Idempotent: all statements use IF NOT EXISTS where applicable.

create extension if not exists vector with schema extensions;
create extension if not exists pg_cron with schema extensions;
create extension if not exists pg_net with schema extensions;
create extension if not exists pg_trgm with schema extensions;

create schema if not exists cryptozavr;

grant usage on schema cryptozavr to service_role;
grant usage on schema cryptozavr to authenticated;
grant usage on schema cryptozavr to anon;
```

- [ ] **Step 2: Verify file**

```bash
cd /Users/laptop/dev/cryptozavr
cat supabase/migrations/00000000000000_extensions.sql
```

Expected output: the SQL content above.

- [ ] **Step 3: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add supabase/migrations/00000000000000_extensions.sql
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(supabase): add extensions migration

Enables vector, pg_cron, pg_net, pg_trgm in extensions schema.
Creates cryptozavr schema with usage grants for service_role,
authenticated, and anon roles (row access still gated by RLS).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 3: Reference tables migration

**Files:**
- Create: `supabase/migrations/00000000000010_reference.sql`

- [ ] **Step 1: Write reference.sql**

Write to `/Users/laptop/dev/cryptozavr/supabase/migrations/00000000000010_reference.sql`:
```sql
-- Reference tables: venues, assets, symbols, symbol_aliases + supporting enums.
-- Designed to match domain entities in src/cryptozavr/domain/venues.py,
-- assets.py, symbols.py.

create type cryptozavr.venue_kind as enum ('exchange_cex', 'exchange_dex', 'aggregator');
create type cryptozavr.venue_state_kind as enum ('healthy', 'degraded', 'rate_limited', 'down');
create type cryptozavr.market_type as enum ('spot', 'linear_perp', 'inverse_perp');
create type cryptozavr.timeframe as enum ('1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w');

create table cryptozavr.venues (
  id               text primary key,
  kind             cryptozavr.venue_kind not null,
  display_name     text not null,
  capabilities     text[] not null default '{}',
  state            cryptozavr.venue_state_kind not null default 'healthy',
  state_changed_at timestamptz not null default now(),
  meta             jsonb not null default '{}'
);

create table cryptozavr.assets (
  code            text primary key,
  name            text,
  coingecko_id    text unique,
  market_cap_rank int,
  categories      text[] not null default '{}',
  meta            jsonb not null default '{}',
  updated_at      timestamptz not null default now()
);

create table cryptozavr.symbols (
  id            bigint generated always as identity primary key,
  venue_id      text not null references cryptozavr.venues(id),
  base          text not null,
  quote         text not null,
  market_type   cryptozavr.market_type not null default 'spot',
  native_symbol text not null,
  active        boolean not null default true,
  meta          jsonb not null default '{}',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (venue_id, base, quote, market_type)
);

create index symbols_active_by_venue
  on cryptozavr.symbols (venue_id, active);

create index symbols_native_trgm
  on cryptozavr.symbols using gin (native_symbol gin_trgm_ops);

create table cryptozavr.symbol_aliases (
  id        bigint generated always as identity primary key,
  alias     text not null,
  base      text,
  symbol_id bigint references cryptozavr.symbols(id) on delete cascade,
  venue_id  text references cryptozavr.venues(id),
  source    text not null default 'manual',
  unique (alias, venue_id)
);

create index symbol_aliases_alias_trgm
  on cryptozavr.symbol_aliases using gin (alias gin_trgm_ops);
```

- [ ] **Step 2: Verify**

```bash
cd /Users/laptop/dev/cryptozavr
wc -l supabase/migrations/00000000000010_reference.sql
```

Expected: ~55 lines.

- [ ] **Step 3: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add supabase/migrations/00000000000010_reference.sql
```

Write to `/tmp/commit-msg.txt`:
```text
feat(supabase): add reference schema (venues/assets/symbols/aliases)

Enums: venue_kind, venue_state_kind, market_type, timeframe.
Tables: venues (kucoin/coingecko identity), assets (by uppercase code),
symbols (unique on venue+base+quote+market_type), symbol_aliases (fuzzy
lookup via pg_trgm GIN index).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 4: Market data tables migration

**Files:**
- Create: `supabase/migrations/00000000000020_market_data.sql`

- [ ] **Step 1: Write market_data.sql**

Write to `/Users/laptop/dev/cryptozavr/supabase/migrations/00000000000020_market_data.sql`:
```sql
-- Hot cache: tickers_live (one row per symbol, upserted every few seconds).
-- Warm cache: ohlcv_candles (millions of rows, compound PK), orderbook_snapshots, trades.

create table cryptozavr.tickers_live (
  symbol_id       bigint primary key references cryptozavr.symbols(id) on delete cascade,
  last            numeric(38, 18) not null,
  bid             numeric(38, 18),
  ask             numeric(38, 18),
  volume_24h      numeric(38, 18),
  change_24h_pct  numeric(10, 6),
  high_24h        numeric(38, 18),
  low_24h         numeric(38, 18),
  observed_at     timestamptz not null,
  fetched_at      timestamptz not null default now(),
  source_endpoint text not null default 'fetch_ticker'
);

create table cryptozavr.ohlcv_candles (
  symbol_id  bigint not null references cryptozavr.symbols(id) on delete cascade,
  timeframe  cryptozavr.timeframe not null,
  opened_at  timestamptz not null,
  open       numeric(38, 18) not null,
  high       numeric(38, 18) not null,
  low        numeric(38, 18) not null,
  close      numeric(38, 18) not null,
  volume     numeric(38, 18) not null,
  closed     boolean not null default true,
  fetched_at timestamptz not null default now(),
  primary key (symbol_id, timeframe, opened_at)
);

create index ohlcv_by_symbol_tf_opened_desc
  on cryptozavr.ohlcv_candles (symbol_id, timeframe, opened_at desc);

create table cryptozavr.orderbook_snapshots (
  id           bigint generated always as identity primary key,
  symbol_id    bigint not null references cryptozavr.symbols(id) on delete cascade,
  bids         jsonb not null,
  asks         jsonb not null,
  depth_levels int not null,
  observed_at  timestamptz not null,
  fetched_at   timestamptz not null default now()
);

create index orderbook_snapshots_by_symbol_observed_desc
  on cryptozavr.orderbook_snapshots (symbol_id, observed_at desc);

create table cryptozavr.trades (
  id          bigint generated always as identity primary key,
  symbol_id   bigint not null references cryptozavr.symbols(id) on delete cascade,
  trade_id    text,
  price       numeric(38, 18) not null,
  size        numeric(38, 18) not null,
  side        text check (side in ('buy', 'sell', 'unknown')),
  executed_at timestamptz not null,
  fetched_at  timestamptz not null default now(),
  unique (symbol_id, trade_id)
);

create index trades_by_symbol_executed_desc
  on cryptozavr.trades (symbol_id, executed_at desc);
```

- [ ] **Step 2: Verify**

```bash
cd /Users/laptop/dev/cryptozavr
wc -l supabase/migrations/00000000000020_market_data.sql
```

Expected: ~60 lines.

- [ ] **Step 3: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add supabase/migrations/00000000000020_market_data.sql
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(supabase): add market_data tables

tickers_live: hot cache, one row per symbol with upsert on every refresh.
ohlcv_candles: composite PK (symbol_id, timeframe, opened_at) + DESC index
for range reads. orderbook_snapshots: JSONB bids/asks for compact storage.
trades: unique (symbol_id, trade_id) for dedup.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 5: Audit tables migration

**Files:**
- Create: `supabase/migrations/00000000000030_audit.sql`

- [ ] **Step 1: Write audit.sql**

Write to `/Users/laptop/dev/cryptozavr/supabase/migrations/00000000000030_audit.sql`:
```sql
-- Audit / explainability tables: query_log (MCP tool calls), provider_events (venue health).

create type cryptozavr.query_kind as enum (
  'ohlcv', 'ticker', 'orderbook', 'trades', 'snapshot', 'discovery', 'analyze'
);

create table cryptozavr.query_log (
  id              uuid primary key default gen_random_uuid(),
  kind            cryptozavr.query_kind not null,
  symbol_id       bigint references cryptozavr.symbols(id),
  timeframe       cryptozavr.timeframe,
  range_start     timestamptz,
  range_end       timestamptz,
  limit_n         int,
  force_refresh   boolean not null default false,
  reason_codes    text[] not null default '{}',
  quality         jsonb,
  issued_by       text not null,
  client_id       text,
  issued_at       timestamptz not null default now(),
  query_embedding extensions.halfvec(1536)  -- populated in phase 2+ for semantic similarity
);

create index query_log_issued_at_desc
  on cryptozavr.query_log (issued_at desc);
create index query_log_by_client_issued_desc
  on cryptozavr.query_log (client_id, issued_at desc);
create index query_log_by_kind_issued_desc
  on cryptozavr.query_log (kind, issued_at desc);

create table cryptozavr.provider_events (
  id           bigint generated always as identity primary key,
  venue_id     text not null references cryptozavr.venues(id),
  kind         text not null,                 -- 'state_transition' | 'rate_limit' | 'outage'
  from_state   cryptozavr.venue_state_kind,
  to_state     cryptozavr.venue_state_kind,
  details      jsonb not null default '{}',
  occurred_at  timestamptz not null default now()
);

create index provider_events_by_venue_occurred_desc
  on cryptozavr.provider_events (venue_id, occurred_at desc);
```

- [ ] **Step 2: Verify**

```bash
cd /Users/laptop/dev/cryptozavr
wc -l supabase/migrations/00000000000030_audit.sql
```

Expected: ~35 lines.

- [ ] **Step 3: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add supabase/migrations/00000000000030_audit.sql
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(supabase): add audit tables (query_log + provider_events)

query_log: UUID PK, kind enum, symbol/timeframe/range/limit, reason_codes,
quality JSONB, issued_by/client_id — plus halfvec(1536) embedding column
(reserved for phase 2+ semantic similarity). Three indexes for recent
queries, per-client, per-kind lookups.
provider_events: venue state transitions and outages for health history.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 6: Row-Level Security migration

**Files:**
- Create: `supabase/migrations/00000000000040_rls.sql`

- [ ] **Step 1: Write rls.sql**

Write to `/Users/laptop/dev/cryptozavr/supabase/migrations/00000000000040_rls.sql`:
```sql
-- Enable RLS on every cryptozavr table + allow service_role full access.
-- MVP is single-user: anon/authenticated get nothing until phase 2+ Auth lands.

alter table cryptozavr.venues              enable row level security;
alter table cryptozavr.assets              enable row level security;
alter table cryptozavr.symbols             enable row level security;
alter table cryptozavr.symbol_aliases      enable row level security;
alter table cryptozavr.tickers_live        enable row level security;
alter table cryptozavr.ohlcv_candles       enable row level security;
alter table cryptozavr.orderbook_snapshots enable row level security;
alter table cryptozavr.trades              enable row level security;
alter table cryptozavr.query_log           enable row level security;
alter table cryptozavr.provider_events     enable row level security;

-- Service-role full access (bypasses RLS via superuser bit for postgres,
-- but we also want explicit policies for clarity when running as
-- service_role via PostgREST).

create policy service_role_all on cryptozavr.venues
  for all to service_role using (true) with check (true);
create policy service_role_all on cryptozavr.assets
  for all to service_role using (true) with check (true);
create policy service_role_all on cryptozavr.symbols
  for all to service_role using (true) with check (true);
create policy service_role_all on cryptozavr.symbol_aliases
  for all to service_role using (true) with check (true);
create policy service_role_all on cryptozavr.tickers_live
  for all to service_role using (true) with check (true);
create policy service_role_all on cryptozavr.ohlcv_candles
  for all to service_role using (true) with check (true);
create policy service_role_all on cryptozavr.orderbook_snapshots
  for all to service_role using (true) with check (true);
create policy service_role_all on cryptozavr.trades
  for all to service_role using (true) with check (true);
create policy service_role_all on cryptozavr.query_log
  for all to service_role using (true) with check (true);
create policy service_role_all on cryptozavr.provider_events
  for all to service_role using (true) with check (true);
```

- [ ] **Step 2: Verify**

```bash
cd /Users/laptop/dev/cryptozavr
grep -c "^alter table\|^create policy" supabase/migrations/00000000000040_rls.sql
```

Expected: 20 (10 alter + 10 policies).

- [ ] **Step 3: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add supabase/migrations/00000000000040_rls.sql
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(supabase): enable RLS with service_role full-access policies

RLS ON for all 10 cryptozavr tables. Explicit service_role ALL policies
for clarity (service_role bypasses RLS by privilege, but named policies
document the intended contract). anon/authenticated get no access in
MVP — gated at policy level until phase 2+ Auth.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 7: pg_cron jobs migration

**Files:**
- Create: `supabase/migrations/00000000000050_cron.sql`

- [ ] **Step 1: Write cron.sql**

Write to `/Users/laptop/dev/cryptozavr/supabase/migrations/00000000000050_cron.sql`:
```sql
-- pg_cron jobs for background maintenance.
-- refresh-symbols: queued as marker in maintenance_queue; Python worker drains.
-- In M2.2 we only schedule two pruning jobs that run purely in-DB.

-- Prune tickers whose observed_at is older than 5 minutes (every 15 minutes).
select cron.schedule(
  'prune-stale-tickers',
  '*/15 * * * *',
  $$
    delete from cryptozavr.tickers_live
     where observed_at < now() - interval '5 minutes'
  $$
);

-- Retain query_log for 30 days (run daily at 03:00 UTC).
select cron.schedule(
  'prune-query-log',
  '0 3 * * *',
  $$
    delete from cryptozavr.query_log
     where issued_at < now() - interval '30 days'
  $$
);
```

- [ ] **Step 2: Verify**

```bash
cd /Users/laptop/dev/cryptozavr
grep -c "cron.schedule" supabase/migrations/00000000000050_cron.sql
```

Expected: 2.

- [ ] **Step 3: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add supabase/migrations/00000000000050_cron.sql
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(supabase): schedule pg_cron jobs for pruning

prune-stale-tickers: every 15m delete rows whose observed_at >5m old.
prune-query-log: daily 03:00 UTC, retain 30 days.

Symbol-refresh job intentionally deferred: it needs a Python worker
(CCXT calls) — will arrive in M2.3 Providers via maintenance_queue.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 8: Seed venues

**Files:**
- Modify: `supabase/seed.sql`

- [ ] **Step 1: Replace seed.sql content**

Write to `/Users/laptop/dev/cryptozavr/supabase/seed.sql`:
```sql
-- Seed data for local development.
-- Baseline venues referenced throughout M2.x code paths.

insert into cryptozavr.venues (id, kind, display_name, capabilities)
values
  ('kucoin', 'exchange_cex', 'KuCoin',
    array['spot_ohlcv', 'spot_orderbook', 'spot_trades', 'spot_ticker',
          'futures_ohlcv', 'funding_rate', 'open_interest']),
  ('coingecko', 'aggregator', 'CoinGecko',
    array['market_cap_rank', 'category_data', 'spot_ticker'])
on conflict (id) do update
  set kind = excluded.kind,
      display_name = excluded.display_name,
      capabilities = excluded.capabilities;
```

- [ ] **Step 2: Verify**

```bash
cd /Users/laptop/dev/cryptozavr
cat supabase/seed.sql
```

Expected: the SQL above; two venue rows.

- [ ] **Step 3: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add supabase/seed.sql
```

Write to `/tmp/commit-msg.txt`:
```text
feat(supabase): seed kucoin + coingecko venues

Upsert with on-conflict preserves idempotency: running `supabase db reset`
+ seed always lands the same two venues with their capabilities.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 9: Apply migrations + verify (conditional)

**Files:** (none — verification task; no code changes)

- [ ] **Step 1: Check Docker availability**

```bash
docker info 2>&1 | head -5
```

If Docker is running → continue to Step 2. If Docker is NOT running, document in the plan output that verification is deferred (user will run this after starting Docker), then SKIP Steps 2-5 and mark this task **deferred**.

- [ ] **Step 2: Start Supabase**

```bash
cd /Users/laptop/dev/cryptozavr
supabase start
```

Expected: docker images pull (first run ~2-3min), then all services report healthy. Note the printed API URL, anon key, service_role key, db URL.

- [ ] **Step 3: Push migrations**

```bash
cd /Users/laptop/dev/cryptozavr
supabase db push
```

Expected: `Applying migration 00000000000000_extensions.sql`, ..., `Applying migration 00000000000050_cron.sql`. All 6 apply cleanly.

If a migration fails: inspect error, adjust migration SQL, commit fix, rerun `supabase db reset` + `supabase db push`.

- [ ] **Step 4: Verify schema**

```bash
cd /Users/laptop/dev/cryptozavr
supabase db execute --db-url "postgresql://postgres:postgres@127.0.0.1:54322/postgres" --query "
  select table_name from information_schema.tables
   where table_schema = 'cryptozavr' order by table_name;
"
```

Expected tables: `assets`, `ohlcv_candles`, `orderbook_snapshots`, `provider_events`, `query_log`, `symbol_aliases`, `symbols`, `tickers_live`, `trades`, `venues`.

If `supabase db execute` syntax differs in your Supabase CLI version, use `psql "postgresql://postgres:postgres@127.0.0.1:54322/postgres" -c "<query>"` instead.

- [ ] **Step 5: Verify cron jobs**

```bash
cd /Users/laptop/dev/cryptozavr
supabase db execute --db-url "postgresql://postgres:postgres@127.0.0.1:54322/postgres" --query "
  select jobname, schedule from cron.job order by jobname;
"
```

Expected:
```text
prune-query-log     | 0 3 * * *
prune-stale-tickers | */15 * * * *
```

- [ ] **Step 6: Stop Supabase (clean up)**

```bash
cd /Users/laptop/dev/cryptozavr
supabase stop
```

**No commit** — verification only. If any issue surfaces, fix the offending migration in its own commit.

---

### Task 10: Infrastructure supabase package scaffolding

**Files:**
- Create: `src/cryptozavr/infrastructure/supabase/__init__.py`
- Create: `tests/unit/infrastructure/__init__.py`
- Create: `tests/unit/infrastructure/supabase/__init__.py`
- Create: `tests/integration/__init__.py`

- [ ] **Step 1: Create src package marker**

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/supabase/__init__.py`:
```python
"""Supabase integration: pool, gateway, mappers, realtime/storage/rpc wrappers.

Populated in M2.2 (schema migrations already live under supabase/migrations/).
"""
```

- [ ] **Step 2: Create test package markers (3 empty files)**

Write empty content (0 bytes) to:
- `/Users/laptop/dev/cryptozavr/tests/unit/infrastructure/__init__.py`
- `/Users/laptop/dev/cryptozavr/tests/unit/infrastructure/supabase/__init__.py`
- `/Users/laptop/dev/cryptozavr/tests/integration/__init__.py`

- [ ] **Step 3: Verify**

```bash
cd /Users/laptop/dev/cryptozavr
uv run python -c "
import cryptozavr.infrastructure.supabase
import tests.unit.infrastructure.supabase
import tests.integration
print('ok')
"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/infrastructure/supabase tests/unit/infrastructure tests/integration
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(infrastructure): scaffold supabase package + test directories

Empty markers for src/cryptozavr/infrastructure/supabase/ and the two
matching test dirs (unit/infrastructure/supabase + integration/).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 11: asyncpg pool factory

**Files:**
- Create: `src/cryptozavr/infrastructure/supabase/pg_pool.py`
- Create: `tests/unit/infrastructure/supabase/test_pg_pool.py`

- [ ] **Step 1: Write failing test**

Write to `/Users/laptop/dev/cryptozavr/tests/unit/infrastructure/supabase/test_pg_pool.py`:
```python
"""Test asyncpg Pool factory configuration and lifecycle."""

from __future__ import annotations

import pytest

from cryptozavr.infrastructure.supabase.pg_pool import PgPoolConfig, create_pool

class TestPgPoolConfig:
    def test_defaults(self) -> None:
        cfg = PgPoolConfig(dsn="postgresql://user:pw@host:5432/db")
        assert cfg.dsn == "postgresql://user:pw@host:5432/db"
        assert cfg.min_size == 1
        assert cfg.max_size == 10
        assert cfg.max_inactive_connection_lifetime == 60.0
        assert cfg.command_timeout == 30.0

    def test_custom(self) -> None:
        cfg = PgPoolConfig(
            dsn="postgresql://u:p@h/d",
            min_size=5,
            max_size=20,
            max_inactive_connection_lifetime=120.0,
            command_timeout=10.0,
        )
        assert cfg.min_size == 5
        assert cfg.max_size == 20
        assert cfg.max_inactive_connection_lifetime == 120.0
        assert cfg.command_timeout == 10.0

@pytest.mark.asyncio
async def test_create_pool_invalid_dsn_raises() -> None:
    """Invalid DSN must surface as an exception from asyncpg."""
    cfg = PgPoolConfig(dsn="postgresql://invalid:invalid@127.0.0.1:1/nowhere")
    with pytest.raises(Exception):
        pool = await create_pool(cfg)
        await pool.close()
```

- [ ] **Step 2: Run — must FAIL**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/supabase/test_pg_pool.py -v
```

Expected: `ModuleNotFoundError: No module named 'cryptozavr.infrastructure.supabase.pg_pool'`.

- [ ] **Step 3: Implement pg_pool.py**

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/supabase/pg_pool.py`:
```python
"""asyncpg Pool factory wrapper.

One Pool per process (Singleton via DI). Lifespan managed by the application
(FastMCP startup/shutdown hooks in L5).
"""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg

@dataclass(frozen=True, slots=True)
class PgPoolConfig:
    """Connection-pool sizing and timeouts for asyncpg."""

    dsn: str
    min_size: int = 1
    max_size: int = 10
    max_inactive_connection_lifetime: float = 60.0
    command_timeout: float = 30.0

async def create_pool(config: PgPoolConfig) -> asyncpg.Pool:
    """Create an asyncpg.Pool. Caller is responsible for awaiting pool.close()."""
    return await asyncpg.create_pool(
        dsn=config.dsn,
        min_size=config.min_size,
        max_size=config.max_size,
        max_inactive_connection_lifetime=config.max_inactive_connection_lifetime,
        command_timeout=config.command_timeout,
    )
```

- [ ] **Step 4: Run — must PASS**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/supabase/test_pg_pool.py -v
```

Expected: 3 passed (2 config + 1 invalid-dsn).

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/infrastructure/supabase/pg_pool.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/infrastructure/supabase/pg_pool.py tests/unit/infrastructure/supabase/test_pg_pool.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(supabase): add asyncpg Pool factory

PgPoolConfig: DSN + min_size/max_size + lifetime/timeout tunables.
create_pool(config) -> asyncpg.Pool. Caller owns lifecycle (close).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 12: Mappers — rows → Domain entities (TDD, unit tests only)

**Files:**
- Create: `src/cryptozavr/infrastructure/supabase/mappers.py`
- Create: `tests/unit/infrastructure/supabase/test_mappers.py`

- [ ] **Step 1: Write failing tests**

Write to `/Users/laptop/dev/cryptozavr/tests/unit/infrastructure/supabase/test_mappers.py`:
```python
"""Test pure row-to-Domain mappers."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId
from cryptozavr.infrastructure.supabase.mappers import (
    row_to_ohlcv_candle,
    row_to_ohlcv_series,
    row_to_symbol,
    row_to_ticker,
)

@pytest.fixture
def registry() -> SymbolRegistry:
    return SymbolRegistry()

@pytest.fixture
def btc_symbol(registry: SymbolRegistry) -> Symbol:
    return registry.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

def _fresh_quality() -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
        fetched_at=Instant.now(),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=True,  # from DB is always cache_hit
    )

class TestRowToSymbol:
    def test_happy_path(self, registry: SymbolRegistry) -> None:
        row = {
            "id": 42,
            "venue_id": "kucoin",
            "base": "BTC",
            "quote": "USDT",
            "market_type": "spot",
            "native_symbol": "BTC-USDT",
            "active": True,
        }
        sym = row_to_symbol(row, registry)
        assert sym.venue == VenueId.KUCOIN
        assert sym.base == "BTC"
        assert sym.quote == "USDT"
        assert sym.market_type == MarketType.SPOT
        assert sym.native_symbol == "BTC-USDT"

    def test_reuses_registry_instance(self, registry: SymbolRegistry, btc_symbol: Symbol) -> None:
        row = {
            "id": 42, "venue_id": "kucoin", "base": "BTC", "quote": "USDT",
            "market_type": "spot", "native_symbol": "BTC-USDT", "active": True,
        }
        sym = row_to_symbol(row, registry)
        assert sym is btc_symbol  # Flyweight identity preserved

class TestRowToTicker:
    def test_full_row(self, btc_symbol: Symbol) -> None:
        observed = datetime(2026, 4, 21, 10, 0, 0, tzinfo=timezone.utc)
        row = {
            "symbol_id": 42,
            "last": Decimal("65000.50"),
            "bid": Decimal("64999.50"),
            "ask": Decimal("65001.50"),
            "volume_24h": Decimal("1234.56"),
            "change_24h_pct": Decimal("2.5"),
            "high_24h": Decimal("66000"),
            "low_24h": Decimal("64000"),
            "observed_at": observed,
            "fetched_at": observed,
            "source_endpoint": "fetch_ticker",
        }
        ticker = row_to_ticker(row, symbol=btc_symbol, quality=_fresh_quality())
        assert ticker.last == Decimal("65000.50")
        assert ticker.bid == Decimal("64999.50")
        assert ticker.ask == Decimal("65001.50")
        assert ticker.volume_24h == Decimal("1234.56")
        assert ticker.change_24h_pct is not None
        assert ticker.change_24h_pct.value == Decimal("2.5")
        assert ticker.observed_at == Instant(observed)

    def test_minimal_row(self, btc_symbol: Symbol) -> None:
        observed = datetime(2026, 4, 21, 10, 0, 0, tzinfo=timezone.utc)
        row = {
            "symbol_id": 42, "last": Decimal("65000"), "bid": None, "ask": None,
            "volume_24h": None, "change_24h_pct": None, "high_24h": None, "low_24h": None,
            "observed_at": observed, "fetched_at": observed,
            "source_endpoint": "fetch_ticker",
        }
        ticker = row_to_ticker(row, symbol=btc_symbol, quality=_fresh_quality())
        assert ticker.last == Decimal("65000")
        assert ticker.bid is None

class TestRowToOhlcvCandle:
    def test_happy_path(self) -> None:
        opened = datetime(2026, 4, 21, 10, 0, 0, tzinfo=timezone.utc)
        row = {
            "opened_at": opened,
            "open": Decimal("100"),
            "high": Decimal("110"),
            "low": Decimal("90"),
            "close": Decimal("105"),
            "volume": Decimal("1000"),
            "closed": True,
        }
        candle = row_to_ohlcv_candle(row)
        assert candle.opened_at == Instant(opened)
        assert candle.open == Decimal("100")
        assert candle.high == Decimal("110")
        assert candle.low == Decimal("90")
        assert candle.close == Decimal("105")
        assert candle.volume == Decimal("1000")
        assert candle.closed is True

class TestRowToOhlcvSeries:
    def test_happy_path(self, btc_symbol: Symbol) -> None:
        rows = [
            {
                "opened_at": datetime(2026, 4, 21, 10 + i, 0, 0, tzinfo=timezone.utc),
                "open": Decimal("100"),
                "high": Decimal("110"),
                "low": Decimal("90"),
                "close": Decimal("105"),
                "volume": Decimal("1000"),
                "closed": True,
            }
            for i in range(3)
        ]
        series = row_to_ohlcv_series(
            rows,
            symbol=btc_symbol,
            timeframe=Timeframe.H1,
            quality=_fresh_quality(),
        )
        assert len(series.candles) == 3
        assert series.timeframe == Timeframe.H1
        assert series.symbol is btc_symbol

    def test_empty_rows_raises(self, btc_symbol: Symbol) -> None:
        with pytest.raises(ValueError):
            row_to_ohlcv_series(
                [],
                symbol=btc_symbol,
                timeframe=Timeframe.H1,
                quality=_fresh_quality(),
            )
```

- [ ] **Step 2: Run — FAIL expected**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/supabase/test_mappers.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement mappers.py**

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/supabase/mappers.py`:
```python
"""Pure functions converting Supabase rows (dict-like) to Domain entities.

No I/O. These are called by SupabaseGateway after fetching rows via asyncpg.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from cryptozavr.domain.market_data import (
    OHLCVCandle,
    OHLCVSeries,
    Ticker,
)
from cryptozavr.domain.quality import DataQuality
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.value_objects import (
    Instant,
    Percentage,
    Timeframe,
    TimeRange,
)
from cryptozavr.domain.venues import MarketType, VenueId

def row_to_symbol(row: Mapping[str, Any], registry: SymbolRegistry) -> Symbol:
    """Resolve a symbols row through the Flyweight registry.

    Identity is (venue, base, quote, market_type); metadata (id, active) ignored.
    """
    return registry.get(
        VenueId(row["venue_id"]),
        row["base"],
        row["quote"],
        market_type=MarketType(row["market_type"]),
        native_symbol=row["native_symbol"],
    )

def row_to_ticker(
    row: Mapping[str, Any],
    *,
    symbol: Symbol,
    quality: DataQuality,
) -> Ticker:
    """Map tickers_live row + resolved Symbol + externally-computed DataQuality."""
    change_pct_raw = row.get("change_24h_pct")
    change_pct = (
        Percentage(value=Decimal(str(change_pct_raw)))
        if change_pct_raw is not None
        else None
    )
    return Ticker(
        symbol=symbol,
        last=Decimal(str(row["last"])),
        observed_at=Instant(row["observed_at"]),
        quality=quality,
        bid=_optional_decimal(row.get("bid")),
        ask=_optional_decimal(row.get("ask")),
        volume_24h=_optional_decimal(row.get("volume_24h")),
        change_24h_pct=change_pct,
        high_24h=_optional_decimal(row.get("high_24h")),
        low_24h=_optional_decimal(row.get("low_24h")),
    )

def row_to_ohlcv_candle(row: Mapping[str, Any]) -> OHLCVCandle:
    """Map a single ohlcv_candles row."""
    return OHLCVCandle(
        opened_at=Instant(row["opened_at"]),
        open=Decimal(str(row["open"])),
        high=Decimal(str(row["high"])),
        low=Decimal(str(row["low"])),
        close=Decimal(str(row["close"])),
        volume=Decimal(str(row["volume"])),
        closed=bool(row["closed"]),
    )

def row_to_ohlcv_series(
    rows: Sequence[Mapping[str, Any]],
    *,
    symbol: Symbol,
    timeframe: Timeframe,
    quality: DataQuality,
) -> OHLCVSeries:
    """Map a list of ohlcv_candles rows into an OHLCVSeries.

    Rows must be non-empty (series range is derived from first/last opened_at).
    """
    if not rows:
        raise ValueError("row_to_ohlcv_series requires at least one row")
    candles = tuple(row_to_ohlcv_candle(r) for r in rows)
    tf_ms = timeframe.to_milliseconds()
    last_open_ms = candles[-1].opened_at.to_ms()
    # Series range is half-open: [first_opened_at, last_opened_at + 1 timeframe).
    series_range = TimeRange(
        start=candles[0].opened_at,
        end=Instant.from_ms(last_open_ms + tf_ms),
    )
    return OHLCVSeries(
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        range=series_range,
        quality=quality,
    )

def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))
```

- [ ] **Step 4: Run — PASS**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit/infrastructure/supabase/test_mappers.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/infrastructure/supabase/mappers.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/infrastructure/supabase/mappers.py tests/unit/infrastructure/supabase/test_mappers.py
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(supabase): add row → Domain mappers

Pure functions: row_to_symbol (via SymbolRegistry Flyweight), row_to_ticker,
row_to_ohlcv_candle, row_to_ohlcv_series. Zero I/O. Consumers pass in
DataQuality + resolved Symbol explicitly — keeps mappers composable.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 13: Realtime + Storage + RPC stubs

**Files:**
- Create: `src/cryptozavr/infrastructure/supabase/realtime.py`
- Create: `src/cryptozavr/infrastructure/supabase/storage.py`
- Create: `src/cryptozavr/infrastructure/supabase/rpc.py`

- [ ] **Step 1: Write realtime.py (stub)**

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/supabase/realtime.py`:
```python
"""Realtime subscriptions wrapper — stub for M2.2.

Full implementation (postgres_changes subscriptions for tickers/decisions)
lands in phase 1.5 per MVP design spec section 11.
"""

from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class SubscriptionHandle:
    """Identifier for an active realtime subscription. Used to unsubscribe later."""

    channel_id: str

class RealtimeSubscriber:
    """Stub: raises NotImplementedError in M2.2. Replaced in phase 1.5."""

    def __init__(self) -> None:
        pass

    async def subscribe_tickers(
        self,
        venue_id: str,
        callback: object,  # Callable[[Ticker], Awaitable[None]] — tightened in phase 1.5
    ) -> SubscriptionHandle:
        raise NotImplementedError(
            "Realtime subscriptions arrive in phase 1.5; see MVP spec section 11."
        )

    async def close(self) -> None:
        return None
```

- [ ] **Step 2: Write storage.py (stub)**

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/supabase/storage.py`:
```python
"""Supabase Storage wrapper — stub for M2.2.

Full implementation (upload/download backtest reports, exported OHLCV)
lands in phase 2+ per MVP design spec section 5 Storage subsection.
"""

from __future__ import annotations

class StorageClient:
    """Stub: raises NotImplementedError in M2.2. Populated in phase 2+."""

    async def upload(
        self, bucket: str, key: str, data: bytes, content_type: str,
    ) -> str:
        raise NotImplementedError(
            "Storage uploads arrive in phase 2+ for backtest artefacts."
        )

    async def get_signed_url(self, bucket: str, key: str, expires_sec: int) -> str:
        raise NotImplementedError("Signed URLs arrive in phase 2+.")
```

- [ ] **Step 3: Write rpc.py (stub)**

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/supabase/rpc.py`:
```python
"""Typed RPC wrappers — stub for M2.2.

First real RPC lands in phase 2 with pgvector similarity search (match_regimes,
match_similar_strategies). See MVP design spec section 11 phase 2.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

class RpcClient:
    """Stub: raises NotImplementedError in M2.2. Populated in phase 2+."""

    async def match_regimes(
        self, embedding: Sequence[float], threshold: float, limit: int,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "match_regimes RPC arrives in phase 2 alongside pgvector activation."
        )
```

- [ ] **Step 4: Verify imports**

```bash
cd /Users/laptop/dev/cryptozavr
uv run python -c "
from cryptozavr.infrastructure.supabase.realtime import RealtimeSubscriber, SubscriptionHandle
from cryptozavr.infrastructure.supabase.storage import StorageClient
from cryptozavr.infrastructure.supabase.rpc import RpcClient
print('ok')
"
```

Expected: `ok`.

- [ ] **Step 5: Mypy**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/infrastructure/supabase/realtime.py src/cryptozavr/infrastructure/supabase/storage.py src/cryptozavr/infrastructure/supabase/rpc.py
```

Expected: Success.

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/infrastructure/supabase/realtime.py src/cryptozavr/infrastructure/supabase/storage.py src/cryptozavr/infrastructure/supabase/rpc.py
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(supabase): add realtime/storage/rpc stubs

All three classes raise NotImplementedError in M2.2 — signalling that the
interface is fixed but the impl ships later (realtime phase 1.5, storage
phase 2+, rpc phase 2+). SubscriptionHandle value object defined now so
SupabaseGateway.subscribe_* signatures are stable from day one.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 14: SupabaseGateway Facade + integration fixtures

**Files:**
- Create: `src/cryptozavr/infrastructure/supabase/gateway.py`
- Create: `tests/integration/conftest.py`

- [ ] **Step 1: Write gateway.py**

Write to `/Users/laptop/dev/cryptozavr/src/cryptozavr/infrastructure/supabase/gateway.py`:
```python
"""SupabaseGateway: Facade over asyncpg + supabase-py + realtime-py + storage/rpc.

M2.2 exposes:
- symbol id resolution (asyncpg)
- OHLCV upsert + range load (asyncpg bulk)
- ticker upsert + single-symbol load (asyncpg)
- query_log insert (asyncpg)
- close (lifecycle)

Stubs (raise NotImplementedError): realtime subscribe_tickers, storage
uploads, rpc match_regimes.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

import asyncpg

from cryptozavr.domain.market_data import OHLCVSeries, Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.infrastructure.supabase.mappers import (
    row_to_ohlcv_series,
    row_to_ticker,
)
from cryptozavr.infrastructure.supabase.realtime import (
    RealtimeSubscriber,
    SubscriptionHandle,
)
from cryptozavr.infrastructure.supabase.rpc import RpcClient
from cryptozavr.infrastructure.supabase.storage import StorageClient

class SupabaseGateway:
    """Facade over Supabase integration clients.

    Owns the asyncpg Pool; stubs realtime/storage/rpc until later phases.
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        symbol_registry: SymbolRegistry,
        *,
        realtime: RealtimeSubscriber | None = None,
        storage: StorageClient | None = None,
        rpc: RpcClient | None = None,
    ) -> None:
        self._pool = pool
        self._registry = symbol_registry
        self._realtime = realtime or RealtimeSubscriber()
        self._storage = storage or StorageClient()
        self._rpc = rpc or RpcClient()

    # --- Symbol resolution (used by every hot-path read/write) ---
    async def resolve_symbol_id(self, symbol: Symbol) -> int:
        """Look up symbols.id by identity tuple (venue, base, quote, market_type).

        Raises LookupError if the symbol is not yet registered in the DB.
        (Register via separate upsert_symbol path — will be added in M2.3 providers.)
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select id from cryptozavr.symbols
                 where venue_id = $1 and base = $2 and quote = $3 and market_type = $4
                """,
                symbol.venue.value,
                symbol.base,
                symbol.quote,
                symbol.market_type.value,
            )
        if row is None:
            raise LookupError(
                f"symbol not registered in DB: {symbol.venue.value}:"
                f"{symbol.base}/{symbol.quote}/{symbol.market_type.value}"
            )
        return int(row["id"])

    # --- Ticker ---
    async def upsert_ticker(self, ticker: Ticker) -> None:
        """Upsert a single ticker into tickers_live (one row per symbol)."""
        symbol_id = await self.resolve_symbol_id(ticker.symbol)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                insert into cryptozavr.tickers_live (
                  symbol_id, last, bid, ask, volume_24h, change_24h_pct,
                  high_24h, low_24h, observed_at, source_endpoint
                )
                values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                on conflict (symbol_id) do update set
                  last = excluded.last,
                  bid = excluded.bid,
                  ask = excluded.ask,
                  volume_24h = excluded.volume_24h,
                  change_24h_pct = excluded.change_24h_pct,
                  high_24h = excluded.high_24h,
                  low_24h = excluded.low_24h,
                  observed_at = excluded.observed_at,
                  fetched_at = now(),
                  source_endpoint = excluded.source_endpoint
                """,
                symbol_id,
                ticker.last,
                ticker.bid,
                ticker.ask,
                ticker.volume_24h,
                ticker.change_24h_pct.value if ticker.change_24h_pct else None,
                ticker.high_24h,
                ticker.low_24h,
                ticker.observed_at.to_datetime(),
                ticker.quality.source.endpoint,
            )

    async def load_ticker(self, symbol: Symbol) -> Ticker | None:
        """Fetch the latest ticker for symbol, if any."""
        symbol_id = await self.resolve_symbol_id(symbol)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select symbol_id, last, bid, ask, volume_24h, change_24h_pct,
                       high_24h, low_24h, observed_at, fetched_at, source_endpoint
                  from cryptozavr.tickers_live
                 where symbol_id = $1
                """,
                symbol_id,
            )
        if row is None:
            return None
        quality = DataQuality(
            source=Provenance(
                venue_id=symbol.venue.value,
                endpoint=row["source_endpoint"],
            ),
            fetched_at=Instant(row["fetched_at"]),
            staleness=Staleness.FRESH,  # caller may reclassify based on observed_at age
            confidence=Confidence.HIGH,
            cache_hit=True,
        )
        return row_to_ticker(row, symbol=symbol, quality=quality)

    # --- OHLCV ---
    async def upsert_ohlcv(self, series: OHLCVSeries) -> int:
        """Bulk-upsert OHLCV candles. Returns number of candles written."""
        if not series.candles:
            return 0
        symbol_id = await self.resolve_symbol_id(series.symbol)
        records = [
            (
                symbol_id,
                series.timeframe.value,
                c.opened_at.to_datetime(),
                c.open, c.high, c.low, c.close, c.volume,
                c.closed,
            )
            for c in series.candles
        ]
        async with self._pool.acquire() as conn:
            await conn.executemany(
                """
                insert into cryptozavr.ohlcv_candles (
                  symbol_id, timeframe, opened_at,
                  open, high, low, close, volume, closed
                )
                values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                on conflict (symbol_id, timeframe, opened_at) do update set
                  open = excluded.open,
                  high = excluded.high,
                  low = excluded.low,
                  close = excluded.close,
                  volume = excluded.volume,
                  closed = excluded.closed,
                  fetched_at = now()
                """,
                records,
            )
        return len(records)

    async def load_ohlcv(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        *,
        since: Instant | None = None,
        limit: int = 500,
    ) -> OHLCVSeries | None:
        """Fetch OHLCV range DESC-ordered by opened_at, then re-sort ASC for the domain series."""
        symbol_id = await self.resolve_symbol_id(symbol)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select opened_at, open, high, low, close, volume, closed
                  from cryptozavr.ohlcv_candles
                 where symbol_id = $1 and timeframe = $2
                   and ($3::timestamptz is null or opened_at >= $3)
                 order by opened_at desc
                 limit $4
                """,
                symbol_id,
                timeframe.value,
                since.to_datetime() if since else None,
                limit,
            )
        if not rows:
            return None
        ordered_rows: Sequence[dict[str, Any]] = list(reversed(rows))
        quality = DataQuality(
            source=Provenance(
                venue_id=symbol.venue.value,
                endpoint="fetch_ohlcv",
            ),
            fetched_at=Instant.now(),
            staleness=Staleness.FRESH,
            confidence=Confidence.HIGH,
            cache_hit=True,
        )
        return row_to_ohlcv_series(
            ordered_rows, symbol=symbol, timeframe=timeframe, quality=quality,
        )

    # --- Query log ---
    async def insert_query_log(
        self,
        *,
        kind: str,
        symbol: Symbol | None,
        timeframe: Timeframe | None,
        range_start: Instant | None,
        range_end: Instant | None,
        limit_n: int | None,
        force_refresh: bool,
        reason_codes: Sequence[str],
        quality: dict[str, Any] | None,
        issued_by: str,
        client_id: str | None,
    ) -> UUID:
        """Insert a row into query_log. Returns the generated UUID."""
        symbol_id: int | None = None
        if symbol is not None:
            symbol_id = await self.resolve_symbol_id(symbol)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                insert into cryptozavr.query_log (
                  kind, symbol_id, timeframe, range_start, range_end,
                  limit_n, force_refresh, reason_codes, quality,
                  issued_by, client_id
                )
                values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                returning id
                """,
                kind,
                symbol_id,
                timeframe.value if timeframe else None,
                range_start.to_datetime() if range_start else None,
                range_end.to_datetime() if range_end else None,
                limit_n,
                force_refresh,
                list(reason_codes),
                quality,
                issued_by,
                client_id,
            )
        assert row is not None  # INSERT ... RETURNING always yields one row
        return UUID(str(row["id"]))

    # --- Realtime / Storage / RPC delegations (stubs) ---
    async def subscribe_tickers(
        self, venue_id: str, callback: object,
    ) -> SubscriptionHandle:
        return await self._realtime.subscribe_tickers(venue_id, callback)

    async def upload_artifact(
        self, bucket: str, key: str, data: bytes, content_type: str,
    ) -> str:
        return await self._storage.upload(bucket, key, data, content_type)

    async def match_regimes(
        self, embedding: Sequence[float], threshold: float, limit: int,
    ) -> list[dict[str, Any]]:
        return await self._rpc.match_regimes(embedding, threshold, limit)

    # --- Lifecycle ---
    async def close(self) -> None:
        """Close the underlying pool. Safe to call multiple times."""
        await self._realtime.close()
        await self._pool.close()
```

- [ ] **Step 2: Write integration conftest**

Write to `/Users/laptop/dev/cryptozavr/tests/integration/conftest.py`:
```python
"""Fixtures for integration tests (require `supabase start` locally + Docker).

Tests using these fixtures are marked `integration`. Skip automatically if
Supabase is not reachable on the expected local URL.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.infrastructure.supabase.gateway import SupabaseGateway
from cryptozavr.infrastructure.supabase.pg_pool import PgPoolConfig, create_pool

LOCAL_DB_URL = os.environ.get(
    "SUPABASE_DB_URL",
    "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
)

async def _is_supabase_reachable(dsn: str) -> bool:
    try:
        conn = await asyncpg.connect(dsn, timeout=2)
        await conn.close()
        return True
    except Exception:
        return False

@pytest_asyncio.fixture(scope="session")
async def supabase_pool() -> AsyncIterator[asyncpg.Pool]:
    """Session-scoped pool against the local Supabase Postgres.

    Skips the whole integration session if Supabase is unreachable.
    """
    if not await _is_supabase_reachable(LOCAL_DB_URL):
        pytest.skip(
            "Supabase not reachable at " + LOCAL_DB_URL
            + " — run `supabase start` first."
        )
    pool = await create_pool(PgPoolConfig(dsn=LOCAL_DB_URL, min_size=1, max_size=5))
    yield pool
    await pool.close()

@pytest_asyncio.fixture
async def supabase_gateway(
    supabase_pool: asyncpg.Pool,
) -> AsyncIterator[SupabaseGateway]:
    """Gateway wired to the live local Supabase stack."""
    registry = SymbolRegistry()
    gw = SupabaseGateway(supabase_pool, registry)
    yield gw
    # Don't close the pool here — it's session-scoped.

@pytest_asyncio.fixture
async def clean_market_data(supabase_pool: asyncpg.Pool) -> AsyncIterator[None]:
    """Truncate market-data tables before each test to ensure clean slate."""
    async with supabase_pool.acquire() as conn:
        await conn.execute(
            "truncate table cryptozavr.tickers_live, "
            "cryptozavr.ohlcv_candles, "
            "cryptozavr.orderbook_snapshots, "
            "cryptozavr.trades "
            "restart identity cascade"
        )
    yield
```

- [ ] **Step 3: Mypy on gateway.py**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src/cryptozavr/infrastructure/supabase/gateway.py tests/integration/conftest.py
```

Expected: Success.

- [ ] **Step 4: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add src/cryptozavr/infrastructure/supabase/gateway.py tests/integration/conftest.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(supabase): add SupabaseGateway Facade + integration fixtures

Gateway methods: resolve_symbol_id, upsert_ticker/load_ticker,
upsert_ohlcv/load_ohlcv, insert_query_log, subscribe_tickers (stub),
upload_artifact (stub), match_regimes (stub), close.

conftest: session-scoped pool + per-test gateway; auto-skip when
Supabase is not reachable so the M1 test suite still runs without Docker.
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 15: Integration test — migrations apply cleanly

**Files:**
- Create: `tests/integration/test_migrations_apply.py`

- [ ] **Step 1: Write integration test**

Write to `/Users/laptop/dev/cryptozavr/tests/integration/test_migrations_apply.py`:
```python
"""Smoke: all cryptozavr tables + cron jobs exist after `supabase db push`."""

from __future__ import annotations

import pytest
import pytest_asyncio

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "assets",
    "ohlcv_candles",
    "orderbook_snapshots",
    "provider_events",
    "query_log",
    "symbol_aliases",
    "symbols",
    "tickers_live",
    "trades",
    "venues",
}

EXPECTED_CRON_JOBS = {"prune-stale-tickers", "prune-query-log"}

@pytest_asyncio.fixture
async def db_conn(supabase_pool):  # type: ignore[no-untyped-def]
    async with supabase_pool.acquire() as conn:
        yield conn

async def test_all_tables_exist(db_conn) -> None:  # type: ignore[no-untyped-def]
    rows = await db_conn.fetch(
        "select table_name from information_schema.tables "
        "where table_schema = 'cryptozavr' order by table_name"
    )
    actual = {r["table_name"] for r in rows}
    assert EXPECTED_TABLES.issubset(actual), (
        f"missing tables: {EXPECTED_TABLES - actual}"
    )

async def test_rls_enabled_on_all_tables(db_conn) -> None:  # type: ignore[no-untyped-def]
    rows = await db_conn.fetch(
        "select c.relname from pg_class c "
        "join pg_namespace n on n.oid = c.relnamespace "
        "where n.nspname = 'cryptozavr' and c.relkind = 'r' and c.relrowsecurity"
    )
    actual = {r["relname"] for r in rows}
    assert EXPECTED_TABLES.issubset(actual), (
        f"tables without RLS: {EXPECTED_TABLES - actual}"
    )

async def test_cron_jobs_registered(db_conn) -> None:  # type: ignore[no-untyped-def]
    rows = await db_conn.fetch("select jobname from cron.job order by jobname")
    actual = {r["jobname"] for r in rows}
    assert EXPECTED_CRON_JOBS.issubset(actual), (
        f"missing cron jobs: {EXPECTED_CRON_JOBS - actual}"
    )

async def test_seed_venues_present(db_conn) -> None:  # type: ignore[no-untyped-def]
    rows = await db_conn.fetch(
        "select id from cryptozavr.venues order by id"
    )
    ids = {r["id"] for r in rows}
    assert "kucoin" in ids
    assert "coingecko" in ids
```

- [ ] **Step 2: Run (if Supabase running — otherwise test skips)**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/integration/test_migrations_apply.py -v -m integration
```

Expected (if Docker up):
- 4 tests pass.
Expected (if Docker down):
- Session-scoped `supabase_pool` fixture fails reachability check → all 4 skipped with reason.

- [ ] **Step 3: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add tests/integration/test_migrations_apply.py
```

Write to `/tmp/commit-msg.txt`:
```text
test(supabase): verify migrations + cron + seed applied

4 integration checks: all tables present, RLS enabled on all, two cron
jobs registered, seed venues (kucoin/coingecko) inserted. Skips cleanly
when Supabase isn't running locally (docker not available).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 16: Integration test — OHLCV roundtrip + ticker upsert + query_log insert

**Files:**
- Create: `tests/integration/test_ohlcv_roundtrip.py`
- Create: `tests/integration/test_tickers_upsert.py`
- Create: `tests/integration/test_query_log_insert.py`

- [ ] **Step 1: Write OHLCV roundtrip test**

Write to `/Users/laptop/dev/cryptozavr/tests/integration/test_ohlcv_roundtrip.py`:
```python
"""OHLCV upsert → load roundtrip via SupabaseGateway."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.domain.market_data import OHLCVCandle, OHLCVSeries
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe, TimeRange
from cryptozavr.domain.venues import MarketType, VenueId

pytestmark = pytest.mark.integration

async def _ensure_btc_symbol_registered(
    supabase_pool, registry: SymbolRegistry,  # type: ignore[no-untyped-def]
) -> Symbol:
    async with supabase_pool.acquire() as conn:
        await conn.execute(
            """
            insert into cryptozavr.symbols
              (venue_id, base, quote, market_type, native_symbol, active)
            values ('kucoin', 'BTC', 'USDT', 'spot', 'BTC-USDT', true)
            on conflict (venue_id, base, quote, market_type) do nothing
            """
        )
    return registry.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

def _fresh_quality() -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ohlcv"),
        fetched_at=Instant.now(),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )

def _make_series(symbol: Symbol, count: int) -> OHLCVSeries:
    tf = Timeframe.H1
    step_ms = tf.to_milliseconds()
    base_ms = 1_745_200_800_000  # fixed anchor — avoids flaky now()
    candles = tuple(
        OHLCVCandle(
            opened_at=Instant.from_ms(base_ms + i * step_ms),
            open=Decimal("100") + Decimal(i),
            high=Decimal("110") + Decimal(i),
            low=Decimal("90") + Decimal(i),
            close=Decimal("105") + Decimal(i),
            volume=Decimal("1000"),
            closed=True,
        )
        for i in range(count)
    )
    return OHLCVSeries(
        symbol=symbol, timeframe=tf, candles=candles,
        range=TimeRange(
            start=candles[0].opened_at,
            end=Instant.from_ms(candles[-1].opened_at.to_ms() + step_ms),
        ),
        quality=_fresh_quality(),
    )

async def test_ohlcv_upsert_then_load_roundtrip(
    supabase_gateway, supabase_pool, clean_market_data,  # type: ignore[no-untyped-def]
) -> None:
    registry = supabase_gateway._registry  # noqa: SLF001
    symbol = await _ensure_btc_symbol_registered(supabase_pool, registry)

    series = _make_series(symbol, count=5)

    written = await supabase_gateway.upsert_ohlcv(series)
    assert written == 5

    loaded = await supabase_gateway.load_ohlcv(symbol, Timeframe.H1, limit=100)
    assert loaded is not None
    assert len(loaded.candles) == 5
    assert loaded.candles[0].open == Decimal("100")
    assert loaded.candles[-1].close == Decimal("109")

async def test_ohlcv_upsert_is_idempotent(
    supabase_gateway, supabase_pool, clean_market_data,  # type: ignore[no-untyped-def]
) -> None:
    registry = supabase_gateway._registry  # noqa: SLF001
    symbol = await _ensure_btc_symbol_registered(supabase_pool, registry)

    series = _make_series(symbol, count=3)
    await supabase_gateway.upsert_ohlcv(series)
    await supabase_gateway.upsert_ohlcv(series)  # second time — should overwrite

    loaded = await supabase_gateway.load_ohlcv(symbol, Timeframe.H1, limit=100)
    assert loaded is not None
    assert len(loaded.candles) == 3  # not duplicated

async def test_load_ohlcv_empty_returns_none(
    supabase_gateway, supabase_pool, clean_market_data,  # type: ignore[no-untyped-def]
) -> None:
    registry = supabase_gateway._registry  # noqa: SLF001
    symbol = await _ensure_btc_symbol_registered(supabase_pool, registry)

    loaded = await supabase_gateway.load_ohlcv(symbol, Timeframe.H1, limit=100)
    assert loaded is None
```

- [ ] **Step 2: Write tickers upsert test**

Write to `/Users/laptop/dev/cryptozavr/tests/integration/test_tickers_upsert.py`:
```python
"""Ticker upsert → load roundtrip via SupabaseGateway."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol, SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Percentage
from cryptozavr.domain.venues import MarketType, VenueId

pytestmark = pytest.mark.integration

async def _ensure_btc_symbol_registered(
    supabase_pool, registry: SymbolRegistry,  # type: ignore[no-untyped-def]
) -> Symbol:
    async with supabase_pool.acquire() as conn:
        await conn.execute(
            """
            insert into cryptozavr.symbols
              (venue_id, base, quote, market_type, native_symbol, active)
            values ('kucoin', 'BTC', 'USDT', 'spot', 'BTC-USDT', true)
            on conflict (venue_id, base, quote, market_type) do nothing
            """
        )
    return registry.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

def _quality() -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id="kucoin", endpoint="fetch_ticker"),
        fetched_at=Instant.now(),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )

async def test_ticker_upsert_then_load(
    supabase_gateway, supabase_pool, clean_market_data,  # type: ignore[no-untyped-def]
) -> None:
    registry = supabase_gateway._registry  # noqa: SLF001
    symbol = await _ensure_btc_symbol_registered(supabase_pool, registry)

    observed = Instant.from_ms(1_745_200_800_000)
    ticker = Ticker(
        symbol=symbol,
        last=Decimal("65000.5"),
        bid=Decimal("64999.5"),
        ask=Decimal("65001.5"),
        volume_24h=Decimal("1234"),
        change_24h_pct=Percentage(value=Decimal("2.5")),
        high_24h=Decimal("66000"),
        low_24h=Decimal("64000"),
        observed_at=observed,
        quality=_quality(),
    )

    await supabase_gateway.upsert_ticker(ticker)

    loaded = await supabase_gateway.load_ticker(symbol)
    assert loaded is not None
    assert loaded.last == Decimal("65000.5")
    assert loaded.bid == Decimal("64999.5")
    assert loaded.ask == Decimal("65001.5")
    assert loaded.change_24h_pct is not None
    assert loaded.change_24h_pct.value == Decimal("2.5")

async def test_ticker_upsert_overwrites(
    supabase_gateway, supabase_pool, clean_market_data,  # type: ignore[no-untyped-def]
) -> None:
    registry = supabase_gateway._registry  # noqa: SLF001
    symbol = await _ensure_btc_symbol_registered(supabase_pool, registry)
    observed = Instant.from_ms(1_745_200_800_000)

    first = Ticker(
        symbol=symbol, last=Decimal("60000"),
        observed_at=observed, quality=_quality(),
    )
    second = Ticker(
        symbol=symbol, last=Decimal("65000"),
        observed_at=observed, quality=_quality(),
    )
    await supabase_gateway.upsert_ticker(first)
    await supabase_gateway.upsert_ticker(second)

    loaded = await supabase_gateway.load_ticker(symbol)
    assert loaded is not None
    assert loaded.last == Decimal("65000")
```

- [ ] **Step 3: Write query_log insert test**

Write to `/Users/laptop/dev/cryptozavr/tests/integration/test_query_log_insert.py`:
```python
"""Insert-only audit trail: query_log."""

from __future__ import annotations

import pytest

from cryptozavr.domain.symbols import SymbolRegistry
from cryptozavr.domain.value_objects import Instant, Timeframe
from cryptozavr.domain.venues import MarketType, VenueId

pytestmark = pytest.mark.integration

async def _ensure_btc_symbol_registered(
    supabase_pool, registry: SymbolRegistry,  # type: ignore[no-untyped-def]
):
    async with supabase_pool.acquire() as conn:
        await conn.execute(
            """
            insert into cryptozavr.symbols
              (venue_id, base, quote, market_type, native_symbol, active)
            values ('kucoin', 'BTC', 'USDT', 'spot', 'BTC-USDT', true)
            on conflict (venue_id, base, quote, market_type) do nothing
            """
        )
    return registry.get(
        VenueId.KUCOIN, "BTC", "USDT",
        market_type=MarketType.SPOT, native_symbol="BTC-USDT",
    )

async def test_insert_query_log_returns_uuid(
    supabase_gateway, supabase_pool,  # type: ignore[no-untyped-def]
) -> None:
    registry = supabase_gateway._registry  # noqa: SLF001
    symbol = await _ensure_btc_symbol_registered(supabase_pool, registry)

    query_id = await supabase_gateway.insert_query_log(
        kind="ohlcv",
        symbol=symbol,
        timeframe=Timeframe.H1,
        range_start=Instant.from_ms(1_745_200_800_000),
        range_end=Instant.from_ms(1_745_287_200_000),
        limit_n=500,
        force_refresh=False,
        reason_codes=("venue:healthy", "cache:miss"),
        quality=None,
        issued_by="mcp_tool:get_ohlcv",
        client_id="session-abc",
    )
    assert query_id is not None

    # Verify it lands in the table.
    async with supabase_pool.acquire() as conn:
        row = await conn.fetchrow(
            "select kind, issued_by, client_id, reason_codes "
            "  from cryptozavr.query_log where id = $1",
            query_id,
        )
    assert row is not None
    assert row["kind"] == "ohlcv"
    assert row["issued_by"] == "mcp_tool:get_ohlcv"
    assert row["client_id"] == "session-abc"
    assert list(row["reason_codes"]) == ["venue:healthy", "cache:miss"]

async def test_insert_query_log_without_symbol(
    supabase_gateway,  # type: ignore[no-untyped-def]
) -> None:
    query_id = await supabase_gateway.insert_query_log(
        kind="discovery",
        symbol=None,
        timeframe=None,
        range_start=None,
        range_end=None,
        limit_n=None,
        force_refresh=False,
        reason_codes=(),
        quality=None,
        issued_by="mcp_tool:list_trending",
        client_id=None,
    )
    assert query_id is not None
```

- [ ] **Step 4: Run tests (skipped if no Supabase)**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/integration/ -v -m integration
```

Expected (Supabase running): 9 passed (4 migrations + 3 OHLCV + 2 tickers + 2 query_log = but test counts may differ slightly). Expected (no Supabase): all skipped at fixture level.

- [ ] **Step 5: Mypy on new test files**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy tests/integration
```

Expected: Success (tests override disallow_untyped_defs=false already).

- [ ] **Step 6: Commit**

```bash
cd /Users/laptop/dev/cryptozavr
git add tests/integration/test_ohlcv_roundtrip.py tests/integration/test_tickers_upsert.py tests/integration/test_query_log_insert.py
```

Write to `/tmp/commit-msg.txt`:
```sql
test(supabase): add roundtrip integration tests

OHLCV: upsert N candles, load same N, verify values + idempotency on
repeat upsert. Ticker: upsert + load single-symbol; second upsert
overwrites last. Query log: insert_query_log returns UUID; subsequent
row SELECT confirms kind/issued_by/client_id/reason_codes stored.
Requires local Supabase (auto-skip otherwise).
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 17: Full local verification

**Files:** (none — verification only)

- [ ] **Step 1: Lint + format**

```bash
cd /Users/laptop/dev/cryptozavr
uv run ruff check .
uv run ruff format --check .
```

Expected: zero errors.

- [ ] **Step 2: Typecheck**

```bash
cd /Users/laptop/dev/cryptozavr
uv run mypy src
```

Expected: `Success`.

- [ ] **Step 3: Unit tests + coverage**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/unit -v --cov=cryptozavr --cov-report=term-missing
```

Expected: all unit tests pass (114 domain from M2.1 + new mappers/pool tests). Coverage on `src/cryptozavr/infrastructure/supabase/mappers.py` ≥ 95%, `pg_pool.py` config ≥ 90% (create_pool path is integration-covered).

- [ ] **Step 4: Integration tests (skipped if no Supabase)**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pytest tests/integration -v -m integration
```

Expected (Supabase up): all pass. Expected (no Supabase): all skipped with clear reason.

- [ ] **Step 5: Pre-commit**

```bash
cd /Users/laptop/dev/cryptozavr
uv run pre-commit run --all-files
```

Expected: all hooks pass.

- [ ] **Step 6: Verify package importability**

```bash
cd /Users/laptop/dev/cryptozavr
uv run python -c "
from cryptozavr.infrastructure.supabase.gateway import SupabaseGateway
from cryptozavr.infrastructure.supabase.mappers import (
    row_to_symbol, row_to_ticker, row_to_ohlcv_candle, row_to_ohlcv_series,
)
from cryptozavr.infrastructure.supabase.pg_pool import PgPoolConfig, create_pool
from cryptozavr.infrastructure.supabase.realtime import RealtimeSubscriber
from cryptozavr.infrastructure.supabase.storage import StorageClient
from cryptozavr.infrastructure.supabase.rpc import RpcClient
print('all supabase layer imports OK')
"
```

Expected: `all supabase layer imports OK`.

**No commit** — verification only.

---

### Task 18: Tag v0.0.3 + update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Verify git clean**

```bash
cd /Users/laptop/dev/cryptozavr
git status
```

Expected: clean.

- [ ] **Step 2: Update CHANGELOG**

Use Edit tool. Find:

```markdown
## [Unreleased]

## [0.0.2] - 2026-04-21
```

Replace with:

```markdown
## [Unreleased]

## [0.0.3] - 2026-04-21

### Added — M2.2 Supabase schema + Gateway
- SQL migrations (6 files): extensions (vector/pg_cron/pg_net/pg_trgm), reference (venues/assets/symbols/symbol_aliases + 4 enums), market_data (tickers_live/ohlcv_candles/orderbook_snapshots/trades with indexes), audit (query_log with halfvec(1536) reserved column + provider_events), RLS policies, pg_cron jobs (prune-stale-tickers, prune-query-log).
- Seed: baseline kucoin + coingecko venues with capabilities.
- `SupabaseGateway` Facade: resolve_symbol_id, upsert_ticker/load_ticker, upsert_ohlcv/load_ohlcv, insert_query_log, realtime/storage/rpc stubs, close.
- `PgPoolConfig` + `create_pool` for asyncpg connection pool.
- Row mappers (pure functions): row_to_symbol, row_to_ticker, row_to_ohlcv_candle, row_to_ohlcv_series.
- Stubs for phase-later integrations: RealtimeSubscriber, StorageClient, RpcClient.
- Integration tests (auto-skip when Supabase not running): migrations apply, OHLCV upsert→load roundtrip, ticker upsert→load, query_log insert.
- New dev deps: asyncpg, supabase, realtime (M2 optional group + dev group).

## [0.0.2] - 2026-04-21
```

- [ ] **Step 3: Commit CHANGELOG**

```bash
cd /Users/laptop/dev/cryptozavr
git add CHANGELOG.md docs/superpowers/plans/2026-04-21-cryptozavr-m2.2-supabase-gateway.md
```

Write to `/tmp/commit-msg.txt`:
```bash
docs: finalize CHANGELOG for v0.0.3 (M2.2 Supabase + Gateway)
```

```bash
cd /Users/laptop/dev/cryptozavr
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

- [ ] **Step 4: Create tag**

```bash
cd /Users/laptop/dev/cryptozavr
git tag -a v0.0.3 -m "M2.2 Supabase schema + Gateway complete

6 SQL migrations + seed + SupabaseGateway Facade + mappers + stubs.
Integration tests skip-safe without local Supabase.
Ready for M2.3 (Providers layer: CCXT/CoinGecko adapters + chain + state)."
```

- [ ] **Step 5: Summary**

```bash
cd /Users/laptop/dev/cryptozavr
echo "=== M2.2 complete ==="
git log --oneline v0.0.2..HEAD
echo ""
git tag -l
```

**Do not push.** Remote still deferred.

---

## Acceptance Criteria for M2.2

1. ✅ All 18 tasks executed (or Task 9 explicitly deferred due to Docker).
2. ✅ All 6 migrations syntactically valid (SQL parses; verified by `supabase db push` if Docker up, otherwise deferred).
3. ✅ Unit tests on mappers.py ≥ 95% coverage.
4. ✅ Mypy clean across new Supabase layer.
5. ✅ Integration tests either pass (with Supabase) or skip cleanly (without).
6. ✅ Ruff clean.
7. ✅ Package imports: every new module importable without errors.
8. ✅ Git tag `v0.0.3` at HEAD.

---

## Handoff to M2.3

After M2.2 complete:

1. Invoke `writing-plans` with context: "M2.2 Supabase complete. Write plan for M2.3 Providers layer (BaseProvider Template Method, CCXTProvider for KuCoin, CoinGeckoProvider, adapters, 4 decorators, Chain of Responsibility handlers, VenueState State pattern, ProviderFactory)."
2. M2.3 will populate `src/cryptozavr/infrastructure/providers/` with ~25 tasks.

---

## Notes

- **Integration tests gracefully skip** when Supabase is unreachable. This means the full pytest suite runs on CI/dev workstation without requiring Docker during M2.2 development — a deliberate design choice so the unit tests (mappers, pg_pool config) stay the source of truth for correctness, while integration tests are a "nice to have" signal.
- **Domain import discipline preserved.** Mappers import Domain entities; migrations are pure SQL with zero Python coupling; Gateway depends on Domain Protocols and concrete entity types only.
- **`Gateway._registry` accessed via name-mangled underscore in tests** with a `# noqa: SLF001` — acceptable for integration tests; production callers inject a fresh SymbolRegistry via DI.
- **Symbol registration pre-requisite.** M2.2 Gateway assumes symbols already live in `cryptozavr.symbols`. Integration tests insert directly. M2.3 will add the production path: `CCXTProvider.load_markets` → bulk upsert to `cryptozavr.symbols` via a dedicated method on Gateway.
