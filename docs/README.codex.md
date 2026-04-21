# Installing cryptozavr in OpenAI Codex

See `.codex/README.md` for the canonical Codex install steps.

Quick summary:

    gh repo clone evgenygurin/cryptozavr ~/codex-plugins/cryptozavr
    cd ~/codex-plugins/cryptozavr
    uv sync --all-extras
    cp .env.example .env   # fill SUPABASE_* values
    codex plugins add ~/codex-plugins/cryptozavr

Restart codex. Run `/cryptozavr:health` to verify.
