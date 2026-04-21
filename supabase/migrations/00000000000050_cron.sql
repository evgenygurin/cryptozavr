-- pg_cron jobs for background maintenance.
-- Symbol-refresh job deferred: needs Python worker (CCXT calls), ships in M2.3
-- via maintenance_queue marker table.

select cron.schedule(
  'prune-stale-tickers',
  '*/15 * * * *',
  $$
    delete from cryptozavr.tickers_live
     where observed_at < now() - interval '5 minutes'
  $$
);

select cron.schedule(
  'prune-query-log',
  '0 3 * * *',
  $$
    delete from cryptozavr.query_log
     where issued_at < now() - interval '30 days'
  $$
);
