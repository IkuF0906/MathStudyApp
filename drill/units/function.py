"""単元「関数」：1次関数の式・2次関数の頂点・最大値と最小値（中学〜数I）。"""

import sympy as sp

from ..checker import X
from ..core import Built, Misconception, ProblemType, Unit, nonzero, to_latex

UNIT = Unit(
    id="function",
    name="関数",
    prompt="",  # 問題ごとに決める
    answer_prefix="y =",
    list_answers=True,
)

MISCONCEPTIONS = [
    Misconception(
        "fn_slope_inverted",
        r"傾きを $\frac{x \text{ の増加量}}{y \text{ の増加量}}$ とした",
        r"傾きは $\frac{y \text{ の増加量}}{x \text{ の増加量}}$ です。分母と分子が逆になっていないか確かめましょう。",
    ),
    Misconception(
        "fn_intercept_sign",
        "切片を求めるときに移項の符号を間違えた",
        r"$y = ax + b$ に通る点 $(p, q)$ を代入すると $q = ap + b$ なので、$b = q - ap$ です。",
    ),
    Misconception(
        "fn_vertex_sign",
        r"頂点の $x$ 座標の符号を逆にした",
        r"$y = a(x - p)^2 + q$ の頂点は $(p, q)$ です。$(x + 2)^2$ なら $p = -2$ になります。",
    ),
    Misconception(
        "fn_complete_square_a",
        r"平方完成で $x^2$ の係数をくくり出さなかった",
        r"$ax^2 + bx + c$ は、まず $a$ をくくり出して $a\left(x^2 + \frac{b}{a}x\right) + c$ としてから平方完成します。"
        r"頂点の $x$ 座標は $-\frac{b}{2a}$ です。",
    ),
    Misconception(
        "fn_vertex_outside",
        "頂点が範囲の外にあるのに、頂点の y 座標を答えた",
        r"定義域に制限があるときは、頂点がその範囲に入っているか確かめます。入っていなければ、範囲の端の値で最大・最小が決まります。",
    ),
    Misconception(
        "fn_wrong_endpoint",
        "範囲の端のうち、反対側の値を答えた",
        r"グラフをかいて、範囲の両端のうちどちらが軸から遠いか（近いか）を確かめましょう。下に凸の放物線では、軸から遠い端ほど $y$ が大きくなります。",
    ),
    Misconception(
        "fn_vertex_as_max",
        "下に凸の放物線で、頂点を最大値とした",
        r"$x^2$ の係数が正の放物線は下に凸なので、頂点は最小値です。最大値は範囲の端のうち、軸から遠いほうでとります。",
    ),
    Misconception(
        "fn_endpoint_only",
        "範囲の端だけを調べて、頂点を見落とした",
        r"頂点が範囲の中にあるとき、下に凸の放物線の最小値は頂点の $y$ 座標です。",
    ),
]


def _p(v) -> str:
    return f"({v})" if v < 0 else str(v)


def _build_linear(rng):
    """2点を通る直線の式。"""
    m, b = nonzero(rng, -4, 4), rng.randint(-6, 6)
    x1, x2 = sorted(rng.sample(range(-4, 6), 2))
    y1, y2 = m * x1 + b, m * x2 + b
    answer = m * X + b
    wrongs = [("fn_intercept_sign", m * X + (y1 + m * x1))]
    if y2 != y1:
        s = sp.Rational(x2 - x1, y2 - y1)
        wrongs.insert(0, ("fn_slope_inverted", sp.expand(s * (X - x1) + y1)))
    steps = [
        rf"傾きは $\frac{{{y2} - {_p(y1)}}}{{{x2} - {_p(x1)}}} = {m}$",
        rf"$y = {m}x + b$ に $({x1}, {y1})$ を代入して $b = {y1} - {_p(m)} \times {_p(x1)} = {b}$",
    ]
    return Built(
        answer,
        wrongs,
        steps,
        latex="",
        answer=answer,
        prompt=rf"2 点 $({x1},\ {y1})$、$({x2},\ {y2})$ を通る直線の式を求めなさい。",
        meta={"points": [(x1, y1), (x2, y2)]},
    )


def _build_vertex(rng):
    a = rng.choice([1, 1, -1, 2, -2, 3])
    p, q = nonzero(rng, -5, 5), rng.randint(-6, 6)
    b, c = -2 * a * p, a * p * p + q
    f = a * X**2 + b * X + c
    answer = sp.Tuple(p, q)
    wrongs = [("fn_vertex_sign", sp.Tuple(-p, q))]
    if a != 1:
        wrongs.append(("fn_complete_square_a", sp.Tuple(sp.Rational(-b, 2), c - sp.Rational(b * b, 4))))
    inner = sp.expand(X**2 + sp.Rational(b, a) * X)
    steps = [
        rf"$x^2$ の係数でくくる: $y = {'' if a == 1 else '-' if a == -1 else a}\left({to_latex(inner)}\right) + {_p(c)}$"
        if a != 1
        else rf"$y = {to_latex(f)}$",
        rf"平方完成する: $y = {'' if a == 1 else '-' if a == -1 else a}\left({to_latex(X - p)}\right)^2 {'+' if q >= 0 else '-'} {abs(q)}$",
        rf"頂点は $({p},\ {q})$",
    ]
    return Built(
        f,
        wrongs,
        steps,
        latex=rf"y = {to_latex(f)}",
        answer=answer,
        prompt="次の放物線の頂点の座標を「(2, -3)」のように答えなさい。",
        answer_prefix=r"\text{頂点} =",
        answer_latex=rf"({p},\ {q})",
        meta={"a": a, "b": b, "c": c},
    )


def _build_max_min(rng):
    """y = (x - p)^2 + q の、区間 s ≤ x ≤ t での最大値・最小値。"""
    p, q = rng.randint(-3, 3), rng.randint(-5, 5)
    f = sp.expand((X - p) ** 2 + q)

    def val(x):
        return f.subs(X, x)

    kind = rng.choice(["min_outside", "max_inside", "min_inside"])
    if kind == "min_outside":
        width = rng.randint(1, 3)
        if rng.random() < 0.5:
            s = p + rng.randint(1, 3)
            t = s + width
        else:
            t = p - rng.randint(1, 3)
            s = t - width
        near, far = (s, t) if abs(s - p) < abs(t - p) else (t, s)
        answer, target = val(near), "最小値"
        wrongs = [("fn_vertex_outside", sp.Integer(q)), ("fn_wrong_endpoint", val(far))]
        steps = [
            rf"$y = \left({to_latex(X - p)}\right)^2 {'+' if q >= 0 else '-'} {abs(q)}$ より軸は $x = {p}$",
            rf"軸は範囲 ${s} \le x \le {t}$ の外にあるので、軸に近い端 $x = {near}$ で最小になる",
        ]
    else:
        s = p - rng.randint(1, 3)
        t = p + rng.randint(1, 3)
        while t - p == p - s:
            t = p + rng.randint(1, 4)
        near, far = (s, t) if abs(s - p) < abs(t - p) else (t, s)
        if kind == "max_inside":
            answer, target = val(far), "最大値"
            wrongs = [("fn_vertex_as_max", sp.Integer(q)), ("fn_wrong_endpoint", val(near))]
            steps = [
                rf"$y = \left({to_latex(X - p)}\right)^2 {'+' if q >= 0 else '-'} {abs(q)}$ より軸は $x = {p}$（下に凸）",
                rf"軸から遠い端 $x = {far}$ で最大になる",
            ]
        else:
            answer, target = sp.Integer(q), "最小値"
            wrongs = [("fn_endpoint_only", min(val(s), val(t)))]
            steps = [
                rf"$y = \left({to_latex(X - p)}\right)^2 {'+' if q >= 0 else '-'} {abs(q)}$ より軸は $x = {p}$",
                rf"軸は範囲 ${s} \le x \le {t}$ の中にあるので、頂点で最小になる",
            ]
    return Built(
        f,
        wrongs,
        steps,
        latex=rf"y = {to_latex(f)} \quad ({s} \le x \le {t})",
        answer=sp.Integer(answer),
        prompt=f"次の関数の{target}を求めなさい。",
        answer_prefix=rf"\text{{{target}}} =",
        meta={"s": s, "t": t, "kind": kind},
    )


TYPES = [
    ProblemType("fn_linear", "function", "1次関数の式", r"2 点を通る直線 $y = ax + b$", _build_linear, level=2),
    ProblemType("fn_vertex", "function", "2次関数の頂点", r"平方完成 $y = a(x - p)^2 + q$", _build_vertex, level=5),
    ProblemType("fn_max_min", "function", "2次関数の最大・最小", r"定義域に制限があるときの最大値・最小値", _build_max_min, level=5),
]
