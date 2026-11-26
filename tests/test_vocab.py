"""語彙チェック（static/vocab.js）の単語データの検査。

くり返し受けても同じ語が出にくいよう各レベルに十分な語があること、
選択肢が紛らわしくならないよう、同じ語・近いレベルの同じ意味の語がないことを確かめる。
"""

import json
import re
from pathlib import Path

import pytest

SRC = (Path(__file__).resolve().parent.parent / "static" / "vocab.js").read_text(encoding="utf-8")
ENTRY = re.compile(r'\["([^"]+)","([^"]+)",(\d+)(?:,"([a-z])")?\]')
MIN_PER_LEVEL = 40  # 2回受けたときに重なる語が 20 語中 3 語ほどになる数（シミュレーションで確かめた）


def words(lang: str) -> list[tuple[str, str, int, str | None]]:
    start = SRC.index(" ja:{") if lang == "ja" else SRC.index(" en:{")
    end = SRC.index(" en:{") if lang == "ja" else SRC.index("\n};", start)
    return [(w, m, int(lv), pos or None) for w, m, lv, pos in ENTRY.findall(SRC[start:end])]


@pytest.mark.parametrize("lang, levels", [("ja", 11), ("en", 7)])
def test_enough_words_per_level(lang, levels):
    counts = {}
    for _, _, lv, _ in words(lang):
        counts[lv] = counts.get(lv, 0) + 1
    assert sorted(counts) == list(range(1, levels + 1))
    assert min(counts.values()) >= MIN_PER_LEVEL, counts


@pytest.mark.parametrize("lang", ["ja", "en"])
def test_no_duplicates(lang):
    ws = words(lang)
    names = [w for w, _, _, _ in ws]
    assert len(names) == len(set(names))
    # 同じ意味の語が近いレベル（±2）にあると、同じ問題の選択肢に並んで紛らわしい
    seen: dict[tuple[str, str | None], int] = {}
    for w, m, lv, pos in ws:
        key = (m, pos)
        assert key not in seen or abs(seen[key] - lv) > 2, f"{w}: {m}"
        seen[key] = lv


def test_english_has_parts_of_speech_and_enough_choices():
    ws = words("en")
    assert all(pos in ("n", "v", "a") for _, _, _, pos in ws)
    # 誤答の選択肢は、近いレベル（±1）・同じ品詞の語から3つ選ぶ
    for w, _, lv, pos in ws:
        near = [x for x in ws if x[0] != w and x[3] == pos and abs(x[2] - lv) <= 1]
        assert len(near) >= 3, w


def test_japanese_levels_follow_kanken_table():
    """日本語の語のレベルは、使っている漢字のうち最も高い漢検の級（級別漢字表 2020 年度版）。
    表にない漢字（常用漢字の外）を含む語はレベル 11（準1級以上）。"""
    data = json.loads((Path(__file__).parent / "data" / "kanken_2020.json").read_text(encoding="utf-8"))
    order = ["10", "9", "8", "7", "6", "5", "4", "3", "準2", "2"]
    grade = {c: i + 1 for i, g in enumerate(order) for c in data["grades"][g]}
    # 表の字数が公式の数と合っていること（読み取りの誤りがないか）
    counts = [len(data["grades"][g]) for g in order]
    assert counts == [80, 160, 200, 202, 193, 191, 313, 284, 328, 185]
    for w, _, lv, _ in words("ja"):
        expected = max((grade.get(c, 11) for c in w if "\u4e00" <= c <= "\u9fff"), default=1)
        assert lv == expected, f"{w}: レベル {lv}（表では {expected}）"
