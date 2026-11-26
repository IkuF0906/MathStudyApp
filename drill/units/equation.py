"""単元「方程式」：1次方程式・連立方程式・2次方程式・絶対値（中学〜数I）。

答えが2つ以上ある問題は「2, -3」のようにコンマで区切って答える。
方程式の解は順番を問わない（sp.FiniteSet）、連立方程式の (x, y) は順番どおり（sp.Tuple）に比べる。
"""

import math

import sympy as sp

from ..checker import X
from ..core import Built, Misconception, ProblemType, Unit, nonzero, to_latex

Y = sp.Symbol("y")  # 連立方程式の表示にだけ使う

UNIT = Unit(
    id="equation",
    name="方程式",
    prompt="次の方程式を解きなさい。",
    answer_prefix="x =",
    list_answers=True,
)

MULTI_HINT = "解が2つあるときは「2, -3」のようにコンマで区切って答えなさい（± も使えます）。"

MISCONCEPTIONS = [
    Misconception(
        "eq_transpose_sign",
        "移項で符号を変え忘れた",
        r"項を等号の反対側に移すときは符号を変えます。$ax + b = c$ なら $ax = c - b$ です。",
    ),
    Misconception(
        "eq_divide_inverted",
        r"$ax = b$ を $x = \frac{a}{b}$ とした",
        r"$ax = b$ の両辺を $a$ で割って $x = \frac{b}{a}$ です。割る数と割られる数を取り違えないようにしましょう。",
    ),
    Misconception(
        "eq_system_swap",
        "x と y の値を取り違えた",
        r"求めた値がどちらの文字のものか確かめましょう。元の 2 つの式に代入して、両方とも成り立てば正しい解です。",
    ),
    Misconception(
        "eq_root_sign",
        r"$(x - a)(x - b) = 0$ の解を $x = -a, -b$ とした",
        r"$(x - a)(x - b) = 0$ なら $x - a = 0$ または $x - b = 0$ なので、$x = a, b$ です。符号が逆になります。",
    ),
    Misconception(
        "eq_divide_by_x",
        "両辺を x で割って、x = 0 の解を落とした",
        r"$x^2 = kx$ の両辺を $x$ で割ると、$x = 0$ の場合を見落とします。$x(x - k) = 0$ と因数分解して $x = 0, k$ です。",
    ),
    Misconception(
        "eq_sqrt_one_root",
        "正の解（片方）だけを答えた",
        r"2 乗して $m$ になる数は $\pm\sqrt{m}$ の 2 つあります。負の解も忘れずに答えましょう。",
    ),
    Misconception(
        "eq_formula_sign_b",
        r"解の公式の $-b$ を $b$ とした",
        r"解の公式は $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$ です。$b$ の符号を変えて使います。",
    ),
    Misconception(
        "eq_formula_no_2a",
        r"解の公式の分母を $2a$ ではなく $a$ とした",
        r"解の公式の分母は $2a$ です。$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$",
    ),
    Misconception(
        "eq_formula_d_sign",
        r"判別式を $b^2 + 4ac$ とした",
        r"根号の中は $b^2 - 4ac$ です。$c$ が負のときは $-4ac$ が正になることにも注意しましょう。",
    ),
    Misconception(
        "eq_disc_no_4",
        r"判別式の $4ac$ の 4 を忘れた",
        r"判別式は $D = b^2 - 4ac$ です。重解をもつ条件は $D = 0$ です。",
    ),
    Misconception(
        "eq_abs_one_side",
        r"$|x - a| = b$ の解を 1 つだけ答えた",
        r"$|x - a| = b$ は「$x$ と $a$ の距離が $b$」なので、$x - a = \pm b$、つまり $x = a + b, a - b$ の 2 つです。",
    ),
    Misconception(
        "eq_abs_sign",
        r"$|x - a| = b$ を $x = -a \pm b$ とした",
        r"$|x - a| = b$ は $x - a = \pm b$ なので、$a$ を移項して $x = a \pm b$ です。",
    ),
]


def _p(v) -> str:
    return f"({v})" if v < 0 else str(v)


def _set(*vals) -> sp.FiniteSet:
    return sp.FiniteSet(*(sp.nsimplify(v) for v in vals))


def _build_linear(rng):
    """ax + b = cx + d。"""
    while True:
        a, c = nonzero(rng, -6, 6), nonzero(rng, -6, 6)
        if a != c:
            break
    x0 = rng.randint(-6, 6)
    b = nonzero(rng, -9, 9)
    d = a * x0 + b - c * x0
    answer = sp.Integer(x0)
    latex = rf"{to_latex(a * X + b)} = {to_latex(c * X + d)}"
    wrongs = [("eq_transpose_sign", sp.Rational(d + b, a - c))]  # 数の移項で符号を変え忘れた
    if a + c != 0:  # x の項の移項で符号を変え忘れた
        wrongs.append(("eq_transpose_sign", sp.Rational(d - b, a + c)))
    if d != b:
        wrongs.append(("eq_divide_inverted", sp.Rational(a - c, d - b)))
    steps = [
        rf"$x$ の項を左辺に、数を右辺に移項する（移した項は符号を変える）: ${a}x - {_p(c)}x = {d} - {_p(b)}$",
        rf"${a - c}x = {d - b}$ の両辺を ${a - c}$ で割る",
    ]
    return Built(answer, wrongs, steps, latex=latex, answer=answer, meta={"a": a, "b": b, "c": c, "d": d})


def _build_system(rng):
    """ax + by = p, cx + dy = q。"""
    while True:
        a, b, c, d = (nonzero(rng, -5, 5) for _ in range(4))
        x0, y0 = rng.randint(-5, 5), rng.randint(-5, 5)
        if a * d - b * c != 0 and x0 != y0:
            break
    p, q = a * x0 + b * y0, c * x0 + d * y0
    answer = sp.Tuple(x0, y0)
    latex = (
        rf"\begin{{cases}} {to_latex(a * X + b * Y)} = {p} \\ {to_latex(c * X + d * Y)} = {q} \end{{cases}}"
    )
    wrongs = [
        ("eq_system_swap", sp.Tuple(y0, x0)),
        # x を正しく求めたあと、1 つ目の式に代入して y を出すときに移項の符号を間違えた
        ("eq_transpose_sign", sp.Tuple(x0, sp.Rational(p + a * x0, b))),
    ]
    steps = [
        r"どちらかの文字の係数をそろえて、2 つの式を足すか引くかして 1 つの文字を消す（加減法）",
        rf"$x = {x0}$ が求まったら、1 つ目の式に代入する: ${b}y = {p} - {_p(a)} \times {_p(x0)}$ から $y = {y0}$",
    ]
    return Built(
        answer,
        wrongs,
        steps,
        latex=latex,
        answer=answer,
        prompt="次の連立方程式を解き、「x = 2, y = -1」のように答えなさい。",
        answer_prefix=r"(x,\ y) =",
        answer_latex=rf"({x0},\ {y0})",
        meta={"a": a, "b": b, "c": c, "d": d, "p": p, "q": q},
    )


def _build_quadratic_factor(rng):
    kind = rng.choice(["two", "two", "zero", "square"])
    if kind == "two":
        r1, r2 = rng.sample([n for n in range(-7, 8) if n != 0], 2)
        while r1 == -r2:
            r2 = rng.choice([n for n in range(-7, 8) if n not in (0, r1, -r1)])
        poly = sp.expand((X - r1) * (X - r2))
        latex = rf"{to_latex(poly)} = 0"
        answer = _set(r1, r2)
        wrongs = [("eq_root_sign", _set(-r1, -r2))]
        steps = [
            rf"左辺を因数分解する: $\left({to_latex(X - r1)}\right)\left({to_latex(X - r2)}\right) = 0$",
            rf"${to_latex(X - r1)} = 0$ または ${to_latex(X - r2)} = 0$",
        ]
        meta = {"poly": poly}
    elif kind == "zero":
        k = nonzero(rng, -9, 9)
        poly = X**2 - k * X
        latex = rf"x^2 = {to_latex(k * X)}"
        answer = _set(0, k)
        wrongs = [("eq_divide_by_x", _set(k)), ("eq_root_sign", _set(0, -k))]
        steps = [
            rf"右辺を移項して因数分解する: $x\left({to_latex(X - k)}\right) = 0$",
            "両辺を $x$ で割ってはいけない（$x = 0$ の解を落とす）",
        ]
        meta = {"poly": poly}
    else:
        m = rng.choice([2, 3, 5, 6, 7, 4, 9, 16, 25, 12, 8, 18])
        poly = X**2 - m
        latex = rf"x^2 = {m}"
        answer = _set(sp.sqrt(m), -sp.sqrt(m))
        wrongs = [("eq_sqrt_one_root", _set(sp.sqrt(m)))]
        steps = [rf"2 乗して ${m}$ になる数は $\pm\sqrt{{{m}}}$"]
        meta = {"poly": poly}
    return Built(poly, wrongs, steps, latex=latex, answer=answer, prompt=f"次の方程式を解きなさい。{MULTI_HINT}", meta=meta)


def _pm_latex(b, d, a2) -> str:
    """(-b ± √d) / a2 を約分した LaTeX。"""
    coef, rad = sp.sqrt(d).as_coeff_Mul()  # √d = coef √rad
    g = math.gcd(math.gcd(int(b), int(coef)), int(a2))
    nb, nc, den = -b // g, int(coef) // g, a2 // g
    if den < 0:
        nb, den = -nb, -den
    root = rf"{'' if nc == 1 else nc}{to_latex(rad)}"
    head = "" if nb == 0 else f"{nb} "
    top = rf"{head}\pm {root}"
    return top if den == 1 else rf"\frac{{{top}}}{{{den}}}"


def _build_quadratic_formula(rng):
    while True:
        a = rng.choice([1, 1, 2, 3])
        b, c = nonzero(rng, -7, 7), nonzero(rng, -6, 6)
        dsc = b * b - 4 * a * c
        if dsc > 0 and math.isqrt(dsc) ** 2 != dsc:
            break
    poly = a * X**2 + b * X + c
    roots = [(-b + s * sp.sqrt(dsc)) / (2 * a) for s in (1, -1)]
    answer = _set(*roots)
    wrongs = [("eq_formula_sign_b", _set(*[(b + s * sp.sqrt(dsc)) / (2 * a) for s in (1, -1)]))]
    if a != 1:
        wrongs.append(("eq_formula_no_2a", _set(*[(-b + s * sp.sqrt(dsc)) / a for s in (1, -1)])))
    d2 = b * b + 4 * a * c
    if d2 > 0:
        wrongs.append(("eq_formula_d_sign", _set(*[(-b + s * sp.sqrt(d2)) / (2 * a) for s in (1, -1)])))
    steps = [
        rf"解の公式 $x = \frac{{-b \pm \sqrt{{b^2 - 4ac}}}}{{2a}}$ に $a = {a},\ b = {b},\ c = {c}$ を代入する",
        rf"$b^2 - 4ac = {_p(b)}^2 - 4 \cdot {a} \cdot {_p(c)} = {dsc}$",
        r"根号の中を整理し、約分できれば約分する",
    ]
    return Built(
        poly,
        wrongs,
        steps,
        latex=rf"{to_latex(poly)} = 0",
        answer=answer,
        prompt=f"次の方程式を解きなさい。{MULTI_HINT}",
        answer_latex=_pm_latex(b, dsc, 2 * a),
        meta={"poly": poly},
    )


def _build_discriminant(rng):
    if rng.random() < 0.5:
        c = rng.randint(1, 6)
        latex = rf"x^2 + kx + {c * c} = 0"
        answer = _set(2 * c, -2 * c)
        wrongs = [("eq_sqrt_one_root", _set(2 * c)), ("eq_disc_no_4", _set(c, -c))]
        steps = [rf"重解をもつのは判別式 $D = k^2 - 4 \cdot {c * c} = 0$ のとき", rf"$k^2 = {4 * c * c}$ より $k = \pm {2 * c}$"]
        meta = {"kind": "k_middle", "c": c}
        prompt = f"$x$ の 2 次方程式 ${latex}$ が重解をもつような定数 $k$ の値を求めなさい。{MULTI_HINT}"
    else:
        b = nonzero(rng, -8, 8)
        latex = rf"{to_latex(X**2 + b * X)} + k = 0"
        answer = sp.Rational(b * b, 4)
        wrongs = [("eq_disc_no_4", sp.Integer(b * b)), ("eq_formula_d_sign", -sp.Rational(b * b, 4))]
        steps = [rf"重解をもつのは判別式 $D = {_p(b)}^2 - 4k = 0$ のとき", rf"$4k = {b * b}$ より $k = {to_latex(answer)}$"]
        meta = {"kind": "k_const", "b": b}
        prompt = f"$x$ の 2 次方程式 ${latex}$ が重解をもつような定数 $k$ の値を求めなさい。"
    return Built(answer, wrongs, steps, latex="", answer=answer, prompt=prompt, answer_prefix="k =", meta=meta)


def _build_abs(rng):
    a, b = nonzero(rng, -6, 6), rng.randint(1, 7)
    latex = rf"\left|{to_latex(X - a)}\right| = {b}"
    answer = _set(a + b, a - b)
    wrongs = [("eq_abs_one_side", _set(a + b)), ("eq_abs_sign", _set(-a + b, -a - b))]
    steps = [rf"${to_latex(X - a)} = \pm {b}$", rf"$x = {a} \pm {b}$"]
    return Built(
        answer,
        wrongs,
        steps,
        latex=latex,
        answer=answer,
        prompt=f"次の方程式を解きなさい。{MULTI_HINT}",
        meta={"a": a, "b": b},
    )


TYPES = [
    ProblemType("eq_linear", "equation", "1次方程式", r"$ax + b = cx + d$", _build_linear, level=1),
    ProblemType("eq_system", "equation", "連立方程式", r"加減法・代入法", _build_system, level=2),
    ProblemType("eq_quadratic_factor", "equation", "2次方程式（因数分解・平方根）", r"$(x - a)(x - b) = 0$、$x^2 = m$", _build_quadratic_factor, level=3, form="radical"),
    ProblemType("eq_quadratic_formula", "equation", "2次方程式（解の公式）", r"$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$", _build_quadratic_formula, level=3, form="radical"),
    ProblemType("eq_discriminant", "equation", "判別式と重解", r"$D = b^2 - 4ac = 0$", _build_discriminant, level=5),  # 数I「二次関数」（グラフと x 軸の共有点）
    ProblemType("eq_abs", "equation", "絶対値を含む方程式", r"$|x - a| = b$", _build_abs, level=4),
]
