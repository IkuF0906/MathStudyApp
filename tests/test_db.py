from datetime import datetime, timedelta

from drill import db
from drill.db import LOCAL_USER, PLACEMENT_TTL, USER_TTL, Store

NOW = datetime(2026, 10, 5, 12, 0)
ALICE = "a" * 32
BOB = "b" * 32


def _count(store: Store, sql: str, *args) -> int:
    return store._conn.execute(sql, args).fetchone()[0]


def _record(store: Store, user: str, when: datetime) -> None:
    store.record(user, "power-0", "power", "0", False, None, when)


def test_old_placement_sessions_are_removed(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    store.save_placement("old", ALICE, {"responses": []}, NOW - PLACEMENT_TTL - timedelta(minutes=1))
    store.save_placement("new", ALICE, {"responses": []}, NOW - timedelta(hours=1))
    store.cleanup(NOW)
    assert store.placement("old", ALICE) is None
    assert store.placement("new", ALICE) is not None


def test_inactive_users_are_removed(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    old = NOW - USER_TTL - timedelta(days=1)
    _record(store, ALICE, old)  # 最後に使ってから期限を過ぎた
    _record(store, BOB, old)
    _record(store, BOB, NOW - timedelta(days=3))  # 昔から使っていても、最近使っていれば残す
    _record(store, LOCAL_USER, old)  # 手元で1人で使うときの履歴は消さない
    store.cleanup(NOW)
    for user, left in [(ALICE, 0), (BOB, 2), (LOCAL_USER, 1)]:
        assert _count(store, "SELECT COUNT(*) FROM attempts WHERE user_id = ?", user) == left
        assert _count(store, "SELECT COUNT(*) FROM type_state WHERE user_id = ?", user) == min(left, 1)


def test_attempts_per_user_are_capped(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "MAX_ATTEMPTS_PER_USER", 3)
    store = Store(str(tmp_path / "t.db"))
    for i in range(5):
        _record(store, ALICE, NOW + timedelta(minutes=i))
    _record(store, BOB, NOW)
    rows = store._conn.execute("SELECT created_at FROM attempts WHERE user_id = ? ORDER BY id", (ALICE,)).fetchall()
    assert [r[0] for r in rows] == [(NOW + timedelta(minutes=i)).isoformat() for i in (2, 3, 4)]
    assert _count(store, "SELECT COUNT(*) FROM attempts WHERE user_id = ?", BOB) == 1
    # 成績の正答数（type_state）は、消した解答の分も数えたまま
    [state] = store.states(ALICE, ["power"])
    assert state.attempts == 5


def test_cleanup_runs_at_most_hourly(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    store.maybe_cleanup(NOW)
    store.save_placement("s", ALICE, {"responses": []}, NOW - PLACEMENT_TTL - timedelta(minutes=1))
    store.maybe_cleanup(NOW + timedelta(minutes=30))
    assert store.placement("s", ALICE) is not None
    store.maybe_cleanup(NOW + timedelta(hours=1))
    assert store.placement("s", ALICE) is None
