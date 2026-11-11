#!/usr/bin/env python3
"""sotime.py - measure what structured output (JSON schema) costs on your
OpenAI-compatible endpoint (vLLM, SGLang, llama.cpp server, ...).

It sends the same prompt in four ways and compares them:

  free     no constraint (the baseline)
  warm     response_format json_schema, the same schema every time
           (the first request is reported separately: it pays the compile)
  cold     a schema that differs on every request (a nonce in "description"),
           so a grammar cache cannot help
  compact  vLLM only: structured_outputs.json with disable_any_whitespace

and reports time to first token (TTFT), inter-token latency (ITL), total time,
tokens, how many outputs are valid JSON that matches the schema, and why a
run looks slow (compile, per-token mask cost, or runaway whitespace).

Standard library only. If the `jsonschema` package is installed it is used
for validation; otherwise a small built-in validator checks the common
keywords.

Examples:
  python sotime.py --base-url http://localhost:8000/v1 --model Qwen/Qwen3-8B
  python sotime.py --base-url ... --model ... --schema my_schema.json -n 8
  python sotime.py --base-url ... --model ... --builtin all --json report.json

Exit codes: 0 = constrained output looked fine, 1 = the constraint was not
applied or outputs did not match the schema, 3 = runaway whitespace
(outputs hit max_tokens padded with whitespace), 2 = could not run.

Backends are chosen at server start in vLLM (--structured-outputs-config.backend,
default "auto"); a request cannot pick one. To compare xgrammar and guidance,
start the server twice and run this script against each, with --label.

https://erimaki-kobo.github.io/en/vllm-structured-output-backend-cost/
"""
import argparse
import json
import os
import re
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

VERSION = "1.0 (2026-11-11)"

BUILTIN = {
    "flat": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer", "minimum": 0, "maximum": 120},
            "email": {"type": "string", "format": "email"},
            "active": {"type": "boolean"},
        },
        "required": ["name", "age", "email", "active"],
        "additionalProperties": False,
    },
    "nested": {
        "type": "object",
        "properties": {
            "invoice_id": {"type": "string", "pattern": "^INV-[0-9]{6}$"},
            "currency": {"type": "string", "enum": ["USD", "EUR", "JPY"]},
            "customer": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "country": {"type": "string"},
                },
                "required": ["name", "country"],
                "additionalProperties": False,
            },
            "lines": {
                "type": "array",
                "minItems": 1,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "sku": {"type": "string"},
                        "qty": {"type": "integer", "minimum": 1},
                        "unit_price": {"type": "number"},
                    },
                    "required": ["sku", "qty", "unit_price"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["invoice_id", "currency", "customer", "lines"],
        "additionalProperties": False,
    },
    # Uses keywords that vLLM's "auto" mode sends to guidance instead of
    # xgrammar (uniqueItems on an array, pattern + maxLength on a string),
    # so on a default vLLM server this measures the fallback path.
    "fallback": {
        "type": "object",
        "properties": {
            "slug": {"type": "string", "pattern": "^[a-z-]+$", "maxLength": 24},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "uniqueItems": True,
                "maxItems": 4,
            },
            "score": {"type": "number"},
        },
        "required": ["slug", "tags", "score"],
        "additionalProperties": False,
    },
}

PROMPTS = {
    "flat": "Invent a user record for a fictional person. Reply with JSON only.",
    "nested": "Invent an invoice with two or three lines for a fictional customer. Reply with JSON only.",
    "fallback": "Invent a short blog post slug, up to four tags and a quality score. Reply with JSON only.",
}
GENERIC_PROMPT = "Fill in this JSON schema with plausible made-up values. Reply with JSON only.\n\nSchema:\n{schema}"


# ----------------------------------------------------------------- validation
def _type_ok(v, t):
    if isinstance(t, list):
        return any(_type_ok(v, x) for x in t)
    if t == "object":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, list)
    if t == "string":
        return isinstance(v, str)
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool) or (isinstance(v, float) and v.is_integer())
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "null":
        return v is None
    return True


def mini_validate(v, s, path="$"):
    """Checks the common JSON Schema keywords. Returns a list of errors."""
    errs = []
    if not isinstance(s, dict):
        return errs
    if "type" in s and not _type_ok(v, s["type"]):
        return [f"{path}: expected {s['type']}"]
    if "enum" in s and v not in s["enum"]:
        errs.append(f"{path}: not in enum")
    if "const" in s and v != s["const"]:
        errs.append(f"{path}: not const")
    if isinstance(v, str):
        if "minLength" in s and len(v) < s["minLength"]:
            errs.append(f"{path}: shorter than minLength")
        if "maxLength" in s and len(v) > s["maxLength"]:
            errs.append(f"{path}: longer than maxLength")
        if "pattern" in s:
            try:
                if not re.search(s["pattern"], v):
                    errs.append(f"{path}: does not match pattern")
            except re.error:
                pass
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in s and v < s["minimum"]:
            errs.append(f"{path}: below minimum")
        if "maximum" in s and v > s["maximum"]:
            errs.append(f"{path}: above maximum")
    if isinstance(v, list):
        if "minItems" in s and len(v) < s["minItems"]:
            errs.append(f"{path}: fewer than minItems")
        if "maxItems" in s and len(v) > s["maxItems"]:
            errs.append(f"{path}: more than maxItems")
        if s.get("uniqueItems"):
            seen = [json.dumps(x, sort_keys=True) for x in v]
            if len(seen) != len(set(seen)):
                errs.append(f"{path}: items not unique")
        if isinstance(s.get("items"), dict):
            for i, x in enumerate(v):
                errs += mini_validate(x, s["items"], f"{path}[{i}]")
    if isinstance(v, dict):
        props = s.get("properties", {})
        for r in s.get("required", []):
            if r not in v:
                errs.append(f"{path}: missing {r}")
        for k, x in v.items():
            if k in props:
                errs += mini_validate(x, props[k], f"{path}.{k}")
            elif s.get("additionalProperties") is False:
                errs.append(f"{path}: unexpected key {k}")
    for key in ("anyOf", "oneOf"):
        if isinstance(s.get(key), list):
            if not any(not mini_validate(v, b, path) for b in s[key]):
                errs.append(f"{path}: matches no {key} branch")
    if isinstance(s.get("allOf"), list):
        for b in s["allOf"]:
            errs += mini_validate(v, b, path)
    return errs


def validate(obj, schema):
    try:
        import jsonschema  # type: ignore

        try:
            jsonschema.validate(obj, schema)
            return []
        except jsonschema.ValidationError as e:
            return [e.message[:120]]
        except jsonschema.SchemaError:
            pass
    except ImportError:
        pass
    return mini_validate(obj, schema)


# ------------------------------------------------------------------- requests
class Result:
    def __init__(self):
        self.ok = False
        self.status = None
        self.error = None
        self.ttft = None
        self.total = None
        self.itl = None
        self.tokens = None
        self.finish = None
        self.text = ""


def stream_chat(base, key, body, timeout):
    r = Result()
    data = json.dumps(body).encode()
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("Authorization", "Bearer " + key)
    t0 = time.perf_counter()
    first = last = None
    chunks = 0
    parts = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            r.status = resp.status
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    ev = json.loads(payload)
                except ValueError:
                    continue
                if ev.get("usage") and ev["usage"].get("completion_tokens") is not None:
                    r.tokens = ev["usage"]["completion_tokens"]
                for ch in ev.get("choices") or []:
                    delta = ch.get("delta") or {}
                    piece = delta.get("content") or ""
                    if delta.get("reasoning_content") or delta.get("reasoning"):
                        piece = piece  # reasoning text is not part of the answer
                    if piece:
                        now = time.perf_counter()
                        if first is None:
                            first = now
                        last = now
                        chunks += 1
                        parts.append(piece)
                    if ch.get("finish_reason"):
                        r.finish = ch["finish_reason"]
    except urllib.error.HTTPError as e:
        r.status = e.code
        try:
            r.error = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            r.error = str(e)
        return r
    except Exception as e:  # connection refused, timeout, ...
        r.error = f"{type(e).__name__}: {e}"
        return r
    end = time.perf_counter()
    r.text = "".join(parts)
    r.total = end - t0
    if first is not None:
        r.ttft = first - t0
        n = r.tokens or chunks
        if n and n > 1 and last > first:
            r.itl = (last - first) / (n - 1)
    if r.tokens is None:
        r.tokens = chunks
    r.ok = True
    return r


def strip_fences(t):
    t = t.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.S)
    return m.group(1) if m else t


def whitespace_share(t):
    if not t:
        return 0.0
    return sum(1 for c in t if c in " \t\r\n") / len(t)


# ---------------------------------------------------------------------- probes
def make_body(args, prompt, mode, schema, nonce=None):
    body = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if args.no_think:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    if mode in ("warm", "cold"):
        s = schema
        if mode == "cold":
            s = dict(schema)
            s["description"] = "run " + nonce
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "answer", "schema": s, "strict": True},
        }
    elif mode == "compact":
        body["structured_outputs"] = {"json": schema, "disable_any_whitespace": True}
    return body


def run_probe(args, name, prompt, mode, schema):
    out = []
    lock = threading.Lock()
    todo = list(range(args.n))

    def worker():
        while True:
            with lock:
                if not todo:
                    return
                i = todo.pop(0)
            nonce = uuid.uuid4().hex[:12]
            body = make_body(args, prompt, mode, schema, nonce)
            r = stream_chat(args.base_url, args.api_key, body, args.timeout)
            r.index = i
            with lock:
                out.append(r)

    # Requests go one at a time unless --concurrency is set, so TTFT shows
    # compile time rather than queueing.
    threads = [threading.Thread(target=worker) for _ in range(max(1, args.concurrency))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    out.sort(key=lambda r: r.index)
    return out


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def summarize(rs, schema, constrained):
    ok = [r for r in rs if r.ok]
    s = {
        "requests": len(rs),
        "errors": len(rs) - len(ok),
        "error_sample": next((f"HTTP {r.status}: {r.error}" if r.status else r.error for r in rs if not r.ok), None),
        "ttft_first": ok[0].ttft if ok else None,
        "ttft_median": med([r.ttft for r in ok]),
        "ttft_median_after_first": med([r.ttft for r in ok[1:]]) if len(ok) > 1 else None,
        "itl_median": med([r.itl for r in ok]),
        "total_median": med([r.total for r in ok]),
        "tokens_median": med([r.tokens for r in ok]),
        "hit_max_tokens": sum(1 for r in ok if r.finish == "length"),
        "whitespace_share_median": med([whitespace_share(r.text) for r in ok]),
        "valid_json": 0,
        "schema_ok": 0,
        "sample_problem": None,
    }
    for r in ok:
        txt = r.text if constrained else strip_fences(r.text)
        try:
            obj = json.loads(txt)
        except ValueError:
            if s["sample_problem"] is None:
                s["sample_problem"] = "not JSON: " + repr(r.text[:80])
            continue
        s["valid_json"] += 1
        errs = validate(obj, schema)
        if not errs:
            s["schema_ok"] += 1
        elif s["sample_problem"] is None:
            s["sample_problem"] = errs[0]
    return s


def fmt_ms(x):
    return "-" if x is None else f"{x * 1000:.0f} ms"


def diagnose(res):
    """Turns the four summaries into findings. Returns (lines, exit_code)."""
    lines, code = [], 0
    free, warm, cold, compact = (res.get(k) for k in ("free", "warm", "cold", "compact"))
    if not warm or warm["requests"] == warm["errors"]:
        msg = warm["error_sample"] if warm else "not run"
        lines.append(f"The constrained request failed on every try ({msg}). The server may not accept response_format json_schema.")
        return lines, 2
    n_ok = warm["requests"] - warm["errors"]
    if warm["valid_json"] < n_ok and warm["hit_max_tokens"] < n_ok:
        lines.append(f"CONSTRAINT NOT APPLIED: {n_ok - warm['valid_json']} of {n_ok} constrained outputs are not JSON although they ended normally. "
                     "The server ignored response_format (an old guided_json field, a proxy that drops it, or an engine without JSON-schema support).")
        code = 1
    elif warm["schema_ok"] < warm["valid_json"]:
        lines.append(f"SCHEMA MISMATCH: {warm['valid_json'] - warm['schema_ok']} constrained outputs are JSON but break the schema "
                     f"(first: {warm['sample_problem']}). Some backends ignore keywords they do not support; on vLLM \"auto\" check which backend the schema lands on.")
        code = 1
    ws = warm["whitespace_share_median"] or 0
    if warm["hit_max_tokens"] and ws > 0.25:
        lines.append(f"RUNAWAY WHITESPACE: {warm['hit_max_tokens']} constrained outputs hit max_tokens and are {ws:.0%} whitespace. "
                     "The grammar allows whitespace between JSON tokens and the model keeps emitting it. "
                     "On vLLM set disable_any_whitespace (per request in structured_outputs, or --structured-outputs-config.disable_any_whitespace true).")
        if compact and compact["requests"] > compact["errors"]:
            lines.append(f"  compact run: {compact['hit_max_tokens']} hit max_tokens, median total {fmt_ms(compact['total_median'])} "
                         f"vs {fmt_ms(warm['total_median'])} with whitespace allowed.")
        code = 3 if code == 0 else code
    if warm["ttft_first"] is not None and warm["ttft_median_after_first"] is not None:
        d = warm["ttft_first"] - warm["ttft_median_after_first"]
        lines.append(f"First request with a new schema: TTFT {fmt_ms(warm['ttft_first'])}; the same schema again: {fmt_ms(warm['ttft_median_after_first'])} "
                     f"(difference {fmt_ms(d)}, mostly grammar compilation).")
    if cold and cold["ttft_median"] is not None and warm["ttft_median_after_first"] is not None:
        d = cold["ttft_median"] - warm["ttft_median_after_first"]
        lines.append(f"A different schema on every request costs about {fmt_ms(d)} of TTFT each (cold median {fmt_ms(cold['ttft_median'])}). "
                     "If your schemas change per request, this is the number that matters.")
    if free and free["itl_median"] and warm["itl_median"]:
        ratio = warm["itl_median"] / free["itl_median"]
        lines.append(f"Per-token cost: ITL {fmt_ms(warm['itl_median'])} constrained vs {fmt_ms(free['itl_median'])} free ({ratio:.2f}x).")
    if free and free["tokens_median"] and warm["tokens_median"]:
        lines.append(f"Output length: {warm['tokens_median']:.0f} tokens constrained vs {free['tokens_median']:.0f} free. "
                     "Total time is mostly length x ITL, so a longer constrained answer is slower even with no per-token overhead.")
    if free and free["requests"] > free["errors"]:
        lines.append(f"Without a constraint, {free['schema_ok']} of {free['requests'] - free['errors']} answers already matched the schema.")
    return lines, code


def print_table(res, label):
    cols = ["probe", "ok/n", "TTFT 1st", "TTFT med", "ITL med", "total med", "tokens", "at max", "ws", "JSON", "schema"]
    rows = []
    for k in ("free", "warm", "cold", "compact"):
        s = res.get(k)
        if not s:
            continue
        okn = s["requests"] - s["errors"]
        rows.append([k, f"{okn}/{s['requests']}", fmt_ms(s["ttft_first"]), fmt_ms(s["ttft_median"]), fmt_ms(s["itl_median"]),
                     fmt_ms(s["total_median"]), "-" if s["tokens_median"] is None else f"{s['tokens_median']:.0f}",
                     str(s["hit_max_tokens"]), "-" if s["whitespace_share_median"] is None else f"{s['whitespace_share_median']:.0%}",
                     f"{s['valid_json']}/{okn}", f"{s['schema_ok']}/{okn}"])
    w = [max(len(str(r[i])) for r in rows + [cols]) for i in range(len(cols))]
    if label:
        print(f"[{label}]")
    print("  ".join(c.ljust(w[i]) for i, c in enumerate(cols)))
    for r in rows:
        print("  ".join(str(c).ljust(w[i]) for i, c in enumerate(r)))


def main():
    ap = argparse.ArgumentParser(description="Measure the cost of JSON-schema structured output on an OpenAI-compatible endpoint.")
    ap.add_argument("--base-url", required=True, help="e.g. http://localhost:8000/v1")
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    ap.add_argument("--schema", help="path to a JSON schema file (default: built-in schemas)")
    ap.add_argument("--prompt", help="prompt to use with --schema")
    ap.add_argument("--builtin", default="flat,nested", help="built-in schemas to run: flat, nested, fallback, or all (default flat,nested)")
    ap.add_argument("-n", type=int, default=6, help="requests per probe (default 6)")
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--concurrency", type=int, default=1, help="parallel requests per probe (default 1, so TTFT is not queueing)")
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--probes", default="free,warm,cold,compact")
    ap.add_argument("--no-think", action="store_true", help="send chat_template_kwargs enable_thinking=false (Qwen3-style models)")
    ap.add_argument("--label", default="", help="name for this run, e.g. the backend the server was started with")
    ap.add_argument("--json", dest="json_out", help="write the full report as JSON")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args()

    if args.schema:
        with open(args.schema, encoding="utf-8") as f:
            schema = json.load(f)
        jobs = [("custom", schema, args.prompt or GENERIC_PROMPT.format(schema=json.dumps(schema)))]
    else:
        names = list(BUILTIN) if args.builtin == "all" else [x.strip() for x in args.builtin.split(",") if x.strip()]
        for x in names:
            if x not in BUILTIN:
                print(f"unknown built-in schema: {x}", file=sys.stderr)
                return 2
        jobs = [(x, BUILTIN[x], PROMPTS[x]) for x in names]
    probes = [p.strip() for p in args.probes.split(",") if p.strip()]

    report = {"version": VERSION, "base_url": args.base_url, "model": args.model, "label": args.label,
              "n": args.n, "max_tokens": args.max_tokens, "concurrency": args.concurrency, "schemas": {}}
    worst = 0
    for name, schema, prompt in jobs:
        res = {}
        for p in probes:
            rs = run_probe(args, name, prompt, p, schema)
            res[p] = summarize(rs, schema, p != "free")
            if p == "free" and res[p]["errors"] == res[p]["requests"]:
                print(f"Cannot reach the endpoint: {res[p]['error_sample']}", file=sys.stderr)
                return 2
        print()
        print_table(res, f"{args.label + ' / ' if args.label else ''}{name}")
        lines, code = diagnose(res)
        for ln in lines:
            print("  - " + ln)
        report["schemas"][name] = {"schema": schema, "results": res, "findings": lines, "exit_code": code}
        if code in (1, 3) and worst != 1:
            worst = code
        elif code == 2 and worst == 0:
            worst = 2
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
    return worst


if __name__ == "__main__":
    sys.exit(main())
