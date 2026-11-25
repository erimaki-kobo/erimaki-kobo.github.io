"""Self-test of toolcheck.py: a local server answers with what vLLM's own parsers returned for a model output (results of
run_parsers.py), shaped as vLLM's chat server shapes it, and toolcheck.py's verdicts are compared with classify.py's.

usage: python3 selftest.py res/ out.json   (res/<tag>.json from run_parsers.py)"""
import http.server, importlib.util, json, os, sys, threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from classify import judge, judge_stream  # noqa: E402
from scenarios import FORMATS  # noqa: E402

spec = importlib.util.spec_from_file_location("toolcheck", os.path.join(HERE, "..", "toolcheck.py"))
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)
key = lambda v: tuple(int(x) for x in v[1:].split("."))
CASE = {"auto": "single", "required": "single", "parallel": "parallel", "nested_args": "nested_unicode", "cut_short": "truncated"}
STATE = {}


def finish_for(version, has_calls, cut):
    """vLLM's rule: before v0.33.0 any parsed call gives "tool_calls"; from v0.33.0 (#59324) a length cut stays "length"."""
    if has_calls and (not cut or key(version) < key("v0.33.0")):
        return "tool_calls"
    return "length" if cut else "stop"


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = body["messages"][0]["content"]
        test = next(t[0] for t in tc.TESTS if t[1] == prompt)
        v, fam = STATE["version"], STATE["family"]
        r = STATE["res"][v]["parsers"][fam]["cases"][CASE[test]]
        cut = test == "cut_short"
        if not body.get("stream"):
            x = r["nonstream"]
            calls = [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}} for c in x["calls"]]
            msg = {"role": "assistant", "content": x["content"], "tool_calls": calls}
            out = {"choices": [{"index": 0, "message": msg, "finish_reason": finish_for(v, bool(calls), cut)}]}
            b = json.dumps(out).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            return
        x = r["stream"]
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        any_call = False
        for d in x["deltas"]:
            delta = {k: d[k] for k in ("content", "tool_calls") if d.get(k) is not None}
            if delta.get("tool_calls"):
                any_call = True
                delta["tool_calls"] = [{k: v2 for k, v2 in t.items() if v2 is not None} for t in delta["tool_calls"]]
            self.wfile.write(b"data: " + json.dumps({"choices": [{"index": 0, "delta": delta, "finish_reason": None}]}).encode() + b"\n\n")
        self.wfile.write(b"data: " + json.dumps({"choices": [{"index": 0, "delta": {}, "finish_reason": finish_for(v, any_call, cut)}]}).encode() + b"\n\n")
        self.wfile.write(b"data: [DONE]\n\n")


def expected(v, fam, test, mode, res):
    """What toolcheck.py should say, from classify.py's verdict on the same parser result."""
    c = FORMATS[fam]["cases"][CASE[test]]
    x = res[v]["parsers"][fam]["cases"][CASE[test]][mode]
    cut = test == "cut_short"
    if mode == "nonstream":
        code, _ = judge(x["calls"], x["content"], c["want"] or [], c["content"], cut)
        has = bool(x["calls"])
    else:
        code, _ = judge_stream(x["deltas"], c["want"] or [], c["content"], cut)
        has = any(d.get("tool_calls") for d in x["deltas"])
    if cut:
        if code == "partial_call":
            from classify import rebuild_stream, parse_args
            calls = x["calls"] if mode == "nonstream" else rebuild_stream(x["deltas"])[0]
            if not parse_args(calls[0]["arguments"])[0]:
                return {"bad_json"}
            return {"finish_reason"} if key(v) < key("v0.33.0") else {"ok"}
        return {"markup_in_content"} if code == "markup_in_content" else {"empty", "no_call"}
    return {{"ok": "ok", "markup_in_content": "markup_in_content", "no_call": "empty", "bad_json": "bad_json", "stream_header": "stream_header"}.get(code, "?" + code)}


def main():
    res = {f[:-5]: json.load(open(os.path.join(sys.argv[1], f))) for f in os.listdir(sys.argv[1]) if f.endswith(".json")}
    STATE["res"] = res
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d/v1" % srv.server_address[1]
    n = agree = 0
    bad = []
    for v in sorted(res, key=key):
        for fam in FORMATS:
            if "error" in res[v]["parsers"][fam]:
                continue
            STATE["version"], STATE["family"] = v, fam
            for test, mode, got, detail in tc.run(base, "m", None, 30):
                m = "nonstream" if mode == "non-stream" else "stream"
                exp = expected(v, fam, test, m, res)
                n += 1
                if got in exp:
                    agree += 1
                else:
                    bad.append([v, fam, test, mode, got, sorted(exp), detail])
    srv.shutdown()
    json.dump({"answers": n, "agree": agree, "disagree": bad}, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    print("toolcheck verdicts agreeing with the parser-level verdict: %d of %d" % (agree, n))
    for b in bad[:15]:
        print("  ", b)


if __name__ == "__main__":
    main()
