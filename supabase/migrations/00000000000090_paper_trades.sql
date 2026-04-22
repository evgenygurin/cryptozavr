-- supabase/migrations/00000000000090_paper_trades.sql
-- Paper trading ledger: one row per trade, insert-then-update lifecycle.
-- Terminal events and manual closes go through atomic
-- UPDATE ... WHERE status = 'running' to be idempotent under races.

create table cryptozavr.paper_trades (
  id              uuid primary key default gen_random_uuid(),
  side            text not null check (side in ('long', 'short')),
  venue           text not null,
  symbol_native   text not null,
  entry           numeric(20, 8) not null check (entry > 0),
  stop            numeric(20, 8) not null check (stop > 0),
  take            numeric(20, 8) not null check (take > 0),
  size_quote      numeric(20, 8) not null check (size_quote > 0),
  opened_at_ms    bigint not null,
  max_duration_sec integer not null,
  status          text not null check (status in ('running', 'closed', 'abandoned')),
  exit_price      numeric(20, 8),
  closed_at_ms    bigint,
  pnl_quote       numeric(20, 8),
  reason          text,
  watch_id        text,
  note            text
);

create index paper_trades_running
  on cryptozavr.paper_trades (status)
  where status = 'running';

create index paper_trades_opened_desc
  on cryptozavr.paper_trades (opened_at_ms desc);

create index paper_trades_watch_id
  on cryptozavr.paper_trades (watch_id)
  where watch_id is not null;

alter table cryptozavr.paper_trades enable row level security;

create policy service_role_all on cryptozavr.paper_trades
  for all to service_role using (true) with check (true);

create or replace view cryptozavr.paper_stats as
select
  count(*) filter (where status = 'closed')                    as trades_count,
  count(*) filter (where status = 'closed' and pnl_quote > 0)  as wins,
  count(*) filter (where status = 'closed' and pnl_quote <= 0) as losses,
  count(*) filter (where status = 'running')                   as open_count,
  coalesce(sum(pnl_quote) filter (where status = 'closed'), 0) as net_pnl_quote,
  coalesce(avg(pnl_quote) filter (where status = 'closed' and pnl_quote > 0), 0)
    as avg_win_quote,
  coalesce(avg(pnl_quote) filter (where status = 'closed' and pnl_quote <= 0), 0)
    as avg_loss_quote
from cryptozavr.paper_trades;

-- Broadcast lifecycle to Supabase Realtime.
alter publication supabase_realtime add table cryptozavr.paper_trades;
