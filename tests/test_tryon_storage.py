"""Tests for the tryon-bot SQLite storage layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from freepik_tryon_bot.storage import Storage


@pytest.fixture()
def storage(tmp_path: Path) -> Storage:
    s = Storage(tmp_path / "db.sqlite3")
    yield s
    s.close()


def test_upsert_user_creates_and_updates(storage: Storage) -> None:
    rec = storage.upsert_user(123, username="abc", full_name="A B")
    assert rec.user_id == 123
    assert rec.tokens == 0
    assert rec.is_admin is False
    rec = storage.upsert_user(123, is_admin=True, full_name="New Name")
    assert rec.is_admin is True
    assert rec.full_name == "New Name"
    assert rec.username == "abc"


def test_grant_tokens_creates_user(storage: Storage) -> None:
    new_balance = storage.grant_tokens(999, 50, actor_id=1)
    assert new_balance == 50
    record = storage.get_user(999)
    assert record is not None
    assert record.tokens == 50


def test_grant_negative_tokens(storage: Storage) -> None:
    storage.grant_tokens(1, 30, actor_id=1)
    after = storage.grant_tokens(1, -10, actor_id=1)
    assert after == 20


def test_consume_token_returns_none_if_empty(storage: Storage) -> None:
    storage.upsert_user(1)
    assert storage.consume_token(1) is None


def test_consume_token_decrements(storage: Storage) -> None:
    storage.grant_tokens(1, 3, actor_id=None)
    assert storage.consume_token(1) == 2
    assert storage.consume_token(1) == 1
    assert storage.consume_token(1) == 0
    assert storage.consume_token(1) is None


def test_has_admin(storage: Storage) -> None:
    assert storage.has_admin() is False
    storage.upsert_user(1)
    assert storage.has_admin() is False
    storage.upsert_user(2, is_admin=True)
    assert storage.has_admin() is True


def test_list_users_orders_admin_first(storage: Storage) -> None:
    storage.upsert_user(1)
    storage.upsert_user(2, is_admin=True)
    storage.upsert_user(3)
    users = storage.list_users()
    assert users[0].user_id == 2
    assert {u.user_id for u in users} == {1, 2, 3}


def test_get_balance(storage: Storage) -> None:
    assert storage.get_balance(42) == 0
    storage.grant_tokens(42, 7, actor_id=None)
    assert storage.get_balance(42) == 7
