"""単元「三角比」：三角比の値・正弦定理・余弦定理（数I）。"""

import sympy as sp

from ..core import Built, Misconception, ProblemType, Unit, to_latex

UNIT = Unit(
    id="trig",
    name="三角比",
    prompt="次の値を求めなさい。",
    answer_prefix="=",
)

MISCONCEPTIONS = [
    Misconception(
        "trig_sin_cos_swap",
        "sin と cos を取り違えた",
        r"直角三角形で、$\sin\theta = \frac{\text{対辺}}{\text{斜辺}}$、$\cos\theta = \frac{\text{隣辺}}{\text{斜辺}}$ です。"
        r"単位円では $\cos\theta$ が $x$ 座標、$\sin\theta$ が $y$ 座標です。",
    ),
    Misconception(
        "trig_reciprocal",
        "分母と分子を逆にした",
        r"$\sin\theta = \frac{\text{対辺}}{\text{斜辺}}$ のように、斜辺は分母です。$\tan\theta = \frac{\sin\theta}{\cos\theta}$ です。",
    ),
    Misconception(
        "trig_obtuse_sign",
        "鈍角の三角比の符号を間違えた",
        r"$90^\circ < \theta < 180^\circ$ では、$\sin\theta > 0$、$\cos\theta < 0$、$\tan\theta < 0$ です。"
        r"$\cos(180^\circ - \theta) = -\cos\theta$ を使いましょう。",
    ),
    Misconception(
        "trig_cos_law_sign",
        r"余弦定理の $-2bc\cos A$ の符号を間違えた",
        r"余弦定理は $a^2 = b^2 + c^2 - 2bc\cos A$ です。$A$ が鈍角なら $\cos A < 0$ なので、$-2bc\cos A$ は正になります。",
    ),
    Misconception(
        "trig_forgot_sqrt",
        r"$a^2$ を求めたところで止めた",
        r"余弦定理で求まるのは $a^2$ です。最後に平方根をとって $a$ を求めます。",
    ),
    Misconception(
        "trig_sine_law_inverted",
        "正弦定理で sin の比を逆にした",
        r"正弦定理は $\frac{a}{\sin A} = \frac{b}{\sin B}$ なので、$b = \frac{a \sin B}{\sin A}$ です。",
    ),
]

_ANGLES = [30, 45, 60, 120, 135, 150]
_FUNCS = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan}


def _value(func: str, deg: int) -> sp.Expr:
    return sp.nsimplify(_FUNCS[func](sp.pi * deg / 180))


def _build_value(rng):
    func, deg = rng.choice(list(_FUNCS)), rng.choice(_ANGLES)
    answer = _value(func, deg)
    wrongs = []
    if func in ("sin", "cos"):
        other = "cos" if func == "sin" else "sin"
        wrongs.append(("trig_sin_cos_swap", _value(other, deg)))
    wrongs.append(("trig_reciprocal", sp.radsimp(1 / answer)))
    if deg > 90:
        wrongs.append(("trig_obtuse_sign", -answer))
    steps = (
        [rf"$\{func} {deg}^\circ = {'' if func == 'sin' else '-'}\{func} {180 - deg}^\circ$（$180^\circ - \theta$ の公式）"]
        if deg > 90
        else []
    ) + [r"$30^\circ$・$45^\circ$・$60^\circ$ の三角比は、2 つの直角三角形（辺の比 $1 : 1 : \sqrt{2}$ と $1 : \sqrt{3} : 2$）から求める"]
    return Built(
        answer,
        wrongs,
        steps,
        latex=rf"\{func} {deg}^\circ",
        answer=answer,
        meta={"func": func, "deg": deg},
    )


def _build_cosine_law(rng):
    b, c = rng.sample(range(2, 9), 2)
    deg = rng.choice([60, 120])
    cos_a = sp.Rational(1, 2) if deg == 60 else sp.Rational(-1, 2)
    a2 = b * b + c * c - 2 * b * c * cos_a
    answer = sp.sqrt(a2)
    wrongs = [
        ("trig_cos_law_sign", sp.sqrt(b * b + c * c + 2 * b * c * cos_a)),
        ("trig_forgot_sqrt", sp.Integer(a2)),
    ]
    steps = [
        rf"余弦定理 $a^2 = b^2 + c^2 - 2bc\cos A$ に代入する: $a^2 = {b}^2 + {c}^2 - 2 \cdot {b} \cdot {c} \cdot \left({to_latex(cos_a)}\right) = {a2}$",
        rf"$a > 0$ なので $a = \sqrt{{{a2}}}$（整理できれば整理する）",
    ]
    return Built(
        answer,
        wrongs,
        steps,
        latex="",
        answer=answer,
        prompt=rf"$\triangle\mathrm{{ABC}}$ において、$b = {b}$、$c = {c}$、$A = {deg}^\circ$ のとき、$a$ を求めなさい。",
        answer_prefix="a =",
        meta={"b": b, "c": c, "deg": deg},
    )


def _build_sine_law(rng):
    while True:
        da, db = rng.sample([30, 45, 60, 90, 120, 135], 2)
        if da + db < 180:
            break
    a = rng.randint(2, 8)
    sa, sb = _value("sin", da), _value("sin", db)
    answer = sp.radsimp(a * sb / sa)
    wrongs = [("trig_sine_law_inverted", sp.radsimp(a * sa / sb))]
    steps = [
        r"正弦定理 $\frac{a}{\sin A} = \frac{b}{\sin B}$ より $b = \frac{a \sin B}{\sin A}$",
        rf"$b = \frac{{{a} \cdot {to_latex(sb)}}}{{{to_latex(sa)}}}$ を計算し、分母に根号があれば有理化する",
    ]
    return Built(
        answer,
        wrongs,
        steps,
        latex="",
        answer=answer,
        prompt=rf"$\triangle\mathrm{{ABC}}$ において、$a = {a}$、$A = {da}^\circ$、$B = {db}^\circ$ のとき、$b$ を求めなさい。",
        answer_prefix="b =",
        meta={"a": a, "A": da, "B": db},
    )


TYPES = [
    ProblemType("trig_value", "trig", "三角比の値", r"$0^\circ$〜$180^\circ$ の有名角の sin・cos・tan", _build_value, level=5),
    ProblemType("trig_cosine_law", "trig", "余弦定理", r"$a^2 = b^2 + c^2 - 2bc\cos A$", _build_cosine_law, level=5, form="radical"),
    ProblemType("trig_sine_law", "trig", "正弦定理", r"$\frac{a}{\sin A} = \frac{b}{\sin B}$", _build_sine_law, level=5, form="radical"),
]
