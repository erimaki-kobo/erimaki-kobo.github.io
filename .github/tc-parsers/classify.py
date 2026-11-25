"""Shared by the page builder and toolcheck.py's self-test: turn what a parser (or a server) returned into a verdict.

verdict codes
  ok                 the calls and the content a client should get
  markup_in_content  no tool call; the model's tool-call markup is in message.content
  no_call            no tool call and no markup in content (the call vanished)
  wrong_calls        tool calls came out, but not the ones in the model output (count, name or arguments differ)
  bad_json           a call's arguments are not valid JSON
  content_lost       the calls are right but text the model wrote before the call is missing from content
  extra_content      the calls are right but content holds something besides the model's own text
  stream_header      streaming: a call's first delta lacks id, type or name, or the name/id is sent twice
  exception          the parser raised
For a truncated output (no complete call in it), `partial_call` means a call came out anyway, with arguments cut short."""
import json, re

MARKUP = re.compile(r"<\|?tool_call|tool_call\|?>|<function=|<\|tool_calls?_|<｜tool|<arg_key>|<minimax:tool_call>|<invoke |\[TOOL_CALLS\]|\"name\"\s*:\s*\"(get_weather|search)\"|\b(get_weather|search)\(")


def norm_content(c):
    c = (c or "").strip()
    return c or None


def parse_args(a):
    try:
        return True, json.loads(a) if isinstance(a, str) else a
    except Exception:
        return False, None


def judge(calls, content, want, want_content, truncated=False):
    """calls: [{"name", "arguments"(str)}]; returns (code, detail)."""
    content = norm_content(content)
    if truncated:
        if calls:
            ok, a = parse_args(calls[0].get("arguments"))
            return ("partial_call", "%s(%s)" % (calls[0].get("name"), json.dumps(a, ensure_ascii=False) if ok else repr(calls[0].get("arguments"))))
        if content and MARKUP.search(content):
            return ("markup_in_content", content[:60])
        return ("no_call", content or "")
    if want and not calls:
        if content and MARKUP.search(content):
            return ("markup_in_content", content[:80])
        return ("no_call", content or "")
    for c in calls:
        ok, _ = parse_args(c.get("arguments"))
        if not ok:
            return ("bad_json", "%s: %s" % (c.get("name"), str(c.get("arguments"))[:60]))
    got = [[c.get("name"), parse_args(c.get("arguments"))[1]] for c in calls]
    if got != [list(w) for w in want]:
        return ("wrong_calls", json.dumps(got, ensure_ascii=False)[:120])
    if want_content and content != want_content:
        return ("content_lost", content or "") if not content or want_content not in content else ("extra_content", content[:80])
    if not want_content and content:
        return ("extra_content", content[:80])
    return ("ok", "")


def rebuild_stream(deltas):
    """Accumulate streamed DeltaMessages the way an OpenAI client does; returns (calls, content, header_problems)."""
    calls, content, problems = {}, "", []
    for d in deltas:
        if d.get("content"):
            content += d["content"]
        for tc in d.get("tool_calls") or []:
            i = tc.get("index", 0)
            f = tc.get("function") or {}
            if i not in calls:
                if not tc.get("id") or not f.get("name") or (tc.get("type") not in (None, "function")):
                    problems.append("call %d: first delta has id=%r name=%r" % (i, tc.get("id"), f.get("name")))
                if tc.get("type") is None:
                    pass
                calls[i] = {"id": tc.get("id"), "name": f.get("name") or "", "arguments": f.get("arguments") or ""}
            else:
                if f.get("name") and calls[i]["name"]:
                    problems.append("call %d: name sent again (%r)" % (i, f.get("name")))
                if f.get("name") and not calls[i]["name"]:
                    calls[i]["name"] = f["name"]
                if tc.get("id") and calls[i]["id"] and tc.get("id") != calls[i]["id"]:
                    problems.append("call %d: a second id" % i)
                calls[i]["id"] = calls[i]["id"] or tc.get("id")
                calls[i]["arguments"] += f.get("arguments") or ""
    return [calls[k] for k in sorted(calls)], content, problems


def judge_stream(deltas, want, want_content, truncated=False):
    calls, content, problems = rebuild_stream(deltas)
    code, detail = judge(calls, content, want, want_content, truncated)
    if code == "ok" and problems:
        return ("stream_header", problems[0])
    return (code, detail)
