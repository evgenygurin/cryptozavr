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
