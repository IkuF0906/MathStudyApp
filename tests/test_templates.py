"""全ての型について、多数のシードで問題・正解・誤答が矛盾しないことを確かめる。

正解は、問題の型が作ったものとは別に、単元の定義から求め直して比べる。
"""

import math
from itertools import combinations, permutations, product

import pytest
import sympy as sp
from sympy.calculus.util import maximum

from drill import form
from drill.checker import N, X, equivalent
from drill.templates import MISCONCEPTIONS, PROBLEM_TYPES, UNITS, from_id, generate

Z = sp.Symbol("z", real=True)  # 方程式を解き直すときの変数（X は正の数に限っているので負の解を落とす）

SEEDS = range(30)


def _first_terms(p, count=6) -> list:
    """数列の問題の第 1〜count 項（または第 count 項までの和）を、一般項を使わずに求める。"""
    m = p.meta
    kind = m["kind"]
    if kind == "arith_sum":
        return [sum(m["a"] + (i - 1) * m["d"] for i in range(1, n + 1)) for n in range(1, count + 1)]
    if kind == "geom_sum":
        return [sum(m["a"] * m["r"] ** (i - 1) for i in range(1, n + 1)) for n in range(1, count + 1)]
    if kind == "sigma":
        return [sum(m["term"].subs(m["k"], i) for i in range(1, n + 1)) for n in range(1, count + 1)]
    if kind == "recur":
        terms = [m["a1"]]
        for n in range(1, count):
            terms.append(m["next"](terms[-1], n))
        return terms
    raise AssertionError(kind)


def _count_by_brute_force(p) -> int:
    m = p.meta
    if p.type_id == "prob_perm_comb":
        pick = permutations if m["ordered"] else combinations
        return sum(1 for _ in pick(range(m["n"]), m["r"]))
    if m["variant"] == "circle":
        # 回転で重なるものを同じとみなす：0 番の人から時計回りに読んだ並びで区別する
        seen = set()
        for order in permutations(range(m["n"])):
            i = order.index(0)
            seen.add(order[i:] + order[:i])
        return len(seen)
    if m["variant"] == "same":
        return len(set(permutations(m["word"])))
    return sum(1 for order in permutations(range(m["n"])) if abs(order.index(0) - order.index(1)) == 1)


def _probability(p) -> sp.Rational:
    m = p.meta
    if p.type_id in ("prob_complement", "prob_binomial"):
        rolls = list(product(range(1, 7), repeat=m["n"]))
        hits = [sum(r in m["faces"] for r in roll) for roll in rolls]
        good = sum(h >= 1 for h in hits) if p.type_id == "prob_complement" else sum(h == m["k"] for h in hits)
        return sp.Rational(good, len(rolls))
    if p.type_id == "prob_draw":
        balls = ["r"] * m["red"] + ["w"] * m["white"]
        pairs = list(permutations(range(len(balls)), 2))
        if m["kind"] == "both_red":
            good = sum(balls[i] == balls[j] == "r" for i, j in pairs)
        else:
            good = sum(balls[i] != balls[j] for i, j in pairs)
        return sp.Rational(good, len(pairs))
    if p.type_id == "prob_conditional":
        # 製品 10000 個あたりの個数で数える
        a_bad = 10000 * m["pa"] * m["da"]
        b_bad = 10000 * (1 - m["pa"]) * m["db"]
        return a_bad / (a_bad + b_bad)
    if p.type_id == "prob_expectation":
        tickets = [x for x, c in zip(m["prizes"], m["counts"]) for _ in range(c)]
        return sp.Rational(sum(tickets), m["total"])
    raise AssertionError(p.type_id)


def _real_roots(poly) -> set:
    return set(sp.solve(poly.subs(X, Z), Z))


def _num(v) -> float:
    return float(sp.N(v))


def check_middle_school(p) -> bool:
    """中学〜数I の単元の正解を確かめる。対象外の型なら False。"""
    m, t = p.meta, p.type_id
    if t == "calc_signed":
        expected = m["a"] - m["b"] * m["c"] if m["kind"] == "sub_mul" else (-m["a"]) ** 2 - m["b"] ** 2
        assert p.answer == expected
    elif t in ("calc_linear_expr", "calc_poly", "calc_monomial", "calc_expand"):
        assert sp.expand(p.answer - m["expr"]) == 0
        assert p.answer == sp.expand(p.answer), "展開した形になっていない"
    elif t in ("calc_factor", "calc_factor_cross"):
        assert sp.expand(p.answer - m["expanded"]) == 0
        assert form._factored(p.answer), "因数分解しきった形になっていない"
    elif t == "calc_sqrt":
        assert math.isclose(_num(p.answer), math.sqrt(m["m"]) + m["sign"] * math.sqrt(m["n"]))
        assert not form._radical_not_simplified(p.answer)
    elif t == "calc_rationalize":
        assert math.isclose(_num(p.answer), _num(p.f))
        assert sp.fraction(sp.together(p.answer))[1].is_Integer, "分母に根号が残っている"
    elif t == "eq_linear":
        x0 = p.answer
        assert m["a"] * x0 + m["b"] == m["c"] * x0 + m["d"]
    elif t == "eq_system":
        x0, y0 = p.answer
        assert m["a"] * x0 + m["b"] * y0 == m["p"] and m["c"] * x0 + m["d"] * y0 == m["q"]
    elif t in ("eq_quadratic_factor", "eq_quadratic_formula"):
        assert _real_roots(m["poly"]) == set(p.answer)
    elif t == "eq_discriminant":
        k = sp.Symbol("k")
        disc = k**2 - 4 * m["c"] ** 2 if m["kind"] == "k_middle" else m["b"] ** 2 - 4 * k
        expected = set(sp.solve(disc, k))
        assert expected == (set(p.answer) if isinstance(p.answer, sp.FiniteSet) else {p.answer})
    elif t == "eq_abs":
        assert set(p.answer) == {x for x in range(-30, 31) if abs(x - m["a"]) == m["b"]}
    elif t == "fn_linear":
        for x, y in m["points"]:
            assert p.answer.subs(X, x) == y
    elif t == "fn_vertex":
        x0, y0 = p.answer
        assert sp.diff(p.f, X).subs(X, x0) == 0 and p.f.subs(X, x0) == y0
    elif t == "fn_max_min":
        s_, t_ = m["s"], m["t"]
        xs = [sp.Rational(i, 4) for i in range(4 * s_, 4 * t_ + 1)]  # 頂点は整数なので 1/4 刻みで足りる
        values = [p.f.subs(X, x) for x in xs]
        assert p.answer == (max(values) if m["kind"] == "max_inside" else min(values))
    elif t == "trig_value":
        f = {"sin": math.sin, "cos": math.cos, "tan": math.tan}[m["func"]]
        assert math.isclose(_num(p.answer), f(math.radians(m["deg"])))
    elif t == "trig_cosine_law":
        b, c, a = m["b"], m["c"], _num(p.answer)
        assert math.isclose(a * a, b * b + c * c - 2 * b * c * math.cos(math.radians(m["deg"])))
        assert not form._radical_not_simplified(p.answer)
    elif t == "trig_sine_law":
        lhs = m["a"] / math.sin(math.radians(m["A"]))
        assert math.isclose(lhs, _num(p.answer) / math.sin(math.radians(m["B"])))
        assert not form._radical_not_simplified(p.answer)
    else:
        return False
    return True


def check_answer(p) -> None:
    """単元の定義に照らして、正解が正しいことを確かめる。"""
    unit = p.unit.id
    if check_middle_school(p):
        return
    if p.type_id == "dint_area":
        lo, hi = p.meta["lo"], p.meta["hi"]
        d = sp.expand(p.f - p.meta["line"])
        assert sp.degree(d, X) == 2 and d.subs(X, lo) == 0 and d.subs(X, hi) == 0, "交点が区間の端でない"
        assert p.answer == abs(sp.integrate(d, (X, lo, hi)))
    elif p.type_id == "dint_distance":
        r, hi = p.meta["r"], p.meta["hi"]
        assert p.f.subs(X, r) == 0 and p.f.subs(X, 0) * p.f.subs(X, hi) < 0, "途中で向きが変わらない"
        assert p.answer == abs(sp.integrate(p.f, (X, 0, r))) + abs(sp.integrate(p.f, (X, r, hi)))
    elif p.type_id == "app_box":
        a, b = p.meta["a"], p.meta["b"]
        volume = X * (a - 2 * X) * (b - 2 * X)
        assert p.answer == maximum(volume, X, sp.Interval.open(0, sp.Rational(min(a, b), 2)))
    elif unit == "sequence":
        if p.meta["kind"] == "arith":
            m = p.meta
            assert p.answer.subs(N, m["p"]) == m["ap"] and p.answer.subs(N, m["q"]) == m["aq"]
            assert sp.degree(p.answer, N) == 1
        else:
            for n, value in enumerate(_first_terms(p), start=1):
                assert sp.simplify(p.answer.subs(N, n) - value) == 0, f"第 {n} 項が違う"
    elif p.type_id in ("prob_perm_comb", "prob_arrange"):
        assert p.answer == _count_by_brute_force(p)
    elif unit == "probability":
        assert p.answer == _probability(p)
    elif unit == "derivative":
        assert equivalent(p.answer, sp.diff(p.f, X))
    elif unit == "integral":
        assert equivalent(sp.diff(p.answer, X), p.f)
    elif unit == "definite":
        assert equivalent(p.answer, sp.integrate(p.f, (X, p.meta["lo"], p.meta["hi"])))
    elif unit == "limit":
        to = p.meta["to"]
        expected = sp.limit(p.f, X, to)
        if to != sp.oo:  # x → a は左右から一致することも確かめる
            assert sp.limit(p.f, X, to, "-") == expected
        assert p.unit.same(p.answer, expected)
    elif p.type_id in ("app_tangent", "app_normal"):
        a = p.meta["a"]
        slope = sp.diff(p.answer, X)
        df_a = sp.diff(p.f, X).subs(X, a)
        assert p.answer.subs(X, a) == p.f.subs(X, a), "接点を通らない"
        assert slope == (df_a if p.type_id == "app_tangent" else -1 / df_a)
    elif p.type_id == "app_extremum":
        x0 = p.meta["x0"]
        df, d2f = sp.diff(p.f, X), sp.diff(p.f, X, 2)
        assert df.subs(X, x0) == 0
        assert (d2f.subs(X, x0) < 0) == (p.meta["kind"] == "極大値")
        assert p.answer == p.f.subs(X, x0)
    else:
        raise AssertionError(f"検証方法が決まっていない型: {p.type_id}")


@pytest.mark.parametrize("type_id", PROBLEM_TYPES)
def test_generated_problems_are_consistent(type_id):
    for seed in SEEDS:
        p = generate(type_id, seed)
        assert p.problem_id == f"{type_id}-{seed}"
        check_answer(p)
        assert p.wrongs, "診断に使える誤答が1つもない"
        same = p.unit.same
        for mid, wrong in p.wrongs:
            assert mid in MISCONCEPTIONS
            assert not same(wrong, p.answer)
        for i, (_, a) in enumerate(p.wrongs):
            for _, b in p.wrongs[i + 1 :]:
                assert not same(a, b)


def test_derivative_problems_are_not_constant():
    for type_id, t in PROBLEM_TYPES.items():
        if t.unit == "derivative":
            for seed in SEEDS:
                assert not equivalent(generate(type_id, seed).answer, sp.Integer(0))


@pytest.mark.parametrize("type_id", PROBLEM_TYPES)
def test_same_seed_gives_same_problem(type_id):
    assert generate(type_id, 7).f == generate(type_id, 7).f


def test_every_type_belongs_to_a_unit():
    assert {t.unit for t in PROBLEM_TYPES.values()} == set(UNITS)


def test_from_id_roundtrip():
    p = from_id("chain-123")
    assert p.type_id == "chain"
    assert p.f == generate("chain", 123).f


@pytest.mark.parametrize("bad", ["", "chain", "nope-1", "chain-abc", "chain--1"])
def test_from_id_rejects(bad):
    with pytest.raises(KeyError):
        from_id(bad)


def test_every_misconception_is_used():
    used = {mid for t in PROBLEM_TYPES for s in SEEDS for mid, _ in generate(t, s).wrongs}
    # 答えの形の誤り（展開しきっていない など）は誤答の式ではなく、書いた形で見つける
    form_ids = {m.id for m in form.MISCONCEPTIONS}
    assert used == set(MISCONCEPTIONS) - form_ids


def test_every_level_has_types():
    """レベル診断で測る Lv1（中1）〜Lv9（数III）に、どれも3つ以上の型がある。"""
    for level in range(1, 10):
        assert sum(t.level == level for t in PROBLEM_TYPES.values()) >= 3, level
