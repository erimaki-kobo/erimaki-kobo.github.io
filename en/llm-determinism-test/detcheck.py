#!/usr/bin/env python3
"""detcheck.py - black-box determinism test for OpenAI-compatible LLM endpoints
(vLLM, SGLang, llama.cpp, Ollama, hosted APIs).

It sends the same prompt at temperature 0 under different conditions and
compares the generated tokens and their logprobs:

  load   same prompt, increasing concurrency          (batch size)
  mixed  same prompt among different-length traffic   (batch composition)
  cache  a fresh prompt sent cold, then again warm    (prefix cache)
  ab     the same prompts on two endpoints            (--against URL: spec
         decoding on/off, TP degree, quantization, version upgrade)

Standard library only. Python 3.8+.

    python detcheck.py --base-url http://localhost:8000/v1
    python detcheck.py --base-url http://localhost:8000/v1 --against http://localhost:8001/v1
    python detcheck.py --base-url http://localhost:8000/v1 --runs 64 \
        --concurrency 1,8,32,64 --max-tokens 500 --json report.json

Exit code: 0 no divergence observed, 1 tokens diverged, 3 only logprobs
drifted, 2 could not run.
"""
import argparse
import collections
import concurrent.futures
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

VERSION = "1.0.0"
DEFAULT_PROMPT = "Tell me about Richard Feynman"
PASSAGE = (
    "The harbour town of Velmar keeps a ledger of every ship that has entered its bay since the "
    "lighthouse was built. Each entry records the name of the vessel, the colour of its sails, the "
    "cargo it declared and the weather on the day it arrived. Clerks copy the ledger by hand every "
    "ten years, and the old copies are stored in a dry cellar under the customs house. Visitors may "
    "read them on market days if they bring their own lamp. "
)
FILLERS = [
    "Hi",
    "List three prime numbers.",
    "Explain in two sentences why the sky is blue.",
    "Write a short product description for a steel water bottle aimed at hikers who travel light.",
    PASSAGE + "Who may read the old copies, and when?",
    PASSAGE * 3 + "Summarize the passage in one sentence.",
]
AB_PROMPTS = [
    DEFAULT_PROMPT,
    "Hi",
    "serving " * 48,
    PASSAGE * 2 + "Summarize the passage in three sentences.",
]


class Client:
    def __init__(self, base, model, api_key, args, use_lp):
        self.base, self.model, self.key, self.args, self.use_lp = base.rstrip("/"), model, api_key, args, use_lp
        self.url = self.base + ("/completions" if args.completions else "/chat/completions")

    def _http(self, url, payload):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="GET" if data is None else "POST")
        req.add_header("Content-Type", "application/json")
        if self.key:
            req.add_header("Authorization", "Bearer " + self.key)
        with urllib.request.urlopen(req, timeout=self.args.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def first_model(self):
        return self._http(self.base + "/models", None)["data"][0]["id"]

    def payload(self, prompt):
        a = self.args
        if a.completions:
            p = {"model": self.model, "prompt": prompt}
            if self.use_lp:
                p["logprobs"] = 2
        else:
            p = {"model": self.model, "messages": [{"role": "user", "content": prompt}]}
            if self.use_lp:
                p["logprobs"] = True
                p["top_logprobs"] = 2
        p["temperature"] = 0
        p["max_tokens"] = a.max_tokens
        if a.seed is not None:
            p["seed"] = a.seed
        return p

    def send(self, prompt):
        try:
            return parse_response(self._http(self.url, self.payload(prompt)), self.args.completions)
        except urllib.error.HTTPError as e:
            return {"error": "HTTP %d: %s" % (e.code, e.read().decode("utf-8", "replace")[:300])}
        except Exception as e:  # noqa: BLE001 - report any transport/format problem
            return {"error": "%s: %s" % (type(e).__name__, e)}


def parse_response(resp, completions):
    """-> dict(text, tokens, lps, top). tokens/lps/top are None without logprobs.
    lps[i] is the logprob of the chosen token; top[i] is [(token, logprob), ...]."""
    ch = resp["choices"][0]
    out = {"text": "", "tokens": None, "lps": None, "top": None,
           "finish": ch.get("finish_reason"), "fingerprint": resp.get("system_fingerprint")}
    lp = ch.get("logprobs")
    if completions:
        out["text"] = ch.get("text") or ""
        if lp and lp.get("tokens"):
            out["tokens"] = list(lp["tokens"])
            out["lps"] = list(lp.get("token_logprobs") or [])
            out["top"] = [sorted((d or {}).items(), key=lambda kv: -kv[1]) for d in (lp.get("top_logprobs") or [])]
    else:
        out["text"] = (ch.get("message") or {}).get("content") or ""
        if lp and lp.get("content"):
            out["tokens"] = [t.get("token", "") for t in lp["content"]]
            out["lps"] = [t.get("logprob") for t in lp["content"]]
            out["top"] = [sorted(((a.get("token", ""), a.get("logprob", float("nan")))
                                  for a in (t.get("top_logprobs") or [])), key=lambda kv: -kv[1])
                          for t in lp["content"]]
    return out


def key_of(run):
    return json.dumps(run["tokens"], ensure_ascii=False) if run["tokens"] is not None else run["text"]


def compare(ref, other):
    """-> (divergence position or None, unit, max |logprob delta| over the shared prefix or None)."""
    if ref["tokens"] is not None and other["tokens"] is not None:
        a, b, unit = ref["tokens"], other["tokens"], "token"
    else:
        a, b, unit = ref["text"], other["text"], "char"
    n = min(len(a), len(b))
    pos = next((i for i in range(n) if a[i] != b[i]), None)
    if pos is None and len(a) != len(b):
        pos = n
    delta = None
    if unit == "token" and ref["lps"] and other["lps"]:
        m = min(n if pos is None else pos, len(ref["lps"]), len(other["lps"]))
        ds = [abs(ref["lps"][i] - other["lps"][i]) for i in range(m)
              if ref["lps"][i] is not None and other["lps"][i] is not None]
        delta = max(ds) if ds else 0.0
    return pos, unit, delta


def example(ref, other, pos, unit):
    ex = {"position": pos, "unit": unit}
    if unit == "token":
        ex["prefix"] = "".join(ref["tokens"][max(0, pos - 12):pos])
        ex["ref_next"] = "".join(ref["tokens"][pos:pos + 8])
        ex["other_next"] = "".join(other["tokens"][pos:pos + 8])
        top = ref["top"][pos] if ref["top"] and pos < len(ref["top"]) else []
        if len(top) >= 2:
            ex["ref_top2"] = [list(top[0]), list(top[1])]
            ex["logprob_gap"] = top[0][1] - top[1][1]
    else:
        ex["prefix"] = ref["text"][max(0, pos - 60):pos]
        ex["ref_next"] = ref["text"][pos:pos + 40]
        ex["other_next"] = other["text"][pos:pos + 40]
    return ex


def summarize(runs, ref):
    """Compare every successful run with ref."""
    ok = [r for r in runs if "error" not in r]
    counts = collections.Counter(key_of(r) for r in ok)
    s = {"ok": len(ok), "errors": len(runs) - len(ok), "unique": len(counts), "differ": 0,
         "shared_prefix": None, "unit": None, "max_logprob_delta": None, "example": None}
    if ref is None:
        return s
    for r in ok:
        pos, unit, delta = compare(ref, r)
        if delta is not None and (s["max_logprob_delta"] is None or delta > s["max_logprob_delta"]):
            s["max_logprob_delta"] = delta
        if pos is None:
            continue
        s["differ"] += 1
        if s["shared_prefix"] is None or pos < s["shared_prefix"]:
            s["shared_prefix"], s["unit"], s["example"] = pos, unit, example(ref, r, pos, unit)
    return s


def modal(runs):
    ok = [r for r in runs if "error" not in r]
    if not ok:
        return None
    best = collections.Counter(key_of(r) for r in ok).most_common(1)[0][0]
    return next(r for r in ok if key_of(r) == best)


def pool_run(client, prompts, workers):
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(client.send, prompts))


def state(s, tol):
    """'tokens' if any output diverged, 'logprobs' if only logprobs moved, else 'same'."""
    if s["differ"] or s["unique"] > 1:
        return "tokens"
    if s["max_logprob_delta"] is not None and s["max_logprob_delta"] > tol:
        return "logprobs"
    return "same"


def fmt_delta(d):
    return "-" if d is None else ("0" if d == 0 else "%.3e" % d)


def row(label, s, tol):
    shared = "-" if s["shared_prefix"] is None else "%d %ss" % (s["shared_prefix"], s["unit"])
    mark = {"tokens": "TOKENS DIFFER", "logprobs": "logprobs differ", "same": "identical"}[state(s, tol)]
    print("%-22s %4d %4d %7d %7d %14s %12s  %s" % (
        label, s["ok"], s["errors"], s["unique"], s["differ"], shared, fmt_delta(s["max_logprob_delta"]), mark))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://localhost:8000/v1", help="OpenAI-compatible base URL ending in /v1")
    ap.add_argument("--model", default=None, help="model id (default: first id from GET /models)")
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""), help="bearer token (default: $OPENAI_API_KEY)")
    ap.add_argument("--against", default=None, metavar="URL", help="second base URL for the A/B probe")
    ap.add_argument("--against-model", default=None, help="model id on the second endpoint (default: auto)")
    ap.add_argument("--probes", default="load,mixed,cache", help="comma-separated subset of load,mixed,cache")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--runs", type=int, default=32, help="identical requests per concurrency level")
    ap.add_argument("--concurrency", default="1,8,32", help="comma-separated levels; the first is the baseline")
    ap.add_argument("--cache-trials", type=int, default=8, help="cold/warm pairs for the cache probe")
    ap.add_argument("--max-tokens", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0, help="seed sent with every request")
    ap.add_argument("--no-seed", action="store_true", help="do not send a seed")
    ap.add_argument("--no-logprobs", action="store_true", help="do not request logprobs (text-only comparison)")
    ap.add_argument("--logprob-tol", type=float, default=0.0, help="logprob differences up to this value count as identical")
    ap.add_argument("--completions", action="store_true", help="use /completions instead of /chat/completions")
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--json", dest="json_out", default=None, help="write the full report to this file")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args()
    if args.no_seed:
        args.seed = None
    try:
        order = [int(x) for x in args.concurrency.split(",") if x.strip()]
        probes = [p.strip() for p in args.probes.split(",") if p.strip()]
        assert order and all(c >= 1 for c in order) and args.runs >= 1
        assert all(p in ("load", "mixed", "cache") for p in probes)
    except Exception:  # noqa: BLE001
        print("error: check --concurrency (positive integers), --runs (>= 1) and --probes", file=sys.stderr)
        return 2
    tol = args.logprob_tol

    def connect(base, model):
        c = Client(base, model, args.api_key, args, not args.no_logprobs)
        if c.model is None:
            c.model = c.first_model()
        warm = c.send(args.prompt)
        if "error" in warm and c.use_lp:
            c.use_lp = False
            retry = c.send(args.prompt)
            if "error" not in retry:
                print("note: %s rejected logprobs (%s); comparing text only." % (base, warm["error"][:100]))
                warm = retry
        if "error" in warm:
            raise RuntimeError("warm-up request to %s failed: %s" % (base, warm["error"]))
        return c, warm

    try:
        A, warm = connect(args.base_url, args.model)
        B = connect(args.against, args.against_model)[0] if args.against else None
    except Exception as e:  # noqa: BLE001
        print("error: %s" % e, file=sys.stderr)
        return 2

    print("detcheck %s  endpoint=%s  model=%s" % (VERSION, A.url, A.model))
    print("max_tokens=%d  seed=%s  compare=%s" % (
        args.max_tokens, args.seed, "tokens+logprobs" if warm["lps"] else ("tokens" if warm["tokens"] else "text")))
    print()
    print("%-22s %4s %4s %7s %7s %14s %12s" % ("probe", "ok", "err", "unique", "differ", "shared prefix", "max |dlogp|"))

    results, raw_text, errors, fps = {}, {}, [], set()

    def note(runs):
        for r in runs:
            if "error" in r:
                errors.append(r["error"])
            elif r.get("fingerprint"):
                fps.add(r["fingerprint"])

    # baseline + load: same prompt, rising concurrency
    base_runs = pool_run(A, [args.prompt] * args.runs, order[0])
    note(base_runs)
    ref = modal(base_runs)
    if ref is None:
        print("error: every baseline request failed: %s" % errors[0], file=sys.stderr)
        return 2
    results["baseline c=%d" % order[0]] = summarize(base_runs, ref)
    raw_text["baseline"] = [r.get("text") for r in base_runs]
    row("baseline c=%d" % order[0], results["baseline c=%d" % order[0]], tol)
    if "load" in probes:
        for c in order[1:]:
            runs = pool_run(A, [args.prompt] * args.runs, c)
            note(runs)
            results["load c=%d" % c] = summarize(runs, ref)
            raw_text["load c=%d" % c] = [r.get("text") for r in runs]
            row("load c=%d" % c, results["load c=%d" % c], tol)

    # mixed: the same prompt surrounded by traffic of other lengths and contents
    if "mixed" in probes:
        c = max(max(order), 4)
        jobs = [args.prompt] * args.runs + [FILLERS[i % len(FILLERS)] for i in range(3 * args.runs)]
        random.Random(0).shuffle(jobs)
        runs = pool_run(A, jobs, c)
        targets = [r for p, r in zip(jobs, runs) if p == args.prompt]
        note(runs)
        results["mixed c=%d" % c] = summarize(targets, ref)
        raw_text["mixed c=%d" % c] = [r.get("text") for r in targets]
        row("mixed c=%d" % c, results["mixed c=%d" % c], tol)

    # cache: a never-seen prompt sent cold, then twice more warm, one request at a time
    if "cache" in probes:
        agg = {"ok": 0, "errors": 0, "unique": 1, "differ": 0, "shared_prefix": None, "unit": None,
               "max_logprob_delta": None, "example": None}
        for _ in range(args.cache_trials):
            prompt = "Session %s.\n%s\nSummarize the passage above in three sentences." % (os.urandom(6).hex(), PASSAGE * 3)
            cold = A.send(prompt)
            warms = [A.send(prompt), A.send(prompt)]
            note([cold] + warms)
            if "error" in cold:
                agg["errors"] += 1
                continue
            s = summarize(warms, cold)
            agg["ok"] += s["ok"]
            agg["errors"] += s["errors"]
            agg["differ"] += s["differ"]
            if s["differ"]:
                agg["unique"] = 2
            if s["max_logprob_delta"] is not None:
                agg["max_logprob_delta"] = max(agg["max_logprob_delta"] or 0.0, s["max_logprob_delta"])
            if s["shared_prefix"] is not None and (agg["shared_prefix"] is None or s["shared_prefix"] < agg["shared_prefix"]):
                agg["shared_prefix"], agg["unit"], agg["example"] = s["shared_prefix"], s["unit"], s["example"]
        results["cache warm-vs-cold"] = agg
        row("cache warm-vs-cold", agg, tol)

    # ab: the same prompts on a second endpoint
    ab = None
    if B is not None:
        ab = {"ok": 0, "errors": 0, "unique": 1, "differ": 0, "shared_prefix": None, "unit": None,
              "max_logprob_delta": None, "example": None, "a_self_differ": 0}
        for prompt in AB_PROMPTS:
            ra = [A.send(prompt) for _ in range(2)]
            rb = [B.send(prompt) for _ in range(2)]
            note(ra + rb)
            if "error" in ra[0]:
                ab["errors"] += 1
                continue
            ab["a_self_differ"] += summarize(ra[1:], ra[0])["differ"]
            s = summarize(rb, ra[0])
            ab["ok"] += s["ok"]
            ab["errors"] += s["errors"]
            ab["differ"] += s["differ"]
            if s["differ"]:
                ab["unique"] = 2
            if s["max_logprob_delta"] is not None:
                ab["max_logprob_delta"] = max(ab["max_logprob_delta"] or 0.0, s["max_logprob_delta"])
            if s["shared_prefix"] is not None and (ab["shared_prefix"] is None or s["shared_prefix"] < ab["shared_prefix"]):
                ab["shared_prefix"], ab["unit"], ab["example"] = s["shared_prefix"], s["unit"], s["example"]
        results["ab endpoint B vs A"] = ab
        row("ab endpoint B vs A", ab, tol)

    # verdict
    base_key = "baseline c=%d" % order[0]
    states = {k: state(s, tol) for k, s in results.items()}
    own = {k: v for k, v in states.items() if not k.startswith("ab ")}
    tok = [k for k, v in own.items() if v == "tokens"]
    drift = [k for k, v in own.items() if v == "logprobs"]
    if states[base_key] == "tokens":
        code, text = "NONDETERMINISTIC_AT_BASELINE", (
            "Outputs differ even for identical sequential requests. The endpoint is shared with other "
            "traffic, requests reach different replicas or hardware, or decoding is not greedy at temperature 0.")
    elif tok:
        code, text = "TOKEN_DIVERGENCE", (
            "Generated tokens changed in: %s. The output of a request depends on the conditions it is served under." % ", ".join(tok))
    elif drift:
        code, text = "LOGPROB_DRIFT", (
            "Tokens were identical but logprobs moved in: %s. The numerics are not invariant; a token flip "
            "needs only a near-tie, so longer outputs or other prompts can diverge." % ", ".join(drift))
    else:
        total = sum(s["ok"] for k, s in results.items() if not k.startswith("ab "))
        code, text = "NO_DIVERGENCE_OBSERVED", (
            "All %d completions matched the baseline%s. This is evidence, not proof: use more runs, longer "
            "outputs and your real peak concurrency before relying on it." % (
                total, " in tokens and logprobs" if warm["lps"] else ""))
    print()
    print("VERDICT: %s" % code)
    print(text)
    if ab is not None:
        st = states["ab endpoint B vs A"]
        print("A/B: %s" % {"same": "endpoint B matched endpoint A on every prompt.",
                           "logprobs": "same tokens on both endpoints, but logprobs differ (max %s)." % fmt_delta(ab["max_logprob_delta"]),
                           "tokens": "endpoint B produced different tokens on %d of %d comparisons." % (ab["differ"], ab["ok"])}[st])
        if ab["a_self_differ"]:
            print("     note: endpoint A also disagreed with itself on %d repeat(s); fix that first." % ab["a_self_differ"])

    exs = [(k, s["example"]) for k, s in results.items() if s["example"]]
    if exs:
        k, ex = min(exs, key=lambda ke: ke[1]["position"])
        print()
        print("Earliest divergence (%s): the first %d %ss are identical, then:" % (k, ex["position"], ex["unit"]))
        print("  ...%r" % ex["prefix"])
        print("  reference: %r" % ex["ref_next"])
        print("  other:     %r" % ex["other_next"])
        if "logprob_gap" in ex:
            print("  reference top-2 there: %r (%.4f) vs %r (%.4f); gap %.4f nats" % (
                ex["ref_top2"][0][0], ex["ref_top2"][0][1], ex["ref_top2"][1][0], ex["ref_top2"][1][1], ex["logprob_gap"]))
    if len(fps) > 1:
        print("\nnote: %d different system_fingerprint values seen - the backend changed between requests." % len(fps))
    if errors:
        print("\nnote: %d request(s) failed, e.g. %s" % (len(errors), errors[0][:160]))
    if ref.get("finish") != "length":
        print("\nnote: the baseline output ended before max_tokens. Longer outputs give divergence more chances to show.")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({"tool": "detcheck", "version": VERSION, "endpoint": A.url, "model": A.model,
                       "against": B.url if B else None, "prompt": args.prompt, "max_tokens": args.max_tokens,
                       "seed": args.seed, "runs_per_level": args.runs, "verdict": code, "probes": results,
                       "states": states, "reference_text": ref["text"], "outputs": raw_text},
                      f, ensure_ascii=False, indent=2)
        print("\nreport written to %s" % args.json_out)

    ab_tokens = ab is not None and states["ab endpoint B vs A"] == "tokens"
    if code in ("NONDETERMINISTIC_AT_BASELINE", "TOKEN_DIVERGENCE") or ab_tokens:
        return 1
    if code == "LOGPROB_DRIFT" or (ab is not None and states["ab endpoint B vs A"] == "logprobs"):
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
