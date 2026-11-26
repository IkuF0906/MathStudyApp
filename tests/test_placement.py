"""レベル診断の推定と出題。能力の違う仮想の受験者に解かせて、推定が分かれることを確かめる。"""

import random
import statistics

import pytest

from drill.placement import (
    LEVEL_NAMES,
    START_LEVEL,
    TOTAL,
    Response,
    estimate,
    next_type,
    p_correct,
    standard_error,
    summarize,
)
from drill.templates import PROBLEM_TYPES

RUNS = 40  # 能力ごとの仮想受験者の人数


def simulate(true_theta: float, seed: int) -> list[Response]:
    """能力 true_theta の受験者が、モデルどおりの確率で正解しながら診断を受ける。"""
    rng = random.Random(seed)
    responses: list[Response] = []
    for _ in range(TOTAL):
        tid = next_type(responses, rng)
        level = PROBLEM_TYPES[tid].level
        responses.append(Response(tid, level, rng.random() < p_correct(true_theta, level)))
    return responses


def test_every_type_has_a_level():
    for t in PROBLEM_TYPES.values():
        assert t.level in LEVEL_NAMES, t.id
    # Lv1（中1）〜Lv9（数III）を埋める（Lv10 の大学教養は上限として名前だけ持つ）
    assert {t.level for t in PROBLEM_TYPES.values()} == set(range(1, 10))


def test_p_correct():
    assert p_correct(7, 7) == pytest.approx(0.5)
    assert p_correct(8, 7) > 0.8 > 0.2 > p_correct(6, 7)


def test_estimate_moves_with_answers():
    prior = estimate([])
    right = estimate([Response("power", 7, True)])
    wrong = estimate([Response("power", 7, False)])
    assert wrong < prior < right


def test_no_repeat_and_unit_variety():
    responses = simulate(7.5, seed=0)
    ids = [r.type_id for r in responses]
    assert len(ids) == len(set(ids)) == TOTAL
    units = [PROBLEM_TYPES[t].unit for t in ids]
    assert all(a != b for a, b in zip(units, units[1:]))


def test_next_item_follows_last_answer():
    rng = random.Random(1)
    first = next_type([], rng)
    assert PROBLEM_TYPES[first].level == START_LEVEL
    up = next_type([Response(first, START_LEVEL, True)], rng)
    down = next_type([Response(first, START_LEVEL, False)], rng)
    assert PROBLEM_TYPES[up].level >= START_LEVEL >= PROBLEM_TYPES[down].level


def test_next_level_staircase():
    from drill.placement import next_level

    r = lambda level, ok: Response("power", level, ok)  # noqa: E731（型は使わないので何でもよい）
    assert next_level([]) == START_LEVEL
    # レベル 8 より下: 正解で 3 段上がる（8 で止まる）、不正解で 1 段下がる
    assert next_level([r(4, True)]) == 7
    assert next_level([r(6, True)]) == 8
    assert next_level([r(5, False)]) == 4
    assert next_level([r(1, False)]) == 1
    # レベル 8 から上: 2 問続けて正解して 1 段上がる
    assert next_level([r(8, True)]) == 8
    assert next_level([r(8, True), r(8, True)]) == 9
    assert next_level([r(8, False), r(8, True)]) == 8
    assert next_level([r(9, True), r(9, True)]) == 9  # いちばん上（Lv9）より上には行かない
    assert next_level([r(9, False)]) == 8


@pytest.mark.parametrize("true_theta", [2.0, 4.0, 6.0, 7.5, 9.0])
def test_simulated_examinee_is_recovered(true_theta):
    estimates = [estimate(simulate(true_theta, seed)) for seed in range(RUNS)]
    assert statistics.mean(estimates) == pytest.approx(true_theta, abs=0.3)
    # 10 問で、不正解では 1 段ずつしか下がらないので、低いレベルの受験者ほど推定がばらつく（θ=2 で ±0.55 ほど）
    assert statistics.stdev(estimates) < 0.7


def test_different_abilities_are_separated():
    low = [estimate(simulate(3.0, s)) for s in range(RUNS)]
    mid = [estimate(simulate(4.5, s + 1000)) for s in range(RUNS)]
    high = [estimate(simulate(6.0, s + 2000)) for s in range(RUNS)]
    # 1.5 レベル違う受験者どうしは、ほとんどの組で推定の大小が入れ替わらない
    pairs = [(lo, hi) for a, b in [(low, mid), (mid, high)] for lo, hi in zip(a, b)]
    assert sum(lo < hi for lo, hi in pairs) / len(pairs) >= 0.9
    # 3.0 と 6.0 の受験者は、ほぼ必ず推定の大小が入れ替わらない（最初の数問は易しい問題なので、たまに近づく）
    assert sum(lo < hi for lo in low for hi in high) / (len(low) * len(high)) >= 0.99


def test_standard_error_shrinks():
    responses = simulate(7.5, seed=3)
    assert standard_error(responses) < standard_error(responses[:5]) < standard_error([])


def test_summary():
    responses = [
        Response("power", 7, True),
        Response("product", 8, False, "product_naive"),
        Response("quotient", 8, False, None),
        Response("chain", 8, False, "product_naive"),
    ]
    s = summarize(responses)
    assert s["answered"] == 4 and s["correct"] == 1
    assert s["label"].endswith("相当") or s["label"].endswith("未満")
    lv8 = next(b for b in s["by_level"] if b["level"] == 8)
    assert (lv8["attempts"], lv8["correct"]) == (3, 0)
    assert s["misconceptions"][0]["count"] == 2
    assert s["unclassified_wrong"] == 1
    assert [m["level"] for m in s["missed"]] == [8, 8, 8]
    # 4問とも微分の単元。出題しなかった単元は名前だけを返す
    assert s["by_unit"] == [{"unit_id": "derivative", "unit_name": "微分", "attempts": 4, "correct": 1}]
    assert "微分" not in s["untested_units"] and "三角比" in s["untested_units"]


def test_summary_labels():
    labels = [summarize(simulate(9.5, s))["label"] for s in range(20)]
    # 推定は平均 9.4・ばらつき ±0.6。数III入口〜大学教養に収まり、半分以上は数III以上になる
    assert set(labels) <= {"数III入口相当", "数III相当", "大学教養相当"}
    assert sum(label in ("数III相当", "大学教養相当") for label in labels) >= 10
    strong_low = summarize([Response(t, PROBLEM_TYPES[t].level, False) for t in list(PROBLEM_TYPES)[:20]])
    assert strong_low["label"] == "中学1年未満"
