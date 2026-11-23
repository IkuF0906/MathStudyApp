# 語彙数チェッカー（バックアップ）

アプリに「語彙」タブとして取り込む前に、単独のページ（claude.ai の Artifact）として公開していたものの控えです。
アプリからは読み込んでいません。

- `original.html`: 日本語・English の語彙数チェッカー（数学タブを足す前の版）
- `index.html`: 上に「数学」タブ（選択式のレベル診断）を足した版。`mathbank.json` を同じフォルダから読み込む
- `mathbank.json`: `drill/` の問題の型から書き出した選択式の問題（164問）と誤答パターン

ローカルで開くとき: `python -m http.server -d archive/vocab-checker` で配信して `http://localhost:8000/` を開く
（`file://` で直接開くと `mathbank.json` を読み込めない）。
