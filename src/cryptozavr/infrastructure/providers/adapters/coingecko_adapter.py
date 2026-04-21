"""CoinGeckoAdapter: raw JSON → Domain entities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from cryptozavr.domain.assets import Asset
from cryptozavr.domain.market_data import Ticker
from cryptozavr.domain.quality import Confidence, DataQuality, Provenance, Staleness
from cryptozavr.domain.symbols import Symbol
from cryptozavr.domain.value_objects import Instant, Percentage


class CoinGeckoAdapter:
    """Static conversions from CoinGecko REST JSON to Domain entities."""

    @staticmethod
    def simple_price_to_ticker(
        raw: Mapping[str, Any],
        *,
        coin_id: str,
        vs_currency: str,
        symbol: Symbol,
    ) -> Ticker:
        """Map /simple/price response to Domain Ticker."""
        entry = raw[coin_id]
        last = Decimal(str(entry[vs_currency]))
        volume_24h_key = f"{vs_currency}_24h_vol"
        change_24h_key = f"{vs_currency}_24h_change"
        volume_24h = Decimal(str(entry[volume_24h_key])) if volume_24h_key in entry else None
        change_pct = (
            Percentage(value=Decimal(str(entry[change_24h_key])))
            if change_24h_key in entry
            else None
        )
        ts = int(entry.get("last_updated_at", 0))
        observed_at = Instant.from_ms(ts * 1000) if ts else Instant.now()
        return Ticker(
            symbol=symbol,
            last=last,
            observed_at=observed_at,
            quality=_fresh_quality(endpoint="simple_price"),
            volume_24h=volume_24h,
            change_24h_pct=change_pct,
        )

    @staticmethod
    def trending_to_assets(raw: Mapping[str, Any]) -> list[Asset]:
        """Map /search/trending response to list of Assets."""
        coins = raw.get("coins", [])
        return [
            Asset(
                code=coin["item"]["symbol"].upper(),
                name=coin["item"].get("name"),
                coingecko_id=coin["item"].get("id"),
                market_cap_rank=coin["item"].get("market_cap_rank"),
            )
            for coin in coins
        ]

    @staticmethod
    def categories_to_list(
        raw: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        """Map /coins/categories response to plain list of dicts."""
        return [dict(c) for c in raw]


def _fresh_quality(*, endpoint: str) -> DataQuality:
    return DataQuality(
        source=Provenance(venue_id="coingecko", endpoint=endpoint),
        fetched_at=Instant.now(),
        staleness=Staleness.FRESH,
        confidence=Confidence.HIGH,
        cache_hit=False,
    )
