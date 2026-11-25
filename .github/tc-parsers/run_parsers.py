"""usage: <venv python> run_parsers.py <vllm source tree of one release> > results.json

Runs vLLM's own tool parsers (the code of that release) on fixed model outputs, without a GPU, torch or a model:
modules that only the engine needs (torch, the compiled extension, model code) are stubbed by stubload.py; the parser
code itself runs as released. For each parser and each model output it records what extract_tool_calls returns
(non-streaming) and what extract_tool_calls_streaming returns when the same text arrives in pieces (streaming).

The tokenizer is a stand-in (as in vLLM's own parser tests): the parser's special tokens are single tokens, other text
is split into words, spaces and single punctuation characters. Real tokenizers cut text differently, so a streaming
result here is for this split only."""
import json, os, re, sys, traceback, warnings

warnings.simplefilter("ignore")
REAL, sys.stdout = sys.stdout, open(os.devnull, "w")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubload  # noqa: E402

stubload.install(sys.argv[1])
import logging  # noqa: E402

logging.disable(logging.CRITICAL)

from scenarios import FORMATS, TOOLS  # noqa: E402

try:
    from vllm.tool_parsers import ToolParserManager
except ImportError:
    from vllm.entrypoints.openai.tool_parsers import ToolParserManager
REQ = None
for mod in ("vllm.entrypoints.openai.chat_completion.protocol", "vllm.entrypoints.openai.protocol"):
    try:
        REQ = __import__(mod, fromlist=["ChatCompletionRequest"]).ChatCompletionRequest
        break
    except (ImportError, AttributeError):
        continue

SPECIAL_RE = re.compile(r"<\|[^<>\s]{0,40}?>|<[^<>\s|]{1,40}\|>|<[A-Za-z_:/]{2,40}>|<｜[^｜]{1,40}｜>|\[TOOL_CALLS\]|\[ARGS\]|\[CALL_ID\]")


class FakeTokenizer:
    """Special tokens are single ids; other text is cut into words, spaces and single punctuation characters."""

    def __init__(self, specials):
        self.specials = sorted(set(specials), key=len, reverse=True)
        self._v = {}
        for s in self.specials:
            self._id(s)
        self.all_special_tokens = list(self.specials)
        self.all_special_ids = [self._v[s] for s in self.specials]
        pat = "|".join(re.escape(s) for s in self.specials)
        self._split = re.compile(("(%s)|" % pat if pat else "") + r"(\w+|\s+|.)", re.S)
        self.model_max_length = 1 << 20
        self.name_or_path = "fake"
        self.eos_token_id = self._id("<eos>")
        self.bos_token_id = self._id("<bos>")

    def _id(self, piece):
        if piece not in self._v:
            self._v[piece] = len(self._v) + 1000
        return self._v[piece]

    @property
    def vocab(self):
        return dict(self._v)

    def get_vocab(self):
        return dict(self._v)

    def __len__(self):
        return len(self._v)

    @property
    def vocab_size(self):
        return len(self._v)

    def pieces(self, text):
        return [m.group(0) for m in self._split.finditer(text)]

    def tokenize(self, text, **k):
        return self.pieces(text)

    def encode(self, text, add_special_tokens=False, **k):
        return [self._id(p) for p in self.pieces(text)]

    def decode(self, ids, skip_special_tokens=False, **k):
        inv = {v: s for s, v in self._v.items()}
        if isinstance(ids, int):
            ids = [ids]
        return "".join(inv.get(i, "") for i in ids if not (skip_special_tokens and inv.get(i) in self.specials))

    def convert_tokens_to_ids(self, t):
        if isinstance(t, list):
            return [self.convert_tokens_to_ids(x) for x in t]
        return self._v.get(t)

    def convert_ids_to_tokens(self, ids, skip_special_tokens=False):
        inv = {v: s for s, v in self._v.items()}
        return [inv.get(i) for i in ids] if isinstance(ids, list) else inv.get(ids)

    def convert_tokens_to_string(self, toks):
        return "".join(t or "" for t in toks)

    def __call__(self, text, **k):
        return {"input_ids": self.encode(text)}

    def get_added_vocab(self):
        return {s: self._v[s] for s in self.specials}

    def __bool__(self):
        return True


def plain(x):
    if x is None or isinstance(x, (str, int, float, bool)):
        return x
    if isinstance(x, (list, tuple)):
        return [plain(y) for y in x]
    if isinstance(x, dict):
        return {k: plain(v) for k, v in x.items()}
    if hasattr(x, "model_dump"):
        return plain(x.model_dump())
    return repr(x)


def calls_of(tc):
    out = []
    for c in tc or []:
        f = getattr(c, "function", None)
        out.append({"id": getattr(c, "id", None), "type": getattr(c, "type", None), "name": getattr(f, "name", None), "arguments": getattr(f, "arguments", None)})
    return out


def specials_for(parser_cls, texts):
    sp = set()
    for t in texts:
        sp.update(SPECIAL_RE.findall(t))
    for k in dir(parser_cls):
        try:
            v = getattr(parser_cls, k)
        except Exception:
            continue
        if isinstance(v, str) and 2 < len(v) < 60 and SPECIAL_RE.fullmatch(v):
            sp.add(v)
    return sp


def run_one(cls, fmt, text, streaming):
    tok = FakeTokenizer(specials_for(cls, [s["text"] for s in FORMATS[fmt]["cases"].values()]))
    req = REQ(messages=[{"role": "user", "content": "hi"}], model="m", tools=[{"type": "function", "function": t} for t in TOOLS], tool_choice="auto")
    try:   # as vLLM's chat server does: self.tool_parser(tokenizer, request.tools)
        parser = cls(tok, req.tools)
    except TypeError:
        parser = cls(tok)
    if not streaming:
        r = parser.extract_tool_calls(text, req)
        return {"tools_called": bool(r.tools_called), "content": r.content, "calls": calls_of(r.tool_calls)}
    ids = tok.encode(text)
    prev_text, prev_ids, deltas = "", [], []
    for i in range(len(ids)):
        cur_ids = ids[: i + 1]
        cur_text = tok.decode(cur_ids)
        d_text = cur_text[len(prev_text):]
        d = parser.extract_tool_calls_streaming(prev_text, cur_text, d_text, prev_ids, cur_ids, [ids[i]], req)
        if d is not None:
            deltas.append(plain(d))
        prev_text, prev_ids = cur_text, cur_ids
    return {"deltas": deltas, "pieces": len(ids)}


out = {"parsers": {}}
for fmt, spec in FORMATS.items():
    try:
        cls = ToolParserManager.get_tool_parser(spec["parser"])
    except Exception as e:
        out["parsers"][fmt] = {"error": "%s: %s" % (type(e).__name__, str(e)[:200])}
        continue
    res = {"class": "%s.%s" % (cls.__module__, cls.__name__), "cases": {}}
    for case, c in spec["cases"].items():
        r = {}
        for mode in ("nonstream", "stream"):
            try:
                r[mode] = run_one(cls, fmt, c["text"], mode == "stream")
            except Exception as e:
                tb = traceback.extract_tb(e.__traceback__)
                where = next((f"{os.path.relpath(f.filename, sys.argv[1])}:{f.lineno}" for f in reversed(tb) if "/vllm/" in f.filename), "")
                r[mode] = {"exception": "%s: %s" % (type(e).__name__, " ".join(str(e).split())[:200]), "where": where}
        res["cases"][case] = r
    out["parsers"][fmt] = res
# which parser reads which model family's output (the "single" output of every family, non-streaming)
cross = {}
for pf, spec in FORMATS.items():
    if "error" in out["parsers"].get(pf, {}):
        continue
    cls = ToolParserManager.get_tool_parser(spec["parser"])
    for of, ospec in FORMATS.items():
        t = ospec["cases"]["single"]["text"]
        try:
            tok = FakeTokenizer(specials_for(cls, [t] + [x["text"] for x in spec["cases"].values()]))   # the parser's own tokens exist, as in its model's tokenizer
            req = REQ(messages=[{"role": "user", "content": "hi"}], model="m", tools=[{"type": "function", "function": x} for x in TOOLS], tool_choice="auto")
            try:
                parser = cls(tok, req.tools)
            except TypeError:
                parser = cls(tok)
            r = parser.extract_tool_calls(t, req)
            cross["%s|%s" % (pf, of)] = {"content": r.content, "calls": calls_of(r.tool_calls)}
        except Exception as e:
            cross["%s|%s" % (pf, of)] = {"exception": "%s: %s" % (type(e).__name__, str(e)[:120])}
out["cross"] = cross
# reasoning parser "qwen3" first, then the tool parser on the content it leaves (non-streaming), as the chat server does
from vllm.reasoning import ReasoningParserManager  # noqa: E402
CALL_H = '<tool_call>\n{"name": "get_weather", "arguments": {"city": "Tokyo", "days": 3}}\n</tool_call>'
CALL_C = "<tool_call>\n<function=get_weather>\n<parameter=city>\nTokyo\n</parameter>\n<parameter=days>\n3\n</parameter>\n</function>\n</tool_call>"
REASON = {
    "closed": "<think>\nThe user wants the weather.\n</think>\n\n%s",
    "unclosed": "<think>\nThe user wants the weather.\n%s",                 # the model wrote the call before </think>
    "inside_closed": "<think>\nThe user wants the weather.\n%s\n</think>\n\n",   # the whole call inside a closed thinking block (vLLM #39056)
    "prompt_opened": "The user wants the weather.\n</think>\n\n%s",          # chat template put <think> in the prompt
}
reason = {}
for tp, call in (("hermes", CALL_H), ("qwen3_coder", CALL_C)):
    for case, tpl in REASON.items():
        text = tpl % call
        k = "%s|%s" % (tp, case)
        try:
            rcls = ReasoningParserManager.get_reasoning_parser("qwen3")
            tcls = ToolParserManager.get_tool_parser(tp)
            tok = FakeTokenizer(specials_for(tcls, [text]) | specials_for(rcls, [text]) | {"<think>", "</think>"})
            req = REQ(messages=[{"role": "user", "content": "hi"}], model="m", tools=[{"type": "function", "function": x} for x in TOOLS], tool_choice="auto")
            try:
                rp = rcls(tok)
            except TypeError:
                rp = rcls(tok, req.tools)
            reasoning, content = rp.extract_reasoning(text, req)
            try:
                tparser = tcls(tok, req.tools)
            except TypeError:
                tparser = tcls(tok)
            r = tparser.extract_tool_calls(content or "", req) if content else None
            reason[k] = {"reasoning": reasoning, "content_after_reasoning": content,
                         "content": r.content if r else None, "calls": calls_of(r.tool_calls) if r else []}
        except Exception as e:
            reason[k] = {"exception": "%s: %s" % (type(e).__name__, str(e)[:160])}
out["reasoning"] = reason
out["stubbed"] = sorted(set(m.split(".")[0] if not m.startswith("vllm") else m for m in stubload.STUBBED))
json.dump(out, REAL, default=repr)
