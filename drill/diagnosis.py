"""利用者の解答を正解・誤答パターンと照合する。"""

from dataclasses import dataclass

import sympy as sp

from .checker import C
from .form import check_form
from .templates import MISCONCEPTIONS, Misconception, Problem


@dataclass
class Diagnosis:
    correct: bool
    misconception: Misconception | None  # 不正解で、どの誤答パターンにも一致しなければ None
    note: str | None = None  # 正誤とは別の注意（積分定数の書き忘れなど）


def diagnose(problem: Problem, user_expr, text: str | None = None) -> Diagnosis:
    """text は利用者が書いた解答の文字列。あれば、答えの形（展開しきったかなど）も確かめる。"""
    same = problem.unit.same
    if same(user_expr, problem.answer):
        bad_form = check_form(problem.form, text) if text is not None else None
        if bad_form:
            return Diagnosis(correct=False, misconception=MISCONCEPTIONS[bad_form])
        note = None
        if problem.unit.needs_constant and not user_expr.has(C):
            note = r"積分定数 $C$ が書かれていません。不定積分では $+C$ を付けましょう。"
        return Diagnosis(correct=True, misconception=None, note=note)
    for mid, wrong in problem.wrongs:
        if same(user_expr, wrong):
            return Diagnosis(correct=False, misconception=MISCONCEPTIONS[mid])
    return Diagnosis(correct=False, misconception=None)
