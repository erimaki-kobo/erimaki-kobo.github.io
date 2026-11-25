"""Replay each engine's context-overflow response (status + body, taken from the
engine's source) to openai-python and LiteLLM, and record what the client does.

usage: venv/bin/python replay.py cases.json > replay_results.json
Every case is served by a local mock server; the number of HTTP requests the
client sent tells whether it retried.
"""
import json, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CASES = json.load(open(sys.argv[1]))
STATE = {"case": None, "hits": 0}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        self.rfile.read(n)
        STATE["hits"] += 1
        c = STATE["case"]
        if c.get("sse"):
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.end_headers()
            for ev in c["sse"]:
                self.wfile.write(("data: " + (ev if isinstance(ev, str) else json.dumps(ev)) + "\n\n").encode())
            self.wfile.flush()
            return
        body = c["body"]
        raw = body if isinstance(body, str) else json.dumps(body)
        self.send_response(c["status"])
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw.encode())))
        self.end_headers()
        self.wfile.write(raw.encode())


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{port}"

import openai
import litellm
litellm.suppress_debug_info = True
litellm.num_retries = 0

MSG = [{"role": "user", "content": "hi"}]


def run(fn):
    STATE["hits"] = 0
    t = time.time()
    try:
        r = fn()
        if hasattr(r, "__iter__") and not isinstance(r, (dict, str)):
            chunks = [x for x in r]
            out = {"raised": None, "chunks": len(chunks),
                   "first_chunk": (chunks[0].model_dump() if chunks and hasattr(chunks[0], "model_dump") else None)}
        else:
            out = {"raised": None}
    except Exception as e:  # record the class the caller would have to catch
        out = {"raised": type(e).__name__,
               "mro": [k.__name__ for k in type(e).__mro__[:6]],
               "message": str(e)[:300]}
    out["requests"] = STATE["hits"]
    out["seconds"] = round(time.time() - t, 2)
    return out


results = []
for c in CASES:
    STATE["case"] = c
    stream = bool(c.get("sse"))
    row = {"id": c["id"]}
    path = c.get("path", "/v1/chat/completions")
    if path == "/v1/chat/completions":
        cl = openai.OpenAI(base_url=BASE + "/v1", api_key="x")  # default max_retries=2
        row["openai_python"] = run(lambda: cl.chat.completions.create(model="m", messages=MSG, stream=stream))
        for prov in ["openai", "hosted_vllm"]:
            row["litellm_" + prov] = run(lambda: litellm.completion(
                model=f"{prov}/m", api_base=BASE + "/v1", api_key="x", messages=MSG, stream=stream, max_retries=0))
    if path == "/api/chat":
        row["litellm_ollama_chat"] = run(lambda: litellm.completion(
            model="ollama_chat/m", api_base=BASE, messages=MSG, stream=stream))
    results.append(row)
    print(c["id"], json.dumps({k: (v.get("raised"), v.get("requests")) for k, v in row.items() if k != "id"}), file=sys.stderr)

import importlib.metadata as md
print(json.dumps({"openai": md.version("openai"), "litellm": md.version("litellm"), "results": results}, indent=1))
