"""Asset entity: BTC, ETH, USDT, ... with optional metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from cryptozavr.domain.exceptions import ValidationError


class AssetCategory(StrEnum):
    LAYER_1 = "layer_1"
    LAYER_2 = "layer_2"
    DEFI = "defi"
    MEME = "meme"
    STABLECOIN = "stablecoin"
    NFT = "nft"
    GAMING = "gaming"
    AI = "ai"
    OTHER = "other"


@dataclass(frozen=True, slots=True, eq=False)
class Asset:
    """Crypto asset. Equality and hash based on `code` only.

    Two Assets with the same code are considered equal even if metadata differs.
    Metadata is enriched over time; identity is the code.
    """

    code: str
    name: str | None = None
    category: AssetCategory | None = None
    market_cap_rank: int | None = None
    coingecko_id: str | None = None
    categories: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.code:
            raise ValidationError("Asset.code must not be empty")
        if not self.code.isupper() or not self.code.replace("_", "").isalnum():
            raise ValidationError(f"Asset.code must be uppercase alphanumeric (got {self.code!r})")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Asset):
            return NotImplemented
        return self.code == other.code

    def __hash__(self) -> int:
        return hash(self.code)
