#!/usr/bin/env python3
"""cachecheck.py - find out why llama-server re-processes the whole prompt.

Standard library only. Works against a running llama-server (any recent build
with /apply-template and /tokenize) and/or its log and the GGUF file.

  # 1. where do two consecutive requests stop sharing tokens?
  python cachecheck.py diff turn1.json turn2.json --server http://127.0.0.1:8080
  #    or two prompts written by llama-server --log-prompts-dir DIR (build b9577+)
  python cachecheck.py diff DIR/000001.txt DIR/000002.txt --server http://127.0.0.1:8080

  # 2. send them for real and compare what the server reused with what it could have reused
  python cachecheck.py live turn1.json turn2.json --server http://127.0.0.1:8080

  # 3. explain the cache lines in a server log (start the server with -lv 4 to see them all)
  python cachecheck.py log server.log

  # 4. what kind of memory does this model have (full attention, SWA, recurrent, hybrid)?
  python cachecheck.py gguf model.gguf

A request file is the JSON body you POST to /v1/chat/completions (messages, tools, ...)
or to /completion ({"prompt": "..."}). For `live`, turn2.json may contain the literal
string "{{REPLY}}" in an assistant message; it is replaced by the text the server
returned for turn1, the way a chat client would send it back.
"""
import argparse
import json
import re
import struct
import sys
import urllib.error
import urllib.request

# ---------------------------------------------------------------- HTTP helpers


def post(server, path, body, timeout=600):
    req = urllib.request.Request(server.rstrip("/") + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit("%s %s -> HTTP %d: %s" % ("POST", path, e.code, e.read()[:300].decode("utf-8", "replace")))


def get(server, path, timeout=30):
    try:
        with urllib.request.urlopen(server.rstrip("/") + path, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:  # /slots can be disabled with --no-slots
        return None


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render(server, body):
    """The exact text llama-server will tokenize for this request."""
    if "messages" in body:
        return post(server, "/apply-template", body)["prompt"]
    p = body.get("prompt", "")
    if not isinstance(p, str):
        raise SystemExit("only string prompts are supported for /completion bodies")
    return p


def tokenize(server, text):
    r = post(server, "/tokenize", {"content": text, "add_special": True, "parse_special": True,
                                    "with_pieces": True})
    ids, pieces = [], []
    for t in r["tokens"]:
        if isinstance(t, dict):
            ids.append(t["id"])
            p = t["piece"]
            pieces.append(p.encode("utf-8") if isinstance(p, str) else bytes(p))
        else:
            ids.append(t)
            pieces.append(b"?")
    return ids, pieces


def lcp(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def show(pieces, i, width):
    lo, hi = max(0, i - width), min(len(pieces), i + width)
    left = b"".join(pieces[lo:i]).decode("utf-8", "replace").lstrip("�")
    right = b"".join(pieces[i:hi]).decode("utf-8", "replace")
    return (left + " ┃ " + right).replace("▁", " ").replace("\n", "\\n")


# ---------------------------------------------------------------- diff


def prompt_text(server, path):
    """A .txt file is an already rendered prompt (e.g. from llama-server --log-prompts-dir);
    anything else is a JSON request body."""
    if path.endswith(".txt"):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return render(server, load(path))


def cmd_diff(a, server, width=12, quiet=False):
    ta, tb = prompt_text(server, a.turn1), prompt_text(server, a.turn2)
    if a.offline:
        c = lcp(ta, tb)
        print("offline: comparing characters only (%d and %d chars), shared prefix %d chars" % (len(ta), len(tb), c))
        print("  turn 1: %r" % ta[max(0, c - 40):c + 40])
        print("  turn 2: %r" % tb[max(0, c - 40):c + 40])
        return {"common_prefix_chars": c}, None
    ia, pa = tokenize(server, ta)
    ib, pb = tokenize(server, tb)
    n = lcp(ia, ib)
    res = {"turn1_tokens": len(ia), "turn2_tokens": len(ib), "common_prefix": n}
    if quiet:
        return res, (ia, ib)
    print("turn 1: %d tokens   turn 2: %d tokens   shared prefix: %d tokens" % (len(ia), len(ib), n))
    if n == len(ia):
        print("OK  turn 2 starts with all of turn 1. The cache can be reused up to token %d;" % n)
        print("    the assistant reply the server generated is cached too, so the real reuse can be larger.")
    else:
        print("PREFIX CHANGED at token %d of %d (%.0f%% into turn 1)." % (n, len(ia), 100.0 * n / max(1, len(ia))))
        print("  turn 1: ..." + show(pa, n, width))
        print("  turn 2: ..." + show(pb, n, width))
        c = lcp(ta, tb)
        print("  first differing character: offset %d" % c)
        print("  turn 1: %r" % ta[max(0, c - 40):c + 40])
        print("  turn 2: %r" % tb[max(0, c - 40):c + 40])
        print("  Every token after this point must be processed again on any model.")
        print("  On SWA / hybrid / recurrent models it is often the WHOLE prompt (see `gguf` and the table on the page).")
    return res, (ia, ib)


# ---------------------------------------------------------------- live


def complete(server, body):
    body = dict(body)
    body["stream"] = False
    body.setdefault("cache_prompt", True)
    path = "/v1/chat/completions" if "messages" in body else "/completion"
    r = post(server, path, body)
    t = r.get("timings") or {}
    if "messages" in body:
        text = r["choices"][0]["message"].get("content") or ""
    else:
        text = r.get("content", "")
    return text, t, r


def fill_reply(body, reply):
    s = json.dumps(body)
    return json.loads(s.replace("{{REPLY}}", json.dumps(reply)[1:-1]))


def slot_snapshot(server):
    s = get(server, "/slots")
    if not isinstance(s, list):
        return None
    return {x.get("id"): x.get("id_task") for x in s}


def cmd_live(a, server):
    b1, b2 = load(a.turn1), load(a.turn2)
    props = get(server, "/props") or {}
    print("server build: %s   slots: %s" % (props.get("build_info", "?"), props.get("total_slots", "?")))
    s0 = slot_snapshot(server)
    reply, t1, _ = complete(server, b1)
    s1 = slot_snapshot(server)
    b2 = fill_reply(b2, reply)
    # what the second request shares with the first one, token by token
    ta, tb = render(server, b1), render(server, b2)
    ia, _ = tokenize(server, ta)
    ib, pb = tokenize(server, tb)
    n = lcp(ia, ib)
    _, t2, _ = complete(server, b2)
    s2 = slot_snapshot(server)

    c2, p2 = t2.get("cache_n"), t2.get("prompt_n")
    print("turn 1: %d prompt tokens, cache_n %s, prompt_n %s" % (len(ia), t1.get("cache_n"), t1.get("prompt_n")))
    print("turn 2: %d prompt tokens, cache_n %s, prompt_n %s" % (len(ib), c2, p2))
    print("shared prefix of the two rendered prompts: %d tokens%s" % (
        n, " (all of turn 1)" if n == len(ia) else " (turn 1 has %d)" % len(ia)))
    if c2 is None:
        print("no timings in the response: this build is too old for `live`; use `diff` and `log`.")
        return 2
    slot1 = [k for k in (s1 or {}) if s0 is not None and s1[k] != s0.get(k)]
    slot2 = [k for k in (s2 or {}) if s1 is not None and s2[k] != s1.get(k)]
    verdict, code = classify(len(ia), len(ib), n, c2, slot1, slot2)
    print("\nVERDICT: " + verdict)
    if n < len(ia):
        print("  divergence: ..." + show(pb, n, 10))
    return code


def classify(n1, n2, shared, cache_n, slot1, slot2):
    """Return (verdict, exit code). n1/n2: prompt tokens of turn 1/2, shared: common prefix of the
    two rendered prompts, cache_n: tokens the server reused for turn 2 (timings.cache_n)."""
    other_slot = bool(slot1 and slot2 and slot1 != slot2)
    lost = max(0, shared - cache_n)
    if shared < n1:
        head = ("CLIENT CHANGED THE PREFIX at token %d of %d: the request itself differs from turn 1 there "
                "(system prompt, tool list, rewritten or trimmed history). " % (shared, n1))
        if cache_n > shared + 1:
            return head + ("The server reused %d tokens, more than the %d shared ones: --cache-reuse shifted cached "
                           "chunks that follow the change (it only works when text was removed)." % (cache_n, shared)), 1
        if cache_n >= shared - 1:
            return head + "The server reused all %d shared tokens; fix the client." % shared, 1
        if cache_n <= 1:
            return head + ("On top of that the server reused nothing (cache_n %d): with SWA / hybrid / recurrent "
                           "memory there was no context checkpoint before token %d, so the WHOLE prompt was "
                           "re-processed. Fixing the client fixes both." % (cache_n, shared)), 1
        return head + ("The server rolled back to a context checkpoint at %d, %d tokens before the change "
                       "(SWA / hybrid / recurrent memory)." % (cache_n, lost)), 1
    if cache_n >= shared - 1:
        return "OK. The server reused %d tokens (turn 2 extends turn 1, shared prefix %d)." % (cache_n, shared), 0
    if other_slot:
        return ("DIFFERENT SLOT. Turn 1 ran on slot %s and turn 2 on slot %s. Pin the conversation with "
                "\"id_slot\", run -np 1, or keep --cache-ram on so the prompt can be restored from host "
                "memory." % (slot1, slot2)), 3
    if cache_n <= 1:
        return ("FULL RE-PROCESSING ON THE SERVER SIDE. Turn 2 extends turn 1 (%d shared tokens) but cache_n is "
                "%d: the cached state was not usable and no context checkpoint was either. Check -lv 4 logs for "
                "'forcing full prompt re-processing', the slot that served each turn, and --cache-ram / "
                "--ctx-checkpoints." % (shared, cache_n)), 4
    return ("PARTIAL REUSE. Turn 2 extends turn 1, %d tokens reused of %d: the server rolled back to a context "
            "checkpoint %d tokens earlier (normal for SWA / hybrid / recurrent memory; small)." % (
                cache_n, shared, lost)), 5 if lost > 64 else 0


# ---------------------------------------------------------------- log

LOG_RULES = [
    (r"forcing full prompt re-processing due to lack of cache data",
     "No usable cached state at the divergence point -> whole prompt re-processed. SWA/hybrid/recurrent model and "
     "no checkpoint before the first changed token. Find out WHY the prompt changed (`diff`), or for SWA use --swa-full."),
    (r"erased invalidated context checkpoint",
     "A checkpoint covered tokens that the new prompt does not share, so it was dropped. Many of these per turn "
     "= the prompt changes early (client side)."),
    (r"restored context checkpoint",
     "Rolled back to a checkpoint: only the tokens after it are re-processed (partial reuse, expected)."),
    (r"created context checkpoint",
     "A checkpoint was saved (near the end of the prompt and at user-message starts)."),
    (r"erasing old context checkpoint",
     "The per-slot list is full (--ctx-checkpoints); the oldest was dropped."),
    (r"cache reuse is not supported",
     "--cache-reuse (KV shifting) does not work for this model / multimodal; it is ignored."),
    (r"exceeds cache size limit",
     "This prompt's state is larger than --cache-ram; it is not saved to the host prompt cache."),
    (r"selected slot by LRU",
     "No slot matched the prompt well enough; the least recently used slot was taken (can mean another conversation's "
     "slot -> its cache is lost unless --cache-ram keeps it)."),
    (r"selected slot by LCP similarity",
     "Slot chosen because its cached prompt matches this one."),
    (r"swa_full is not supported by this model",
     "--swa-full given for a model without SWA: it does nothing."),
    (r"print_info: n_swa\s*=", "Sliding window size of this model (0 = no SWA)."),
    (r"need to evaluate at least 1 token",
     "Prompt identical to the cache: 1 token is re-evaluated to get logits (harmless)."),
]


def cmd_log(a):
    counts = {}
    first = {}
    with open(a.logfile, encoding="utf-8", errors="replace") as f:
        for line in f:
            for pat, _ in LOG_RULES:
                if re.search(pat, line):
                    counts[pat] = counts.get(pat, 0) + 1
                    first.setdefault(pat, line.strip()[:200])
    if not counts:
        print("No prompt-cache lines found. Since build b9829 most of them are trace level: restart llama-server "
              "with -lv 4 (or -v) and send the two requests again.")
        return 1
    trace = ("forcing full", "erased invalidated", "restored context", "created context")
    if not any(k in p for p in counts for k in trace):
        print("NOTE: no checkpoint lines in this log. Since build b9829 (2026-06-28) they are trace level and hidden "
              "at the default -lv 3. Restart llama-server with -lv 4 to see them.\n")
    for pat, why in LOG_RULES:
        if pat in counts:
            print("[%dx] %s\n      e.g. %s\n      -> %s\n" % (counts[pat], pat, first[pat], why))
    return 0


# ---------------------------------------------------------------- gguf (header only)

RECURRENT = {"mamba", "mamba2", "rwkv6", "rwkv6qwen2", "rwkv7", "arwkv7"}
HYBRID = {"jamba", "falcon-h1", "plamo2", "granitehybrid", "lfm2", "lfm2moe", "lfm3", "zaya1", "nemotron_h",
          "nemotron_h_moe", "metis16", "qwen3next", "kimi-linear", "bailingmoe3", "kimi-k3", "kimi-k31", "glm5-next",
          "qwen35", "qwen35moe", "clover_moe", "qwen4exp", "deepseek4", "deepseek41", "minimax-01", "zonos3",
          "inkling2", "inkling2_loop"}
SWA_DEFAULT = {"gemma2", "gemma3", "gemma3n", "gemma4", "cohere2"}  # SWA even without the key in some files


def read_gguf_kv(path):
    fmt = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}
    with open(path, "rb") as f:
        if f.read(4) != b"GGUF":
            raise SystemExit("not a GGUF file")
        ver, = struct.unpack("<I", f.read(4))
        if ver < 2:
            raise SystemExit("GGUF v1 is not supported")
        _, n_kv = struct.unpack("<QQ", f.read(16))

        def rstr():
            n, = struct.unpack("<Q", f.read(8))
            return f.read(n).decode("utf-8", "replace")

        def rval(t):
            if t == 8:
                return rstr()
            if t == 9:
                et, n = struct.unpack("<IQ", f.read(12))
                if et == 8:
                    out = [rstr() for _ in range(n)]
                else:
                    sz = struct.calcsize(fmt[et])
                    out = [struct.unpack(fmt[et], f.read(sz))[0] for _ in range(n)]
                return out if n <= 64 else "[%d items]" % n
            return struct.unpack(fmt[t], f.read(struct.calcsize(fmt[t])))[0]

        kv = {}
        for _ in range(n_kv):
            k = rstr()
            t, = struct.unpack("<I", f.read(4))
            kv[k] = rval(t)
        return kv


def cmd_gguf(a):
    kv = read_gguf_kv(a.model)
    arch = kv.get("general.architecture", "?")
    swa = kv.get(arch + ".attention.sliding_window")
    print("architecture: %s" % arch)
    if arch in RECURRENT:
        kind = "recurrent"
    elif arch in HYBRID:
        kind = "hybrid (recurrent/linear-attention layers + attention layers)"
    elif swa or arch in SWA_DEFAULT:
        kind = "SWA (sliding-window attention, window %s)" % (swa if swa else "set in code")
    else:
        kind = "full attention"
    print("memory: " + kind)
    if kind == "full attention":
        print("-> llama-server can always reuse the cache up to the first changed token. If it re-processes "
              "everything, the prompt changed near the start or the request went to another slot.")
    elif kind.startswith("SWA"):
        print("-> without --swa-full only the last window of KV is kept: going back further needs a context "
              "checkpoint. --swa-full keeps all KV (more memory) and makes reuse behave like full attention.")
    else:
        print("-> the recurrent state cannot be rolled back. Reuse needs the new prompt to extend the cached one, "
              "or a context checkpoint before the first changed token. --swa-full does not help.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("diff", "live"):
        p = sp.add_parser(name)
        p.add_argument("turn1")
        p.add_argument("turn2")
        p.add_argument("--server", default="http://127.0.0.1:8080")
        if name == "diff":
            p.add_argument("--offline", action="store_true",
                           help="no server: compare the two .txt prompts character by character")
    p = sp.add_parser("log")
    p.add_argument("logfile")
    p = sp.add_parser("gguf")
    p.add_argument("model")
    a = ap.parse_args()
    if a.cmd == "diff":
        cmd_diff(a, a.server)
        return 0
    if a.cmd == "live":
        return cmd_live(a, a.server)
    if a.cmd == "log":
        return cmd_log(a)
    return cmd_gguf(a)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:  # e.g. piped into head
        sys.exit(0)
