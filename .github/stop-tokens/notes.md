# generation-stop-tokens-check 記録（2026-11-13 夜 チャットで作成、opus 5.5）

状態：下書き完了（公開待ち。Liz の site が要る）。公開先 https://erimaki-kobo.github.io/en/generation-stop-tokens-check/ （index.html と jinja-0.5.13.js の2ファイル）。

## 問い
「モデルが生成を止めない」「Llama 3 が <|eot_id|> で止まらない」「vLLM が eos で止まらない」「llama.cpp が止まらない」。エンジンごとに見るファイルが違うことを横断で示す答えが無い。

## 答えの形
- ツール：Hugging Face のモデル id で4ファイル（config.json・generation_config.json・tokenizer_config.json・chat_template.jinja、要れば tokenizer.json）を取るか、貼る。チャットテンプレートを @huggingface/jinja 0.5.13 で [user, assistant] の会話に描き、答えの直後に来るトークンを「ターンの終わり」とする。6エンジン（Transformers・vLLM・SGLang・llama.cpp・Ollama・MLX-LM）で止まる集合を作り、止まるか・直し方を表にする。llama.cpp は読み込みログを貼れば実物、無ければ予測。llama.cpp のビルド・Ollama の版を入れると、その時点の一覧で判定（Ollama の版→同梱ビルドは gguf のページの archs.json を読む）
- 表：エンジン別の決まり方（読んだ版つき）／人気14モデルの判定／よくある原因／llama.cpp の実テンプレート74本の終わりのトークンと、llama.cpp の組み込み一覧に入っているか／組み込み一覧の各テキストの初出ビルド

## 各エンジンの決まり（読んだソース）
- Transformers v5.22.2：generation_config.json の eos_token_id。無ければ config.json から（トップ、無ければ text_config）。tokenizer の eos は足さない。generation_config.json があって eos が無いと終了トークン無し
- vLLM v0.33.0：tokenizer の eos ＋ generation_config.json（無ければ config.json から作る）の eos ＋ リクエストの stop_token_ids
- SGLang v0.5.23：config.json（トップ）＋ generation_config.json ＋ tokenizer の eos ＋ 組み込み3つ（<|eom_id|>・<|content_model_end_sampling|>・<|ifm|im_end|>）＋ stop_token_ids
- MLX-LM v0.32.2：config.json（トップ）の eos を generation_config.json の値で置き換え ＋ tokenizer の eos
- llama.cpp b12352：GGUF の eos・eot・eom、FIM の pad・repo・sep、語彙のうち組み込み一覧（24テキスト）に合うもの。<|end|> は <|return|>＋<|call|>（gpt-oss）か <|calls|>＋<|flush|> があれば外す。</s> は Gemma 4・PLaMo・Beam で外す。予測の GGUF eos は tokenizer_config の eos_token、無ければ config.json の eos_token_id（gguf-py の SpecialVocab の順）
- Ollama v0.40.16：llama-server に渡すので llama.cpp の EOG ＋ Modelfile・リクエストの stop 文字列（llm/llama_server.go）

## 分かったこと
- Qwen/Qwen3.5-4B（sha 851bf6e、11/13 時点）は generation_config.json が無く、config.json の eos は text_config の 248044（<|endoftext|>）だけ。上の決まりでは Transformers の generate() は <|im_end|> で止まらない。vLLM・SGLang・MLX-LM は tokenizer の eos（<|im_end|>）を足すので止まる。27B と Qwen3.6 には generation_config.json がある（eos [248046, 248044]）。実際の生成はしていない
- llama.cpp のテスト用テンプレート74本：59本が終わりのトークンを書き、9本は何も書かず、6本は簡単な会話では描けなかった。終わりのトークンのうち12種（</assistant>・<|message_sep|>・<|END_RESPONSE|>・<|close|> など）は組み込み一覧に無く、GGUF の eos/eot が指していないと止まらない
- 組み込み一覧の初出：<|eot_id|> と <end_of_turn> は b2702（2024-04-21）、<|im_end|> は b2714（b2702 は <|im_emd|> という打ち間違いだった）、<turn|>（Gemma 4）は b8637、<eos> は b8717、<|eot|> は b11671

## 検査
- test_core.mjs：合成の7ケース（Llama 3 の元の設定・generation_config 無し・eos 無しの generation_config・Qwen の base 型 eos・Instruct・Ollama の stop 文字列＋ログ・マルチモーダルの text_config）ALL PASS
- test_templates.mjs：llama.cpp の models/templates 74本を描いて終わりのトークンを抜く（out/tmpl_markers.txt）
- real_table.mjs：Hugging Face から取った14モデルの要点（fixtures/real_2026-11-13.json。内蔵ブラウザで取得、jinja は jsDelivr から取り sha256 aa05843d… を確かめた）で判定
- check_browser.js：ヘッドレス Chrome、幅1200と375で10ケース（Llama 3.1・generation_config 無し・古いビルド・Qwen3 base・Ollama の stop＋ログ・Gemma 4・古い Ollama・gpt-oss・手入力・空）＋はみ出し0＋エラー0。ALL PASS
- HTML の構文・JSON-LD・h1 は1つ・ASCII のみ
- 未検証：Fetch ボタン（コンテナから Hugging Face に届かない。公開後に内蔵ブラウザで確かめる）、実際の生成、GGUF の予測と実物の一致（変換器のモデル別の上書き、eot の設定は見ていない）

## ソースの置き場
スクリプト・テスト・fixtures の正本はサイトのリポジトリ erimaki-kobo.github.io の `.github/stop-tokens/`（gguf のページと同じ扱い。プロジェクト文書には置いていない）。

## 作り直し方
1. llama.cpp・Transformers・vLLM・SGLang・MLX-LM・Ollama を `git clone --bare --filter=tree:0`
2. `python3 llama_eog_lists.py <llama.cpp> bNNNNN > out/llama_eog.json`（約10分。一覧の形が変わると assert で止まる）
3. models/templates/*.jinja を tmpl/ に取り出し `node test_templates.mjs tmpl > out/tmpl_markers.txt`
4. `node real_table.mjs fixtures/real_….json > out/real.json`
5. style.css は gguf のページの <style>、jinja-0.5.13.js は npm の @huggingface/jinja 0.5.13 の dist/index.js
6. `python3 build_page.py out/llama_eog.json out/tmpl_markers.txt scripts build 公開日 更新日`（本文の数字は assert つき）
7. 各エンジンの決まりは手で読んだもの。新しい版で変わっていないかは、上の「読んだソース」の関数を読み直す

## 後で足すと強くなるもの
- 変換器のモデル別の eot 設定（GLM の <|user|> など）を予測に入れる
- Ollama の MLX ランナー（macOS）
- vLLM・SGLang の古い版の違い（v0.4.1 より前など）を版の入力で出す

## 2026-11-14 の訂正（独立検査 claude/en/audit_2026-11-14.md の S1〜S4）
- Solar Open：テンプレートは履歴を <|end|> で閉じるが、生成の終わりは <|flush|>（ツール呼び出しは <|calls|>）。モデルの generation_config.json は eos_token_id [2, 24, 25] で <|end|>（21）を含まず、llama.cpp はこの語彙で <|end|> を EOG から外す。stopcheck.js に読み替え（src "solar"）、build_page.py の表はこの1本だけ上書き、test_core.mjs に1ケース
- <|end|> を外す条件に「<|calls|> と <|flush|> がある」を足した
- 日付は UTC のコミット日（llama_eog_lists.py。gguf のページと同じ）。b5674 と b10141 が1日動いた
- Ollama の独自エンジンは v0.5.12〜v0.24.0（runner/ollamarunner があるタグ）。v0.30.0 から llama-server
- 検査：test_core.mjs ALL PASS、check_browser.js ALL PASS（サイトと同じ配置で。archs.json を読むため）
- jinja-0.5.13.js は作り直さない（build_page.py に既にヘッダつきのファイルを渡すとヘッダが二重になる）
