import sqlite3
from datetime import datetime, timedelta

import pytest
import sympy as sp
from fastapi.testclient import TestClient

from drill.api import MAX_ANSWER_LENGTH, create_app
from drill.sandbox import Sandbox

NOW = datetime(2026, 10, 5, 12, 0)


@pytest.fixture
def clock():
    return {"now": NOW}


@pytest.fixture(scope="module")
def sandbox():
    # ワーカーの起動には SymPy の読み込みで数秒かかるので、このファイルのテストで共有する
    sb = Sandbox(workers=1)
    yield sb
    sb.close()


@pytest.fixture
def client(tmp_path, clock, sandbox):
    return TestClient(create_app(str(tmp_path / "test.db"), now=lambda: clock["now"], sandbox=sandbox))


def answer(client, problem_id, text):
    return client.post("/api/answer", json={"problem_id": problem_id, "answer": text})


def test_index_is_served(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "学力診断テスト" in res.text


def test_problem_for_type(client):
    res = client.get("/api/problem", params={"type": "chain"})
    assert res.status_code == 200
    body = res.json()
    assert body["type_id"] == "chain"
    assert body["problem_id"].startswith("chain-")


def test_unknown_type_is_404(client):
    assert client.get("/api/problem", params={"type": "nope"}).status_code == 404


def test_correct_answer(client):
    res = answer(client, "power-0", "-15x^4 + 15x^2")
    body = res.json()
    assert body["correct"] is True
    assert body["misconception"] is None
    assert body["next_due"] == (NOW + timedelta(days=1)).isoformat()


def test_wrong_answer_is_diagnosed(client):
    # power-0 は -3x^5 + 5x^3 + 9。指数を前に出し忘れると -3x^4 + 5x^2
    body = answer(client, "power-0", "-3x^4 + 5x^2").json()
    assert body["correct"] is False
    assert body["misconception"]["id"] == "power_no_coeff"
    assert body["next_due"] == NOW.isoformat()


def test_parse_error_is_400(client):
    res = answer(client, "power-0", "(x+")
    assert res.status_code == 400
    assert res.json()["detail"]


def test_unknown_problem_is_404(client):
    assert answer(client, "nope-1", "x").status_code == 404


def test_review_picks_failed_type_first(client, clock):
    answer(client, "power-0", "-15x^4 + 15x^2")  # 正解 → 1日後
    answer(client, "trig-0", "0")  # 不正解 → すぐ
    clock["now"] = NOW + timedelta(minutes=1)
    assert client.get("/api/review").json()["type_id"] == "trig"


def test_stats(client):
    answer(client, "power-0", "-3x^4 + 5x^2")
    answer(client, "power-1", "1")
    answer(client, "power-2", "12x^3 + 10x")
    power = next(s for s in client.get("/api/stats").json() if s["type_id"] == "power")
    assert (power["attempts"], power["correct"]) == (3, 1)
    labels = {m["label"] for m in power["mistakes"]}
    assert "未分類の誤り" in labels
    assert any("前に出し忘れ" in label for label in labels)


def test_units_and_types(client):
    units = [u["id"] for u in client.get("/api/units").json()]
    assert units == [
        "calc", "equation", "function", "trig", "probability", "sequence",
        "derivative", "integral", "definite", "limit", "application",
    ]  # fmt: skip
    types = client.get("/api/types", params={"unit": "limit"}).json()
    assert types and all(t["unit"] == "limit" for t in types)
    assert client.get("/api/types", params={"unit": "nope"}).status_code == 404


def test_problem_for_unit(client):
    for _ in range(5):
        body = client.get("/api/problem", params={"unit": "definite"}).json()
        assert body["unit_id"] == "definite"
        assert body["prompt"] and body["answer_prefix"]


def test_review_within_unit(client, clock):
    answer(client, "power-0", "0")  # 微分で不正解 → すぐ復習
    clock["now"] = NOW + timedelta(minutes=1)
    assert client.get("/api/review").json()["type_id"] == "power"
    assert client.get("/api/review", params={"unit": "integral"}).json()["unit_id"] == "integral"


def test_integral_answer_with_note(client):
    body = answer(client, "int_power-0", "x^6/2 + 4x^5/5 + 9x").json()
    assert body["correct"] is True
    assert "C" in body["note"]
    assert body["answer_latex"].endswith("+ C")


def test_sequence_answer_in_n(client):
    # seq_recur-1 は a_1 = 2, a_{n+1} = 2a_n + 3。一般項は 5・2^{n-1} - 3
    problem = client.get("/api/problem", params={"type": "seq_recur"}).json()
    assert problem["variable"] == "n"
    assert answer(client, "seq_recur-1", "5*2^(n-1) - 3").json()["correct"] is True
    body = answer(client, "seq_recur-1", "5*2^n - 3").json()
    assert body["misconception"]["id"] == "seq_recur_power_n"


def test_wrong_variable_is_400(client):
    res = answer(client, "seq_recur-1", "5*2^(x-1) - 3")
    assert res.status_code == 400
    assert "n の式" in res.json()["detail"]
    assert answer(client, "power-0", "-15n^4 + 15n^2").status_code == 400
    assert answer(client, "dint_poly-0", "3 + C").status_code == 400


def test_word_problem_has_no_formula(client):
    body = client.get("/api/problem", params={"type": "prob_draw"}).json()
    assert body["latex"] == ""
    assert "袋の中に" in body["prompt"]
    assert body["variable"] == "x"


def test_stats_has_unit(client):
    s = next(s for s in client.get("/api/stats").json() if s["type_id"] == "lim_e")
    assert (s["unit_id"], s["unit_name"]) == ("limit", "極限")


def test_preview(client):
    assert client.get("/api/preview", params={"text": "2xsin(x)"}).json()["latex"] == r"2 x \sin{\left(x \right)}"
    assert client.get("/api/preview", params={"text": "(x+"}).status_code == 400


def _power_attempts(client):
    power = next(s for s in client.get("/api/stats").json() if s["type_id"] == "power")
    return power["attempts"]


def test_users_are_separated_by_cookie(client):
    answer(client, "power-0", "0")
    uid = client.cookies.get("drill_uid")
    assert uid and len(uid) == 32
    other = TestClient(client.app)
    assert _power_attempts(other) == 0
    assert other.cookies.get("drill_uid") != uid
    assert _power_attempts(client) == 1


def test_invalid_cookie_gets_new_id(client):
    res = client.get("/api/stats", headers={"Cookie": "drill_uid=abc"})
    assert len(res.cookies.get("drill_uid")) == 32


def test_old_db_is_migrated_to_local_user(tmp_path, sandbox):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, problem_id TEXT NOT NULL,
            type_id TEXT NOT NULL, answer_text TEXT NOT NULL, correct INTEGER NOT NULL,
            misconception_id TEXT, created_at TEXT NOT NULL);
        CREATE TABLE type_state (type_id TEXT PRIMARY KEY, box INTEGER NOT NULL, due_at TEXT,
            attempts INTEGER NOT NULL, correct INTEGER NOT NULL);
        INSERT INTO attempts VALUES (1, 'power-0', 'power', '0', 0, NULL, '2026-10-01T12:00:00');
        INSERT INTO type_state VALUES ('power', 0, '2026-10-01T12:00:00', 1, 0);
    """)
    conn.commit()
    conn.close()

    local = TestClient(create_app(str(path), now=lambda: NOW, adopt_local=True, sandbox=sandbox))
    assert _power_attempts(local) == 1
    assert local.cookies.get("drill_uid") == "local"
    # Cookie が付いた後は、引き継ぎの設定なしで起動しても同じ履歴が見える
    later = TestClient(create_app(str(path), now=lambda: NOW, sandbox=sandbox))
    later.cookies.set("drill_uid", "local")
    answer(later, "power-1", "0")
    assert _power_attempts(later) == 2
    assert _power_attempts(TestClient(later.app)) == 0


def test_cookie_is_renewed_on_each_use(client):
    # 有効期限を「最後に使ってから」数えるため、Cookie を持っていても付け直す
    client.get("/api/stats")
    uid = client.cookies.get("drill_uid")
    res = client.get("/api/stats")
    assert res.cookies.get("drill_uid") == uid
    assert "max-age=34560000" in res.headers["set-cookie"].lower()


def test_cookie_is_secure_only_over_https(client):
    assert "secure" not in client.get("/api/stats").headers["set-cookie"].lower()
    https = TestClient(client.app, base_url="https://testserver")
    assert "secure" in https.get("/api/stats").headers["set-cookie"].lower()


def test_version(client):
    assert client.get("/api/version").json() == {"version": "dev"}


def test_too_long_answer_is_400(client):
    res = answer(client, "power-0", "x+" * MAX_ANSWER_LENGTH)
    assert res.status_code == 400
    assert "長すぎ" in res.json()["detail"]


def test_heavy_answer_times_out_and_worker_recovers(tmp_path):
    # 計算が終わらない解答でも、時間の上限で打ち切り、次の解答は普通に答え合わせできる
    sb = Sandbox(workers=1, timeout=1)
    try:
        client = TestClient(create_app(str(tmp_path / "t.db"), now=lambda: NOW, sandbox=sb))
        res = answer(client, "power-0", "(x+1)^100000")
        assert res.status_code == 400
        assert "計算が終わりません" in res.json()["detail"]
        assert answer(client, "power-0", "-15x^4 + 15x^2").json()["correct"] is True
    finally:
        sb.close()


# --- レベル診断 ---


def placement_answer(client, session_id, problem_id, text="", skip=False):
    return client.post(
        "/api/placement/answer",
        json={"session_id": session_id, "problem_id": problem_id, "answer": text, "skip": skip},
    )


def test_placement_runs_to_the_end(client):
    start = client.post("/api/placement/start", json={}).json()
    sid, problem = start["session_id"], start["problem"]
    assert start["total"] == 20 and problem["index"] == 1
    seen = []
    for i in range(1, 21):
        seen.append(problem["type_id"])
        body = placement_answer(client, sid, problem["problem_id"], skip=True).json()
        assert body["correct"] is False and body["index"] == i
        if i < 20:
            assert body["result"] is None
            problem = body["next"]
            assert problem["index"] == i + 1
    assert body["next"] is None
    assert len(set(seen)) == 20
    result = body["result"]
    assert result["answered"] == 20 and result["correct"] == 0
    assert result["label"] == "中学1年未満"
    # 診断で解いた問題は、復習の履歴にも残る
    attempts = sum(s["attempts"] for s in client.get("/api/stats").json())
    assert attempts == 20


def test_placement_grades_with_checker(client):
    start = client.post("/api/placement/start", json={}).json()
    from drill.templates import from_id

    from drill.placement import START_LEVEL

    p = from_id(start["problem"]["problem_id"])
    items = p.answer.args if isinstance(p.answer, (sp.Tuple, sp.FiniteSet)) else [p.answer]
    text = ", ".join(str(e).replace("**", "^") for e in items)
    body = placement_answer(client, start["session_id"], p.problem_id, text).json()
    assert body["correct"] is True
    assert body["theta"] > START_LEVEL  # 最初は START_LEVEL の問題。正解すると推定が上がる
    assert body["next"]["index"] == 2


def test_placement_rejects_stale_or_foreign_answers(client):
    start = client.post("/api/placement/start", json={}).json()
    sid, pid = start["session_id"], start["problem"]["problem_id"]
    assert placement_answer(client, sid, "power-0", skip=True).status_code == 409
    assert placement_answer(client, "nope", pid, skip=True).status_code == 404
    assert placement_answer(client, sid, pid, skip=True).status_code == 200
    assert placement_answer(client, sid, pid, skip=True).status_code == 409  # 同じ問題に2回は答えられない
    # 別の利用者（Cookie なし）からは見えない
    client.cookies.clear()
    assert placement_answer(client, sid, pid, skip=True).status_code == 404


def test_placement_parse_error_keeps_problem(client):
    start = client.post("/api/placement/start", json={}).json()
    sid, pid = start["session_id"], start["problem"]["problem_id"]
    assert placement_answer(client, sid, pid, "(x+").status_code == 400
    assert placement_answer(client, sid, pid, skip=True).status_code == 200


def test_top_page_and_vocab_are_served(client):
    html = client.get("/").text
    # トップから数学・漢字・英語の3つの診断へ進める
    for tab in ("placement", "kanji", "english"):
        assert f'data-go="{tab}"' in html and f'data-tab="{tab}"' in html
    js = client.get("/vocab.js")
    assert js.status_code == 200
    assert "showVocab" in js.text and "語彙" in js.text


# --- 公開に向けた守り ---


def test_cross_site_post_is_rejected_without_new_cookie(client):
    # 別サイトのページからのフォームの送信で、利用者の Cookie を置き換えさせない
    res = client.post(
        "/api/placement/start",
        data={"x": "1"},
        headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"},
    )
    assert res.status_code == 403
    assert "drill_uid" not in res.headers.get("set-cookie", "")


def test_placement_start_needs_json_body(client):
    # Sec-Fetch-Site を付けない古いブラウザでも、フォームの本文では始められない
    res = client.post("/api/placement/start", data={"x": "1"})
    assert res.status_code == 422
    assert "drill_uid" not in res.headers.get("set-cookie", "")


def test_origin_is_checked_when_sec_fetch_site_is_missing(client):
    other = client.post("/api/placement/start", json={}, headers={"Origin": "https://evil.example"})
    assert other.status_code == 403
    same = client.post("/api/placement/start", json={}, headers={"Origin": "http://testserver"})
    assert same.status_code == 200
    fetch = client.post("/api/placement/start", json={}, headers={"Sec-Fetch-Site": "same-origin"})
    assert fetch.status_code == 200


def test_cookie_is_kept_on_rejected_cross_site_post(client):
    client.get("/api/stats")
    uid = client.cookies.get("drill_uid")
    res = client.post("/api/placement/start", json={}, headers={"Sec-Fetch-Site": "cross-site"})
    assert res.status_code == 403
    assert client.cookies.get("drill_uid") == uid


def test_client_key_groups_ipv6_by_64():
    from starlette.requests import Request as StarletteRequest

    from drill.api import _client_key

    def key(real_ip):
        scope = {"type": "http", "headers": [(b"x-real-ip", real_ip.encode())], "client": ("10.0.0.1", 1)}
        return _client_key(StarletteRequest(scope))

    assert key("2001:db8:1:2::1") == key("2001:db8:1:2:aaaa:bbbb:cccc:dddd")
    assert key("2001:db8:1:2::1") != key("2001:db8:1:3::1")
    assert key("203.0.113.5") == "203.0.113.5"


def test_one_computation_per_client_at_a_time():
    from fastapi import HTTPException

    from drill.api import _ComputeSlots

    slots = _ComputeSlots()
    with slots.hold("a"):
        with pytest.raises(HTTPException) as e:
            with slots.hold("a"):
                pass
        assert e.value.status_code == 429
        with slots.hold("b"):  # ほかの送信元は計算できる
            pass
    with slots.hold("a"):  # 終われば、また送れる
        pass


def test_too_many_waiting_is_busy(client, sandbox):
    # 空きを待つ数が上限に達していたら、待たずに「混み合っています」を返す
    sandbox.max_waiting = 0
    try:
        res = answer(client, "power-0", "0")
    finally:
        sandbox.max_waiting = 8
    assert res.status_code == 503
