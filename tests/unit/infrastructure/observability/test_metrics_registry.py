"""MetricsRegistry: counters aggregation + cumulative histogram buckets."""

from __future__ import annotations

from cryptozavr.infrastructure.observability.metrics import MetricsRegistry


def test_counter_accumulates_per_label_set() -> None:
    reg = MetricsRegistry()
    reg.inc_counter("calls", labels={"venue": "kucoin", "outcome": "ok"})
    reg.inc_counter("calls", labels={"venue": "kucoin", "outcome": "ok"})
    reg.inc_counter("calls", labels={"venue": "kucoin", "outcome": "error"})

    snap = reg.snapshot()
    by_labels = {tuple(sorted(c["labels"].items())): c["value"] for c in snap["counters"]}
    assert by_labels[(("outcome", "ok"), ("venue", "kucoin"))] == 2
    assert by_labels[(("outcome", "error"), ("venue", "kucoin"))] == 1


def test_counter_distinct_labels_are_separate() -> None:
    reg = MetricsRegistry()
    reg.inc_counter("calls", labels={"venue": "kucoin"})
    reg.inc_counter("calls", labels={"venue": "coingecko"})
    snap = reg.snapshot()
    assert len(snap["counters"]) == 2


def test_histogram_buckets_are_cumulative() -> None:
    reg = MetricsRegistry()
    labels = {"venue": "kucoin", "endpoint": "fetch_ticker"}
    for value in (30.0, 80.0, 200.0, 3000.0):
        reg.observe_histogram("duration_ms", labels=labels, value=value)

    snap = reg.snapshot()
    hist = snap["histograms"][0]
    assert hist["count"] == 4
    assert hist["sum"] == 3310.0
    bucket_counts = {b["le"]: b["count"] for b in hist["buckets"]}
    assert bucket_counts[50.0] == 1  # 30
    assert bucket_counts[100.0] == 2  # 30, 80
    assert bucket_counts[250.0] == 3  # 30, 80, 200
    assert bucket_counts[2500.0] == 3
    assert bucket_counts["+Inf"] == 4


def test_histogram_zero_observations_absent() -> None:
    reg = MetricsRegistry()
    snap = reg.snapshot()
    assert snap["histograms"] == []


def test_snapshot_reflects_live_state() -> None:
    reg = MetricsRegistry()
    reg.inc_counter("calls", labels={"v": "a"})
    snap1 = reg.snapshot()
    reg.inc_counter("calls", labels={"v": "a"})
    snap2 = reg.snapshot()
    assert snap1["counters"][0]["value"] == 1
    assert snap2["counters"][0]["value"] == 2
