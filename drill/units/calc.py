"""単元「式の計算」：正負の数・文字式・展開・因数分解・平方根（中学〜数I）。答えは数、または x の式。"""

import math

import sympy as sp

from ..checker import X
from ..core import Built, Misconception, ProblemType, Unit, nonzero, to_latex

UNIT = Unit(
    id="calc",
    name="式の計算",
    prompt="次の計算をしなさい。",
    answer_prefix="=",
)

MISCONCEPTIONS = [
    Misconception(
        "calc_order_ops",
        "掛け算より先に足し算・引き算をした",
        r"掛け算・割り算は、足し算・引き算より先に計算します。$a - b \times c$ は $a - (b \times c)$ です。",
    ),
    Misconception(
        "calc_minus_neg",
        "負の数を引くときに符号を変え忘れた",
        r"負の数を引くことは、その絶対値を足すことと同じです。$a - (-b) = a + b$ です。",
    ),
    Misconception(
        "calc_neg_square",
        r"$(-a)^2$ と $-a^2$ を取り違えた",
        r"$(-a)^2 = (-a) \times (-a) = a^2$ ですが、$-a^2 = -(a \times a)$ です。括弧があるかどうかで符号が変わります。",
    ),
    Misconception(
        "calc_minus_dist",
        "括弧の前のマイナスを、後ろの項に掛け忘れた",
        r"$-(a + b) = -a - b$ です。括弧の前の $-$ は、括弧の中のすべての項に掛かります。",
    ),
    Misconception(
        "calc_dist_first",
        "括弧の前の数を、最初の項にだけ掛けた",
        r"$k(a + b) = ka + kb$ です。括弧の前の数は、括弧の中のすべての項に掛けます（分配法則）。",
    ),
    Misconception(
        "calc_div_order",
        "割り算と掛け算を、後ろから計算した",
        r"掛け算・割り算だけの式は左から順に計算します。$a \div b \times c = \frac{a \times c}{b}$ で、"
        r"$\frac{a}{b \times c}$ ではありません。",
    ),
    Misconception(
        "calc_expand_no_middle",
        r"展開で $x$ の1次の項を忘れた",
        r"$(x + a)(x + b) = x^2 + (a + b)x + ab$ です。外側どうし・内側どうしの積 $bx$、$ax$ も足します。",
    ),
    Misconception(
        "calc_square_middle_once",
        r"$(x + a)^2$ の真ん中の項を $2ax$ ではなく $ax$ とした",
        r"$(x + a)^2 = x^2 + 2ax + a^2$ です。$ax$ が 2 回出てくるので 2 倍します。",
    ),
    Misconception(
        "calc_diff_squares_sign",
        r"$(x + a)(x - a)$ を $x^2 + a^2$ とした",
        r"$(x + a)(x - a) = x^2 - a^2$ です。$a \times (-a) = -a^2$ なので、定数項はマイナスです。",
    ),
    Misconception(
        "calc_factor_sign",
        "因数分解で符号を逆にした",
        r"$x^2 + (a + b)x + ab = (x + a)(x + b)$ です。展開して元の式に戻るか確かめましょう。",
    ),
    Misconception(
        "calc_factor_drop_common",
        "くくり出した共通因数を書き忘れた",
        r"最初にくくり出した数も、答えの式に残します。$k x^2 + \cdots = k(x + a)(x + b)$ です。",
    ),
    Misconception(
        "calc_factor_cross_swap",
        "たすき掛けで定数項の組み合わせを逆にした",
        r"$(px + q)(rx + s)$ を展開すると、$x$ の係数は $ps + qr$ です。たすき掛けで $x$ の係数が合う組み合わせを選びます。",
    ),
    Misconception(
        "calc_sqrt_add",
        r"$\sqrt{a} + \sqrt{b}$ を $\sqrt{a + b}$ とした",
        r"根号の中どうしを足すことはできません。$\sqrt{a^2 b} = a\sqrt{b}$ の形にしてから、同じ根号の項をまとめます。",
    ),
    Misconception(
        "calc_sqrt_square_out",
        r"根号の外に、2乗の数のまま出した",
        r"$\sqrt{a^2 b} = a\sqrt{b}$ です。根号の外に出るのは $a^2$ ではなく $a$ です。",
    ),
    Misconception(
        "calc_rat_no_denominator",
        "有理化で分母を掛け忘れた",
        r"分母と分子の両方に同じものを掛けます。$\frac{k}{\sqrt{a}} = \frac{k\sqrt{a}}{\sqrt{a}\sqrt{a}} = \frac{k\sqrt{a}}{a}$ です。",
    ),
    Misconception(
        "calc_rat_denominator_sum",
        r"$(\sqrt{a} - \sqrt{b})(\sqrt{a} + \sqrt{b})$ を $a + b$ とした",
        r"$(\sqrt{a} - \sqrt{b})(\sqrt{a} + \sqrt{b}) = a - b$ です（和と差の積）。",
    ),
    Misconception(
        "calc_rat_conjugate_sign",
        "分母と同じ式を掛けて有理化しようとした",
        r"$\sqrt{a} - \sqrt{b}$ を有理化するには、符号を変えた $\sqrt{a} + \sqrt{b}$ を分母と分子に掛けます。",
    ),
]


def _p(v) -> str:
    """負の数だけ括弧で囲む。"""
    return f"({v})" if v < 0 else str(v)


def _join(p, q) -> str:
    """p と q を足した形の LaTeX（q の符号をそのまま見せる）。"""
    lq = to_latex(q)
    return f"{to_latex(p)} {lq}" if lq.startswith("-") else f"{to_latex(p)} + {lq}"


def _built(f, answer, wrongs, steps, latex, prompt=None, answer_latex=None, meta=None) -> Built:
    return Built(
        f,
        wrongs,
        steps,
        latex=latex,
        answer=answer,
        prompt=prompt,
        answer_latex=answer_latex,
        meta=meta or {},
    )


def _build_signed(rng):
    """正負の数の四則と累乗。"""
    if rng.random() < 0.5:
        a, b, c = rng.randint(-9, 9), -rng.randint(2, 6), rng.randint(2, 6)
        answer = a - b * c
        latex = rf"{a} - {_p(b)} \times {c}"
        wrongs = [("calc_order_ops", (a - b) * c), ("calc_minus_neg", a + b * c)]
        steps = [rf"掛け算を先に計算する: ${_p(b)} \times {c} = {b * c}$", rf"${a} - {_p(b * c)} = {answer}$"]
        meta = {"kind": "sub_mul", "a": a, "b": b, "c": c}
    else:
        a, b = rng.randint(2, 6), rng.randint(2, 6)
        answer = a**2 - b**2
        latex = rf"(-{a})^2 - {b}^2"
        wrongs = [("calc_neg_square", -(a**2) - b**2), ("calc_neg_square", a**2 + b**2)]
        steps = [rf"$(-{a})^2 = (-{a}) \times (-{a}) = {a * a}$、${b}^2 = {b * b}$", rf"${a * a} - {b * b} = {answer}$"]
        meta = {"kind": "squares", "a": a, "b": b}
    return _built(sp.Integer(answer), sp.Integer(answer), [(m, sp.Integer(w)) for m, w in wrongs], steps, latex, meta=meta)


def _build_linear_expr(rng):
    """a(bx + c) - d(ex + f) を計算する。"""
    while True:
        a, d = rng.randint(2, 5), rng.randint(2, 5)
        b, e = rng.randint(1, 5), rng.randint(1, 5)
        if a * b != d * e:  # x の項が消えないようにする
            break
    c, f = nonzero(rng, -6, 6), nonzero(rng, -6, 6)
    expr = a * (b * X + c) - d * (e * X + f)
    answer = sp.expand(expr)
    latex = rf"{a}\left({to_latex(b * X + c)}\right) - {d}\left({to_latex(e * X + f)}\right)"
    wrongs = [
        ("calc_minus_dist", sp.expand(a * (b * X + c) - d * e * X + d * f)),
        ("calc_dist_first", sp.expand(a * b * X + c - (d * e * X + f))),
    ]
    steps = [
        rf"分配法則で括弧を外す（$-{d}$ は括弧の中の両方の項に掛ける）: "
        rf"${_join(sp.expand(a * (b * X + c)), sp.expand(-d * (e * X + f)))}$",
        r"同じ種類の項（$x$ の項どうし、数どうし）をまとめる",
    ]
    return _built(expr, answer, wrongs, steps, latex, meta={"expr": expr})


def _build_poly(rng):
    """(ax^2 + bx + c) - (dx^2 + ex + f) を計算する。"""
    a, d = rng.randint(1, 6), rng.randint(1, 6)
    b, e, c, f = (nonzero(rng, -7, 7) for _ in range(4))
    p1, p2 = a * X**2 + b * X + c, d * X**2 + e * X + f
    expr = p1 - p2
    answer = sp.expand(expr)
    latex = rf"\left({to_latex(p1)}\right) - \left({to_latex(p2)}\right)"
    wrongs = [
        ("calc_minus_dist", (a - d) * X**2 + (b + e) * X + (c + f)),
        ("calc_minus_dist", (a - d) * X**2 + (b - e) * X + (c + f)),
    ]
    steps = [
        rf"括弧の前の $-$ は全部の項に掛かる: ${_join(p1, -p2)}$",
        r"同じ次数の項をまとめる",
    ]
    return _built(expr, answer, wrongs, steps, latex, meta={"expr": expr})


def _build_monomial(rng):
    """A x^3 ÷ B x × C x の計算（割り算と掛け算は左から）。"""
    b, c = rng.randint(2, 4), rng.randint(2, 5)
    a = b * rng.randint(1, 4) * rng.choice([1, -1])
    m = rng.randint(2, 4)
    answer = sp.Integer(a) / b * c * X**m
    latex = rf"{a}x^{{{m}}} \div {b}x \times {c}x"
    wrongs = [("calc_div_order", sp.Rational(a, b * c) * X ** (m - 2))]
    steps = [
        rf"左から順に計算する: ${a}x^{{{m}}} \div {b}x = {to_latex(sp.Integer(a) / b * X ** (m - 1))}$",
        rf"${to_latex(sp.Integer(a) / b * X ** (m - 1))} \times {c}x = {to_latex(answer)}$",
    ]
    return _built(answer, answer, wrongs, steps, latex, meta={"expr": sp.Integer(a) * X**m / (b * X) * (c * X)})


def _build_expand(rng):
    kind = rng.choice(["product", "square", "diff", "general"])
    a = nonzero(rng, -6, 6)
    if kind == "product":
        b = rng.choice([n for n in range(-6, 7) if n not in (0, a, -a)])
        expr = (X + a) * (X + b)
        wrongs = [("calc_expand_no_middle", X**2 + a * b)]
        steps = [rf"$(x + a)(x + b) = x^2 + (a + b)x + ab$ で $a = {a},\ b = {b}$"]
    elif kind == "square":
        expr = (X + a) ** 2
        wrongs = [("calc_expand_no_middle", X**2 + a**2), ("calc_square_middle_once", X**2 + a * X + a**2)]
        steps = [rf"$(x + a)^2 = x^2 + 2ax + a^2$ で $a = {a}$"]
    elif kind == "diff":
        a = abs(a)
        expr = (X + a) * (X - a)
        wrongs = [("calc_diff_squares_sign", X**2 + a**2), ("calc_square_middle_once", X**2 - 2 * a * X - a**2)]
        steps = [rf"$(x + a)(x - a) = x^2 - a^2$ で $a = {a}$"]
    else:
        p, r = rng.randint(2, 4), rng.randint(1, 3)
        b = nonzero(rng, -5, 5)
        expr = (p * X + a) * (r * X + b)
        wrongs = [("calc_expand_no_middle", p * r * X**2 + a * b)]
        steps = [rf"$(px + q)(rx + s) = prx^2 + (ps + qr)x + qs$ で $p = {p},\ q = {a},\ r = {r},\ s = {b}$"]
    latex = _factored_latex(expr)
    answer = sp.expand(expr)
    return _built(expr, answer, wrongs, steps, latex, prompt="次の式を展開しなさい。", meta={"expr": expr})


def _factored_latex(expr: sp.Expr) -> str:
    """(x + 2)(x - 3) のような積を、因数の順番を保ったまま LaTeX にする。"""
    parts = []
    coeff = 1
    for factor in sp.Mul.make_args(expr):
        if factor.is_Number:
            coeff *= factor
            continue
        base, exp = (factor.base, factor.exp) if isinstance(factor, sp.Pow) else (factor, 1)
        s = rf"\left({to_latex(base)}\right)"
        parts.append(s + (f"^{{{exp}}}" if exp != 1 else ""))
    head = "" if coeff == 1 else "-" if coeff == -1 else to_latex(coeff)
    return head + "".join(parts)


def _build_factor(rng):
    kind = rng.choice(["product", "common", "square", "diff"])
    a = nonzero(rng, -7, 7)
    if kind == "product":
        b = rng.choice([n for n in range(-7, 8) if n not in (0, a, -a)])
        answer = (X + a) * (X + b)
        wrongs = [("calc_factor_sign", (X - a) * (X - b))]
        steps = [rf"足して ${a + b}$、掛けて ${a * b}$ になる 2 数は ${a}$ と ${b}$"]
    elif kind == "common":
        k = rng.randint(2, 4)
        b = rng.choice([n for n in range(-6, 7) if n not in (0, a, -a)])
        # 数と和の積は SymPy が展開してしまう（4(x + 7) → 4x + 28）ので、掛けた形のまま持つ
        answer = sp.Mul(k, X + a, X + b, evaluate=False)
        wrongs = [
            ("calc_factor_drop_common", (X + a) * (X + b)),
            ("calc_factor_sign", sp.Mul(k, X - a, X - b, evaluate=False)),
        ]
        steps = [
            rf"まず共通因数 ${k}$ をくくり出す: ${k}\left({to_latex(sp.expand((X + a) * (X + b)))}\right)$",
            rf"足して ${a + b}$、掛けて ${a * b}$ になる 2 数は ${a}$ と ${b}$",
        ]
    elif kind == "square":
        answer = (X + a) ** 2
        wrongs = [("calc_factor_sign", (X - a) ** 2)]
        steps = [rf"$x^2 + 2ax + a^2 = (x + a)^2$ の形で、$a = {a}$"]
    else:
        a = abs(a)
        answer = (X + a) * (X - a)
        wrongs = [("calc_factor_sign", (X - a) ** 2), ("calc_factor_sign", (X + a) ** 2)]
        steps = [rf"$x^2 - a^2 = (x + a)(x - a)$ の形で、$a = {a}$"]
    expanded = sp.expand(answer)
    return _built(
        expanded,
        answer,
        wrongs,
        steps,
        to_latex(expanded),
        prompt="次の式を因数分解しなさい。",
        answer_latex=_factored_latex(answer),
        meta={"expanded": expanded},
    )


def _build_factor_cross(rng):
    """たすき掛け (px + q)(rx + s)。"""
    while True:
        p, r = rng.choice([(2, 1), (3, 1), (2, 3), (3, 2), (1, 2), (1, 3), (2, 5), (5, 2)])
        q, s = nonzero(rng, -5, 5), nonzero(rng, -5, 5)
        if math.gcd(p, q) == 1 and math.gcd(r, s) == 1 and p * s + q * r != 0:
            break
    answer = (p * X + q) * (r * X + s)
    expanded = sp.expand(answer)
    wrongs = [("calc_factor_cross_swap", (p * X + s) * (r * X + q)), ("calc_factor_sign", (p * X - q) * (r * X - s))]
    steps = [
        rf"$x^2$ の係数 ${p * r} = {p} \times {r}$、定数項 ${q * s} = {_p(q)} \times {_p(s)}$ に分ける",
        rf"たすき掛けで $x$ の係数を確かめる: ${p} \times {_p(s)} + {_p(q)} \times {r} = {p * s + q * r}$",
    ]
    return _built(
        expanded,
        answer,
        wrongs,
        steps,
        to_latex(expanded),
        prompt="次の式を因数分解しなさい。",
        answer_latex=_factored_latex(answer),
        meta={"expanded": expanded},
    )


_SQUAREFREE = [2, 3, 5, 6, 7]


def _build_sqrt(rng):
    """√(a²s) ± √(b²s) を簡単にする。"""
    s = rng.choice(_SQUAREFREE)
    a, b = rng.sample(range(1, 6), 2)
    sign = rng.choice([1, -1])
    m, n = a * a * s, b * b * s
    answer = (a + sign * b) * sp.sqrt(s)
    op = "+" if sign > 0 else "-"
    latex = rf"\sqrt{{{m}}} {op} \sqrt{{{n}}}"
    wrongs = [("calc_sqrt_square_out", (a * a + sign * b * b) * sp.sqrt(s))]
    if m + sign * n > 0:
        wrongs.insert(0, ("calc_sqrt_add", sp.sqrt(m + sign * n)))
    steps = [
        rf"$\sqrt{{{m}}} = \sqrt{{{a}^2 \times {s}}} = {a if a > 1 else ''}\sqrt{{{s}}}$、"
        rf"$\sqrt{{{n}}} = {b if b > 1 else ''}\sqrt{{{s}}}$",
        rf"同じ根号の項をまとめる: $({a} {op} {b})\sqrt{{{s}}}$",
    ]
    return _built(answer, answer, wrongs, steps, latex, meta={"m": m, "n": n, "sign": sign})


_RAT_PAIRS = [(3, 2), (5, 2), (5, 3), (6, 5), (7, 3), (7, 5), (6, 2), (7, 6)]


def _build_rationalize(rng):
    if rng.random() < 0.4:
        a = rng.choice(_SQUAREFREE)
        k = rng.choice([n for n in range(1, 13) if n % a != 0] + [a * rng.randint(1, 3)])
        given = sp.Integer(k) / sp.sqrt(a)
        latex = rf"\frac{{{k}}}{{\sqrt{{{a}}}}}"
        wrongs = [("calc_rat_no_denominator", k * sp.sqrt(a))]
        steps = [rf"分母と分子に $\sqrt{{{a}}}$ を掛ける: $\frac{{{k}\sqrt{{{a}}}}}{{{a}}}$", "約分できれば約分する"]
        meta = {"kind": "single", "k": k, "a": a}
    else:
        a, b = rng.choice(_RAT_PAIRS)
        k = (a - b) * rng.randint(1, 3) if rng.random() < 0.6 else rng.randint(1, 6)
        given = sp.Integer(k) / (sp.sqrt(a) - sp.sqrt(b))
        latex = rf"\frac{{{k}}}{{\sqrt{{{a}}} - \sqrt{{{b}}}}}"
        wrongs = [
            ("calc_rat_denominator_sum", k * (sp.sqrt(a) + sp.sqrt(b)) / (a + b)),
            ("calc_rat_conjugate_sign", k * (sp.sqrt(a) - sp.sqrt(b)) / (a - b)),
        ]
        steps = [
            rf"分母と分子に $\sqrt{{{a}}} + \sqrt{{{b}}}$ を掛ける",
            rf"分母は $(\sqrt{{{a}}} - \sqrt{{{b}}})(\sqrt{{{a}}} + \sqrt{{{b}}}) = {a} - {b} = {a - b}$",
        ]
        meta = {"kind": "pair", "k": k, "a": a, "b": b}
    answer = sp.radsimp(given)
    return _built(given, answer, wrongs, steps, latex, prompt="次の式の分母を有理化しなさい。", meta=meta)


TYPES = [
    ProblemType("calc_signed", "calc", "正負の数の計算", r"$a - (-b) \times c$、$(-a)^2$", _build_signed, level=1),
    ProblemType("calc_linear_expr", "calc", "文字式の計算", r"$a(bx + c) - d(ex + f)$", _build_linear_expr, level=1, form="expanded"),
    ProblemType("calc_poly", "calc", "多項式の加法・減法", r"$(ax^2 + bx + c) - (dx^2 + ex + f)$", _build_poly, level=2, form="expanded"),
    ProblemType("calc_monomial", "calc", "単項式の乗法・除法", r"$ax^3 \div bx \times cx$", _build_monomial, level=2),
    ProblemType("calc_expand", "calc", "式の展開", r"$(x + a)(x + b)$、$(x + a)^2$ など", _build_expand, level=3, form="expanded"),
    ProblemType("calc_factor", "calc", "因数分解", r"$x^2 + (a + b)x + ab = (x + a)(x + b)$ など", _build_factor, level=3, form="factored"),
    ProblemType("calc_sqrt", "calc", "平方根の計算", r"$\sqrt{a^2 b} = a\sqrt{b}$", _build_sqrt, level=3, form="radical"),
    ProblemType("calc_factor_cross", "calc", "たすき掛けの因数分解", r"$(px + q)(rx + s)$", _build_factor_cross, level=4, form="factored"),
    ProblemType("calc_rationalize", "calc", "分母の有理化", r"$\frac{k}{\sqrt{a} - \sqrt{b}}$", _build_rationalize, level=4, form="radical"),
]
