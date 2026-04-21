# Installing cryptozavr in OpenCode

See `.opencode/README.md` for the canonical OpenCode install steps.

Quick summary:

    gh repo clone evgenygurin/cryptozavr ~/opencode/plugins/cryptozavr
    cd ~/opencode/plugins/cryptozavr
    uv sync --all-extras
    cp .env.example .env   # fill SUPABASE_* values

Enable the plugin in OpenCode Settings → Plugins → Add local plugin.
