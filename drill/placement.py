"""レベル診断（適応型テスト）。

20問で数学の到達レベル θ を推定する。問題の型ごとのレベル L に対して、
正解する確率を P(正解 | θ, L) = 1 / (1 + exp(-1.6 (θ - L))) とおき（1パラメータのロジスティックモデル）、
回答ごとに θ を最尤推定（弱い事前分布つき）し直す。
記述式なので当てずっぽうで正解する確率は 0 とみなし、補正はしない。

次の問題は、直前に正解なら θ + 0.4、不正解なら θ - 0.4 に近いレベルの、まだ出していない型から選ぶ。
"""

import math
import random
from collections import Counter
from dataclasses import dataclass

from .templates import MISCONCEPTIONS, PROBLEM_TYPES, UNITS

TOTAL = 20  # 1回の診断の問題数
SLOPE = 1.6  # ロジスティック曲線の傾き（レベルが1違うと正答率がどれだけ変わるか）
START_LEVEL = 5  # 最初の問題のレベル（事前分布の中心）。中学〜数III の真ん中の数I から始める
PRIOR_SD = 3.0  # 事前分布の標準偏差。大きいほど弱い（回答に引っ張られやすい）
STEP = 0.4  # 次の問題を、いまの推定値からどれだけずらしたレベルで出すか
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
    lp = -((theta - START_LEVEL) ** 2) / (2 * PRIOR_SD**2)
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


def next_type(responses: list[Response], rng: random.Random, type_ids: list[str] | None = None) -> str:
    """次に出す問題の型。目標のレベルに最も近い未出題の型から選ぶ（同じ単元が続かないようにする）。"""
    pool_ids = type_ids if type_ids is not None else list(PROBLEM_TYPES)
    used = {r.type_id for r in responses}
    pool = [PROBLEM_TYPES[t] for t in pool_ids if t not in used]
    if not pool:
        raise ValueError("出題できる型が残っていません")
    if responses:
        theta = estimate(responses)
        target = theta + (STEP if responses[-1].correct else -STEP)
    else:
        target = START_LEVEL
    d = min(abs(t.level - target) for t in pool)
    near = [t for t in pool if abs(t.level - target) <= d + 0.5]
    # 単元が偏らないよう、これまでに出た回数が少ない単元の型を優先する
    unit_counts = Counter(PROBLEM_TYPES[r.type_id].unit for r in responses)
    fewest = min(unit_counts[t.unit] for t in near)
    near = [t for t in near if unit_counts[t.unit] == fewest]
    return rng.choice(near).id


def level_name(level: int) -> str:
    return LEVEL_NAMES[min(max(level, MIN_LEVEL), MAX_LEVEL)]


def summarize(responses: list[Response]) -> dict:
    """診断結果。到達レベルは、正答率が 50% 以上と推定される最も高いレベル（θ の切り捨て）。"""
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
    return {
        "theta": round(theta, 2),
        "se": round(standard_error(responses), 2),
        "level": min(max(reached, 0), MAX_LEVEL),
        "label": label,
        "answered": len(responses),
        "correct": sum(r.correct for r in responses),
        "by_level": by_level,
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
    }
