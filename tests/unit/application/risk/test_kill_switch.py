"""KillSwitch runtime singleton: engage / disengage / status / thread safety."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from cryptozavr.application.risk.kill_switch import KillSwitch, KillSwitchStatus


def test_new_killswitch_is_disengaged() -> None:
    ks = KillSwitch()
    assert ks.is_engaged() is False
    status = ks.status()
    assert status.engaged is False
    assert status.engaged_at_ms is None
    assert status.reason is None


def test_engage_flips_state_and_sets_reason_and_timestamp() -> None:
    ks = KillSwitch()
    before_ms = int(time.time() * 1000)
    status = ks.engage(reason="manual halt")
    after_ms = int(time.time() * 1000)
    assert isinstance(status, KillSwitchStatus)
    assert status.engaged is True
    assert status.reason == "manual halt"
    assert status.engaged_at_ms is not None
    assert before_ms <= status.engaged_at_ms <= after_ms
    # State persists through new reads.
    assert ks.is_engaged() is True
    assert ks.status().reason == "manual halt"


def test_engage_empty_reason_raises_value_error() -> None:
    ks = KillSwitch()
    with pytest.raises(ValueError, match="reason must be non-empty"):
        ks.engage(reason="")
    # State untouched after failed engage.
    assert ks.is_engaged() is False


def test_disengage_resets_state() -> None:
    ks = KillSwitch()
    ks.engage(reason="halt")
    status = ks.disengage()
    assert status.engaged is False
    assert status.engaged_at_ms is None
    assert status.reason is None
    assert ks.is_engaged() is False


def test_engage_called_twice_overwrites_reason_and_timestamp() -> None:
    ks = KillSwitch()
    ks.engage(reason="first")
    first_ts = ks.status().engaged_at_ms
    assert first_ts is not None
    # Sleep a moment so the timestamp materially advances.
    time.sleep(0.002)
    ks.engage(reason="second")
    second = ks.status()
    assert second.reason == "second"
    assert second.engaged_at_ms is not None
    assert second.engaged_at_ms >= first_ts


def test_thread_safety_smoke_concurrent_engage_and_disengage() -> None:
    ks = KillSwitch()

    def worker(idx: int) -> None:
        if idx % 2 == 0:
            ks.engage(reason=f"t{idx}")
        else:
            ks.disengage()

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(worker, range(50)))

    # Final state must be internally consistent regardless of interleaving.
    final = ks.status()
    assert final.engaged in (True, False)
    if final.engaged:
        assert final.reason is not None
        assert final.reason != ""
        assert final.engaged_at_ms is not None
    else:
        assert final.reason is None
        assert final.engaged_at_ms is None
