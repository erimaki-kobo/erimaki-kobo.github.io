#!/usr/bin/env python3
"""thinkcheck.py - did the server actually stop thinking, and does it use top_k / min_p / seed?

Sends pairs of small requests to any OpenAI-compatible /v1/chat/completions endpoint
(llama-server, Ollama, vLLM, SGLang, LM Studio, a proxy ...) and reports, per request field:

  worked     the field changed the output the way it should
  ignored    the request succeeded but the field made no difference (silently dropped)
  error      the server rejected the request (HTTP status and message shown)
  can't tell the baseline gave no signal (e.g. the model does not think by default)

Thinking switches tried: chat_template_kwargs.enable_thinking=false, chat_template_kwargs.thinking=false
(DeepSeek V3.1, Kimi K2 templates), reasoning_effort="none",
think=false (Ollama's native field), top-level enable_thinking=false, and "/no_think" in the
prompt (Qwen3 soft switch). Thinking is detected in message.reasoning_content, message.reasoning,
message.reasoning_text, or a non-empty <think>...</think> block left in content.

Sampling fields tried: an unknown canary field, top_k=1, min_p=1.0, seed, and the three spellings
of a repetition penalty (repeat_penalty, repetition_penalty, frequency_penalty).

Standard library only. Python 3.8+.

  python thinkcheck.py --base-url http://localhost:8080/v1 --model qwen3
  python thinkcheck.py --base-url http://localhost:11434/v1 --model qwen3:0.6b
  python thinkcheck.py --base-url http://localhost:8000/v1 --model Qwen/Qwen3-0.6B --json out.json

https://erimaki-kobo.github.io/en/disable-thinking-request-field-check/
"""
import argparse, json, re, sys, time, urllib.request, urllib.error

VERSION = "1.0"
THINK_RE = re.compile(r"<think>(.*?)(?:</think>|$)", re.S)


class Client:
    def __init__(self, base, model, key, timeout):
        self.url = base.rstrip("/") + "/chat/completions"
        self.model, self.key, self.timeout = model, key, timeout
        self.calls = 0
        self.extra = {}

    def chat(self, prompt, **extra):
        body = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "stream": False}
        body.update(self.extra)
        body.update(extra)
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        if self.key:
            req.add_header("Authorization", "Bearer " + self.key)
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.status, json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                data = json.loads(raw)
            except ValueError:
                data = {"error": {"message": raw[:300]}}
            return e.code, data


def err_text(data):
    e = data.get("error", data) if isinstance(data, dict) else data
    if isinstance(e, dict):
        e = e.get("message") or e.get("detail") or json.dumps(e)
    return " ".join(str(e).split())[:160]


def parse(data):
    """-> (content, reasoning_text, where_found, completion_tokens)"""
    try:
        msg = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return "", "", "", None
    content = msg.get("content") or ""
    for k in ("reasoning_content", "reasoning", "reasoning_text"):
        v = msg.get(k)
        if isinstance(v, str) and v.strip():
            return content, v, "message." + k, (data.get("usage") or {}).get("completion_tokens")
    m = THINK_RE.search(content)
    if m and m.group(1).strip():
        return content, m.group(1), "<think> in content", (data.get("usage") or {}).get("completion_tokens")
    return content, "", "", (data.get("usage") or {}).get("completion_tokens")


def visible(content):
    return THINK_RE.sub("", content).strip()


def thinking_checks(c, a):
    prompt = a.think_prompt
    base = dict(max_tokens=a.think_tokens, temperature=0)
    rows = []
    st, d = c.chat(prompt, **base)
    if st != 200:
        print("baseline request failed: HTTP %s %s" % (st, err_text(d)), file=sys.stderr)
        sys.exit(2)
    _, r0, where0, n0 = parse(d)
    rows.append({"field": "(none, baseline)", "status": st, "thinking": bool(r0), "where": where0,
                 "completion_tokens": n0, "verdict": "thinks by default" if r0 else "no thinking seen"})
    tries = [
        ('chat_template_kwargs: {"enable_thinking": false}', prompt, {"chat_template_kwargs": {"enable_thinking": False}}),
        ('chat_template_kwargs: {"thinking": false}', prompt, {"chat_template_kwargs": {"thinking": False}}),
        ('reasoning_effort: "none"', prompt, {"reasoning_effort": "none"}),
        ("think: false", prompt, {"think": False}),
        ("enable_thinking: false (top level)", prompt, {"enable_thinking": False}),
        ('"/no_think" at the end of the prompt', prompt + " /no_think", {}),
    ]
    for name, p, extra in tries:
        body = dict(base); body.update(extra)
        st, d = c.chat(p, **body)
        if st != 200:
            rows.append({"field": name, "status": st, "thinking": None, "where": "", "completion_tokens": None,
                         "verdict": "error: " + err_text(d)})
            continue
        _, r, where, n = parse(d)
        if not r0:
            v = "can't tell (baseline does not think)"
        elif r:
            v = "ignored (still thinking)"
        else:
            v = "worked (no thinking)"
        rows.append({"field": name, "status": st, "thinking": bool(r), "where": where, "completion_tokens": n, "verdict": v,
                     "_extra": extra, "_prompt_suffix": p[len(prompt):]})
    return rows


def samples(c, prompt, n, **kw):
    outs = []
    for _ in range(n):
        st, d = c.chat(prompt, **kw)
        if st != 200:
            return st, err_text(d), None
        content, reasoning, _, _ = parse(d)
        outs.append(reasoning.strip() + "\n" + visible(content))
    return 200, "", outs


def sampling_checks(c, a):
    rows = []
    extra = json.loads(a.no_think_field) if a.no_think_field else {}
    P = a.sample_prompt
    hot = dict(max_tokens=a.sample_tokens, temperature=a.temperature, **extra)

    st, d = c.chat(P, max_tokens=8, erimaki_unknown_canary=1, **extra)
    rows.append({"field": "unknown field (erimaki_unknown_canary)", "status": st,
                 "verdict": "accepted and ignored (typos are silently dropped)" if st == 200 else "error: " + err_text(d)})

    st, e, base = samples(c, P, a.n, **hot)
    if base is None:
        rows.append({"field": "temperature %.1f baseline" % a.temperature, "status": st, "verdict": "error: " + e})
        return rows
    base_varies = len(set(base)) > 1
    for name, kw in (("top_k: 1", {"top_k": 1}), ("min_p: 1.0", {"min_p": 1.0})):
        body = dict(hot); body.update(kw)
        st, e, outs = samples(c, P, a.n, **body)
        if outs is None:
            v = "error: " + e
        elif len(set(outs)) == 1:
            v = "worked (%d samples identical)" % a.n if base_varies else "can't tell (baseline did not vary either)"
        else:
            v = "ignored (%d different outputs at temperature %.1f)" % (len(set(outs)), a.temperature)
        rows.append({"field": name, "status": st, "verdict": v})

    body = dict(hot, seed=1234)
    st, e, s1 = samples(c, P, 2, **body)
    if s1 is None:
        rows.append({"field": "seed", "status": st, "verdict": "error: " + e})
    else:
        st2, e2, s2 = samples(c, P, 1, **dict(hot, seed=4321))
        if s1[0] != s1[1]:
            v = "ignored (same seed gave different outputs)"
        elif s2 and s2[0] != s1[0]:
            v = "worked (same seed repeats, other seed differs)"
        else:
            v = "can't tell (all outputs identical)"
        rows.append({"field": "seed", "status": st, "verdict": v})

    RP = a.repeat_prompt
    cold = dict(max_tokens=a.sample_tokens, temperature=0, **extra)
    st, e, b0 = samples(c, RP, 1, **cold)
    for name, kw in (("repeat_penalty: 2.0", {"repeat_penalty": 2.0}),
                     ("repetition_penalty: 2.0", {"repetition_penalty": 2.0}),
                     ("frequency_penalty: 2.0", {"frequency_penalty": 2.0})):
        st, e, o = samples(c, RP, 1, **dict(cold, **kw))
        if o is None:
            v = "error: " + e
        elif b0 is None:
            v = "can't tell (baseline failed)"
        elif o[0] != b0[0]:
            v = "worked (output changed at temperature 0)"
        else:
            v = "no effect seen (identical at temperature 0: ignored, or nothing repeated to penalize)"
        rows.append({"field": name, "status": st, "verdict": v})
    return rows


def show(title, rows, cols):
    print("\n" + title)
    w = [max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols]
    w[-1] = min(w[-1], 90)
    print("  ".join(c.ljust(x) for c, x in zip(cols, w)))
    for r in rows:
        print("  ".join(str(r.get(c, "") if r.get(c) is not None else "-")[:x].ljust(x) for c, x in zip(cols, w)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base-url", required=True, help="e.g. http://localhost:8080/v1")
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key", default="")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--think-prompt", default="What is 17 * 23? Answer with the number only.")
    ap.add_argument("--think-tokens", type=int, default=512)
    ap.add_argument("--sample-prompt", default="Write one sentence about a random animal.")
    ap.add_argument("--repeat-prompt", default="Write the word apple twenty times, separated by spaces.")
    ap.add_argument("--sample-tokens", type=int, default=48)
    ap.add_argument("--temperature", type=float, default=1.5)
    ap.add_argument("-n", type=int, default=3, help="samples per sampling check (default 3)")
    ap.add_argument("--no-think-field", default=None,
                    help="JSON merged into the sampling checks so thinking does not eat max_tokens. Default: the first "
                         "switch that worked in the thinking checks, else nothing; pass '' to send nothing")
    ap.add_argument("--extra", default="", help="JSON merged into every request (e.g. a field your proxy needs)")
    ap.add_argument("--skip-thinking", action="store_true")
    ap.add_argument("--skip-sampling", action="store_true")
    ap.add_argument("--json", help="also write the results to this file")
    a = ap.parse_args()
    c = Client(a.base_url, a.model, a.api_key, a.timeout)
    if a.extra:
        c.extra = json.loads(a.extra)
    t0 = time.time()
    out = {"thinkcheck": VERSION, "base_url": a.base_url, "model": a.model}
    print("thinkcheck %s  %s  model=%s" % (VERSION, c.url, a.model))
    if not a.skip_thinking:
        out["thinking"] = thinking_checks(c, a)
        if a.no_think_field is None:
            for r in out["thinking"]:
                if r["verdict"].startswith("worked") and r.get("_extra"):
                    a.no_think_field = json.dumps(r["_extra"])
                    break
        for r in out["thinking"]:
            r.pop("_extra", None); r.pop("_prompt_suffix", None)
        show("Turning thinking off (temperature 0, max_tokens %d)" % a.think_tokens, out["thinking"],
             ["field", "status", "where", "completion_tokens", "verdict"])
    if not a.skip_sampling:
        out["sampling_extra"] = json.loads(a.no_think_field) if a.no_think_field else {}
        out["sampling"] = sampling_checks(c, a)
        show("Sampling fields (temperature %.1f, %d samples each; also sent: %s)" % (
            a.temperature, a.n, json.dumps(out["sampling_extra"]) if out["sampling_extra"] else "nothing"), out["sampling"],
             ["field", "status", "verdict"])
    out["requests"] = c.calls
    out["seconds"] = round(time.time() - t0, 1)
    print("\n%d requests, %.1f s" % (c.calls, out["seconds"]))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
