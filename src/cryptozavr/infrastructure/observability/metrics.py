"""In-memory Prometheus-compatible metrics registry (counters + histograms)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

_DEFAULT_BUCKETS: tuple[float, ...] = (
    50.0,
    100.0,
    250.0,
    500.0,
    1000.0,
    2500.0,
    5000.0,
    float("inf"),
)


@dataclass
class _HistogramStats:
    """Cumulative-bucket histogram state; Prometheus "le" semantics."""

    buckets: tuple[float, ...]
    counts: list[int] = field(default_factory=list)
    sum: float = 0.0

    def __post_init__(self) -> None:
        if not self.buckets:
            raise ValueError("histogram buckets must not be empty")
        if list(self.buckets) != sorted(self.buckets):
            raise ValueError(f"histogram buckets must be sorted ascending, got {self.buckets!r}")
        if self.buckets[-1] != float("inf"):
            raise ValueError(f"histogram last bucket must be +inf, got {self.buckets[-1]!r}")
        if not self.counts:
            self.counts = [0] * len(self.buckets)

    def observe(self, value: float) -> None:
        self.sum += value
        for idx, bound in enumerate(self.buckets):
            if value <= bound:
                self.counts[idx] += 1

    @property
    def count(self) -> int:
        return self.counts[-1] if self.counts else 0


def _labels_key(labels: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(labels.items()))


def _format_le(bound: float) -> str | float:
    return "+Inf" if bound == float("inf") else bound


class MetricsRegistry:
    """Thread-safe in-memory registry for Prometheus-compatible metrics.

    Counters: `{name, labels} -> int`.
    Histograms: `{name, labels} -> HistogramStats` with cumulative bucket counts.
    `snapshot()` returns a serializable dict suitable for text-format export.
    """

    def __init__(self, *, buckets: tuple[float, ...] = _DEFAULT_BUCKETS) -> None:
        if not buckets:
            raise ValueError("histogram buckets must not be empty")
        if list(buckets) != sorted(buckets):
            raise ValueError(f"histogram buckets must be sorted ascending, got {buckets!r}")
        if buckets[-1] != float("inf"):
            raise ValueError(f"histogram last bucket must be +inf, got {buckets[-1]!r}")
        self._buckets = buckets
        self._counters: dict[str, dict[tuple[tuple[str, str], ...], int]] = {}
        self._histograms: dict[str, dict[tuple[tuple[str, str], ...], _HistogramStats]] = {}
        self._lock = Lock()

    def inc_counter(self, name: str, *, labels: Mapping[str, str]) -> None:
        key = _labels_key(labels)
        with self._lock:
            bucket = self._counters.setdefault(name, {})
            bucket[key] = bucket.get(key, 0) + 1

    def observe_histogram(
        self,
        name: str,
        *,
        labels: Mapping[str, str],
        value: float,
    ) -> None:
        key = _labels_key(labels)
        with self._lock:
            entries = self._histograms.setdefault(name, {})
            stats = entries.get(key)
            if stats is None:
                stats = _HistogramStats(buckets=self._buckets)
                entries[key] = stats
            stats.observe(value)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = [
                {
                    "name": name,
                    "labels": dict(key),
                    "value": count,
                }
                for name, entries in self._counters.items()
                for key, count in entries.items()
            ]
            histograms = [
                {
                    "name": name,
                    "labels": dict(key),
                    "buckets": [
                        {"le": _format_le(bound), "count": cnt}
                        for bound, cnt in zip(stats.buckets, stats.counts, strict=True)
                    ],
                    "count": stats.count,
                    "sum": stats.sum,
                }
                for name, entries in self._histograms.items()
                for key, stats in entries.items()
            ]
        return {"counters": counters, "histograms": histograms}
