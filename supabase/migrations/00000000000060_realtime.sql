-- Add market_data tables to the Supabase Realtime publication
-- so postgres_changes subscriptions receive INSERT/UPDATE/DELETE events.
--
-- tickers_live is the primary target (phase 1.5 per MVP spec § 11).
-- OHLCV and orderbook are not included: they're batch-written and a
-- realtime feed of every row would overwhelm clients.

alter publication supabase_realtime add table cryptozavr.tickers_live;
