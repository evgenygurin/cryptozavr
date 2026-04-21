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
  query_embedding extensions.halfvec(1536)
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
  kind         text not null,
  from_state   cryptozavr.venue_state_kind,
  to_state     cryptozavr.venue_state_kind,
  details      jsonb not null default '{}',
  occurred_at  timestamptz not null default now()
);

create index provider_events_by_venue_occurred_desc
  on cryptozavr.provider_events (venue_id, occurred_at desc);
