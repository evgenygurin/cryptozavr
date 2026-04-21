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
