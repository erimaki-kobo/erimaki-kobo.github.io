#!/usr/bin/env python3
"""overflow_check.py - what does your OpenAI-compatible server do when a request
does not fit in the context window, and what will your client do with that?

It sends four requests to /v1/chat/completions:
  prompt_over        a prompt about 64 tokens longer than the context
  prompt_over_stream the same with stream=true
  total_over         a prompt that fits, plus max_tokens that does not
  max_tokens_over    a short prompt with max_tokens larger than the context
and records the HTTP status, the error type and message, the first SSE event
for the streaming request, and for a 200 the usage counts (a prompt_tokens far
below what was sent means the server truncated the prompt without telling you).

For every error it then says whether openai-python retries it (408/409/429/5xx,
or the x-should-retry header) and whether LiteLLM's message check would raise
ContextWindowExceededError. With --clients it also calls the installed
openai-python and LiteLLM against the server and reports what they raised.

usage:
  python overflow_check.py --base-url http://localhost:8000/v1 --model MODEL [--ctx N]
         [--api-key KEY] [--clients] [--json out.json]
Only the standard library is needed; --clients needs `pip install openai litellm`.
https://erimaki-kobo.github.io/en/context-overflow-error-status-check/
"""
import argparse, json, sys, time, urllib.request, urllib.error

# LiteLLM 1.111.0, litellm/litellm_core_utils/exception_mapping_utils.py,
# ExceptionCheckers.is_error_str_context_window_exceeded (lower-cased substrings)
LITELLM_SUBSTRINGS = [
    "exceed context limit", "this model's maximum context length is",
    "requested token count exceeds the model's maximum context length",
    "string too long. expected a string with maximum length", "model's maximum context limit",
    "is longer than the model's context length", "input tokens exceed the configured limit",
    "`inputs` tokens + `max_new_tokens` must be", "exceeds the available context size",
    "exceeds the maximum number of tokens allowed", '"code": "context_length_exceeded"', "prompt is too long",
]


def litellm_says_context(msg):
    s = (msg or "").lower()
    if "string_above_max_length" in s:
        return False
    if any(x in s for x in LITELLM_SUBSTRINGS):
        return True
    return ("current length is" in s and "while limit is" in s) or \
           ("maximum input length is" in s and "tokens" in s) or \
           ("input too long:" in s and "input tokens, limit is" in s)


def openai_python_retries(status, headers):
    h = (headers.get("x-should-retry") or "").lower()
    if h == "true":
        return True
    if h == "false":
        return False
    return status in (408, 409, 429) or status >= 500


class Server:
    def __init__(self, base, model, key):
        self.base, self.model, self.key = base.rstrip("/"), model, key

    def post(self, path, body, stream=False, timeout=600):
        req = urllib.request.Request(self.base + path, json.dumps(body).encode(), method="POST",
                                     headers={"content-type": "application/json",
                                              "authorization": "Bearer " + self.key})
        try:
            r = urllib.request.urlopen(req, timeout=timeout)
            status, headers = r.status, r.headers
        except urllib.error.HTTPError as e:
            r, status, headers = e, e.code, e.headers
        if stream and status == 200:
            first = None
            n = 0
            for line in r:
                line = line.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                n += 1
                if first is None:
                    first = line[5:].strip()
                if n >= 3:
                    break
            r.close()
            return status, headers, first
        return status, headers, r.read().decode("utf-8", "replace")

    def get(self, url):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"authorization": "Bearer " + self.key}), timeout=30) as r:
                return json.loads(r.read())
        except Exception:
            return None

    def chat(self, text, max_tokens, stream=False):
        body = {"model": self.model, "messages": [{"role": "user", "content": text}],
                "max_tokens": max_tokens, "temperature": 0, "stream": stream}
        return self.post("/chat/completions", body, stream=stream)


def guess_ctx(s):
    root = s.base[:-3] if s.base.endswith("/v1") else s.base
    m = s.get(s.base + "/models") or {}
    for d in m.get("data", []):  # vLLM, SGLang
        for k in ("max_model_len", "context_length", "max_context_length"):
            if isinstance(d.get(k), int):
                return d[k], "/v1/models " + k
    p = s.get(root + "/props") or {}  # llama.cpp
    n = (p.get("default_generation_settings") or {}).get("n_ctx")
    if isinstance(n, int):
        return n, "/props n_ctx (per slot)"
    return None, None


def calibrate(s):
    """tokens per repetition of 'the ' from two small requests (prompt_tokens in usage)."""
    pts = []
    for reps in (10, 40):
        st, _, body = s.chat("the " * reps, 1)
        if st != 200:
            raise SystemExit("calibration request failed: HTTP %d %s" % (st, body[:300]))
        pts.append((reps, json.loads(body)["usage"]["prompt_tokens"]))
    per = (pts[1][1] - pts[0][1]) / 30.0
    base = pts[0][1] - per * 10
    return per, base


def describe(name, sent_tokens, max_tokens, st, headers, body):
    row = {"test": name, "sent_prompt_tokens": round(sent_tokens), "max_tokens": max_tokens, "status": st,
           "content_type": headers.get("content-type")}
    if name.endswith("_stream") and st == 200:
        row["first_sse_event"] = (body or "")[:400]
        try:
            ev = json.loads(body)
        except Exception:
            ev = {}
        err = ev.get("error") if isinstance(ev.get("error"), dict) else (ev if ev.get("object") == "error" else None)
        if err:
            row["verdict"] = "error sent INSIDE a 200 stream: clients see a chunk, not an exception"
            row["message"] = err.get("message")
        elif "error" in ev:
            row["verdict"] = "error sent inside a 200 stream"
            row["message"] = str(ev["error"])
        else:
            row["verdict"] = "200 stream started normally (prompt was accepted: truncated or shifted?)"
        return row
    try:
        j = json.loads(body)
    except Exception:
        j = {"_raw": body[:400]}
    if st == 200:
        u = j.get("usage") or {}
        fr = ((j.get("choices") or [{}])[0]).get("finish_reason")
        row.update(prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"), finish_reason=fr)
        pt = u.get("prompt_tokens") or 0
        if name in ("prompt_over",) or pt < sent_tokens * 0.9:
            row["verdict"] = "accepted with HTTP 200: the prompt was truncated without an error" if pt < sent_tokens * 0.9 \
                else "accepted with HTTP 200"
        elif name in ("total_over", "max_tokens_over"):
            ct = u.get("completion_tokens") or 0
            if fr == "length" and ct < max_tokens:
                row["verdict"] = ("accepted with HTTP 200: generation stopped at the context limit "
                                  "after %d of %d requested tokens (finish_reason=length, no error)" % (ct, max_tokens))
            else:
                row["verdict"] = "accepted with HTTP 200: max_tokens is not checked against the context"
        else:
            row["verdict"] = "accepted with HTTP 200"
        return row
    e = j.get("error")
    if isinstance(e, dict):
        row.update(error_type=e.get("type"), error_code=e.get("code"), message=e.get("message"))
        extra = {k: v for k, v in e.items() if k not in ("type", "code", "message", "param")}
        if extra:
            row["error_extra"] = extra
    elif isinstance(e, str):
        row.update(error_type=j.get("error_type"), message=e)
    else:
        row.update(error_type=j.get("type"), message=j.get("message") or j.get("detail") or j.get("_raw"))
    row["openai_python_retries"] = openai_python_retries(st, headers)
    row["litellm_message_check"] = litellm_says_context(row.get("message"))
    row["verdict"] = "HTTP %d%s" % (st, ", openai-python retries it" if row["openai_python_retries"] else "")
    return row


def with_clients(s, text, max_tokens, stream):
    out = {}
    try:
        import openai
        c = openai.OpenAI(base_url=s.base, api_key=s.key)
        try:
            r = c.chat.completions.create(model=s.model, messages=[{"role": "user", "content": text}],
                                          max_tokens=max_tokens, stream=stream)
            if stream:
                first = next(iter(r), None)
                out["openai_python"] = "no exception; first chunk object=%r" % getattr(first, "object", None)
            else:
                out["openai_python"] = "no exception"
        except Exception as e:
            out["openai_python"] = type(e).__name__
    except ImportError:
        out["openai_python"] = "not installed"
    try:
        import litellm
        litellm.suppress_debug_info = True
        for prov in ("openai", "hosted_vllm"):
            try:
                r = litellm.completion(model=prov + "/" + s.model, api_base=s.base, api_key=s.key, stream=stream,
                                       messages=[{"role": "user", "content": text}], max_tokens=max_tokens, max_retries=0)
                if stream:
                    list(r)
                out["litellm_" + prov] = "no exception"
            except Exception as e:
                out["litellm_" + prov] = type(e).__name__
    except ImportError:
        out["litellm"] = "not installed"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True, help="e.g. http://localhost:8000/v1")
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key", default="EMPTY")
    ap.add_argument("--ctx", type=int, help="context length to test against (read from the server if omitted)")
    ap.add_argument("--clients", action="store_true", help="also call openai-python and LiteLLM")
    ap.add_argument("--json")
    a = ap.parse_args()
    s = Server(a.base_url, a.model, a.api_key)
    ctx, src = (a.ctx, "--ctx") if a.ctx else guess_ctx(s)
    if not ctx:
        raise SystemExit("could not read the context length from the server; pass --ctx N")
    per, base = calibrate(s)
    print("context %d (%s); 'the ' = %.3f tokens, template overhead ~%.0f tokens" % (ctx, src, per, base))

    def text_for(tokens):
        reps = max(1, int((tokens - base) / per))
        return "the " * reps, base + per * reps

    plan = [("prompt_over", ctx + 64, 16, False), ("prompt_over_stream", ctx + 64, 16, True),
            ("total_over", ctx - 200, 1000, False), ("max_tokens_over", 20, ctx + 1, False)]
    rows = []
    for name, want, mt, stream in plan:
        text, sent = text_for(want)
        t = time.time()
        st, h, body = s.chat(text, mt, stream=stream)
        row = describe(name, sent, mt, st, h, body)
        row["seconds"] = round(time.time() - t, 2)
        if a.clients:
            row["clients"] = with_clients(s, text, mt, stream)
        rows.append(row)
        print("\n[%s] sent ~%d prompt tokens, max_tokens=%d" % (name, sent, mt))
        for k in ("verdict", "status", "error_type", "message", "error_extra", "first_sse_event", "prompt_tokens",
                  "completion_tokens", "finish_reason", "openai_python_retries", "litellm_message_check", "clients"):
            if row.get(k) is not None:
                print("  %-22s %s" % (k, row[k]))
    if a.json:
        json.dump({"base_url": a.base_url, "model": a.model, "ctx": ctx, "rows": rows}, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
