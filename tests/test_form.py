"""答えの形の判定（展開しきったか・因数分解しきったか・根号を整理したか）。"""

import pytest

from drill.form import check_form


@pytest.mark.parametrize(
    "kind, text, expected",
    [
        ("expanded", "x^2+5x+6", None),
        ("expanded", "(x+2)(x+3)", "form_not_expanded"),
        ("expanded", "(x+1)^2", "form_not_expanded"),
        ("expanded", "-(x-3)+2x", "form_not_expanded"),
        ("expanded", "2-(x-3)", "form_not_expanded"),
        ("expanded", "2(3+1)x", None),  # 数だけの括弧は問わない
        ("factored", "(x+2)(x+3)", None),
        ("factored", "4(x+7)(x-2)", None),
        ("factored", "(x-3)^2", None),
        ("factored", "(2x+1)(x+3)", None),
        ("factored", "x^2+5x+6", "form_not_factored"),
        ("factored", "(x-2)(4x+28)", "form_not_factored"),  # 共通因数が残っている
        ("factored", "(x^2-4)(x+1)", "form_not_factored"),  # まだ分解できる
        ("radical", "7sqrt(5)", None),
        ("radical", "(sqrt(3))/(3)", None),
        ("radical", "(3+sqrt(33))/6", None),
        ("radical", "sqrt(245)", "form_radical_not_simplified"),
        ("radical", "1/sqrt(3)", "form_radical_not_simplified"),
        ("radical", "3sqrt(5)+4sqrt(5)", "form_radical_not_simplified"),
        ("radical", "2, sqrt(8)", "form_radical_not_simplified"),  # 複数の答えはどれも調べる
        (None, "sqrt(245)", None),
    ],
)
def test_check_form(kind, text, expected):
    assert check_form(kind, text) == expected
