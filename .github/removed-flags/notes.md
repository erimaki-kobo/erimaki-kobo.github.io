# vllm-removed-flags-lookup 記録（2026-11-13 夜 チャットで作成、opus 5.5）

状態：下書き完了（公開待ち。Liz の site が要る）。公開先 https://erimaki-kobo.github.io/en/vllm-removed-flags-lookup/ （index.html 1ファイル、約154KB）。

## 問い
「vllm serve: error: unrecognized arguments: --X」と、エラーにならず黙って効かなくなる環境変数・リクエストの項目。上位の答えは bot の「--help を見ろ」だけで、消えた名前の行き先が無い。

## 答えの形
- ツール：コマンド・エラー文・`export VLLM_...`・リクエストの JSON・`SamplingParams(...)` を貼ると、名前ごとに「その名前があった版の範囲」「最新版での状態」「代わり」を出す。版を入れるとその版で判定。vLLM と SGLang（自動判定か選択）。`--max_model_len`（_ を - に読む）、`--x.key`（JSON 引数の中のキー）、`--no-X`（否定形）を扱う
- 表：消えたときに何が起きるか（大きな音／黙る）／よく写される引数・環境変数・リクエストの項目・SGLang の代わり（人手で選び、版は assert で照合）／消えた名前の全一覧（vLLM 引数81・環境変数120・チャットの項目11・SamplingParams 7・SGLang 106）

## 分かったこと（ソースで確かめた）
- サーバーへのリクエストの知らない項目：v0.6.4 までは拒否（extra="forbid"、400）。v0.6.5〜v0.17.1 は受け取って捨て、WARNING「The following fields were present in the request but ignored」。v0.18.0 からその行が DEBUG になり、既定では何も出ない。v0.30.0 から、消えた guided_* だけは「出力は制約されない」という専用の警告が出る
- 環境変数：v0.17.0 から起動時に「Unknown vLLM environment variable detected: VLLM_X」の警告（`--fail-on-environ-validation` でエラー）。それより前は何も出ない
- vLLM のパーサーは _ と - を同じに読み、`--json-arg.key value` を JSON 引数の中のキーとして読む（v0.33.0 の utils/argparse_utils.py）。v0.33.0 は `--task` に「vllm serve の引数ではない」というヒントを出す
- 数（v0.33.0・SGLang v0.5.23 時点）：vLLM の引数 402 種（今 321）、環境変数 423 種（今 303）、SGLang の引数 653 種（今 547）

## 検査
- test_data.py：無作為の引数30・環境変数30で、最初の版のソースに名前があり、1つ前に無いことを git show で直接確かめた。60/60
- build_page.py：代わりの表の「最後の版」と「代わりが入った版」をすべてデータと assert で照合
- check_browser.js：ヘッドレス Chrome、幅1200と375で14ケース（古い serve・古い版で可・新しすぎ・否定形・ドット・JSON 要求・ignored のログ・SamplingParams・TypeError・SGLang・打ち間違い・取り違え・環境変数・空）＋絞り込み＋URL からの復元＋はみ出し0＋エラー0。ALL PASS
- 未検証：実際に vllm serve を動かしてのエラー文（ソースから読んだ）。値の変化（backend 名など）は見ていない

## ソースの置き場
スクリプト・テストの正本はサイトのリポジトリ `.github/removed-flags/`。抽出スクリプトの元は claude/kiban/scripts/（vllm_cli_hist.py・vllm_env_hist.py・vllm_request_fields_hist.py・sglang_cli_hist.py。ここでは不要な部分を削った版）。

## 作り直し方（vLLM か SGLang の正式版が出たら）
1. vLLM・SGLang を `git clone --bare --filter=tree:0`
2. 4本の *_hist.py を回して out/ に json（並行で約5分）
3. `python3 build_data.py` → out/data.json
4. `python3 build_page.py out/data.json scripts build 公開日 更新日`。消えた数が変わると assert で止まるので、数と、新しく消えた名前の代わり（消える直前の版の help の文で確かめる）を足す
5. test_data.py と check_browser.js

## 2026-11-14 の訂正（独立検査 claude/en/audit_2026-11-14.md の R1〜R6）
- vllm_cli_hist.py を AST にした：名前が変数の add_argument（非推奨の別名をループで登録するもの）と、serve サブコマンド自身の引数（scripts.py・entrypoints/cli/serve.py の serve_parser）を読む。--guided-decoding-* 4本の最後は v0.11.2、--config は v0.6.0 から、など9本の範囲が変わった。件数（81・120・106）は同じ
- vllm_env_hist.py は envs.py の外の引用符つきの名前も出し、build_data.py が「envs.py に入る直前まで連続して名前が出ている版」を足す（VLLM_BATCH_INVARIANT は v0.11.1 から。4本）。消えたあとの版には足さない（非推奨の文面に名前が残るため）
- 本文：リクエスト項目の拒否は v0.4.2〜v0.6.4.post1 だけ／SGLang の --stream-output は v0.5.19 まで・代わりは --incremental-streaming-output／vLLM も argparse の前方一致の省略形を受け付ける
- tool.js：消えた名前が、その版にある引数の前方一致になるとき「別の引数として読まれる」「ambiguous option になる」を出す
- 検査：test_data.py 60/60、check_browser.js 20ケース×幅2つ ALL PASS
- 未検証：実際に vllm serve を動かしての動き（--guided-decoding-backend の値が v0.11.x で効かないことを含む。ソースの読み）
