"""Model outputs fed to every vLLM release's tool parsers, in each model family's own format (written after the examples
in vLLM's tests/tool_parsers/). `want` is the tool calls a client should receive; `content` the text that should stay
in message.content (None: nothing, or only whitespace)."""

TOOLS = [
    {"name": "get_weather", "description": "Weather for a city", "parameters": {"type": "object", "properties": {
        "city": {"type": "string"}, "days": {"type": "integer"}}, "required": ["city"]}},
    {"name": "search", "description": "Web search", "parameters": {"type": "object", "properties": {
        "query": {"type": "string"}, "filters": {"type": "object", "properties": {"lang": {"type": "string"}, "limit": {"type": "integer"}}}},
        "required": ["query"]}},
]
W = ["get_weather", {"city": "Tokyo", "days": 3}]
S = ["search", {"query": "東京 天気", "filters": {"lang": "ja", "limit": 5}}]
TEXT = "Let me check that."
PLAIN = "It is sunny in Tokyo today."


def fam(parser, one, sep="\n", pre=None, wrap=None, post=None):
    """one(name, args) -> the text of one call; wrap(body) -> the section around all calls."""
    wrap = wrap or (lambda b: b)
    single = wrap(one(*W))
    cases = {
        "single": {"text": single, "want": [W], "content": None},
        "text_before": {"text": TEXT + ("\n" if pre is None else pre) + single, "want": [W], "content": TEXT},
        "parallel": {"text": wrap(one(*W) + sep + one(*S)), "want": [W, S], "content": None},
        "nested_unicode": {"text": wrap(one(*S)), "want": [S], "content": None},
        "no_call": {"text": PLAIN, "want": [], "content": PLAIN},
    }
    return {"parser": parser, "cases": cases}


def js(o):
    import json
    return json.dumps(o, ensure_ascii=False)


def gemma_val(v):
    if isinstance(v, str):
        return '<|"|>%s<|"|>' % v
    if isinstance(v, dict):
        return "{" + ",".join("%s:%s" % (k, gemma_val(x)) for k, x in v.items()) + "}"
    return js(v)


def renumber(b):
    i = 0
    while "@IDX@" in b:
        b = b.replace("@IDX@", str(i), 1)
        i += 1
    return b


def xml_val(v):
    return v if isinstance(v, str) else js(v)


FORMATS = {
    "hermes": fam("hermes", lambda n, a: '<tool_call>\n%s\n</tool_call>' % js({"name": n, "arguments": a})),
    "qwen3_coder": fam("qwen3_coder", lambda n, a: "<tool_call>\n<function=%s>\n%s</function>\n</tool_call>" % (
        n, "".join("<parameter=%s>\n%s\n</parameter>\n" % (k, xml_val(v)) for k, v in a.items()))),
    "qwen3_xml": fam("qwen3_xml", lambda n, a: "<tool_call>\n<function=%s>\n%s</function>\n</tool_call>" % (
        n, "".join("<parameter=%s>\n%s\n</parameter>\n" % (k, xml_val(v)) for k, v in a.items()))),
    "gemma4": fam("gemma4", lambda n, a: "<|tool_call>call:%s%s<tool_call|>" % (n, gemma_val(a)), sep="", pre=""),
    "llama3_json": fam("llama3_json", lambda n, a: js({"name": n, "parameters": a}), sep="; "),
    "pythonic": fam("pythonic", lambda n, a: "%s(%s)" % (n, ", ".join("%s=%s" % (k, js(v)) for k, v in a.items())), sep=", ",
                    wrap=lambda b: "[" + b + "]"),
    "kimi_k2": fam("kimi_k2", lambda n, a: "<|tool_call_begin|>functions.%s:@IDX@<|tool_call_argument_begin|>%s<|tool_call_end|>" % (n, js(a)),
                   sep="", pre="", wrap=lambda b: "<|tool_calls_section_begin|>" + renumber(b) + "<|tool_calls_section_end|>"),
    "deepseek_v31": fam("deepseek_v31", lambda n, a: "<｜tool▁call▁begin｜>%s<｜tool▁sep｜>%s<｜tool▁call▁end｜>" % (n, js(a)), sep="", pre="",
                        wrap=lambda b: "<｜tool▁calls▁begin｜>" + b + "<｜tool▁calls▁end｜>"),
    "glm45": fam("glm45", lambda n, a: "<tool_call>%s\n%s</tool_call>" % (n, "".join("<arg_key>%s</arg_key>\n<arg_value>%s</arg_value>\n" % (k, xml_val(v)) for k, v in a.items())),
                 pre=" "),
    "minimax_m2": fam("minimax_m2", lambda n, a: '<invoke name="%s">\n%s</invoke>\n' % (n, "".join('<parameter name="%s">%s</parameter>\n' % (k, xml_val(v)) for k, v in a.items())),
                      sep="", wrap=lambda b: "<minimax:tool_call>\n" + b + "</minimax:tool_call>"),
}
# truncated output (max_tokens reached inside the call): the call is incomplete; no well-formed call should come out
for f in FORMATS.values():
    t = f["cases"]["single"]["text"]
    f["cases"]["truncated"] = {"text": t[: int(len(t) * 0.6)], "want": None, "content": None}
