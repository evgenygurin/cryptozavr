"""Tests for Unit 2D-2 / 2E-1 read-only strategy tools: list / explain / diff.

explain_strategy / diff_strategies are pure (no DI dependencies). list_
strategies, as of 2E-1, pulls from StrategySpecRepository — tests inject a
MagicMock with an AsyncMock `list_recent` returning a list of StoredStrategy-
Row instances. We use the same Client(mcp).call_tool(...) pattern as
test_validate_strategy / test_catalog_tools and a shared `_structured`
helper to extract either structured_content (MCP-native) or parsed text JSON.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastmcp import Client, FastMCP
from pydantic import ValidationError

from cryptozavr.infrastructure.persistence.strategy_spec_repo import (
    StoredStrategyRow,
    StrategySpecRepository,
)
from cryptozavr.mcp.lifespan_state import LIFESPAN_KEYS
from cryptozavr.mcp.tools.strategy_dtos import (
    DiffStrategiesResponse,
    ExplainStrategyResponse,
    ExplanationSectionDTO,
    FieldDiffDTO,
)
from cryptozavr.mcp.tools.strategy_read_only import register_strategy_read_only_tools


def _build_server(repo: MagicMock | None = None) -> FastMCP:
    """Build a server with an optional mock StrategySpecRepository in the
    lifespan dict. Tools that don't touch the repo (explain / diff) still need
    a StrategySpecRepository-spec'd mock so FastMCP's `Depends()` resolver
    doesn't try to treat the repo as a context manager (bare MagicMock()
    synthesises __aenter__ which trips resolve-time wrapping)."""
    effective_repo = repo if repo is not None else _mock_repo(rows=[])

    @asynccontextmanager
    async def lifespan(_server):  # type: ignore[no-untyped-def]
        yield {LIFESPAN_KEYS.strategy_spec_repo: effective_repo}

    mcp = FastMCP(name="t", version="0", lifespan=lifespan)
    register_strategy_read_only_tools(mcp)
    return mcp


def _mock_repo(rows: list[StoredStrategyRow] | None = None) -> MagicMock:
    """Build a StrategySpecRepository-spec MagicMock with a pre-wired
    `list_recent` AsyncMock. The `spec=...` constraint is load-bearing —
    see docstring on `_build_server`."""
    repo = MagicMock(spec=StrategySpecRepository)
    repo.list_recent = AsyncMock(return_value=list(rows or []))
    return repo


def _make_row(
    *,
    name: str = "sma-cross",
    version: int = 1,
    venue_id: str = "kucoin",
    symbol_native: str = "BTC-USDT",
    timeframe: str = "1h",
) -> StoredStrategyRow:
    created = datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC)
    updated = datetime(2026, 4, 22, 12, 30, 0, tzinfo=UTC)
    return StoredStrategyRow(
        id=uuid4(),
        name=name,
        version=version,
        venue_id=venue_id,
        symbol_native=symbol_native,
        timeframe=timeframe,
        created_at_ms=int(created.timestamp() * 1000),
        updated_at_ms=int(updated.timestamp() * 1000),
    )


def _structured(result) -> dict:  # type: ignore[no-untyped-def]
    sc = getattr(result, "structured_content", None)
    if sc is not None:
        return sc
    return json.loads(result.content[0].text)


def _valid_payload() -> dict:
    return {
        "name": "sma-cross",
        "description": "fast-over-slow SMA cross",
        "venue": "kucoin",
        "symbol": {
            "venue": "kucoin",
            "base": "BTC",
            "quote": "USDT",
            "market_type": "spot",
            "native_symbol": "BTC-USDT",
        },
        "timeframe": "1h",
        "entry": {
            "side": "long",
            "conditions": [
                {
                    "lhs": {"kind": "sma", "period": 20, "source": "close"},
                    "op": "crosses_above",
                    "rhs": {"kind": "sma", "period": 50, "source": "close"},
                },
            ],
        },
        "exit": {
            "conditions": [],
            "take_profit_pct": "0.05",
            "stop_loss_pct": "0.02",
        },
        "size_pct": "0.25",
        "version": 1,
    }


# -------------------------- list_strategies --------------------------------


class TestListStrategies:
    @pytest.mark.asyncio
    async def test_empty_repo_returns_empty_list(self) -> None:
        repo = _mock_repo(rows=[])
        mcp = _build_server(repo)
        async with Client(mcp) as client:
            result = await client.call_tool("list_strategies", {})
        payload = _structured(result)
        assert payload["strategies"] == []
        assert payload["error"] is None
        # list_recent called with default limit=50
        repo.list_recent.assert_awaited_once_with(limit=50)

    @pytest.mark.asyncio
    async def test_rows_mapped_to_summary_dto(self) -> None:
        row = _make_row(name="sma-cross", venue_id="kucoin", symbol_native="BTC-USDT")
        repo = _mock_repo(rows=[row])
        mcp = _build_server(repo)
        async with Client(mcp) as client:
            result = await client.call_tool("list_strategies", {})
        payload = _structured(result)
        assert len(payload["strategies"]) == 1
        entry = payload["strategies"][0]
        assert entry["id"] == str(row.id)
        assert entry["name"] == "sma-cross"
        assert entry["version"] == row.version
        assert entry["venue"] == "kucoin"
        assert entry["symbol_native"] == "BTC-USDT"
        assert entry["timeframe"] == "1h"
        assert entry["created_at_ms"] == row.created_at_ms
        assert entry["updated_at_ms"] == row.updated_at_ms
        assert payload["error"] is None

    @pytest.mark.asyncio
    async def test_limit_passed_through_to_repo(self) -> None:
        repo = _mock_repo(rows=[])
        mcp = _build_server(repo)
        async with Client(mcp) as client:
            await client.call_tool("list_strategies", {"limit": 5})
        repo.list_recent.assert_awaited_once_with(limit=5)

    @pytest.mark.asyncio
    async def test_repository_error_surfaces_in_error_field(self) -> None:
        repo = MagicMock(spec=StrategySpecRepository)
        repo.list_recent = AsyncMock(side_effect=RuntimeError("db down"))
        mcp = _build_server(repo)
        async with Client(mcp) as client:
            result = await client.call_tool("list_strategies", {})
        payload = _structured(result)
        assert payload["strategies"] == []
        assert payload["error"] is not None
        assert "RuntimeError" in payload["error"]
        assert "db down" in payload["error"]

    @pytest.mark.asyncio
    async def test_structured_content_populated(self) -> None:
        repo = _mock_repo(rows=[])
        mcp = _build_server(repo)
        async with Client(mcp) as client:
            result = await client.call_tool("list_strategies", {})
        sc = getattr(result, "structured_content", None)
        if sc is not None:
            assert "strategies" in sc
            assert "error" in sc
        else:
            parsed = json.loads(result.content[0].text)
            assert "strategies" in parsed
            assert "error" in parsed


# -------------------------- explain_strategy -------------------------------


class TestExplainStrategy:
    @pytest.mark.asyncio
    async def test_valid_payload_renders_markdown_with_name_side_indicator(self) -> None:
        mcp = _build_server()
        async with Client(mcp) as client:
            result = await client.call_tool("explain_strategy", {"spec": _valid_payload()})
        payload = _structured(result)
        assert payload["error"] is None
        md = payload["markdown"]
        assert md is not None
        assert "sma-cross" in md
        assert "LONG" in md
        assert "SMA(20, close)" in md

    @pytest.mark.asyncio
    async def test_valid_payload_has_entry_and_exit_sections(self) -> None:
        mcp = _build_server()
        async with Client(mcp) as client:
            result = await client.call_tool("explain_strategy", {"spec": _valid_payload()})
        payload = _structured(result)
        titles = {s["title"] for s in payload["sections"]}
        assert "Entry" in titles
        assert "Exit" in titles

    @pytest.mark.asyncio
    async def test_malformed_payload_returns_error_only(self) -> None:
        mcp = _build_server()
        bad = _valid_payload()
        del bad["name"]
        async with Client(mcp) as client:
            result = await client.call_tool("explain_strategy", {"spec": bad})
        payload = _structured(result)
        assert payload["error"] is not None
        assert payload["markdown"] is None
        assert payload["sections"] == []

    def test_coherence_rejects_error_with_markdown(self) -> None:
        with pytest.raises(ValidationError):
            ExplainStrategyResponse(markdown="stuff", error="boom")

    def test_coherence_rejects_success_without_markdown(self) -> None:
        with pytest.raises(ValidationError):
            ExplainStrategyResponse(markdown=None, error=None)

    @pytest.mark.asyncio
    async def test_markdown_includes_crosses_above_op(self) -> None:
        mcp = _build_server()
        async with Client(mcp) as client:
            result = await client.call_tool("explain_strategy", {"spec": _valid_payload()})
        payload = _structured(result)
        assert "crosses_above" in payload["markdown"]


# -------------------------- diff_strategies --------------------------------


class TestDiffStrategies:
    @pytest.mark.asyncio
    async def test_identical_specs_are_equal(self) -> None:
        mcp = _build_server()
        spec = _valid_payload()
        async with Client(mcp) as client:
            result = await client.call_tool("diff_strategies", {"a": spec, "b": deepcopy(spec)})
        payload = _structured(result)
        assert payload["equal"] is True
        assert payload["differences"] == []
        assert payload["errors"] == []

    @pytest.mark.asyncio
    async def test_differ_only_in_name_reports_one_diff(self) -> None:
        mcp = _build_server()
        a = _valid_payload()
        b = deepcopy(a)
        b["name"] = "renamed"
        async with Client(mcp) as client:
            result = await client.call_tool("diff_strategies", {"a": a, "b": b})
        payload = _structured(result)
        assert payload["equal"] is False
        name_diffs = [d for d in payload["differences"] if d["path"] == "/name"]
        assert len(name_diffs) == 1
        assert name_diffs[0]["left"] == "sma-cross"
        assert name_diffs[0]["right"] == "renamed"

    @pytest.mark.asyncio
    async def test_nested_condition_period_diff_path(self) -> None:
        mcp = _build_server()
        a = _valid_payload()
        b = deepcopy(a)
        b["entry"]["conditions"][0]["lhs"]["period"] = 25
        async with Client(mcp) as client:
            result = await client.call_tool("diff_strategies", {"a": a, "b": b})
        payload = _structured(result)
        assert payload["equal"] is False
        paths = [d["path"] for d in payload["differences"]]
        assert "/entry/conditions/0/lhs/period" in paths

    @pytest.mark.asyncio
    async def test_array_length_difference_reports_none_side(self) -> None:
        mcp = _build_server()
        a = _valid_payload()
        b = deepcopy(a)
        # add an extra entry condition on b
        b["entry"]["conditions"].append(
            {
                "lhs": {"kind": "rsi", "period": 14, "source": "close"},
                "op": "lt",
                "rhs": "30",
            }
        )
        async with Client(mcp) as client:
            result = await client.call_tool("diff_strategies", {"a": a, "b": b})
        payload = _structured(result)
        assert payload["equal"] is False
        # At least one diff must have left=None / right=not-None under /entry/conditions/1/...
        missing_on_a = [
            d
            for d in payload["differences"]
            if d["path"].startswith("/entry/conditions/1") and d["left"] is None
        ]
        assert missing_on_a, (
            f"expected at least one diff with left=None under /entry/conditions/1, "
            f"got {payload['differences']!r}"
        )

    @pytest.mark.asyncio
    async def test_different_size_pct_captured(self) -> None:
        mcp = _build_server()
        a = _valid_payload()
        b = deepcopy(a)
        b["size_pct"] = "0.5"
        async with Client(mcp) as client:
            result = await client.call_tool("diff_strategies", {"a": a, "b": b})
        payload = _structured(result)
        assert payload["equal"] is False
        size_diffs = [d for d in payload["differences"] if d["path"] == "/size_pct"]
        assert len(size_diffs) == 1

    @pytest.mark.asyncio
    async def test_malformed_a_returns_errors(self) -> None:
        mcp = _build_server()
        bad = _valid_payload()
        del bad["name"]
        good = _valid_payload()
        async with Client(mcp) as client:
            result = await client.call_tool("diff_strategies", {"a": bad, "b": good})
        payload = _structured(result)
        assert payload["errors"]
        assert payload["equal"] is False
        assert payload["differences"] == []

    @pytest.mark.asyncio
    async def test_malformed_b_returns_errors(self) -> None:
        mcp = _build_server()
        good = _valid_payload()
        bad = _valid_payload()
        del bad["name"]
        async with Client(mcp) as client:
            result = await client.call_tool("diff_strategies", {"a": good, "b": bad})
        payload = _structured(result)
        assert payload["errors"]
        assert payload["equal"] is False
        assert payload["differences"] == []

    @pytest.mark.asyncio
    async def test_both_malformed_returns_two_errors(self) -> None:
        mcp = _build_server()
        bad_a = _valid_payload()
        del bad_a["name"]
        bad_b = _valid_payload()
        del bad_b["venue"]
        async with Client(mcp) as client:
            result = await client.call_tool("diff_strategies", {"a": bad_a, "b": bad_b})
        payload = _structured(result)
        assert len(payload["errors"]) == 2

    def test_coherence_rejects_errors_plus_equal_true(self) -> None:
        with pytest.raises(ValidationError):
            DiffStrategiesResponse(equal=True, differences=[], errors=["bad"])

    def test_coherence_rejects_equal_true_with_differences(self) -> None:
        with pytest.raises(ValidationError):
            DiffStrategiesResponse(
                equal=True,
                differences=[FieldDiffDTO(path="/x", left=1, right=2)],
            )


class TestExplanationSectionDTO:
    def test_is_frozen(self) -> None:
        sec = ExplanationSectionDTO(title="Entry", body="text")
        with pytest.raises(ValidationError):
            sec.title = "Exit"  # type: ignore[misc]


class TestFieldDiffDTO:
    def test_accepts_heterogeneous_any_values(self) -> None:
        # left / right annotated as Any — must accept None, int, str, nested dicts
        d1 = FieldDiffDTO(path="/a", left=None, right="x")
        assert d1.left is None
        d2 = FieldDiffDTO(path="/b", left=1, right={"nested": [1, 2]})
        assert d2.right == {"nested": [1, 2]}
