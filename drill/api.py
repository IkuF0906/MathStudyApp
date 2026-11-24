"""Web API と画面の配信。

起動: uvicorn drill.api:app --reload
保存先の DB は環境変数 DRILL_DB で変えられる（既定は drill.db）。
利用者は Cookie の ID で区別する。DRILL_ADOPT_LOCAL=1 で起動すると、Cookie のない
ブラウザに、利用者を区別する前の履歴（ID は local）を引き継がせる。
"""

import ipaddress
import os
import random
import re
import threading
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import placement, scheduler
from .checker import AnswerParseError
from .db import LOCAL_USER, USER_TTL, Store
from .sandbox import Busy, ComputeTimeout, Sandbox, from_env
from .templates import MISCONCEPTIONS, PROBLEM_TYPES, UNITS, Problem, from_id, generate

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
USER_COOKIE = "drill_uid"
_USER_ID = re.compile(rf"[0-9a-f]{{32}}|{LOCAL_USER}")
# 解答の文字数の上限（長い式ほど計算が重くなるため）
MAX_ANSWER_LENGTH = 300


class AnswerRequest(BaseModel):
    problem_id: str
    answer: str


class PlacementStartRequest(BaseModel):
    """本文は空でよい。JSON の本文を必須にして、別サイトのフォームから送れないようにする。"""


class PlacementAnswerRequest(BaseModel):
    session_id: str
    problem_id: str
    answer: str = ""
    skip: bool = False  # 「わからない」（答え合わせをせずに不正解とする）


def _problem_json(p: Problem) -> dict:
    return {
        "problem_id": p.problem_id,
        "type_id": p.type_id,
        "type_name": PROBLEM_TYPES[p.type_id].name,
        "unit_id": p.unit.id,
        "unit_name": p.unit.name,
        "prompt": p.prompt,
        "latex": p.latex,
        "answer_prefix": p.answer_prefix,
        "variable": str(p.unit.var),
        "list_answers": p.unit.list_answers,
    }


def _stats_json(s: scheduler.TypeState, mistakes: Counter) -> dict:
    """型ごとの成績。mistakes は誤答パターン ID ごとの回数（None は未分類の誤り）。"""
    t = PROBLEM_TYPES[s.type_id]
    return {
        "type_id": s.type_id,
        "type_name": t.name,
        "unit_id": t.unit,
        "unit_name": UNITS[t.unit].name,
        "attempts": s.attempts,
        "correct": s.correct,
        "accuracy": s.accuracy,
        "box": s.box,
        "due_at": s.due_at.isoformat() if s.due_at else None,
        "mistakes": [
            {"id": mid, "label": MISCONCEPTIONS[mid].label if mid else "未分類の誤り", "count": n}
            for mid, n in mistakes.most_common()
        ],
    }


def _cross_site(request: Request) -> bool:
    """別のサイトのページから送られたリクエストか。

    ブラウザが付ける Sec-Fetch-Site で決める。付けない古いブラウザでは、Origin と Host を比べる。
    """
    site = request.headers.get("sec-fetch-site")
    if site is not None:
        return site not in ("same-origin", "none")
    origin = request.headers.get("origin")
    return origin is not None and urlsplit(origin).netloc != request.headers.get("host")


def _client_key(request: Request) -> str:
    """送信元の鍵。nginx が付ける X-Real-IP（なければ直接の接続元）。
    IPv6 は1つの回線に /64 の範囲が割り当てられるので、/64 でまとめる。"""
    ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "")
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if addr.version == 6:
        return str(ipaddress.ip_network(f"{addr}/64", strict=False))
    return str(addr)


class _ComputeSlots:
    """送信元ごとに、答え合わせの計算を同時に1つまでにする。

    nginx の limit_conn は接続を数えるので、送った直後に接続を切ると数が戻るが、
    計算はワーカーで続いている。ここでは計算が終わるまで数えておく。
    """

    def __init__(self):
        self._busy: set[str] = set()
        self._lock = threading.Lock()

    @contextmanager
    def hold(self, key: str):
        with self._lock:
            if key in self._busy:
                raise HTTPException(429, "前の答え合わせが終わってから送ってください")
            self._busy.add(key)
        try:
            yield
        finally:
            with self._lock:
                self._busy.discard(key)


def _new_problem(type_id: str) -> Problem:
    return generate(type_id, random.randrange(10**9))


def _type_ids(unit: str | None) -> list[str]:
    """単元の型 ID の一覧（unit が None なら全単元）。"""
    if unit is not None and unit not in UNITS:
        raise HTTPException(404, "単元が見つかりません")
    return [tid for tid, t in PROBLEM_TYPES.items() if unit is None or t.unit == unit]


def create_app(
    db_path: str, now=datetime.now, adopt_local: bool = False, sandbox: Sandbox | None = None
) -> FastAPI:
    """now は現在時刻を返す関数（テストで時刻を固定するため差し替え可能）。
    adopt_local が真なら、Cookie のない利用者を LOCAL_USER とする。
    sandbox は答え合わせを動かすワーカー（省略すると環境変数の設定で作る）。"""
    app = FastAPI(title="学力診断テスト")
    store = Store(db_path)
    sandbox = sandbox or from_env()
    slots = _ComputeSlots()

    @app.middleware("http")
    async def reject_cross_site(request: Request, call_next):
        """別のサイトのページから、状態を変えるリクエスト（POST など）を送らせない（CSRF 対策）。"""
        if request.method not in ("GET", "HEAD", "OPTIONS") and _cross_site(request):
            return JSONResponse({"detail": "別のサイトからの送信は受け付けません"}, status_code=403)
        return await call_next(request)

    def grade(request: Request, task: str, text: str, *args):
        """ワーカーで答え合わせの処理をし、失敗を HTTP のエラーに変える。"""
        if len(text) > MAX_ANSWER_LENGTH:
            raise HTTPException(400, f"解答が長すぎます（{MAX_ANSWER_LENGTH}文字まで）")
        try:
            with slots.hold(_client_key(request)):
                return sandbox.call(task, *args, text)
        except KeyError:
            raise HTTPException(404, "問題が見つかりません")
        except AnswerParseError as exc:
            raise HTTPException(400, str(exc))
        except ComputeTimeout:
            raise HTTPException(400, "式の計算が終わりませんでした。指数や数が大きすぎないか確認してください")
        except Busy:
            raise HTTPException(503, "混み合っています。少し待ってからもう一度送ってください")

    def user_id(request: Request, response: Response) -> str:
        """Cookie の利用者 ID。なければ新しく発行する。
        使うたびに Cookie を付け直し、有効期限を「最後に使ってから400日」にする（DB の掃除の期限と同じ）。"""
        store.maybe_cleanup(now())
        uid = request.cookies.get(USER_COOKIE, "")
        if not _USER_ID.fullmatch(uid):
            uid = LOCAL_USER if adopt_local else uuid.uuid4().hex
        response.set_cookie(
            USER_COOKIE,
            uid,
            max_age=int(USER_TTL.total_seconds()),
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
        )
        return uid

    @app.get("/api/version")
    def version():
        """動いている版（イメージを作ったコミット）。Docker の外では dev。"""
        return {"version": os.environ.get("APP_VERSION", "dev")}

    @app.get("/api/units")
    def list_units():
        return [{"id": u.id, "name": u.name} for u in UNITS.values()]

    @app.get("/api/types")
    def list_types(unit: str | None = None):
        types = (PROBLEM_TYPES[tid] for tid in _type_ids(unit))
        return [{"id": t.id, "unit": t.unit, "name": t.name, "description": t.description} for t in types]

    @app.get("/api/problem")
    def problem(type: str | None = None, unit: str | None = None):
        """type を指定するとその型、省略すると unit（省略時は全単元）の中からランダムに出題する。"""
        if type is None:
            type = random.choice(_type_ids(unit))
        if type not in PROBLEM_TYPES:
            raise HTTPException(404, "問題の型が見つかりません")
        return _problem_json(_new_problem(type))

    @app.get("/api/review")
    def review(unit: str | None = None, uid: str = Depends(user_id)):
        state = scheduler.pick_next(store.states(uid, _type_ids(unit)), now())
        return _problem_json(_new_problem(state.type_id))

    @app.get("/api/preview")
    def preview(text: str, request: Request):
        """テキスト入力の解答がどの式として読み取られるかを返す（答え合わせ前の確認用）。"""
        return {"latex": grade(request, "preview", text)}

    def check_and_record(request: Request, uid: str, problem_id: str, text: str) -> tuple[dict, dict]:
        """答え合わせをして履歴に残す。(答え合わせの結果, 画面に返す内容) を返す。"""
        g = grade(request, "check", text, problem_id)
        mid = g["misconception_id"]
        mc = MISCONCEPTIONS[mid] if mid else None
        state = store.record(uid, g["problem_id"], g["type_id"], text, g["correct"], mid, now())
        return g, {
            "correct": g["correct"],
            "user_latex": g["user_latex"],
            "answer_latex": g["answer_latex"],
            "misconception": {"id": mc.id, "label": mc.label, "explanation": mc.explanation} if mc else None,
            "note": g["note"],
            "steps": g["steps"],
            "next_due": state.due_at.isoformat(),
        }

    @app.post("/api/answer")
    def answer(req: AnswerRequest, request: Request, uid: str = Depends(user_id)):
        return check_and_record(request, uid, req.problem_id, req.answer)[1]

    # --- レベル診断 ---

    def placement_problem(data: dict, rng: random.Random) -> dict:
        """次の型を選んで問題を作り、途中経過に「出題中」として入れる。"""
        responses = [placement.Response(**r) for r in data["responses"]]
        p = _new_problem(placement.next_type(responses, rng))
        data["current"] = p.problem_id
        return {**_problem_json(p), "index": len(responses) + 1, "total": placement.TOTAL}

    @app.post("/api/placement/start")
    def placement_start(_: PlacementStartRequest, uid: str = Depends(user_id)):
        session_id = uuid.uuid4().hex
        data = {"responses": [], "current": None}
        problem = placement_problem(data, random.Random())
        store.save_placement(session_id, uid, data, now())
        return {"session_id": session_id, "total": placement.TOTAL, "problem": problem}

    @app.post("/api/placement/answer")
    def placement_answer(req: PlacementAnswerRequest, request: Request, uid: str = Depends(user_id)):
        data = store.placement(req.session_id, uid)
        if data is None:
            raise HTTPException(404, "診断が見つかりません。はじめからやり直してください")
        if data["current"] is None or req.problem_id != data["current"]:
            raise HTTPException(409, "この問題の答えはもう受け付けていません")
        type_id = req.problem_id.rpartition("-")[0]
        if req.skip:
            p = from_id(req.problem_id)
            state = store.record(uid, p.problem_id, type_id, "", False, None, now())
            correct, mid = False, None
            body = {
                "correct": False,
                "skipped": True,
                "user_latex": "",
                "answer_latex": p.answer_latex,
                "misconception": None,
                "note": None,
                "steps": p.steps,
                "next_due": state.due_at.isoformat(),
            }
        else:
            g, body = check_and_record(request, uid, req.problem_id, req.answer)
            correct, mid = g["correct"], g["misconception_id"]
        data["responses"].append(
            {"type_id": type_id, "level": PROBLEM_TYPES[type_id].level, "correct": correct, "misconception_id": mid}
        )
        responses = [placement.Response(**r) for r in data["responses"]]
        done = len(responses) >= placement.TOTAL
        data["current"] = None
        body["theta"] = round(placement.estimate(responses), 2)
        body["index"] = len(responses)
        body["total"] = placement.TOTAL
        body["next"] = None if done else placement_problem(data, random.Random())
        body["result"] = placement.summarize(responses) if done else None
        store.save_placement(req.session_id, uid, data, now())
        return body

    @app.get("/api/stats")
    def stats(uid: str = Depends(user_id)):
        counts = store.misconception_counts(uid)
        return [_stats_json(s, counts.get(s.type_id, Counter())) for s in store.states(uid, list(PROBLEM_TYPES))]

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


_sandbox = from_env()
# 最初の答え合わせを待たせないよう、起動時にワーカーを立ち上げておく
_sandbox.start()
app = create_app(
    os.environ.get("DRILL_DB", "drill.db"), adopt_local=os.environ.get("DRILL_ADOPT_LOCAL") == "1", sandbox=_sandbox
)
