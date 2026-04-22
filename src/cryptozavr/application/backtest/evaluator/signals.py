"""SignalTick: per-bar entry/exit signal output from StrategyEvaluator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SignalTick:
    bar_index: int
    entry_signal: bool | None
    exit_signal: bool | None
