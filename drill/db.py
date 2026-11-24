"""解答履歴と、型ごとの復習状態を利用者ごとに SQLite に保存する。"""

import json
import sqlite3
import threading
from collections import Counter
from datetime import datetime, timedelta

from . import scheduler
from .scheduler import TypeState

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    type_id TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    correct INTEGER NOT NULL,
    misconception_id TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS type_state (
    user_id TEXT NOT NULL,
    type_id TEXT NOT NULL,
    box INTEGER NOT NULL,
    due_at TEXT,
    attempts INTEGER NOT NULL,
    correct INTEGER NOT NULL,
    PRIMARY KEY (user_id, type_id)
);
CREATE INDEX IF NOT EXISTS attempts_user ON attempts (user_id, type_id);
CREATE TABLE IF NOT EXISTS placement (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL
);
"""

# 利用者を区別する前の DB の履歴は、この利用者のものとして引き継ぐ
LOCAL_USER = "local"

# 古い記録を消して、DB が増え続けないようにする（公開して訪問者が増えても、ディスクを使い切らないため）
# - レベル診断の途中経過: 結果は画面に返したあとは使わないので、始めてから1日で消す
# - 利用者の履歴: Cookie の有効期限（最後に使ってから400日）を過ぎたら、もう誰も見られないので消す
# - 1人あたりの解答の記録: 新しいものから一定の数だけ残す（成績の正答数は type_state にあるので消えない）
PLACEMENT_TTL = timedelta(days=1)
USER_TTL = timedelta(days=400)
MAX_ATTEMPTS_PER_USER = 5000
CLEANUP_INTERVAL = timedelta(hours=1)


def _migrate(conn: sqlite3.Connection) -> None:
    """user_id の列がない古い DB に列を足し、既存の行を LOCAL_USER のものにする。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(attempts)")}
    if not cols or "user_id" in cols:
        return
    conn.executescript(f"""
        ALTER TABLE attempts ADD COLUMN user_id TEXT NOT NULL DEFAULT '{LOCAL_USER}';
        ALTER TABLE type_state RENAME TO type_state_old;
    """)
    conn.executescript(_SCHEMA)
    conn.executescript(f"""
        INSERT INTO type_state (user_id, type_id, box, due_at, attempts, correct)
            SELECT '{LOCAL_USER}', type_id, box, due_at, attempts, correct FROM type_state_old;
        DROP TABLE type_state_old;
    """)


class Store:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # FastAPI の同期エンドポイントは複数スレッドから呼ばれるため直列化する
        self._lock = threading.Lock()
        self._last_cleanup: datetime | None = None
        with self._lock, self._conn:
            _migrate(self._conn)
            self._conn.executescript(_SCHEMA)

    def states(self, user_id: str, type_ids: list[str]) -> list[TypeState]:
        """利用者の、指定した型の状態を返す。記録のない型は未学習の状態になる。"""
        with self._lock:
            rows = {
                r["type_id"]: r
                for r in self._conn.execute("SELECT * FROM type_state WHERE user_id = ?", (user_id,))
            }
        result = []
        for tid in type_ids:
            r = rows.get(tid)
            if r is None:
                result.append(TypeState(tid))
            else:
                due = datetime.fromisoformat(r["due_at"]) if r["due_at"] else None
                result.append(TypeState(tid, r["box"], due, r["attempts"], r["correct"]))
        return result

    def record(
        self,
        user_id: str,
        problem_id: str,
        type_id: str,
        answer_text: str,
        correct: bool,
        misconception_id: str | None,
        now: datetime,
    ) -> TypeState:
        [state] = self.states(user_id, [type_id])
        new = scheduler.update(state, correct, now)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO attempts (user_id, problem_id, type_id, answer_text, correct, misconception_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, problem_id, type_id, answer_text, int(correct), misconception_id, now.isoformat()),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO type_state (user_id, type_id, box, due_at, attempts, correct)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, type_id, new.box, new.due_at.isoformat(), new.attempts, new.correct),
            )
            self._conn.execute(
                "DELETE FROM attempts WHERE user_id = ? AND id <= ("
                " SELECT id FROM attempts WHERE user_id = ? ORDER BY id DESC LIMIT 1 OFFSET ?)",
                (user_id, user_id, MAX_ATTEMPTS_PER_USER),
            )
        return new

    def cleanup(self, now: datetime) -> None:
        """期限を過ぎた記録を消す（上の PLACEMENT_TTL・USER_TTL）。"""
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM placement WHERE created_at < ?", ((now - PLACEMENT_TTL).isoformat(),))
            stale = (
                "SELECT user_id FROM attempts WHERE user_id != ? GROUP BY user_id HAVING MAX(created_at) < ?"
            )
            args = (LOCAL_USER, (now - USER_TTL).isoformat())
            self._conn.execute(f"DELETE FROM type_state WHERE user_id IN ({stale})", args)
            self._conn.execute(f"DELETE FROM attempts WHERE user_id IN ({stale})", args)
        self._last_cleanup = now

    def maybe_cleanup(self, now: datetime) -> None:
        """前の掃除から CLEANUP_INTERVAL 経っていれば掃除する。"""
        if self._last_cleanup is None or now - self._last_cleanup >= CLEANUP_INTERVAL:
            self.cleanup(now)

    def misconception_counts(self, user_id: str) -> dict[str, Counter]:
        """利用者の、型ごとの診断された誤答ルールの回数。"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT type_id, misconception_id FROM attempts WHERE user_id = ? AND correct = 0", (user_id,)
            ).fetchall()
        counts: dict[str, Counter] = {}
        for r in rows:
            counts.setdefault(r["type_id"], Counter())[r["misconception_id"]] += 1
        return counts

    def save_placement(self, session_id: str, user_id: str, data: dict, now: datetime) -> None:
        """レベル診断の途中経過（出題中の問題と、これまでの回答）を保存する。"""
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO placement (session_id, user_id, created_at, data) VALUES (?, ?, ?, ?)"
                " ON CONFLICT (session_id) DO UPDATE SET data = excluded.data",
                (session_id, user_id, now.isoformat(), json.dumps(data, ensure_ascii=False)),
            )

    def placement(self, session_id: str, user_id: str) -> dict | None:
        """利用者のレベル診断の途中経過。ほかの利用者のものや、ないものは None。"""
        with self._lock:
            r = self._conn.execute(
                "SELECT data FROM placement WHERE session_id = ? AND user_id = ?", (session_id, user_id)
            ).fetchone()
        return json.loads(r["data"]) if r else None
