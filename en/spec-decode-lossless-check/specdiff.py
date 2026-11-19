#!/usr/bin/env python3
"""specdiff.py - is speculative decoding lossless on *your* endpoint?

Sends the same prompts to two OpenAI-compatible endpoints, one serving the
target model without speculative decoding (--base) and one with it (--spec),
and answers three questions:

  1. greedy   Do temperature-0 outputs match token for token? Where a pair
              diverges, was the baseline's choice a near-tie (a numerics flip:
              the batched verify pass rounds differently from one-token decode)
              or a clear winner (a correctness bug in the speculative path)?
  2. sample   At temperature > 0, do both endpoints sample the same answer
              distribution? (chi-square two-sample test + total variation)
  3. engaged  Did speculation actually run? Draft / accepted token counts are
              read from vLLM (--per-request-spec-decode-metrics), SGLang
              (return_spec_tokens_details) and llama-server (timings). A test
              in which no draft token was accepted proves nothing.

Works with vLLM, SGLang, llama-server and anything else that speaks the
OpenAI API. Standard library only, Python 3.8+. License: MIT.

    python specdiff.py --base http://localhost:8000/v1 --spec http://localhost:8001/v1
    python specdiff.py --base ... --spec ... --prompts my_prompts.jsonl --max-tokens 512 --json out.json
    python specdiff.py --base ... --spec ... --skip-sample      # greedy only

Exit codes: 0 no problem found, 1 suspected bug (large-gap divergence or a
distribution shift), 3 only near-tie divergences, 4 inconclusive (baseline not
deterministic, or speculation never engaged), 2 could not run.
"""
import argparse
import collections
import concurrent.futures
import json
import math
import os
import sys
import urllib.error
import urllib.request

VERSION = "1.0.0"

# Greedy prompts: long, ordinary outputs with many decision points. Two of them
# repeat earlier text so that n-gram / prompt-lookup drafters get accepted.
PASSAGE = (
    "The harbour town of Velmar keeps a ledger of every ship that has entered its bay since the "
    "lighthouse was built. Each entry records the name of the vessel, the colour of its sails, the "
    "cargo it declared and the weather on the day it arrived. Clerks copy the ledger by hand every "
    "ten years, and the old copies are stored in a dry cellar under the customs house."
)
GREEDY_PROMPTS = [
    "Explain how a CPU branch predictor works, in about 300 words.",
    "What happens when a browser requests https://example.com? Five bullet points.",
    "Write a Python function that parses an ISO 8601 date string without using datetime, with comments.",
    "Copy the following paragraph exactly, then summarize it in two sentences.\n\n" + PASSAGE,
    "Here is a list: alpha, bravo, charlie, delta, echo, foxtrot, golf, hotel, india, juliett. "
    "Write it out three times, numbering each item, then say which word is longest.",
    "Solve step by step: a train leaves at 14:35 and travels 312 km at 78 km/h. When does it arrive?",
    "Describe the water cycle to a ten-year-old.",
    "List ten common Linux commands and what each one does.",
]
# Sampling prompts: short answers with a spread-out distribution. The answer
# is several tokens long so that tokens after the first one go through the
# speculative verify step (the first token comes from prefill on both sides).
SAMPLE_PROMPTS = [
    "Repeat this list once, then pick one item at random and write only that item on the last line: "
    "red apple, green pear, yellow banana, purple grape, orange tangerine.",
    "Write a random date in 2025 in the form YYYY-MM-DD. Output only the date.",
]


class Client:
    def __init__(self, base, model, api_key, timeout, completions):
        self.base, self.model, self.key = base.rstrip("/"), model, api_key
        self.timeout, self.completions = timeout, completions
        self.url = self.base + ("/completions" if completions else "/chat/completions")
        self.use_lp = True
        self.extra = {}

    def _http(self, url, payload):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="GET" if data is None else "POST")
        req.add_header("Content-Type", "application/json")
        if self.key:
            req.add_header("Authorization", "Bearer " + self.key)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def first_model(self):
        return self._http(self.base + "/models", None)["data"][0]["id"]

    def payload(self, prompt, temperature, max_tokens, top, seed):
        if self.completions:
            p = {"model": self.model, "prompt": prompt}
            if self.use_lp:
                p["logprobs"] = top
        else:
            p = {"model": self.model, "messages": [{"role": "user", "content": prompt}]}
            if self.use_lp:
                p["logprobs"] = True
                p["top_logprobs"] = top
        p.update({"temperature": temperature, "max_tokens": max_tokens, "top_p": 1})
        if temperature == 0:
            p["top_k"] = 1  # llama-server and SGLang honour it; vLLM ignores it at temperature 0
        if seed is not None:
            p["seed"] = seed
        # ask every engine for its speculative statistics; unknown fields are ignored by all three
        p["return_spec_tokens_details"] = True
        p.update(self.extra)
        return p

    def send(self, prompt, temperature=0.0, max_tokens=256, top=5, seed=None):
        try:
            raw = self._http(self.url, self.payload(prompt, temperature, max_tokens, top, seed))
            return parse_response(raw, self.completions)
        except urllib.error.HTTPError as e:
            return {"error": "HTTP %d: %s" % (e.code, e.read().decode("utf-8", "replace")[:300])}
        except Exception as e:  # noqa: BLE001 - report any transport/format problem
            return {"error": "%s: %s" % (type(e).__name__, e)}


def spec_stats(resp):
    """-> (draft_tokens, accepted_tokens) or None, from whichever engine answered."""
    m = (resp.get("metrics") or {}).get("speculative_decoding")  # vLLM, --per-request-spec-decode-metrics
    if isinstance(m, dict) and m.get("num_draft_tokens") is not None:
        return int(m["num_draft_tokens"]), int(m.get("num_accepted_draft_tokens") or 0)
    d = (resp.get("sglext") or {}).get("spec_tokens_details")  # SGLang, return_spec_tokens_details
    if isinstance(d, list):
        d = d[0] if d else None
    if isinstance(d, dict) and d.get("spec_num_proposed_drafts") is not None:
        return int(d["spec_num_proposed_drafts"]), int(d.get("spec_num_correct_drafts") or 0)
    t = resp.get("timings") or {}  # llama-server: keys only present when drafts were made
    if "draft_n" in t:
        return int(t["draft_n"]), int(t.get("draft_n_accepted") or 0)
    if t:
        return 0, 0
    return None


def _key(t):
    """Comparison key for a token: its id when the server sends one (llama-server does),
    so that two different byte tokens that both print as U+FFFD are not taken as equal."""
    return "#%d" % t["id"] if isinstance(t.get("id"), int) else t.get("token", "")


def parse_response(resp, completions):
    """-> dict(text, tokens, disp, lps, top, finish, spec). tokens are comparison keys,
    disp the printable pieces, lps[i] the chosen token's logprob, top[i] a list of
    (key, logprob) sorted best first, top_disp the same with printable pieces."""
    ch = resp["choices"][0]
    out = {"text": "", "tokens": None, "disp": None, "lps": None, "top": None, "top_disp": None,
           "finish": ch.get("finish_reason"), "spec": spec_stats(resp)}
    lp = ch.get("logprobs")
    out["text"] = (ch.get("text") or "") if completions else ((ch.get("message") or {}).get("content") or "")
    if lp and lp.get("content"):  # chat format; llama-server also uses it on /v1/completions
        c = lp["content"]
        out["tokens"] = [_key(t) for t in c]
        out["disp"] = [t.get("token", "") for t in c]
        out["lps"] = [t.get("logprob") for t in c]
        tops = [sorted((a for a in (t.get("top_logprobs") or [])), key=lambda a: -a.get("logprob", float("-inf"))) for t in c]
        out["top"] = [[(_key(a), a.get("logprob", float("nan"))) for a in tp] for tp in tops]
        out["top_disp"] = [[(a.get("token", ""), a.get("logprob", float("nan"))) for a in tp] for tp in tops]
    elif lp and lp.get("tokens"):  # legacy completions format
        out["tokens"] = list(lp["tokens"])
        out["disp"] = out["tokens"]
        out["lps"] = list(lp.get("token_logprobs") or [])
        out["top"] = [sorted((d or {}).items(), key=lambda kv: -kv[1]) for d in (lp.get("top_logprobs") or [])]
        out["top_disp"] = out["top"]
    return out


def logprobs_broken(run):
    """True when an endpoint returns logprobs that cannot be real: every value
    exactly 0.0 with empty top lists after the first token (llama.cpp #27972)."""
    if not run.get("lps") or len(run["lps"]) < 4:
        return False
    rest_lp = run["lps"][1:]
    rest_top = (run.get("top") or [])[1:]
    return all(v == 0.0 for v in rest_lp) and all(not t for t in rest_top)


def first_divergence(a, b):
    """Index of the first differing token (or char when tokens are missing), None if equal."""
    if a["tokens"] is not None and b["tokens"] is not None:
        x, y, unit = a["tokens"], b["tokens"], "token"
    else:
        x, y, unit = a["text"], b["text"], "char"
    n = min(len(x), len(y))
    pos = next((i for i in range(n) if x[i] != y[i]), None)
    if pos is None and len(x) != len(y):
        # one side stopped earlier; only a divergence if both were cut by max_tokens or text differs
        pos = n
    return pos, unit


def shared_noise(a, b, upto):
    """Max |logprob_a - logprob_b| over the shared prefix (same token at the same position)."""
    if not a["lps"] or not b["lps"]:
        return None
    m = min(upto, len(a["lps"]), len(b["lps"]))
    ds = [abs(a["lps"][i] - b["lps"][i]) for i in range(m)
          if a["lps"][i] is not None and b["lps"][i] is not None]
    return max(ds) if ds else 0.0


def gap_at(run, pos, other_token):
    """How far the endpoint's own choice at pos was ahead of the other endpoint's token.
    -> (gap_nats, exact). exact=False means other_token was not in the top list, so the
    value is a lower bound (top-1 minus the last listed logprob)."""
    if not run["top"] or pos >= len(run["top"]) or not run["top"][pos]:
        return None, False
    top = run["top"][pos]
    chosen = run["lps"][pos] if run["lps"] and pos < len(run["lps"]) and run["lps"][pos] is not None else top[0][1]
    for tok, lp in top:
        if tok == other_token:
            return chosen - lp, True
    return chosen - top[-1][1], False


def classify(gap, exact, tie_threshold):
    if gap is None:
        return "unknown"
    if exact and gap <= tie_threshold:
        return "near-tie"
    return "large-gap"


# ---------------------------------------------------------------- statistics

def _gammainc_upper_reg(s, x):
    """Q(s, x) = Gamma(s, x) / Gamma(s), for chi-square survival. Numerical Recipes style."""
    if x <= 0:
        return 1.0
    if x < s + 1:
        term = total = 1.0 / s
        a = s
        for _ in range(10000):
            a += 1
            term *= x / a
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return max(0.0, 1.0 - total * math.exp(-x + s * math.log(x) - math.lgamma(s)))
    b, c, d = x + 1 - s, 1e300, 1.0 / (x + 1 - s)
    h = d
    for i in range(1, 10000):
        an = -i * (i - s)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return min(1.0, math.exp(-x + s * math.log(x) - math.lgamma(s)) * h)


def chi2_sf(stat, dof):
    return 1.0 if dof <= 0 else _gammainc_upper_reg(dof / 2.0, stat / 2.0)


def two_sample(counts_a, counts_b, min_expected=5.0):
    """Chi-square test of homogeneity on two count tables. Categories whose expected
    count is below min_expected on either side are pooled into one 'other' bin.
    -> dict(tv, chi2, dof, p, n_a, n_b, categories)."""
    na, nb = sum(counts_a.values()), sum(counts_b.values())
    keys = set(counts_a) | set(counts_b)
    tv = 0.5 * sum(abs(counts_a.get(k, 0) / na - counts_b.get(k, 0) / nb) for k in keys) if na and nb else None
    n = na + nb
    big, other_a, other_b = [], 0, 0
    for k in keys:
        tot = counts_a.get(k, 0) + counts_b.get(k, 0)
        if tot * min(na, nb) / n >= min_expected:
            big.append(k)
        else:
            other_a += counts_a.get(k, 0)
            other_b += counts_b.get(k, 0)
    rows = [(counts_a.get(k, 0), counts_b.get(k, 0)) for k in big]
    if other_a + other_b:
        rows.append((other_a, other_b))
    stat = 0.0
    for ca, cb in rows:
        tot = ca + cb
        ea, eb = tot * na / n, tot * nb / n
        stat += (ca - ea) ** 2 / ea + (cb - eb) ** 2 / eb
    dof = len(rows) - 1
    return {"tv": tv, "chi2": stat, "dof": dof, "p": chi2_sf(stat, dof), "n_a": na, "n_b": nb,
            "categories": len(keys)}


def normalize_answer(text, mode):
    t = text.strip()
    if mode == "lastline":
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        t = lines[-1] if lines else ""
    return t.lower().strip(" .!*\"'`")


# ---------------------------------------------------------------- main

def load_prompts(path):
    out = []
    with open(path, encoding="utf-8") as f:
        if path.endswith(".jsonl"):
            for line in f:
                line = line.strip()
                if line:
                    obj = json.loads(line)
                    out.append(obj["prompt"] if isinstance(obj, dict) else obj)
        else:
            out = [blk.strip() for blk in f.read().split("\n\n\n") if blk.strip()]
    return out


def fmt(x, spec="%.4f"):
    return "-" if x is None else spec % x


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="base URL (ending in /v1) of the endpoint WITHOUT speculative decoding")
    ap.add_argument("--spec", required=True, help="base URL of the same target model WITH speculative decoding")
    ap.add_argument("--model", default=None, help="model id on --base (default: first id from GET /models)")
    ap.add_argument("--spec-model", default=None, help="model id on --spec (default: first id from GET /models)")
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    ap.add_argument("--prompts", default=None, help="greedy prompts: .jsonl ({\"prompt\": ...} per line) or text blocks separated by two blank lines")
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--top-logprobs", type=int, default=5, help="alternatives per position (vLLM allows up to --max-logprobs, default 20)")
    ap.add_argument("--tie-threshold", type=float, default=None,
                    help="divergences where the baseline preferred its token by at most this many nats count as near-ties "
                         "(default: max(0.05, 4 x the largest logprob difference seen on matching tokens))")
    ap.add_argument("--samples", type=int, default=200, help="samples per endpoint and prompt for the temperature test")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--sample-max-tokens", type=int, default=48)
    ap.add_argument("--sample-prompts", default=None, help="file like --prompts for the temperature test")
    ap.add_argument("--answer", choices=["full", "lastline"], default="lastline", help="what to compare in the temperature test")
    ap.add_argument("--skip-sample", action="store_true", help="greedy test only")
    ap.add_argument("--concurrency", type=int, default=1, help="parallel requests per endpoint (1 keeps batching out of the picture)")
    ap.add_argument("--completions", action="store_true", help="use /completions instead of /chat/completions")
    ap.add_argument("--extra", default=None, help="JSON object merged into every request, e.g. '{\"chat_template_kwargs\":{\"enable_thinking\":false}}'")
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--json", dest="json_out", default=None)
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args()

    greedy_prompts = load_prompts(args.prompts) if args.prompts else GREEDY_PROMPTS
    sample_prompts = load_prompts(args.sample_prompts) if args.sample_prompts else SAMPLE_PROMPTS
    extra = json.loads(args.extra) if args.extra else {}

    def connect(base, model):
        c = Client(base, model, args.api_key, args.timeout, args.completions)
        c.extra = extra
        if c.model is None:
            c.model = c.first_model()
        r = c.send("Say hi.", 0.0, 4, args.top_logprobs)
        if "error" in r:
            c.use_lp = False
            r2 = c.send("Say hi.", 0.0, 4, args.top_logprobs)
            if "error" in r2:
                raise RuntimeError("request to %s failed: %s" % (base, r["error"]))
            print("note: %s rejected logprobs (%s); comparing text only." % (base, r["error"][:100]))
        return c

    try:
        A = connect(args.base, args.model)
        B = connect(args.spec, args.spec_model)
    except Exception as e:  # noqa: BLE001
        print("error: %s" % e, file=sys.stderr)
        return 2

    print("specdiff %s" % VERSION)
    print("base: %s  model=%s" % (A.url, A.model))
    print("spec: %s  model=%s" % (B.url, B.model))
    print()

    def many(client, jobs):
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
            return list(pool.map(lambda j: client.send(*j), jobs))

    # ---- 1. greedy
    gjobs = [(p, 0.0, args.max_tokens, args.top_logprobs) for p in greedy_prompts]
    a1, a2 = many(A, gjobs), many(A, gjobs)
    b1 = many(B, gjobs)
    errors = [r["error"] for r in a1 + a2 + b1 if "error" in r]

    spec_lp_broken = any(logprobs_broken(r) for r in b1 if "error" not in r)
    self_differ = sum(1 for x, y in zip(a1, a2) if "error" not in x and "error" not in y and first_divergence(x, y)[0] is not None)

    rows, noise_all = [], []
    for i, (ra, rb) in enumerate(zip(a1, b1)):
        if "error" in ra or "error" in rb:
            rows.append({"i": i, "error": ra.get("error") or rb.get("error")})
            continue
        pos, unit = first_divergence(ra, rb)
        n = len(ra["tokens"]) if ra["tokens"] is not None else len(ra["text"])
        noise = None if spec_lp_broken else shared_noise(ra, rb, n if pos is None else pos)
        if noise is not None:
            noise_all.append(noise)
        rows.append({"i": i, "pos": pos, "unit": unit, "len": n, "noise": noise, "spec": rb["spec"],
                     "a": ra, "b": rb})

    tie = args.tie_threshold
    if tie is None:
        tie = max(0.05, 4 * max(noise_all)) if noise_all else 0.05

    print("1) greedy (temperature 0): %d prompts, max_tokens=%d, near-tie threshold %.4f nats"
          % (len(greedy_prompts), args.max_tokens, tie))
    print("%-3s %-11s %-9s %-13s %-12s %-10s %s" % ("#", "result", "first diff", "base gap", "spec gap", "drafts", "class"))
    n_tie = n_big = n_same = n_unknown = 0
    draft_tot = acc_tot = 0
    any_stats = False
    for r in rows:
        if "error" in r:
            print("%-3d ERROR %s" % (r["i"], r["error"][:90]))
            continue
        st = r["spec"]
        if st is not None:
            any_stats = True
            draft_tot += st[0]
            acc_tot += st[1]
        drafts = "-" if st is None else "%d/%d" % (st[1], st[0])
        if r["pos"] is None:
            n_same += 1
            r["class"] = "identical"
            print("%-3d %-11s %-9s %-13s %-12s %-10s %s" % (r["i"], "identical", "-", "-", "-", drafts, ""))
            continue
        a, b, pos = r["a"], r["b"], r["pos"]
        if r["unit"] == "token" and pos < len(a["tokens"]) and pos < len(b["tokens"]):
            ga, ea = gap_at(a, pos, b["tokens"][pos])
            gb, eb = (None, False) if spec_lp_broken else gap_at(b, pos, a["tokens"][pos])
        else:
            ga = gb = None
            ea = eb = False
        cls = classify(ga, ea, tie)
        r.update({"class": cls, "base_gap": ga, "base_gap_exact": ea, "spec_gap": gb, "spec_gap_exact": eb})
        n_tie += cls == "near-tie"
        n_big += cls == "large-gap"
        n_unknown += cls == "unknown"
        gtxt = "-" if ga is None else ("%.4f" % ga if ea else ">%.3f" % ga)
        stxt = "-" if gb is None else ("%.4f" % gb if eb else ">%.3f" % gb)
        print("%-3d %-11s %-9s %-13s %-12s %-10s %s" % (r["i"], "DIFFERS", "%d %s" % (pos, r["unit"]), gtxt, stxt, drafts, cls))

    if spec_lp_broken:
        print("\nwarning: the spec endpoint returned logprob 0.0 with no alternatives for every token after the first.")
        print("         Those values are not real (llama.cpp issue #27972); the gaps above use the baseline only.")
    if self_differ:
        print("\nwarning: the baseline disagreed with itself on %d of %d prompts at temperature 0." % (self_differ, len(greedy_prompts)))
        print("         Fix that first (other traffic on the server, prefix cache, batch invariance) - see the page.")

    # earliest divergence detail
    divs = [r for r in rows if "error" not in r and r["pos"] is not None]
    if divs:
        r = min(divs, key=lambda x: x["pos"])
        a, b, pos = r["a"], r["b"], r["pos"]
        print("\nearliest divergence: prompt %d after %d identical %ss" % (r["i"], pos, r["unit"]))
        if r["unit"] == "token":
            print("  ...%r" % "".join(a["disp"][max(0, pos - 12):pos]))
            print("  base: %r" % "".join(a["disp"][pos:pos + 8]))
            print("  spec: %r" % "".join(b["disp"][pos:pos + 8]))
            if a["top_disp"] and pos < len(a["top_disp"]):
                print("  base top-%d there: %s" % (len(a["top_disp"][pos]), ", ".join("%r %.4f" % kv for kv in a["top_disp"][pos])))
        else:
            print("  base: %r" % a["text"][pos:pos + 40])
            print("  spec: %r" % b["text"][pos:pos + 40])

    # ---- 2. sampling
    sample_res = []
    if not args.skip_sample:
        print("\n2) sampling (temperature %.2f): %d samples per endpoint and prompt" % (args.temperature, args.samples))
        print("%-3s %8s %6s %8s %10s %5s %10s %s" % ("#", "TV", "chi2", "dof", "p", "cats", "drafts", "top answers base | spec"))
        for i, p in enumerate(sample_prompts):
            jobs = [(p, args.temperature, args.sample_max_tokens, 1)] * args.samples
            ra = many(A, jobs)
            rb = many(B, jobs)
            ca = collections.Counter(normalize_answer(x["text"], args.answer) for x in ra if "error" not in x)
            cb = collections.Counter(normalize_answer(x["text"], args.answer) for x in rb if "error" not in x)
            errors += [x["error"] for x in ra + rb if "error" in x]
            stats = [x["spec"] for x in rb if "error" not in x and x["spec"] is not None]
            d = sum(s[0] for s in stats)
            acc = sum(s[1] for s in stats)
            res = two_sample(ca, cb) if ca and cb else None
            sample_res.append({"i": i, "test": res, "drafts": [acc, d] if stats else None,
                               "base_top": ca.most_common(5), "spec_top": cb.most_common(5)})
            if res is None:
                print("%-3d no successful samples" % i)
                continue
            top = "%s | %s" % (", ".join("%s:%d" % kv for kv in ca.most_common(3)),
                               ", ".join("%s:%d" % kv for kv in cb.most_common(3)))
            print("%-3d %8.4f %6.1f %8d %10.3g %5d %10s %s" % (
                i, res["tv"], res["chi2"], res["dof"], res["p"], res["categories"],
                "-" if not stats else "%d/%d" % (acc, d), top[:100]))

    # ---- 3. verdict
    shift = [s for s in sample_res if s["test"] and s["test"]["p"] < 0.001]
    engaged = (acc_tot > 0) if any_stats else None
    print()
    if any_stats:
        print("speculation: %d of %d draft tokens accepted in the greedy test (%.1f%%)" % (
            acc_tot, draft_tot, 100.0 * acc_tot / draft_tot if draft_tot else 0.0))
    else:
        print("speculation: the spec endpoint reported no draft statistics. For vLLM start it with")
        print("  --per-request-spec-decode-metrics summary; SGLang and llama-server report them by default.")

    if self_differ:
        code, verdict = 4, "INCONCLUSIVE_BASELINE_NONDETERMINISTIC"
    elif n_big or shift:
        code, verdict = 1, "SUSPECTED_BUG"
    elif engaged is False:
        code, verdict = 4, "INCONCLUSIVE_NO_DRAFTS_ACCEPTED"
    elif n_tie or n_unknown:
        code, verdict = 3, "NEAR_TIE_DIVERGENCE" if not n_unknown else "DIVERGENCE_UNCLASSIFIED"
    else:
        code, verdict = 0, "NO_DIFFERENCE_FOUND"
    print("VERDICT: %s" % verdict)
    explain = {
        "INCONCLUSIVE_BASELINE_NONDETERMINISTIC": "The baseline is not reproducible on its own, so differences cannot be blamed on speculation.",
        "SUSPECTED_BUG": " ".join(x for x in (
            ("%d greedy divergence(s) started where the baseline's token was clearly ahead (more than %.3f nats);"
             " rounding alone does not do that." % (n_big, tie)) if n_big else "",
            ("The sampled answers differ beyond chance on %d prompt(s) (p < 0.001)." % len(shift)) if shift else "",
            "Check that the speculative settings are not lossy by design (relaxed thresholds, synthetic or FLy"
            " acceptance), then the known-issue table for your engine and method.") if x),
        "INCONCLUSIVE_NO_DRAFTS_ACCEPTED": "No draft token was accepted, so every token came from ordinary decoding. "
                                           "Use prompts the drafter can predict (repetition, code, copying).",
        "NEAR_TIE_DIVERGENCE": "Every divergence started at a near-tie (%d of %d prompts). This is the batched verify pass "
                               "rounding differently from one-token decode: expected on most stacks, not a bug in the "
                               "acceptance rule, but it does make outputs non-reproducible across the two modes." % (n_tie, len(rows)),
        "DIVERGENCE_UNCLASSIFIED": "Outputs diverged but logprobs were missing at the divergence point. Re-run with logprobs enabled.",
        "NO_DIFFERENCE_FOUND": "All %d greedy outputs matched%s. Evidence, not proof: longer outputs and your own prompts "
                               "give divergence more chances to show." % (n_same, "" if args.skip_sample else " and sampled answers agreed"),
    }
    print(explain[verdict])
    if errors:
        print("\nnote: %d request(s) failed, e.g. %s" % (len(errors), errors[0][:160]))

    if args.json_out:
        slim = []
        for r in rows:
            r2 = {k: v for k, v in r.items() if k not in ("a", "b")}
            if "a" in r:
                r2["base_text"], r2["spec_text"] = r["a"]["text"], r["b"]["text"]
            slim.append(r2)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({"tool": "specdiff", "version": VERSION, "base": A.url, "spec": B.url,
                       "model": A.model, "spec_model": B.model, "verdict": verdict, "tie_threshold": tie,
                       "spec_logprobs_broken": spec_lp_broken, "baseline_self_differ": self_differ,
                       "draft_tokens": draft_tot, "accepted_tokens": acc_tot,
                       "greedy": slim, "sampling": sample_res}, f, ensure_ascii=False, indent=2)
        print("report written to %s" % args.json_out)
    return code


if __name__ == "__main__":
    sys.exit(main())
