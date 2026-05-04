"""Tests for config loading."""

from __future__ import annotations

import pytest

from freepik_tryon_bot.config import load_config


def test_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("FREEPIK_API_KEYS", raising=False)
    monkeypatch.delenv("FREEPIK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        load_config(env_file=None)


def test_requires_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "abc")
    monkeypatch.delenv("FREEPIK_API_KEYS", raising=False)
    monkeypatch.delenv("FREEPIK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FREEPIK_API_KEYS"):
        load_config(env_file=None)


def test_parses_keys_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "abc")
    monkeypatch.setenv("FREEPIK_API_KEYS", "key1, key2 ,key3")
    monkeypatch.delenv("FREEPIK_API_KEY", raising=False)
    monkeypatch.setenv("ADMIN_USER_IDS", "1,2,3")
    cfg = load_config(env_file=None)
    assert cfg.api_keys == ("key1", "key2", "key3")
    assert cfg.admin_user_ids == frozenset({1, 2, 3})
    assert cfg.brand_footer == "By : Aksara Strategy"


def test_falls_back_to_single_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "abc")
    monkeypatch.delenv("FREEPIK_API_KEYS", raising=False)
    monkeypatch.setenv("FREEPIK_API_KEY", "single")
    cfg = load_config(env_file=None)
    assert cfg.api_keys == ("single",)
