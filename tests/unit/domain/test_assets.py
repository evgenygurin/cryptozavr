"""Test Asset + AssetCategory."""

from __future__ import annotations

import pytest

from cryptozavr.domain.assets import Asset, AssetCategory
from cryptozavr.domain.exceptions import ValidationError


class TestAssetCategory:
    def test_values(self) -> None:
        assert AssetCategory.LAYER_1.value == "layer_1"
        assert AssetCategory.DEFI.value == "defi"
        assert AssetCategory.MEME.value == "meme"
        assert AssetCategory.STABLECOIN.value == "stablecoin"


class TestAsset:
    def test_happy_path(self) -> None:
        a = Asset(code="BTC", name="Bitcoin", category=AssetCategory.LAYER_1)
        assert a.code == "BTC"
        assert a.name == "Bitcoin"
        assert a.category == AssetCategory.LAYER_1

    def test_minimal(self) -> None:
        a = Asset(code="BTC")
        assert a.code == "BTC"
        assert a.name is None
        assert a.category is None
        assert a.coingecko_id is None
        assert a.market_cap_rank is None

    def test_rejects_lowercase_code(self) -> None:
        with pytest.raises(ValidationError):
            Asset(code="btc")

    def test_rejects_empty_code(self) -> None:
        with pytest.raises(ValidationError):
            Asset(code="")

    def test_equality_by_code(self) -> None:
        a = Asset(code="BTC", name="Bitcoin")
        b = Asset(code="BTC", name=None)
        assert a == b
        assert hash(a) == hash(b)
