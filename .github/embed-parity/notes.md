# gguf-embedding-rerank-parity-check（下書きの記録）

2026-11-28 チャットで作成（Liz「yep」13:48）。状態：drafted（公開は「site」をもらってから）。

## 答えの形
- ページ index.html：6つの原因（pooling・前置き・長い入力・正規化・cross-encoder の segment id・rerank の尺度）× 5者（sentence-transformers・llama-server b12826・Ollama v0.40.19・TEI v1.10.0・vLLM v0.34.0）の表、llama-server の実測10行、点検の使い方、直し方、既知の報告、FAQ 5問（schema の FAQPage と同じ文）。
- 点検スクリプト embedcheck.py（v1.0）：embed／rerank。同じ入力を手元の sentence-transformers／CrossEncoder（Qwen3 は model card の P(yes) の作り方）とサーバに流し、cosine・Spearman を出す。ずれたら pooling×前置き×切り捨ての全組み合わせ、rerank は sigmoid・token_type_ids=0・pooler なし・softmax(hidden)[0] の変種と照らして原因を名指す。--gguf でヘッダも見る（pooling_type 無し、cls.* 無し、Qwen3 で rank でない、BERT の cls.weight 無し）。終了コード 0 一致（注意書きだけは 0）／1 不一致／2 届かない。

## 実測（すべて CPU、トイ）
- トイの作り方 repro/make_toys.py：重みは乱数（seed 固定、hidden 64・2層）、語彙は本物（llama.cpp の models/ggml-vocab-bert-bge.gguf と ggml-vocab-qwen2.gguf から HF の tokenizer を組み立てた。BERT は変換で pre=jina-v2-en と判定された＝chkhsh が既知のもの）。
- llama.cpp：clone の HEAD 8e23278（b12826, 2026-11-27）をビルド。変換は b12826 と b12816（pooler 修正 15fcfc7 の直前のタグ。15fcfc7 自体にはタグが無く、最初に含むのは b12818）。
- 結果は repro/results.txt（run_matrix.sh 11件、run_mock.sh 9件の出力そのまま）。
- 見つけたこと：
  1. b12816 で変換した cross-encoder は「pooler なし＋segment id 0」の計算と一致（#33109 の再現）。b12826 の変換では pooler は直ったが「token_type_ids=0」の計算と一致＝**llama.cpp は今も文書側の segment id を 0 で流す**（src/models/bert.cpp の type_row0）。トイでは Spearman 0.90/1.00。学習済みモデルでの大きさは未測定。
  2. Qwen3 を reranker と判定させずに変換した GGUF（cls.output.weight 無し）を --pooling rank で動かすと、スコア＝softmax(最後の隠れ状態)[0]。しかも**同じ要求の他の文書で値が変わる**（文書2：単独 0.00486、文書1と一緒 0.01073）。理由は追っていない。
  3. modules.json の無いフォルダから変換した GGUF は pooling_type 無し → /v1/embeddings が 400「Pooling type 'none' is not OAI compatible」。
  4. 正しく変換した Qwen3-Reranker 型は P(yes) と一致（llama.cpp は yes/no の2行の softmax を返す）。
- Ollama・TEI・vLLM は動かしていない。ソースの決まりを mock_engine.py に写し、点検スクリプトのクライアント部分と診断を試しただけ（run_mock.sh）。

## ソースで確かめたこと（タグ）
- Ollama v0.40.19 server/routes.go：/api/embed と /v1/embeddings は context_length（num_ctx があれば小さい方）で黙って切り、必ず L2 正規化。"truncate": false で 400「the input length exceeds the context length」。旧 /api/embeddings は切らず正規化もしない。rerank の口は無い。
- TEI v1.10.0：max_seq_length で切る（--auto-truncate 既定 true）、normalize 既定 true、前置きは --default-prompt-name か要求の prompt_name のときだけ（設定ファイルの default_prompt_name は読まない）、1_Pooling が無い BERT は CLS に警告つきで落ちる、rerank は raw_scores でなければ sigmoid、token_type_ids を渡す。
- vLLM v0.34.0：modules.json と 1_Pooling に従う、max_model_len は max_seq_length、超えると拒否（truncate_prompt_tokens で切る）、1ラベルは sigmoid（use_activation false で生）、ST の prompts は /v2/embed の input_type のときだけ、Qwen3-Reranker の原本は hf_overrides が要る、token_type_ids を渡す。
- llama.cpp b12826：Qwen3 を reranker と見なす条件は README の「# Qwen3-Reranker」・フォルダ名か _name_or_path の「qwen3-reranker」・*ForSequenceClassification（conversion/qwen.py）。Qwen3 reranker の対応は #15824（2025-09-25、最初のタグ b6578）。

## 作り直し方
1. llama.cpp を clone してビルド（llama-server）。`pip install torch sentence-transformers transformers tokenizers` と `pip install -e llama.cpp/gguf-py`。
2. `python repro/make_toys.py llama.cpp toys`、各トイを `convert_hf_to_gguf.py --outtype f32` で変換（cross-encoder は b12816 の worktree でも）。no-st-files 用の参照フォルダは bert-no-st-files に bert-mean-prompt の ST ファイル（prompts 無し）を足したもの（コマンドは 2026-11-28 のチャット）。
3. `repro/run_matrix.sh <llama-server> toys gguf out`、`repro/run_mock.sh toys out_mock`。
4. `python .github/embed-parity/build_page.py <site repo> <出力先>`（repro の中身は en/gguf-embedding-rerank-parity-check/repro/）（style はサイトの disable-thinking のページから写す）。

## sha256（2026-11-28 時点）
- embedcheck.py 9db43fb268f3379352ebff45324390b7cbdb37c7c9ba4191509504e761c706d4
- index.html de339bce9ed37d6d300bf7daeb95a4da4874638cca91290c379d15d56dc8c4fc

## 公開の前に（erimaki-en-publish で）
- seo-onpage → seo-aeo-geo → schema-markup の手当て、本番をスマホ幅で確認、Search Console に登録リクエスト。
- 未確認：学習済みモデル（bge-small、all-MiniLM-L6-v2、ms-marco-MiniLM、Qwen3-Reranker-0.6B）での数字。コンテナから huggingface.co に届かないので測っていない。
