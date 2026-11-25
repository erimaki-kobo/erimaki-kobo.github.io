#!/usr/bin/env python3
"""Build en/tool-call-parser-conformance-check/ (index.html, parser_results.json, toolcheck.py).

usage: python3 -I build_page.py res/ selftest.json toolcheck.py out_dir PUBLISHED MODIFIED
res/: <tag>.json from run_parsers.py (one per vLLM release). selftest.json: from selftest.py. ASCII only in the page
(the test strings with Japanese are shown escaped); the facts the prose names are asserted."""
import html, json, os, re, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from classify import judge, judge_stream  # noqa: E402
from scenarios import FORMATS  # noqa: E402

RD, ST, TC, OUT, PUB, MOD = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3], Path(sys.argv[4]), sys.argv[5], sys.argv[6]
e = html.escape
key = lambda v: tuple(int(x) for x in v[1:].split("."))
VS = sorted([f[:-5] for f in os.listdir(RD) if f.endswith(".json")], key=key)
R = {v: json.load(open(os.path.join(RD, v + ".json"))) for v in VS}
FAMS = list(FORMATS)
CASES = ["single", "text_before", "parallel", "nested_unicode", "no_call", "truncated"]


def runs(seq):
    out = []
    for v, s in zip(VS, seq):
        if out and out[-1][2] == s:
            out[-1][1] = v
        else:
            out.append([v, v, s])
    return out


def span(a, b):
    return a if a == b else "%s to %s" % (a, b)


# ---- per parser x case x mode verdicts
V = {}
for f in FAMS:
    for c in CASES:
        spec = FORMATS[f]["cases"][c]
        for m in ("nonstream", "stream"):
            seq = []
            for v in VS:
                p = R[v]["parsers"][f]
                if "error" in p:
                    seq.append(("absent", ""))
                    continue
                x = p["cases"][c][m]
                if "exception" in x:
                    seq.append(("exception", x["exception"][:80]))
                elif m == "nonstream":
                    seq.append(judge(x["calls"], x["content"], spec["want"] or [], spec["content"], spec["want"] is None))
                else:
                    seq.append(judge_stream(x["deltas"], spec["want"] or [], spec["content"], spec["want"] is None))
            V[(f, c, m)] = seq
FIRST = {f: next(v for v, s in zip(VS, V[(f, "single", "nonstream")]) if s[0] != "absent") for f in FAMS}

# ---- reasoning (qwen3 reasoning parser, then the tool parser)
RS = {}
for k in R[VS[-1]]["reasoning"]:
    seq = []
    for v in VS:
        x = R[v]["reasoning"][k]
        if "exception" in x:
            seq.append(("exception",))
        elif x["calls"]:
            seq.append(("call",))
        elif "tool_call" in (x["reasoning"] or ""):
            seq.append(("in_reasoning",))
        else:
            seq.append(("lost",))
    RS[k] = seq

# ---- cross: parsers that share <tool_call> and plain-text formats
G = ["hermes", "qwen3_coder", "qwen3_xml", "glm45", "llama3_json", "pythonic"]
X = {}
for pf in G:
    for of in G:
        seq = []
        for v in VS:
            x = R[v]["cross"]["%s|%s" % (pf, of)]
            c = FORMATS[of]["cases"]["single"]
            seq.append(("exception",) if "exception" in x else judge(x["calls"], x["content"], c["want"], c["content"])[:1])
        X[(pf, of)] = seq


def first_change(seq):
    return [r for r in runs(seq)]


# ---- facts the prose names (asserted against the measurements)
ALLV = (VS[0], VS[-1])
ok_all = lambda f, c, m: all(s[0] == "ok" for s, v in zip(V[(f, c, m)], VS) if key(v) >= key(FIRST[f]))
for f in FAMS:
    for c in ("single", "parallel", "nested_unicode", "no_call"):
        for m in ("nonstream", "stream"):
            assert ok_all(f, c, m), (f, c, m, runs(V[(f, c, m)]))
assert FIRST["gemma4"] == "v0.19.1" and all(FIRST[f] == VS[0] for f in FAMS if f != "gemma4")
for f in ("pythonic",):
    assert all(s[0] == "markup_in_content" for s in V[(f, "text_before", "nonstream")]) and all(s[0] == "markup_in_content" for s in V[(f, "text_before", "stream")])
assert [r[2][0] for r in runs(V[("llama3_json", "text_before", "nonstream")])] == ["content_lost", "markup_in_content"] and runs(V[("llama3_json", "text_before", "nonstream")])[1][0] == "v0.34.0"
assert all(s[0] == "markup_in_content" for s in V[("llama3_json", "text_before", "stream")])
for f in FAMS:
    if f not in ("llama3_json", "pythonic"):
        assert ok_all(f, "text_before", "nonstream") and ok_all(f, "text_before", "stream"), f
rq = {k: [[r[0], r[1], r[2][0]] for r in runs(s)] for k, s in RS.items()}
assert rq["hermes|unclosed"] == [["v0.15.1", "v0.16.0", "call"], ["v0.17.1", "v0.19.1", "in_reasoning"], ["v0.20.2", "v0.34.0", "call"]], rq["hermes|unclosed"]
assert rq["hermes|inside_closed"] == [["v0.15.1", "v0.23.0", "in_reasoning"], ["v0.24.0", "v0.34.0", "call"]], rq["hermes|inside_closed"]
assert rq["qwen3_coder|unclosed"] == rq["hermes|unclosed"] and rq["qwen3_coder|inside_closed"] == rq["hermes|inside_closed"]
assert all(r[2] == "call" for r in rq["hermes|closed"]) and all(r[2] == "call" for r in rq["qwen3_coder|closed"])
xr = lambda pf, of: [[r[0], r[1], r[2][0]] for r in runs(X[(pf, of)])]
assert xr("qwen3_coder", "hermes") == [["v0.15.1", "v0.23.0", "markup_in_content"], ["v0.24.0", "v0.34.0", "no_call"]]
assert xr("hermes", "qwen3_coder") == [[VS[0], VS[-1], "markup_in_content"]] and xr("qwen3_coder", "qwen3_xml")[0][2] == "ok" and xr("qwen3_xml", "qwen3_coder")[0][2] == "ok"
assert xr("llama3_json", "hermes") == [["v0.15.1", "v0.33.0", "ok"], ["v0.34.0", "v0.34.0", "markup_in_content"]]
assert xr("qwen3_xml", "hermes") == [[VS[0], VS[-1], "no_call"]]
assert xr("glm45", "hermes") == [["v0.15.1", "v0.23.0", "wrong_calls"], ["v0.24.0", "v0.34.0", "no_call"]]
# truncated: which parsers hand back a cut call with valid JSON (non-streaming) in the latest release
TR = {}
for f in FAMS:
    x = R[VS[-1]]["parsers"][f]["cases"]["truncated"]["nonstream"]
    TR[f] = judge(x["calls"], x["content"], [], None, True)
cutjson = sorted(f for f, (c, d) in TR.items() if c == "partial_call" and not d.endswith("')"))
assert cutjson == ["gemma4", "glm45", "minimax_m2", "qwen3_coder", "qwen3_xml"], (cutjson, TR)
assert TR["qwen3_coder"] == ("partial_call", 'get_weather({"city": "Tokyo"})')
assert [r[0] for r in runs(V[("qwen3_coder", "truncated", "nonstream")])] == [VS[0]]
for f in ("glm45", "minimax_m2"):
    rr = runs(V[(f, "truncated", "nonstream")])
    assert rr[0][2][0] == "markup_in_content" and rr[-1][0] == "v0.24.0" and rr[-1][2][0] == "partial_call", (f, rr)
assert ST["answers"] == ST["agree"] and ST["answers"] >= 1900, ST
src = lambda v, p: (Path(RD).parent / "tr" / v / p)
n_cases = sum(len(FORMATS[f]["cases"]) for f in FAMS)
n_runs = sum(1 for v in VS for f in FAMS if "error" not in R[v]["parsers"][f] for c in R[v]["parsers"][f]["cases"] for m in ("nonstream", "stream"))

# ---- tables
LBL = {"ok": "ok", "markup_in_content": "call left in content", "no_call": "call dropped (empty answer)", "content_lost": "call ok, text before it dropped",
       "partial_call": "cut call returned", "wrong_calls": "wrong calls", "bad_json": "invalid JSON args", "stream_header": "stream header missing",
       "exception": "parser error", "absent": "no such parser", "extra_content": "extra text in content"}
CLS = {"ok": "s-ok", "absent": "note"}


def cell(seq, detail=False):
    rr = runs(seq)
    if len(rr) == 1:
        s = rr[0][2]
        return '<span class="%s">%s</span>%s' % (CLS.get(s[0], "s-bad"), LBL.get(s[0], s[0]), (" <code>%s</code>" % e(s[1][:60].replace("\n", "\\n")) if detail and len(s) > 1 and s[1] else ""))
    return "<br>".join('%s: <span class="%s">%s</span>%s' % (span(a, b), CLS.get(s[0], "s-bad"), LBL.get(s[0], s[0]),
                                                            (" <code>%s</code>" % e(s[1][:60].replace("\n", "\\n")) if detail and len(s) > 1 and s[1] else "")) for a, b, s in rr)


CASE_LBL = {"single": "one call", "text_before": "text, then the call", "parallel": "two calls", "nested_unicode": "object argument, non-ASCII", "no_call": "plain answer", "truncated": "cut by max_tokens"}
rows = []
for f in FAMS:
    tds = []
    for c in CASES[:-1]:
        a, b = V[(f, c, "nonstream")], V[(f, c, "stream")]
        tds.append(cell(a) if a == b else "non-stream: %s<br>stream: %s" % (cell(a), cell(b)))
    rows.append("<tr><td><code>%s</code></td>%s</tr>" % (f, "".join("<td>%s</td>" % t for t in tds)))
tab_main = "\n".join(rows)
rows = []
for f in FAMS:
    rows.append("<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>" % (f, cell(V[(f, "truncated", "nonstream")], True), cell(V[(f, "truncated", "stream")], True)))
tab_trunc = "\n".join(rows)
RL = {"call": ("s-ok", "call comes out"), "in_reasoning": ("s-bad", "call stays in reasoning; tool_calls empty"), "lost": ("s-bad", "call lost"), "exception": ("s-bad", "error")}
RCASE = {"closed": "<code>&lt;think&gt;...&lt;/think&gt;</code> then the call", "unclosed": "call written before <code>&lt;/think&gt;</code>, no <code>&lt;/think&gt;</code>",
         "inside_closed": "whole call inside <code>&lt;think&gt;...&lt;/think&gt;</code>", "prompt_opened": "<code>&lt;think&gt;</code> in the prompt, output starts with reasoning"}
rows = []
for case in ("closed", "unclosed", "inside_closed", "prompt_opened"):
    for tp in ("hermes", "qwen3_coder"):
        rr = runs(RS["%s|%s" % (tp, case)])
        rows.append("<tr><td>%s</td><td><code>%s</code></td><td>%s</td></tr>" % (RCASE[case], tp, "<br>".join(
            '%s: <span class="%s">%s</span>' % (span(a, b), RL[s[0]][0], RL[s[0]][1]) for a, b, s in rr)))
tab_reason = "\n".join(rows)
rows = []
for pf in G:
    tds = []
    for of in G:
        rr = runs(X[(pf, of)])
        if pf == of:
            tds.append('<span class="s-ok">its own</span>')
            continue
        tds.append("<br>".join(('%s: ' % span(a, b) if len(rr) > 1 else "") + '<span class="%s">%s</span>' % (CLS.get(s[0], "s-bad"), {"ok": "reads it", "markup_in_content": "in content", "no_call": "empty", "wrong_calls": "wrong call", "exception": "error"}.get(s[0], s[0])) for a, b, s in rr))
    rows.append("<tr><th><code>%s</code></th>%s</tr>" % (pf, "".join("<td>%s</td>" % t for t in tds)))
tab_cross = "\n".join(rows)
FMT_EX = {f: FORMATS[f]["cases"]["single"]["text"] for f in FAMS}
fmt_rows = "\n".join("<tr><td><code>%s</code></td><td><code>%s</code></td></tr>" % (f, e(FMT_EX[f].encode("ascii", "backslashreplace").decode()).replace("\n", "\\n")) for f in FAMS)

DATA = {"releases": VS, "cases": CASES, "families": FAMS,
        "verdicts": {"%s|%s|%s" % k: [list(s) for s in seq] for k, seq in V.items()},
        "reasoning": {k: [s[0] for s in seq] for k, seq in RS.items()},
        "cross": {"%s|%s" % k: [s[0] for s in seq] for k, seq in X.items()}}
data_json = json.dumps(DATA, separators=(",", ":"), ensure_ascii=True).replace("</", "<\\/")   # details quote </tool_call>
assert "</" not in data_json

URL = "https://erimaki-kobo.github.io/en/tool-call-parser-conformance-check/"
TITLE = "vLLM tool call in content, tool_calls empty: parser test by release"
H1 = "vLLM returns the tool call in content, or tool_calls is empty: what each --tool-call-parser does with the same model output, v0.15 to v0.34, and a script to test your server"
DESC = ("vLLM's tool parsers from %d releases run on the same model outputs: why a call lands in content, in reasoning, or nowhere, which release fixed it, and a test script."
        % len(VS))
assert len(TITLE) <= 75 and 140 <= len(DESC) <= 175, (len(TITLE), len(DESC))
FAQ = [
    ("Why does vLLM return the tool call in content with tool_calls empty?",
     "The tool parser did not recognise the model's output. Either --tool-call-parser does not match the model's call format (hermes reads JSON inside <tool_call>, qwen3_coder reads <function=...> inside <tool_call>, "
     "gemma4 reads <|tool_call>call:...; a mismatch leaves the markup in content), or the model wrote text before the call and the parser is llama3_json or pythonic, which only read a call at the very start of the output "
     "(every release from %s to %s). The server still answers 200 with finish_reason stop." % ALLV),
    ("Why is tool_calls empty and content empty, with the call in reasoning (Qwen3, Qwen3.5)?",
     "The qwen3 reasoning parser kept the call in reasoning, and the tool parser only reads content. Measured on vLLM's own parser code: a call written before </think> (no </think> at all) stays in reasoning "
     "in v0.17.1 to v0.19.1 and comes out from v0.20.2 (PR #35687, in v0.20.0); a whole call inside a closed <think>...</think> block stays in reasoning in every release up to v0.23.0 and comes out from v0.24.0. "
     "On an older release, turn thinking off for tool turns (chat_template_kwargs enable_thinking false) or upgrade."),
    ("Why is the answer completely empty (no content, no tool_calls, no reasoning)?",
     "qwen3_xml in every release, and qwen3_coder and glm45 from v0.24.0, consume a <tool_call> section they cannot read: a JSON call inside <tool_call> (the hermes format, written by Qwen2.5, Qwen3 and many fine-tunes) "
     "disappears instead of landing in content. Use --tool-call-parser hermes for those models; qwen3_coder is for models that write <function=name><parameter=...>."),
    ("Why does a tool call come back with arguments missing?",
     "max_tokens cut the model's output inside the call. In %s, qwen3_coder, qwen3_xml, glm45, minimax_m2 and gemma4 return the cut call as a complete call with valid JSON arguments (the keys after the cut are simply missing). "
     "Before v0.33.0 vLLM also reports finish_reason \"tool_calls\" for it; from v0.33.0 (PR #59324) finish_reason stays \"length\". Check finish_reason before running a call, and raise max_tokens." % VS[-1]),
    ("What does \"auto\" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set mean?",
     "vLLM answers HTTP 400 with that text when a request has tools and tool_choice auto (the default when tools are sent) but the server was started without both flags. The same text is in every release from %s to %s. "
     "Start vllm serve with --enable-auto-tool-choice --tool-call-parser <name>." % ALLV),
    ("How do I test my own server?",
     "Run toolcheck.py (Python 3.8+, no packages): python3 toolcheck.py --base-url http://localhost:8000/v1 --model <name>. It sends five tool requests with and without streaming and labels each answer "
     "(ok, call left in content, call in reasoning, empty, invalid JSON, schema mismatch, missing stream header, finish_reason). Run it more than once: the model decides whether to call."),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["vLLM", "tool calling", "function calling"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "SoftwareApplication", "name": "toolcheck.py", "url": URL + "toolcheck.py", "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (Python 3.8+)",
     "description": "Tests the tool calls of an OpenAI-compatible server (vLLM, SGLang, llama.cpp, Ollama) and labels each answer.", "isAccessibleForFree": True,
     "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "vLLM tool parser results by release", "url": URL + "parser_results.json", "dateModified": MOD,
     "description": "What %d vLLM tool parsers return for %d model outputs in %d releases (%s to %s), non-streaming and streaming." % (len(FAMS), n_cases, len(VS), VS[0], VS[-1]),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "parser_results.json"}]},
    {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
LD = json.dumps(ld).replace("</", "<\\/")
assert "</" not in LD
css = (HERE.parent / "llama-args" / "style.css").read_text(encoding="ascii")
css += ("\ntd code,p code,li code,h1,h2,h3{overflow-wrap:anywhere}main p,main li,td{overflow-wrap:break-word}\n.s-ok{color:var(--ok)}.s-bad{color:var(--bad)}"
        "\n.note{color:var(--mut)}select{font:inherit;padding:7px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);width:100%}\n")
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
JS = r"""
(function () {
  var D = JSON.parse(document.getElementById("data").textContent), p = document.getElementById("p"), v = document.getElementById("v"), res = document.getElementById("res");
  var L = {ok: "ok", markup_in_content: "the call is left in message.content, tool_calls empty", no_call: "the call is dropped: no tool_calls and no content",
           content_lost: "the call comes out, the text before it is dropped", partial_call: "a cut call is returned as a call", wrong_calls: "wrong calls",
           bad_json: "arguments are not valid JSON", stream_header: "a stream chunk lacks id or name", exception: "the parser raised an error", absent: "this release has no such parser"};
  var C = {single: "One call", text_before: "Text, then the call", parallel: "Two calls in one answer", nested_unicode: "Object argument and non-ASCII text", no_call: "A plain answer, no call", truncated: "Output cut by max_tokens inside the call"};
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  D.families.forEach(function (f) { var o = document.createElement("option"); o.value = f; o.textContent = f; p.appendChild(o); });
  D.releases.slice().reverse().forEach(function (r) { var o = document.createElement("option"); o.value = r; o.textContent = r; v.appendChild(o); });
  function show() {
    var f = p.value, i = D.releases.indexOf(v.value), h = '<div class="tw"><table>' + "<thead><tr><th>Model output</th><th>Non-streaming</th><th>Streaming</th></tr></thead><tbody>";
    D.cases.forEach(function (c) {
      var a = D.verdicts[f + "|" + c + "|nonstream"][i], b = D.verdicts[f + "|" + c + "|stream"][i];
      function t(x) { var s = L[x[0]] || x[0]; return '<span class="' + (x[0] === "ok" ? "s-ok" : "s-bad") + '">' + esc(s) + "</span>" + (x[1] && x[0] === "partial_call" ? " <code>" + esc(x[1]) + "</code>" : ""); }
      h += "<tr><td>" + C[c] + "</td><td>" + t(a) + "</td><td>" + t(b) + "</td></tr>";
    });
    h += "</tbody></table></div>";
    if (f === "hermes" || f === "qwen3_coder") {
      h += "<p>With <code>--reasoning-parser qwen3</code>: ";
      ["unclosed", "inside_closed"].forEach(function (k, j) {
        var s = D.reasoning[f + "|" + k][i];
        h += (j ? "; " : "") + (k === "unclosed" ? "a call written before &lt;/think&gt; " : "a whole call inside &lt;think&gt;...&lt;/think&gt; ") + (s === "call" ? '<span class="s-ok">comes out</span>' : '<span class="s-bad">stays in reasoning, tool_calls empty</span>');
      });
      h += ".</p>";
    }
    var fin = D.releases.indexOf("v0.33.0");
    h += "<p>finish_reason for a cut call: " + (i >= fin ? '<span class="s-ok">"length"</span>' : '<span class="s-bad">"tool_calls"</span> (check usage.completion_tokens against max_tokens)') + ".</p>";
    res.innerHTML = h; res.setAttribute("data-done", String(Date.now()));
  }
  p.addEventListener("change", show); v.addEventListener("change", show);
  var u = new URLSearchParams(location.search);
  if (u.get("parser") && D.families.indexOf(u.get("parser")) >= 0) p.value = u.get("parser");
  if (u.get("vllm") && D.releases.indexOf(u.get("vllm")) >= 0) v.value = u.get("vllm");
  show();
  window.TC_READY = true;
})();
"""
assert "</script" not in JS
page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(TITLE, quote=False)}</title>
<meta name="description" content="{e(DESC)}">
<link rel="canonical" href="{URL}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(TITLE)}">
<meta property="og:description" content="{e(DESC)}">
<meta property="og:url" content="{URL}">
<style>
{css}</style>
<script type="application/ld+json">{LD}</script>
</head>
<body>
<main>
<p class="meta"><a href="/en/">Answers for LLM inference engineers</a></p>
<h1>{e(H1, quote=False)}</h1>
<p class="lede"><strong>For a well-formed call, every tool parser tested returns the right tool_calls in every release from {VS[0]} to {VS[-1]} (gemma4 from {FIRST["gemma4"]}), streaming included.</strong> The failures come from four places, each measured below on vLLM's own parser code: <strong>(1)</strong> a <code>--tool-call-parser</code> that does not match the model's call format leaves the markup in <code>content</code>, or drops the call so the answer is empty (<code>qwen3_xml</code> reading a JSON call in every release, <code>qwen3_coder</code> from v0.24.0); <strong>(2)</strong> <code>llama3_json</code> and <code>pythonic</code> only read a call at the start of the output, so any text before it puts the whole call in <code>content</code>; <strong>(3)</strong> with <code>--reasoning-parser qwen3</code>, a call written inside the thinking block stays in <code>reasoning</code> (fixed for an unclosed block in v0.20, for a closed one in v0.24); <strong>(4)</strong> a call cut by <code>max_tokens</code> comes back as a complete-looking call with keys missing, and before v0.33.0 with <code>finish_reason: "tool_calls"</code>.</p>
<p class="meta">Published {PUB} &middot; {len(FAMS)} parsers &times; {n_cases // len(FAMS)} model outputs &times; {len(VS)} vLLM releases, non-streaming and streaming ({n_runs:,} parser runs) &middot; <a href="toolcheck.py">toolcheck.py</a> &middot; <a href="#how">how</a></p>

<div class="card" id="lookup">
<div class="grid">
<div><label for="p">--tool-call-parser</label><select id="p"></select></div>
<div><label for="v">vLLM release</label><select id="v"></select></div>
</div>
<div id="res" aria-live="polite"></div>
<p class="note">From the measurements on this page (<a href="parser_results.json">parser_results.json</a>). Deep link: <code>?parser=qwen3_coder&amp;vllm=v0.19.1</code>.</p>
</div>

<h2 id="symptoms">Which symptom do you have?</h2>
<div class="tw"><table>
<thead><tr><th>What the response shows</th><th>Cause</th><th>Releases</th><th>Fix</th></tr></thead>
<tbody>
<tr><td><code>tool_calls: []</code>, the call markup in <code>content</code>, <code>finish_reason: "stop"</code></td><td>The parser does not read the model's format (<a href="#cross">table</a>), or the model wrote text before a <code>llama3_json</code>/<code>pythonic</code> call</td><td>All {len(VS)}</td><td>Pick the parser for the model's format; for llama3_json/pythonic, a prompt that makes the call the whole answer</td></tr>
<tr><td><code>tool_calls: []</code>, <code>content: ""</code>, the call in <code>reasoning</code></td><td>The qwen3 reasoning parser kept the call (<a href="#reasoning">table</a>)</td><td>Unclosed block: v0.17.1 to v0.19.1. Call inside a closed block: up to v0.23.0</td><td>v0.24.0 or later, or turn thinking off for tool turns</td></tr>
<tr><td><code>tool_calls: []</code>, <code>content</code> empty, no reasoning</td><td><code>qwen3_coder</code>/<code>qwen3_xml</code>/<code>glm45</code> consumed a <code>&lt;tool_call&gt;</code> they cannot read (a JSON call)</td><td>From v0.24.0 (qwen3_xml: all)</td><td><code>--tool-call-parser hermes</code> for models that write JSON inside <code>&lt;tool_call&gt;</code></td></tr>
<tr><td>A call with keys missing (<code>{{"city": "Tokyo"}}</code> without <code>days</code>)</td><td><code>max_tokens</code> cut the call (<a href="#cut">table</a>)</td><td><code>finish_reason: "tool_calls"</code> up to v0.32.0; <code>"length"</code> from v0.33.0</td><td>Check <code>finish_reason</code>; raise <code>max_tokens</code></td></tr>
<tr><td>HTTP 400 <code>"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set</code></td><td>The server was started without both flags</td><td>Same text in all {len(VS)}</td><td><code>vllm serve ... --enable-auto-tool-choice --tool-call-parser &lt;name&gt;</code></td></tr>
</tbody></table></div>

<h2 id="matrix">What does each parser return for a well-formed call?</h2>
<p><strong>Each parser, in each release, given the same model output in its own family's format</strong> (written after the examples in vLLM's <code>tests/tool_parsers/</code>). "ok" means tool_calls hold exactly the calls in the output, with the same arguments, and content holds only the text the model wrote. A cell that is the same in non-streaming and streaming is shown once.</p>
<div class="tw wide"><table class="flt">
<thead><tr><th>Parser</th><th>One call</th><th>Text, then the call</th><th>Two calls</th><th>Object argument, non-ASCII</th><th>Plain answer</th></tr></thead>
<tbody>
{tab_main}
</tbody></table></div>
<p>The model outputs, one call each:</p>
<div class="tw"><table>
<thead><tr><th>Parser</th><th>Output fed to it</th></tr></thead>
<tbody>
{fmt_rows}
</tbody></table></div>

<h2 id="cross">Which parser reads which format?</h2>
<p><strong>Six parsers that use <code>&lt;tool_call&gt;</code> or plain text, each given the other formats' one-call output</strong> (rows: the <code>--tool-call-parser</code>; columns: what the model wrote). "in content": tool_calls empty, the markup in content. "empty": no tool_calls and no content.</p>
<div class="tw wide"><table>
<thead><tr><th>Parser \\ output</th>{"".join("<th>%s</th>" % g for g in G)}</tr></thead>
<tbody>
{tab_cross}
</tbody></table></div>

<h2 id="reasoning">Does a call inside the thinking block come out (Qwen3, Qwen3.5)?</h2>
<p><strong>The <code>qwen3</code> reasoning parser of each release, then the tool parser on the content it leaves</strong>, as vLLM's chat server chains them (non-streaming). vLLM <a href="https://github.com/vllm-project/vllm/issues/39056">#39056</a> reports the "whole call inside a closed block" case on v0.19.0; <a href="https://github.com/vllm-project/vllm/pull/35687">PR #35687</a> (in v0.20.0) makes <code>&lt;tool_call&gt;</code> end an unclosed block.</p>
<div class="tw"><table>
<thead><tr><th>Model output</th><th>Tool parser</th><th>Result</th></tr></thead>
<tbody>
{tab_reason}
</tbody></table></div>

<h2 id="cut">What comes back when max_tokens cuts the call?</h2>
<p><strong>The one-call output cut at 60% of its length.</strong> "cut call returned" shows the call the parser handed back. Before v0.33.0 vLLM sets <code>finish_reason: "tool_calls"</code> whenever the parser returned a call; from v0.33.0 (<a href="https://github.com/vllm-project/vllm/pull/59324">PR #59324</a>, read from the source) a <code>length</code> stop stays <code>"length"</code>.</p>
<div class="tw wide"><table>
<thead><tr><th>Parser</th><th>Non-streaming</th><th>Streaming (arguments as sent)</th></tr></thead>
<tbody>
{tab_trunc}
</tbody></table></div>

<h2 id="toolcheck">How do I test my own server?</h2>
<p><strong><a href="toolcheck.py">toolcheck.py</a> sends five tool requests (auto, required, two calls, an object argument with non-ASCII text, and one cut by <code>max_tokens</code>), each with and without streaming, and labels every answer.</strong> It works with any OpenAI-compatible server and needs only Python 3.8+.</p>
<pre><code>python3 toolcheck.py --base-url http://localhost:8000/v1 --model Qwen/Qwen3-8B
python3 toolcheck.py --base-url http://localhost:8000/v1 --model M --extra '{{"chat_template_kwargs": {{"enable_thinking": false}}}}'</code></pre>
<p>Labels: <code>ok</code>, <code>markup_in_content</code>, <code>call_in_reasoning</code>, <code>empty</code>, <code>no_call</code> (the model chose not to call), <code>bad_json</code>, <code>schema_mismatch</code>, <code>stream_header</code> (a call's first chunk lacks id or name), <code>stream_differs</code>, <code>finish_reason</code>, <code>http_&lt;status&gt;</code>. The exit code is 1 when an answer points at the server rather than the model. Checked two ways: against a local server that replays what each release's parsers returned above ({ST["agree"]:,} of {ST["answers"]:,} labels match this page's verdicts), and against a running llama-server (build 12733) with a small test model.</p>

<h2 id="how">How was this measured?</h2>
<p><strong>The <code>vllm/</code> source of each of {len(VS)} releases (the newest patch of every minor from {VS[0]} to {VS[-1]}, from vLLM's git tags) was loaded in Python 3.12 without a GPU: torch, the compiled extension and the model and engine code were replaced by stubs, and the tool parsers, reasoning parsers and request models ran as released.</strong> Each parser was built as vLLM's chat server builds it (<code>parser(tokenizer, request.tools)</code>) and given the same model outputs through <code>extract_tool_calls</code> and, piece by piece, <code>extract_tool_calls_streaming</code>. The streamed pieces were put back together the way an OpenAI client does.</p>
<p>The tokenizer is a stand-in, as in vLLM's own parser tests: each special token (<code>&lt;tool_call&gt;</code>, <code>&lt;|tool_call&gt;</code>, <code>&lt;think&gt;</code>, ...) is one token, and other text is split into words, spaces and single characters. A real tokenizer cuts text differently, so a streaming result here holds for this split; the non-streaming results do not depend on it. Not covered: <code>mistral</code> (needs the Mistral tokenizer), <code>openai</code>/gpt-oss (Harmony format), and the server's own code around the parser, except the reasoning chain and the <code>finish_reason</code> rule, which were read from each release's source.</p>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>vLLM's source at the git tags {VS[0]} to {VS[-1]} (<code>vllm/tool_parsers/</code>, <code>vllm/reasoning/</code>, the chat server), and the model-output formats in <code>tests/tool_parsers/</code>: <a href="https://github.com/vllm-project/vllm">github.com/vllm-project/vllm</a>.</li>
<li>Reports: <a href="https://github.com/vllm-project/vllm/issues/39056">#39056</a> (Qwen3.5, call inside thinking, v0.19.0), <a href="https://github.com/vllm-project/vllm/issues/39468">#39468</a> (Gemma 4 call returned as content, v0.19.0), <a href="https://github.com/vllm-project/vllm/issues/44522">#44522</a> (Gemma 4 streaming leaks <code>&lt;|"|&gt;</code>), <a href="https://github.com/vllm-project/vllm/issues/42696">#42696</a> (Gemma 4 streaming with OpenCode, v0.20.2).</li>
<li>Changes: <a href="https://github.com/vllm-project/vllm/pull/35687">#35687</a> (v0.20.0), <a href="https://github.com/vllm-project/vllm/pull/45588">#45588</a> and <a href="https://github.com/vllm-project/vllm/pull/45553">#45553</a> (Gemma 4 parsers, v0.24.0), <a href="https://github.com/vllm-project/vllm/pull/59324">#59324</a> (finish_reason, v0.33.0); the first release of each is the first tag that contains the commit.</li>
</ul>
<p>The results as JSON: <a href="parser_results.json">parser_results.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. The scripts that produced them are in this site's repository under <code>.github/tc-parsers/</code>.</p>
<p class="note">Related: <a href="/en/vllm-removed-flags-lookup/">"vllm serve: error: unrecognized arguments"</a> &middot; <a href="/en/context-overflow-error-status-check/">what each engine returns when the prompt is too long</a> &middot; <a href="/en/generation-stop-tokens-check/">a model that does not stop generating</a> &middot; <a href="/en/spec-decode-lossless-check/">speculative decoding changes the output</a>.</p>
</main>
<script type="application/json" id="data">{data_json}</script>
<script>
{JS}</script>
</body>
</html>
"""
page.encode("ascii")
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "index.html").write_text(page, encoding="ascii")
(OUT / "parser_results.json").write_text(json.dumps(DATA, indent=0, ensure_ascii=True), encoding="ascii")
shutil.copyfile(TC, OUT / "toolcheck.py")
print("index.html %d bytes | %d releases, %d parsers, %d parser runs | selftest %d/%d" % (len(page), len(VS), len(FAMS), n_runs, ST["agree"], ST["answers"]), file=sys.stderr)
