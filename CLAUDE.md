# プロジェクトのルール

このファイルは、PC のセッションにも Web（クラウド）のセッションにも読み込まれるよう、リポジトリの中に置いている。

## 話し方・進め方
- 日本語で話す
- 必要なツールの導入やアップデートはしてよい。ただし、する前に確認を取る

## 前提
- LLM・AI の API は使わない。数式処理（SymPy）とルールで実現する（ブラウザ内蔵の AI の API も使わない）
- フロントエンドは素の HTML/CSS/JavaScript で、ビルドの手順を持たない。外部ライブラリは CDN から読み込む
  - CDN のファイルには SRI（integrity・crossorigin）を付ける。版を上げたらハッシュも付け直す
- 画面の文言は日本語で書く

## 文字コード・改行
- ファイルは UTF-8・LF で書く（Python と Web のファイルのため）

## テスト・評価
- コミットの前に `PYTHONIOENCODING=utf-8 .venv/Scripts/python -m pytest -q` を通す（cp932 での文字化けを防ぐため環境変数を付ける。Windows 以外では `python -m pytest -q`）
- 問題の型や誤答パターンを追加・変更したら、テストを足したうえで `python -m scripts.evaluate 200` を実行し、`docs/evaluation.md` の結果を更新する

## 画面の確認
- 画面（static/）を変えたら `python -m scripts.screenshot <出力先>` でスクリーンショットを撮り、画像を見て確かめる。エラーが出ていないことも確認する
- 普段の解答履歴（drill.db）を汚さないよう、確認用の操作は普段のサーバー（ポート 8000）に対して行わない
- 画面の見た目を変えたら、スクリーンショットを見たうえで unslop（プラグイン）の `references/signs.md` に沿ってレビューし、当てはまる印を直す。作り直しはせず、今のデザインの方向を保った「軽い手直し（polish）」の範囲にとどめる。方向性を変えるような大きな案は、直さずに提案として伝える

## 本番（Oracle Cloud の VM）
- main に push すると CI がテスト・イメージ作成のあと VM にデプロイする。VM の `/opt/drill/deploy.sh` は手でコピーしたものなので、`deploy/vm/deploy.sh` を変えたら VM 側も差し替えが要る（VM に入れるのはユーザーの PC だけ）
