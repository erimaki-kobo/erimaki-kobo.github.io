#!/usr/bin/env python3
"""lpcheck.py - logprob parity check for LLM inference engines
(vLLM, llama.cpp server, SGLang, any OpenAI-compatible endpoint, Hugging Face transformers).

It answers "my engine's logprobs or greedy outputs differ from the reference:
is that rounding, a setting, or a bug?" in five steps:

  T  tokens in    does the endpoint tokenize the prompt text to the same ids?
  P  meaning      do the returned logprobs change with temperature, top_p or a
                  repetition penalty (processed) or not (raw model output)?
  G  greedy       free-running greedy generation from identical token ids
  S  same tokens  the candidate scores the reference's own continuation, so every
                  position is compared on identical context (teacher forcing)
  C  self         the candidate's decode-path logprobs against its scoring-path
                  logprobs for the same tokens (its own noise floor)

Reference (exactly one):
  --ref-hf PATH_OR_ID   Hugging Face transformers in this process (needs torch)
  --ref-url URL         another OpenAI-compatible endpoint
  --ref-file FILE       a reference saved earlier with --save-ref
Candidate (one):
  --base-url URL        an OpenAI-compatible endpoint (/v1/completions with logprobs)
  --cand-hf PATH_OR_ID  transformers in this process (e.g. another dtype)

Standard library only unless --ref-hf or --cand-hf is used. Python 3.8+.

    python lpcheck.py --ref-hf Qwen/Qwen3-0.6B --base-url http://localhost:8000/v1
    python lpcheck.py --ref-hf ./model --save-ref ref.json          # reference only
    python lpcheck.py --ref-file ref.json --base-url http://localhost:8080/v1
    python lpcheck.py --ref-url http://localhost:8000/v1 --base-url http://localhost:8001/v1
    python lpcheck.py --ref-hf ./model --cand-hf ./model --cand-dtype bfloat16

Exit code: 0 identical or within tolerance, 1 numeric gap beyond tolerance,
3 the two sides are not computing the same thing (tokenization or logprob
semantics), 2 could not run.
"""
import argparse
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request

VERSION = "1.0.0"
PASSAGE = (
    "The harbour town of Velmar keeps a ledger of every ship that has entered its bay since the "
    "lighthouse was built. Each entry records the name of the vessel, the colour of its sails, the "
    "cargo it declared and the weather on the day it arrived. Clerks copy the ledger by hand every "
    "ten years, and the old copies are stored in a dry cellar under the customs house. "
)
PROMPTS = [
    ("story", "Once upon a time, there was a little girl named Lily. She"),
    ("fact", "The capital of France is"),
    ("code", "def fibonacci(n):\n    \"\"\"Return the n-th Fibonacci number.\"\"\"\n"),
    ("qa", "Q: What is 17 + 26?\nA:"),
    ("list", "The planets of the solar system, ordered by distance from the sun:\n1."),
    ("passage", PASSAGE + "In short,"),
    ("repeat", "one two three four five six one two three four five six one two three"),
    ("dialogue", "Tom said, \"Let's go to the park.\" Sue smiled and said, \""),
]
TOKID = re.compile(r"^token_id:(\d+)$")


class HttpError(Exception):
    def __init__(self, code, body):
        Exception.__init__(self, "HTTP %s: %s" % (code, body))
        self.code = code


def http(url, payload=None, key="", timeout=600.0):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="GET" if data is None else "POST")
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, e.read().decode("utf-8", "replace")[:300])


# ----------------------------------------------------------------- response parsing

def _entry(tok_or_key, lp, tid=None):
    """One candidate token: [id or None, text, logprob]."""
    text = tok_or_key if isinstance(tok_or_key, str) else ""
    if tid is None and isinstance(tok_or_key, str):
        m = TOKID.match(tok_or_key)
        if m:
            tid, text = int(m.group(1)), ""
    return [tid, text, lp]


def parse_steps(choice):
    """-> list of steps {id, tok, lp, top:[[id, text, logprob], ...] sorted, kind}.
    Understands the legacy completions shape (tokens / token_logprobs / top_logprobs,
    with vLLM's token_id:N strings) and the chat-style shape (logprobs.content[...],
    which llama.cpp also uses for /v1/completions and which carries token ids)."""
    lp = choice.get("logprobs") or {}
    steps = []
    if isinstance(lp.get("content"), list):
        for t in lp["content"]:
            kind = "logprob"
            raw_top = t.get("top_logprobs")
            if raw_top is None and "top_probs" in t:          # llama.cpp post_sampling_probs
                kind, raw_top = "prob", t.get("top_probs")
            top = []
            for a in raw_top or []:
                v = a.get("logprob") if kind == "logprob" else _safe_log(a.get("prob"))
                if v is not None:
                    top.append(_entry(a.get("token", ""), v, a.get("id")))
            v = t.get("logprob") if "logprob" in t else _safe_log(t.get("prob"))
            e = _entry(t.get("token", ""), v, t.get("id"))
            top.sort(key=lambda x: -x[2])
            steps.append({"id": e[0], "tok": e[1], "lp": e[2], "top": top, "kind": kind})
    elif isinstance(lp.get("tokens"), list):
        tls = lp.get("token_logprobs") or []
        tops = lp.get("top_logprobs") or []
        ids = choice.get("token_ids") or []
        for i, tk in enumerate(lp["tokens"]):
            e = _entry(tk, tls[i] if i < len(tls) else None, ids[i] if i < len(ids) else None)
            d = tops[i] if i < len(tops) and isinstance(tops[i], dict) else {}
            top = sorted((_entry(k, v) for k, v in d.items() if v is not None), key=lambda x: -x[2])
            steps.append({"id": e[0], "tok": e[1], "lp": e[2], "top": top, "kind": "logprob"})
    return steps


def _safe_log(p):
    if p is None:
        return None
    return math.log(p) if p > 0 else -9999.0


# ----------------------------------------------------------------- endpoint

class Endpoint:
    def __init__(self, base, model, key, timeout, k, flavor="auto"):
        self.base = base.rstrip("/")
        self.root = re.sub(r"/v1$", "", self.base)
        self.url = self.base + "/completions"
        self.model, self.key, self.timeout, self.k, self.flavor = model, key, timeout, k, flavor
        self.id_prompts = True
        self.notes = []

    def _post(self, url, payload):
        return http(url, payload, self.key, self.timeout)

    def connect(self):
        info = http(self.base + "/models", None, self.key, self.timeout)
        entries = info.get("data") or []
        entry = next((e for e in entries if e.get("id") == self.model), entries[0] if entries else {})
        if not self.model:
            self.model = entry.get("id")
        if self.flavor == "auto":
            owner = str(entry.get("owned_by") or "").lower()
            self.flavor = ("vllm" if "vllm" in owner else "llamacpp" if "llama" in owner
                           else "sglang" if "sglang" in owner else "generic")
        probe_ids = [1, 2, 3]
        try:
            self.complete(probe_ids, 1)
        except HttpError as e:
            if self.flavor != "generic":
                self.notes.append("%s-specific parameters were rejected (%s); using standard parameters only."
                                  % (self.flavor, str(e)[:80]))
                self.flavor = "generic"
                try:
                    self.complete(probe_ids, 1)
                    return self
                except HttpError:
                    pass
            self.id_prompts = False
            self.notes.append("the endpoint does not accept token-id prompts; text prompts are used, so "
                              "tokenization and numeric differences cannot be separated and step S is skipped.")
            self.complete("Hello", 1)
        return self

    def payload(self, prompt, n, temperature, extra=None):
        p = {"model": self.model, "prompt": prompt, "max_tokens": n, "temperature": temperature,
             "logprobs": self.k, "stream": False}
        if self.flavor == "vllm":
            p["return_tokens_as_token_ids"] = True
        elif self.flavor == "llamacpp":
            p["n_probs"] = self.k
        if extra:
            p.update(extra)
        return p

    def complete(self, prompt, n, temperature=0.0, extra=None):
        resp = self._post(self.url, self.payload(prompt, n, temperature, extra))
        choice = resp["choices"][0]
        return {"steps": parse_steps(choice), "text": choice.get("text") or "",
                "prompt_tokens": (resp.get("usage") or {}).get("prompt_tokens"), "choice": choice}

    def tokenize(self, text):
        """-> token ids the endpoint would feed the model for this text prompt, or None."""
        attempts = []
        if self.flavor in ("vllm", "generic", "sglang"):
            attempts.append((self.root + "/tokenize", {"model": self.model, "prompt": text, "add_special_tokens": True}))
        if self.flavor in ("llamacpp", "generic"):
            attempts.append((self.root + "/tokenize", {"content": text, "add_special": True, "parse_special": True}))
        for url, payload in attempts:
            try:
                out = self._post(url, payload)
                toks = out.get("tokens")
                if isinstance(toks, list) and toks and all(isinstance(x, int) for x in toks):
                    return toks
            except Exception:  # noqa: BLE001 - endpoint without this route
                continue
        return None

    def chat_ids(self, messages):
        """-> token ids of the rendered chat prompt as the endpoint builds it, or None."""
        try:
            if self.flavor in ("vllm", "generic", "sglang"):
                out = self._post(self.root + "/tokenize", {"model": self.model, "messages": messages,
                                                           "add_generation_prompt": True})
                if isinstance(out.get("tokens"), list) and out["tokens"]:
                    return out["tokens"]
            if self.flavor in ("llamacpp", "generic"):
                out = self._post(self.root + "/apply-template", {"messages": messages})
                if isinstance(out.get("prompt"), str):
                    return self.tokenize(out["prompt"])
        except Exception:  # noqa: BLE001
            return None
        return None

    def score(self, prompt_ids, cont_ids, mode):
        """Score cont_ids token by token given prompt_ids. -> (steps, method).
        steps[i] holds the endpoint's top-k for position i (and the reference token when known)."""
        if mode in ("auto", "prompt_logprobs") and self.flavor == "vllm":
            try:
                full = list(prompt_ids) + list(cont_ids)
                resp = self._post(self.url, {"model": self.model, "prompt": full, "max_tokens": 1,
                                             "temperature": 0.0, "prompt_logprobs": self.k, "stream": False})
                pl = resp["choices"][0].get("prompt_logprobs")
                if isinstance(pl, list) and len(pl) == len(full):
                    steps = []
                    for pos in range(len(prompt_ids), len(full)):
                        d = pl[pos] or {}
                        top = sorted(([int(k), (v.get("decoded_token") or ""), v.get("logprob")]
                                      for k, v in d.items() if v.get("logprob") is not None), key=lambda x: -x[2])
                        actual = d.get(str(full[pos])) or {}
                        steps.append({"id": full[pos], "tok": actual.get("decoded_token") or "",
                                      "lp": actual.get("logprob"), "top": top, "kind": "logprob"})
                    return steps, "prompt_logprobs"
                self.notes.append("prompt_logprobs came back in an unexpected shape; scoring step by step.")
            except HttpError as e:
                if mode == "prompt_logprobs":
                    raise
                self.notes.append("prompt_logprobs was rejected (%s); scoring step by step." % str(e)[:80])
        steps = []
        for i in range(len(cont_ids)):
            r = self.complete(list(prompt_ids) + list(cont_ids[:i]), 1)
            steps.append(r["steps"][0] if r["steps"] else None)
        return steps, "stepwise"


# ----------------------------------------------------------------- Hugging Face in process

class HFEngine:
    """transformers model in this process, with the same interface as Endpoint.
    complete() decodes greedily with the KV cache (the way generate() runs);
    score() runs one full forward pass over prompt + continuation."""
    flavor = "hf"
    id_prompts = True

    def __init__(self, path, dtype, device, k):
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch, self.k, self.notes = torch, k, []
        self.tok = AutoTokenizer.from_pretrained(path)
        self._anchor = self.tok("x", add_special_tokens=False)["input_ids"][-1:]
        self._anchor_text = self._decode(self._anchor)
        self._texts = {}
        want = {"float32": torch.float32, "float64": torch.float32, "float16": torch.float16,
                "bfloat16": torch.bfloat16}.get(dtype, "auto")
        try:
            model = AutoModelForCausalLM.from_pretrained(path, dtype=want)
        except TypeError:                                   # transformers 4.x
            model = AutoModelForCausalLM.from_pretrained(path, torch_dtype=want)
        if dtype == "float64":
            model = model.double()
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.net, self.device = model.to(device).eval(), device
        eos = getattr(getattr(model, "generation_config", None), "eos_token_id", None)
        if eos is None:
            eos = getattr(model.config, "eos_token_id", None)
        self.eos = set(eos) if isinstance(eos, (list, tuple)) else ({eos} if eos is not None else set())
        self.dtype = str(next(model.parameters()).dtype).replace("torch.", "")
        self.url = "hf:%s" % path
        self.model = self.name = getattr(model.config, "_name_or_path", path)
        self.libs = {"torch": torch.__version__, "transformers": transformers.__version__}

    def _decode(self, ids):
        try:
            return self.tok.decode(ids, clean_up_tokenization_spaces=False)
        except TypeError:
            return self.tok.decode(ids)

    def text(self, tid):
        """Text of one token as it appears inside running text. Decoding a lone SentencePiece id drops its
        leading space, so decode it after an anchor token and cut the anchor off."""
        if tid not in self._texts:
            both = self._decode(self._anchor + [tid])
            self._texts[tid] = both[len(self._anchor_text):] if both.startswith(self._anchor_text) else self._decode([tid])
        return self._texts[tid]

    def tokenize(self, text):
        return [int(x) for x in self.tok(text, add_special_tokens=True)["input_ids"]]

    def chat_ids(self, messages):
        ids = self.tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=True)
        if not isinstance(ids, list):
            ids = ids["input_ids"]
        if ids and isinstance(ids[0], list):
            ids = ids[0]
        return [int(x) for x in ids]

    def _step(self, row, chosen=None):
        torch = self.torch
        lsm = torch.log_softmax(row.double(), dim=-1)
        vals, idx = torch.topk(lsm, self.k)
        if chosen is None:
            chosen = int(idx[0])
        return {"id": chosen, "tok": self.text(chosen), "lp": float(lsm[chosen]), "kind": "logprob",
                "top": [[int(j), self.text(int(j)), float(v)] for v, j in zip(vals, idx)]}

    def complete(self, prompt, n, temperature=0.0, extra=None):
        torch = self.torch
        ids = self.tokenize(prompt) if isinstance(prompt, str) else list(prompt)
        steps = []
        with torch.inference_mode():
            out = self.net(torch.tensor([ids], device=self.device), use_cache=True)
            for _ in range(n):
                st = self._step(out.logits[0, -1])
                if st["id"] in self.eos:        # stop where a server would, without emitting the EOS token
                    break
                steps.append(st)
                out = self.net(torch.tensor([[st["id"]]], device=self.device),
                               past_key_values=out.past_key_values, use_cache=True)
        return {"steps": steps, "text": self._decode([s["id"] for s in steps]), "prompt_tokens": len(ids)}

    def score(self, prompt_ids, cont_ids, mode):
        torch = self.torch
        full = list(prompt_ids) + list(cont_ids)
        with torch.inference_mode():
            logits = self.net(torch.tensor([full], device=self.device), use_cache=False).logits[0]
        return [self._step(logits[len(prompt_ids) - 1 + i], cont_ids[i]) for i in range(len(cont_ids))], "full forward"


# ----------------------------------------------------------------- references

def build_reference(eng, prompts, n, k, chat):
    """Greedy continuation of every prompt on the reference engine, with its top-k at every step.
    For transformers the numbers come from a full forward pass; for an endpoint, from its decode path."""
    traces = []
    for name, text in prompts:
        messages = [{"role": "user", "content": text}] if chat else None
        ids = eng.chat_ids(messages) if chat else eng.tokenize(text)
        if ids is None:
            raise RuntimeError("the reference endpoint cannot tokenize%s; use --ref-hf or --ref-file."
                               % (" chat messages" if chat else " (no /tokenize route)"))
        steps = eng.complete(ids, n)["steps"]
        if not steps:
            continue                    # the model ends the text immediately; nothing to compare
        if any(st["id"] is None for st in steps):
            raise RuntimeError("the reference endpoint did not return token ids with its logprobs.")
        cont, self_lp = [st["id"] for st in steps], None
        if eng.flavor == "hf":
            self_lp = [st["lp"] for st in steps]
            steps, _ = eng.score(ids, cont, "auto")
        elif eng.flavor == "vllm":
            # vLLM returns either ids or text for the top-k; ask again for the text and line the two up
            try:
                txt = eng.complete(ids, n, extra={"return_tokens_as_token_ids": False})["steps"]
                if len(txt) == len(steps):
                    for a, b in zip(steps, txt):
                        if len(a["top"]) == len(b["top"]) and all(abs(x[2] - y[2]) < 1e-9 for x, y in zip(a["top"], b["top"])):
                            for x, y in zip(a["top"], b["top"]):
                                x[1] = y[1]
            except Exception:  # noqa: BLE001 - ids alone are enough for id-capable candidates
                pass
        traces.append({"name": name, "text": text, "messages": messages, "prompt_ids": ids, "cont_ids": cont,
                       "lp": [st["lp"] for st in steps], "top": [st["top"][:k] for st in steps], "self_lp": self_lp})
    if not traces:
        raise RuntimeError("the reference produced no tokens for any prompt.")
    if eng.flavor == "hf":
        return {"source": eng.url, "dtype": eng.dtype, "device": str(eng.device), "model": eng.name, "k": k,
                "traces": traces, "libs": eng.libs}
    return {"source": "endpoint:%s" % eng.url, "dtype": "unknown", "device": "remote", "model": eng.model, "k": k,
            "traces": traces, "libs": {"api": eng.flavor}}


# ----------------------------------------------------------------- analysis

def key_of(e):
    return ("i", e[0]) if e[0] is not None else ("t", e[1])


def lookup(cmap, ref_entry, cand_has_ids):
    """Candidate logprob for a reference token. By id when the candidate returns ids; otherwise by text,
    tolerating the two conventions for a leading space (' the' and 'the')."""
    if cand_has_ids:
        return cmap.get(("i", ref_entry[0]))
    t = ref_entry[1] or ""
    for form in (t, t.lstrip(" "), " " + t):
        v = cmap.get(("t", form))
        if v is not None:
            return v
    return None


def same_token(cand_entry, ref_entry, cand_has_ids):
    if cand_has_ids:
        return cand_entry[0] == ref_entry[0]
    a, b = cand_entry[1] or "", ref_entry[1] or ""
    return a == b or (a.lstrip(" ") == b.lstrip(" ") and a.strip() != "")


def pct(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, int(math.ceil(q * len(s))) - 1)]


def stats(xs):
    if not xs:
        return None
    return {"n": len(xs), "mean": sum(xs) / len(xs), "p50": pct(xs, 0.5), "p99": pct(xs, 0.99), "max": max(xs)}


def logsumexp(xs):
    m = max(xs)
    return m + math.log(sum(math.exp(x - m) for x in xs))


def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def analyze_scores(traces, scored):
    """Compare the candidate's teacher-forced scores with the reference, position by position."""
    rows, deltas, slopes, kls, flips, offsets, spreads = [], [], [], [], [], [], []
    in_ctx, out_ctx = [], []
    agree = n_pos = missing = not_norm = positive = 0
    shift_hits = {-1: 0, 0: 0, 1: 0}
    shift_n = {-1: 0, 0: 0, 1: 0}
    for t, steps in zip(traces, scored):
        if steps is None:
            continue
        ctx = set(t["prompt_ids"])
        for i, st in enumerate(steps):
            ctx_i = ctx | set(t["cont_ids"][:i])
            rtop = t["top"][i]
            if st is None or not st["top"]:
                continue
            has_ids = st["top"][0][0] is not None
            cmap = {key_of(e): e[2] for e in st["top"]}
            if st.get("id") is not None and st.get("lp") is not None:
                cmap.setdefault(("i", st["id"]), st["lp"])
            n_pos += 1
            vals = [e[2] for e in st["top"]]
            if max(vals) > 1e-4:
                positive += 1
            elif logsumexp(vals) > 1e-3:
                not_norm += 1
            rtok = next((e for e in rtop if e[0] == t["cont_ids"][i]), [t["cont_ids"][i], "", None])
            clp = lookup(cmap, rtok, has_ids)
            d = None
            if clp is None:
                missing += 1
            else:
                d = clp - t["lp"][i]
                deltas.append(abs(d))
            r1 = rtop[0]
            margin = r1[2] - rtop[1][2] if len(rtop) > 1 else None
            c1 = st["top"][0]
            same = same_token(c1, r1, has_ids)
            agree += 1 if same else 0
            if not same:
                flips.append({"prompt": t["name"], "pos": i, "ref_token": r1[1], "cand_token": c1[1],
                              "ref_id": r1[0], "cand_id": c1[0], "ref_margin": margin})
            cl = [lookup(cmap, e, has_ids) for e in rtop]      # candidate logprob of each reference top-k token
            if cl[0] is not None:
                for e, v in zip(rtop[1:], cl[1:]):
                    x = r1[2] - e[2]
                    if v is not None and x > 1.0 and v > -9000:
                        slopes.append((cl[0] - v) / x)
            if all(v is not None for v in cl):
                p = [math.exp(e[2]) for e in rtop]
                q = [math.exp(v) for v in cl]
                kl = sum(pi * (e[2] - v) for pi, e, v in zip(p, rtop, cl))
                rp, rq = 1.0 - sum(p), 1.0 - sum(q)
                if rp > 1e-12 and rq > 1e-12:
                    kl += rp * math.log(rp / rq)
                kls.append(max(kl, 0.0))
            common = [v - e[2] for e, v in zip(rtop, cl) if v is not None and v > -9000]
            off = spread = None
            if len(common) >= 3:
                # split the gap into an offset every top-k token shares (the normalizer) and what is left (the shape)
                off = median(common)
                spread = max(abs(x - off) for x in common)
                offsets.append(abs(off))
                spreads.append(spread)
            for e, v in zip(rtop, cl):
                if v is not None and e[0] is not None and v > -9000:
                    (in_ctx if e[0] in ctx_i else out_ctx).append(v - e[2])
            for s in (-1, 0, 1):
                j = i + s
                if 0 <= j < len(steps) and steps[j] is not None and steps[j]["top"]:
                    shift_n[s] += 1
                    shift_hits[s] += 1 if same_token(steps[j]["top"][0], r1, has_ids) else 0
            rows.append({"prompt": t["name"], "pos": i, "tok": _ref_text(t, i), "ref_lp": t["lp"][i], "cand_lp": clp,
                         "delta": d, "offset": off, "spread": spread, "ref_margin": margin, "top1_same": same,
                         "cand_top1": None if same else (c1[1] or "id %s" % c1[0])})
    p99 = pct(deltas, 0.99) or 0.0
    for f in flips:
        m = f["ref_margin"]
        f["near_tie"] = m is not None and m <= max(4.0 * p99, 1e-6)
    return {"n": n_pos, "delta": stats(deltas), "mult_err": (sum(math.exp(x) for x in deltas) / len(deltas)) if deltas else None,
            "agree": agree, "missing": missing, "flips": flips, "kl": stats(kls),
            "offset": stats(offsets), "spread": stats(spreads),
            "slope": median(slopes) if len(slopes) >= 10 else None, "slope_n": len(slopes),
            "slope_mad": median([abs(x - median(slopes)) for x in slopes]) if len(slopes) >= 10 else None,
            "positive": positive, "not_norm": not_norm,
            "ctx_bias": (median(in_ctx) - median(out_ctx)) if len(in_ctx) >= 5 and len(out_ctx) >= 5 else None,
            "shift": {s: (shift_hits[s] / shift_n[s] if shift_n[s] else None) for s in (-1, 0, 1)}, "rows": rows}


def analyze_greedy(traces, gens):
    """Free-running greedy generation from identical ids, plus the candidate's self-consistency inputs."""
    out = {"prompts": 0, "identical": 0, "first_split": None, "decode_delta": [], "not_top1": 0, "steps": 0,
           "shared": []}
    for t, g in zip(traces, gens):
        if g is None:
            continue
        out["prompts"] += 1
        has_ids = bool(g) and g[0]["id"] is not None
        split = None
        for i in range(min(len(g), len(t["cont_ids"]))):
            st = g[i]
            out["steps"] += 1
            if st["top"] and st["lp"] is not None and st["top"][0][2] - st["lp"] > 1e-6 and key_of(st["top"][0]) != key_of([st["id"], st["tok"], 0]):
                out["not_top1"] += 1
            same = same_token([st["id"], st["tok"], 0], [t["cont_ids"][i], _ref_text(t, i), 0], has_ids)
            if not same:
                split = i
                break
            if st["lp"] is not None:
                out["decode_delta"].append(abs(st["lp"] - t["lp"][i]))
        if split is None and len(g) < len(t["cont_ids"]):
            split = len(g)
        out["shared"].append(len(t["cont_ids"]) if split is None else split)
        if split is None:
            out["identical"] += 1
        else:
            rtop = t["top"][split] if split < len(t["top"]) else None
            margin = (rtop[0][2] - rtop[1][2]) if rtop and len(rtop) > 1 else None
            cand = g[split] if split < len(g) else None
            rec = {"prompt": t["name"], "pos": split, "ref_margin": margin,
                   "ref_token": _ref_text(t, split) if split < len(t["cont_ids"]) else None,
                   "cand_token": cand["tok"] if cand else None, "cand_id": cand["id"] if cand else None,
                   "ref_id": t["cont_ids"][split] if split < len(t["cont_ids"]) else None}
            if out["first_split"] is None or split < out["first_split"]["pos"]:
                out["first_split"] = rec
    out["decode_delta"] = stats(out["decode_delta"])
    return out


def _ref_text(t, i):
    rid = t["cont_ids"][i]
    for e in t["top"][i]:
        if e[0] == rid:
            return e[1]
    return ""


def self_consistency(traces, gens, scored, shared):
    ds = []
    for t, g, s, n in zip(traces, gens, scored, shared):
        if g is None or s is None:
            continue
        for i in range(n):
            if s[i] is None or g[i]["lp"] is None:
                continue
            cmap = {key_of(e): e[2] for e in s[i]["top"]}
            if s[i].get("lp") is not None and s[i].get("id") is not None:
                cmap.setdefault(("i", s[i]["id"]), s[i]["lp"])
            v = cmap.get(key_of([g[i]["id"], g[i]["tok"], 0]))
            if v is not None:
                ds.append(abs(g[i]["lp"] - v))
    return stats(ds)


def probe_semantics(ep, ctx):
    """Does the returned top-k change with sampling parameters? -> dict of findings."""
    def top(temperature, extra):
        e = {"seed": 1, "top_p": 1.0}
        e.update(extra)
        try:
            r = ep.complete(ctx, 1, temperature, e)
        except HttpError as err:
            return str(err)[:120]
        return r["steps"][0] if r["steps"] else "no logprobs returned"

    def diff(a, b):
        """Largest logprob change among the top-k tokens; inf when the set itself changed."""
        if isinstance(a, str) or isinstance(b, str):
            return None
        ta = [e for e in a["top"][:ep.k] if e[2] > -9000]
        mb = {key_of(e): e[2] for e in b["top"] if e[2] > -9000}
        common = [e for e in ta if key_of(e) in mb]
        if not ta or len(common) < 0.6 * len(ta) or len(mb) < 0.6 * len(ta):
            return float("inf")
        return max(abs(e[2] - mb[key_of(e)]) for e in common)

    top(1.0, {})            # warm-up: the first request for a prefix can take a different path (prompt cache)
    base = top(1.0, {})
    res = {"error": base if isinstance(base, str) else None, "kind": None if isinstance(base, str) else base.get("kind")}
    if isinstance(base, str):
        return res
    res["temperature"] = diff(base, top(0.5, {}))
    res["top_p"] = diff(base, top(1.0, {"top_p": 0.2}))
    res["penalty"] = diff(base, top(1.0, {"repetition_penalty": 1.5, "repeat_penalty": 1.5}))
    res["greedy"] = diff(base, top(0.0, {}))
    res["repeat"] = diff(base, top(1.0, {}))
    return res


def finite(o):
    """Replace inf/nan so the report is valid JSON for strict parsers (browsers)."""
    if isinstance(o, float) and (o != o or o in (float("inf"), float("-inf"))):
        return None if o != o else ("inf" if o > 0 else "-inf")
    if isinstance(o, dict):
        return {k: finite(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [finite(v) for v in o]
    return o


def show(text, tid):
    if text:
        return "%r" % text if tid is None else "%r (id %s)" % (text, tid)
    return "id %s" % tid


def fmt(x):
    if x is None:
        return "-"
    if x == 0:
        return "0"
    return "%.2e" % x


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=None, help="candidate: OpenAI-compatible base URL ending in /v1")
    ap.add_argument("--model", default=None, help="candidate model id (default: first id from GET /models)")
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    ap.add_argument("--flavor", default="auto", choices=["auto", "vllm", "llamacpp", "sglang", "generic"])
    ap.add_argument("--cand-hf", default=None, metavar="PATH_OR_ID",
                    help="candidate: a Hugging Face model in this process instead of an endpoint")
    ap.add_argument("--cand-dtype", default="auto", choices=["float32", "float64", "bfloat16", "float16", "auto"])
    ap.add_argument("--cand-device", default="auto")
    ap.add_argument("--ref-hf", default=None, metavar="PATH_OR_ID", help="reference: Hugging Face model (needs torch, transformers)")
    ap.add_argument("--ref-dtype", default="float32", choices=["float32", "float64", "bfloat16", "float16", "auto"])
    ap.add_argument("--ref-device", default="auto")
    ap.add_argument("--ref-url", default=None, metavar="URL", help="reference: another OpenAI-compatible base URL")
    ap.add_argument("--ref-model", default=None)
    ap.add_argument("--ref-file", default=None, metavar="FILE", help="reference saved earlier with --save-ref")
    ap.add_argument("--save-ref", default=None, metavar="FILE")
    ap.add_argument("--prompts", default=None, metavar="FILE", help="JSON list of strings (default: 8 built-in prompts)")
    ap.add_argument("--chat", action="store_true", help="wrap each prompt with the model's chat template (--ref-hf only)")
    ap.add_argument("--max-tokens", type=int, default=32, help="continuation length per prompt")
    ap.add_argument("--top-k", type=int, default=5, help="logprobs requested per position (vLLM allows up to 20 by default)")
    ap.add_argument("--score", default="auto", choices=["auto", "prompt_logprobs", "stepwise"])
    ap.add_argument("--max-mult-err", type=float, default=1.05,
                    help="pass when mean exp(|dlogprob|) is at most this (default 1.05)")
    ap.add_argument("--no-probe", action="store_true", help="skip step P")
    ap.add_argument("--no-tokens-check", action="store_true",
                    help="skip step T (use when production also sends token ids, so text tokenization does not matter)")
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--json", dest="json_out", default=None)
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args()

    prompts = PROMPTS
    if args.prompts:
        with open(args.prompts, encoding="utf-8") as f:
            prompts = [("p%d" % (i + 1), s) for i, s in enumerate(json.load(f))]

    # ---- reference
    try:
        if sum(x is not None for x in (args.ref_hf, args.ref_url, args.ref_file)) != 1:
            raise RuntimeError("give exactly one of --ref-hf, --ref-url, --ref-file.")
        if args.ref_file:
            with open(args.ref_file, encoding="utf-8") as f:
                ref = json.load(f)
        elif args.ref_hf:
            ref = build_reference(HFEngine(args.ref_hf, args.ref_dtype, args.ref_device, args.top_k),
                                  prompts, args.max_tokens, args.top_k, args.chat)
        else:
            if args.chat:
                raise RuntimeError("--chat needs --ref-hf (the chat template comes from the reference tokenizer).")
            rep = Endpoint(args.ref_url, args.ref_model, args.api_key, args.timeout, args.top_k).connect()
            ref = build_reference(rep, prompts, args.max_tokens, args.top_k, False)
    except Exception as e:  # noqa: BLE001
        print("error: could not build the reference: %s" % e, file=sys.stderr)
        return 2
    if args.save_ref:
        with open(args.save_ref, "w", encoding="utf-8") as f:
            json.dump(finite(dict(ref, tool="lpcheck", version=VERSION)), f, ensure_ascii=False, allow_nan=False)
        print("reference written to %s (%d prompts, %d tokens each)" % (
            args.save_ref, len(ref["traces"]), max(len(t["cont_ids"]) for t in ref["traces"])))
    traces = ref["traces"]
    if not args.base_url and not args.cand_hf:
        if not args.save_ref:
            print("error: give --base-url or --cand-hf (what to check), or --save-ref.", file=sys.stderr)
            return 2
        return 0

    # ---- candidate
    kk = min(args.top_k, ref.get("k", args.top_k))
    try:
        if args.cand_hf:
            ep = HFEngine(args.cand_hf, args.cand_dtype, args.cand_device, kk)
        else:
            ep = Endpoint(args.base_url, args.model, args.api_key, args.timeout, kk, args.flavor).connect()
    except Exception as e:  # noqa: BLE001
        print("error: could not reach the candidate: %s" % e, file=sys.stderr)
        return 2
    print("lpcheck %s" % VERSION)
    print("reference: %s  dtype=%s  model=%s" % (ref["source"], ref.get("dtype"), ref.get("model")))
    if ep.flavor == "hf":
        print("candidate: %s  dtype=%s  (transformers %s, torch %s, %s)" % (
            ep.url, ep.dtype, ep.libs["transformers"], ep.libs["torch"], ep.device))
    else:
        print("candidate: %s  model=%s  api=%s" % (ep.url, ep.model, ep.flavor))
    print("prompts=%d  tokens per prompt=%d  top-k=%d" % (len(traces), max(len(t["cont_ids"]) for t in traces), ep.k))
    print()
    report = {"tool": "lpcheck", "version": VERSION, "reference": {k: v for k, v in ref.items() if k != "traces"},
              "candidate": {"url": ep.url, "model": getattr(ep, "model", None) or getattr(ep, "name", None),
                            "flavor": ep.flavor, "dtype": getattr(ep, "dtype", None)}}
    reasons = []          # why the two sides are not computing the same thing (exit 3)

    # ---- T: tokens in
    tok = {"checked": 0, "same": 0, "examples": []}
    for t in ([] if args.no_tokens_check else traces):
        ids = ep.chat_ids(t["messages"]) if t.get("messages") else (ep.tokenize(t["text"]) if t.get("text") else None)
        if ids is None:
            continue
        tok["checked"] += 1
        if ids == t["prompt_ids"]:
            tok["same"] += 1
        elif len(tok["examples"]) < 3:
            pos = next((i for i in range(min(len(ids), len(t["prompt_ids"]))) if ids[i] != t["prompt_ids"][i]),
                       min(len(ids), len(t["prompt_ids"])))
            tok["examples"].append({"prompt": t["name"], "pos": pos, "ref": t["prompt_ids"][max(0, pos - 2):pos + 4],
                                    "cand": ids[max(0, pos - 2):pos + 4], "ref_len": len(t["prompt_ids"]), "cand_len": len(ids)})
    report["tokens_in"] = tok
    if args.no_tokens_check:
        print("[T] tokens in      skipped (--no-tokens-check)")
    elif tok["checked"] == 0:
        print("[T] tokens in      not checked (the candidate has no tokenize route, or the reference has no prompt text)")
    else:
        print("[T] tokens in      %d of %d prompts tokenize to the reference ids" % (tok["same"], tok["checked"]))
        for ex in tok["examples"]:
            print("      %-9s first difference at token %d: reference %s (%d tokens), candidate %s (%d tokens)" % (
                ex["prompt"], ex["pos"], ex["ref"], ex["ref_len"], ex["cand"], ex["cand_len"]))
        if tok["same"] < tok["checked"]:
            reasons.append("TOKENS_IN: the candidate turns the same prompt text into different token ids, so a text "
                           "prompt is not the same input on both sides. Steps G and S send token ids, so their numbers "
                           "are not affected by this.")

    # ---- P: what the logprobs mean
    if not args.no_probe and ep.id_prompts and ep.flavor != "hf":
        t0 = traces[0]
        pr = probe_semantics(ep, t0["prompt_ids"] + t0["cont_ids"][:8])
        report["meaning"] = pr
        if pr.get("error"):
            print("[P] meaning        not checked (%s)" % pr["error"])
        else:
            def word(v, tol=1e-6):
                return "not tested" if v is None else ("unchanged" if v <= tol else "CHANGES")
            noise = pr.get("repeat") or 0.0
            tol = max(1e-6, 10 * noise)
            print("[P] meaning        returned logprobs vs temperature: %s | top_p: %s | repetition penalty: %s | greedy vs sampling: %s" % (
                word(pr["temperature"], tol), word(pr["top_p"], tol), word(pr["penalty"], tol), word(pr["greedy"], tol)))
            moved = [n for n in ("temperature", "top_p", "penalty") if pr[n] is not None and pr[n] > tol]
            if pr.get("kind") == "prob":
                print("      the endpoint returns post-sampling probabilities, not model logprobs.")
                reasons.append("MEANING: the endpoint returns probabilities after its sampling chain (llama.cpp "
                               "post_sampling_probs), which are not comparable with a reference log-softmax.")
            elif moved:
                print("      the endpoint returns processed logprobs: they follow %s. A reference computed as "
                      "log_softmax(logits) will differ whenever those are not neutral." % ", ".join(moved))
            else:
                print("      the endpoint returns raw model logprobs: sampling parameters do not change them.")
            report["meaning"]["processed_by"] = moved

    # ---- G: greedy from identical ids
    gens = []
    for t in traces:
        try:
            gens.append(ep.complete(t["prompt_ids"] if ep.id_prompts else t["text"], len(t["cont_ids"]))["steps"] or None)
        except Exception as e:  # noqa: BLE001
            ep.notes.append("generation failed for %s: %s" % (t["name"], str(e)[:100]))
            gens.append(None)
    g = analyze_greedy(traces, gens)
    report["greedy"] = {k: v for k, v in g.items() if k != "shared"}
    if g["prompts"] == 0:
        print("error: the candidate returned no logprobs for any prompt.", file=sys.stderr)
        return 2
    print("[G] greedy         %d of %d prompts give the reference tokens for all %d steps" % (
        g["identical"], g["prompts"], max(len(t["cont_ids"]) for t in traces)))
    if g["first_split"]:
        fs = g["first_split"]
        print("      earliest split: %s, step %d: reference %s, candidate %s; reference top-2 gap %s nats" % (
            fs["prompt"], fs["pos"], show(fs["ref_token"], fs["ref_id"]), show(fs["cand_token"], fs["cand_id"]), fmt(fs["ref_margin"])))
    if g["decode_delta"]:
        print("      while the tokens agree (%d steps): |dlogprob| mean %s  p99 %s  max %s" % (
            g["decode_delta"]["n"], fmt(g["decode_delta"]["mean"]), fmt(g["decode_delta"]["p99"]), fmt(g["decode_delta"]["max"])))
    if g["not_top1"]:
        print("      at %d of %d steps the candidate emitted a token that is not its own top-1 logprob at temperature 0." % (
            g["not_top1"], g["steps"]))
        reasons.append("SAMPLER: at temperature 0 the candidate chose tokens that are not the top-1 of the logprobs it "
                       "returned. Something reshapes the distribution before the choice (a repetition penalty, logit "
                       "bias or min_tokens), often a server default taken from generation_config.json.")

    # ---- S: same tokens on both sides
    scored, method = [], None
    if ep.id_prompts:
        for t in traces:
            try:
                st, method = ep.score(t["prompt_ids"], t["cont_ids"], args.score)
                scored.append(st)
            except Exception as e:  # noqa: BLE001
                ep.notes.append("scoring failed for %s: %s" % (t["name"], str(e)[:100]))
                scored.append(None)
        s = analyze_scores(traces, scored)
    else:
        scored = [None] * len(traces)
        # text prompts only: compare the generated steps up to the first split
        s = analyze_scores(traces, [gg[:m] if gg else None for gg, m in zip(gens, g["shared"])])
    report["same_tokens"] = dict({k: v for k, v in s.items() if k != "rows"}, method=method)
    report["rows"] = s["rows"]
    report["prompts"] = [{"name": t["name"], "text": t.get("text"), "prompt_tokens": len(t["prompt_ids"])} for t in traces]
    report["settings"] = {"max_tokens": max(len(t["cont_ids"]) for t in traces), "top_k": ep.k,
                          "max_mult_err": args.max_mult_err}
    if s["n"] == 0:
        print("error: the candidate returned no logprobs to compare.", file=sys.stderr)
        return 2
    d = s["delta"] or {"n": 0, "mean": None, "p50": None, "p99": None, "max": None}
    near = sum(1 for f in s["flips"] if f["near_tie"])
    far = len(s["flips"]) - near
    print("[S] same tokens    %d positions scored on identical context (%s)" % (s["n"], method or "generated prefix only"))
    print("      |dlogprob| of the reference token   mean %s  p50 %s  p99 %s  max %s" % (
        fmt(d["mean"]), fmt(d["p50"]), fmt(d["p99"]), fmt(d["max"])))
    if s["offset"]:
        print("        offset shared by the top-%d at a position (normalizer)   mean %s  max %s" % (
            ep.k, fmt(s["offset"]["mean"]), fmt(s["offset"]["max"])))
        print("        spread left after removing it (shape)                  mean %s  max %s" % (
            fmt(s["spread"]["mean"]), fmt(s["spread"]["max"])))
    if s["mult_err"] is not None:
        print("      mean exp(|dlogprob|)                %.5f   (tolerance %.3f)" % (s["mult_err"], args.max_mult_err))
    print("      top-1 agreement                     %d of %d (%.1f%%); flips: %d at near-ties, %d with a clear reference margin" % (
        s["agree"], s["n"], 100.0 * s["agree"] / s["n"], near, far))
    if s["kl"]:
        print("      KL(reference || candidate), top-%d + rest   mean %s  max %s nats" % (ep.k, fmt(s["kl"]["mean"]), fmt(s["kl"]["max"])))
    if s["missing"]:
        print("      at %d positions the reference token was not in the candidate's top-%d (not counted above)." % (s["missing"], ep.k))
    for f in [f for f in s["flips"] if not f["near_tie"]][:3]:
        print("      clear-margin flip: %s step %d: reference %s, candidate %s, reference gap %s nats" % (
            f["prompt"], f["pos"], show(f["ref_token"], f["ref_id"]), show(f["cand_token"], f["cand_id"]), fmt(f["ref_margin"])))
    if s["positive"] or s["not_norm"]:
        reasons.append("NOT_LOGPROBS: %d positions have positive values and %d sum to more than 1. The candidate is "
                       "returning logits or unnormalized scores (vLLM --logprobs-mode raw_logits / processed_logits)."
                       % (s["positive"], s["not_norm"]))
    if s["slope"] is not None and abs(s["slope"] - 1.0) > 0.03 and s["slope_mad"] < 0.02 * abs(s["slope"]):
        reasons.append("TEMPERATURE: logprob gaps on the candidate are %.3f times the reference gaps, the signature "
                       "of logits divided by a temperature of about %.2f on one side." % (s["slope"], 1.0 / s["slope"]))
    if s["ctx_bias"] is not None and s["ctx_bias"] < -0.05 and (d["p50"] or 0) < abs(s["ctx_bias"]) and not s["positive"]:
        reasons.append("PENALTY: tokens that already occur in the context are %.3f nats less likely on the candidate "
                       "than other tokens, the signature of a repetition or presence penalty inside the returned logprobs."
                       % -s["ctx_bias"])
    sh = s["shift"]
    if method == "prompt_logprobs" and sh[0] is not None and sh[0] < 0.6:
        best = max((v, k) for k, v in sh.items() if v is not None and k != 0) if any(v is not None for k, v in sh.items() if k != 0) else None
        if best and best[0] > 0.9:
            reasons.append("POSITION: the candidate's prompt logprobs line up with the reference when shifted by %+d "
                           "position; the per-token values are attached to the wrong token." % best[1])

    # ---- C: the candidate against itself
    sc = self_consistency(traces, gens, scored, g["shared"]) if ep.id_prompts else None
    report["self"] = sc
    if sc:
        print("[C] self           candidate decode path vs its %s path, same tokens (%d steps): mean %s  max %s" % (
            method, sc["n"], fmt(sc["mean"]), fmt(sc["max"])))
    ref_self = [abs(a - b) for t in traces if t.get("self_lp") for a, b in zip(t["self_lp"], t["lp"])]
    if ref_self:
        report["reference_self"] = stats(ref_self)
        print("                   reference KV-cache decode vs full forward, same tokens (%d steps): mean %s  max %s" % (
            len(ref_self), fmt(sum(ref_self) / len(ref_self)), fmt(max(ref_self))))

    # ---- verdict
    print()
    if reasons:
        code, exit_code = "NOT_THE_SAME_COMPUTATION", 3
        text = "The two sides differ before numerics come into it:"
    elif not d["n"]:
        code, exit_code = "NUMERIC_GAP", 1
        text = ("The reference token was not among the candidate's top-%d at any scored position, so no logprob could "
                "be compared. The two sides are not running the same model on the same tokens." % ep.k)
    elif d["max"] == 0 and not s["flips"] and g["identical"] == g["prompts"] and not (g["decode_delta"] or {}).get("max"):
        code, exit_code = "IDENTICAL", 0
        text = "Every compared logprob is bit-for-bit the reference value as printed by both sides."
    elif s["mult_err"] <= args.max_mult_err and far == 0:
        code, exit_code = "WITHIN_TOLERANCE", 0
        text = ("Same tokens in, same meaning, and the remaining gap is small: mean exp(|dlogprob|) %.5f, largest "
                "single gap %s nats on the scoring path and %s on the decode path, and every top-1 flip sits at a "
                "near-tie." % (s["mult_err"], fmt(d["max"]), fmt((g["decode_delta"] or {}).get("max"))))
    else:
        code, exit_code = "NUMERIC_GAP", 1
        why = []
        if s["mult_err"] > args.max_mult_err:
            why.append("mean exp(|dlogprob|) is %.4f, above %.3f" % (s["mult_err"], args.max_mult_err))
        if far:
            why.append("%d top-1 flips happen where the reference separates its top two tokens by more than the noise seen elsewhere" % far)
        text = ("On identical token ids and with comparable logprob semantics, the candidate still disagrees: %s. "
                "Rounding at the declared precision does not usually do this; check the weights (quantization, "
                "revision, LoRA), the dtype on both sides, and the engine version." % "; ".join(why))
    print("VERDICT: %s" % code)
    print(text)
    for r in reasons:
        print("  - " + r)
    if reasons and d["n"] and s["mult_err"] is not None:
        ok = s["mult_err"] <= args.max_mult_err and far == 0
        print("With token ids pinned, the numbers themselves are %s: mean exp(|dlogprob|) %.5f, largest gap %s nats." % (
            "within tolerance" if ok else "beyond tolerance", s["mult_err"], fmt(d["max"])))
    if d["n"]:
        print("Scale (mean |dlogprob|, one 15M model on CPU against float64, see the page): float32 1.5e-06, "
              "fp16 1.8e-03, bf16 1.6e-02, Q8_0 2.8e-02, Q4_0 2.3e-01. Here: %s." % fmt(d["mean"]))
    moved = (report.get("meaning") or {}).get("processed_by")
    if moved:
        print("Note: this endpoint returns processed logprobs (they follow %s). The comparison above ran at "
              "temperature 0 with neutral settings; at other settings apply the same processing to the reference." % ", ".join(moved))
    if sc and d["max"] and sc["max"] and code in ("WITHIN_TOLERANCE", "NUMERIC_GAP"):
        ratio = d["max"] / sc["max"]
        print("For scale: the largest gap to the reference is %.1f times the candidate's own decode-vs-%s gap." % (ratio, method))
    for n in ep.notes:
        print("note: " + n)
    report["verdict"] = code
    report["reasons"] = reasons
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(finite(report), f, ensure_ascii=False, indent=1, allow_nan=False)
        print("\nreport written to %s" % args.json_out)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
