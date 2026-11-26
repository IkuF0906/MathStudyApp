"""レベル診断（適応型テスト）。

10問で数学の到達レベル θ を推定する。問題の型ごとのレベル L に対して、
正解する確率を P(正解 | θ, L) = 1 / (1 + exp(-1.6 (θ - L))) とおき（1パラメータのロジスティックモデル）、
回答ごとに θ を最尤推定（弱い事前分布つき）し直す。
記述式なので当てずっぽうで正解する確率は 0 とみなし、補正はしない。

次の問題のレベルは階段のように決める（推定の θ とは別）。
- レベル 8 より下: 正解なら 3 段上がる（8 まで）。不正解なら 1 段下がる
- レベル 8 から上: 2 問続けて正解すると 1 段上がる。不正解なら 1 段下がる
易しいところは早く通り過ぎ、難しいところは慎重に上がるため。そのレベルに最も近い、まだ出していない型から選ぶ。
"""

import math
import random
from collections import Counter
from dataclasses import dataclass

from .templates import MISCONCEPTIONS, PROBLEM_TYPES, UNITS

TOTAL = 10  # 1回の診断の問題数（20問では長いので 10 問にしている）
SLOPE = 1.6  # ロジスティック曲線の傾き（レベルが1違うと正答率がどれだけ変わるか）
START_LEVEL = 1  # 最初の問題のレベル。易しい中学1年から始め、正解で 3 段ずつ上がる
PRIOR_CENTER = 5  # 事前分布の中心。中学〜数III の真ん中の数I
PRIOR_SD = 3.0  # 事前分布の標準偏差。大きいほど弱い（回答に引っ張られやすい）
FAST_JUMP = 3  # レベル SLOW_FROM より下で正解したときに上がる段数
SLOW_FROM = 8  # このレベルから上は、2 問続けて正解したときだけ 1 段上がる
GRID = [i / 20 for i in range(0, 12 * 20 + 1)]  # θ の探索範囲 0〜12 を 0.05 刻み
MIN_LEVEL, MAX_LEVEL = 1, 10

# レベルの定義。各レベルの範囲と問題の型は docs/levels.md にまとめている
LEVEL_NAMES = {
    1: "中学1年",
    2: "中学2年",
    3: "中学3年",
    4: "数I（数と式）",
    5: "数I（2次関数・三角比）",
    6: "数A（場合の数と確率）",
    7: "数II・B",
    8: "数III入口",
    9: "数III",
    10: "大学教養",
}


@dataclass(frozen=True)
class Response:
    type_id: str
    level: int
    correct: bool
    misconception_id: str | None = None


def p_correct(theta: float, level: float) -> float:
    return 1 / (1 + math.exp(-SLOPE * (theta - level)))


def _log_posterior(theta: float, responses: list[Response]) -> float:
    lp = -((theta - PRIOR_CENTER) ** 2) / (2 * PRIOR_SD**2)
    for r in responses:
        p = p_correct(theta, r.level)
        lp += math.log(p if r.correct else 1 - p)
    return lp


def estimate(responses: list[Response]) -> float:
    """θ の推定値（事後分布の最頻値）。回答がなければ事前分布の中心。"""
    return max(GRID, key=lambda t: _log_posterior(t, responses))


def standard_error(responses: list[Response]) -> float:
    """推定の誤差の目安（グリッド上の事後分布の標準偏差）。"""
    lps = [_log_posterior(t, responses) for t in GRID]
    top = max(lps)
    ws = [math.exp(lp - top) for lp in lps]
    total = sum(ws)
    mean = sum(w * t for w, t in zip(ws, GRID)) / total
    return math.sqrt(sum(w * (t - mean) ** 2 for w, t in zip(ws, GRID)) / total)


def next_level(responses: list[Response]) -> int:
    """次に出す問題のレベル（階段のルール。モジュールの説明を参照）。"""
    if not responses:
        return START_LEVEL
    last = responses[-1]
    top = max(t.level for t in PROBLEM_TYPES.values())
    if not last.correct:
        return max(MIN_LEVEL, last.level - 1)
    if last.level < SLOW_FROM:
        return min(last.level + FAST_JUMP, SLOW_FROM)
    # レベル 8 から上で続けて正解した数。2 問目・4 問目…の正解で 1 段上がる
    streak = 0
    for r in reversed(responses):
        if not (r.correct and r.level >= SLOW_FROM):
            break
        streak += 1
    return min(last.level + 1, top) if streak % 2 == 0 else last.level


def next_type(responses: list[Response], rng: random.Random, type_ids: list[str] | None = None) -> str:
    """次に出す問題の型。目標のレベルに最も近い未出題の型から選ぶ（同じ単元が続かないようにする）。"""
    pool_ids = type_ids if type_ids is not None else list(PROBLEM_TYPES)
    used = {r.type_id for r in responses}
    pool = [PROBLEM_TYPES[t] for t in pool_ids if t not in used]
    if not pool:
        raise ValueError("出題できる型が残っていません")
    target = next_level(responses)
    d = min(abs(t.level - target) for t in pool)
    near = [t for t in pool if abs(t.level - target) <= d + 0.5]
    # 単元が偏らないよう、これまでに出た回数が少ない単元の型を優先する
    unit_counts = Counter(PROBLEM_TYPES[r.type_id].unit for r in responses)
    fewest = min(unit_counts[t.unit] for t in near)
    near = [t for t in near if unit_counts[t.unit] == fewest]
    return rng.choice(near).id


def level_name(level: int) -> str:
    return LEVEL_NAMES[min(max(level, MIN_LEVEL), MAX_LEVEL)]


def summarize(responses: list[Response], log: list[dict] | None = None) -> dict:
    """診断結果。到達レベルは、正答率が 50% 以上と推定される最も高いレベル（θ の切り捨て）。

    log は1問ごとの問題・自分の答え・正答（API が記録したもの）。そのまま結果の items に入れる。
    """
    theta = estimate(responses)
    reached = math.floor(theta)
    lowest = min(t.level for t in PROBLEM_TYPES.values())
    if reached < lowest:
        # 出題している型より下のレベルは測れないので、「〜未満」とだけ伝える
        label = f"{LEVEL_NAMES[lowest]}未満"
    else:
        label = f"{level_name(reached)}相当"
    levels = sorted({t.level for t in PROBLEM_TYPES.values()})
    by_level = []
    for lv in levels:
        rs = [r for r in responses if r.level == lv]
        by_level.append(
            {
                "level": lv,
                "name": LEVEL_NAMES[lv],
                "attempts": len(rs),
                "correct": sum(r.correct for r in rs),
                "p": round(p_correct(theta, lv), 3),
            }
        )
    mistakes = Counter(r.misconception_id for r in responses if not r.correct and r.misconception_id)
    wrong = [r for r in responses if not r.correct]
    # 単元ごとの手ごたえ（出題した単元だけ。並びは単元の定義の順）
    by_unit = []
    for uid, unit in UNITS.items():
        rs = [r for r in responses if PROBLEM_TYPES[r.type_id].unit == uid]
        if rs:
            by_unit.append({"unit_id": uid, "unit_name": unit.name, "attempts": len(rs), "correct": sum(r.correct for r in rs)})
    asked = {u["unit_id"] for u in by_unit}
    return {
        "theta": round(theta, 2),
        "se": round(standard_error(responses), 2),
        "level": min(max(reached, 0), MAX_LEVEL),
        "label": label,
        "answered": len(responses),
        "correct": sum(r.correct for r in responses),
        "by_level": by_level,
        "by_unit": by_unit,
        "untested_units": [unit.name for uid, unit in UNITS.items() if uid not in asked],
        "misconceptions": [
            {
                "id": mid,
                "label": MISCONCEPTIONS[mid].label,
                "explanation": MISCONCEPTIONS[mid].explanation,
                "count": n,
            }
            for mid, n in mistakes.most_common(5)
        ],
        "unclassified_wrong": sum(1 for r in wrong if r.misconception_id is None),
        "missed": [
            {
                "type_id": r.type_id,
                "type_name": PROBLEM_TYPES[r.type_id].name,
                "unit_id": PROBLEM_TYPES[r.type_id].unit,
                "unit_name": UNITS[PROBLEM_TYPES[r.type_id].unit].name,
                "level": r.level,
            }
            for r in sorted(wrong, key=lambda r: r.level)
        ],
        "items": log or [],
    }
