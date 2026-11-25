#!/usr/bin/env python3
"""toolcheck.py: test the tool calls of an OpenAI-compatible server (vLLM, SGLang, llama.cpp, Ollama, LM Studio, ...).

  python3 toolcheck.py --base-url http://localhost:8000/v1 --model Qwen/Qwen3-8B
  python3 toolcheck.py --base-url http://localhost:8000/v1 --model M --api-key KEY --json report.json

Sends a few chat requests with tools, non-streaming and streaming, and sorts each answer into one verdict:

  ok                 tool_calls hold the call, arguments are valid JSON and fit the tool's schema
  markup_in_content  no tool_calls, but the model's tool-call markup (<tool_call>, <|tool_call>, [TOOL_CALLS], {"name": ...)
                     is in message.content: the server's tool parser did not match the model's output
  call_in_reasoning  no tool_calls; the markup is in reasoning / reasoning_content (the call was written while thinking)
  empty              no tool_calls, no content, no reasoning: the answer is empty (a parser ate the call)
  no_call            the model answered in text without calling a tool (not a server bug when tool_choice is auto)
  bad_json           a call's arguments are not valid JSON
  schema_mismatch    the arguments are JSON but miss a required key or have the wrong type
  stream_header      streaming: a call's first chunk lacks id or function.name, or they are sent again
  stream_differs     streaming gave different calls than the same request without streaming
  finish_reason      calls came back but finish_reason is not "tool_calls" (or a cut call says "tool_calls")
  http_<status>      the server refused the request; the error text is shown

The model decides whether to call, so run it more than once before calling a server broken; a markup_in_content,
call_in_reasoning, empty or stream_header verdict is about the server, not the model. Python 3.8+, no packages.
https://erimaki-kobo.github.io/en/tool-call-parser-conformance-check/"""
import argparse, json, re, sys, time, urllib.error, urllib.request

TOOLS = [
    {"type": "function", "function": {"name": "get_weather", "description": "Get the weather forecast for a city.",
                                      "parameters": {"type": "object", "properties": {"city": {"type": "string", "description": "City name"},
                                                                                      "days": {"type": "integer", "description": "Number of days, 1 to 7"}},
                                                     "required": ["city"]}}},
    {"type": "function", "function": {"name": "search", "description": "Search the web.",
                                      "parameters": {"type": "object", "properties": {"query": {"type": "string"},
                                                                                      "filters": {"type": "object", "properties": {"lang": {"type": "string"}, "limit": {"type": "integer"}}}},
                                                     "required": ["query"]}}},
]
TESTS = [
    ("auto", "What is the weather in Tokyo for the next 3 days? Use the get_weather tool.", {"tool_choice": "auto"}, 1),
    ("required", "What is the weather in Paris?", {"tool_choice": "required"}, 1),
    ("parallel", "Get the weather for Tokyo and for Paris. Call get_weather once for each city, both in this turn.", {"tool_choice": "auto", "parallel_tool_calls": True}, 2),
    ("nested_args", "Search the web for 東京 天気 with filters lang=ja and limit=5. Use the search tool with a filters object.", {"tool_choice": "auto"}, 1),
    ("cut_short", "What is the weather in San Francisco for the next 7 days? Use the get_weather tool.", {"tool_choice": "required", "max_tokens": 8}, None),
]
MARKUP = re.compile(r"<\|?tool_call|tool_call\|?>|<function=|<\|tool_calls?_|<｜tool|<arg_key>|<minimax:tool_call>|<invoke |\[TOOL_CALLS\]|<\|python_tag\|>|"
                    r"\"name\"\s*:\s*\"(get_weather|search)\"|\b(get_weather|search)\s*\(|call:(get_weather|search)\b")


def post(base, key, body, stream, timeout):
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + key} if key else {})})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    if not stream:
        return 200, json.loads(r.read().decode())
    chunks = []
    for line in r:
        line = line.decode("utf-8", "replace").strip()
        if line.startswith("data:"):
            d = line[5:].strip()
            if d == "[DONE]":
                break
            try:
                chunks.append(json.loads(d))
            except ValueError:
                chunks.append({"_unparsed": d})
    return 200, chunks


def merge_stream(chunks):
    """Accumulate chunks as an OpenAI client does. Returns (message, finish_reason, header problems)."""
    msg, calls, problems, finish = {"content": "", "reasoning": ""}, {}, [], None
    for ch in chunks:
        if ch.get("error"):
            problems.append("error chunk: %s" % json.dumps(ch["error"])[:120])
        for c in ch.get("choices") or []:
            d = c.get("delta") or {}
            finish = c.get("finish_reason") or finish
            msg["content"] += d.get("content") or ""
            msg["reasoning"] += d.get("reasoning") or d.get("reasoning_content") or ""
            for tc in d.get("tool_calls") or []:
                i, f = tc.get("index", 0), tc.get("function") or {}
                if i not in calls:
                    if not tc.get("id") or not f.get("name"):
                        problems.append("call %d: first chunk has id=%r name=%r" % (i, tc.get("id"), f.get("name")))
                    calls[i] = {"id": tc.get("id"), "type": "function", "function": {"name": f.get("name") or "", "arguments": f.get("arguments") or ""}}
                else:
                    if f.get("name") and calls[i]["function"]["name"]:
                        problems.append("call %d: name sent twice (%r)" % (i, f["name"]))
                    calls[i]["function"]["name"] = calls[i]["function"]["name"] or f.get("name") or ""
                    calls[i]["id"] = calls[i]["id"] or tc.get("id")
                    calls[i]["function"]["arguments"] += f.get("arguments") or ""
    msg["tool_calls"] = [calls[k] for k in sorted(calls)]
    return msg, finish, problems


def schema_problem(name, args):
    t = next((x["function"] for x in TOOLS if x["function"]["name"] == name), None)
    if t is None:
        return "unknown tool %r" % name
    if not isinstance(args, dict):
        return "arguments are %s, not an object" % type(args).__name__
    props, req = t["parameters"]["properties"], t["parameters"].get("required", [])
    for k in req:
        if k not in args:
            return "missing %r" % k
    pyt = {"string": str, "integer": int, "object": dict}
    for k, v in args.items():
        if k in props and not isinstance(v, pyt[props[k]["type"]]) or (props.get(k, {}).get("type") == "integer" and isinstance(v, bool)):
            return "%s is %s, schema says %s" % (k, type(v).__name__, props[k]["type"])
    return None


def verdict(msg, finish, cut=False, problems=()):
    """One verdict for one answer (message dict with content, reasoning*, tool_calls)."""
    calls = msg.get("tool_calls") or []
    content = (msg.get("content") or "").strip()
    reasoning = (msg.get("reasoning") or msg.get("reasoning_content") or "").strip()
    if not calls:
        if MARKUP.search(content):
            return "markup_in_content", content[:100]
        if MARKUP.search(reasoning):
            return "call_in_reasoning", reasoning[-100:]
        if not content and not reasoning:
            return "empty", "finish_reason=%s" % finish
        return "no_call", content[:80]
    for c in calls:
        f = c.get("function") or {}
        try:
            a = json.loads(f.get("arguments") or "")
        except ValueError:
            return "bad_json", "%s: %s" % (f.get("name"), (f.get("arguments") or "")[:80])
        p = schema_problem(f.get("name"), a)
        if p and not cut:
            return "schema_mismatch", "%s: %s" % (f.get("name"), p)
    if problems:
        return "stream_header", problems[0]
    if cut and finish != "length":
        return "finish_reason", "max_tokens cut the answer but finish_reason=%r and a call came back" % finish
    if not cut and finish != "tool_calls":
        return "finish_reason", "calls came back with finish_reason=%r" % finish
    return "ok", ", ".join("%s(%s)" % ((c.get("function") or {}).get("name"), (c.get("function") or {}).get("arguments")) for c in calls)[:120]


def calls_key(msg):
    out = []
    for c in msg.get("tool_calls") or []:
        f = c.get("function") or {}
        try:
            a = json.loads(f.get("arguments") or "")
        except ValueError:
            a = f.get("arguments")
        out.append([f.get("name"), a])
    return out


def run(base, model, key, timeout, stream_too=True, extra=None):
    rows = []
    for name, prompt, opts, want in TESTS:
        body = {"model": model, "messages": [{"role": "user", "content": prompt}], "tools": TOOLS, "temperature": 0, **opts, **(extra or {})}
        body.setdefault("max_tokens", 1024)
        cut = name == "cut_short"
        st, r = post(base, key, body, False, timeout)
        if st != 200:
            rows.append([name, "non-stream", "http_%d" % st, " ".join(str(r).split())[:160]]); ns_msg = None
        else:
            ch = (r.get("choices") or [{}])[0]
            ns_msg, fin = ch.get("message") or {}, ch.get("finish_reason")
            v, d = verdict(ns_msg, fin, cut)
            if v == "ok" and want and len(ns_msg.get("tool_calls") or []) < want:
                v, d = "ok", d + " (fewer calls than asked: the model's choice)"
            rows.append([name, "non-stream", v, d])
        if not stream_too:
            continue
        st, chunks = post(base, key, dict(body, stream=True), True, timeout)
        if st != 200:
            rows.append([name, "stream", "http_%d" % st, " ".join(str(chunks).split())[:160]]); continue
        msg, fin, problems = merge_stream(chunks)
        v, d = verdict(msg, fin, cut, problems)
        if v == "ok" and ns_msg is not None and not cut and calls_key(ns_msg) and calls_key(msg) != calls_key(ns_msg) and len(calls_key(msg)) == len(calls_key(ns_msg)):
            names_same = [c[0] for c in calls_key(msg)] == [c[0] for c in calls_key(ns_msg)]
            if names_same:
                v, d = "stream_differs", "stream %s vs non-stream %s" % (json.dumps(calls_key(msg), ensure_ascii=False)[:60], json.dumps(calls_key(ns_msg), ensure_ascii=False)[:60])
        rows.append([name, "stream", v, d])
    return rows


SERVER_BUG = {"markup_in_content", "call_in_reasoning", "empty", "bad_json", "stream_header", "finish_reason"}
HINT = {
    "markup_in_content": "The server's tool parser did not read this model's call format. vLLM: check --tool-call-parser matches the model "
                         "(hermes for Qwen2.5/Qwen3 JSON calls, qwen3_coder for <function=...> calls, gemma4, llama3_json, ...). llama.cpp: start with --jinja.",
    "call_in_reasoning": "The call was written inside the thinking block. vLLM: Qwen3 parser fix #35687 is in v0.20.0; otherwise disable thinking for tool turns.",
    "empty": "Nothing came back: a parser consumed the output. vLLM: a <tool_call> section in a format the parser does not read is dropped (qwen3_coder reading JSON calls, v0.24+).",
    "http_400": "vLLM: tool_choice auto needs --enable-auto-tool-choice and --tool-call-parser.",
    "finish_reason": "Check finish_reason == 'length' before running a call: vLLM before v0.33.0 reports 'tool_calls' for a call cut by max_tokens.",
    "stream_header": "Clients that build calls from stream chunks need id and function.name in the first chunk of each call.",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base-url", required=True, help="e.g. http://localhost:8000/v1")
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--no-stream", action="store_true", help="skip the streaming requests")
    ap.add_argument("--extra", default=None, help='extra JSON merged into every request, e.g. \'{"chat_template_kwargs": {"enable_thinking": false}}\'')
    ap.add_argument("--json", default=None, help="also write the rows to this file")
    a = ap.parse_args()
    t0 = time.time()
    rows = run(a.base_url, a.model, a.api_key, a.timeout, not a.no_stream, json.loads(a.extra) if a.extra else None)
    w = max(len(r[0]) for r in rows)
    for r in rows:
        print("%-*s  %-10s  %-17s  %s" % (w, r[0], r[1], r[2], r[3]))
    seen = sorted({r[2] for r in rows if r[2] in HINT or r[2].startswith("http_")})
    for v in seen:
        if v in HINT:
            print("\n%s: %s" % (v, HINT[v]))
    bad = [r for r in rows if r[2] in SERVER_BUG or r[2].startswith("http_")]
    print("\n%d requests in %.0f s; %d answers point at the server, not the model." % (len(rows), time.time() - t0, len(bad)))
    if a.json:
        json.dump({"base_url": a.base_url, "model": a.model, "rows": rows}, open(a.json, "w"), ensure_ascii=False, indent=1)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
