"""英単語のレベル（static/vocab.js）が CEFR-J Wordlist・Octanove Vocabulary Profile と合っているかを確かめる。

実行: python -m scripts.check_vocab_levels
リストは GitHub（openlanguageprofiles/olp-en-cefrj）から読み込む（CI では動かさない。語を足したときに手で実行する）。
レベル: A1=1 … C2=6、どちらのリストにもない語=7。品詞（名詞・動詞・形容詞）ごとにレベルを引く。
"""

import csv
import io
import re
import sys
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/"
FILES = ["cefrj-vocabulary-profile-1.5.csv", "octanove-vocabulary-profile-c1c2-1.0.csv"]
CEFR = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
POS = {"n": "noun", "v": "verb", "a": "adjective"}


def load_lists() -> dict[str, dict[str, str]]:
    lex: dict[str, dict[str, str]] = {}
    for name in FILES:
        with urllib.request.urlopen(BASE + name) as res:
            rows = csv.DictReader(io.StringIO(res.read().decode("utf-8")))
            for row in rows:
                for hw in row["headword"].split("/"):
                    lex.setdefault(hw.strip().lower(), {}).setdefault(row["pos"].strip(), row["CEFR"].strip())
    return lex


def main() -> int:
    src = (Path(__file__).resolve().parent.parent / "static" / "vocab.js").read_text(encoding="utf-8")
    en = src[src.index(" en:{") :]
    lex = load_lists()
    wrong = []
    for w, _, lv, pos in re.findall(r'\["([^"]+)","([^"]+)",(\d+),"([nva])"\]', en):
        expected = CEFR.get(lex.get(w.lower(), {}).get(POS[pos]), 7)
        if int(lv) != expected:
            wrong.append(f"{w}: レベル {lv}（リストでは {expected}）")
    print("\n".join(wrong) or "すべてリストどおりです")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
