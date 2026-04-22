-- Phase 2 Sub-project E — declarative strategy persistence.
-- pgvector + cryptozavr schema already provided by 00000000000000_extensions.sql.
-- gen_random_uuid() is available via pgcrypto (bundled with Postgres 13+ and
-- used elsewhere in this project — see 00000000000030_audit.sql query_log).

create table cryptozavr.strategy_specs (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  version       integer not null default 1,
  venue_id      text not null,       -- denormalized from spec_json for quick filters
  symbol_native text not null,       -- e.g. "BTC-USDT" — denormalized
  timeframe     cryptozavr.timeframe not null,
  spec_json     jsonb not null,
  content_hash  text not null unique, -- BLAKE2b of canonical spec_json
  embedding     extensions.vector(384),  -- nullable; placeholder fills deterministically
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index strategy_specs_created_desc
  on cryptozavr.strategy_specs (created_at desc);

create index strategy_specs_name
  on cryptozavr.strategy_specs (name);

-- IVFFLAT index on embedding for approximate similarity search.
-- Small default lists=100; tuneable once real scale arrives.
create index strategy_specs_embedding_ivfflat
  on cryptozavr.strategy_specs
  using ivfflat (embedding extensions.vector_l2_ops)
  with (lists = 100);

-- RLS — service_role only (same pattern as other cryptozavr tables).
alter table cryptozavr.strategy_specs enable row level security;

create policy service_role_all on cryptozavr.strategy_specs
  for all to service_role using (true) with check (true);

-- Similarity RPC: top-K by L2 distance.
-- Returns (id, name, similarity) where similarity = 1 - L2_distance.
create or replace function cryptozavr.match_similar_strategies(
  query_embedding extensions.vector(384),
  similarity_threshold float,
  max_results integer
)
returns table (
  id uuid,
  name text,
  similarity float
)
language sql
stable
as $$
  select s.id, s.name, 1 - (s.embedding <-> query_embedding) as similarity
    from cryptozavr.strategy_specs s
   where s.embedding is not null
     and 1 - (s.embedding <-> query_embedding) >= similarity_threshold
   order by s.embedding <-> query_embedding asc
   limit max_results;
$$;

grant execute on function cryptozavr.match_similar_strategies to service_role;

-- updated_at auto-touch trigger.
create or replace function cryptozavr.touch_strategy_specs_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger strategy_specs_touch_updated_at
before update on cryptozavr.strategy_specs
for each row execute function cryptozavr.touch_strategy_specs_updated_at();
