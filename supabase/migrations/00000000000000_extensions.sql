-- Enable required Postgres extensions and create the cryptozavr schema.
-- Idempotent: all statements use IF NOT EXISTS where applicable.

create extension if not exists vector with schema extensions;
create extension if not exists pg_cron with schema extensions;
create extension if not exists pg_net with schema extensions;
create extension if not exists pg_trgm with schema extensions;

create schema if not exists cryptozavr;

grant usage on schema cryptozavr to service_role;
grant usage on schema cryptozavr to authenticated;
grant usage on schema cryptozavr to anon;
