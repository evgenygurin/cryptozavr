"""Domain exception hierarchy for cryptozavr.

All exceptions derive from DomainError. Layer L3 throws these.
Layers L2/L4/L5 translate foreign exceptions (CCXT, Supabase) into these.
"""

from __future__ import annotations


class DomainError(Exception):
    """Root of all domain exceptions. Do not raise directly; use a subclass."""


# -- ValidationError ------------------------------------------------------
class ValidationError(DomainError):
    """Invalid value for a domain constraint (bad input, invariant broken)."""


# -- NotFoundError family -------------------------------------------------
class NotFoundError(DomainError):
    """Requested domain resource does not exist."""


class SymbolNotFoundError(NotFoundError):
    """Requested symbol does not exist on the given venue."""

    def __init__(self, user_input: str, venue: str) -> None:
        self.user_input = user_input
        self.venue = venue
        super().__init__(f"symbol {user_input!r} was not found on venue {venue!r}")


class VenueNotSupportedError(NotFoundError):
    """Requested venue is not registered / not supported."""

    def __init__(self, venue: str) -> None:
        self.venue = venue
        super().__init__(f"venue {venue!r} is not supported")


# -- ProviderError family -------------------------------------------------
class ProviderError(DomainError):
    """Provider-layer failures raised as domain exceptions."""


class ProviderUnavailableError(ProviderError):
    """Provider is unreachable (network, outage, rate-limited state)."""


class RateLimitExceededError(ProviderError):
    """Provider rejected the request due to rate limit."""


class AuthenticationError(ProviderError):
    """Provider rejected credentials (reserved for authed endpoints; phase 5+)."""


# -- QualityError family --------------------------------------------------
class QualityError(DomainError):
    """Data quality insufficient for the requested operation."""


class StaleDataError(QualityError):
    """Data is older than the acceptable staleness threshold."""


class IncompleteDataError(QualityError):
    """Partial/truncated response, cannot be used for the requested operation."""
