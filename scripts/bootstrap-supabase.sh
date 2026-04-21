#!/usr/bin/env bash
# Bootstrap local Supabase stack for cryptozavr development.
# Usage: ./scripts/bootstrap-supabase.sh

set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Starting Supabase stack..."
supabase start

echo ""
echo "==> Applying migrations (if any)..."
supabase db push || echo "    (no migrations yet — expected in M1)"

echo ""
echo "==> Ready. Keys for .env:"
supabase status
