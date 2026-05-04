"""Tests for the API key rotation pool."""

from __future__ import annotations

import time

import pytest

from freepik_tryon_bot.apikey_pool import APIKeyPool


def test_lease_round_robin() -> None:
    pool = APIKeyPool(["a", "b", "c"])
    assert pool.lease() == "a"
    assert pool.lease() == "b"
    assert pool.lease() == "c"
    assert pool.lease() == "a"


def test_permanent_disable_skips_key() -> None:
    pool = APIKeyPool(["a", "b"])
    assert pool.lease() == "a"
    pool.report_failure("a", permanent=True)
    # Subsequent leases should never return 'a'
    leases = {pool.lease() for _ in range(5)}
    assert "a" not in leases
    assert leases == {"b"}


def test_cooldown_temporarily_skips_key() -> None:
    pool = APIKeyPool(["a", "b"])
    pool.report_failure("a", cooldown_seconds=0.05)
    assert pool.lease() == "b"  # 'a' is on cooldown
    assert pool.lease() == "b"  # still cooling
    time.sleep(0.06)
    # After cooldown, 'a' becomes available again
    leased = {pool.lease() for _ in range(4)}
    assert "a" in leased


def test_returns_none_when_all_disabled() -> None:
    pool = APIKeyPool(["a", "b"])
    pool.report_failure("a", permanent=True)
    pool.report_failure("b", permanent=True)
    assert pool.lease() is None


def test_report_success_clears_failures() -> None:
    pool = APIKeyPool(["a"])
    pool.report_failure("a", cooldown_seconds=60.0)
    assert pool.lease() is None
    pool.report_success("a")
    assert pool.lease() == "a"


def test_status_includes_fingerprint() -> None:
    pool = APIKeyPool(["FPSXabcdefghijklmnop"])
    [s] = pool.status()
    assert "FPSX" in str(s["fingerprint"])
    assert s["available"] is True


def test_constructor_rejects_empty() -> None:
    with pytest.raises(ValueError):
        APIKeyPool([])
