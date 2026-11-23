"""答えの形の判定。値は正しくても、問われた形になっていなければ正解にしない。

SymPy は読み取った時点で √12 を 2√3 にするなど式を整えてしまうので、
書いた形のまま読み取った式（evaluate=False）を調べる。
- expanded: 展開しきっている（括弧のついた和の積・累乗が残っていない）
- factored: 因数分解しきっている（和の形でない。どの因数もこれ以上分解できず、共通因数も残っていない）
- radical: 根号を整理している（根号の中に平方数の因数が残っていない、分母に根号がない、同じ根号の項をまとめている）
"""

import sympy as sp

from .checker import X, answer_parts, parse_single
from .core import Misconception

MISCONCEPTIONS = [
    Misconception(
        "form_not_expanded",
        "展開しきっていない",
        r"値は合っていますが、括弧が残っています。分配法則で括弧を外し、同じ次数の項をまとめた形で答えましょう。",
    ),
    Misconception(
        "form_not_factored",
        "因数分解しきっていない",
        r"値は合っていますが、まだ因数分解できます。共通因数をくくり出し、どの因数もこれ以上分解できない形で答えましょう。",
    ),
    Misconception(
        "form_radical_not_simplified",
        "根号を整理していない",
        r"値は合っていますが、根号が整理されていません。$\sqrt{a^2 b} = a\sqrt{b}$ のように根号の中を小さくし、"
        r"分母の根号は有理化し、同じ根号の項はまとめて答えましょう。",
    ),
]

MESSAGES = {m.id: m for m in MISCONCEPTIONS}


def _not_expanded(e: sp.Basic) -> bool:
    for node in sp.preorder_traversal(e):
        # x を含む和に何かを掛けている（定数だけの括弧 2(3+1) などは問わない）
        if isinstance(node, sp.Mul) and any(isinstance(a, sp.Add) and a.has(X) for a in node.args):
            return True
        # 先頭の -(x - 3) は読み取りの時点で 3 - x に配られ、和の中の和として残る
        if isinstance(node, sp.Add) and any(isinstance(a, sp.Add) and a.has(X) for a in node.args):
            return True
        if isinstance(node, sp.Pow) and isinstance(node.base, sp.Add) and node.base.has(X):
            if node.exp.is_Integer and node.exp > 1:
                return True
    return False


def _factors(e: sp.Basic) -> list[sp.Basic]:
    """書いた形の積を、掛けている因数（累乗は底）に分ける。"""
    if isinstance(e, sp.Mul):
        return [f for a in e.args for f in _factors(a)]
    if isinstance(e, sp.Pow) and e.exp.is_Integer and e.exp > 0:
        return _factors(e.base)
    return [e]


def _factored(e: sp.Basic) -> bool:
    """e（書いた形のまま読んだ式）が、これ以上因数分解できない形か。

    evaluate すると 4(x + 7) が 4x + 28 になってしまうので、書いた形で調べる。
    """
    if isinstance(e, sp.Add):
        return False
    for base in _factors(e):
        if not base.has(X) or not isinstance(base, sp.Add):
            continue
        poly = sp.Poly(base, X)
        if abs(poly.content()) != 1:  # 2x + 4 のように共通因数が残っている
            return False
        _, factors = sp.factor_list(base)
        if len(factors) > 1 or any(m > 1 for _, m in factors):
            return False
    return True


def _square_factor(n: sp.Integer) -> bool:
    return any(m >= 2 for m in sp.factorint(abs(int(n))).values())


def _radical_not_simplified(e: sp.Basic) -> bool:
    for node in sp.preorder_traversal(e):
        if isinstance(node, sp.Pow):
            if node.exp == sp.Rational(1, 2) and node.base.is_Integer and _square_factor(node.base):
                return True  # √12 のように平方数の因数が残っている
            if node.exp.is_negative and any(
                isinstance(s, sp.Pow) and s.exp == sp.Rational(1, 2) for s in sp.preorder_traversal(node.base)
            ):
                return True  # 分母に根号がある
    # 同じ根号の項がまとまっていない（2√3 + √3 など）
    for node in sp.preorder_traversal(e):
        if isinstance(node, sp.Add):
            radicals = []
            for term in node.args:
                rs = frozenset(
                    s.base for s in sp.preorder_traversal(term) if isinstance(s, sp.Pow) and s.exp == sp.Rational(1, 2)
                )
                if rs:
                    radicals.append(rs)
            if len(radicals) != len(set(radicals)):
                return True
    return False


def check_form(kind: str | None, text: str) -> str | None:
    """問われた形になっていなければ、その誤答パターンの ID を返す。値が正しいことは確かめてある前提。"""
    if kind is None:
        return None
    for part in answer_parts(text):
        raw = parse_single(part, evaluate=False)
        if kind == "expanded" and _not_expanded(raw):
            return "form_not_expanded"
        if kind == "factored" and not _factored(raw):
            return "form_not_factored"
        if kind == "radical" and _radical_not_simplified(raw):
            return "form_radical_not_simplified"
    return None
