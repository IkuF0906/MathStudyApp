"""解答文字列の解析と、数式の等価判定。"""

import re

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

# 問題・解答で共通に使う変数。正の実数にしておくと ln や √ の簡約が素直になる
X = sp.Symbol("x", positive=True)
# 数列の項の番号
N = sp.Symbol("n", positive=True)
# 不定積分の積分定数
C = sp.Symbol("C")

LOCAL_NAMES = {
    "x": X,
    "n": N,
    "C": C,
    "oo": sp.oo,
    "inf": sp.oo,
    "e": sp.E,
    "pi": sp.pi,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "sec": sp.sec,
    "csc": sp.csc,
    "cot": sp.cot,
    "ln": sp.log,
    "log": sp.log,
    "exp": sp.exp,
    "sqrt": sp.sqrt,
}
# 長い名前から順に当てはめて "xsinx" を "x sin x" に分割する
_WORDS_LONGEST_FIRST = sorted(LOCAL_NAMES, key=len, reverse=True)

_ALLOWED_CHARS = re.compile(r"^[0-9A-Za-z+\-*/^().\s]*$")
_UNICODE_REPLACEMENTS = {
    "−": "-",
    "·": "*",
    "⋅": "*",
    "×": "*",
    "÷": "/",
    "π": "pi",
    "√": "sqrt",
    "∞": "oo",
}
_TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

# 数値による等価判定で x に代入する点（特殊な値を避けた正の数）
_SAMPLE_POINTS = (0.37, 0.81, 1.29, 1.73, 2.41, 3.17)


class AnswerParseError(ValueError):
    """解答を数式として解釈できなかった。message は利用者向けの日本語。"""


def _split_word(word: str) -> list[str]:
    parts = []
    i = 0
    while i < len(word):
        for name in _WORDS_LONGEST_FIRST:
            if word.startswith(name, i):
                parts.append(name)
                i += len(name)
                break
        else:
            raise AnswerParseError(f"「{word}」は使えない記号です。使える文字: x, e, pi, sin, cos, tan, ln, sqrt など")
    return parts


def normalize(text: str) -> str:
    for src, dst in _UNICODE_REPLACEMENTS.items():
        text = text.replace(src, dst)
    if not _ALLOWED_CHARS.match(text):
        raise AnswerParseError("使えない文字が含まれています")
    # 英字の並びを既知の名前に分割する。名前の一覧以外は通さないので eval されても安全
    return re.sub(r"[A-Za-z]+", lambda m: " ".join(_split_word(m.group())) + " ", text)


def _split_top_level(text: str) -> list[str]:
    """括弧の外にあるコンマで区切る。"""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


def _strip_outer_parens(text: str) -> str:
    """「(2, -3)」のように全体を囲む括弧があり、中にコンマがあれば外す。"""
    if not (text.startswith("(") and text.endswith(")")):
        return text
    depth = 0
    for i, ch in enumerate(text):
        depth += ch == "("
        depth -= ch == ")"
        if depth == 0 and i < len(text) - 1:
            return text  # 先頭の括弧が途中で閉じている（(x+1)(x+2) など）
    inner = text[1:-1]
    return inner if len(_split_top_level(inner)) > 1 else text


def answer_parts(text: str) -> list[str]:
    """解答を、答え1つずつの文字列に分ける。

    「x = 2, -3」「(2, -3)」「x = 2, y = -1」のようにコンマで区切った複数の答えと、
    「1 ± √2」（MathLive からは "+-" で届く）の ± を2つの答えに分ける。各答えの「x =」などの左辺は除く。
    """
    text = (text or "").strip()
    for src in ("、", "，"):
        text = text.replace(src, ",")
    text = _strip_outer_parens(text)
    parts = []
    for part in _split_top_level(text):
        # 「y = 2x + 1」「F(x) = ...」のように左辺ごと書かれたときは右辺だけを使う
        part = part.rpartition("=")[2].strip()
        if not part:
            raise AnswerParseError("コンマの前後に答えがありません" if "," in text else "解答が空です")
        part = part.replace("+-", "±").replace("\\pm", "±")
        if "±" in part:
            parts += [part.replace("±", "+", 1), part.replace("±", "-", 1)]
        else:
            parts.append(part)
    return parts


def parse_single(text: str, evaluate: bool = True) -> sp.Expr:
    """答え1つ分の文字列を式にする。evaluate=False は書いた形のまま読む（答えの形を調べるため）。"""
    normalized = normalize(text)
    try:
        expr = parse_expr(
            normalized, local_dict=dict(LOCAL_NAMES), transformations=_TRANSFORMATIONS, evaluate=evaluate
        )
    except Exception as exc:
        raise AnswerParseError("数式として読み取れませんでした。括弧や演算子を確認してください") from exc
    if not isinstance(expr, sp.Expr) or (expr.free_symbols - {X, N, C}):
        raise AnswerParseError("x（数列では n）の式として読み取れませんでした")
    return expr


def parse_answer(text: str) -> sp.Expr | sp.Tuple:
    """解答を式にする。答えが複数あるとき（コンマ区切り・±）は、書いた順の sp.Tuple にする。"""
    exprs = [parse_single(part) for part in answer_parts(text)]
    return exprs[0] if len(exprs) == 1 else sp.Tuple(*exprs)


def _value(expr: sp.Expr, point: float) -> complex | None:
    try:
        v = complex(expr.subs({X: point, N: point}).evalf())
    except (TypeError, ValueError):
        return None
    if v != v or abs(v) == float("inf"):
        return None
    return v


def _items(v) -> list:
    return list(v.args) if isinstance(v, (sp.Tuple, sp.FiniteSet)) else [v]


def equivalent(a, b) -> bool:
    """a と b が x（数列では n）の関数として等しいか。

    数値代入で判定し、評価できる点が足りないときだけ記号的な簡約に頼る
    （simplify は遅く、等しくても 0 にならないことがあるため）。
    答えが複数あるとき、sp.FiniteSet（方程式の解など）は順番を問わず、
    sp.Tuple（連立方程式の x, y や頂点の座標）は順番どおりに比べる。
    """
    if isinstance(a, sp.FiniteSet) or isinstance(b, sp.FiniteSet):
        xs, ys = _items(a), _items(b)
        return all(any(equivalent(x, y) for y in ys) for x in xs) and all(
            any(equivalent(x, y) for x in xs) for y in ys
        )
    if isinstance(a, sp.Tuple) or isinstance(b, sp.Tuple):
        xs, ys = _items(a), _items(b)
        return (
            isinstance(a, sp.Tuple)
            and isinstance(b, sp.Tuple)
            and len(xs) == len(ys)
            and all(equivalent(x, y) for x, y in zip(xs, ys))
        )
    # 極限の答えの ∞ は数値で比べられないので、そのまま比べる
    if a.has(sp.oo, -sp.oo, sp.zoo) or b.has(sp.oo, -sp.oo, sp.zoo):
        return a == b
    checked = 0
    for p in _SAMPLE_POINTS:
        va, vb = _value(a, p), _value(b, p)
        if va is None or vb is None:
            continue
        if abs(va - vb) > 1e-9 * max(1.0, abs(va), abs(vb)):
            return False
        checked += 1
    if checked >= 3:
        return True
    return sp.simplify(a - b) == 0
