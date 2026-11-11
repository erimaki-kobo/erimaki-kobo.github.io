# A100以降のGPUで動かす LLMファインチューニング＆強化学習 OSSガイドブック

**2026年11月版**（調査基準日：2026-11-11）

---

## はじめに

### この本の目的

NVIDIA A100 以降のデータセンター向けGPU（A100 / H100 / H200 / B200 / B300 など）を前提に、LLM の**ファインチューニング（FT）**と**強化学習（RL）**に使えるオープンソースソフトウェアを一冊で見渡せるようにまとめました。

- どんな OSS があり、それぞれ何が得意で、いまも開発が続いているのか
- インストールから最小構成の実行まで、最初の一歩をどう踏み出すか
- 手元の GPU 構成と目的から、どれを選べばよいか

の3点に答えることを目標にしています。

### 調査方法

- **リポジトリを直接確認**：約150のリポジトリを取得し、README・ドキュメント・サンプル設定・LICENSE・タグ・最終コミット日を確認しました。
- **PyPI と突き合わせ**：配布パッケージの最新バージョン・公開日・対応 Python を確認しました。
- **ハードウェアと基盤ソフト**：NVIDIA と PyTorch の公式情報（CUDA 対応表、リリースノート、公式ブログ）を参照しました。
- 出典は各章末と付録Eにまとめています。

### 読むうえでの注意

1. **コマンド例は「公式の書き方に沿った最小例」です。** 各 OSS の README・ドキュメントの記法を確認して書いていますが、本書のために GPU 上で実行検証したものではありません。実行前に必ず公式ドキュメントの最新版を確認してください。
2. **この分野は月単位で変わります。** バージョン番号と日付はすべて調査基準日時点のものです。
3. **スター数は載せていません。** 人気の指標ではなく、最終コミット日・最新リリース日・README の保守状況の記載で「生きているか」を判断しています。
4. **対象外としたもの**：マネージドサービス本体（各社のファインチューニング API、サーバーレス RL など）、Apple Silicon 専用のもの、ロボット・画像生成専用の RL 基盤は、関連箇所で名前を挙げる程度にとどめています。

### 本書の構成

| 部 | 内容 | こんなときに |
|---|---|---|
| 第I部 前提 | GPU 世代とソフトウェアの現在地、手法の地図、OSS 全体マップ | 全体像をつかみたい |
| 第II部 ファインチューニング | Hugging Face スタック、Unsloth、LLaMA-Factory、Axolotl、ms-swift ほか | SFT / LoRA / フル FT をしたい |
| 第III部 強化学習 | TRL の GRPO から分散 RL 基盤、エージェント RL、環境まで | GRPO・RLHF・エージェント学習をしたい |
| 第IV部 実践 | 周辺 OSS、構成別レシピ、落とし穴 | 構成を決めたい・事故を避けたい |
| 付録 | 一覧表、コマンド早見表、用語集、論文、出典 | 調べものに |

急ぐ場合は **第3章（全体マップ）→ 第21章（構成別レシピ）** の順に読むと、候補が絞れます。

---

## 目次

**第I部 前提**
- 第1章 「A100以降」という前提
- 第2章 手法の地図
- 第3章 OSS 全体マップ

**第II部 ファインチューニング OSS**
- 第4章 Hugging Face スタック（Transformers / PEFT / TRL / Accelerate / bitsandbytes）
- 第5章 Unsloth
- 第6章 LLaMA-Factory（LlamaFactory）
- 第7章 Axolotl
- 第8章 ms-swift
- 第9章 そのほかの統合フレームワーク
- 第10章 大規模・分散学習の基盤とカーネル
- 第11章 開発が終了・停止した FT 系 OSS

**第III部 強化学習 OSS**
- 第12章 LLM×RL システムの共通構造
- 第13章 まず手元で試す RL
- 第14章 分散 RL 基盤
- 第15章 エージェント RL フレームワーク
- 第16章 環境と報酬の OSS
- 第17章 一般的な RL ライブラリ
- 第18章 学習用・教育用の実装
- 第19章 歴史的な OSS と開発が止まったもの

**第IV部 実践**
- 第20章 周辺 OSS
- 第21章 構成別レシピ
- 第22章 落とし穴チェックリスト

**付録**
- 付録A OSS 一覧表
- 付録B コマンド早見表
- 付録C 用語集
- 付録D 主要論文
- 付録E 出典・公式ドキュメント
- 付録F 確認できなかったこと

---
# 第I部 前提

## 第1章 「A100以降」という前提

### 1.1 なぜ A100 が境界線になるのか

「A100以降」は単なる世代の目安ではなく、ソフトウェア側の要件として実際に線が引かれています。

| 境界になっている要件 | 内容 | 根拠 |
|---|---|---|
| **bf16（bfloat16）混合精度** | 現在の LLM 学習の標準精度。Ampere（A100、RTX 30 系）以降で使う前提 | TRL は「Ampere 以降は `bf16=True`、それより古い GPU は `fp16=True`」と案内。Axolotl も要件に「bf16 と Flash Attention には Ampere 以降」と明記 |
| **FlashAttention-2** | Ampere / Ada / Hopper が対象。bf16 での利用は Ampere 以降 | flash-attention の README |
| **Compute Capability 8.0 以上** | A100 は CC 8.0。これを最低要件とする OSS がある | Trinity-RFT は「CC 8.0 以上の NVIDIA GPU（RTX 30、A100、H100 など）」を要件に記載 |
| **MIG（GPU 分割）** | Ampere 世代（CC 8.0 以上）から対応。A100 は最大7インスタンス | NVIDIA MIG User Guide |
| **CUDA 13 系への移行** | CUDA 13.0 で CC 7.5 未満（Maxwell / Pascal / **Volta＝V100**）のサポートが削除 | NVIDIA 公式ブログ |
| **PyTorch のビルド** | PyTorch 2.15 から CUDA 12.x のホイール配布が終了。配布されるのは CUDA 13.x（Turing〜Blackwell 対応）のみ | PyTorch dev-discuss / 2.15 リリースブログ |

つまり 2026年11月時点では、**V100 以前は最新の PyTorch と主要フレームワークから事実上外れており、A100 が「現行ソフトウェアがそのまま動く最古のデータセンター GPU」**という位置づけです（T4 などの Turing 世代も CUDA 13 の対象ですが、bf16 と FlashAttention-2 の要件を満たしません）。

### 1.2 GPU 世代の早見表

| GPU | アーキテクチャ | Compute Capability | メモリ | 低精度演算 | 備考 |
|---|---|---|---|---|---|
| A100 | Ampere | 8.0 | 40GB / 80GB | bf16・TF32 | 本書の基準。FP8 のテンソルコアは非搭載 |
| L40S | Ada | 8.9 | 48GB | bf16・FP8 | 推論・小〜中規模 FT 向け |
| H100 | Hopper | 9.0 | 80GB（94GB 版あり） | bf16・**FP8** | FlashAttention-3 の対象 |
| H200 | Hopper | 9.0 | 141GB | bf16・FP8 | H100 のメモリ増強版 |
| B200 | Blackwell | 10.0 | 180GB | bf16・FP8・**FP4（NVFP4）** | DGX B200 は8基で合計 1,440GB |
| B300 | Blackwell Ultra | 10.3 | 公称 288GB | bf16・FP8・FP4 | メモリ容量は資料により 268〜288GB と表記が揺れる |
| GB200 / GB300 | Grace + Blackwell | 10.0 / 10.3 | GB200 は 186GB | 同上 | CPU が Arm（aarch64）。ホイールの対応に注意 |
| RTX PRO 6000 Blackwell | Blackwell | 12.0 | 96GB | — | ワークステーション／サーバー向け |

- Compute Capability は NVIDIA の「CUDA GPU Compute Capability」ページ、メモリ容量は MIG User Guide の対応 GPU 表によります（L40S は NVIDIA の製品ページ）。
- 次世代の **Rubin** については、PyTorch 2.15 の CUDA 13.4 ホイールが「実験的サポート」を追加した段階です。

### 1.3 ソフトウェアスタックの現在地

調査基準日時点の主要バージョンです。

| ソフトウェア | 最新版 | 公開日 | メモ |
|---|---|---|---|
| PyTorch | 2.15.0 | 2026-10-28 | 既定ホイールは CUDA 13.2。CUDA 13.4 版も配布。Python 3.11 以上 |
| Transformers | 5.22.2 | 2026-11-06 | Python 3.11 以上、PyTorch 2.6 以上 |
| PEFT | 0.21.2 | 2026-10-01 | |
| TRL | 1.17.1 | 2026-10-30 | Python 3.11 以上 |
| Accelerate | 1.15.0 | 2026-09-09 | |
| bitsandbytes | 0.50.2 | 2026-08-27 | Python 3.10 以上、PyTorch 2.4 以上 |
| DeepSpeed | 0.19.9 | 2026-10-29 | |
| Megatron Core | 0.20.0 | 2026-10-29 | Python 3.12 以上を推奨 |
| flash-attn | 2.8.3.post2 | 2026-10-14 | |
| vLLM | 0.33.0 | 2026-11-02 | RL のロールアウトに多用 |
| SGLang | 0.5.23 | 2026-10-30 | 同上 |
| Ray | 2.60.0 | 2026-11-04 | 分散 RL のオーケストレーション |

押さえておきたい傾向は次のとおりです。

- **CUDA 13 / PyTorch 2.13 以降が事実上の標準に。** verl は「CUDA 12.8 以上」を要件とし、uv のロックファイルは cu130 / torch 2.13 で固定されています。NVIDIA の Molt は「CUDA 13 必須、CUDA 12 環境では動かない」と明記。Axolotl は PyTorch 2.13 以上を要件にしています。
- **ドライバは 580 系以降が目安。** CUDA 13.0 はドライバ 580 系と同時に提供されました。古いドライバのホストでは、前方互換レイヤーを同梱したコンテナ（Molt、slime など）を使う方法が案内されています。
- **Python は 3.11〜3.12 が中心。** PyTorch 2.15 と Transformers は 3.11 以上、Axolotl は 3.12 以上です。
- **uv + ロックファイル + コンテナ** での配布が主流になりました（verl、NeMo RL、NeMo AutoModel、prime-rl、Axolotl、Unsloth など）。

### 1.4 世代ごとの注意点

**A100**
- FlashAttention は 2 系を使います。3 系は Hopper（H100 / H800）向け、4 系は Hopper と Blackwell 向けです。
- FP8 学習や NVFP4 系の機能は Hopper / Blackwell 世代を前提にしたものが中心で、A100 では bf16 が基本になります。
- Megatron ベースの大規模 RL 基盤は Hopper 以降で主に検証されています（slime の公式イメージ表は H100 / H200 と B200 / B300 のみ）。一方で prime-rl は開発・検証対象に A100 を挙げ、Miles も対応ハードに A100 を含めています。

**H100 / H200**
- FP8、FlashAttention-3 / 4、Megatron 系バックエンドの恩恵を受けやすい世代です。多くの分散 RL 基盤の CI がこの世代で回っています。

**B200 / B300（Blackwell）**
- CUDA 12.8 以降が必要です。verl のサンプルスクリプトには Blackwell 用の切り替え（eager 実行の強制、bf16 の明示、SGLang の注意機構バックエンド変更など）があり、「FlashAttention-3 は SM 9.0 より新しい世代では使えない」と注記されています。
- GB200 / GB300 は aarch64 です。verl のロックファイルは x86_64 と aarch64 の両方を含みます。

### 1.5 VRAM の見積もり

LLaMA-Factory の README にある概算表が目安として使いやすいので、要点を抜き出します（いずれも推定値）。

| 手法 | 精度 | 7B | 14B | 30B | 70B |
|---|---|---|---|---|---|
| フル FT（bf16 混合精度） | 32bit 相当 | 120GB | 240GB | 600GB | 1200GB |
| フル FT（pure bf16） | 16bit | 60GB | 120GB | 300GB | 600GB |
| LoRA / Freeze など | 16bit | 16GB | 32GB | 64GB | 160GB |
| QLoRA | 8bit | 10GB | 20GB | 40GB | 80GB |
| QLoRA | 4bit | 6GB | 12GB | 24GB | 48GB |

A100 80GB 1枚に当てはめると、**LoRA なら 30B 級、4bit QLoRA なら 70B 級、pure bf16 のフル FT なら 7B 級**までが1枚に収まる目安です。実際にはシーケンス長とバッチサイズで大きく変わるので、最初は小さく始めて `nvidia-smi` で確認するのが確実です。

### 1.6 マルチ GPU の基礎

| 方式 | 何をするか | 向いている場面 |
|---|---|---|
| **DDP** | 各 GPU にモデルを丸ごと複製し、別々のバッチを処理 | 1枚に収まるモデル（LoRA / QLoRA、小さめのフル FT）のスループット向上 |
| **FSDP2** | パラメータ・勾配・オプティマイザ状態を GPU 間で分割 | 1枚に収まらないモデルのフル FT。PyTorch 標準 |
| **DeepSpeed ZeRO** | ステージ1〜3 で分割範囲を段階的に拡大。CPU / NVMe オフロードも可 | FSDP と同じ用途。設定ファイルで切り替え |
| **Megatron（TP / PP / CP / EP）** | テンソル・パイプライン・コンテキスト・エキスパート並列 | 数百B 級や MoE モデルの学習 |
| **`device_map` による単純分割** | 層ごとに GPU へ割り振るだけ | 推論やお試し。学習速度は出ない |

- 起動は `torchrun` が基本です。TRL は「トレーナは torchrun で起動する」と案内しており、`trl` CLI も内部で同じことを行います。
- DDP では実効バッチサイズが `per_device_train_batch_size × GPU数 × gradient_accumulation_steps` になる点に注意します。GPU を増やしたら、どれかを調整して揃えます。
- A100 以降は MIG で1枚を複数インスタンスに分けられるため、小さなモデルの実験や CI を並列に回す用途にも使えます。

**出典**：[CUDA GPU Compute Capability](https://developer.nvidia.com/cuda/gpus) / [MIG User Guide: Supported GPUs](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-gpus.html) / [Navigating GPU Architecture Support（NVIDIA）](https://developer.nvidia.com/blog/navigating-gpu-architecture-support-a-guide-for-nvidia-cuda-developers) / [PyTorch 2.15 Release Blog](https://pytorch.org/blog/pytorch-2-15-release-blog/) / [PyTorch dev-discuss: CUDA 12.6 ホイール終了の告知](https://dev-discuss.pytorch.org/t/notice-cuda-12-6-wheels-will-no-longer-be-published-from-pytorch-2-15-drops-maxwell-pascal-volta/3432) / [DGX B200](https://www.nvidia.com/en-us/data-center/dgx-b200/) / [flash-attention](https://github.com/Dao-AILab/flash-attention) / [TRL: Speeding Up Training](https://huggingface.co/docs/trl/speeding_up_training) / [LlamaFactory](https://github.com/hiyouga/LlamaFactory)

---

## 第2章 手法の地図

OSS を選ぶ前に、「何をしたいのか」を手法の名前に落としておくと迷いません。

### 2.1 ファインチューニングの手法

| 手法 | 概要 | 使いどころ |
|---|---|---|
| **継続事前学習（CPT）** | ラベルなしテキストで次トークン予測を続ける | ドメイン語彙・文体の取り込み |
| **SFT（教師あり FT）** | 入力と望ましい出力の対で学習。指示チューニングもここ | もっとも一般的。タスク適応・フォーマット遵守 |
| **フル FT** | 全パラメータを更新 | データが十分にあり、VRAM に余裕があるとき |
| **LoRA** | 低ランクのアダプタだけを学習 | 既定の選択肢。省メモリで複数タスクを切り替えやすい |
| **QLoRA** | ベースを 4bit / 8bit 量子化したうえで LoRA | VRAM が足りないとき。大きなモデルを1枚で |
| **DoRA / rsLoRA / PiSSA / OFT など** | LoRA の改良版や別系統のアダプタ | LoRA で精度が足りないときの次の一手 |
| **Freeze チューニング** | 一部の層だけ更新 | 軽量に済ませたいとき |
| **QAT / 低精度学習** | 量子化後の精度を見込んだ学習、FP8 / NVFP4 での学習 | 量子化デプロイが前提のとき（Hopper 以降向けが中心） |

PEFT には調査時点で 40 種類以上のアダプタ手法が実装されています。まずは LoRA、足りなければ QLoRA やランク・対象モジュールの調整、という順で十分です。

### 2.2 選好最適化（オフライン）

「良い応答」と「悪い応答」の対から直接学習する方法です。学習中にモデルに生成させる必要がないので、SFT と同じ感覚で回せます。

| 手法 | 特徴 |
|---|---|
| **DPO** | 採用／不採用の応答ペアと参照モデルを使う。もっとも普及 |
| **IPO / SimPO / CPO** | DPO の損失を変えた派生 |
| **KTO** | ペアでなく「良い／悪い」の二値ラベルだけで学習できる |
| **ORPO** | 参照モデルなしで SFT と選好学習を同時に行う |

### 2.3 RLHF（報酬モデル + PPO）

人間の選好データから**報酬モデル**を学習し、その報酬を最大化するように PPO で方策（LLM）を更新する古典的な構成です。価値関数（クリティック）と参照モデルへの KL 制約を伴うため、必要な GPU メモリが大きくなります。

### 2.4 RLVR と GRPO 系

**RLVR（検証可能な報酬による RL）**は、数学の答え合わせやユニットテストのように機械的に判定できる報酬で学習する方法です。推論モデルの学習で主流になりました。アルゴリズムは GRPO とその派生が中心です。

| アルゴリズム | おおまかな特徴 |
|---|---|
| **GRPO** | 1つのプロンプトに複数の応答を生成し、グループ内で報酬を正規化してアドバンテージにする。クリティック不要 |
| **DAPO** | クリップ幅の非対称化、動的サンプリング、トークン単位の損失集計、長すぎる応答への報酬整形などを加えた改良 |
| **Dr. GRPO** | 長さ正規化などに由来するバイアスを除く |
| **GSPO** | 重要度比とクリップを系列単位で扱う。MoE モデルで安定しやすいとされる |
| **RLOO** | 自分以外のサンプル平均をベースラインにする（leave-one-out） |
| **REINFORCE++** | クリティックなしの REINFORCE に PPO の工夫を組み合わせたもの |
| **CISPO** | トークン更新を切り捨てる代わりに重要度重みをクリップする |
| **PPO** | クリティックを持つ。安定だがメモリを使う |

TRL の `GRPOTrainer` は損失の集計方法を `loss_type` で切り替えられ、既定値は `"dapo"` です（`"grpo"` は長さバイアスがあるため非推奨と説明されています）。

### 2.5 エージェント RL

複数ターンにわたってツールを呼び、環境とやり取りする軌跡全体に報酬を与えて学習します。2026年の特徴は次の2点です。

- **環境の標準化**：OpenEnv、verifiers、NeMo Gym など、環境側のフレームワークが独立して発展しました（第16章）。
- **実ハーネスでの学習**：コーディングエージェントなどの実際のハーネス（実行の枠組み）をそのまま動かし、モデルへのリクエストをゲートウェイで捕捉して学習データにする方式が広がっています（Agent Lightning、rLLM、uni-agent、TRL と OpenEnv の Harbor 連携など。第15章）。

### 2.6 蒸留

教師モデルの出力分布に生徒を近づけます。RL 基盤の多くが **オンポリシー蒸留**（生徒自身が生成した系列上で教師との KL を最小化）をレシピとして備えるようになりました（NeMo RL、Molt、Miles、AReaL、Trinity-RFT、TRL など）。

### 2.7 学習と推論のズレ、そして非同期化

RL ではロールアウト（生成）を vLLM や SGLang に任せるのが普通ですが、**推論エンジンと学習エンジンで同じ重みでも出力確率がわずかに異なる**ため、オンポリシーのつもりがオフポリシーになるという問題があります。TRL のドキュメントはこれを明示的に解説しており、対策として重要度サンプリング補正（切り詰める TIS、範囲外を捨てる MIS / IcePop）を標準で備えています。OpenRLHF、Molt、AReaL、Axolotl にも同種のオプションがあります。

もう一つの潮流が**非同期化**です。生成と学習を止めずに並走させ、古くなりすぎたサンプルだけを捨てる方式で、長い軌跡やツール呼び出しを含む学習でスループットを稼ぎます（AReaL、prime-rl、Molt、ROLL、slime、TRL の `AsyncGRPOTrainer` など）。

### 2.8 どれを選ぶか

```
やりたいこと
 ├─ 文体・知識・出力フォーマットを合わせたい ─────────→ SFT（LoRA から）
 ├─ 「こちらの応答の方が良い」というペアがある ─────→ DPO / KTO
 ├─ 正解を機械的に判定できる（数学・コード・SQL）──→ GRPO 系（RLVR）
 ├─ ツールを使う複数ターンのタスクを上達させたい ──→ エージェント RL（環境 + GRPO 系）
 └─ 大きなモデルの振る舞いを小さなモデルに移したい → 蒸留（+ SFT）
```

多くの場合、**SFT で土台を作ってから RL に進む**のが定石です。TRL の OpenEnv ガイドにも「SFT のウォームアップから始める」という節があります。

---

## 第3章 OSS 全体マップ

### 3.1 レイヤー構造

上から順に、利用者に近い層です。

| 層 | 代表的な OSS |
|---|---|
| 環境・報酬 | OpenEnv、verifiers、NeMo Gym、Harbor、Reasoning Gym |
| エージェント RL | ART、Agent Lightning、rLLM、uni-agent |
| 分散 RL 基盤 | verl、OpenRLHF、NeMo RL、Molt、ROLL、AReaL、slime、Miles、prime-rl、SkyRL、Trinity-RFT |
| 統合 FT フレームワーク | Unsloth、LlamaFactory、Axolotl、ms-swift、LitGPT、NeMo AutoModel、Oumi、Ludwig、H2O LLM Studio |
| 基盤ライブラリ | Transformers、PEFT、TRL、Accelerate、bitsandbytes |
| 分散学習エンジン | FSDP2（PyTorch 標準）、DeepSpeed、Megatron Core、torchtitan |
| 推論エンジン（ロールアウト） | vLLM、SGLang |
| カーネル | FlashAttention、Liger-Kernel、Transformer Engine、torchao |
| 土台 | PyTorch 2.13〜2.15、CUDA 13.x、ドライバ 580 系以降 |

上の層は下の層を組み合わせて作られています。たとえば Unsloth と Axolotl は TRL のトレーナを内部で使い、分散 RL 基盤の多くは「学習エンジン（FSDP2 か Megatron）+ 推論エンジン（vLLM か SGLang）+ Ray」の組み合わせです。

### 3.2 カテゴリ別の一覧

状態の凡例：◎ 活発（直近1か月以内にコミットあり）／○ 継続（直近半年以内にコミットあり）／△ 半年以上更新なし／× 開発終了・停止を README で明記

**ファインチューニング**

| OSS | 一言で | 状態 | 章 |
|---|---|---|---|
| Transformers / PEFT / TRL / Accelerate / bitsandbytes | 事実上の標準。ほかのほとんどがこの上に乗る | ◎ | 4 |
| Unsloth | 省メモリ・高速。デスクトップアプリと Web UI も提供 | ◎ | 5 |
| LlamaFactory（LLaMA-Factory） | YAML 1枚と Web UI。手法の品揃えが広い | ◎ | 6 |
| Axolotl | YAML 駆動。マルチ GPU・マルチノードと最新手法に強い | ◎ | 7 |
| ms-swift | ModelScope 発。対応モデル数が多く、Megatron 連携と GRPO 系を内蔵 | ◎ | 8 |
| LitGPT | 抽象化を排した実装。事前学習から FT まで CLI で | ◎ | 9 |
| NeMo AutoModel | NVIDIA の DTensor ネイティブ学習ライブラリ | ◎ | 9 |
| Oumi | データ準備〜学習〜評価〜デプロイを YAML で通す | ◎ | 9 |
| Ludwig | 宣言的 ML。LLM の LoRA FT も YAML で | ◎ | 9 |
| H2O LLM Studio | GUI 中心のノーコード FT | ◎ | 9 |
| XTuner | 超大規模 MoE 向けの学習エンジンに刷新（V1） | ◎ | 9 |
| Kiln / Transformer Lab / RapidFire AI | アプリ型・実験管理型のツール | ◎ / ○ / ◎ | 9 |
| DeepSpeed / Megatron Core / torchtitan / Megatron-Bridge | 分散学習エンジン | ◎ | 10 |
| torchtune / AutoTrain Advanced / mistral-finetune | 開発終了 | × | 11 |

**強化学習**

| OSS | 一言で | 状態 | 章 |
|---|---|---|---|
| TRL（GRPO / RLOO / DPO / KTO ほか） | 単一ノードで RL を始める標準 | ◎ | 13 |
| verl | もっとも広く使われる分散 RL 基盤。FSDP / Megatron × vLLM / SGLang | ◎ | 14 |
| OpenRLHF | Ray + vLLM の先駆け。読みやすいコード | ◎ | 14 |
| NeMo RL / Molt | NVIDIA の RL 基盤（本格版と軽量版） | ◎ | 14 |
| ROLL | Alibaba。マルチタスク RLVR とエージェント RL | ◎ | 14 |
| AReaL | 完全非同期。2.0 でマイクロサービス構成に | ◎ | 14 |
| slime / Miles | Megatron + SGLang。GLM シリーズの学習基盤とその企業向け派生 | ◎ | 14 |
| prime-rl | 非同期 RL。verifiers の環境と直結 | ◎ | 14 |
| SkyRL / Trinity-RFT | モジュール型のフルスタック RL | ◎ / ○ | 14 |
| ART / Agent Lightning / rLLM / uni-agent | 既存エージェントをそのまま RL で鍛える | ◎ | 15 |
| OpenEnv / verifiers / NeMo Gym / Harbor | 環境とタスクの枠組み | ◎ | 16 |
| Gymnasium / Stable-Baselines3 / TorchRL / RLlib | LLM 以外も含む一般的な RL | ◎ | 17 |
| trlX / RL4LMs / TinyZero / open-r1 / torchforge / Atropos | 開発終了・停止 | × | 19 |

全リポジトリの URL・ライセンス・最新タグ・最終コミット日は付録Aにあります。

### 3.3 2026年11月時点の潮流

1. **統廃合が進んだ。** torchtune は「2025年に開発を終了」と README で告知。AutoTrain Advanced は保守終了で、代替として Axolotl・TRL・Transformers の Trainer を案内。mistral-finetune はアーカイブ。torchforge は開発停止で、PyTorch の LLM 学習は torchtitan に集約。Atropos はアーカイブ、open-r1 は保守終了、TinyZero は verl への移行を案内。
2. **リポジトリの移管・改名。** verl は 2026年1月に `verl-project` 組織へ移管。LLaMA-Factory はリポジトリ名が `LlamaFactory` に。OpenRLHF の README は冒頭で NVIDIA の Molt を「推奨」として紹介しています。
3. **学習エンジンは「FSDP2 か Megatron」、推論は「vLLM か SGLang」** に収束し、その組み合わせ方と非同期化の度合いで各 RL 基盤が差別化しています。
4. **RL の非同期化と重要度サンプリング補正が標準装備に。**
5. **実ハーネスでのエージェント学習** が実用段階に入りました。
6. **Tinker API を軸にした連携の広がり。** マネージド学習 API「Tinker」と互換のバックエンドを自前の GPU で動かすもの（SkyRL、verl の VeRL-Tinker）と、Tinker を学習バックエンドとして呼び出せるもの（Trinity-RFT、rLLM、Axolotl のリモート学習）が出てきました。
7. **JAX 系は別枝。** Google の Tunix と MaxText は TPU を主眼にしており、NVIDIA GPU 中心の本書の文脈では参考扱いです。

**出典**：各リポジトリの README（付録A・E）/ [Open Source RL Libraries for LLMs（Anyscale）](https://anyscale.com/blog/open-source-rl-libraries-for-llms) / [SGLang: Post-Training Integration](https://docs.sglang.io/references/post_training_integration.html)

---
# 第II部 ファインチューニング OSS

## 第4章 Hugging Face スタック

ほとんどの FT 系 OSS は、この5つのライブラリの上に作られています。上位のフレームワークを使う場合でも、ここを理解しておくとトラブル時に切り分けができます。

### 4.1 役割分担

| ライブラリ | 役割 | 最新版（公開日） | ライセンス |
|---|---|---|---|
| **Transformers** | モデル定義・トークナイザ・`Trainer` | 5.22.2（2026-11-06） | Apache-2.0 |
| **PEFT** | LoRA などのアダプタ手法 | 0.21.2（2026-10-01） | Apache-2.0 |
| **TRL** | 事後学習用トレーナ（SFT / DPO / GRPO ほか）と CLI | 1.17.1（2026-10-30） | Apache-2.0 |
| **Accelerate** | デバイス配置と分散実行の土台 | 1.15.0（2026-09-09） | Apache-2.0 |
| **bitsandbytes** | 4bit / 8bit 量子化、8bit オプティマイザ | 0.50.2（2026-08-27） | MIT |

TRL は自身を「基盤モデルを事後学習するための総合ライブラリ」と位置づけており、各トレーナは Transformers の `Trainer` の薄いラッパーです。DDP・DeepSpeed ZeRO・FSDP といった分散学習にそのまま対応します。

### 4.2 インストール

```bash
pip install "transformers[torch]" peft trl accelerate bitsandbytes datasets
# vLLM を使う RL まで試すなら
pip install "trl[vllm]"
```

### 4.3 最小の SFT

TRL の `SFTTrainer` は、モデル名とデータセットを渡すだけで動きます。

```python
from datasets import load_dataset
from trl import SFTTrainer

trainer = SFTTrainer(
    model="Qwen/Qwen3-0.6B",
    train_dataset=load_dataset("trl-lib/Capybara", split="train"),
)
trainer.train()
```

### 4.4 LoRA と QLoRA

実務では LoRA を付けて学習するのが普通です。`peft_config` を渡すだけで有効になり、QLoRA にしたい場合は `quantization_config` を足します。

```python
import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

# {"messages": [{"role": "user", ...}, {"role": "assistant", ...}]} 形式の JSONL
dataset = load_dataset("json", data_files="train.jsonl", split="train")

args = SFTConfig(
    output_dir="out/qwen3-4b-lora",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=1e-4,            # アダプタ学習は高め（公式の目安は 1e-4 前後）
    bf16=True,                     # A100 以降は bf16
    max_length=2048,
    assistant_only_loss=True,      # アシスタントの発話だけを損失の対象にする
    model_init_kwargs={"dtype": torch.bfloat16},
)

trainer = SFTTrainer(
    model="Qwen/Qwen3-4B-Instruct-2507",
    args=args,
    train_dataset=dataset,
    peft_config=LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM"),
    # QLoRA にする場合は次を追加:
    # quantization_config=BitsAndBytesConfig(
    #     load_in_4bit=True, bnb_4bit_quant_type="nf4",
    #     bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True),
)
trainer.train()
trainer.save_model()
```

押さえどころ：

- `quantization_config` 引数は `SFTTrainer`・`DPOTrainer`・`GRPOTrainer`・`RLOOTrainer` で共通です。
- 学習済みアダプタの追加学習は、`AutoPeftModelForCausalLM.from_pretrained(..., is_trainable=True)` で読み込んだモデルを `model=` に渡します（このとき `peft_config` は渡しません）。
- `assistant_only_loss=True` は、チャットテンプレートが生成区間を示すキーワードを含んでいる必要があります。Qwen3 など既知のモデル系列では TRL が自動でテンプレートを補正します。それ以外のモデルではテンプレートの確認が必要です。
- MXFP4 や FP8 で配布されている量子化済みチェックポイントは、そのままでは学習できず、読み込み時に展開されます。必要メモリが配布サイズより大きくなる点に注意します。

PEFT を単体で使う場合は `get_peft_model` でモデルを包みます。

```python
from transformers import AutoModelForCausalLM
from peft import LoraConfig, TaskType, get_peft_model

model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-3B-Instruct", device_map="cuda")
model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, task_type=TaskType.CAUSAL_LM))
model.print_trainable_parameters()   # 学習対象は全体の約 0.1%
```

### 4.5 データ形式

`SFTTrainer` が受け付ける形式は4種類です。

| 形式 | 中身 | 損失の対象 |
|---|---|---|
| 標準の言語モデリング | `text` 列に生テキスト | 全トークン |
| 会話形式 | `messages` 列にロール付きメッセージ | 全体（`assistant_only_loss=True` でアシスタントのみ） |
| プロンプト・補完 | `prompt` と `completion` | 既定で補完部分のみ |
| 会話形式のプロンプト・補完 | 上2つの組み合わせ | 補完部分（+アシスタントのみも可） |

### 4.6 CLI と設定ファイル

コードを書かずに回すこともできます。

```bash
# 引数で指定
trl sft --model_name_or_path Qwen/Qwen2.5-0.5B --dataset_name stanfordnlp/imdb

# YAML にまとめて再現性を確保
trl sft --config sft_config.yaml
```

```yaml
# sft_config.yaml
model_name_or_path: Qwen/Qwen2.5-0.5B
dataset_name: stanfordnlp/imdb
```

用意されているサブコマンドは `sft` / `dpo` / `grpo` / `rloo` / `kto` / `reward` / `distillation` と、環境情報を出す `env` です。LoRA を使う場合は、`trl/scripts/sft.py` に `--use_peft --lora_r 32 --lora_alpha 16` のようなフラグを付ける方法が公式ドキュメントに示されています（QLoRA は `--load_in_4bit` を追加）。

### 4.7 マルチ GPU とマルチノード

```bash
# 1ノード 8GPU
torchrun --nproc_per_node 8 train.py

# 2ノード × 8GPU（各ノードで実行。node_rank だけ変える）
torchrun --nnodes 2 --nproc_per_node 8 --node_rank 0 \
  --rdzv_backend c10d --rdzv_endpoint 10.0.0.1:29500 train.py
```

- `trl sft ...` はそのマシンの全 GPU で動きます。使う枚数を絞るには `--nproc_per_node` を渡します。
- 1枚に収まらないモデルは DeepSpeed を使います。学習スクリプトは変えず、`SFTConfig(deepspeed="zero2.json")` か `trl sft ... --deepspeed examples/deepspeed_configs/zero2.json` のように設定ファイルを指定します。TRL のリポジトリには DeepSpeed と FSDP の設定例が同梱されています。
- Slurm では `srun torchrun ...` の形で、ノードごとに torchrun を1つ起動します。

### 4.8 省メモリ・高速化のオプション

| 目的 | 設定 | 補足 |
|---|---|---|
| 系列を詰めて無駄を減らす | `SFTConfig(packing=True)` | 複数サンプルを1系列に詰める |
| パディングをなくす | `SFTConfig(padding_free=True)` | 最適化された注意機構の実装と併用 |
| 活性の退避 | `SFTConfig(activation_offloading=True)` | 順伝播の活性を一時的に CPU へ |
| 勾配チェックポイント | 既定で有効 | `gradient_checkpointing_kwargs={"selective": True}` で長文時の速度低下を緩和 |
| 高速な注意機構 | `model_init_kwargs={"attn_implementation": "kernels-community/flash-attn2"}` | Kernels Hub のビルド済みカーネル。手動ビルド版は `"flash_attention_2"` |
| 混合精度 | `bf16=True` | A100 以降 |
| 系列長の上限 | `max_length=...` | まずここを見直す |

FlashAttention を自前でビルドする方法は「複雑で時間がかかるため、必要な場合以外は推奨しない」とされ、Kernels Hub のビルド済みカーネルが勧められています。

### 4.9 このスタックを直接使うべき場面

- 学習ループに手を入れたい、独自の損失やコールバックを足したい
- 上位フレームワークが未対応の新しいモデル・手法を試したい
- 依存を最小にして、何が起きているかを把握しておきたい

逆に、定型的な LoRA の SFT を素早く回したいだけなら、次章以降の統合フレームワークのほうが手間が少なくて済みます。

**出典**：[TRL ドキュメント](https://huggingface.co/docs/trl)（SFT Trainer / PEFT Integration / Distributing Training / DeepSpeed Integration / Reducing Memory Usage / Speeding Up Training / CLIs）/ [huggingface/trl](https://github.com/huggingface/trl) / [huggingface/peft](https://github.com/huggingface/peft) / [bitsandbytes](https://github.com/bitsandbytes-foundation/bitsandbytes)

---

## 第5章 Unsloth

### 5.1 概要

| 項目 | 内容 |
|---|---|
| リポジトリ | [unslothai/unsloth](https://github.com/unslothai/unsloth) |
| 最新版 | PyPI `unsloth` 2026.11.3（2026-11-06）。リポジトリは毎日のように更新 |
| ライセンス | コアは Apache-2.0。Studio の UI など一部は AGPL-3.0。補助パッケージ `unsloth-zoo` は LGPL-3.0 |
| 対応手法 | LoRA、QLoRA、フル FT、継続事前学習、GRPO などの RL、DPO、FP8 |
| 特徴 | 省メモリ・高速化の独自最適化。TRL のトレーナをそのまま使える |

Unsloth はライブラリ単体から大きく姿を変え、現在は3つの形で提供されています。

- **Unsloth Desktop**：ネイティブのデスクトップアプリ（README では推奨の導入方法）
- **Unsloth Studio**：ブラウザで使う Web UI（`unsloth studio` で起動）
- **Unsloth Core**：従来からの Python ライブラリ

README は対応環境として Windows / Linux / WSL / macOS、マルチ GPU、NVIDIA・AMD・Intel の GPU を挙げています。本書では、A100 以降のサーバーで使う前提で **Core** を中心に扱います。

### 5.2 インストール（Core）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv unsloth_env --python 3.13
source unsloth_env/bin/activate
uv pip install unsloth --torch-backend=auto
```

Docker イメージ `unsloth/unsloth` も提供されています（ノートブック用途のみなら `unsloth/unsloth:core` タグ）。Blackwell 世代向けには専用のガイドが用意されています。

### 5.3 SFT の基本形

モデルの読み込みとアダプタの付与を Unsloth の `FastLanguageModel` で行い、学習は TRL の `SFTTrainer` に渡します。

```python
from unsloth import FastLanguageModel, is_bfloat16_supported
from datasets import load_dataset
from trl import SFTConfig, SFTTrainer

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/llama-3.1-8b-unsloth-bnb-4bit",
    max_seq_length=2048,
    load_in_4bit=True,          # QLoRA。16bit LoRA なら False
)

model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

dataset = load_dataset("json", data_files="train.jsonl", split="train")  # "text" 列を持つ形式

trainer = SFTTrainer(
    model=model,
    processing_class=tokenizer,
    train_dataset=dataset,
    args=SFTConfig(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        max_steps=60,
        learning_rate=2e-4,
        bf16=is_bfloat16_supported(),
        optim="adamw_8bit",
        output_dir="outputs",
    ),
)
trainer.train()
```

読み込み時の主な切り替え：

| 引数 | 意味 |
|---|---|
| `load_in_4bit=True` | 4bit 量子化（QLoRA） |
| `load_in_8bit=True` | 8bit での FT |
| `load_in_16bit=True` | 16bit の LoRA |
| `full_finetuning=True` | フル FT |

（同時に有効にできるのは1つだけです。）

### 5.4 保存とエクスポート

```python
model.save_pretrained_merged("merged_model", tokenizer, save_method="merged_16bit")
model.save_pretrained_gguf("gguf_model", tokenizer, quantization_method="q4_k_m")
# Hub へ直接: push_to_hub_merged / push_to_hub_gguf
```

GGUF への変換まで一気に行えるのが Unsloth の便利な点です。README は NVFP4 や FP8 など他の形式へのエクスポートにも触れています。

### 5.5 マルチ GPU

公式ドキュメントの DDP ガイドは、`torchrun` で学習スクリプトを起動する方法を示しています。2枚以上で起動すると DDP が自動で有効になります。

```bash
torchrun --nproc_per_node=2 unsloth-cli.py \
  --model_name=Qwen/Qwen3-8B \
  --dataset=yahma/alpaca-cleaned \
  --max_seq_length=2048 \
  --per_device_train_batch_size=1 \
  --gradient_accumulation_steps=4 \
  --max_steps=1000 \
  --save_model
```

- リポジトリ同梱の `unsloth-cli.py` はスターター用の学習スクリプトで、LoRA のランクや保存形式まで引数で指定できます。
- DDP は各 GPU にモデル全体を載せる方式なので、**1枚に収まるモデルの学習を速くする**用途です。同ガイドは単一ノードの例のみを扱っています。
- README はマルチ GPU 対応を掲げていますが、ドキュメントのマルチ GPU 概要ページには「より簡単な公式サポートを準備中」という趣旨の記述も残っています。1枚に収まらないモデルを分割して学習する用途では、Axolotl など情報が揃っているフレームワークも検討してください。

### 5.6 強化学習

Unsloth の RL は、TRL の GRPO トレーナに Unsloth で読み込んだモデルを渡す形です。

```python
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Llama-3.2-3B-Instruct",
    fast_inference=True,     # vLLM による高速生成（pip install unsloth vllm）
)
```

- vLLM が未対応のモデルでは `fast_inference=False` にします。
- 損失は `GRPOConfig` の `loss_type` で切り替えます。公式ガイドは GSPO（`loss_type='gspo'`）と Dr. GRPO（`'dr_grpo'`）への対応を挙げています。
- 公式ガイドの目安：報酬が上がり始めるまで**少なくとも 300 ステップ**は待つこと、データは 500 行以上が望ましいこと、思考トークンを安定して出すにはモデルは 1.5B 以上が望ましいこと。
- 無料ノートブックに GRPO・GSPO の例が多数あります。

### 5.7 向き・不向き

**向いている**：1枚の GPU で素早く LoRA / QLoRA を回したい、GGUF まで一気に作りたい、GRPO を小さく試したい、GUI で作業したい。

**注意**：独自最適化の層が挟まるため、最新モデルへの対応は Unsloth 側の更新に依存します。ライセンスが部分ごとに異なる（コア Apache-2.0、Studio AGPL-3.0、unsloth-zoo LGPL-3.0）ので、組み込み利用の際は確認が必要です。

**出典**：[unslothai/unsloth](https://github.com/unslothai/unsloth)（README、`unsloth-cli.py`）/ [Unsloth Docs](https://unsloth.ai/docs)（Fine-tuning Guide、Multi-GPU / DDP、Reinforcement Learning Guide）

---
## 第6章 LLaMA-Factory（LlamaFactory）

### 6.1 概要

| 項目 | 内容 |
|---|---|
| リポジトリ | [hiyouga/LlamaFactory](https://github.com/hiyouga/LlamaFactory)（旧名 LLaMA-Factory。旧 URL でも到達可能） |
| 最新版 | v0.9.5（2026-05-30）。main ブランチは 2026-11-11 時点でも更新が続く |
| ライセンス | Apache-2.0 |
| 対応手法 | 継続事前学習、（マルチモーダル）SFT、報酬モデル学習、PPO、DPO、KTO、ORPO、SimPO |
| 学習方式 | フル、Freeze、LoRA、QLoRA（2〜8bit）、OFT、QOFT |
| 特徴 | YAML 1枚で学習・推論・マージ。Web UI（LLaMA Board）。対応モデルが多い |

100 を超えるモデルに対応し、GaLore、BAdam、APOLLO、Adam-mini、Muon、DoRA、LongLoRA、LoRA+、LoftQ、PiSSA といった発展的な手法を設定項目として備えています。FlashAttention-2、Unsloth、Liger Kernel との連携や、2025年10月からは Megatron Core を学習バックエンドに使う構成にも対応しました。

### 6.2 インストール

README は**ソースからのインストールを必須**としています。

```bash
git clone --depth 1 https://github.com/hiyouga/LlamaFactory.git
cd LlamaFactory
pip install -e .
pip install -r requirements/metrics.txt
# DeepSpeed を使うなら requirements/deepspeed.txt も
```

Docker イメージ（`hiyouga/llamafactory:latest`）もあります。README 記載のイメージ構成は Ubuntu 22.04、CUDA 12.4、Python 3.11、PyTorch 2.6.0、flash-attn 2.7.4 です。

動作要件（README の表）：Python 3.11 以上、PyTorch は最低 2.0.0・推奨 2.6.0、CUDA は最低 11.6・推奨 12.2。最新の PyTorch 2.15 / CUDA 13 で使う場合は、main ブランチの状況を確認してから環境を固定するのが安全です。

### 6.3 基本の3コマンド

```bash
llamafactory-cli train  examples/train_lora/qwen3_lora_sft.yaml   # 学習
llamafactory-cli chat   examples/inference/qwen3_lora_sft.yaml    # 対話で確認
llamafactory-cli export examples/merge_lora/qwen3_lora_sft.yaml   # LoRA をマージ
```

Web UI を使う場合は `llamafactory-cli webui` です。

### 6.4 設定ファイルの読み方

同梱の `examples/train_lora/qwen3_lora_sft.yaml` を要約すると、次の5ブロックで構成されています。

```yaml
### model
model_name_or_path: Qwen/Qwen3-4B-Instruct-2507

### method
stage: sft              # sft / pt / rm / ppo / dpo / kto
do_train: true
finetuning_type: lora   # lora / oft / freeze / full
lora_rank: 8
lora_target: all

### dataset
dataset: identity,alpaca_en_demo   # data/dataset_info.json に登録した名前
template: qwen3_nothink            # チャットテンプレート
cutoff_len: 2048

### output
output_dir: saves/qwen3-4b/lora/sft
logging_steps: 10
save_steps: 500

### train
per_device_train_batch_size: 1
gradient_accumulation_steps: 8
learning_rate: 1.0e-4
num_train_epochs: 3.0
lr_scheduler_type: cosine
warmup_ratio: 0.1
bf16: true
```

- **自前のデータ**は `data/dataset_info.json` に登録して、`dataset:` に名前を書きます。Hugging Face / ModelScope 上のデータセット、ローカルファイル、S3 / GCS のパスが使えます。
- **`template`** はモデルに合ったものを選びます。ここを間違えると学習は進んでも推論が崩れます。
- 設定はコマンドラインから `key=value` で上書きできます（例：`llamafactory-cli train xxx.yaml learning_rate=1e-5`）。

### 6.5 マルチ GPU・マルチノード

既定では見えている GPU をすべて使います。絞る場合は `CUDA_VISIBLE_DEVICES` を指定します。

```bash
# GPU を指定
CUDA_VISIBLE_DEVICES=0,1 llamafactory-cli train examples/train_lora/qwen3_lora_sft.yaml

# フル FT（単一ノード・複数 GPU）
FORCE_TORCHRUN=1 llamafactory-cli train examples/train_full/qwen3_full_sft.yaml

# DeepSpeed ZeRO-3（重みを分割）
FORCE_TORCHRUN=1 llamafactory-cli train examples/train_lora/qwen3_lora_sft_ds3.yaml

# 2ノード（各ノードで NODE_RANK を変えて実行）
FORCE_TORCHRUN=1 NNODES=2 NODE_RANK=0 MASTER_ADDR=192.168.0.1 MASTER_PORT=29500 \
  llamafactory-cli train examples/train_full/qwen3_full_sft.yaml

# Ray で 4GPU
USE_RAY=1 llamafactory-cli train examples/train_lora/qwen3_lora_sft_ray.yaml
```

ノード数を伸縮させる耐障害構成（`MIN_NNODES` / `MAX_NNODES` / `MAX_RESTARTS`）や、FSDP と QLoRA を組み合わせるスクリプト（`examples/extras/fsdp_qlora/train.sh`）も用意されています。

### 6.6 選好最適化と RLHF

```bash
llamafactory-cli train examples/train_lora/qwen3_lora_dpo.yaml      # DPO / ORPO / SimPO
llamafactory-cli train examples/train_lora/qwen3_lora_kto.yaml      # KTO
llamafactory-cli train examples/train_lora/qwen3_lora_reward.yaml   # 報酬モデル
```

報酬モデルを学習してから PPO で方策を更新する、古典的な RLHF の流れをひととおり備えています。GRPO 系は README の対応手法には含まれていません。

### 6.7 推論・評価・デプロイ

```bash
# OpenAI 互換 API（vLLM バックエンド）
API_PORT=8000 llamafactory-cli api examples/inference/qwen3.yaml infer_backend=vllm vllm_enforce_eager=true

# vLLM で一括推論して BLEU / ROUGE を計算
python scripts/vllm_infer.py --model_name_or_path Qwen/Qwen3-4B-Instruct-2507 \
  --template qwen3_nothink --dataset alpaca_en_demo
python scripts/eval_bleu_rouge.py generated_predictions.jsonl
```

### 6.8 向き・不向き

**向いている**：設定ファイルだけで再現性よく回したい、Web UI でチームに使ってもらいたい、手法をいろいろ比較したい、Qwen・GLM・InternLM など中国発モデルを扱う。

**注意**：リリースタグの間隔が長く、実質的に main ブランチを追う運用になります。コミットを固定して使うのが無難です。マージ時は量子化モデルを使わないこと（README に明記）。

**出典**：[hiyouga/LlamaFactory](https://github.com/hiyouga/LlamaFactory)（README、`examples/README.md`、`examples/train_lora/qwen3_lora_sft.yaml`）/ [ドキュメント](https://llamafactory.readthedocs.io/en/latest/)

---

## 第7章 Axolotl

### 7.1 概要

| 項目 | 内容 |
|---|---|
| リポジトリ | [axolotl-ai-cloud/axolotl](https://github.com/axolotl-ai-cloud/axolotl) |
| 最新版 | v0.21.1（2026-10-27） |
| ライセンス | Apache-2.0 |
| 対応手法 | フル FT、LoRA、QLoRA、GPTQ、QAT、FP8 混合精度、NVFP4 / MXFP4 の MoE LoRA、選好チューニング（DPO / IPO / KTO / ORPO）、RL（GRPO / GDPO）、報酬モデル（RM / PRM） |
| 要件 | NVIDIA GPU（bf16 と Flash Attention には Ampere 以降）または AMD GPU、Python 3.12 以上、PyTorch 2.13 以上 |
| 特徴 | 1つの YAML で前処理・学習・評価・量子化・推論まで。分散学習の選択肢がもっとも豊富 |

Axolotl は**スケールアウトと最新手法への追随**が強みです。2026年だけでも、エキスパート並列（EP）、コンテキスト並列、FSDP2 + QLoRA の CPU 段階ロード、NVFP4 LoRA、非同期 GRPO、GGUF エクスポートなどが追加されています。要件に「Ampere 以降」と明記されており、A100 以降という本書の前提にそのまま合います。

### 7.2 インストール

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export UV_TORCH_BACKEND=cu130        # 環境に合わせる
uv venv --python 3.12 && source .venv/bin/activate
uv pip install torch==2.14.0 torchvision
uv pip install "axolotl[deepspeed]"

axolotl fetch examples               # サンプル設定を取得
axolotl fetch deepspeed_configs      # DeepSpeed の設定（任意）
```

Docker なら `docker run --gpus '"all"' --ipc=host --rm -it axolotlai/axolotl:main-latest` です。README も「Docker のほうが環境構築の失敗が少ない」としています。

### 7.3 最初の学習

```bash
axolotl train examples/llama-3/lora-1b.yml
```

設定ファイルの骨格は次のとおりです（同梱例を要約）。

```yaml
base_model: NousResearch/Llama-3.2-1B
datasets:
  - path: teknium/GPT4-LLM-Cleaned
    type: alpaca
val_set_size: 0.1
output_dir: ./outputs/lora-out

adapter: lora            # QLoRA は adapter: qlora と load_in_4bit: true。フル FT なら書かない
lora_r: 16
lora_alpha: 32
lora_dropout: 0.05
lora_target_modules: [q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj]

sequence_len: 2048
sample_packing: true     # 系列の詰め込み（multipack）

micro_batch_size: 2
gradient_accumulation_steps: 2
num_epochs: 1
optimizer: adamw_8bit
lr_scheduler: cosine
learning_rate: 0.0002
bf16: auto
attn_implementation: flash_attention_2
```

### 7.4 マルチ GPU

Axolotl は3つの分散方式に対応しており、併用はできません。

| 方式 | 設定 | 用途 |
|---|---|---|
| DDP | 既定（何も指定しない） | 1枚に収まるモデル |
| **FSDP2**（推奨） | `fsdp_version: 2` と `fsdp_config:` | 1枚に収まらないモデル。FSDP1 は削除済み |
| DeepSpeed | `deepspeed: deepspeed_configs/zero1.json` | ZeRO ステージ1〜3 |

```yaml
# FSDP2 の例
fsdp_version: 2
fsdp_config:
  offload_params: false
  cpu_ram_efficient_loading: true
  auto_wrap_policy: TRANSFORMER_BASED_WRAP
  transformer_layer_cls_to_wrap: Qwen3DecoderLayer
  state_dict_type: FULL_STATE_DICT
  reshard_after_forward: true
```

```bash
# DeepSpeed は設定ファイルか CLI 引数で
axolotl train config.yml --deepspeed deepspeed_configs/zero1.json
```

DeepSpeed は「VRAM に収まる範囲でオフロードがいちばん少ない設定」を選ぶのが基本で、ステージ1 → 2 → 3 の順に試します。長い系列を複数 GPU に分割するコンテキスト並列や、FSDP と QLoRA の併用、複数ノード学習、TP / CP / FSDP を組み合わせる N-D 並列にも専用のドキュメントがあります。

### 7.5 GRPO

Axolotl の GRPO は、**vLLM サーバーとトレーナを分けて動かす**構成が基本です。

```
ターミナル1（GPU 0）              ターミナル2（GPU 1）
vLLM サーバー  ←── HTTP ──→  トレーナ
ベースモデル + LoRA             1. プロンプトを vLLM へ送る
                                2. 応答を採点（報酬関数）
                                3. アドバンテージ計算と更新
                                4. LoRA の重みを vLLM に同期
```

必要なものは3つです。

1. `rl: grpo` を指定した YAML
2. 報酬関数を書いた Python モジュール
3. vLLM バックエンド（`axolotl vllm-serve config.yaml` でサーバーを起動するか、`vllm_mode: colocate` で学習用 GPU に同居させる）

```python
# 報酬関数の形
def my_reward(completions, **kwargs) -> list[float]:
    # completions[i][0]["content"] が i 番目の応答テキスト
    return [score(c[0]["content"]) for c in completions]
```

`async_prefetch: true` を指定すると、TRL の `AsyncGRPOTrainer` を使った非同期学習になります。公式ドキュメントには学習の健全性の目安（20 ステップ以内に報酬平均が立ち上がるか、報酬の標準偏差が 0 に張り付いていないか、エントロピーが極端に下がっていないか）が載っており、実運用で役立ちます。

### 7.6 そのほかの便利な機能

- `axolotl export`：GGUF へのエクスポート（量子化オプション付き）
- `axolotl agent-docs`：AI コーディングエージェント向けに最適化したドキュメントを表示（`sft` / `grpo` / `preference_tuning` などトピック別）
- `axolotl config-schema`：設定スキーマをダンプ。設定生成の自動化に使える
- クラウド連携：RunPod、Modal、SkyPilot、Hugging Face Jobs などで起動するための手順が用意されている

### 7.7 向き・不向き

**向いている**：複数 GPU・複数ノードでのフル FT、大きなモデルや MoE モデル、設定を Git 管理して再現性を確保したい、最新の最適化を早く使いたい。

**注意**：機能が多いぶん設定項目も多く、最初は同梱例から出発するのが近道です。更新が速いので、バージョンを固定して使います。

**出典**：[axolotl-ai-cloud/axolotl](https://github.com/axolotl-ai-cloud/axolotl)（README、`docs/multi-gpu.qmd`、`docs/agents/grpo.md`、`examples/llama-3/lora-1b.yml`）/ [Axolotl Docs](https://docs.axolotl.ai)

---

## 第8章 ms-swift

### 8.1 概要

| 項目 | 内容 |
|---|---|
| リポジトリ | [modelscope/ms-swift](https://github.com/modelscope/ms-swift) |
| 最新版 | v4.6.0（2026-10-13） |
| ライセンス | Apache-2.0 |
| 対応モデル | テキスト 600 以上、マルチモーダル 400 以上（README の記載） |
| 対応手法 | 事前学習、SFT、DPO / KTO / CPO / SimPO / ORPO、報酬モデル、PPO、GKD、GRPO 系、Embedding / Reranker / 系列分類 |
| 特徴 | ModelScope コミュニティ製。学習から推論・評価・量子化・デプロイまで一貫。Megatron 並列と GRPO 系を内蔵 |

対応ハードウェアとして NVIDIA（A100 / H100 / RTX 系）、AMD（ROCm）、Huawei Ascend などが挙げられています。軽量チューニングは LoRA、QLoRA、DoRA、LoRA+、LongLoRA、LoRA-GA、ReFT、RS-LoRA、Adapter など、分散は DDP、`device_map`、DeepSpeed ZeRO-2 / 3、FSDP / FSDP2、Megatron に対応します。

### 8.2 インストール

```bash
pip install ms-swift -U
# または
uv pip install ms-swift -U --torch-backend=auto
```

README の推奨環境は Python 3.12、CUDA 12.8 / 13.0、PyTorch 2.8.0 / 2.11.0 です。main ブランチが 4.x 系で、3.x 系は `release/3.12` ブランチにあります。

### 8.3 SFT

```bash
CUDA_VISIBLE_DEVICES=0 swift sft \
    --model Qwen/Qwen3-4B-Instruct-2507 \
    --tuner_type lora \
    --dataset 'AI-ModelScope/alpaca-gpt4-data-en#500' \
    --torch_dtype bfloat16 \
    --num_train_epochs 1 \
    --per_device_train_batch_size 1 \
    --gradient_accumulation_steps 16 \
    --learning_rate 1e-4 \
    --lora_rank 8 --lora_alpha 32 \
    --target_modules all-linear \
    --max_length 2048 \
    --output_dir output
```

- 既定では **ModelScope** からモデルとデータを取得します。Hugging Face を使うなら `--use_hf true` を付けます。
- データセット名の後ろの `#500` は、使う件数の指定です。
- 自前データは公式ドキュメントの形式に整えて `--dataset <path>` で渡します。

### 8.4 マルチ GPU・事前学習

```bash
# 8×A100 での事前学習（README の例）
NPROC_PER_NODE=8 CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
swift pt \
    --model Qwen/Qwen3-4B-Base \
    --dataset swift/chinese-c4 --streaming true \
    --tuner_type full \
    --deepspeed zero2 \
    --output_dir output --max_steps 10000
```

`NPROC_PER_NODE` でプロセス数を指定し、`--deepspeed zero2` / `zero3` で ZeRO を有効にします。

### 8.5 Megatron-SWIFT

大規模クラスタや MoE モデルの学習向けに、Megatron の並列化（TP / PP / CP / EP など）を使うモードがあります。事前学習・SFT・GRPO・DPO・KTO などに対応し、フル・LoRA・MoE・マルチモーダル・FP8 を扱えます。

```bash
NPROC_PER_NODE=2 CUDA_VISIBLE_DEVICES=0,1 megatron sft \
    --model Qwen/Qwen3-4B-Instruct-2507 \
    --save_safetensors true \
    --dataset AI-ModelScope/alpaca-gpt4-data-zh \
    --tuner_type lora \
    --output_dir output
```

### 8.6 選好最適化と GRPO

```bash
# DPO
CUDA_VISIBLE_DEVICES=0 swift rlhf --rlhf_type dpo \
    --model Qwen/Qwen3-4B-Instruct-2507 \
    --dataset hjh0119/shareAI-Llama3-DPO-zh-en-emoji \
    --tuner_type lora --output_dir output

# GRPO（4GPU、vLLM を同居）
CUDA_VISIBLE_DEVICES=0,1,2,3 NPROC_PER_NODE=4 swift rlhf --rlhf_type grpo \
    --model Qwen/Qwen3-4B-Instruct-2507 \
    --tuner_type lora \
    --use_vllm true --vllm_mode colocate \
    --dataset AI-MO/NuminaMath-TIR#10000 \
    --output_dir output
```

GRPO 系として GRPO、DAPO、GSPO、SAPO、CISPO、CHORD、RLOO、Reinforce++ を備え、vLLM の同期・非同期推論、プラグインによる報酬関数・マルチターンのスケジューラ・環境の拡張に対応します。

### 8.7 向き・不向き

**向いている**：Qwen 系をはじめ ModelScope 上のモデルを使う、マルチモーダルモデルの FT、1つの CLI で SFT から GRPO・評価・量子化までつなげたい。

**注意**：既定の取得先が ModelScope であること。依存ライブラリの対応範囲に上限があること（README の環境表では `peft` が 0.21 未満、`trl` が 1.0 未満など）から、ほかのフレームワークと同じ環境に混在させず、専用の仮想環境を用意するのが安全です。

**出典**：[modelscope/ms-swift](https://github.com/modelscope/ms-swift)（README）/ [ms-swift ドキュメント](https://swift.readthedocs.io/en/latest/)

---
## 第9章 そのほかの統合フレームワーク

第5〜8章の4つ以外にも、目的がはっきりしていれば有力な選択肢があります。

### 9.1 LitGPT（Lightning AI）

| 項目 | 内容 |
|---|---|
| リポジトリ | [Lightning-AI/litgpt](https://github.com/Lightning-AI/litgpt) |
| 最新版 | v0.5.14（2026-11-10） |
| ライセンス | Apache-2.0 |

20 以上の LLM を**抽象化なしでゼロから実装**しているのが特徴で、コードを読んで改造したい人に向いています。事前学習・継続事前学習・FT・評価・デプロイを1つの CLI で扱えます。

```bash
pip install 'litgpt[extra]'

# 自前の JSON データで FT → 対話で確認 → サーバー起動
litgpt finetune microsoft/phi-2 \
  --data JSON --data.json_path my_custom_dataset.json \
  --data.val_split_fraction 0.1 --out_dir out/custom-model
litgpt chat  out/custom-model/final
litgpt serve out/custom-model/final

# LoRA / QLoRA
litgpt finetune_lora stabilityai/stablelm-base-alpha-3b --quantize "bnb.nf4"
litgpt merge_lora "out/lora/step-002000"
```

LoRA・QLoRA・Adapter・Adapter v2 に対応し、精度（`bf16-true` / `bf16-mixed` / `32-true`）、GPU 数（`devices`）、ノード数（`num_nodes`）、量子化（`quantize`）は設定項目として指定します。検証済みの YAML レシピ集（`config_hub`）があり、`litgpt finetune --config <YAML の URL>` で使えます。マルチ GPU は FSDP ベースです。

### 9.2 NeMo AutoModel（NVIDIA）

| 項目 | 内容 |
|---|---|
| リポジトリ | [NVIDIA-NeMo/Automodel](https://github.com/NVIDIA-NeMo/Automodel) |
| 最新版 | v0.7.0（2026-10-21） |
| ライセンス | Apache-2.0 |

PyTorch の DTensor をネイティブに使う SPMD（単一プログラム・複数データ）型の学習ライブラリで、LLM・VLM・拡散モデル・検索モデルの学習と FT を対象にします。「同じスクリプトが1枚から1000枚超まで、メッシュの設定を変えるだけで動く」ことを設計の中心に据え、FSDP2、HSDP、TP、CP、SP、PP を組み合わせられます。FP8、MoE の高速化、Hugging Face モデルのデイゼロ対応も特徴です。NeMo RL と Molt の学習バックエンドでもあります（第14章）。

```bash
# コンテナで 2GPU の FT を 10 ステップだけ試す
docker run --gpus all -it --rm --shm-size=8g \
  -v "$PWD/checkpoints:/opt/Automodel/checkpoints" \
  nvcr.io/nvidia/nemo-automodel:26.10.00 \
  automodel /opt/Automodel/examples/llm_finetune/qwen/qwen3_0p6b_hellaswag.yaml \
  --nproc-per-node 2 --step_scheduler.max_steps 10

# ソースから（uv）
uv venv && uv sync --frozen
automodel examples/llm_finetune/qwen/qwen3_0p6b_hellaswag.yaml --nproc-per-node 8   # FSDP2 で 8GPU
automodel examples/llm_finetune/qwen/qwen3_0p6b_hellaswag_peft.yaml                 # LoRA
```

レシピは YAML で、任意の項目を CLI から上書きできます。複数ノードは Slurm の sbatch スクリプト（`slurm.sub`）を雛形にします。

### 9.3 Oumi

| 項目 | 内容 |
|---|---|
| リポジトリ | [oumi-ai/oumi](https://github.com/oumi-ai/oumi) |
| 最新版 | v0.9（2026-09-16） |
| ライセンス | Apache-2.0 |

データ準備から学習・評価・デプロイまで、基盤モデルのライフサイクル全体を同じ設定体系で扱うプラットフォームです。手元のマシンでもクラウドでも同じ YAML が使えます。

```bash
uv pip install 'oumi[gpu]'
oumi train    -c configs/recipes/smollm/sft/135m/quickstart_train.yaml
oumi evaluate -c configs/recipes/smollm/evaluation/135m/quickstart_eval.yaml
oumi infer    -c configs/recipes/smollm/inference/135m_infer.yaml --interactive
oumi launch up -c configs/recipes/smollm/sft/135m/quickstart_gcp_job.yaml --resources.cloud aws
```

### 9.4 Ludwig

| 項目 | 内容 |
|---|---|
| リポジトリ | [ludwig-ai/ludwig](https://github.com/ludwig-ai/ludwig) |
| 最新版 | v0.17.10（2026-10-26） |
| ライセンス | Apache-2.0 |

宣言的な機械学習フレームワークで、LLM の FT も YAML だけで定義できます。Linux Foundation AI & Data がホストしています。

```yaml
model_type: llm
base_model: meta-llama/Llama-3.1-8B
adapter:
  type: lora
trainer:
  type: finetune
  epochs: 3
input_features:
  - name: instruction
    type: text
output_features:
  - name: response
    type: text
```

```bash
pip install "ludwig[llm]"
ludwig train --config model.yaml --dataset my_data.csv
```

### 9.5 H2O LLM Studio

| 項目 | 内容 |
|---|---|
| リポジトリ | [h2oai/h2o-llmstudio](https://github.com/h2oai/h2o-llmstudio) |
| 最新版 | v1.15.4（2026-11-04） |
| ライセンス | Apache-2.0 |

ブラウザの GUI で学習設定・実験比較・公開までを行うノーコード寄りのツールです。CLI でも回せます。

```bash
wave run llm_studio.app                                   # GUI
uv run python llm_studio/train.py -Y {設定YAMLのパス}       # CLI
```

RLHF（PPO）は廃止の方向で、選好最適化は DPO / IPO に寄せられています。

### 9.6 XTuner

[InternLM/xtuner](https://github.com/InternLM/xtuner)（v1.0.1、2026-05-15、Apache-2.0）は、V1 で**超大規模 MoE モデル向けの学習エンジン**として作り直されました。従来の「軽量 FT ツールキット」としての XTuner とは性格が変わっている点に注意してください。PyPI の `xtuner` パッケージは 0.2.0（2025-07）のままなので、V1 を使う場合はリポジトリから導入します。

### 9.7 アプリ型・実験管理型のツール

| OSS | 最新版 | ライセンス | 内容 |
|---|---|---|---|
| [Kiln](https://github.com/Kiln-AI/Kiln) | v1.2.1（2026-11-10） | MIT | デスクトップアプリ + ライブラリ。評価の自動生成、合成データ生成、FT、プロンプト最適化をひとつの流れで扱う |
| [Transformer Lab](https://github.com/transformerlab/transformerlab-app) | v0.40.1（2026-06-19） | AGPL-3.0 | 学習・FT・対話・評価を GUI で扱う ML プラットフォーム。フル FT、LoRA / QLoRA、DPO 系、報酬モデル学習に対応し、手元でもリモートクラスタでも同じ UI で回せる |
| [RapidFire AI](https://github.com/RapidFireAI/rapidfireai) | v0.16.2（2026-10-20） | Apache-2.0 | TRL の上で複数の設定を同時に走らせ、途中で止めたり複製したりできる実験エンジン。TRL 公式ドキュメントに連携ガイドあり |

### 9.8 そのほか

| OSS | 状況 | メモ |
|---|---|---|
| [LMFlow](https://github.com/OptimalScale/LMFlow) | v1.0.0（2025-07）、最終コミット 2026-08 | 研究向けの FT ツールボックス |
| [xTuring](https://github.com/stochasticai/xTuring) | 最終タグ 2023-09、最終コミット 2026-09 | シンプルな API での FT |
| [LLM Finetuning Toolkit](https://github.com/georgian-io/LLM-Finetuning-Toolkit) | v0.2.3（2024-07）、最終コミット 2026-10 | YAML 1枚で実験を回す CLI（`llmtune run`） |
| [360-LLaMA-Factory](https://github.com/Qihoo360/360-LLaMA-Factory) | 最終コミット 2025-10 | LLaMA-Factory に系列並列（長文学習）を足した派生 |
| [llama-cookbook](https://github.com/meta-llama/llama-cookbook) | 最終コミット 2025-11 | Llama 系の FT・推論レシピ集（Meta 公式） |

### 9.9 JAX 系（参考）

NVIDIA GPU を前提とする本書では参考扱いですが、Google 系のスタックも挙げておきます。

| OSS | 最新版 | 内容 |
|---|---|---|
| [Tunix](https://github.com/google/tunix) | v0.1.7（2026-06-09） | JAX ネイティブの事後学習ライブラリ。SFT、PEFT、DPO / ORPO、PPO、GRPO 系に対応。TPU 上の vLLM 連携や MaxText との統合が中心 |
| [MaxText](https://github.com/AI-Hypercomputer/maxtext) | 継続更新 | 純 Python / JAX の高性能 LLM 実装。Google Cloud の TPU と GPU が対象 |
| [Keras Hub](https://github.com/keras-team/keras-hub) | v0.33.0（2026-11-03） | Keras 用の事前学習済みモデル集 |
| [Levanter](https://github.com/stanford-crfm/levanter) | 最終コミット 2025-11 | 可読性と再現性を重視した JAX の学習フレームワーク |

**出典**：各リポジトリの README（付録A）

---

## 第10章 大規模・分散学習の基盤とカーネル

統合フレームワークの下で実際に計算を担っている層です。数十B を超えるモデルのフル FT や MoE モデルを扱うなら、ここを直接触る場面が出てきます。

### 10.1 学習エンジン

| OSS | 最新版 | ライセンス | 位置づけ |
|---|---|---|---|
| **FSDP2**（PyTorch 標準） | PyTorch 2.15 | — | パラメータ分割の標準。TRL、Axolotl、verl、prime-rl などが利用 |
| [**DeepSpeed**](https://github.com/deepspeedai/DeepSpeed) | 0.19.9（2026-10-29） | Apache-2.0 | ZeRO による分割とオフロード。Transformers の `deepspeed=` で設定ファイルを渡すだけで使える。リポジトリは `deepspeedai` 組織に移っている |
| [**Megatron-LM / Megatron Core**](https://github.com/NVIDIA/Megatron-LM) | megatron-core 0.20.0（2026-10-29） | BSD 系（NVIDIA） | 大規模学習の定番。TP / PP / DP / EP / CP を組み合わせる |
| [**Megatron-Bridge**](https://github.com/NVIDIA-NeMo/Megatron-Bridge) | v0.7.0（2026-10-27） | Apache-2.0 | Hugging Face ⇔ Megatron の双方向変換と、Megatron Core を使う学習ループ（事前学習・SFT・LoRA） |
| [**torchtitan**](https://github.com/pytorch/torchtitan) | v0.4.0（2026-10-28） | BSD-3-Clause | PyTorch ネイティブの大規模学習基盤。FSDP2・TP・PP・CP・EP を DeviceMesh で合成。事前学習から SFT、RL（TitanRL）まで |
| [**NeMo AutoModel**](https://github.com/NVIDIA-NeMo/Automodel) | v0.7.0 | Apache-2.0 | 第9章参照 |
| [VeOmni](https://github.com/ByteDance-Seed/VeOmni) | v0.1.13（2026-09-30） | Apache-2.0 | ByteDance のモデル中心の分散学習レシピ集。verl の学習エンジンの1つ |
| [Nanotron](https://github.com/huggingface/nanotron) | 最終コミット 2026-10 | Apache-2.0 | 事前学習用のミニマルなライブラリ |
| [LLM Foundry](https://github.com/mosaicml/llm-foundry) | v0.22.0（2025-07）、最終コミット 2026-03 | Apache-2.0 | Composer ベースの学習・FT・評価コード。更新は緩やか |
| [Colossal-AI](https://github.com/hpcaitech/ColossalAI) | v0.5.1（2025-06） | Apache-2.0 | 分散学習の統合システム |

**Megatron Core の導入**

```bash
uv pip install megatron-core
# ソースからなら
git clone https://github.com/NVIDIA/Megatron-LM.git && cd Megatron-LM && uv pip install -e .
```

Python 3.12 以上・PyTorch 2.6 以上が推奨です。分散 RL 基盤の多く（verl、slime、Miles、ROLL、AReaL、NeMo RL、ms-swift）が Megatron をバックエンドの選択肢として持つため、直接使わなくても間接的にお世話になるライブラリです。

**torchtitan の導入**

```bash
git clone https://github.com/pytorch/torchtitan && cd torchtitan
pip install --pre torch --index-url https://download.pytorch.org/whl/nightly/cu132
pip install -r requirements.txt
NGPU=1 ./run_train.sh        # デバッグ用モデルで 10 ステップ
```

レシピが Python の関数として書かれており、「実行内容を変える＝関数を書く」という設計です。PyTorch の nightly を前提にしている点に注意します。

### 10.2 どのエンジンを選ぶか

| 状況 | 選択 |
|---|---|
| LoRA / QLoRA、1枚に収まるフル FT | DDP で十分 |
| 1枚に収まらないフル FT（〜数十B） | FSDP2。設定の手軽さを優先するなら DeepSpeed ZeRO-2 / 3 |
| 100B 超、MoE、長大コンテキスト | Megatron 系、torchtitan、NeMo AutoModel |
| RL と同じ基盤で SFT も回したい | RL 基盤側の SFT レシピ（verl、NeMo RL、prime-rl、Molt など）を使う |

### 10.3 カーネルと最適化ライブラリ

| OSS | 最新版 | 役割 | A100 以降での要点 |
|---|---|---|---|
| [FlashAttention](https://github.com/Dao-AILab/flash-attention) | 2.8.3.post2（2026-10-14） | 高速・省メモリな注意機構 | 2 系は Ampere 以降。3 系は Hopper、4 系は Hopper と Blackwell |
| [Liger-Kernel](https://github.com/linkedin/Liger-Kernel) | 0.8.5（2026-10-21） | Triton 製の学習用カーネル | DPO、KTO、GRPO 系など事後学習の損失も最適化 |
| [Transformer Engine](https://github.com/NVIDIA/TransformerEngine) | v2.21.0（2026-10-30） | FP8 などの低精度学習 | Hopper 以降向け |
| [torchao](https://github.com/pytorch/ao) | 0.18.0（2026-08-03） | 量子化・QAT・低精度 | Axolotl、Unsloth、NeMo AutoModel が利用 |
| [Hugging Face kernels](https://github.com/huggingface/kernels) | v0.18.2（2026-11-09） | ビルド済みカーネルを Hub から読み込む仕組み | TRL が `kernels-community/flash-attn2` などで利用 |

**出典**：各リポジトリの README（付録A）/ [Megatron Core 開発者ガイド](https://docs.nvidia.com/megatron-core/developer-guide/latest/)

---

## 第11章 開発が終了・停止した FT 系 OSS

古い記事やチュートリアルに頻出するため、現状を整理しておきます。**新規に採用するのは避け、後継を使ってください。**

| OSS | 状況（README の記載など） | 後継・代替 |
|---|---|---|
| [torchtune](https://github.com/meta-pytorch/torchtune) | 「もう積極的には保守されていない。開発は 2025年に終了」と明記。最終リリース v0.6.1（2025-04） | PyTorch 系は torchtitan、一般用途は TRL / Axolotl / Unsloth |
| [AutoTrain Advanced](https://github.com/huggingface/autotrain-advanced) | 「保守終了。新機能の追加もバグ修正も行わない」と明記 | README が Axolotl、TRL、`transformers.Trainer` を案内 |
| [mistral-finetune](https://github.com/mistralai/mistral-finetune) | 「アーカイブ済み、保守終了」と明記。最終リリース v1.1.0（2024-07） | Axolotl、TRL（Mistral 系モデルの例あり） |
| [nanoGPT](https://github.com/karpathy/nanoGPT) | 「非常に古く非推奨」。後継として nanochat を案内 | [nanochat](https://github.com/karpathy/nanochat) |
| [QLoRA（研究コード）](https://github.com/artidoro/qlora) | 最終コミット 2023-07 | PEFT + bitsandbytes に統合済み |
| [microsoft/LoRA（loralib）](https://github.com/microsoft/LoRA) | 最終コミット 2024-12 | PEFT |
| [Firefly](https://github.com/yangjianxin1/Firefly) | 最終コミット 2024-10 | LlamaFactory、ms-swift |

また、NVIDIA の `NVIDIA/NeMo` リポジトリは現在、音声 AI（NeMo Speech）を中心とした内容になっています。LLM の学習・FT は `NVIDIA-NeMo` 組織配下の AutoModel、Megatron-Bridge、RL などに分かれました。

**出典**：各リポジトリの README

---
# 第III部 強化学習 OSS

## 第12章 LLM×RL システムの共通構造

### 12.1 4つの部品

LLM の RL 基盤は、名前や実装が違っても同じ骨格を持っています。1回の反復は次の流れです。

```
(1) プロンプト ──→ ロールアウト（推論エンジンが応答を生成）
(2) 応答       ──→ 報酬の計算（関数・検証器・環境・審査モデル）
(3) 報酬つきサンプル ──→ データバッファ
(4) バッファ   ──→ 学習（アドバンテージ計算と方策の更新）
(5) 更新した重み ──→ 推論エンジンへ同期 ──→ (1) に戻る
```

| 部品 | 役割 | 主な選択肢 |
|---|---|---|
| **ロールアウト** | 現在の方策で応答を生成する | vLLM、SGLang、Transformers の `generate` や連続バッチ |
| **報酬** | 応答を採点する | Python 関数（答え合わせ・形式チェック）、報酬モデル、LLM による審査、サンドボックスでのコード実行、環境 |
| **学習** | アドバンテージを計算して方策を更新する | FSDP2、DeepSpeed、Megatron、NeMo AutoModel |
| **オーケストレーション** | 部品の配置と受け渡しを管理する | Ray（多数派）、独自実装、Kubernetes、Slurm |

### 12.2 設計上の分かれ目

**同居（colocate）か分離（server）か**
推論エンジンを学習と同じ GPU に同居させると枚数を節約できますが、メモリの取り合いになります。別の GPU に分けると安定しますが、枚数が必要です。TRL の `GRPOTrainer` は両方のモードを持ち、同居が既定です。分離モードで同じ GPU を共有すると NCCL エラーの原因になるため、`CUDA_VISIBLE_DEVICES` で分けます。

**同期か非同期か**
同期方式は「全サンプルの生成完了 → 学習 → 重み同期」を順に繰り返します。非同期方式は生成と学習を並走させ、古すぎるサンプルだけを捨てます。応答長のばらつきやツール実行の待ち時間が大きいタスクでは、非同期の効果が大きくなります。

**重みの同期方法**
LoRA ならアダプタを推論サーバーに読み込ませるだけで済みます。フル FT では全重みの転送が必要で、NCCL による直接転送、共有ストレージ経由、差分圧縮（NeMo RL の NeMo-DCR、slime の差分同期）といった工夫があります。

**学習と推論のズレへの対処**
第2章で触れたとおり、推論エンジンの出力確率は学習エンジンと厳密には一致しません。重要度サンプリング補正のほか、verl の `vexact`（学習と同じモデル定義でロールアウトする）のように、ズレ自体をなくす方向の実装も出ています。

### 12.3 GPU の配分の考え方

RL は SFT より GPU を多く使います。学習用のメモリに加えて、推論エンジンのメモリ、参照モデル（KL 制約を使う場合）、クリティック（PPO の場合）が要るためです。

- **1枚で試す**：小さなモデル + LoRA + 同居モード。TRL の連続バッチ生成（`use_transformers_continuous_batching`）や vLLM のスリープモード（`vllm_enable_sleep_mode`）がメモリ節約に使えます。
- **2〜8枚**：推論と学習を別の GPU に分ける。prime-rl の動作確認手順でも、RL のフルスタックには 2GPU が必要とされています。
- **複数ノード**：verl、NeMo RL、OpenRLHF、ROLL、AReaL、slime などの分散基盤へ。

---

## 第13章 まず手元で試す RL

分散基盤に進む前に、単一ノードで動かせる選択肢から始めるのが近道です。

### 13.1 TRL の GRPOTrainer

```python
# train_grpo.py
from datasets import load_dataset
from trl import GRPOTrainer
from trl.rewards import accuracy_reward   # pip install "trl[math_verify]" が必要

dataset = load_dataset("trl-lib/DeepMath-103K", split="train")

trainer = GRPOTrainer(
    model="Qwen/Qwen2.5-0.5B-Instruct",
    reward_funcs=accuracy_reward,
    train_dataset=dataset,
)
trainer.train()
```

```bash
torchrun --nproc_per_node 8 train_grpo.py
```

公式ドキュメントによれば、この例は 8GPU で約1日かかります。RL は SFT に比べて桁違いに時間がかかるという感覚を、最初に持っておくとよいでしょう。推論モデルには `reasoning_accuracy_reward` の利用が勧められています。

**自作の報酬関数**

報酬関数はキーワード引数で `prompts`、`completions`、`completion_ids`、`trainer_state` などと、データセットの各列を受け取り、応答ごとの実数のリストを返します。`**kwargs` で受けるのが簡単です。非同期関数（`async def`）も使え、複数ある場合は並行に実行されます。

```python
from trl import GRPOConfig, GRPOTrainer

def format_reward(completions, **kwargs):
    # 会話形式ではメッセージのリスト、標準形式では文字列が渡される
    texts = [c[0]["content"] if isinstance(c, list) else c for c in completions]
    return [1.0 if "\\boxed{" in t else 0.0 for t in texts]

def length_penalty(completion_ids, **kwargs):
    return [-0.001 * len(ids) for ids in completion_ids]

args = GRPOConfig(
    output_dir="out/grpo",
    num_generations=8,             # 1プロンプトあたりの生成数
    max_completion_length=1024,
    learning_rate=1e-6,
    reward_weights=[1.0, 0.5],     # 複数の報酬関数の重み
    use_vllm=True,                 # vLLM で生成（既定は同居モード）
)
trainer = GRPOTrainer(
    model="Qwen/Qwen2.5-0.5B-Instruct",
    reward_funcs=[format_reward, length_penalty],
    args=args,
    train_dataset=dataset,
)
```

**生成の高速化**

| 方法 | 設定 | 特徴 |
|---|---|---|
| vLLM 同居 | `use_vllm=True`（`vllm_mode="colocate"` が既定） | サーバー不要。学習とメモリを取り合う |
| vLLM 分離 | `use_vllm=True, vllm_mode="server"` | 推論専用の GPU がある場合に最適 |
| 連続バッチ | `use_transformers_continuous_batching=True` | サーバーも重み同期も不要。単一 GPU 向け |

分離モードでは、先に vLLM サーバーを起動します。

```bash
VLLM_SERVER_DEV_MODE=1 vllm serve <model_name> \
    --weight-transfer-config '{"backend": "nccl"}' \
    --logprobs-mode processed_logprobs \
    --max-logprobs -1
```

同居モードで OOM になる場合は、`vllm_gpu_memory_utilization` を調整するか、`vllm_enable_sleep_mode=True` で最適化ステップ中に vLLM の重みを退避させます。vLLM 利用時は、系列単位のマスク付き重要度サンプリング補正が既定で有効です。

**損失の種類**

`loss_type` で集計方法を選べます。既定は `"dapo"` で、ほかに `"dr_grpo"`、`"bnpo"`、`"grpo"` などがあります。

**エージェント学習**

`GRPOTrainer` はツール呼び出しと環境に対応しています。`environment_factory` に環境クラスを渡すと、エピソード中の状態を報酬関数から参照できます。OpenEnv の環境（Wordle など）を使う手順や、Harbor 上で実際のコーディングエージェントのハーネスを動かして学習する手順が公式ガイドにあります（第16章）。

### 13.2 TRL のそのほかのトレーナ

| トレーナ | 手法 | 区分 |
|---|---|---|
| `SFTTrainer` | SFT | 安定版 |
| `DPOTrainer` | DPO | 安定版 |
| `KTOTrainer` | KTO | 安定版 |
| `GRPOTrainer` | GRPO 系 | 安定版 |
| `RLOOTrainer` | RLOO | 安定版 |
| `RewardTrainer` | 報酬モデルの学習 | 安定版 |
| `DistillationTrainer` | オンポリシー蒸留 | 安定版 |
| `AsyncGRPOTrainer` | 非同期 GRPO | 実験的 |
| Online DPO、ORPO、CPO、GKD、GOLD など | — | 実験的（`trl.experimental`） |

```python
from datasets import load_dataset
from trl import DPOTrainer

trainer = DPOTrainer(
    model="Qwen/Qwen3-0.6B",
    train_dataset=load_dataset("trl-lib/ultrafeedback_binarized", split="train"),
)
trainer.train()
```

CLI なら `trl dpo` / `trl kto` / `trl grpo` / `trl rloo` / `trl reward` です。

```bash
trl grpo --model_name_or_path Qwen/Qwen2.5-0.5B \
    --dataset_name HuggingFaceH4/Polaris-Dataset-53K \
    --reward_funcs accuracy_reward
```

`AsyncGRPOTrainer` は vLLM サーバー（開発モードと NCCL による重み転送が必須）を別 GPU で起動し、生成と学習を並走させます。

なお、かつて TRL にあった PPO トレーナは現在の一覧にはありません。古典的な RLHF（報酬モデル + PPO）を行うなら、LlamaFactory、ms-swift、OpenRLHF、verl などを使います。

### 13.3 統合フレームワークの RL 機能

| フレームワーク | RL / 選好最適化 | 補足 |
|---|---|---|
| **Unsloth** | GRPO（GSPO、Dr. GRPO）、DPO | TRL のトレーナを利用。省メモリ。ノートブックが豊富（第5章） |
| **Axolotl** | GRPO、GDPO、DPO / IPO / KTO / ORPO、RM / PRM | vLLM サーバー分離が基本。非同期 GRPO に対応（第7章） |
| **ms-swift** | GRPO、DAPO、GSPO、SAPO、CISPO、CHORD、RLOO、Reinforce++、PPO、DPO 系 | `swift rlhf --rlhf_type ...`。Megatron 連携あり（第8章） |
| **LlamaFactory** | 報酬モデル、PPO、DPO、KTO、ORPO、SimPO | 古典的 RLHF をひととおり。GRPO 系は README に記載なし（第6章） |
| **H2O LLM Studio** | DPO / IPO | RLHF（PPO）は廃止の方向 |

### 13.4 ここまでで足りなくなったら

次のような要求が出てきたら、第14章の分散基盤を検討します。

- 複数ノードで学習と推論の GPU を柔軟に割り振りたい
- 数十B 以上のモデルをフル FT で RL にかけたい（Megatron が必要）
- 生成と学習を非同期にしてスループットを上げたい
- サンドボックスやツールを含む長いエピソードを大量に並列実行したい

**出典**：[TRL ドキュメント](https://huggingface.co/docs/trl)（GRPO Trainer、Asynchronous GRPO、vLLM Integration、OpenEnv Integration、CLIs）/ [huggingface/trl](https://github.com/huggingface/trl)（`trl/trainer/grpo_config.py`）

---

## 第14章 分散 RL 基盤

### 14.1 比較表

| OSS | 開発元 | 最新版 | 学習エンジン | ロールアウト | 実行基盤 | 非同期 |
|---|---|---|---|---|---|---|
| **verl** | ByteDance Seed 発、コミュニティ運営 | v0.9.1（2026-09-20） | FSDP / FSDP2 / Megatron / VeOmni | vLLM / SGLang ほか | Ray | 対応（発展中） |
| **OpenRLHF** | コミュニティ | v0.11.2（2026-09-14） | DeepSpeed | vLLM | Ray | 対応 |
| **NeMo RL** | NVIDIA | v0.8.0（2026-11-06） | AutoModel / Megatron | vLLM / SGLang / Megatron 推論 | Ray | 対応 |
| **Molt** | NVIDIA（Labs） | v0.2.2（2026-11-06） | AutoModel（FSDP2） | vLLM | Ray | 完全非同期 |
| **ROLL** | Alibaba | v0.4.0（2026-09-29） | FSDP2 / Megatron | vLLM / SGLang | Ray | 対応 |
| **AReaL** | Ant Group・清華大 | v2.1.1（2026-11-04） | Megatron / FSDP / Archon | SGLang（既定）/ vLLM | ローカル / Ray | 完全非同期 |
| **slime** | 清華大 THUDM・Z.ai | v0.4.0（2026-10-09） | Megatron | SGLang | Ray | 同期・完全非同期 |
| **Miles** | RadixArk | v0.1.3（2026-10-22） | Megatron（FSDP2・torchtitan も） | SGLang | Ray / Kubernetes | 完全非同期 |
| **prime-rl** | Prime Intellect | v0.10.0（2026-10-14） | FSDP2 | vLLM | 独自 + Slurm | 完全非同期 |
| **SkyRL** | UC Berkeley NovaSky | skyrl 0.4.0（2026-10-01） | FSDP ほか | vLLM ほか | Ray | —（未確認） |
| **Trinity-RFT** | Alibaba（AgentScope） | v0.6.0（2026-06-26） | verl / Tinker を利用 | vLLM / SGLang | Ray | 対応 |

ライセンスはいずれも Apache-2.0 です。

### 14.2 verl

[verl-project/verl](https://github.com/verl-project/verl) は HybridFlow 論文の OSS 版で、もっとも広く使われている分散 RL 基盤です。2026年1月に `volcengine/verl` から `verl-project` 組織へ移管されました。

**特徴**
- 学習は FSDP・FSDP2・Megatron-LM、ロールアウトは vLLM・SGLang・Transformers
- PPO、GRPO、GSPO、ReMax、REINFORCE++、RLOO、PRIME、DAPO、Dr. GRPO など多数のアルゴリズム（一部は別リポジトリ `verl-recipe`）
- 関数ベースとモデルベースの報酬、VLM、ツール呼び出しを伴うマルチターン、LoRA による RL
- エキスパート並列で 671B 級・数百 GPU までスケールした実績
- NVIDIA、AMD、Huawei Ascend に対応

**要件**：Python 3.10 以上、CUDA 12.8 以上。vLLM は 0.18.0 以降のみ対応。

**環境構築の考え方**：verl は uv を前提にしており、**インストール手順がありません**。`uv run --extra ...` が初回にロックファイルから仮想環境を作ります。バックエンドは extras で選びます（推論：`vllm` / `sglang`、学習：`fsdp` / `megatron` / `veomni`）。対象は Linux の Python 3.12（x86_64 と aarch64）で、ネイティブ拡張はビルド済みホイールを verl の配布インデックスから取得します。

```bash
git clone https://github.com/verl-project/verl.git && cd verl

# そのまま実行できるサンプル（GRPO、Qwen3-8B、FSDP 学習）
bash examples/grpo_trainer/run_qwen3_8b_fsdp.sh

# 推論バックエンドを SGLang に変える
INFER_BACKEND=sglang bash examples/grpo_trainer/run_qwen3_8b_fsdp.sh
```

サンプルスクリプトは環境変数で調整できます（`MODEL_PATH`、`NNODES`、`NGPUS_PER_NODE`、`TRAIN_BATCH_SIZE`、`ROLLOUT_N` など）。`MACHINE=gb200` で Blackwell 向けの設定に切り替わります。

自分で起動する場合は、Hydra 形式の `key=value` で設定を渡します。

```bash
UV_RUN="uv run --frozen --all-packages --extra vllm --extra fsdp"
$UV_RUN python3 examples/data_preprocess/gsm8k.py --local_save_dir ~/data/gsm8k

$UV_RUN python3 -m verl.trainer.main_ppo \
  data.train_files=$HOME/data/gsm8k/train.parquet \
  data.val_files=$HOME/data/gsm8k/test.parquet \
  data.train_batch_size=256 \
  actor_rollout_ref.model.path=Qwen/Qwen2.5-0.5B-Instruct \
  actor_rollout_ref.actor.optim.lr=1e-6 \
  actor_rollout_ref.rollout.name=vllm \
  trainer.n_gpus_per_node=8 \
  ray_kwargs.ray_init.runtime_env.py_executable="${UV_RUN}"
```

データは事前に Parquet へ変換しておきます。クイックスタートの例は 24GB 以上の GPU 1枚から試せます。同じジョブの中では extras の組み合わせを変えないこと（変えるたびに PyTorch が入れ直されます）。

**エコシステム**：`verl-recipe`（アルゴリズムのレシピ集）、`uni-agent`（エージェント学習、第15章）、`vexact`（ズレのないロールアウト）、`rl-insight`（学習の可観測性）、VeRL-Tinker（Tinker Cookbook のループを自前 GPU で動かす）など。

### 14.3 OpenRLHF

[OpenRLHF/OpenRLHF](https://github.com/OpenRLHF/OpenRLHF) は Ray + vLLM 構成の先駆けで、簡潔な設計と見通しのよいコード構造を特徴に掲げています。README の冒頭では、NVIDIA の Molt（14.5 節）が「推奨」として紹介されています。

**特徴**
- PPO、REINFORCE++、REINFORCE++-baseline、GRPO、Dr. GRPO、RLOO、FlashREINFORCE
- 「エージェント実行パイプライン」に一本化した設計。単発生成（既定）とマルチターンのどちらでも、同じアルゴリズムが使える
- SFT、DPO / IPO / cDPO、報酬モデル学習、VLM、LoRA / QLoRA、DeepSpeed の AutoTP、長文向けの RingAttention

```bash
# コンテナ内で（README 推奨は NGC の PyTorch イメージ）
pip install "openrlhf[vllm]"

ray start --head --node-ip-address 0.0.0.0 --num-gpus 8

ray job submit --address="http://127.0.0.1:8265" \
  --runtime-env-json='{"working_dir": "/openrlhf"}' \
  -- python3 -m openrlhf.cli.train_ppo_ray \
  --actor.model_name_or_path OpenRLHF/Llama-3-8b-sft-mixture \
  --reward.model_name_or_path OpenRLHF/Llama-3-8b-rm-700k \
  --actor.num_nodes 1 --actor.num_gpus_per_node 8 \
  --vllm.num_engines 4 --vllm.tensor_parallel_size 2 \
  --train.colocate_all \
  --train.batch_size 128 --rollout.batch_size 1024 \
  --data.prompt_dataset OpenRLHF/prompt-collection-v0.1 \
  --data.input_key context_messages --data.apply_chat_template \
  --ds.zero_stage 3 --ds.param_dtype bf16 \
  --actor.adam.lr 5e-7 --critic.adam.lr 9e-6 \
  --ckpt.output_dir ./ckpt/llama3-8b-rlhf
```

アルゴリズムは `--algo.advantage.estimator` で切り替えます。

| 値 | アルゴリズム |
|---|---|
| （既定） | PPO |
| `reinforce` | REINFORCE++ |
| `reinforce_baseline` | REINFORCE++-baseline（RLVR 向けに推奨） |
| `group_norm` | GRPO |
| `dr_grpo` | Dr. GRPO |
| `rloo` | RLOO |

報酬モデルの代わりに関数を使う場合は、`reward_func(queries, prompts, labels)` を定義して `rewards`・`scores`・`extra_logs` を含む辞書を返します。README の注意点として、オプション名が `--actor.*`、`--vllm.*`、`--algo.*` のように名前空間つきになっています。古い記事のフラグ名とは異なるので注意してください。

### 14.4 NeMo RL

[NVIDIA-NeMo/RL](https://github.com/NVIDIA-NeMo/RL) は NVIDIA の本格的な事後学習ライブラリです。学習バックエンドは AutoModel（PyTorch ネイティブ）と Megatron から、YAML の設定に応じて自動で選ばれます。

**特徴**：GRPO / GSPO / DAPO、SFT（LoRA 対応）、DPO、オンポリシー蒸留、トークナイザが異なるモデル間の蒸留、マルチターン RL、NeMo Gym との連携、Ray による分散、コンポーネント間の依存分離。

```bash
# コンテナ（推奨）
docker pull nvcr.io/nvidia/nemo-rl:latest
git clone git@github.com:NVIDIA-NeMo/RL.git nemo-rl --recursive && cd nemo-rl
# コンテナ内で
uv run python examples/run_grpo.py

# ベアメタル
uv venv
uv run python examples/run_grpo.py                                            # AutoModel
uv run examples/run_grpo.py --config examples/configs/grpo_math_1B_megatron.yaml   # Megatron
uv run examples/run_grpo.py --config examples/configs/grpo_smoke.yaml              # 10 ステップの動作確認
```

サブモジュールを使うため、クローン時に `--recursive` が必要です。新しいモデルへの対応が早く、専用ブランチとモデル別ガイドで提供されます。

### 14.5 Molt

[NVIDIA-NeMo/labs-molt](https://github.com/NVIDIA-NeMo/labs-molt) は、Ray + vLLM + AutoModel（FSDP2）による軽量な構成で、SFT と RL を扱います。「3つの箱と1つの非同期ループ」という単純さが売りで、OpenRLHF とよく似たオプション体系を持っています。

**要件**：**CUDA 13 が必須**（`torch==2.13.0+cu130`）。CUDA 12 環境では動きません。ホストのドライバが 580 より古い場合はコンテナを使います。PyPI の `molt-rl` は現時点では推奨の導入経路ではなく、コンテナかリポジトリからのローカルインストールを使います。

```bash
git clone https://github.com/NVIDIA-NeMo/labs-molt.git && cd labs-molt
pip install -e ".[vllm]"

# SFT
torchrun --standalone --nproc_per_node=8 -m molt.cli.train_sft \
  --model.model_name_or_path /path/to/model \
  --data.dataset /path/to/sft.jsonl \
  --data.input_key input --data.output_key output \
  --ckpt.output_dir ./ckpt/sft

# RL
python3 -m molt.cli.train_rl_ray \
  --actor.model_name_or_path /path/to/model \
  --data.prompt_dataset /path/to/prompts.jsonl --data.input_key input \
  --train.agent_path examples/python/agents/math.py \
  --vllm.num_engines 2 --vllm.tensor_parallel_size 2 \
  --rollout.batch_size 128 --train.batch_size 128 \
  --algo.advantage.estimator reinforce \
  --ckpt.output_dir ./ckpt/rl
```

推定器は `reinforce`、`reinforce_baseline`、`rloo`、`grpo`、`dr_grpo`、`gae`（PPO）、`on_policy_distill` から選びます。エージェントは Gymnasium 風の `Env`（フレームワークがループを持つ）か、OpenAI / Anthropic の SDK で自分でループを書く `ChatAgent` のどちらかで定義します。

### 14.6 ROLL

[alibaba/ROLL](https://github.com/alibaba/ROLL) は、大規模 GPU 資源を前提にした RL ライブラリです。

**特徴**：数学・コード・推論・指示追従などを混ぜる**マルチタスク RLVR**（ドメインごとのバッチ配分を制御可能）、マルチターンのエージェント RL（軌跡単位の StarPO と、ステップ単位の GiGPO）、サンプル単位の非同期ロールアウトと非同期学習、PPO・GRPO・Reinforce++・TOPR・RAFT++・GSPO など。学習は FSDP2 と Megatron（`mcore_adapter` 経由）、推論は vLLM と SGLang です。

```bash
# サンプルは設定ディレクトリごとに起動スクリプトを持つ
bash examples/qwen3-8B-rlvr_fsdp2/run_rlvr_pipeline.sh
# 中身は: python examples/start_rlvr_pipeline.py --config_path <dir> --config_name rlvr_config
```

インストール、単一ノード・複数ノードの手順は[公式ドキュメント](https://alibaba.github.io/ROLL/)にまとまっています。

### 14.7 AReaL

[areal-project/AReaL](https://github.com/areal-project/AReaL)（旧 inclusionAI/AReaL。旧 URL でも到達可能）は、**完全非同期**を設計の中心に据えた RL 基盤です。2026年7月の 2.0 で、学習・推論・エージェント・重み更新を独立したサービスに分けるマイクロサービス構成になりました。

**特徴**：GRPO、GSPO、PPO、DAPO、LitePPO、Dr. GRPO、REINFORCE++、RLOO、SAPO、IcePop、KPop、M2PO、DPO、報酬モデル、SFT、蒸留。すべてのアルゴリズムで、`max_head_offpolicyness=0` にすると同期版になります。学習バックエンドは Megatron・FSDP・独自の Archon、推論は SGLang（既定）と vLLM です。

```bash
git clone https://github.com/areal-project/AReaL && cd AReaL
pip install uv
uv sync --extra cuda     # 学習用パッケージ + SGLang

# 単一ノード（データとモデルは自動で取得）
python3 examples/math/gsm8k_rl.py --config examples/math/gsm8k_grpo.yaml scheduler.type=local

# Ray クラスタ
python3 examples/math/gsm8k_rl.py --config examples/math/gsm8k_grpo.yaml \
  cluster.n_nodes=2 cluster.n_gpus_per_node=8 \
  cluster.fileroot=/path/to/nfs scheduler.type=ray
```

flash-attn はビルド済みホイールを先に入れる手順が README に示されています。

### 14.8 slime と Miles

[THUDM/slime](https://github.com/THUDM/slime) は Megatron（学習）と SGLang（推論）を直結した RL 基盤で、GLM-4.5 から GLM-5.3 までの学習に使われてきました。学習・ロールアウト・データバッファの3モジュールだけという小ささと、実戦での検証が特徴です。Megatron の引数はそのまま、SGLang の引数は `--sglang-` を付けて渡します。

対応ハードウェアと公式イメージは次のとおりで、**A100 は表にありません**。

| ハードウェア | イメージ | CUDA |
|---|---|---|
| H100 / H200 | `slimerl/slime:latest` または `latest-cu130` | 13.0 |
| B200 / B300（x86） | `slimerl/slime:latest-cu130` | 13.0 |

```bash
SLIME_IMAGE=slimerl/slime:latest-cu130
docker pull "$SLIME_IMAGE"
git clone https://github.com/THUDM/slime.git && cd slime
docker run --rm -it --gpus all --ipc=host --shm-size=16g \
  -v "$PWD:/root/slime" -w /root/slime "$SLIME_IMAGE" /bin/bash
# コンテナ内
pip install -e . --no-deps
```

学習の起動は `scripts/` 以下のモデル別スクリプト（`run-qwen3-30B-A3B.sh` など）を雛形にします。

[radixark/miles](https://github.com/radixark/miles) は slime を土台にした企業向けの RL 基盤で、slime の README でもエコシステムの一つとして紹介されています。SGLang と Megatron-LM の組み合わせを軸に、ロールアウトと学習を切り離した完全非同期の RL を備えます。新しいモデルへの即日対応と、**GB300 から A100 まで**（および AMD の MI300 系）の幅広いハードウェア対応を掲げています。GRPO、GSPO、PPO、REINFORCE++、SFT、オンポリシー蒸留に対応し、Ray でも Kubernetes でも同じ起動スクリプトが使えます。手順は[公式ドキュメント](https://miles.radixark.com/docs/getting-started/installation)を参照してください。

### 14.9 prime-rl

[PrimeIntellect-ai/prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) は完全非同期の RL 基盤で、環境ライブラリ verifiers（第16章）と一体で設計されています。学習は FSDP2、推論は vLLM です。**開発・検証の対象 GPU として RTX 3090 / 4090 / 5090、A100、H100、H200、B200 が明記**されており、A100 ユーザーにとって安心材料です。SFT・RL・評価をひととおり備え、Slurm での複数ノード展開にも対応します。

```bash
curl -sSL https://raw.githubusercontent.com/PrimeIntellect-ai/prime-rl/main/scripts/install.sh | bash

# 動作確認（設定は TOML）
uv run sft @ configs/debug/fake/sft.toml              # SFT トレーナ（1GPU）
uv run inference --vllm.model Qwen/Qwen3-0.6B         # 推論サーバー（1GPU）
uv run rl @ examples/basic/reverse-text/rl.toml       # 推論 + オーケストレータ + 学習（2GPU）
```

### 14.10 SkyRL

[NovaSky-AI/SkyRL](https://github.com/NovaSky-AI/SkyRL) は UC Berkeley 発のフルスタック RL ライブラリです。現在は `skyrl` という統合パッケージに、学習フレームワーク（旧 skyrl-train）と、Tinker API 互換のバックエンド（旧 skyrl-tx）がまとめられています。ほかに、長いタスク向けのエージェント層 `skyrl-agent` と、ツール利用タスクの環境集 `skyrl-gym`（数学・コード・検索・SQL、Gymnasium API）があります。

```bash
# データ準備 → 学習（クイックスタートより）
uv run --isolated examples/train/gsm8k/gsm8k_dataset.py --output_dir $HOME/data/gsm8k
bash examples/train/gsm8k/run_gsm8k.sh
```

### 14.11 Trinity-RFT

[agentscope-ai/Trinity-RFT](https://github.com/agentscope-ai/Trinity-RFT)（旧 modelscope/Trinity-RFT）は、RFT を **Explorer（経験の生成）・Trainer（学習）・Buffer（データ処理）** の3つに分けて協調させる枠組みです。同期／非同期、オンポリシー／オフポリシー、オンライン／オフラインを切り替えられ、AgentScope で作ったエージェントをそのまま学習対象にできます。対応アルゴリズムは PPO、GRPO、DAPO、GiGPO、SFT、DPO、CHORD、RLOO、REINFORCE++、GSPO、TOPR、CISPO、SAPO、オンポリシー蒸留などです。

**要件**：Python 3.10〜3.12、CUDA 12.8 以上、**Compute Capability 8.0 以上の NVIDIA GPU**（RTX 30 系、A100、H100 など）。

```bash
git clone https://github.com/agentscope-ai/Trinity-RFT && cd Trinity-RFT
bash scripts/install/install_trinity.sh && source .venv/bin/activate

ray start --head
trinity run --config examples/grpo_gsm8k/gsm8k.yaml   # Qwen2.5-1.5B を GSM8K で GRPO
trinity studio --port 8080                            # 設定用の Web UI
```

### 14.12 そのほか

| OSS | 状況 | 内容 |
|---|---|---|
| [torchtitan の TitanRL](https://github.com/pytorch/torchtitan) | v0.4.0（2026-10-28） | torchtitan 内の RL 機能（`torchtitan/rl`）。PyTorch 公式系の RL はここに集約 |
| [RL2](https://github.com/ChenmienTan/RL2) | 最終コミット 2026-05 | 「Ray を使わない」簡潔な事後学習ライブラリ（`pip install rl-square`） |
| [EasyR1](https://github.com/hiyouga/EasyR1) | 最終コミット 2026-11 | verl ベースのマルチモーダル RL。LlamaFactory の作者による |
| [siiRL](https://github.com/sii-research/siiRL) | v0.2.0（2025-12）、最終コミット 2026-01 | LLM とマルチエージェント向けの RL フレームワーク |
| [Tunix](https://github.com/google/tunix) | v0.1.7 | JAX。PPO / GRPO 系に対応（第9章） |

### 14.13 選び方の目安

| 状況 | 候補 |
|---|---|
| まず定番から始めたい、情報が多いものがよい | **verl** |
| コードを読んで仕組みを理解したい | **OpenRLHF**、**Molt** |
| A100 での動作を明記しているものがよい | **prime-rl**、**Miles**、**Trinity-RFT**（CC 8.0 以上） |
| NVIDIA のスタックで揃えたい | **NeMo RL**（本格）、**Molt**（軽量） |
| H100 以降で大規模 MoE を学習したい | **slime**、**Miles**、**verl（Megatron）**、**NeMo RL（Megatron）** |
| 長いエージェントタスクを非同期で回したい | **AReaL**、**prime-rl**、**ROLL** |
| 複数ドメインを混ぜた RLVR | **ROLL** |
| エージェント開発フレームワークと直結したい | **Trinity-RFT**（AgentScope）、**SkyRL** |

**出典**：各リポジトリの README とドキュメント（付録A・E）/ [verl ドキュメント](https://verl.readthedocs.io/en/latest/) / [OpenRLHF ドキュメント](https://openrlhf.readthedocs.io/) / [NeMo RL ドキュメント](https://docs.nvidia.com/nemo/rl/latest/index.html) / [AReaL ドキュメント](https://areal-project.github.io/AReaL/) / [slime ドキュメント](https://thudm.github.io/slime/) / [SkyRL ドキュメント](https://docs.skyrl.ai/docs/index) / [Trinity-RFT ドキュメント](https://agentscope-ai.github.io/Trinity-RFT/)

---
## 第15章 エージェント RL フレームワーク

第14章の基盤が「学習の仕組み」を提供するのに対し、この章の OSS は「**すでにあるエージェントのコードを、なるべく変えずに RL で鍛える**」ことに重点を置いています。

### 15.1 ART（Agent Reinforcement Trainer）

| 項目 | 内容 |
|---|---|
| リポジトリ | [OpenPipe/ART](https://github.com/OpenPipe/ART) |
| 最新版 | v0.5.24（2026-11-04） |
| ライセンス | Apache-2.0 |

既存の Python アプリケーションに GRPO を組み込むためのフレームワークです。**クライアントとサーバーに分かれている**のが特徴で、クライアント（OpenAI 互換）は自分のコード側に置き、サーバー（バックエンド）が推論と学習を受け持ちます。

学習ループの流れ：

1. 自分のコードが ART クライアント経由でエージェントを実行する（複数のロールアウトを並列に）
2. 推論リクエストはバックエンドに送られ、最新の LoRA を載せた vLLM が応答する
3. やり取りは Trajectory に記録され、終了時に自分のコードが `reward` を付ける
4. Trajectory をグループにまとめて送ると、バックエンドが GRPO で LoRA を更新し、vLLM に読み込み直す

バックエンドは2種類あります。

| バックエンド | 内容 |
|---|---|
| `LocalBackend` | 手元の GPU マシンで vLLM と学習（Unsloth か torchtune）を動かす |
| `ServerlessBackend` | W&B Training（マネージドのサーバーレス RL）を使う。W&B の API キーが必要 |

```bash
pip install openpipe-art                     # クライアントのみ
pip install --extra-index-url https://download.pytorch.org/whl/cu128 \
  "openpipe-art[backend]"                    # ローカルで学習も動かす（CUDA 13 は backend-cu130）
```

```python
from art import TrainableModel
from art.local.backend import LocalBackend

backend = LocalBackend()
model = TrainableModel(
    name="agent-001",
    project="my-agentic-task",
    base_model="OpenPipe/Qwen3-14B-Instruct",
)
await model.register(backend)
# 以降、model を通してエージェントを実行し、報酬つきの軌跡を集めて学習に渡す
```

LangGraph との連携、MCP サーバーのツール利用を学習させる仕組み、LLM に相対評価させて報酬を自動生成する RULER、OpenEnv との連携などが用意されています。

### 15.2 Agent Lightning

| 項目 | 内容 |
|---|---|
| リポジトリ | [microsoft/agent-lightning](https://github.com/microsoft/agent-lightning) |
| 最新版 | v1.0.3（2026-11-03） |
| ライセンス | MIT |

v1.0 で全面的に作り直され、「約 3,500 行の軽量なエージェント RL フレームワーク」になりました（旧版は `v0.x` ブランチ）。構成要素は3つです。

| 構成要素 | 役割 |
|---|---|
| Trainer | verl と vLLM を動かし、学習サンプルを組み立てて方策を更新する |
| API Gateway | モデルへのリクエストを中継し、学習データとして記録する |
| Rollout Controller | エージェントをローカル、または Kubernetes の Job として実行する |

エージェントはゲートウェイ越しにモデルを呼ぶだけなので、**ツール・コンテキスト管理・制御フロー・環境を含む実際のハーネスを変更なしで学習に使える**、というのが要点です。README には、コーディングエージェントの学習例（データ整備、報酬ハッキング対策、学習スクリプトを含むパイプライン一式）が公開されています。

```bash
# CUDA 13.0 環境での例
uv sync
bash scripts/setup_verl.sh 0.8.0 cu130
```

### 15.3 rLLM

| 項目 | 内容 |
|---|---|
| リポジトリ | [rllm-org/rllm](https://github.com/rllm-org/rllm) |
| 最新版 | v0.2.1.post1（2025-12-18）。main は 2026-10 まで更新 |
| ライセンス | Apache-2.0 |

「どのハーネスでも、どのバックエンドでも、どのベンチマークでも」を掲げるエージェント RL フレームワークです。

- **ハーネス**：10 種類以上の CLI ハーネスや Harbor 互換のタスクに対応。自作エージェント（LangGraph、OpenAI Agents SDK、素の OpenAI クライアントなど）は `@rllm.rollout` で包む
- **サンドボックス**：Docker、Daytona、Modal、ローカル
- **学習バックエンド**：`verl`（分散・複数 GPU）、`tinker`（単一マシン）、`fireworks` をフラグ1つで切り替え
- **ベンチマーク**：60 以上を統合。`rllm eval <名前>` で実行

```bash
uv pip install "rllm[verl] @ git+https://github.com/rllm-org/rllm.git"

rllm model setup     # モデル提供元の設定
rllm eval gsm8k      # 評価
rllm train gsm8k     # RL で学習
```

Python API では、ロールアウト（エージェント）と評価器（報酬関数）をデコレータで定義して `AgentTrainer` に渡します。学習中はゲートウェイがトークン ID と対数確率を透過的に記録するので、評価と学習で同じエージェントコードが使えます。

### 15.4 そのほか

| OSS | 状況 | 内容 |
|---|---|---|
| [uni-agent](https://github.com/verl-project/uni-agent) | v0.1.1（2026-11-10）、Apache-2.0 | verl ファミリー。コーディングエージェントなどのハーネスの接続先を Uni-Agent Gateway に向けるだけで、学習用のトークン列が得られる |
| [verl-agent](https://github.com/langfengQ/verl-agent) | v0.1.0、最終コミット 2026-06 | verl を拡張した LLM エージェント学習用フレームワーク |
| [RAGEN](https://github.com/RAGEN-AI/RAGEN) | 最終コミット 2026-10、MIT | エージェント RL の失敗モード（Echo Trap など）の診断と対策。verl ベース |
| [MARTI](https://github.com/TsinghuaC3I/MARTI) | 最終コミット 2026-08、MIT | マルチエージェント RL。OpenRLHF からの派生 |
| [AgentGym-RL](https://github.com/WooooDyy/AgentGym-RL) | 最終コミット 2026-02、MIT | マルチターンの意思決定タスク向け |
| [RL-Factory](https://github.com/Simple-Efficient/RL-Factory) | 最終コミット 2025-12、Apache-2.0 | ツール利用エージェントの事後学習 |
| [OpenClaw-RL](https://github.com/Gen-Verse/OpenClaw-RL) | 最終コミット 2026-05、Apache-2.0 | 自前ホストのモデルとの実際の会話を横取りし、バックグラウンドで継続的に学習する方式 |
| [OpenManus-RL](https://github.com/OpenManus/OpenManus-RL) | 最終コミット 2025-09 | エージェントの RL チューニング |
| [Tinker Cookbook](https://github.com/thinking-machines-lab/tinker-cookbook) | v0.6.1（2026-11-06）、Apache-2.0 | マネージド学習 API「Tinker」を使う事後学習アルゴリズムの実装集。Tinker 本体は OSS ではない |

この分野のリポジトリを網羅的に追うには、キュレーションリスト [AgentsMeetRL](https://github.com/thinkwee/AgentsMeetRL) が便利です。

### 15.5 選び方の目安

- **既存のエージェントに手を入れたくない** → Agent Lightning、rLLM、uni-agent（ゲートウェイ方式）
- **Python のコードから自分で軌跡と報酬を組み立てたい** → ART
- **GPU を持たずに試したい** → ART の ServerlessBackend、rLLM / Trinity-RFT の Tinker バックエンド（いずれも外部サービスの利用が前提）
- **分散基盤まで自前で持ちたい** → verl + uni-agent、または第14章の基盤のエージェント機能

**出典**：各リポジトリの README とドキュメント / [ART Docs](https://art.openpipe.ai) / [Agent Lightning Docs](https://microsoft.github.io/agent-lightning/stable/) / [rLLM Docs](https://docs.rllm-project.com/)

---

## 第16章 環境と報酬の OSS

エージェント RL では、**環境の質と量**が成果を左右します。環境側のフレームワークは学習基盤から独立して発展しており、組み合わせを選べるようになっています。

### 16.1 主要な環境フレームワーク

| OSS | 最新版 | ライセンス | 特徴 |
|---|---|---|---|
| [**OpenEnv**](https://github.com/meta-pytorch/OpenEnv) | v0.12.0（2026-11-05） | BSD-3-Clause | `reset()` / `step()` / `state()` の統一 API。環境は Docker イメージとして隔離実行 |
| [**verifiers**](https://github.com/PrimeIntellect-ai/verifiers) | v0.4.1（2026-11-03） | MIT | タスクセット・ハーネス・エージェント・環境を分けて定義。Environments Hub と prime-rl に直結 |
| [**NeMo Gym**](https://github.com/NVIDIA-NeMo/Gym) | v0.7.0（2026-10-08） | Apache-2.0 | 環境の開発、評価と学習のスケール実行、ベンチマーク集。NeMo RL と連携 |
| [**Harbor**](https://github.com/laude-institute/harbor) | v0.25.0（2026-10-25） | Apache-2.0 | Terminal-Bench の開発元による、サンドボックス上でのエージェント評価・最適化の枠組み |
| [SkyRL-Gym](https://github.com/NovaSky-AI/SkyRL) | SkyRL に同梱 | Apache-2.0 | 数学・コード・検索・SQL などツール利用タスク。Gymnasium API |

**OpenEnv**

```bash
pip install openenv
pip install git+https://huggingface.co/spaces/openenv/echo_env   # 環境クライアントの例
```

```python
from echo_env import CallToolAction, EchoEnv

with EchoEnv(base_url="https://openenv-echo-env.hf.space").sync() as client:
    result = client.reset()
    result = client.step(CallToolAction(tool_name="echo_message",
                                        arguments={"message": "Hello"}))
    print(result.reward)
```

環境はローカル、クラウドのサンドボックス、Hugging Face Spaces のいずれでも動かせ、40 以上の環境がカタログにあります。TRL、Unsloth、SkyRL、ART、Oumi、Miles、TitanRL などが連携を提供しています。MCP でツールを公開する本番モードや、ルーブリックによる報酬の合成にも対応します。

**verifiers**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/PrimeIntellect-ai/verifiers.git && cd verifiers && uv sync

uv run vf-validate reverse-text -n 1     # モデルを呼ばずにタスクの設定を検証
uv run vf-run reverse-text -n 2 -r 1     # 数エピソードを実行してトレースを保存
```

用語を押さえると理解が早まります。**タスクセット**（評価・学習に使う仕事の集まり）、**ハーネス**（モデルを動かすプログラム）、**エージェント**（ハーネス × モデル × 実行方針）、**環境**（1つ以上のエージェントとその制御フロー）、**トレース**（メッセージ・報酬・指標の記録）。CLI は `vf-validate`、`vf-debug`、`vf-run`、`vf-gepa`（タスクの報酬に対してシステムプロンプトを最適化）の4つです。

**Harbor**

```bash
uv tool install harbor
harbor run -d "<dataset@version>" -m "<model>" -a "<agent>"
```

TRL と OpenEnv の両方が Harbor 連携を持ち、実際のコーディングエージェントのハーネスを Harbor のタスク上で動かして、生成されたトークンをそのまま RL に使えます。

### 16.2 タスク・データ生成系

| OSS | 状況 | 内容 |
|---|---|---|
| [Reasoning Gym](https://github.com/open-thought/reasoning-gym) | v0.1.25（2026-03-28）、Apache-2.0 | 代数・算術・論理・グラフ・ゲームなど 100 以上のタスクを手続き的に生成。答え合わせが機械的にできる |
| [TextArena](https://github.com/LeonGuertler/TextArena) | 最終コミット 2026-10、MIT | 1人・2人・多人数のテキストゲーム 100 以上 |
| [GEM](https://github.com/axon-rl/gem) | v0.1.0（2025-10）、最終コミット 2026-01 | LLM 向けの汎用環境ライブラリ（`pip install gem-llm`） |
| [SWE-Gym](https://github.com/SWE-Gym/SWE-Gym) | 最終コミット 2026-10 | ソフトウェア開発エージェントの学習用環境 |
| [R2E-Gym](https://github.com/R2E-Gym/R2E-Gym) | 最終コミット 2025-07 | 手続き的な環境生成による SWE エージェント学習 |
| [HUD](https://github.com/hud-evals/hud-python) | v0.6.23（2026-11-09）、MIT | コーディング・ブラウザ・PC 操作などの RL 環境を構築する基盤（`pip install hud`） |
| [Atropos](https://github.com/NousResearch/atropos) | **アーカイブ済み**（README に保守終了と明記） | 非同期 RL 向けの環境マイクロサービス |

### 16.3 報酬の設計

OSS が提供する報酬の仕組みは、おおむね次の4種類です。

| 種類 | 例 | 注意点 |
|---|---|---|
| 規則ベースの関数 | 数値の一致、形式チェック、テストの合否 | 抜け道を突かれやすい。形式報酬だけ稼ぐ挙動に注意 |
| 検証器 | 数式の同値判定（TRL の `accuracy_reward` など） | 判定の網羅性を事前に確認 |
| 報酬モデル | 選好データで学習した採点モデル | 学習コストと分布外での信頼性 |
| LLM による審査 | ART の RULER、ルーブリック採点 | コストと一貫性。審査モデルの偏り |

環境フレームワークの違いを理解するには、Hugging Face のチームが 2026年5月に公開した比較ガイド「[The ultimate guide to RL environments](https://adithyask-rl-environments-guide.hf.space/)」が参考になります。同じ環境を複数のフレームワークで実装して比較したもので、「トレーナを同梱するもの（prime-rl、NeMo RL、SkyRL）」と「TRL のような外部の学習ループに接続するもの」に分かれるという整理が示されています。

**出典**：各リポジトリの README / [OpenEnv Docs](https://huggingface.co/docs/openenv) / [TRL: OpenEnv Integration](https://huggingface.co/docs/trl/openenv)

---

## 第17章 一般的な RL ライブラリ

LLM 専用ではありませんが、RL の基礎を学ぶときや、環境の API 設計の参照元として重要です。LLM 向けの環境の多くは Gymnasium の `reset` / `step` を下敷きにしています。

| OSS | 最新版 | ライセンス | 内容 |
|---|---|---|---|
| [Gymnasium](https://github.com/Farama-Foundation/Gymnasium) | v1.4.0（2026-10-05） | MIT | 環境 API の標準。OpenAI Gym の後継 |
| [Stable-Baselines3](https://github.com/DLR-RM/stable-baselines3) | v2.9.2（2026-10-26） | MIT | 信頼性の高い定番アルゴリズム実装（PyTorch） |
| [CleanRL](https://github.com/vwxyzjn/cleanrl) | 最終コミット 2026-04 | MIT | 1ファイル完結の実装。アルゴリズムを読んで理解するのに最適 |
| [Tianshou](https://github.com/thu-ml/tianshou) | v2.0.1（2026-04-02） | MIT | オンライン・オフライン RL を広くカバーするモジュール型ライブラリ |
| [TorchRL](https://github.com/pytorch/rl) | v0.15.0（2026-11-07） | MIT | PyTorch ネイティブの RL ツールキット |
| [RLlib](https://github.com/ray-project/ray)（Ray） | Ray 2.60.0（2026-11-04） | Apache-2.0 | Ray 上の分散 RL |
| [PufferLib](https://github.com/PufferAI/PufferLib) | PyPI 3.0.0（2025-06）、開発は 5.0 ブランチ | MIT | 高速なシミュレーションと学習 |

```bash
pip install gymnasium "stable-baselines3[extra]"
```

PPO やアドバンテージ推定の考え方は、CleanRL の `ppo.py` を1本読むだけで十分に掴めます。そのうえで第13章の GRPO に戻ると、「クリティックをなくしてグループ内比較に置き換えた」という関係がはっきり見えてきます。

---

## 第18章 学習用・教育用の実装

仕組みを理解するには、小さな実装を読むのが近道です。

### 18.1 GRPO を最小構成で読む

| OSS | 状況 | 内容 |
|---|---|---|
| [nano-aha-moment](https://github.com/McGill-NLP/nano-aha-moment) | 最終コミット 2025-10、MIT | すべての行が追える単純な GRPO 実装。複数 GPU にも対応 |
| [GRPO-Zero](https://github.com/policy-gradient/GRPO-Zero) | 最終コミット 2025-04、Apache-2.0 | 依存を最小限にしてほぼゼロから実装。24GB 向けの設定あり |
| [simple_GRPO](https://github.com/lsdefine/simple_GRPO) | 最終コミット 2025-11、Apache-2.0 | TRL の損失計算を参考にした最小実装 |

### 18.2 LLM をゼロから作って学ぶ

| OSS | 状況 | 内容 |
|---|---|---|
| [nanochat](https://github.com/karpathy/nanochat) | 最終コミット 2026-07、MIT | トークン化・事前学習・FT・評価・推論までを1ノードで通す最小のハーネス。README の例は 8×H100 |
| [minimind](https://github.com/jingyaogong/minimind) | 最終コミット 2026-10、Apache-2.0 | 小さな LLM を事前学習から SFT、LoRA、DPO、PPO / GRPO、蒸留、ツール利用のエージェント RL まで自前実装で通す（中国語） |
| [LLMs-from-scratch](https://github.com/rasbt/LLMs-from-scratch) | 継続更新、Apache-2.0 | 書籍『Build a Large Language Model (From Scratch)』の公式コード |
| [reasoning-from-scratch](https://github.com/rasbt/reasoning-from-scratch) | v1.0（2026-05-18）、Apache-2.0 | 書籍『Build a Reasoning Model (From Scratch)』の公式コード |

### 18.3 コースと読み物

| 資料 | 内容 |
|---|---|
| [RLHF Book](https://github.com/natolambert/rlhf-book) | RLHF と事後学習全般の包括的な解説書（継続更新） |
| [smol-course](https://github.com/huggingface/smol-course) | 小さなモデルで事後学習を一通り体験する Hugging Face の実践コース |
| [llm-course](https://github.com/mlabonne/llm-course) | LLM のロードマップとノートブック集 |
| [Deep RL Course](https://github.com/huggingface/deep-rl-class) | Hugging Face の深層強化学習コース |
| [Spinning Up](https://github.com/openai/spinningup) | 深層 RL の古典的な入門（更新は 2020年で停止） |
| [Awesome-ML-SYS-Tutorial](https://github.com/zhaochenyang20/Awesome-ML-SYS-Tutorial) | verl や SGLang のコードウォークスルーを含むシステム寄りの解説集 |
| [RL_Envs_101](https://github.com/adithya-s-k/RL_Envs_101) | 第16章で触れた環境比較ガイドのコード |

---

## 第19章 歴史的な OSS と開発が止まったもの

2023〜2025年の記事によく登場しますが、現在は新規採用を避けるべきものです。

### 19.1 README で終了・停止が明記されているもの

| OSS | 記載内容 | 移行先 |
|---|---|---|
| [TinyZero](https://github.com/Jiayi-Pan/TinyZero) | 非推奨。RL の実験には最新の verl を直接使うよう案内 | verl |
| [open-r1](https://github.com/huggingface/open-r1) | 保守終了。成果物（データセット・モデル・記事）は引き続き公開 | TRL |
| [torchforge](https://github.com/meta-pytorch/torchforge) | 開発を一時停止。PyTorch での LLM 学習は torchtitan に集約 | torchtitan（TitanRL） |
| [Atropos](https://github.com/NousResearch/atropos) | アーカイブ済み、保守終了 | OpenEnv、verifiers など |

### 19.2 更新が止まっている初期の RLHF 実装

| OSS | 最終コミット | 内容 |
|---|---|---|
| [trlX](https://github.com/CarperAI/trlx) | 2024-01 | 初期の分散 RLHF フレームワーク（PPO / ILQL） |
| [RL4LMs](https://github.com/allenai/RL4LMs) | 2023-03 | 言語モデルの RL ライブラリの草分け |
| [safe-rlhf](https://github.com/PKU-Alignment/safe-rlhf) | 2024-06 | 制約つき RLHF（Safe RLHF）の実装 |
| [LlamaGym](https://github.com/KhoomeiK/LlamaGym) | 2024-03 | Gym 環境で LLM エージェントをオンライン学習 |
| [Online-RLHF](https://github.com/RLHFlow/Online-RLHF) | 2024-12 | オンライン RLHF の研究コード |
| [lamorel](https://github.com/flowersteam/lamorel) | 2025-12 | RL 環境で LLM を使うための分散ライブラリ |
| [align-anything](https://github.com/PKU-Alignment/align-anything) | 2025-11 | 任意モダリティのアライメント学習 |
| DeepSpeed-Chat（[DeepSpeedExamples](https://github.com/microsoft/DeepSpeedExamples) 内） | リポジトリの最終コミット 2026-09 | 3段階の RLHF パイプラインの参照実装。verl の README も設計上の着想元として挙げている |
| [PaLM-rlhf-pytorch](https://github.com/lucidrains/PaLM-rlhf-pytorch) | 2026-09 | RLHF の参照実装（学習用） |

### 19.3 論文付属の研究コード

アルゴリズムやタスクの再現には有用ですが、汎用フレームワークとしては使いません。

| OSS | 最終コミット | 内容 |
|---|---|---|
| [understand-r1-zero](https://github.com/sail-sg/understand-r1-zero) | 2025-08 | Dr. GRPO の論文コード |
| [Search-R1](https://github.com/PeterGriffinJin/Search-R1) | 2025-11 | 検索を使う推論の RL |
| [ZeroSearch](https://github.com/Alibaba-NLP/ZeroSearch) | 2025-08 | 検索エンジンを模擬して学習 |
| [DeepResearcher](https://github.com/GAIR-NLP/DeepResearcher) | 2026-11 | 実 Web 環境でのリサーチエージェント学習 |

**出典**：各リポジトリの README と Git の履歴

---
# 第IV部 実践

## 第20章 周辺 OSS

学習そのもの以外で、ほぼ必ず必要になる道具です。

### 20.1 推論エンジン

| OSS | 最新版 | ライセンス | 役割 |
|---|---|---|---|
| [vLLM](https://github.com/vllm-project/vllm) | 0.33.0（2026-11-02） | Apache-2.0 | RL のロールアウト、学習後モデルの提供、一括推論 |
| [SGLang](https://github.com/sgl-project/sglang) | 0.5.23（2026-10-30） | Apache-2.0 | 同上。slime、Miles、AReaL、ROLL、verl などが利用 |

RL 基盤は対応する vLLM / SGLang のバージョンを固定していることが多いため（verl は vLLM 0.18.0 以降、OpenRLHF は 0.29.0 以降を推奨など）、**推論エンジンは RL 基盤が指定するバージョンに合わせる**のが原則です。

### 20.2 データの準備

| OSS | 状況 | 内容 |
|---|---|---|
| [Datasets](https://github.com/huggingface/datasets) | 5.2.0（2026-11-09） | データの読み込み・加工の標準 |
| [NeMo Data Designer](https://github.com/NVIDIA-NeMo/DataDesigner) | v0.10.0（2026-10-30）、Apache-2.0 | 合成データの設計・生成 |
| [distilabel](https://github.com/argilla-io/distilabel) | 1.5.3（2025-01） | 合成データと AI フィードバックのパイプライン。元の開発者が離れ、コミュニティ有志が保守を引き継いでいる |
| [synthetic-data-kit](https://github.com/meta-llama/synthetic-data-kit) | 最終コミット 2025-10 | FT 用データ生成のツールキット（Meta） |

LlamaFactory の README は、合成データ作成ツールとして Easy Dataset、DataFlow、GraphGen を紹介しています。Unsloth Studio には PDF や CSV からデータセットを作る機能があります。

### 20.3 評価

| OSS | 最新版 | ライセンス | 内容 |
|---|---|---|---|
| [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) | 0.4.13（2026-08-31） | MIT | ベンチマーク評価の定番 |
| [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) | 0.3.289（2026-11-10） | MIT | エージェント評価を含む評価フレームワーク。OpenEnv に連携チュートリアルあり |
| [lighteval](https://github.com/huggingface/lighteval) | 0.13.0（2025-11-24） | MIT | 軽量な評価ツールキット |

ms-swift は EvalScope を評価バックエンドに使い、prime-rl と rLLM は評価コマンドを内蔵しています。**学習の前後で同じ評価を回せる状態を先に作っておく**と、RL の改善が本物かどうかを判断しやすくなります。

### 20.4 実験管理と実行基盤

- **ログ**：W&B、MLflow、TensorBoard が広く対応されています（LlamaFactory と verl は加えて SwanLab にも対応）。TRL には Hugging Face の Trackio との連携ガイドがあります。
- **ジョブ実行**：Slurm は TRL、NeMo AutoModel、prime-rl、OpenRLHF などが手順を用意しています。クラウドをまたぐなら [SkyPilot](https://github.com/skypilot-org/skypilot)（v0.14.2）や [dstack](https://github.com/dstackai/dstack)（0.22.7）、Kubernetes なら [Kubeflow Trainer](https://github.com/kubeflow/trainer)（v2.4.0）が選択肢です。
- **分散実行**：[Ray](https://github.com/ray-project/ray)（2.60.0）は分散 RL 基盤の大半が前提としています。

### 20.5 モデルの加工

| OSS | 内容 |
|---|---|
| [mergekit](https://github.com/arcee-ai/mergekit) | 学習済みモデルのマージ（LGPL-3.0） |
| [Sentence Transformers](https://github.com/UKPLab/sentence-transformers) | 埋め込み・リランカーの学習 |
| [DSPy](https://github.com/stanfordnlp/dspy) | プロンプトとパイプラインの最適化。FT の前に試す価値がある |

---

## 第21章 構成別レシピ

ここからは本書としての提案です。VRAM の数字は第1章の概算表に基づく目安なので、実際の系列長とバッチサイズで確認してください。

### 21.1 A100 80GB × 1

**できること**
- SFT：LoRA なら 30B 級まで、4bit QLoRA なら 70B 級まで、フル FT は 7B 級まで
- RL：小さなモデル（数B まで）の LoRA + GRPO

**おすすめの構成**

| 目的 | 構成 |
|---|---|
| とにかく早く LoRA を回す | Unsloth（Core）、または TRL + PEFT |
| 設定ファイルで管理したい | LlamaFactory、Axolotl |
| GGUF まで作りたい | Unsloth、Axolotl（`axolotl export`） |
| GRPO を試す | TRL の `GRPOTrainer`（vLLM 同居か連続バッチ）、Unsloth の GRPO ノートブック |
| エージェントを学習させる | ART の `LocalBackend`（1枚では推論と学習を交互に行うため、小さなモデルで） |

**気をつけること**：RL では推論エンジンと学習がメモリを取り合います。`vllm_gpu_memory_utilization` の調整やスリープモードを使い、まずは小さなモデルで全体が回ることを確認します。

### 21.2 A100 80GB × 4〜8（1ノード）

**できること**
- SFT：LoRA を DDP で高速化。14B〜30B 級のフル FT を FSDP2 か DeepSpeed ZeRO-3 で
- RL：推論用と学習用に GPU を分けた本格的な構成

**おすすめの構成**

| 目的 | 構成 |
|---|---|
| フル FT | Axolotl（FSDP2）、TRL + DeepSpeed、LlamaFactory（`FORCE_TORCHRUN=1`）、NeMo AutoModel |
| RL（定番） | verl（FSDP 学習 + vLLM）。サンプルスクリプトから出発 |
| RL（A100 での動作が明記） | prime-rl、Miles |
| RL（単純な構成） | TRL の vLLM 分離モード、Axolotl の GRPO、Molt（CUDA 13 環境） |
| エージェント RL | Agent Lightning、rLLM（verl バックエンド） |

**気をつけること**：Megatron ベースの基盤（slime など）は Hopper 以降を主な対象にしています。A100 では FSDP 系のバックエンドを選ぶほうが無難です。CUDA 13 系へ移行する際は、ドライバを 580 系以降にするか、前方互換レイヤー入りのコンテナを使います。

### 21.3 H100 / H200 × 8 以上

**できること**
- FP8、FlashAttention-3 / 4、Megatron バックエンドを含む、ほぼすべての OSS が想定する環境
- 数十B〜数百B 級、MoE モデルの RL

**おすすめの構成**

| 目的 | 構成 |
|---|---|
| 大規模モデルの SFT | NeMo AutoModel、Megatron-Bridge、torchtitan、Axolotl（N-D 並列） |
| 大規模 RL | verl（Megatron）、NeMo RL、slime、Miles、ROLL |
| 非同期で長い軌跡を回す | AReaL、prime-rl |

H200 の 141GB は、推論エンジンの同居や長いコンテキストでの余裕として効いてきます。

### 21.4 B200 / B300 / GB200

**気をつけること**
- CUDA 13 と対応ホイールが前提です。verl は aarch64（GB200）用のロックファイルを持ち、サンプルスクリプトに Blackwell 用の切り替えがあります。
- FlashAttention は 4 系か、SGLang の別バックエンドを使います（3 系は Blackwell では使えません）。
- NVFP4 を使う LoRA（Axolotl）など、Blackwell 世代ならではの機能があります。
- slime と Miles は Blackwell 向けのイメージ・対応を明記しています。

### 21.5 目的別の早見表

| やりたいこと | 第一候補 | 次点 |
|---|---|---|
| まず1回 LoRA を成功させる | Unsloth | TRL + PEFT |
| チームで同じ手順を回す（設定ファイル中心） | Axolotl、LlamaFactory | Oumi、NeMo AutoModel |
| GUI で作業する | LlamaFactory の Web UI、Unsloth Studio | H2O LLM Studio、Transformer Lab |
| Qwen 系・マルチモーダルを幅広く | ms-swift | LlamaFactory |
| コードを読んで改造する | LitGPT、TRL | torchtitan |
| 選好データ（良い／悪い）で調整 | TRL の `DPOTrainer` | LlamaFactory、Axolotl、ms-swift |
| 検証可能な報酬で GRPO | TRL → verl | prime-rl、OpenRLHF、ms-swift |
| 既存エージェントを RL で改善 | Agent Lightning、rLLM | ART、uni-agent |
| 環境を自作・再利用 | OpenEnv、verifiers | NeMo Gym、Harbor |
| 超大規模・MoE | verl（Megatron）、slime / Miles、NeMo RL | ROLL、AReaL |

---

## 第22章 落とし穴チェックリスト

### 22.1 データとテンプレート

- [ ] **チャットテンプレートが学習と推論で一致している。** LlamaFactory の `template`、ms-swift のテンプレート、TRL のチャットテンプレートなど、指定を誤ると学習は進んでも推論が崩れます。
- [ ] **損失をかける範囲を確認した。** アシスタント発話のみに絞る設定（TRL の `assistant_only_loss` など）は、テンプレート側の対応が必要です。
- [ ] **終端トークンとパディングトークンが正しい。** 生成が止まらない問題の多くはここが原因です。
- [ ] **系列長の上限で大事な部分が切り捨てられていない。**

### 22.2 メモリと速度

- [ ] bf16 を使っている（A100 以降）。
- [ ] 実効バッチサイズ（1枚あたり × GPU 数 × 勾配累積）を把握している。GPU を増やしたときに学習率との関係が変わります。
- [ ] 勾配チェックポイントの有無を理解している（TRL は既定で有効）。
- [ ] 詰め込み（packing）やパディング排除を検討した。
- [ ] FlashAttention を自前ビルドせず、ビルド済みのホイールやカーネルを使っている。

### 22.3 LoRA と量子化

- [ ] アダプタ学習の学習率を、フル FT より高く設定している（TRL の目安は 1e-4 前後）。
- [ ] **LoRA のマージに量子化モデルを使っていない。** LlamaFactory は「マージ時に量子化モデルや `quantization_bit` を使わないこと」と明記しています。
- [ ] 量子化済みで配布されているチェックポイント（MXFP4 や FP8）は、学習時に展開されてメモリが増えることを見込んでいる。

### 22.4 RL 特有の注意

- [ ] **報酬関数を単体でテストした。** 学習を始める前に、正解・不正解・形式違反の例で想定どおりの値が返るかを確認します。
- [ ] **報酬に分散がある。** グループ内の報酬がすべて同じだと学習信号がありません。Axolotl のドキュメントは、報酬平均の立ち上がり・報酬の標準偏差・エントロピー・勾配ノルムを健全性の指標として挙げています。
- [ ] **報酬の抜け道を塞いだ。** 形式点だけを稼ぐ、長さで稼ぐ、といった挙動が起きていないかを生成例で確認します。
- [ ] **推論と学習の GPU が重なっていない**（分離モードの場合）。TRL は NCCL エラーの原因になると警告しています。
- [ ] **学習と推論のズレへの補正を理解している。** 既定で有効な補正（TRL の重要度サンプリングなど）を不用意に切らないこと。
- [ ] **十分なステップ数を見込んだ。** Unsloth のガイドは「報酬が上がるまで少なくとも 300 ステップ」としています。SFT の感覚で早々に打ち切らないこと。
- [ ] 学習前のモデルで、タスクが「たまには成功する」難易度になっている。まったく成功しないタスクでは報酬が得られず、学習が始まりません。

### 22.5 環境とバージョン

- [ ] **フレームワークごとに仮想環境を分けている。** 依存の上限・下限が互いに衝突します（例：ms-swift は `trl` 1.0 未満、Axolotl は PyTorch 2.13 以上）。
- [ ] ドライバ・CUDA・PyTorch の組み合わせを確認した。CUDA 13 系はドライバ 580 系以降が目安です。
- [ ] ロックファイル（`uv.lock`）やコンテナイメージのタグを記録している。
- [ ] main ブランチを追う OSS（LlamaFactory、Unsloth など）は、コミットを固定している。

### 22.6 再現性を保つための運用メモ

誰が回しても同じ結果になる状態を作るうえで、2026年の OSS は以前より協力的です。

1. **設定をファイルに寄せる。** YAML（Axolotl、LlamaFactory、Oumi、NeMo AutoModel、ROLL、AReaL）、TOML（prime-rl）、Hydra（verl）。設定ファイルと実行したコミットを一緒に保存します。
2. **環境をロックする。** uv のロックファイルか、コンテナイメージのダイジェストを記録します。
3. **データを版管理する。** 前処理済みのデータ（verl の Parquet、LlamaFactory の `tokenized_path` など）を成果物として残します。
4. **評価を固定する。** 学習前後で同じ評価セット・同じ評価コードを回し、結果を設定と紐づけます。
5. **小さな動作確認を用意する。** NeMo RL のスモーク設定（10 ステップ）や prime-rl のデバッグ設定のように、数分で通る確認ジョブを最初に流します。

### 22.7 ライセンスの確認

学習に使う OSS の多くは Apache-2.0 か MIT ですが、例外があります。

| OSS | ライセンス | 注意 |
|---|---|---|
| Unsloth | コア Apache-2.0 / Studio の UI など AGPL-3.0 / unsloth-zoo LGPL-3.0 | 組み込み・再配布時に確認 |
| Transformer Lab | AGPL-3.0 | サービス提供時に注意 |
| mergekit | LGPL-3.0 | |
| dstack | MPL-2.0 | |

また、**モデル自体のライセンス**は別です。LlamaFactory の README も「モデルの重みは各モデルのライセンスに従うこと」と注意しています。

---
# 付録

## 付録A OSS 一覧表

2026-11-11 時点で各リポジトリを取得して確認した内容です。

- **ライセンス**はリポジトリの LICENSE ファイルに基づきます。
- **最新タグ**は Git のバージョンタグとその日付です。タグの付け方が特殊なリポジトリは PyPI の配布版を記載しています（「PyPI」「megatron-core」「skyrl」と付記）。「—」はバージョンタグがないことを示します。
- **最終コミット**は既定ブランチの最新コミット日です。
- リポジトリ名は調査時点の正式な場所を記載しています（旧名からは転送されます）。

**基盤ライブラリ**

| OSS | リポジトリ | ライセンス | 最新タグ（日付） | 最終コミット |
|---|---|---|---|---|
| Transformers | [huggingface/transformers](https://github.com/huggingface/transformers) | Apache-2.0 | v5.22.2（2026-11-06） | 2026-11-11 |
| PEFT | [huggingface/peft](https://github.com/huggingface/peft) | Apache-2.0 | v0.21.2（2026-10-01） | 2026-11-11 |
| TRL | [huggingface/trl](https://github.com/huggingface/trl) | Apache-2.0 | v1.17.1（2026-10-30） | 2026-11-11 |
| Accelerate | [huggingface/accelerate](https://github.com/huggingface/accelerate) | Apache-2.0 | v1.15.0（2026-09-09） | 2026-11-02 |
| bitsandbytes | [bitsandbytes-foundation/bitsandbytes](https://github.com/bitsandbytes-foundation/bitsandbytes) | MIT | 0.50.2（2026-08-26） | 2026-10-27 |
| Datasets | [huggingface/datasets](https://github.com/huggingface/datasets) | Apache-2.0 | 5.2.0（2026-11-09） | 2026-11-10 |
| PyTorch | [pytorch/pytorch](https://github.com/pytorch/pytorch) | BSD 3条項系 | v2.15.0（2026-10-28） | 2026-11-11 |

**統合 FT フレームワーク**

| OSS | リポジトリ | ライセンス | 最新タグ（日付） | 最終コミット |
|---|---|---|---|---|
| Unsloth | [unslothai/unsloth](https://github.com/unslothai/unsloth) | Apache-2.0（一部 AGPL-3.0） | PyPI 2026.11.3（2026-11-06） | 2026-11-11 |
| LlamaFactory | [hiyouga/LlamaFactory](https://github.com/hiyouga/LlamaFactory) | Apache-2.0 | v0.9.5（2026-05-30） | 2026-11-11 |
| Axolotl | [axolotl-ai-cloud/axolotl](https://github.com/axolotl-ai-cloud/axolotl) | Apache-2.0 | v0.21.1（2026-10-27） | 2026-11-10 |
| ms-swift | [modelscope/ms-swift](https://github.com/modelscope/ms-swift) | Apache-2.0 | v4.6.0（2026-10-13） | 2026-11-11 |
| LitGPT | [Lightning-AI/litgpt](https://github.com/Lightning-AI/litgpt) | Apache-2.0 | v0.5.14（2026-11-10） | 2026-11-10 |
| NeMo AutoModel | [NVIDIA-NeMo/Automodel](https://github.com/NVIDIA-NeMo/Automodel) | Apache-2.0 | v0.7.0（2026-10-21） | 2026-11-10 |
| Oumi | [oumi-ai/oumi](https://github.com/oumi-ai/oumi) | Apache-2.0 | v0.9（2026-09-16） | 2026-11-09 |
| Ludwig | [ludwig-ai/ludwig](https://github.com/ludwig-ai/ludwig) | Apache-2.0 | v0.17.10（2026-10-26） | 2026-10-26 |
| H2O LLM Studio | [h2oai/h2o-llmstudio](https://github.com/h2oai/h2o-llmstudio) | Apache-2.0 | v1.15.4（2026-11-04） | 2026-11-09 |
| XTuner | [InternLM/xtuner](https://github.com/InternLM/xtuner) | Apache-2.0 | v1.0.1（2026-05-15） | 2026-11-10 |
| Kiln | [Kiln-AI/Kiln](https://github.com/Kiln-AI/Kiln) | MIT | v1.2.1（2026-11-10） | 2026-11-10 |
| Transformer Lab | [transformerlab/transformerlab-app](https://github.com/transformerlab/transformerlab-app) | AGPL-3.0 | v0.40.1（2026-06-19） | 2026-08-05 |
| RapidFire AI | [RapidFireAI/rapidfireai](https://github.com/RapidFireAI/rapidfireai) | Apache-2.0 | v0.16.2（2026-10-20） | 2026-10-28 |
| LMFlow | [OptimalScale/LMFlow](https://github.com/OptimalScale/LMFlow) | Apache-2.0 | v1.0.0（2025-07-08） | 2026-08-09 |
| xTuring | [stochasticai/xTuring](https://github.com/stochasticai/xTuring) | Apache-2.0 | v0.1.8（2023-09-06） | 2026-09-12 |
| LLM Finetuning Toolkit | [georgian-io/LLM-Finetuning-Toolkit](https://github.com/georgian-io/LLM-Finetuning-Toolkit) | Apache-2.0 | v0.2.3（2024-07-25） | 2026-10-22 |
| 360-LLaMA-Factory | [Qihoo360/360-LLaMA-Factory](https://github.com/Qihoo360/360-LLaMA-Factory) | Apache-2.0 | — | 2025-10-14 |
| llama-cookbook | [meta-llama/llama-cookbook](https://github.com/meta-llama/llama-cookbook) | MIT | v0.0.5（2025-01-22） | 2025-11-03 |
| Tunix | [google/tunix](https://github.com/google/tunix) | Apache-2.0 | v0.1.7（2026-06-09） | 2026-11-11 |
| MaxText | [AI-Hypercomputer/maxtext](https://github.com/AI-Hypercomputer/maxtext) | Apache-2.0 | — | 2026-11-10 |
| Keras Hub | [keras-team/keras-hub](https://github.com/keras-team/keras-hub) | Apache-2.0 | v0.33.0（2026-11-03） | 2026-11-10 |
| Levanter | [stanford-crfm/levanter](https://github.com/stanford-crfm/levanter) | Apache-2.0 | — | 2025-11-07 |

**分散学習エンジン・カーネル**

| OSS | リポジトリ | ライセンス | 最新タグ（日付） | 最終コミット |
|---|---|---|---|---|
| DeepSpeed | [deepspeedai/DeepSpeed](https://github.com/deepspeedai/DeepSpeed) | Apache-2.0 | v0.19.9（2026-10-29） | 2026-11-11 |
| Megatron-LM | [NVIDIA/Megatron-LM](https://github.com/NVIDIA/Megatron-LM) | BSD 3条項系（NVIDIA） | megatron-core 0.20.0（2026-10-29） | 2026-11-11 |
| Megatron-Bridge | [NVIDIA-NeMo/Megatron-Bridge](https://github.com/NVIDIA-NeMo/Megatron-Bridge) | Apache-2.0 | v0.7.0（2026-10-27） | 2026-11-11 |
| torchtitan | [pytorch/torchtitan](https://github.com/pytorch/torchtitan) | BSD-3-Clause | v0.4.0（2026-10-28） | 2026-11-11 |
| VeOmni | [ByteDance-Seed/VeOmni](https://github.com/ByteDance-Seed/VeOmni) | Apache-2.0 | v0.1.13（2026-09-30） | 2026-11-11 |
| Nanotron | [huggingface/nanotron](https://github.com/huggingface/nanotron) | Apache-2.0 | — | 2026-10-08 |
| LLM Foundry | [mosaicml/llm-foundry](https://github.com/mosaicml/llm-foundry) | Apache-2.0 | v0.22.0（2025-07-28） | 2026-03-25 |
| Colossal-AI | [hpcaitech/ColossalAI](https://github.com/hpcaitech/ColossalAI) | Apache-2.0 | v0.5.1（2025-06-02） | 2026-11-06 |
| FlashAttention | [Dao-AILab/flash-attention](https://github.com/Dao-AILab/flash-attention) | BSD-3-Clause | v2.8.3.post2（2026-10-12） | 2026-11-10 |
| Liger-Kernel | [linkedin/Liger-Kernel](https://github.com/linkedin/Liger-Kernel) | BSD-2-Clause | v0.8.5（2026-10-21） | 2026-11-10 |
| Transformer Engine | [NVIDIA/TransformerEngine](https://github.com/NVIDIA/TransformerEngine) | Apache-2.0 | v2.21.0（2026-10-30） | 2026-11-11 |
| torchao | [pytorch/ao](https://github.com/pytorch/ao) | BSD-3-Clause | v0.18.0（2026-07-31） | 2026-11-07 |
| kernels | [huggingface/kernels](https://github.com/huggingface/kernels) | Apache-2.0 | v0.18.2（2026-11-09） | 2026-11-11 |

**開発終了・停止（FT 系）**

| OSS | リポジトリ | ライセンス | 最新タグ（日付） | 最終コミット |
|---|---|---|---|---|
| torchtune | [meta-pytorch/torchtune](https://github.com/meta-pytorch/torchtune) | BSD-3-Clause | v0.6.1（2025-04-07） | 2026-11-09 |
| AutoTrain Advanced | [huggingface/autotrain-advanced](https://github.com/huggingface/autotrain-advanced) | Apache-2.0 | — | 2026-10-06 |
| mistral-finetune | [mistralai/mistral-finetune](https://github.com/mistralai/mistral-finetune) | Apache-2.0 | v1.1.0（2024-07-19） | 2026-06-16 |
| nanoGPT | [karpathy/nanoGPT](https://github.com/karpathy/nanoGPT) | MIT | — | 2025-11-12 |
| QLoRA | [artidoro/qlora](https://github.com/artidoro/qlora) | MIT | — | 2023-07-24 |
| LoRA (loralib) | [microsoft/LoRA](https://github.com/microsoft/LoRA) | MIT | — | 2024-12-16 |
| Firefly | [yangjianxin1/Firefly](https://github.com/yangjianxin1/Firefly) | 記載なし | — | 2024-10-24 |

**分散 RL 基盤**

| OSS | リポジトリ | ライセンス | 最新タグ（日付） | 最終コミット |
|---|---|---|---|---|
| verl | [verl-project/verl](https://github.com/verl-project/verl) | Apache-2.0 | v0.9.1（2026-09-20） | 2026-11-11 |
| OpenRLHF | [OpenRLHF/OpenRLHF](https://github.com/OpenRLHF/OpenRLHF) | Apache-2.0 | v0.11.2（2026-09-14） | 2026-11-03 |
| NeMo RL | [NVIDIA-NeMo/RL](https://github.com/NVIDIA-NeMo/RL) | Apache-2.0 | v0.8.0（2026-11-06） | 2026-11-11 |
| Molt | [NVIDIA-NeMo/labs-molt](https://github.com/NVIDIA-NeMo/labs-molt) | Apache-2.0 | v0.2.2（2026-11-06） | 2026-11-11 |
| ROLL | [alibaba/ROLL](https://github.com/alibaba/ROLL) | Apache-2.0 | v0.4.0（2026-09-29） | 2026-11-03 |
| AReaL | [areal-project/AReaL](https://github.com/areal-project/AReaL) | Apache-2.0 | v2.1.1（2026-11-04） | 2026-11-11 |
| slime | [THUDM/slime](https://github.com/THUDM/slime) | Apache-2.0 | v0.4.0（2026-10-09） | 2026-11-06 |
| Miles | [radixark/miles](https://github.com/radixark/miles) | Apache-2.0 | v0.1.3（2026-10-22） | 2026-11-10 |
| prime-rl | [PrimeIntellect-ai/prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) | Apache-2.0 | v0.10.0（2026-10-14） | 2026-11-11 |
| SkyRL | [NovaSky-AI/SkyRL](https://github.com/NovaSky-AI/SkyRL) | Apache-2.0 | skyrl 0.4.0（2026-10-01） | 2026-11-10 |
| Trinity-RFT | [agentscope-ai/Trinity-RFT](https://github.com/agentscope-ai/Trinity-RFT) | Apache-2.0 | v0.6.0（2026-06-26） | 2026-10-08 |
| RL2 | [ChenmienTan/RL2](https://github.com/ChenmienTan/RL2) | Apache-2.0 | — | 2026-05-20 |
| EasyR1 | [hiyouga/EasyR1](https://github.com/hiyouga/EasyR1) | Apache-2.0 | v0.3.2（2025-09-18） | 2026-11-08 |
| siiRL | [sii-research/siiRL](https://github.com/sii-research/siiRL) | Apache-2.0 | v0.2.0（2025-12-07） | 2026-01-28 |
| verl-recipe | [verl-project/verl-recipe](https://github.com/verl-project/verl-recipe) | Apache-2.0 | — | 2026-11-11 |

**エージェント RL**

| OSS | リポジトリ | ライセンス | 最新タグ（日付） | 最終コミット |
|---|---|---|---|---|
| ART | [OpenPipe/ART](https://github.com/OpenPipe/ART) | Apache-2.0 | v0.5.24（2026-11-04） | 2026-11-10 |
| Agent Lightning | [microsoft/agent-lightning](https://github.com/microsoft/agent-lightning) | MIT | v1.0.3（2026-11-03） | 2026-11-05 |
| rLLM | [rllm-org/rllm](https://github.com/rllm-org/rllm) | Apache-2.0 | v0.2.1.post1（2025-12-18） | 2026-10-08 |
| uni-agent | [verl-project/uni-agent](https://github.com/verl-project/uni-agent) | Apache-2.0 | v0.1.1（2026-11-10） | 2026-11-11 |
| verl-agent | [langfengQ/verl-agent](https://github.com/langfengQ/verl-agent) | Apache-2.0 | v0.1.0（2025-12-04） | 2026-06-09 |
| RAGEN | [RAGEN-AI/RAGEN](https://github.com/RAGEN-AI/RAGEN) | MIT | — | 2026-10-28 |
| MARTI | [TsinghuaC3I/MARTI](https://github.com/TsinghuaC3I/MARTI) | MIT | — | 2026-08-20 |
| AgentGym-RL | [WooooDyy/AgentGym-RL](https://github.com/WooooDyy/AgentGym-RL) | MIT | — | 2026-02-15 |
| RL-Factory | [Simple-Efficient/RL-Factory](https://github.com/Simple-Efficient/RL-Factory) | Apache-2.0 | v0.1.0（2025-05-23） | 2025-12-05 |
| OpenClaw-RL | [Gen-Verse/OpenClaw-RL](https://github.com/Gen-Verse/OpenClaw-RL) | Apache-2.0 | — | 2026-05-22 |
| OpenManus-RL | [OpenManus/OpenManus-RL](https://github.com/OpenManus/OpenManus-RL) | Apache-2.0 | — | 2025-09-21 |
| Tinker Cookbook | [thinking-machines-lab/tinker-cookbook](https://github.com/thinking-machines-lab/tinker-cookbook) | Apache-2.0 | v0.6.1（2026-11-06） | 2026-11-06 |

**環境・報酬**

| OSS | リポジトリ | ライセンス | 最新タグ（日付） | 最終コミット |
|---|---|---|---|---|
| OpenEnv | [meta-pytorch/OpenEnv](https://github.com/meta-pytorch/OpenEnv) | BSD-3-Clause | v0.12.0（2026-11-05） | 2026-11-10 |
| verifiers | [PrimeIntellect-ai/verifiers](https://github.com/PrimeIntellect-ai/verifiers) | MIT | v0.4.1（2026-11-03） | 2026-11-10 |
| NeMo Gym | [NVIDIA-NeMo/Gym](https://github.com/NVIDIA-NeMo/Gym) | Apache-2.0 | v0.7.0（2026-10-08） | 2026-11-11 |
| Harbor | [laude-institute/harbor](https://github.com/laude-institute/harbor) | Apache-2.0 | v0.25.0（2026-10-25） | 2026-11-10 |
| Reasoning Gym | [open-thought/reasoning-gym](https://github.com/open-thought/reasoning-gym) | Apache-2.0 | v0.1.25（2026-03-28） | 2026-11-09 |
| TextArena | [LeonGuertler/TextArena](https://github.com/LeonGuertler/TextArena) | MIT | — | 2026-10-03 |
| GEM | [axon-rl/gem](https://github.com/axon-rl/gem) | Apache-2.0 | v0.1.0（2025-10-06） | 2026-01-21 |
| SWE-Gym | [SWE-Gym/SWE-Gym](https://github.com/SWE-Gym/SWE-Gym) | Apache-2.0 | — | 2026-10-31 |
| R2E-Gym | [R2E-Gym/R2E-Gym](https://github.com/R2E-Gym/R2E-Gym) | Apache-2.0 | — | 2025-07-13 |
| HUD | [hud-evals/hud-python](https://github.com/hud-evals/hud-python) | MIT | v0.6.23（2026-11-09） | 2026-11-10 |
| Atropos（アーカイブ） | [NousResearch/atropos](https://github.com/NousResearch/atropos) | MIT | v0.4.0（2026-03-09） | 2026-07-04 |

**一般的な RL ライブラリ**

| OSS | リポジトリ | ライセンス | 最新タグ（日付） | 最終コミット |
|---|---|---|---|---|
| Gymnasium | [Farama-Foundation/Gymnasium](https://github.com/Farama-Foundation/Gymnasium) | MIT | v1.4.0（2026-10-05） | 2026-11-10 |
| Stable-Baselines3 | [DLR-RM/stable-baselines3](https://github.com/DLR-RM/stable-baselines3) | MIT | v2.9.2（2026-10-26） | 2026-10-26 |
| CleanRL | [vwxyzjn/cleanrl](https://github.com/vwxyzjn/cleanrl) | MIT | — | 2026-04-20 |
| Tianshou | [thu-ml/tianshou](https://github.com/thu-ml/tianshou) | MIT | v2.0.1（2026-04-02） | 2026-04-03 |
| TorchRL | [pytorch/rl](https://github.com/pytorch/rl) | MIT | v0.15.0（2026-11-07） | 2026-11-07 |
| Ray（RLlib） | [ray-project/ray](https://github.com/ray-project/ray) | Apache-2.0 | 2.60.0（2026-11-04） | 2026-11-11 |
| PufferLib | [PufferAI/PufferLib](https://github.com/PufferAI/PufferLib) | MIT | PyPI 3.0.0（2025-06-23） | 2026-10-14 |

**学習用・教育用**

| OSS | リポジトリ | ライセンス | 最新タグ（日付） | 最終コミット |
|---|---|---|---|---|
| nano-aha-moment | [McGill-NLP/nano-aha-moment](https://github.com/McGill-NLP/nano-aha-moment) | MIT | — | 2025-10-07 |
| GRPO-Zero | [policy-gradient/GRPO-Zero](https://github.com/policy-gradient/GRPO-Zero) | Apache-2.0 | — | 2025-04-18 |
| simple_GRPO | [lsdefine/simple_GRPO](https://github.com/lsdefine/simple_GRPO) | Apache-2.0 | — | 2025-11-21 |
| nanochat | [karpathy/nanochat](https://github.com/karpathy/nanochat) | MIT | — | 2026-07-03 |
| minimind | [jingyaogong/minimind](https://github.com/jingyaogong/minimind) | Apache-2.0 | — | 2026-10-27 |
| LLMs-from-scratch | [rasbt/LLMs-from-scratch](https://github.com/rasbt/LLMs-from-scratch) | Apache-2.0 | — | 2026-11-09 |
| reasoning-from-scratch | [rasbt/reasoning-from-scratch](https://github.com/rasbt/reasoning-from-scratch) | Apache-2.0 | v1.0（2026-05-18） | 2026-11-02 |
| RLHF Book | [natolambert/rlhf-book](https://github.com/natolambert/rlhf-book) | 記載なし | — | 2026-11-05 |
| smol-course | [huggingface/smol-course](https://github.com/huggingface/smol-course) | Apache-2.0 | — | 2026-10-06 |
| llm-course | [mlabonne/llm-course](https://github.com/mlabonne/llm-course) | Apache-2.0 | — | 2026-02-05 |
| Deep RL Course | [huggingface/deep-rl-class](https://github.com/huggingface/deep-rl-class) | Apache-2.0 | — | 2026-10-06 |
| Spinning Up | [openai/spinningup](https://github.com/openai/spinningup) | MIT | v0.1.1（2018-11-11） | 2020-02-07 |
| Awesome-ML-SYS-Tutorial | [zhaochenyang20/Awesome-ML-SYS-Tutorial](https://github.com/zhaochenyang20/Awesome-ML-SYS-Tutorial) | Apache-2.0 | — | 2026-10-21 |
| RL_Envs_101 | [adithya-s-k/RL_Envs_101](https://github.com/adithya-s-k/RL_Envs_101) | Apache-2.0 | — | 2026-10-28 |
| AgentsMeetRL | [thinkwee/AgentsMeetRL](https://github.com/thinkwee/AgentsMeetRL) | 記載なし | — | 2026-11-06 |

**歴史的・停止（RL 系）**

| OSS | リポジトリ | ライセンス | 最新タグ（日付） | 最終コミット |
|---|---|---|---|---|
| TinyZero | [Jiayi-Pan/TinyZero](https://github.com/Jiayi-Pan/TinyZero) | Apache-2.0 | — | 2026-02-27 |
| open-r1 | [huggingface/open-r1](https://github.com/huggingface/open-r1) | Apache-2.0 | — | 2026-10-02 |
| torchforge | [meta-pytorch/torchforge](https://github.com/meta-pytorch/torchforge) | BSD-3-Clause | v0.1.0（2025-10-28） | 2026-04-23 |
| trlX | [CarperAI/trlx](https://github.com/CarperAI/trlx) | MIT | v0.7.0（2023-06-23） | 2024-01-09 |
| RL4LMs | [allenai/RL4LMs](https://github.com/allenai/RL4LMs) | Apache-2.0 | — | 2023-03-30 |
| safe-rlhf | [PKU-Alignment/safe-rlhf](https://github.com/PKU-Alignment/safe-rlhf) | Apache-2.0 | — | 2024-06-13 |
| align-anything | [PKU-Alignment/align-anything](https://github.com/PKU-Alignment/align-anything) | Apache-2.0 | — | 2025-11-27 |
| LlamaGym | [KhoomeiK/LlamaGym](https://github.com/KhoomeiK/LlamaGym) | MIT | — | 2024-03-10 |
| lamorel | [flowersteam/lamorel](https://github.com/flowersteam/lamorel) | MIT | — | 2025-12-11 |
| Online-RLHF | [RLHFlow/Online-RLHF](https://github.com/RLHFlow/Online-RLHF) | 記載なし | — | 2024-12-27 |
| PaLM-rlhf-pytorch | [lucidrains/PaLM-rlhf-pytorch](https://github.com/lucidrains/PaLM-rlhf-pytorch) | MIT | 0.7.1（2025-09-19） | 2026-09-20 |
| DeepSpeedExamples | [microsoft/DeepSpeedExamples](https://github.com/microsoft/DeepSpeedExamples) | Apache-2.0 | — | 2026-09-29 |
| understand-r1-zero | [sail-sg/understand-r1-zero](https://github.com/sail-sg/understand-r1-zero) | MIT | — | 2025-08-27 |
| Search-R1 | [PeterGriffinJin/Search-R1](https://github.com/PeterGriffinJin/Search-R1) | Apache-2.0 | — | 2025-11-13 |
| ZeroSearch | [Alibaba-NLP/ZeroSearch](https://github.com/Alibaba-NLP/ZeroSearch) | Apache-2.0 | — | 2025-08-17 |
| DeepResearcher | [GAIR-NLP/DeepResearcher](https://github.com/GAIR-NLP/DeepResearcher) | Apache-2.0 | — | 2026-11-04 |

**周辺ツール**

| OSS | リポジトリ | ライセンス | 最新タグ（日付） | 最終コミット |
|---|---|---|---|---|
| vLLM | [vllm-project/vllm](https://github.com/vllm-project/vllm) | Apache-2.0 | v0.33.0（2026-11-02） | 2026-11-11 |
| SGLang | [sgl-project/sglang](https://github.com/sgl-project/sglang) | Apache-2.0 | v0.5.23（2026-10-28） | 2026-11-11 |
| NeMo Data Designer | [NVIDIA-NeMo/DataDesigner](https://github.com/NVIDIA-NeMo/DataDesigner) | Apache-2.0 | v0.10.0（2026-10-30） | 2026-11-11 |
| distilabel | [argilla-io/distilabel](https://github.com/argilla-io/distilabel) | Apache-2.0 | 1.5.3（2025-01-28） | 2025-12-15 |
| synthetic-data-kit | [meta-llama/synthetic-data-kit](https://github.com/meta-llama/synthetic-data-kit) | MIT | — | 2025-10-25 |
| lm-evaluation-harness | [EleutherAI/lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) | MIT | v0.4.13（2026-09-01） | 2026-09-14 |
| lighteval | [huggingface/lighteval](https://github.com/huggingface/lighteval) | MIT | v0.13.0（2025-11-24） | 2026-10-29 |
| Inspect AI | [UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai) | MIT | 0.3.289（2026-11-10） | 2026-11-10 |
| SkyPilot | [skypilot-org/skypilot](https://github.com/skypilot-org/skypilot) | Apache-2.0 | v0.14.2（2026-10-28） | 2026-11-11 |
| dstack | [dstackai/dstack](https://github.com/dstackai/dstack) | MPL-2.0 | 0.22.7（2026-11-04） | 2026-11-10 |
| Kubeflow Trainer | [kubeflow/trainer](https://github.com/kubeflow/trainer) | Apache-2.0 | v2.4.0（2026-11-06） | 2026-11-06 |
| mergekit | [arcee-ai/mergekit](https://github.com/arcee-ai/mergekit) | LGPL-3.0 | v0.1.5（2026-10-20） | 2026-10-31 |
| Sentence Transformers | [UKPLab/sentence-transformers](https://github.com/UKPLab/sentence-transformers) | Apache-2.0 | v6.3.0（2026-11-11） | 2026-11-11 |
| DSPy | [stanfordnlp/dspy](https://github.com/stanfordnlp/dspy) | MIT | 3.5.0（2026-11-10） | 2026-11-10 |

補足：Megatron-LM の LICENSE は BSD 3条項系の文面ですが、PyPI の `megatron-core` は Apache 2.0 と表記されています。利用時は両方を確認してください。

---

## 付録B コマンド早見表

いずれも各 OSS の README・ドキュメントに記載された書き方です。実行前に公式の最新版を確認してください。

### ファインチューニング

| OSS | インストール | 最小の学習コマンド |
|---|---|---|
| TRL | `pip install trl` | `trl sft --model_name_or_path <model> --dataset_name <dataset>` |
| Unsloth（Core） | `uv pip install unsloth --torch-backend=auto` | Python から `FastLanguageModel` + `SFTTrainer`。または `python unsloth-cli.py --model_name <model> --dataset <dataset> ...` |
| Unsloth（Studio） | `curl -fsSL https://unsloth.ai/install.sh \| sh` | `unsloth studio` |
| LlamaFactory | `git clone` → `pip install -e .` | `llamafactory-cli train examples/train_lora/qwen3_lora_sft.yaml` |
| Axolotl | `uv pip install "axolotl[deepspeed]"` | `axolotl fetch examples && axolotl train examples/llama-3/lora-1b.yml` |
| ms-swift | `pip install ms-swift -U` | `swift sft --model <model> --dataset <dataset> --tuner_type lora` |
| LitGPT | `pip install 'litgpt[extra]'` | `litgpt finetune_lora <model> --data JSON --data.json_path <file>` |
| NeMo AutoModel | `uv sync --frozen`（リポジトリ内） | `automodel <recipe.yaml> --nproc-per-node 8` |
| Oumi | `uv pip install 'oumi[gpu]'` | `oumi train -c <config.yaml>` |
| Ludwig | `pip install "ludwig[llm]"` | `ludwig train --config model.yaml --dataset data.csv` |
| H2O LLM Studio | リポジトリ内で uv | `uv run python llm_studio/train.py -Y <config.yaml>` |

### マルチ GPU

| OSS | 書き方 |
|---|---|
| TRL | `torchrun --nproc_per_node 8 train.py`（`trl` CLI は自動で全 GPU を使用） |
| Unsloth | `torchrun --nproc_per_node=2 unsloth-cli.py ...`（DDP が自動で有効） |
| LlamaFactory | `FORCE_TORCHRUN=1 llamafactory-cli train <yaml>`／複数ノードは `NNODES` `NODE_RANK` `MASTER_ADDR` `MASTER_PORT` |
| Axolotl | YAML に `fsdp_version: 2` + `fsdp_config:`、または `deepspeed: deepspeed_configs/zero1.json` |
| ms-swift | `NPROC_PER_NODE=8 swift sft ... --deepspeed zero2` |
| NeMo AutoModel | `automodel <yaml> --nproc-per-node 8`／複数ノードは `sbatch slurm.sub` |

### 選好最適化・RL

| OSS | コマンド |
|---|---|
| TRL | `trl dpo ...`／`trl kto ...`／`trl grpo --reward_funcs accuracy_reward ...`／`trl rloo ...`／`trl reward ...` |
| LlamaFactory | `llamafactory-cli train examples/train_lora/qwen3_lora_dpo.yaml`（ほか `_kto` `_reward`） |
| Axolotl | YAML に `rl: grpo`、`axolotl vllm-serve config.yaml` でサーバー起動 → `axolotl train config.yaml` |
| ms-swift | `swift rlhf --rlhf_type dpo ...`／`swift rlhf --rlhf_type grpo --use_vllm true --vllm_mode colocate ...` |
| verl | `bash examples/grpo_trainer/run_qwen3_8b_fsdp.sh`／`uv run ... python3 -m verl.trainer.main_ppo key=value ...` |
| OpenRLHF | `ray job submit ... -- python3 -m openrlhf.cli.train_ppo_ray --algo.advantage.estimator group_norm ...` |
| NeMo RL | `uv run python examples/run_grpo.py [--config <yaml>]` |
| Molt | `python3 -m molt.cli.train_rl_ray --algo.advantage.estimator grpo ...` |
| ROLL | `bash examples/<設定ディレクトリ>/run_rlvr_pipeline.sh` |
| AReaL | `python3 examples/math/gsm8k_rl.py --config examples/math/gsm8k_grpo.yaml scheduler.type=local` |
| prime-rl | `uv run rl @ examples/basic/reverse-text/rl.toml` |
| SkyRL | `bash examples/train/gsm8k/run_gsm8k.sh` |
| Trinity-RFT | `trinity run --config examples/grpo_gsm8k/gsm8k.yaml` |
| rLLM | `rllm eval gsm8k`／`rllm train gsm8k` |

### 環境

| OSS | コマンド |
|---|---|
| OpenEnv | `pip install openenv`／環境ごとのクライアントを `pip install git+https://huggingface.co/spaces/openenv/<env>` |
| verifiers | `uv run vf-validate <taskset> -n 1`／`uv run vf-run <taskset> -n 2 -r 1` |
| Harbor | `harbor run -d "<dataset@version>" -m "<model>" -a "<agent>"` |
| NeMo Gym | リポジトリ内で `uv sync` → `gym eval run ...` |

---

## 付録C 用語集

| 用語 | 説明 |
|---|---|
| **FT（ファインチューニング）** | 学習済みモデルを追加データで調整すること |
| **事後学習（post-training）** | 事前学習のあとに行う SFT・選好最適化・RL・蒸留の総称 |
| **SFT** | 教師あり FT。入力と望ましい出力の対で学習する |
| **CPT** | 継続事前学習。ラベルなしテキストで次トークン予測を続ける |
| **PEFT** | パラメータ効率のよい FT の総称（LoRA など）。同名のライブラリもある |
| **LoRA** | 重みの差分を低ランク行列で表し、それだけを学習する手法 |
| **QLoRA** | ベースモデルを量子化したうえで LoRA を学習する手法 |
| **bf16** | bfloat16。指数部が float32 と同じで、混合精度学習でオーバーフローしにくい |
| **FP8 / NVFP4** | 8bit / 4bit の浮動小数点形式。Hopper 以降 / Blackwell 以降で活用される |
| **Compute Capability（CC）** | NVIDIA GPU の世代を表す番号。A100 は 8.0、H100 は 9.0、B200 は 10.0 |
| **DDP** | 各 GPU にモデルを複製してデータ並列で学習する方式 |
| **FSDP / FSDP2** | パラメータ等を GPU 間で分割して持つ PyTorch 標準の方式。2 は新しい実装 |
| **ZeRO** | DeepSpeed の分割方式。ステージ1〜3 がある |
| **TP / PP / CP / EP** | テンソル並列／パイプライン並列／コンテキスト並列／エキスパート並列 |
| **MoE** | Mixture of Experts。入力ごとに一部の専門家層だけを使うモデル構造 |
| **MIG** | 1枚の GPU を複数の独立したインスタンスに分割する機能 |
| **RLHF** | 人間のフィードバックによる強化学習。狭義には報酬モデル + PPO |
| **RLVR** | 検証可能な報酬による強化学習 |
| **RFT** | Reinforcement Fine-Tuning。RL による FT の総称 |
| **PPO** | クリティックを持つ方策勾配法。古典的 RLHF で使われる |
| **GRPO** | グループ内の報酬比較でアドバンテージを作る、クリティック不要の手法 |
| **DPO** | 採用／不採用の応答ペアから直接学習する選好最適化 |
| **ロールアウト** | 現在の方策で応答（軌跡）を生成すること |
| **アドバンテージ** | ある行動が平均よりどれだけ良かったかを表す量 |
| **オンポリシー / オフポリシー** | 学習に使うサンプルが現在の方策から得られたものか、そうでないか |
| **重要度サンプリング補正** | サンプルを生成した分布と学習対象の分布のズレを重みで補正すること |
| **同居 / 分離（colocate / server）** | 推論エンジンを学習と同じ GPU に置くか、別に立てるか |
| **ハーネス** | モデルを動かす実行の枠組み（ツール、コンテキスト管理、制御フローを含む） |
| **タスクセット** | 評価・学習に使うタスクの集まり |
| **トレース / 軌跡** | 1回のエピソードでのやり取りと報酬の記録 |
| **オンポリシー蒸留** | 生徒自身が生成した系列の上で、教師の分布に近づける蒸留 |

---

## 付録D 主要論文

arXiv の番号は、各 OSS の README やドキュメントが参照しているものを中心に挙げています。

**ファインチューニング**

| 手法 | arXiv |
|---|---|
| LoRA | 2106.09685 |
| QLoRA | 2305.14314 |
| DoRA | 2402.09353 |
| OFT / OFTv2 | 2306.07280 / 2506.19847 |
| ZeRO（DeepSpeed） | 1910.02054 |
| FlashAttention-2 | 2307.08691 |

**選好最適化・RLHF**

| 手法 | arXiv |
|---|---|
| PPO | 1707.06347 |
| RLHF（InstructGPT） | 2203.02155 |
| DPO | 2305.18290 |
| KTO | 2402.01306 |
| ORPO | 2403.07691 |

**GRPO 系・RLVR**

| 手法 | arXiv |
|---|---|
| GRPO（DeepSeekMath） | 2402.03300 |
| RLOO | 2402.14740 |
| REINFORCE++ | 2501.03262 |
| DAPO | 2503.14476 |
| Dr. GRPO | 2503.20783 |
| TOPR | 2503.14286 |
| GiGPO | 2505.10978 |
| CISPO（MiniMax-M1） | 2506.13585 |
| GSPO | 2507.18071 |
| LitePPO | 2508.08221 |
| CHORD | 2508.11408 |
| M2PO | 2510.01161 |
| SAPO | 2511.20347 |

**システム**

| 対象 | arXiv |
|---|---|
| HybridFlow（verl） | 2409.19256 |
| AReaL | 2505.24298 |
| AReaL 2.0 技術報告 | 2607.01120 |
| RollArt（ROLL） | 2512.22560 |
| Agent Lightning v1.0 技術報告 | 2608.17528 |

---

## 付録E 出典・公式ドキュメント

**ハードウェアと基盤ソフトウェア**

- [CUDA GPU Compute Capability（NVIDIA）](https://developer.nvidia.com/cuda/gpus)
- [MIG User Guide: Supported GPUs（NVIDIA）](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-gpus.html)
- [Navigating GPU Architecture Support: A Guide for NVIDIA CUDA Developers（NVIDIA）](https://developer.nvidia.com/blog/navigating-gpu-architecture-support-a-guide-for-nvidia-cuda-developers)
- [NVIDIA DGX B200](https://www.nvidia.com/en-us/data-center/dgx-b200/) / [NVIDIA L40S](https://www.nvidia.com/en-us/data-center/l40s/)
- [Tuning CUDA Applications for Blackwell GPU Architecture（NVIDIA）](https://docs.nvidia.com/cuda/blackwell-tuning-guide)
- [PyTorch 2.15 Release Blog](https://pytorch.org/blog/pytorch-2-15-release-blog/)
- [PyTorch dev-discuss: CUDA 12.6 wheels will no longer be published from PyTorch 2.15](https://dev-discuss.pytorch.org/t/notice-cuda-12-6-wheels-will-no-longer-be-published-from-pytorch-2-15-drops-maxwell-pascal-volta/3432)

**ファインチューニング**

- [TRL ドキュメント](https://huggingface.co/docs/trl) / [huggingface/trl](https://github.com/huggingface/trl)
- [huggingface/peft](https://github.com/huggingface/peft) / [huggingface/transformers](https://github.com/huggingface/transformers)
- [Unsloth Docs](https://unsloth.ai/docs) / [unslothai/unsloth](https://github.com/unslothai/unsloth)
- [LlamaFactory ドキュメント](https://llamafactory.readthedocs.io/en/latest/) / [hiyouga/LlamaFactory](https://github.com/hiyouga/LlamaFactory)
- [Axolotl Docs](https://docs.axolotl.ai) / [axolotl-ai-cloud/axolotl](https://github.com/axolotl-ai-cloud/axolotl)
- [ms-swift ドキュメント](https://swift.readthedocs.io/en/latest/) / [modelscope/ms-swift](https://github.com/modelscope/ms-swift)
- [NeMo AutoModel ドキュメント](https://docs.nvidia.com/nemo/automodel/latest/) / [NVIDIA-NeMo/Automodel](https://github.com/NVIDIA-NeMo/Automodel)
- [Megatron Core 開発者ガイド](https://docs.nvidia.com/megatron-core/developer-guide/latest/)
- [Dao-AILab/flash-attention](https://github.com/Dao-AILab/flash-attention)

**強化学習**

- [verl ドキュメント](https://verl.readthedocs.io/en/latest/) / [verl-project/verl](https://github.com/verl-project/verl)
- [OpenRLHF ドキュメント](https://openrlhf.readthedocs.io/) / [OpenRLHF/OpenRLHF](https://github.com/OpenRLHF/OpenRLHF)
- [NeMo RL ドキュメント](https://docs.nvidia.com/nemo/rl/latest/index.html) / [NVIDIA-NeMo/RL](https://github.com/NVIDIA-NeMo/RL) / [NVIDIA-NeMo/labs-molt](https://github.com/NVIDIA-NeMo/labs-molt)
- [ROLL ドキュメント](https://alibaba.github.io/ROLL/) / [alibaba/ROLL](https://github.com/alibaba/ROLL)
- [AReaL ドキュメント](https://areal-project.github.io/AReaL/) / [areal-project/AReaL](https://github.com/areal-project/AReaL)
- [slime ドキュメント](https://thudm.github.io/slime/) / [THUDM/slime](https://github.com/THUDM/slime) / [Miles ドキュメント](https://miles.radixark.com/docs)
- [PrimeIntellect-ai/prime-rl](https://github.com/PrimeIntellect-ai/prime-rl) / [PrimeIntellect-ai/verifiers](https://github.com/PrimeIntellect-ai/verifiers)
- [SkyRL ドキュメント](https://docs.skyrl.ai/docs/index) / [Trinity-RFT ドキュメント](https://agentscope-ai.github.io/Trinity-RFT/)
- [ART Docs](https://art.openpipe.ai) / [Agent Lightning Docs](https://microsoft.github.io/agent-lightning/stable/) / [rLLM Docs](https://docs.rllm-project.com/)
- [OpenEnv Docs](https://huggingface.co/docs/openenv) / [meta-pytorch/OpenEnv](https://github.com/meta-pytorch/OpenEnv)

**俯瞰・比較の資料**

- [Open Source RL Libraries for LLMs（Anyscale）](https://anyscale.com/blog/open-source-rl-libraries-for-llms)
- [The ultimate guide to RL environments（Hugging Face のチームによる比較ガイド）](https://adithyask-rl-environments-guide.hf.space/)
- [SGLang: Post-Training Integration](https://docs.sglang.io/references/post_training_integration.html)
- [AgentsMeetRL（エージェント RL のキュレーションリスト）](https://github.com/thinkwee/AgentsMeetRL)

そのほかのリポジトリの URL は付録A を参照してください。

---

## 付録F 確認できなかったこと

本書の記述の限界を明示しておきます。

1. **実機での実行検証はしていません。** コマンドと設定例は各 OSS の README・ドキュメント・同梱サンプルの記法を確認して書いたものです。バージョンの組み合わせによっては、そのままでは動かない可能性があります。
2. **GitHub のスター数・Issue の状況は取得していません。** 「活発さ」は最終コミット日と最新リリース日で判断しています。
3. **B300 のメモリ容量**は、資料によって 268GB・270GB・288GB と表記が分かれていました。本書では公称値として 288GB を採り、揺れがあることを注記しています。
4. **Rubin 世代**は、PyTorch 2.15 の CUDA 13.4 ホイールが実験的サポートを追加したという事実のみを確認しました。各 OSS の対応状況は未確認です。
5. **SkyRL の非同期学習への対応**と、**NeMo RL の非同期 GRPO の詳細**は、一次資料で十分に確認できていません。比較表の該当欄は参考程度に見てください。
6. **Miles・ROLL・Agent Lightning の詳細な手順**は、公式ドキュメントへの案内にとどめています。
7. **ライセンス**は LICENSE ファイルの文面から判定しました。複数ライセンスが混在するリポジトリ（Unsloth など）や、依存ライブラリのライセンスまでは精査していません。商用利用の際は必ず原文を確認してください。
8. **マネージドサービス**（各社のファインチューニング API、W&B のサーバーレス RL、Tinker、Prime Intellect のホスト型学習など）は、OSS との接点に触れるのみで、料金や仕様は調べていません。

---

*本書は 2026-11-11 時点の公開情報に基づきます。*
