#!/usr/bin/env python3
"""embedcheck.py - does your embedding / reranker server compute what sentence-transformers computes?

It sends the same texts to your server and to the Hugging Face model run locally, prints the
cosine (embeddings) or the score agreement (rerankers) per input, and names the most likely cause
when they differ: pooling, normalization, prompt prefix, truncation, token type ids, a dropped
pooler, or a missing classifier head.

  pip install sentence-transformers requests
  # embeddings: llama-server, Ollama, TEI, vLLM, or any OpenAI-compatible /v1/embeddings
  python embedcheck.py embed  --model BAAI/bge-small-en-v1.5 --url http://127.0.0.1:8080
  python embedcheck.py embed  --model nomic-ai/nomic-embed-text-v1.5 --url http://127.0.0.1:11434 --api ollama --served-model nomic-embed-text
  # rerankers: llama-server /v1/rerank, TEI /rerank, vLLM /v1/rerank
  python embedcheck.py rerank --model cross-encoder/ms-marco-MiniLM-L6-v2 --url http://127.0.0.1:8080
  python embedcheck.py rerank --model Qwen/Qwen3-Reranker-0.6B --kind qwen3 --url http://127.0.0.1:8080

Exit status: 0 = matches, 1 = mismatch found, 2 = could not run.
https://erimaki-kobo.github.io/en/gguf-embedding-rerank-parity-check/
"""
import argparse, json, math, sys

try:
    import requests
except ImportError:
    sys.exit("pip install requests")

__version__ = "1.0"

TEXTS = [
    "The capital of France is Paris.",
    "How do I install the package on Windows?",
    "A cat is sleeping on the warm windowsill.",
    "東京は日本の首都です。",
    "def add(a, b):\n    return a + b",
    "GPU memory ran out at batch size 64 🙃",
]
LONG_UNIT = ("Retrieval systems split documents into chunks, embed each chunk, and compare the query "
             "vector with every chunk vector using cosine similarity. ")

QUERIES = ["what is the capital of france", "how to install the package"]
DOCS = ["Paris is the capital and largest city of France.",
        "Run pip install package-name in a terminal to install it.",
        "Cats sleep for twelve to sixteen hours a day.",
        "France borders Spain, Italy, Germany and Belgium.",
        "The installer is available for Windows, macOS and Linux."]

OK_COS = 0.999     # float32/float16 engines land above this when nothing is wrong
QUANT_COS = 0.98   # Q8_0 / Q4 GGUF usually land between this and OK_COS


def cos(a, b):
    na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def norm(a):
    return math.sqrt(sum(x * x for x in a))


def spearman(a, b):
    def ranks(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for k, i in enumerate(o):
            r[i] = float(k)
        return r
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    if n < 2:
        return 1.0
    d = sum((x - y) ** 2 for x, y in zip(ra, rb))
    return 1 - 6 * d / (n * (n * n - 1))


# ---------------------------------------------------------------- server calls
class Server:
    def __init__(self, a):
        self.url = a.url.rstrip("/")
        self.api = a.api
        self.model = a.served_model or a.model
        self.timeout = a.timeout
        self.headers = {"Authorization": f"Bearer {a.api_key}"} if a.api_key else {}

    def _post(self, path, body):
        r = requests.post(self.url + path, json=body, headers=self.headers, timeout=self.timeout)
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code} from {path}: {r.text[:300]}")
        return r.json()

    def embed(self, text):
        if self.api == "openai":
            j = self._post("/v1/embeddings", {"model": self.model, "input": [text], "encoding_format": "float"})
            return j["data"][0]["embedding"]
        if self.api == "ollama":
            return self._post("/api/embed", {"model": self.model, "input": [text]})["embeddings"][0]
        if self.api == "ollama-legacy":
            return self._post("/api/embeddings", {"model": self.model, "prompt": text})["embedding"]
        if self.api == "tei":
            return self._post("/embed", {"inputs": [text]})[0]
        raise ValueError(self.api)

    def rerank(self, query, docs):
        if self.api == "tei":
            j = self._post("/rerank", {"query": query, "texts": docs, "raw_scores": True})
            out = [None] * len(docs)
            for it in j:
                out[it["index"]] = it["score"]
            return out
        j = self._post("/v1/rerank", {"model": self.model, "query": query, "documents": docs, "top_n": len(docs)})
        out = [None] * len(docs)
        for it in j["results"]:
            out[it["index"]] = it.get("relevance_score", it.get("score"))
        return out


# ---------------------------------------------------------------- embeddings
def st_variants(st, text, max_pos):
    """Reference vectors for every pooling x prompt x truncation choice an engine might make."""
    import torch
    prompts = {"(none)": ""}
    for k, v in (st.prompts or {}).items():
        if v:
            prompts[k] = v
    out = {}
    keep = st.max_seq_length
    for pname, ptext in prompts.items():
        for trunc in ("st", "none"):
            st.max_seq_length = keep if trunc == "st" else max_pos
            tok = st.encode(text, prompt=ptext, output_value="token_embeddings", convert_to_numpy=False)
            tok = tok.float()
            n_tok = tok.shape[0]
            for pool in ("cls", "mean", "last"):
                v = {"cls": tok[0], "mean": tok.mean(0), "last": tok[-1]}[pool]
                out[(pool, pname, trunc)] = (v / v.norm()).tolist(), n_tok
    st.max_seq_length = keep
    return out


def st_settings(st):
    pool, normalize, extra = None, False, []
    for m in st:
        name = type(m).__name__
        if name == "Pooling":
            pool = getattr(m, "pooling_mode", None) or m.get_pooling_mode_str()
            pool = {"lasttoken": "last"}.get(pool, pool)
        elif name == "Normalize":
            normalize = True
        elif name not in ("Transformer",):
            extra.append(name)
    return pool, normalize, extra


def check_embed(a):
    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer(a.model, device="cpu", trust_remote_code=a.trust_remote_code)
    pool, st_norm, extra = st_settings(st)
    dflt = st.default_prompt_name if a.prompt_name is None else a.prompt_name
    dflt_text = (st.prompts or {}).get(dflt, "") if dflt else ""
    cfg = st[0].auto_model.config
    max_pos = getattr(cfg, "max_position_embeddings", st.max_seq_length) or st.max_seq_length
    srv = Server(a)
    print(f"reference: sentence-transformers, pooling={pool}, normalize={st_norm}, max_seq_length={st.max_seq_length}, "
          f"max_position_embeddings={max_pos}, prompt applied by default={dflt_text!r}" + (f", extra modules={extra}" if extra else ""))
    print(f"server: {srv.url} api={srv.api}\n")

    n_long = 1
    while len(st.tokenizer(LONG_UNIT * n_long)["input_ids"]) <= int(st.max_seq_length * 1.5):
        n_long += 1
    texts = TEXTS + [LONG_UNIT * n_long]
    causes, worst, rows = set(), 1.0, []
    for i, t in enumerate(texts):
        label = "long" if i == len(texts) - 1 else str(i + 1)
        ref = st.encode(t, prompt=dflt_text if dflt else None, normalize_embeddings=False).tolist()
        try:
            got = srv.embed(t)
        except Exception as e:
            msg = str(e)
            rows.append((label, None, None, "error: " + msg[:160]))
            if "Pooling type 'none'" in msg:
                causes.add("pooling-none")
            elif label == "long":
                causes.add("long-error")
            else:
                causes.add("error")
            continue
        if len(got) != len(ref):
            rows.append((label, None, norm(got), f"dimension {len(got)} vs reference {len(ref)}"))
            causes.add("dims")
            continue
        c = cos(ref, got)
        worst = min(worst, c)
        why = ""
        if c < OK_COS and not extra:
            best, bestc, ntok = None, -2, 0
            for key, (v, nt) in st_variants(st, t, max_pos).items():
                cc = cos(v, got)
                if cc > bestc:
                    best, bestc, ntok = key, cc, nt
            bpool, bprompt, btrunc = best
            parts = []
            if bestc < OK_COS:
                parts.append(f"no simple variant matches (best {bestc:.4f})")
                causes.add("unknown" if c < QUANT_COS else "quant")
            else:
                if bpool != pool:
                    parts.append(f"server pools with {bpool} (model: {pool})"); causes.add("pooling")
                want_p = dflt if dflt_text else "(none)"
                if bprompt != want_p:
                    pt = "no prefix" if bprompt == "(none)" else repr(st.prompts[bprompt])
                    parts.append(f"server sees {pt} (reference: {dflt_text!r})"); causes.add("prompt")
                if btrunc != "st":
                    parts.append(f"server reads {ntok} tokens, sentence-transformers cuts at {st.max_seq_length}"); causes.add("truncation")
            why = "; ".join(parts)
        rows.append((label, c, norm(got), why))

    print(f"{'text':>5} {'cosine':>9} {'|server|':>9}  diagnosis")
    for label, c, n, why in rows:
        cs = f"{c:9.6f}" if c is not None else f"{'-':>9}"
        ns = f"{n:9.4f}" if n is not None else f"{'-':>9}"
        print(f"{label:>5} {cs} {ns}  {why}")
    norms = [n for _, c, n, _ in rows if n is not None]
    if norms and st_norm and any(abs(n - 1) > 1e-3 for n in norms):
        causes.add("not-normalized")
    if norms and not st_norm and all(abs(n - 1) < 1e-3 for n in norms):
        causes.add("normalized")
    return report(causes, worst, st=st, pool=pool, dflt_text=dflt_text, api=a.api)


FIX = {
    "pooling": "Pooling differs. llama.cpp: the GGUF's <arch>.pooling_type wins unless you pass --pooling {mean,cls,last}; "
               "a GGUF converted from a folder without modules.json / 1_Pooling has no pooling_type. Ollama uses the GGUF's value. "
               "TEI: --pooling. vLLM: --pooler-config '{\"seq_pooling_type\": \"MEAN\"}'.",
    "prompt": "The prefix differs. sentence-transformers applies default_prompt_name from config_sentence_transformers.json on every encode(); "
              "llama.cpp, Ollama and vLLM's /v1/embeddings never add it, TEI only with --default-prompt-name. Put the prefix in the text yourself "
              "(e.g. 'search_query: ', 'query: ') or pass prompt='' to sentence-transformers.",
    "truncation": "The server embedded more tokens than sentence-transformers does. sentence-transformers cuts at max_seq_length; "
                  "llama.cpp has no max_seq_length (it uses the whole input up to -ub / n_ctx), Ollama cuts at the GGUF context_length (or num_ctx). "
                  "Cut the text to max_seq_length tokens before sending, or raise max_seq_length in sentence-transformers if the model was trained for it.",
    "long-error": "The server refused the long input instead of truncating it. llama-server: 'input (N tokens) is too large to process. increase the physical batch size' "
                  "means the text is longer than -ub (default 512): raise -ub and -b, or cut the text. vLLM refuses inputs over max_model_len unless "
                  "truncate_prompt_tokens is set; TEI refuses with --auto-truncate false.",
    "not-normalized": "Vectors are not unit length but the model ends with Normalize. llama-server normalizes /v1/embeddings by default (--embd-normalize 2), "
                      "but Ollama's legacy /api/embeddings and llama-server with --embd-normalize -1 return raw vectors. Cosine is unaffected; dot product and "
                      "L2 distance are not.",
    "normalized": "The server returns unit vectors but the model has no Normalize module. Cosine is unaffected; if you rank by dot product, "
                  "the scores change (Ollama /api/embed and llama-server /v1/embeddings always normalize by default).",
    "pooling-none": "The GGUF has no pooling_type, so llama-server runs with pooling 'none' and /v1/embeddings refuses it "
                    "('Pooling type none is not OAI compatible'). This happens when the folder you converted had no modules.json / "
                    "1_Pooling/config.json. Start llama-server with --pooling set to the model's pooling (sentence-transformers says it above), "
                    "or reconvert from the full model folder.",
    "dims": "Dimension mismatch: you are comparing a different model, or the server truncates to 'dimensions' (Matryoshka).",
    "quant": "Close but not equal: typical of a quantized GGUF (Q8_0 usually > 0.99, Q4 can be lower). Compare an F16/F32 GGUF to separate quantization from bugs.",
    "unknown": "No pooling/prefix/truncation choice explains it: suspect a broken conversion (wrong tokenizer pre-type, missing tensors), "
               "a wrong model name on the server, or an architecture the engine implements differently. Check the server log for warnings.",
    "error": "The server returned an error for a normal input; fix that first.",
}


WARN_ONLY = {"long-error", "not-normalized", "normalized"}


def report(causes, worst, **kw):
    print()
    bad = sorted(causes - WARN_ONLY)
    if not bad:
        print(f"verdict: MATCH (worst cosine {worst:.6f})" + (" - with notes:" if causes else ""))
    else:
        print("verdict: MISMATCH")
    for c in bad + sorted(causes & WARN_ONLY):
        print(" - " + FIX[c])
    return 1 if bad else 0


# ---------------------------------------------------------------- GGUF metadata
POOL_NAMES = {0: "none", 1: "mean", 2: "cls", 3: "last", 4: "rank"}


def inspect_gguf(path, mode, kind):
    """Read the GGUF header (pip install gguf) and print what llama.cpp / Ollama will do with it."""
    try:
        import gguf
    except ImportError:
        print("(--gguf needs: pip install gguf)")
        return set()
    r = gguf.GGUFReader(path)

    def val(key):
        f = r.fields.get(key)
        if f is None:
            return None
        if f.types and f.types[0] == gguf.GGUFValueType.STRING:
            return bytes(f.parts[-1]).decode("utf-8", "replace")
        if f.types and f.types[0] == gguf.GGUFValueType.ARRAY:
            return [bytes(f.parts[i]).decode("utf-8", "replace") if f.types[-1] == gguf.GGUFValueType.STRING
                    else f.parts[i].tolist()[0] for i in f.data]
        return f.parts[-1].tolist()[0]
    arch = val("general.architecture")
    pool = val(f"{arch}.pooling_type")
    names = {t.name for t in r.tensors}
    cls_t = sorted(n for n in names if n.startswith("cls"))
    tmpl = val("tokenizer.chat_template.rerank")
    act = val(f"{arch}.classifier.activation")
    print(f"gguf: arch={arch} pooling_type={POOL_NAMES.get(pool, pool) if pool is not None else '(not set)'} "
          f"cls tensors={cls_t or 'none'}" + (f" classifier.activation={act}" if act else "") +
          (" rerank template=yes" if tmpl else ""))
    found = set()
    if mode == "embed" and pool is None:
        found.add("gguf-no-pool")
    if mode == "rerank":
        if "cls.output.weight" not in names and "cls.weight" not in names:
            found.add("gguf-no-head")
        if arch == "qwen3" and pool != 4:
            found.add("gguf-qwen3-not-rank")
        if arch == "bert" and "cls.output.weight" in names and "cls.weight" not in names:
            found.add("gguf-maybe-no-pooler")
    return found


GFIX = {
    "gguf-no-pool": "GGUF: no pooling_type. llama-server falls back to pooling 'none' (/v1/embeddings then refuses with 'Pooling type none "
                    "is not OAI compatible'); pass --pooling explicitly or reconvert from a folder that has modules.json and 1_Pooling/.",
    "gguf-no-head": "GGUF: no cls.weight / cls.output.weight, so there is no classifier: /v1/rerank returns softmax(hidden)[0] "
                    "(tiny numbers such as 4.5e-23 on a real model) that also change with the other documents in the request.",
    "gguf-qwen3-not-rank": "GGUF: a Qwen3 model without pooling_type rank. The converter only treats Qwen3 as a reranker when the folder's "
                           "README.md contains '# Qwen3-Reranker', the folder or _name_or_path contains 'qwen3-reranker', or the "
                           "architecture is *ForSequenceClassification.",
    "gguf-maybe-no-pooler": "GGUF: BERT classifier with cls.output.* but no cls.weight. If the original is a BertForSequenceClassification "
                            "(it has bert.pooler.dense), the pooler was dropped: llama.cpp #33109, fixed in the converter from b12818.",
}


# ---------------------------------------------------------------- rerankers
def ce_reference(model_id, pairs, trust):
    """Cross-encoder logits plus the variants converters / engines are known to produce."""
    import torch
    from sentence_transformers import CrossEncoder
    ce = CrossEncoder(model_id, device="cpu", trust_remote_code=trust)
    m, tok = ce.model, ce.tokenizer
    logits = ce.predict(pairs, activation_fn=torch.nn.Identity()).tolist()
    var = {"logit": logits, "sigmoid": [1 / (1 + math.exp(-x)) for x in logits]}
    enc = tok([p[0] for p in pairs], [p[1] for p in pairs], padding=True, truncation=True, return_tensors="pt")
    base = getattr(m, m.base_model_prefix, None)
    with torch.no_grad():
        if "token_type_ids" in enc:
            e0 = dict(enc); e0["token_type_ids"] = torch.zeros_like(enc["token_type_ids"])
            var["token_type_ids=0"] = m(**e0).logits[:, 0].tolist()
        pooler = getattr(base, "pooler", None)
        clf = getattr(m, "classifier", None)
        if pooler is not None and isinstance(clf, torch.nn.Linear):
            for tt, key in ((enc.get("token_type_ids"), "no pooler"), (None, "no pooler, token_type_ids=0")):
                e = dict(enc)
                if tt is None and "token_type_ids" in e:
                    e["token_type_ids"] = torch.zeros_like(enc["token_type_ids"])
                h = base(**{k: v for k, v in e.items()}).last_hidden_state[:, 0]
                var[key] = clf(h)[:, 0].tolist()
    return var


QWEN3_PREFIX = ("<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the "
                "Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n")
QWEN3_SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
QWEN3_TASK = "Given a web search query, retrieve relevant passages that answer the query"


def qwen3_reference(model_id, pairs, trust):
    """The scoring recipe from the Qwen3-Reranker model card: P(yes) from the last-token logits."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_id, padding_side="left", trust_remote_code=trust)
    m = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=trust).eval()
    yes, no = tok.convert_tokens_to_ids("yes"), tok.convert_tokens_to_ids("no")
    texts = [f"{QWEN3_PREFIX}<Instruct>: {QWEN3_TASK}\n<Query>: {q}\n<Document>: {d}{QWEN3_SUFFIX}" for q, d in pairs]
    enc = tok(texts, padding=True, return_tensors="pt", add_special_tokens=False)
    with torch.no_grad():
        last = m(**enc).logits[:, -1, :].float()
    ly, ln = last[:, yes], last[:, no]
    p = torch.softmax(torch.stack([ln, ly], 1), 1)[:, 1]
    var = {"P(yes)": p.tolist(), "logit(yes)-logit(no)": (ly - ln).tolist(), "logit(yes)": ly.tolist()}
    # What llama.cpp computes for a Qwen3 GGUF that has no cls.output.weight and no rerank template:
    # query and document tokens are concatenated, and the softmax is taken over the last hidden state.
    head = []
    with torch.no_grad():
        for q, d in pairs:
            ids = tok(q, add_special_tokens=False)["input_ids"] + tok(d, add_special_tokens=False)["input_ids"]
            h = m.model(input_ids=torch.tensor([ids])).last_hidden_state[0, -1].float()
            head.append(torch.softmax(h, 0)[0].item())
    var["no head: softmax(hidden)[0]"] = head
    return var


def check_rerank(a):
    pairs = [(q, d) for q in QUERIES for d in DOCS]
    ref = (qwen3_reference if a.kind == "qwen3" else ce_reference)(a.model, pairs, a.trust_remote_code)
    main = "P(yes)" if a.kind == "qwen3" else "logit"
    srv = Server(a)
    print(f"reference: {'Qwen3-Reranker recipe (P(yes) at the last token)' if a.kind == 'qwen3' else 'sentence-transformers CrossEncoder, raw logits'}")
    print(f"server: {srv.url} api={'tei /rerank' if srv.api == 'tei' else '/v1/rerank'}\n")
    got = []
    try:
        for q in QUERIES:
            got += srv.rerank(q, DOCS)
    except Exception as e:
        print("error:", str(e)[:300])
        return 2
    print(f"{'pair':>4} {'reference':>11} {'server':>11}")
    for i, (r, g) in enumerate(zip(ref[main], got)):
        print(f"{i + 1:>4} {r:11.5f} {g:11.5g}")
    causes, notes = set(), []

    def close(x, y):
        return all(abs(p - q) <= 1e-3 * max(1.0, abs(p)) + 1e-4 for p, q in zip(x, y))

    rho = [spearman(ref[main][i:i + len(DOCS)], got[i:i + len(DOCS)]) for i in range(0, len(got), len(DOCS))]
    print(f"\nrank agreement per query (Spearman): {', '.join(f'{r:.3f}' for r in rho)}")
    if close(ref[main], got):
        print("server returns the same score as the reference" + (" (raw logit)" if main == "logit" else ""))
    else:
        hit = [k for k, v in ref.items() if k != main and close(v, got)]
        if hit:
            k = hit[0]
            print(f"server score matches the reference variant: {k}")
            causes.add({"sigmoid": "sigmoid", "token_type_ids=0": "segments", "no pooler": "pooler",
                        "no pooler, token_type_ids=0": "pooler+segments", "logit(yes)-logit(no)": "qwen-logit",
                        "logit(yes)": "qwen-yes", "no head: softmax(hidden)[0]": "tiny"}[k])
        elif max(abs(x) for x in got) < 1e-6:
            causes.add("tiny")
        else:
            causes.add("rank-unknown" if min(rho) < 0.999 else "rank-ok-scale")
    for c in sorted(causes):
        notes.append(RFIX[c])
    print()
    if not causes:
        print("verdict: MATCH")
        return 0
    bad = any(c in causes for c in ("pooler", "pooler+segments", "segments", "tiny", "rank-unknown"))
    print("verdict: " + ("MISMATCH" if bad else "SAME RANKING, DIFFERENT SCALE"))
    for n in notes:
        print(" - " + n)
    return 1 if bad else 0


RFIX = {
    "sigmoid": "The server applies a sigmoid (TEI without raw_scores, vLLM for 1-label cross-encoders). Ranking is unchanged; "
               "compare against CrossEncoder.predict() with its default activation, or ask for raw scores.",
    "segments": "The server feeds token_type_ids = 0 for the document. llama.cpp's BERT path passes zeros for every token, "
                "so a cross-encoder trained with segment B embeddings gets slightly different scores.",
    "pooler": "The pooler (dense + tanh on [CLS]) was dropped: this is llama.cpp #33109. GGUFs converted before the fix "
              "(PR #33122, first build b12818, 2026-11-27) lack cls.weight / cls.bias. Reconvert with b12818 or later.",
    "pooler+segments": "The pooler was dropped (llama.cpp #33109, fixed in the converter from b12818) and the document got token_type_ids = 0. "
                       "Reconvert with b12818 or later; the segment-id part remains in current llama.cpp.",
    "qwen-logit": "The server returns logit(yes) - logit(no) (llama.cpp's rank pooling). sigmoid() of it equals P(yes); ranking is the same.",
    "qwen-yes": "The server returns logit(yes) only.",
    "tiny": "The scores are not a relevance score: they equal softmax(last hidden state)[0], which is tiny for a real model (e.g. 4.5e-23). The GGUF has no usable classifier head: a Qwen3-Reranker converted as a plain "
            "Qwen3 LLM has no cls.output.weight and no rank pooling. Reconvert from a folder whose README or name says Qwen3-Reranker, "
            "or use a GGUF that lists cls.output.weight.",
    "rank-ok-scale": "Scores differ but the order is the same; probably a different activation or a quantized GGUF.",
    "rank-unknown": "The order differs and no known variant explains it: check the GGUF has cls.* tensors and pooling_type = rank, "
                    "that -ub covers query + document, and that the KV cache is not quantized (-ctk/-ctv q4_0 hurts rerankers).",
}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=["embed", "rerank"])
    p.add_argument("--model", required=True, help="Hugging Face id or local folder of the original model")
    p.add_argument("--url", default="http://127.0.0.1:8080")
    p.add_argument("--api", default="openai", choices=["openai", "ollama", "ollama-legacy", "tei", "vllm", "llama"],
                   help="embed: openai (llama-server, vLLM, LM Studio...), ollama, ollama-legacy, tei. rerank: llama/vllm (/v1/rerank) or tei")
    p.add_argument("--served-model", help="model name the server expects, if different from --model")
    p.add_argument("--kind", default="cross-encoder", choices=["cross-encoder", "qwen3"])
    p.add_argument("--prompt-name", help="prompt the reference should apply (default: the model's default_prompt_name)")
    p.add_argument("--gguf", help="path to the GGUF the server runs; its header is checked too (pip install gguf)")
    p.add_argument("--api-key")
    p.add_argument("--timeout", type=float, default=120)
    p.add_argument("--trust-remote-code", action="store_true")
    p.add_argument("--version", action="version", version=__version__)
    a = p.parse_args()
    if a.api in ("vllm", "llama") and a.mode == "embed":
        a.api = "openai"
    try:
        g = inspect_gguf(a.gguf, a.mode, a.kind) if a.gguf else set()
        for k in sorted(g):
            print(" ! " + GFIX[k])
        if g:
            print()
        rc = check_embed(a) if a.mode == "embed" else check_rerank(a)
        sys.exit(max(rc, 1 if g else 0))
    except requests.ConnectionError as e:
        print("could not reach the server:", e)
        sys.exit(2)


if __name__ == "__main__":
    main()
