-- Declarative risk policies — insert-only history, one active row.
-- jsonb policy + BLAKE2b content_hash uniqueness → idempotent save.
-- Partial unique index on is_active = true enforces the "exactly one active
-- row at a time" invariant at the DB layer; the repository transaction only
-- has to deactivate-then-activate without extra locking.

create table cryptozavr.risk_policies (
  id           uuid primary key default gen_random_uuid(),
  policy_json  jsonb not null,
  content_hash text not null unique,         -- BLAKE2b of canonical policy_json
  is_active    boolean not null default false,
  created_at   timestamptz not null default now(),
  activated_at timestamptz
);

-- Exactly one active row at any moment.
create unique index risk_policies_one_active
  on cryptozavr.risk_policies (is_active)
  where is_active = true;

create index risk_policies_created_desc
  on cryptozavr.risk_policies (created_at desc);

-- RLS — service_role only (same pattern as other cryptozavr tables).
alter table cryptozavr.risk_policies enable row level security;

create policy service_role_all on cryptozavr.risk_policies
  for all to service_role using (true) with check (true);

-- Trigger: set activated_at := now() on the 0→1 transition of is_active.
-- Deactivation (1→0) leaves activated_at untouched so history preserves the
-- original activation timestamp.
create or replace function cryptozavr.touch_risk_policies_activated_at()
returns trigger language plpgsql as $$
begin
  if new.is_active = true and (old.is_active is distinct from true) then
    new.activated_at := now();
  end if;
  return new;
end;
$$;

create trigger risk_policies_touch_activated_at
before update on cryptozavr.risk_policies
for each row execute function cryptozavr.touch_risk_policies_activated_at();
