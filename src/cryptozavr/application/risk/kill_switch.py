"""KillSwitch runtime singleton — thread-safe engage/disengage gate.

Not persisted in MVP; restart resets to disengaged. A later milestone will
persist the engage state so restarts do not silently resume trading.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KillSwitchStatus:
    engaged: bool
    engaged_at_ms: int | None
    reason: str | None


class KillSwitch:
    """Thread-safe runtime gate; all state access goes through a single lock."""

    def __init__(self) -> None:
        self._engaged = False
        self._engaged_at_ms: int | None = None
        self._reason: str | None = None
        self._lock = threading.Lock()

    def engage(self, *, reason: str) -> KillSwitchStatus:
        if not reason:
            raise ValueError("KillSwitch.engage: reason must be non-empty")
        with self._lock:
            self._engaged = True
            self._engaged_at_ms = int(time.time() * 1000)
            self._reason = reason
            return self._status_locked()

    def disengage(self) -> KillSwitchStatus:
        with self._lock:
            self._engaged = False
            self._engaged_at_ms = None
            self._reason = None
            return self._status_locked()

    def status(self) -> KillSwitchStatus:
        with self._lock:
            return self._status_locked()

    def is_engaged(self) -> bool:
        with self._lock:
            return self._engaged

    def _status_locked(self) -> KillSwitchStatus:
        return KillSwitchStatus(
            engaged=self._engaged,
            engaged_at_ms=self._engaged_at_ms,
            reason=self._reason,
        )
