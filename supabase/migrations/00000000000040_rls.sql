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
