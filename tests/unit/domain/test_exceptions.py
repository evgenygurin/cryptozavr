"""Test domain exception hierarchy."""

from __future__ import annotations

import pytest

from cryptozavr.domain.exceptions import (
    AuthenticationError,
    DomainError,
    IncompleteDataError,
    NotFoundError,
    ProviderError,
    ProviderUnavailableError,
    QualityError,
    RateLimitExceededError,
    StaleDataError,
    SymbolNotFoundError,
    ValidationError,
    VenueNotSupportedError,
)


class TestHierarchy:
    """Every domain exception must derive from DomainError."""

    @pytest.mark.parametrize(
        "exc",
        [
            ValidationError,
            NotFoundError,
            SymbolNotFoundError,
            VenueNotSupportedError,
            ProviderError,
            ProviderUnavailableError,
            RateLimitExceededError,
            AuthenticationError,
            QualityError,
            StaleDataError,
            IncompleteDataError,
        ],
    )
    def test_all_domain_exceptions_descend_from_DomainError(self, exc: type) -> None:
        assert issubclass(exc, DomainError)

    def test_SymbolNotFoundError_is_NotFoundError(self) -> None:
        assert issubclass(SymbolNotFoundError, NotFoundError)

    def test_VenueNotSupportedError_is_NotFoundError(self) -> None:
        assert issubclass(VenueNotSupportedError, NotFoundError)

    def test_ProviderUnavailableError_is_ProviderError(self) -> None:
        assert issubclass(ProviderUnavailableError, ProviderError)

    def test_RateLimitExceededError_is_ProviderError(self) -> None:
        assert issubclass(RateLimitExceededError, ProviderError)

    def test_AuthenticationError_is_ProviderError(self) -> None:
        assert issubclass(AuthenticationError, ProviderError)

    def test_StaleDataError_is_QualityError(self) -> None:
        assert issubclass(StaleDataError, QualityError)

    def test_IncompleteDataError_is_QualityError(self) -> None:
        assert issubclass(IncompleteDataError, QualityError)


class TestInstantiation:
    """All exceptions must accept a message string and carry it."""

    def test_DomainError_accepts_message(self) -> None:
        exc = DomainError("something broke")
        assert str(exc) == "something broke"

    def test_SymbolNotFoundError_has_symbol_and_venue(self) -> None:
        exc = SymbolNotFoundError(user_input="BTC/XYZ", venue="kucoin")
        assert exc.user_input == "BTC/XYZ"
        assert exc.venue == "kucoin"
        assert "BTC/XYZ" in str(exc)
        assert "kucoin" in str(exc)

    def test_VenueNotSupportedError_has_venue(self) -> None:
        exc = VenueNotSupportedError(venue="some-exchange")
        assert exc.venue == "some-exchange"
        assert "some-exchange" in str(exc)
