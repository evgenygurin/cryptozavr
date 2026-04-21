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
