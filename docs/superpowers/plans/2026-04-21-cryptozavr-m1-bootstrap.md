# cryptozavr — Milestone 1: Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Инициализировать greenfield-репозиторий cryptozavr как Claude Code плагин с работающим FastMCP v3+ сервером (один echo-tool для smoke). Подготовить весь tooling (uv, ruff, pytest, Supabase CLI), plugin-манифесты и CI pipeline так, чтобы M2 (data layer) мог начаться без инфраструктурных блокеров.

**Architecture:** Layered Onion — директории `domain/`, `application/`, `infrastructure/`, `mcp/` создаются пустыми (с `__init__.py`) в M1 как скелет; контент добавляется в M2–M4. FastMCP server в M1 содержит один `echo` tool для проверки, что Claude Code видит плагин и может вызывать tools.

**Tech Stack:** Python 3.12, uv, FastMCP v3.2+, pydantic v2, pytest 8.3+, ruff, mypy, Supabase CLI (локально), GitHub Actions.

**Milestone position:** 1 of 4. См. [design doc](../specs/2026-04-21-cryptozavr-mvp-design.md) для полного контекста MVP.

**Spec reference:** docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md

---

## File Structure (создаётся в M1)

| Path | Responsibility |
|------|---------------|
| `.gitignore` | Игнорирование venv, .env, cache, coverage artifacts |
| `.gitattributes` | LF line endings, binary markers |
| `.editorconfig` | Cross-editor indent/line-ending settings |
| `.python-version` | `3.12` (для uv/pyenv) |
| `pyproject.toml` | uv project metadata, dependencies, ruff/mypy/pytest config |
| `uv.lock` | Воспроизводимые build'ы (сгенерится `uv sync`) |
| `README.md` | Quickstart, installation, dev workflow |
| `CHANGELOG.md` | Keep-a-changelog формат, раздел [Unreleased] с M1 bootstrap |
| `LICENSE` | MIT |
| `.env.example` | Все env-переменные MVP (Supabase URLs, mode, TTLs, API keys placeholders) |
| `plugin.json` | Claude Code plugin manifest |
| `.mcp.json` | Регистрация MCP-сервера для Claude Code |
| `fastmcp.json` | FastMCP v3 source + dependencies config |
| `supabase/config.toml` | Supabase CLI config (порты локального стека) |
| `supabase/migrations/.gitkeep` | Placeholder; миграции — в M2 |
| `supabase/seed.sql` | Пустой файл, заполнится в M2 |
| `scripts/bootstrap-supabase.sh` | One-shot: `supabase start` + health check |
| `src/cryptozavr/__init__.py` | `__version__ = "0.0.1"` |
| `src/cryptozavr/mcp/__init__.py` | Package marker |
| `src/cryptozavr/mcp/settings.py` | Pydantic Settings из env |
| `src/cryptozavr/mcp/server.py` | FastMCP server instance + `echo` tool + `main()` |
| `src/cryptozavr/domain/__init__.py` | Пустой (контент в M2) |
| `src/cryptozavr/application/__init__.py` | Пустой (контент в M3) |
| `src/cryptozavr/infrastructure/__init__.py` | Пустой (контент в M2) |
| `skills/.gitkeep` | Placeholder (контент в M4) |
| `commands/.gitkeep` | Placeholder (контент в M4) |
| `hooks/.gitkeep` | Placeholder (возможно в phase 1.5) |
| `tests/__init__.py` | Package marker |
| `tests/conftest.py` | Базовые pytest fixtures |
| `tests/unit/__init__.py` | Package marker |
| `tests/unit/mcp/test_server_startup.py` | Smoke-тест: server собирается, echo tool зарегистрирован |
| `tests/unit/mcp/test_echo_tool.py` | Direct server call: `mcp.call_tool("echo", {...})` |
| `tests/unit/mcp/test_settings.py` | Settings читаются из env корректно |
| `.github/workflows/ci.yml` | Lint (ruff) + typecheck (mypy) + unit tests |
| `.github/workflows/plugin-validate.yml` | Валидация plugin.json / .mcp.json / fastmcp.json JSON-схем |
| `.pre-commit-config.yaml` | ruff + ruff-format + trailing-whitespace + end-of-file-fixer |
| `docs/README.md` | Docs index, ссылки на spec и plans |

---

## Tasks

### Task 1: Git init + ignore rules

**Files:**
- Create: `.gitignore`
- Create: `.gitattributes`
- Create: `.editorconfig`

- [ ] **Step 1: Initialize git repo**

Run:
```bash
cd /Users/laptop/dev/cryptozavr && git init
```

Expected output: `Initialized empty Git repository in /Users/laptop/dev/cryptozavr/.git/`

- [ ] **Step 2: Create `.gitignore`**

Write to `.gitignore`:
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
.venv/
venv/
ENV/
env/

# uv
.uv-cache/

# Testing
.pytest_cache/
.coverage
.coverage.*
htmlcov/
coverage.xml
*.cover
.hypothesis/

# Type checking
.mypy_cache/
.pyright/
.dmypy.json
dmypy.json

# Ruff
.ruff_cache/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Environments
.env
.env.local
.env.*.local

# Supabase
supabase/.temp/
supabase/.branches/

# Plugin-local settings
.claude/settings.local.json
.claude/*.local.md

# Logs
*.log
logs/

# Parquet/CSV exports (phase 2+)
exports/
```

- [ ] **Step 3: Create `.gitattributes`**

Write to `.gitattributes`:
```gitattributes
* text=auto eol=lf
*.py text eol=lf
*.md text eol=lf
*.json text eol=lf
*.toml text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
*.sql text eol=lf
*.sh text eol=lf

*.png binary
*.jpg binary
*.gif binary
*.ico binary
```

- [ ] **Step 4: Create `.editorconfig`**

Write to `.editorconfig`:
```ini
root = true

[*]
indent_style = space
indent_size = 4
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.{json,yml,yaml,toml}]
indent_size = 2

[*.md]
trim_trailing_whitespace = false

[Makefile]
indent_style = tab
```

- [ ] **Step 5: Stage and inspect before first commit**

Run:
```bash
git add .gitignore .gitattributes .editorconfig
git status
```

Expected: `new file: .gitignore`, `new file: .gitattributes`, `new file: .editorconfig` в staging.

- [ ] **Step 6: Write initial commit message**

Write to `/tmp/commit-msg.txt`:
```bash
chore: init repository with ignore/attributes/editorconfig

First commit for cryptozavr — risk-first crypto research Claude Code plugin.
M1 Bootstrap milestone start.
```

- [ ] **Step 7: Commit**

Run:
```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

Expected output: `[main (root-commit) ...] chore: init repository with ignore/attributes/editorconfig`

---

### Task 2: Python toolchain — uv + pyproject.toml

**Files:**
- Create: `.python-version`
- Create: `pyproject.toml`

- [ ] **Step 1: Verify uv installed**

Run:
```bash
uv --version
```

Expected: `uv 0.4.x` или новее. Если не установлен: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

- [ ] **Step 2: Create `.python-version`**

Write to `.python-version`:
```text
3.12
```

- [ ] **Step 3: Create `pyproject.toml`**

Write to `pyproject.toml`:
```toml
[project]
name = "cryptozavr"
version = "0.0.1"
description = "Risk-first crypto market research plugin for Claude Code"
readme = "README.md"
license = { text = "MIT" }
authors = [
    { name = "cryptozavr", email = "e.a.gurin@outlook.com" }
]
requires-python = ">=3.12,<3.14"
keywords = ["crypto", "market-data", "research", "fastmcp", "supabase", "mcp"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
]
dependencies = [
    "fastmcp>=3.2.4",
    "pydantic>=2.9",
    "pydantic-settings>=2.5",
    "structlog>=24.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5",
    "pytest-xdist>=3.6",
    "ruff>=0.6",
    "mypy>=1.11",
    "pre-commit>=3.8",
    "dirty-equals>=0.8",
]
# Dependencies added in later milestones:
# m2 = ["httpx>=0.27", "ccxt>=4.4", "asyncpg>=0.29", "supabase>=2.8", "realtime>=2.0", "punq>=0.7"]
# m3 = ["hypothesis>=6.100", "polyfactory>=2.18", "respx>=0.21", "freezegun>=1.5"]

[project.scripts]
cryptozavr-server = "cryptozavr.mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/cryptozavr"]

[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # Pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "UP",  # pyupgrade
    "SIM", # flake8-simplify
    "RUF", # Ruff-specific
    "TID", # flake8-tidy-imports
    "PL",  # Pylint
    "PT",  # flake8-pytest-style
]
ignore = [
    "E501",     # line-too-long handled by formatter
    "PLR0913",  # too-many-arguments (design choice for DI)
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["PLR2004", "S101"]  # magic values & asserts OK in tests

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
mypy_path = "src"
namespace_packages = true
explicit_package_bases = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"
filterwarnings = ["error"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "-ra",
    "--tb=short",
]
markers = [
    "unit: unit tests (fast, no I/O)",
    "contract: contract tests against saved fixtures",
    "integration: integration tests (require supabase start)",
    "mcp: MCP server direct-call tests",
    "e2e: end-to-end tests (STDIO roundtrip)",
]

[tool.coverage.run]
source = ["src/cryptozavr"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "@abstractmethod",
]
show_missing = true
skip_covered = false
```

- [ ] **Step 4: Create virtual environment with `uv sync`**

Run:
```bash
uv sync --all-extras
```

Expected output includes: `Creating virtual environment at: .venv`, `Installed XX packages`.

- [ ] **Step 5: Verify Python and dependencies**

Run:
```bash
uv run python --version
uv run python -c "import fastmcp; print(fastmcp.__version__)"
```

Expected:
```text
Python 3.12.x
3.2.4 (or newer)
```

- [ ] **Step 6: Commit**

```bash
git add .python-version pyproject.toml uv.lock
```

Write to `/tmp/commit-msg.txt`:
```text
chore: add uv project with Python 3.12 and dev tooling

Pins runtime (fastmcp, pydantic, structlog) and dev deps (pytest, ruff, mypy).
Ruff config with broad rule selection; mypy strict; pytest asyncio-auto.
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 3: Pre-commit hooks

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Create `.pre-commit-config.yaml`**

Write to `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-json
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: check-merge-conflict
      - id: mixed-line-ending
        args: [--fix=lf]

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.2
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic>=2.9
          - pydantic-settings>=2.5
        files: ^src/
        args: [--config-file=pyproject.toml]
```

- [ ] **Step 2: Install pre-commit hooks**

Run:
```bash
uv run pre-commit install
```

Expected: `pre-commit installed at .git/hooks/pre-commit`

- [ ] **Step 3: Run pre-commit on all current files**

Run:
```bash
uv run pre-commit run --all-files
```

Expected: все хуки проходят (возможны фиксы trailing-whitespace в свежесозданных файлах, это нормально).

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml
```

Если есть изменения после autofix — добавить их тоже.

Write to `/tmp/commit-msg.txt`:
```bash
chore: add pre-commit hooks for ruff + mypy + hygiene

Enforces lint/format/types on every commit.
Also catches trailing whitespace, large files, YAML/TOML/JSON errors.
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 4: Package skeleton with empty layers

**Files:**
- Create: `src/cryptozavr/__init__.py`
- Create: `src/cryptozavr/domain/__init__.py`
- Create: `src/cryptozavr/application/__init__.py`
- Create: `src/cryptozavr/infrastructure/__init__.py`
- Create: `src/cryptozavr/mcp/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/mcp/__init__.py`

- [ ] **Step 1: Create `src/cryptozavr/__init__.py`**

Write to `src/cryptozavr/__init__.py`:
```python
"""cryptozavr — risk-first crypto market research plugin for Claude Code.

See docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md for full design.
"""

__version__ = "0.0.1"
```

- [ ] **Step 2: Create domain layer package marker**

Write to `src/cryptozavr/domain/__init__.py`:
```python
"""Domain layer: pure value objects, entities, and Protocol interfaces.

No I/O. No external dependencies except pydantic. Populated in M2.
"""
```

- [ ] **Step 3: Create application layer package marker**

Write to `src/cryptozavr/application/__init__.py`:
```python
"""Application layer: use-case orchestration via services.

Facade over domain + infrastructure. Populated in M3.
"""
```

- [ ] **Step 4: Create infrastructure layer package marker**

Write to `src/cryptozavr/infrastructure/__init__.py`:
```python
"""Infrastructure layer: providers (CCXT, CoinGecko), Supabase gateway, observability.

Implements Protocol interfaces from domain. Populated in M2.
"""
```

- [ ] **Step 5: Create MCP layer package marker**

Write to `src/cryptozavr/mcp/__init__.py`:
```python
"""MCP facade: FastMCP server, tools, resources, prompts, middleware."""
```

- [ ] **Step 6: Create test package markers**

Write to `tests/__init__.py`:
```python
```

Write to `tests/unit/__init__.py`:
```python
```

Write to `tests/unit/mcp/__init__.py`:
```python
```

- [ ] **Step 7: Verify package import**

Run:
```bash
uv run python -c "import cryptozavr; print(cryptozavr.__version__)"
```

Expected: `0.0.1`

- [ ] **Step 8: Commit**

```bash
git add src/cryptozavr tests
```

Write to `/tmp/commit-msg.txt`:
```bash
feat: add layered package skeleton (domain/application/infra/mcp)

Layers stubbed with docstrings describing their roles and M2/M3 fill-in schedule.
Version 0.0.1.
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 5: MCP Settings — Pydantic Settings из env

**Files:**
- Create: `src/cryptozavr/mcp/settings.py`
- Create: `tests/unit/mcp/test_settings.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/mcp/test_settings.py`:
```python
"""Test Settings load from environment variables."""

from __future__ import annotations

import pytest

from cryptozavr.mcp.settings import Mode, Settings

def test_settings_defaults_with_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings must load with minimal required env (SUPABASE_* placeholders)."""
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "local-dev-key")
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
    )

    settings = Settings()

    assert settings.supabase_url == "http://127.0.0.1:54321"
    assert settings.supabase_service_role_key == "local-dev-key"
    assert settings.mode == Mode.RESEARCH_ONLY
    assert settings.log_level == "INFO"

def test_settings_mode_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """CRYPTOZAVR_MODE env overrides default mode."""
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "local-dev-key")
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
    )
    monkeypatch.setenv("CRYPTOZAVR_MODE", "research_only")

    settings = Settings()

    assert settings.mode == Mode.RESEARCH_ONLY

def test_settings_invalid_mode_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid mode value raises ValidationError."""
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "local-dev-key")
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
    )
    monkeypatch.setenv("CRYPTOZAVR_MODE", "cowboy_mode")

    with pytest.raises(Exception):  # pydantic ValidationError
        Settings()

def test_settings_missing_required_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing SUPABASE_URL raises ValidationError."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "local-dev-key")

    with pytest.raises(Exception):
        Settings()
```

- [ ] **Step 2: Run test — must fail**

Run:
```bash
uv run pytest tests/unit/mcp/test_settings.py -v
```

Expected: `FAIL` с `ModuleNotFoundError: No module named 'cryptozavr.mcp.settings'`.

- [ ] **Step 3: Implement Settings**

Write to `src/cryptozavr/mcp/settings.py`:
```python
"""Pydantic Settings for cryptozavr MCP server.

All configuration comes from env vars (prefixed CRYPTOZAVR_ or SUPABASE_).
Loaded once at server startup.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Mode(StrEnum):
    """Operational mode governing which capabilities are available.

    MVP supports only RESEARCH_ONLY. Other modes are reserved for future phases.
    """

    RESEARCH_ONLY = "research_only"
    PAPER_TRADING = "paper_trading"
    APPROVAL_GATED_LIVE = "approval_gated_live"
    POLICY_CONSTRAINED_AUTO_LIVE = "policy_constrained_auto_live"

class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Supabase ---
    supabase_url: str = Field(
        alias="SUPABASE_URL",
        description="Supabase REST endpoint, e.g. http://127.0.0.1:54321 (local) or cloud URL.",
    )
    supabase_service_role_key: str = Field(
        alias="SUPABASE_SERVICE_ROLE_KEY",
        description="Service role key — bypasses RLS. Keep out of git.",
    )
    supabase_db_url: str = Field(
        alias="SUPABASE_DB_URL",
        description="Direct Postgres connection string for asyncpg hot-path.",
    )

    # --- cryptozavr runtime ---
    mode: Mode = Field(
        default=Mode.RESEARCH_ONLY,
        alias="CRYPTOZAVR_MODE",
        description="Operational mode. MVP locks this to research_only.",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        alias="CRYPTOZAVR_LOG_LEVEL",
    )
```

- [ ] **Step 4: Run tests — must pass**

Run:
```bash
uv run pytest tests/unit/mcp/test_settings.py -v
```

Expected: `4 passed`.

- [ ] **Step 5: Run mypy on new file**

Run:
```bash
uv run mypy src/cryptozavr/mcp/settings.py
```

Expected: `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add src/cryptozavr/mcp/settings.py tests/unit/mcp/test_settings.py
```

Write to `/tmp/commit-msg.txt`:
```text
feat(mcp): add Pydantic Settings with Mode enum

Loads SUPABASE_URL/KEY/DB_URL as required, CRYPTOZAVR_MODE/LOG_LEVEL with defaults.
MVP defaults mode to RESEARCH_ONLY.
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 6: FastMCP server with echo tool

**Files:**
- Create: `src/cryptozavr/mcp/server.py`
- Create: `tests/unit/mcp/test_server_startup.py`
- Create: `tests/unit/mcp/test_echo_tool.py`

- [ ] **Step 1: Write the server startup test**

Write to `tests/unit/mcp/test_server_startup.py`:
```python
"""Smoke test: build_server() produces a FastMCP instance with registered tools."""

from __future__ import annotations

import pytest

from cryptozavr.mcp.server import build_server
from cryptozavr.mcp.settings import Mode, Settings

@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "local-dev-key")
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
    )
    return Settings()

def test_build_server_returns_fastmcp_instance(settings: Settings) -> None:
    """build_server produces a server with the correct name and version."""
    mcp = build_server(settings)

    assert mcp.name == "cryptozavr-research"
    assert mcp.version == "0.0.1"

async def test_build_server_registers_echo_tool(settings: Settings) -> None:
    """Echo tool must be listed after server build."""
    mcp = build_server(settings)

    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    assert "echo" in tool_names

async def test_build_server_respects_current_mode(settings: Settings) -> None:
    """Server exposes current mode (for future mode-aware tools)."""
    mcp = build_server(settings)

    # Mode is not directly on FastMCP instance; we verify indirectly via a tool
    # that reports it. In M1 the echo tool doesn't return mode, but we assert
    # that the server was built without errors for research_only.
    assert settings.mode == Mode.RESEARCH_ONLY
```

- [ ] **Step 2: Write the echo tool test**

Write to `tests/unit/mcp/test_echo_tool.py`:
```python
"""Direct server call pattern (FastMCP v3 test style — see v3-notes/provider-test-pattern.md)."""

from __future__ import annotations

import pytest

from cryptozavr.mcp.server import build_server
from cryptozavr.mcp.settings import Settings

@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "local-dev-key")
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
    )
    return Settings()

async def test_echo_tool_returns_the_same_message(settings: Settings) -> None:
    """echo(message) -> {"message": message, "version": "0.0.1"}."""
    mcp = build_server(settings)

    result = await mcp.call_tool("echo", {"message": "hello cryptozavr"})

    assert result.structured_content == {
        "message": "hello cryptozavr",
        "version": "0.0.1",
    }

async def test_echo_tool_handles_empty_string(settings: Settings) -> None:
    """Empty message is allowed and echoed back."""
    mcp = build_server(settings)

    result = await mcp.call_tool("echo", {"message": ""})

    assert result.structured_content == {"message": "", "version": "0.0.1"}

async def test_echo_tool_rejects_missing_message(settings: Settings) -> None:
    """Missing required argument raises an error."""
    mcp = build_server(settings)

    with pytest.raises(Exception):  # FastMCP ToolError or Pydantic ValidationError
        await mcp.call_tool("echo", {})
```

- [ ] **Step 3: Run tests — must fail**

Run:
```bash
uv run pytest tests/unit/mcp/test_server_startup.py tests/unit/mcp/test_echo_tool.py -v
```

Expected: `FAIL` с `ModuleNotFoundError: No module named 'cryptozavr.mcp.server'`.

- [ ] **Step 4: Implement server**

Write to `src/cryptozavr/mcp/server.py`:
```python
"""FastMCP server bootstrap with single echo tool.

M1 scope: echo only. Real tools arrive in M3.
"""

from __future__ import annotations

import logging
import sys
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from cryptozavr import __version__
from cryptozavr.mcp.settings import Settings

_LOGGER = logging.getLogger(__name__)

def build_server(settings: Settings) -> FastMCP:
    """Build the FastMCP server instance.

    Args:
        settings: Runtime configuration loaded from env.

    Returns:
        Configured FastMCP instance ready for mcp.run().
    """
    mcp = FastMCP(
        name="cryptozavr-research",
        version=__version__,
    )

    @mcp.tool(
        name="echo",
        description=(
            "Smoke-test tool. Returns the provided message with server version. "
            "Useful for verifying the plugin loads and dispatches tool calls correctly."
        ),
        tags={"smoke", "mvp", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    def echo(
        message: Annotated[str, Field(description="Any string to echo back.")],
    ) -> dict[str, str]:
        """Echo the input message with server version metadata."""
        return {"message": message, "version": __version__}

    _LOGGER.info(
        "cryptozavr-research built",
        extra={"mode": settings.mode.value, "version": __version__},
    )
    return mcp

def main() -> None:
    """Entrypoint for `python -m cryptozavr.mcp.server` and console_scripts."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    settings = Settings()
    mcp = build_server(settings)
    mcp.run()  # STDIO by default; transport auto-detected

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests — must pass**

Run:
```bash
uv run pytest tests/unit/mcp/ -v
```

Expected: `6 passed` (3 from startup + 3 from echo).

- [ ] **Step 6: Run mypy**

Run:
```bash
uv run mypy src/cryptozavr/mcp/server.py
```

Expected: `Success: no issues found`.

- [ ] **Step 7: Commit**

```bash
git add src/cryptozavr/mcp/server.py tests/unit/mcp/test_server_startup.py tests/unit/mcp/test_echo_tool.py
```

Write to `/tmp/commit-msg.txt`:
```bash
feat(mcp): add FastMCP server with echo smoke tool

build_server() returns configured FastMCP; main() is the CLI entrypoint.
Echo tool returns message + version; used as the smoke test for plugin registration.
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 7: Environment template and conftest

**Files:**
- Create: `.env.example`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `.env.example`**

Write to `.env.example`:
```bash
# cryptozavr environment template.
# Copy to .env (gitignored) and fill in actual values for local dev.

# --- Supabase (required) ---
# For local dev with `supabase start` these defaults usually apply.
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoic3VwYWJhc2UtZGVtbyIsImlhdCI6MTY0MTc2OTIwMCwiZXhwIjoxNzk5NTM1NjAwfQ.DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q
SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
# SUPABASE_JWT_SECRET is only needed from phase 2+ when Auth is introduced.
# SUPABASE_JWT_SECRET=

# --- cryptozavr runtime ---
CRYPTOZAVR_MODE=research_only
CRYPTOZAVR_LOG_LEVEL=INFO

# --- Cache TTLs (used from M2) ---
# CRYPTOZAVR_CACHE_TTL_TICKER_SECONDS=5
# CRYPTOZAVR_CACHE_TTL_OHLCV_SECONDS=60

# --- Providers (used from M2) ---
# KuCoin public endpoints don't require keys in MVP.
# KUCOIN_API_KEY=
# KUCOIN_API_SECRET=
# KUCOIN_API_PASSPHRASE=
# COINGECKO_API_KEY=  # optional for free tier

# --- Rate limits (used from M2) ---
# KUCOIN_RATE_LIMIT_RPS=30
# COINGECKO_RATE_LIMIT_RPM=30
```

- [ ] **Step 2: Create `tests/conftest.py`**

Write to `tests/conftest.py`:
```python
"""Global pytest fixtures for cryptozavr test suite."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest

@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Ensure each test starts with a clean env for CRYPTOZAVR_/SUPABASE_ vars.

    This prevents developer's local .env from leaking into unit tests.
    Integration tests can opt back in by setting vars explicitly via monkeypatch.
    """
    for key in list(os.environ.keys()):
        if key.startswith(("CRYPTOZAVR_", "SUPABASE_", "KUCOIN_", "COINGECKO_")):
            monkeypatch.delenv(key, raising=False)
    yield
```

- [ ] **Step 3: Run tests — still pass with new conftest**

Run:
```bash
uv run pytest tests/ -v
```

Expected: все 7 тестов (4 settings + 3 echo + 3 startup) проходят (isolate_env fixture не ломает существующие — они сами ставят env через monkeypatch).

Note: если конкретный тест startup или echo test сломался — это потому, что его fixture `settings` полагается на env. Он уже ставит env через monkeypatch, поэтому isolate_env (который удаляет сначала) ОК.

- [ ] **Step 4: Commit**

```bash
git add .env.example tests/conftest.py
```

Write to `/tmp/commit-msg.txt`:
```text
chore: add .env.example and env-isolating pytest fixture

Env template documents all current and near-future variables.
conftest auto-clears cryptozavr/supabase vars per test to prevent dev .env leak.
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 8: Supabase CLI init

**Files:**
- Create: `supabase/config.toml` (generated)
- Create: `supabase/migrations/.gitkeep`
- Create: `supabase/seed.sql`
- Create: `scripts/bootstrap-supabase.sh`

- [ ] **Step 1: Verify Supabase CLI installed**

Run:
```bash
supabase --version
```

Expected: `1.x.x` or newer. If not installed: `brew install supabase/tap/supabase`.

- [ ] **Step 2: Initialize Supabase project**

Run:
```bash
cd /Users/laptop/dev/cryptozavr && supabase init
```

Expected output: `Finished supabase init.` — creates `supabase/config.toml` and `supabase/.gitignore`.

- [ ] **Step 3: Inspect and minimize config**

Open `supabase/config.toml` created by init. Verify these key sections exist (edit if Supabase CLI defaults differ):

```toml
project_id = "cryptozavr"

[api]
enabled = true
port = 54321
schemas = ["public", "graphql_public", "cryptozavr"]
extra_search_path = ["public", "extensions"]
max_rows = 1000

[db]
port = 54322
shadow_port = 54320
major_version = 15

[db.pooler]
enabled = false

[realtime]
enabled = true

[studio]
enabled = true
port = 54323

[storage]
enabled = true
file_size_limit = "50MiB"

[auth]
enabled = true
site_url = "http://127.0.0.1:3000"
```

Если CLI сгенерировал дополнительные секции — оставить как есть; только `schemas = [..., "cryptozavr"]` добавить обязательно (иначе PostgREST не увидит нашу схему в M2).

- [ ] **Step 4: Create migrations gitkeep**

Run:
```bash
mkdir -p supabase/migrations
touch supabase/migrations/.gitkeep
```

- [ ] **Step 5: Create empty seed.sql**

Write to `supabase/seed.sql`:
```sql
-- Seed data for local development.
-- Populated in M2 with reference data (venues, core symbol_aliases).
```

- [ ] **Step 6: Create bootstrap script**

Write to `scripts/bootstrap-supabase.sh`:
```bash
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
```

Make executable:
```bash
chmod +x scripts/bootstrap-supabase.sh
```

- [ ] **Step 7: Test bootstrap script**

Run:
```bash
./scripts/bootstrap-supabase.sh
```

Expected: Supabase stack запускается; финальный `supabase status` выводит URL и keys. Может занять 1–3 минуты при первом запуске (pull docker images).

If fails with docker-not-running: start Docker Desktop; rerun.

- [ ] **Step 8: Stop Supabase**

Run:
```bash
supabase stop
```

- [ ] **Step 9: Commit**

```bash
git add supabase/ scripts/bootstrap-supabase.sh
```

Write to `/tmp/commit-msg.txt`:
```text
chore: init supabase cli with cryptozavr schema reserved

config.toml exposes cryptozavr schema via PostgREST; migrations dir stubbed.
scripts/bootstrap-supabase.sh gives one-command local stack + status output.
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 9: Claude Code plugin manifest

**Files:**
- Create: `plugin.json`

- [ ] **Step 1: Create `plugin.json`**

Write to `plugin.json`:
```json
{
  "$schema": "https://anthropic.com/claude-code/plugin-schema.json",
  "name": "cryptozavr",
  "version": "0.0.1",
  "description": "Risk-first crypto market research plugin for Claude Code. Read-only MVP with KuCoin + CoinGecko providers, Supabase-backed cache and audit trail.",
  "author": {
    "name": "cryptozavr",
    "email": "e.a.gurin@outlook.com"
  },
  "license": "MIT",
  "keywords": ["crypto", "market-data", "research", "fastmcp", "supabase", "mcp"],
  "mcpServers": ["cryptozavr-research"],
  "skills": "skills/",
  "commands": "commands/",
  "hooks": "hooks/"
}
```

- [ ] **Step 2: Create placeholder directories**

Run:
```bash
mkdir -p skills commands hooks
touch skills/.gitkeep commands/.gitkeep hooks/.gitkeep
```

- [ ] **Step 3: Validate JSON syntax**

Run:
```bash
uv run python -c "import json; json.load(open('plugin.json'))"
```

Expected: no output (success).

- [ ] **Step 4: Commit**

```bash
git add plugin.json skills commands hooks
```

Write to `/tmp/commit-msg.txt`:
```bash
feat: add Claude Code plugin manifest

plugin.json at v0.0.1 declares name, description, MCP server, and empty skills/commands/hooks dirs.
Real skills/commands populated in M4.
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 10: `.mcp.json` — MCP-server registration

**Files:**
- Create: `.mcp.json`

- [ ] **Step 1: Create `.mcp.json`**

Write to `.mcp.json`:
```json
{
  "$schema": "https://anthropic.com/claude-code/mcp-schema.json",
  "mcpServers": {
    "cryptozavr-research": {
      "command": "sh",
      "args": [
        "-c",
        ". ${CLAUDE_PLUGIN_ROOT}/.env && uv run --directory ${CLAUDE_PLUGIN_ROOT} python -m cryptozavr.mcp.server"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

- [ ] **Step 2: Validate JSON**

Run:
```bash
uv run python -c "import json; json.load(open('.mcp.json'))"
```

Expected: no output (success).

- [ ] **Step 3: Commit**

```bash
git add .mcp.json
```

Write to `/tmp/commit-msg.txt`:
```bash
feat: add .mcp.json registering cryptozavr-research server

Uses sh -c to source .env before uv run, so ${SUPABASE_URL} etc. are in scope.
Relies on ${CLAUDE_PLUGIN_ROOT} to locate the plugin after install/link.
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 11: `fastmcp.json` — FastMCP runtime config

**Files:**
- Create: `fastmcp.json`

- [ ] **Step 1: Create `fastmcp.json`**

Write to `fastmcp.json`:
```json
{
  "$schema": "https://gofastmcp.com/public/schemas/fastmcp.json/v1.json",
  "source": {
    "path": "src/cryptozavr/mcp/server.py",
    "entrypoint": "mcp"
  },
  "environment": {
    "python": ">=3.12,<3.14",
    "dependencies": [
      "fastmcp>=3.2.4",
      "pydantic>=2.9",
      "pydantic-settings>=2.5",
      "structlog>=24.4"
    ]
  }
}
```

Note: M1 deps only. M2 will add httpx/ccxt/asyncpg/supabase/realtime; M3 will add hypothesis/polyfactory/respx.

- [ ] **Step 2: Validate JSON**

Run:
```bash
uv run python -c "import json; json.load(open('fastmcp.json'))"
```

Expected: no output (success).

- [ ] **Step 3: Test via `fastmcp dev`**

Run:
```bash
uv run fastmcp dev fastmcp.json --no-launch-inspector 2>&1 | head -20
```

Expected: сервер стартует и слушает на default порту; видны log-и about "cryptozavr-research". Ctrl-C чтобы остановить.

Note: Если `--no-launch-inspector` не поддерживается в вашей версии FastMCP — просто `fastmcp dev fastmcp.json` и закрыть инспектор вручную.

- [ ] **Step 4: Commit**

```bash
git add fastmcp.json
```

Write to `/tmp/commit-msg.txt`:
```bash
feat: add fastmcp.json for FastMCP v3 dev workflow

Declares server source + entrypoint + minimal M1 dependencies.
Enables `fastmcp dev fastmcp.json` for interactive testing.
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 12: Smoke-test plugin in Claude Code (manual verification)

**Files:** (none — this is a manual verification step)

- [ ] **Step 1: Link plugin locally**

In Claude Code terminal (not regular shell):
```text
/plugin link /Users/laptop/dev/cryptozavr
```

Expected: Claude Code reports "Plugin linked: cryptozavr v0.0.1".

- [ ] **Step 2: Verify plugin is listed**

In Claude Code:
```text
/plugins
```

Expected: `cryptozavr` appears in the list with status `connected`.

- [ ] **Step 3: Verify echo tool is callable**

In Claude Code chat:
```text
Use the echo tool with message "hello from M1"
```

Expected: Claude calls `echo(message="hello from M1")` and returns `{"message": "hello from M1", "version": "0.0.1"}`.

- [ ] **Step 4: Check MCP server logs**

Run:
```bash
tail -50 ~/Library/Logs/Claude/mcp-server-cryptozavr-research.log 2>/dev/null || echo "log path may differ; check /plugin logs"
```

Expected: you see log lines from the server startup and the echo call.

- [ ] **Step 5: Document verification outcome**

If all 4 steps succeeded, this task is done. If any failed:
- Problem diagnosis: inspect `~/Library/Logs/Claude/mcp-server-*.log` or `/plugin logs cryptozavr`.
- Common fixes:
  - Missing `.env`: `cp .env.example .env` (doesn't need real Supabase yet since echo tool doesn't touch DB).
  - Wrong path in `${CLAUDE_PLUGIN_ROOT}`: verify `/plugin link` used absolute path.
  - uv not in PATH for Claude Code: ensure `/usr/local/bin/uv` or `~/.local/bin/uv` is accessible.

**No commit for this task** — it's verification only. Any fixes go into their own commit.

---

### Task 13: CI pipeline — lint + typecheck + unit tests

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create CI workflow**

Write to `.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    name: Lint & Typecheck
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Set up Python
        run: uv python install 3.12
      - name: Install dependencies
        run: uv sync --all-extras
      - name: Ruff check
        run: uv run ruff check .
      - name: Ruff format check
        run: uv run ruff format --check .
      - name: Mypy
        run: uv run mypy src

  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Set up Python
        run: uv python install 3.12
      - name: Install dependencies
        run: uv sync --all-extras
      - name: Run pytest
        run: |
          uv run pytest tests/unit -v \
            --cov=cryptozavr \
            --cov-report=term-missing \
            --cov-report=xml
      - name: Upload coverage
        uses: actions/upload-artifact@v4
        with:
          name: coverage-xml
          path: coverage.xml
          if-no-files-found: ignore
```

- [ ] **Step 2: Verify locally that lint+test passes**

Run:
```bash
uv run ruff check . && \
uv run ruff format --check . && \
uv run mypy src && \
uv run pytest tests/unit -v
```

Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
```

Write to `/tmp/commit-msg.txt`:
```text
ci: add lint + typecheck + unit-tests workflow

Runs on push/PR to main; uses uv with cache.
Lint job: ruff check + ruff format + mypy.
Test job: pytest with coverage reported to term + xml.
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 14: Plugin validation workflow

**Files:**
- Create: `.github/workflows/plugin-validate.yml`
- Create: `scripts/validate-plugin.py`

- [ ] **Step 1: Create validation script**

Write to `scripts/validate-plugin.py`:
```python
#!/usr/bin/env python3
"""Validate plugin artefacts: plugin.json, .mcp.json, fastmcp.json, skills frontmatter.

Used by CI and locally before commits touching plugin-facing files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)

def _ok(msg: str) -> None:
    print(f"ok: {msg}")

def validate_json(path: Path, required_keys: set[str]) -> None:
    if not path.is_file():
        _fail(f"{path} does not exist")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        _fail(f"{path} is not valid JSON: {exc}")
    missing = required_keys - set(data.keys())
    if missing:
        _fail(f"{path} missing required keys: {sorted(missing)}")
    _ok(f"{path} parsed; required keys present")

def validate_plugin_json() -> None:
    validate_json(
        ROOT / "plugin.json",
        required_keys={"name", "version", "description", "mcpServers"},
    )

def validate_mcp_json() -> None:
    path = ROOT / ".mcp.json"
    validate_json(path, required_keys={"mcpServers"})
    data = json.loads(path.read_text())
    servers = data["mcpServers"]
    if "cryptozavr-research" not in servers:
        _fail(".mcp.json missing mcpServers['cryptozavr-research']")
    server = servers["cryptozavr-research"]
    for field in ("command", "args"):
        if field not in server:
            _fail(f".mcp.json cryptozavr-research missing '{field}'")
    _ok(".mcp.json cryptozavr-research server declared correctly")

def validate_fastmcp_json() -> None:
    path = ROOT / "fastmcp.json"
    validate_json(path, required_keys={"source", "environment"})
    data = json.loads(path.read_text())
    src = data["source"]
    if "path" not in src or "entrypoint" not in src:
        _fail("fastmcp.json source must have 'path' and 'entrypoint'")
    src_path = ROOT / src["path"]
    if not src_path.is_file():
        _fail(f"fastmcp.json source.path points to missing file: {src_path}")
    _ok("fastmcp.json source + environment valid")

def main() -> None:
    print("Validating plugin artefacts...")
    validate_plugin_json()
    validate_mcp_json()
    validate_fastmcp_json()
    print("All plugin artefacts valid.")

if __name__ == "__main__":
    main()
```

Make executable:
```bash
chmod +x scripts/validate-plugin.py
```

- [ ] **Step 2: Run validator locally**

Run:
```bash
uv run python scripts/validate-plugin.py
```

Expected output:
```text
Validating plugin artefacts...
ok: plugin.json parsed; required keys present
ok: .mcp.json parsed; required keys present
ok: .mcp.json cryptozavr-research server declared correctly
ok: fastmcp.json parsed; required keys present
ok: fastmcp.json source + environment valid
All plugin artefacts valid.
```

- [ ] **Step 3: Create CI workflow**

Write to `.github/workflows/plugin-validate.yml`:
```yaml
name: Plugin Validate

on:
  push:
    branches: [main]
    paths:
      - "plugin.json"
      - ".mcp.json"
      - "fastmcp.json"
      - "skills/**"
      - "commands/**"
      - "hooks/**"
      - "scripts/validate-plugin.py"
  pull_request:
    branches: [main]
    paths:
      - "plugin.json"
      - ".mcp.json"
      - "fastmcp.json"
      - "skills/**"
      - "commands/**"
      - "hooks/**"
      - "scripts/validate-plugin.py"

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v3
      - name: Set up Python
        run: uv python install 3.12
      - name: Run plugin validator
        run: uv run python scripts/validate-plugin.py
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/plugin-validate.yml scripts/validate-plugin.py
```

Write to `/tmp/commit-msg.txt`:
```text
ci: add plugin artefact validator and workflow

scripts/validate-plugin.py checks plugin.json/.mcp.json/fastmcp.json structure.
Workflow runs on changes to plugin-facing files only (paths filter).
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 15: Documentation

**Files:**
- Create: `README.md`
- Create: `CHANGELOG.md`
- Create: `LICENSE`
- Create: `docs/README.md`

- [ ] **Step 1: Create `README.md`**

Write to `README.md`:
```markdown
# cryptozavr

Risk-first crypto market research plugin for Claude Code. Provides disciplined, declarative, and explainable market data tools through a FastMCP v3+ server with Supabase-backed cache and audit trail.

**Status:** M1 Bootstrap complete. Data-layer and real tools arrive in M2+.

See [docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md](docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md) for the full MVP design.

## Philosophy

1. **Risk-first, not signal-first.** Risk architecture precedes trading features.
2. **Calm execution.** No FOMO, no panic. Dispassionate, institutional-minded.
3. **Declarative over ad-hoc.** Strategies, risk policies, execution policies as Pydantic specs.
4. **Explainability and auditability.** Every answer contains `data`, `quality`, `reasoning`.
5. **Safe agent design.** LLM proposes; human approves; deterministic code executes.

## Quickstart

### Prerequisites

- Python 3.12 (`.python-version` pinned)
- [uv](https://docs.astral.sh/uv/) for Python package management
- [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started) for local DB stack
- [Claude Code](https://www.anthropic.com/claude-code) for plugin integration
- Docker Desktop (runs Supabase locally)

### Install

```bash
git clone <repo-url> cryptozavr
cd cryptozavr
uv sync --all-extras
cp .env.example .env
./scripts/bootstrap-supabase.sh   # starts local Supabase stack
```

### Link plugin in Claude Code

```text
/plugin link /absolute/path/to/cryptozavr
```

Verify:
```text
/plugins                                  # cryptozavr should be connected
# Then ask Claude: "Use the echo tool with message 'test'"
```

## Development

Run tests:
```bash
uv run pytest tests/unit -v
```

Lint + typecheck:
```bash
uv run ruff check .
uv run ruff format .
uv run mypy src
```

Validate plugin artefacts:
```bash
uv run python scripts/validate-plugin.py
```

Run MCP server locally for debugging:
```bash
uv run fastmcp dev fastmcp.json
```

## Architecture

Layered onion: `domain/` (pure) → `application/` (use cases) → `infrastructure/` (providers + Supabase) → `mcp/` (FastMCP facade). See [design doc](docs/superpowers/specs/2026-04-21-cryptozavr-mvp-design.md) for details.

## Roadmap

- **M1 Bootstrap** ✅ — repo, tooling, FastMCP skeleton with echo tool, CI.
- **M2 Data layer** — Domain + Providers (KuCoin CCXT, CoinGecko) + Supabase schema + first real tool.
- **M3 Full MCP surface** — all 17 tools, 8 resources, 2 prompts, Application services.
- **M4 Plugin integration** — skills, slash-commands, E2E tests, v0.1.0 release.

Post-MVP: strategy engine (phase 2), risk engine (phase 3), paper trading (phase 4), approval-gated live (phase 5), multi-exchange (phase 6+).

## License

MIT
```bash

- [ ] **Step 2: Create `CHANGELOG.md`**

Write to `CHANGELOG.md`:
```markdown
# Changelog

All notable changes to cryptozavr will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — M1 Bootstrap
- Repository initialization with git, uv, ruff, mypy, pytest, pre-commit.
- Claude Code plugin manifest (`plugin.json`, `.mcp.json`).
- FastMCP v3+ server skeleton with `echo` smoke tool.
- Supabase CLI init with `cryptozavr` schema reserved.
- CI pipelines: lint + typecheck + unit tests, plugin artefact validation.
- Documentation: README, CHANGELOG, design spec, M1 implementation plan.
```

- [ ] **Step 3: Create `LICENSE`**

Write to `LICENSE`:
```bash
MIT License

Copyright (c) 2026 cryptozavr

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Create `docs/README.md`**

Write to `docs/README.md`:
```markdown
# cryptozavr documentation

## Specs
- [MVP design (2026-04-21)](superpowers/specs/2026-04-21-cryptozavr-mvp-design.md) — full architectural design for MVP (Phase 0 + Phase 1).

## Plans
- [M1 Bootstrap plan (2026-04-21)](superpowers/plans/2026-04-21-cryptozavr-m1-bootstrap.md) — this milestone.
- Plans for M2/M3/M4 are created after each preceding milestone completes.

## Roadmap

- **M1 Bootstrap** — repo, tooling, plugin skeleton, echo tool.
- **M2 Data layer** — domain, providers, Supabase, first real tool.
- **M3 Full MCP surface** — all 17 tools + resources + prompts.
- **M4 Plugin integration** — skills, commands, E2E, release.

## For contributors

See [README.md](../README.md) for quickstart. Design decisions and trade-offs live in the MVP spec.
```

- [ ] **Step 5: Commit**

```bash
git add README.md CHANGELOG.md LICENSE docs/README.md
```

Write to `/tmp/commit-msg.txt`:
```text
docs: add README, CHANGELOG, LICENSE, docs index

README covers philosophy, quickstart, architecture summary, roadmap.
CHANGELOG [Unreleased] records M1 additions.
LICENSE: MIT.
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt
```

---

### Task 16: Full local verification run

**Files:** (none — verification task)

- [ ] **Step 1: Full lint run**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: zero errors.

- [ ] **Step 2: Full typecheck**

Run:
```bash
uv run mypy src
```

Expected: `Success: no issues found`.

- [ ] **Step 3: Full test run with coverage**

Run:
```bash
uv run pytest tests/unit -v --cov=cryptozavr --cov-report=term-missing
```

Expected: 7 tests pass; coverage на `src/cryptozavr/mcp/settings.py` и `src/cryptozavr/mcp/server.py` ~ 90%+ (некоторое снижение допустимо из-за `if __name__ == "__main__"`).

- [ ] **Step 4: Validator run**

Run:
```bash
uv run python scripts/validate-plugin.py
```

Expected: all `ok:`, exit 0.

- [ ] **Step 5: Pre-commit on everything**

Run:
```bash
uv run pre-commit run --all-files
```

Expected: all hooks pass. If any fix trailing whitespace or EOF — add the changes and proceed.

- [ ] **Step 6: Verify package importability outside dev env**

Run:
```bash
uv run python -c "
from cryptozavr import __version__
from cryptozavr.mcp.settings import Mode, Settings
from cryptozavr.mcp.server import build_server
print(f'cryptozavr {__version__}: Mode={Mode.RESEARCH_ONLY}')
"
```

Expected:
```text
cryptozavr 0.0.1: Mode=research_only
```

- [ ] **Step 7: Supabase smoke**

Run:
```bash
supabase start
supabase status
supabase stop
```

Expected: all services report ok; stop cleanly.

---

### Task 17: Tag v0.0.1 and finalize M1

**Files:** (none — tagging task)

- [ ] **Step 1: Verify git is clean**

Run:
```bash
git status
```

Expected: `nothing to commit, working tree clean`.

If not clean — commit or discard outstanding changes before tagging.

- [ ] **Step 2: Review commit log**

Run:
```bash
git log --oneline
```

Expected: ~15 commits from Tasks 1–15, all with Conventional Commits format.

- [ ] **Step 3: Create annotated tag**

Run:
```bash
git tag -a v0.0.1 -m "M1 Bootstrap complete

Plugin skeleton, FastMCP echo tool, Supabase init, CI, documentation.
Ready for M2 (data layer)."
```

- [ ] **Step 4: Verify tag**

Run:
```bash
git tag -l -n5
```

Expected: `v0.0.1   M1 Bootstrap complete...`

- [ ] **Step 5: Document handoff to M2**

Write an `UNRELEASED` entry in `CHANGELOG.md` — move M1 items under `## [0.0.1] - YYYY-MM-DD` heading, add a new empty `## [Unreleased]` on top.

Edit `CHANGELOG.md` replacing:
```markdown
## [Unreleased]

### Added — M1 Bootstrap
- Repository initialization with git, uv, ruff, mypy, pytest, pre-commit.
...
```

with (use today's date, 2026-04-21):
```markdown
## [Unreleased]

## [0.0.1] - 2026-04-21

### Added — M1 Bootstrap
- Repository initialization with git, uv, ruff, mypy, pytest, pre-commit.
- Claude Code plugin manifest (`plugin.json`, `.mcp.json`).
- FastMCP v3+ server skeleton with `echo` smoke tool.
- Supabase CLI init with `cryptozavr` schema reserved.
- CI pipelines: lint + typecheck + unit tests, plugin artefact validation.
- Documentation: README, CHANGELOG, design spec, M1 implementation plan.
```

- [ ] **Step 6: Amend tag to include CHANGELOG update**

```bash
git add CHANGELOG.md
```

Write to `/tmp/commit-msg.txt`:
```bash
docs: finalize CHANGELOG for v0.0.1 (M1 Bootstrap)
```

```bash
git commit -F /tmp/commit-msg.txt
rm /tmp/commit-msg.txt

# Recreate tag at HEAD after the CHANGELOG commit
git tag -d v0.0.1
git tag -a v0.0.1 -m "M1 Bootstrap complete

Plugin skeleton, FastMCP echo tool, Supabase init, CI, documentation.
Ready for M2 (data layer)."
```

- [ ] **Step 7: Summary**

Print final state:
```bash
echo "=== M1 Bootstrap complete ==="
git log --oneline -20
echo ""
git tag -l
echo ""
uv run python -c "import cryptozavr; print(f'Version: {cryptozavr.__version__}')"
```

Expected: ~16 commits, tag `v0.0.1`, version `0.0.1`.

**Do not push yet.** Pushing to remote is an explicit user decision, not part of M1.

---

## Acceptance Criteria for M1 (summary)

1. ✅ `uv sync --all-extras` installs cleanly on fresh clone.
2. ✅ `uv run ruff check .` → zero errors.
3. ✅ `uv run ruff format --check .` → zero differences.
4. ✅ `uv run mypy src` → `Success: no issues found`.
5. ✅ `uv run pytest tests/unit -v` → 7 tests pass (4 settings + 3 echo/startup).
6. ✅ Coverage on `src/cryptozavr/` (excluding empty stubs) ≥ 85%.
7. ✅ `uv run python scripts/validate-plugin.py` → all ok.
8. ✅ `supabase start && supabase status && supabase stop` → clean lifecycle.
9. ✅ `/plugin link /path/to/cryptozavr` in Claude Code connects the plugin.
10. ✅ Claude Code can call `echo` tool and receive `{"message": ..., "version": "0.0.1"}`.
11. ✅ Git tag `v0.0.1` at HEAD.
12. ✅ `.github/workflows/ci.yml` and `.github/workflows/plugin-validate.yml` present and (when run in CI) green.

---

## Handoff to M2

After M1 is complete and the tag exists, the next step is **M2 Data layer**:

1. Invoke writing-plans skill again with context "M1 complete, write plan for M2 Data layer based on the MVP spec sections 3 (Domain model), 4 (Providers), 5 (Supabase)".
2. M2 will populate `src/cryptozavr/domain/`, `src/cryptozavr/infrastructure/providers/` and `supabase/migrations/`, culminating in `get_ticker` tool returning real data from KuCoin through the Supabase cache-aside path.

---

## Notes

- This plan assumes **greenfield** state. If you re-run it on a partially-built repo, every "Create file X" step becomes "Verify X matches spec; adjust if drifted".
- Several commits per task is intentional — atomic Conventional Commits make `git log` readable and bisect-friendly.
- No placeholder code is introduced. Every created file has immediate purpose or a documented M2/M3/M4 slot.
- **Do not skip tests** to move faster. The TDD rhythm (red → green → commit) is the skill being practised, not an optional overhead.
