#!/usr/bin/env python3
"""Build en/gguf-arch-min-build-lookup/index.html from table.json.

Usage: python3 -I build_page.py table.json out_dir
Writes out_dir/index.html and out_dir/archs.json (published next to the page).
ASCII only. Every build number, date and version comes from table.json.
The environment variable PAGE_MODIFIED (YYYY-MM-DD) sets dateModified; default is the publish date.
"""
import html, json, os, re, sys
from pathlib import Path

src, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
T = json.load(open(src))
A = T["archs"]
OT = T["ollama_tags"]
AS_OF = T["as_of"]
PUBLISHED = "2026-11-11"
MODIFIED = os.environ.get("PAGE_MODIFIED") or PUBLISHED
assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", MODIFIED), MODIFIED
URL = "https://erimaki-kobo.github.io/en/gguf-arch-min-build-lookup/"
TITLE = "GGUF Architecture Lookup: Minimum llama.cpp and Ollama"
H1 = "\"unknown model architecture\": which llama.cpp build and Ollama version a GGUF needs"
DESC = ("Look up any GGUF architecture string: the first llama.cpp build (bNNNN) and the first Ollama "
        "release that can load it, read from git history. All %d names." % len(A))
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))
e = html.escape
LC = "https://github.com/ggml-org/llama.cpp"
OL = "https://github.com/ollama/ollama"

def bnum(t):
    return int(t[1:])

# ---- Ollama tag index ----
tag_idx = {t["tag"]: i for i, t in enumerate(OT)}
pinned = [t for t in OT if t["pinned_build"]]
FIRST_PIN = pinned[0]
LATEST_O = OT[-1]
assert LATEST_O["tag"] == T["ollama_latest"]["tag"] and LATEST_O["pinned_build"]
HEAD_TAG = T["llama_head_tag"]

# Go-engine range per architecture (first and last release that registers the name)
go_first, go_last = {}, {}
for t in OT:
    for a in t["go_archs"]:
        go_first.setdefault(a, t["tag"])
        go_last[a] = t["tag"]
# the Go registry must be contiguous per arch, otherwise "from..to" would be wrong
for a, f in go_first.items():
    for t in OT[tag_idx[f]:tag_idx[go_last[a]] + 1]:
        assert a in t["go_archs"], (a, t["tag"])
LAST_GO_TAG = [t for t in OT if t["go_archs"]][-1]
FIRST_NO_GO = OT[tag_idx[LAST_GO_TAG["tag"]] + 1]
FIRST_GO_TAG = [t for t in OT if t["go_archs"]][0]
FIRST_FILE_PIN = next(t for t in OT if t["pin"] and re.fullmatch(r"b\d+", t["pin"]))

# vLLM GGUF plugin: families in its README "Tested model coverage" (v0.0.5), mapped to GGUF names
VLLM_TESTED = {"qwen2": "Qwen 2.5", "qwen3": "Qwen 3", "phi3": "Phi 3.5", "gpt2": "GPT-2", "stablelm": "StableLM",
               "gemma3": "Gemma 3", "olmoe": "OLMoE", "gemma4": "Gemma 4", "qwen35": "Qwen 3.5 / 3.6"}
names = {r["arch"] for r in A}
assert set(VLLM_TESTED) <= names, set(VLLM_TESTED) - names

rows_data = []
for r in A:
    vl = r["ollama_via_llama"]
    before = bool(vl) and vl["tag"] == FIRST_PIN["tag"]
    rows_data.append({
        "a": r["arch"], "b": bnum(r["llama_first_build"]), "d": r["llama_first_build_date"], "c": r["llama_commit"][:10],
        "s": r["llama_subject"], "ol": vl["tag"] if vl else None, "old": vl["date"] if vl else None,
        "olb": vl["pinned_build"] if vl else None, "pre": before,
        "gf": go_first.get(r["arch"]), "gl": go_last.get(r["arch"]),
        "patch": bool(vl) and bool(vl["pinned_build"]) and bnum(vl["pinned_build"]) < bnum(r["llama_first_build"]),
        "er": [[a_, b_] for a_, b_, _ in r["ollama_earlier_runs"]],
    })
rows_data.sort(key=lambda x: (-x["b"], x["a"]))
BY = {x["a"]: x for x in rows_data}

# ---- facts used in prose (asserted) ----
not_in_ollama = [x["a"] for x in rows_data if not x["ol"]]
g4, q35 = BY["gemma4"], BY["qwen35"]
V = json.load(open(src.parent / "ollama_vendored.json"))["vendored"]
vt = [k for k in [t["tag"] for t in OT] if V.get(k)]
assert vt[0] == "v0.3.13" and vt[-1] == "v0.24.0"
assert g4["b"] == 8637 and g4["ol"] == "v0.30.0" and g4["gf"] == "v0.20.0"
assert q35["b"] == 7990 and q35["ol"] == "v0.30.0" and q35["gf"] == "v0.17.1"
go_earlier = [x for x in rows_data if x["gf"] and (not x["ol"] or tag_idx[x["gf"]] < tag_idx[x["ol"]])]
N_2026 = sum(1 for x in rows_data if x["d"] >= "2026-01-01")

# ---- Ollama pin ranges (consecutive releases with the same bundled build) ----
ranges = []
for t in pinned:
    if ranges and ranges[-1]["b"] == t["pinned_build"] and ranges[-1]["exact"] == t["pin_exact"]:
        ranges[-1]["to"] = t["tag"]; ranges[-1]["n"] += 1
    else:
        ranges.append({"from": t["tag"], "to": t["tag"], "date": t["date"], "b": t["pinned_build"], "exact": t["pin_exact"], "pin": t["pin"], "n": 1})
build_date = {}
for t in pinned:
    build_date[t["pinned_build"]] = t["date"]

def otag(tag):
    return '<a href="%s/releases/tag/%s">%s</a>' % (OL, tag, tag[1:])

ROWS = []
for x in rows_data:
    if x["ol"] is None:
        oc = '<span class="s n">not yet</span><br><span class="note">newer than %s in %s</span>' % (LATEST_O["pinned_build"], LATEST_O["tag"][1:])
    elif x["pre"]:
        oc = '%s <span class="note">or earlier</span>' % otag(x["ol"])
    else:
        oc = '%s<br><span class="note">%s, bundles %s%s</span>' % (otag(x["ol"]), x["old"], x["olb"], " + Ollama patch" if x["patch"] else "")
    for a_, b_ in x["er"]:
        oc += '<br><span class="note">also %s&ndash;%s (Ollama patch)</span>' % (otag(a_), otag(b_))
    if x["gf"]:
        gc = "%s&ndash;%s" % (otag(x["gf"]), otag(x["gl"]))
    else:
        gc = "&ndash;"
    vc = '<span class="s y">tested</span><br><span class="note">%s</span>' % e(VLLM_TESTED[x["a"]]) if x["a"] in VLLM_TESTED else "&ndash;"
    ROWS.append('<tr id="a-%s" data-a="%s"><td><code>%s</code></td><td><a href="%s/releases/tag/b%d"><strong>b%d</strong></a><br><span class="meta">%s</span></td>'
                '<td>%s<br><a class="note" href="%s/commit/%s">%s</a></td><td>%s</td><td>%s</td><td>%s</td></tr>'
                % (e(x["a"]), e(x["a"]), e(x["a"]), LC, x["b"], x["b"], x["d"], e(x["s"]), LC, x["c"], x["c"], oc, gc, vc))
ROWS = "\n".join(ROWS)

PINROWS = []
for g in reversed(ranges):
    rel = otag(g["from"]) if g["n"] == 1 else "%s&ndash;%s <span class=\"note\">(%d releases)</span>" % (otag(g["from"]), otag(g["to"]), g["n"])
    b = '<a href="%s/releases/tag/%s">%s</a>' % (LC, g["b"], g["b"]) if g["exact"] else '%s <span class="note">+ later commits (<a href="%s/commit/%s">%s</a>)</span>' % (g["b"], LC, g["pin"], g["pin"][:9])
    PINROWS.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (rel, g["date"], b))
PINROWS = "\n".join(PINROWS)

tool = {
    "asof": AS_OF, "head": bnum(HEAD_TAG),
    "arch": [[x["a"], x["b"], x["d"], x["ol"], x["gf"], x["gl"], 1 if x["a"] in VLLM_TESTED else 0, x["er"], 1 if x["pre"] else 0] for x in rows_data],
    "ot": [[t["tag"][1:], t["date"], bnum(t["pinned_build"]) if t["pinned_build"] else 0] for t in OT],
}
DATA_JSON = json.dumps(tool, separators=(",", ":"))
assert "</" not in DATA_JSON

FAQ = [
    ("What does \"unknown model architecture\" mean when loading a GGUF?",
     "The file's <code>general.architecture</code> value is a name the llama.cpp build inside your runtime does not have in its architecture table. "
     "The file is usually fine. The runtime is older than the commit that added that architecture; the table above gives the first build that has it."),
    ("Which llama.cpp build do I need for Gemma 4 GGUF files?",
     "<code>gemma4</code> first appears in build <strong>b%d</strong> (%s). Ollama's bundled llama.cpp has it from %s; Ollama's own engine registered "
     "<code>gemma4</code> from %s to %s." % (g4["b"], g4["d"], g4["ol"][1:], g4["gf"][1:], g4["gl"][1:])),
    ("Which llama.cpp build do I need for Qwen 3.5 and Qwen 3.6 GGUF files?",
     "Both families use the architecture string <code>qwen35</code> (MoE variants use <code>qwen35moe</code>). <code>qwen35</code> first appears in build "
     "<strong>b%d</strong> (%s), and Ollama's bundled llama.cpp has it from %s." % (q35["b"], q35["d"], q35["ol"][1:])),
    ("How do I find which llama.cpp version my Ollama uses?",
     "From Ollama %s the repository has a <code>LLAMA_CPP_VERSION</code> file at each release tag holding the llama.cpp tag, for example %s for Ollama %s. "
     "Older releases pin a commit in <code>Makefile.sync</code>, <code>llama/vendoring</code> or a git submodule; the second table on this page resolves "
     "all of them to build numbers." % (FIRST_FILE_PIN["tag"][1:], LATEST_O["pinned_build"], LATEST_O["tag"][1:])),
    ("How do I read the architecture string of a GGUF file?",
     "Run <code>gguf-dump --no-tensors model.gguf</code> from the <code>gguf</code> Python package and read <code>general.architecture</code>. llama.cpp also "
     "prints it while loading, and the Hugging Face file viewer shows it in the metadata panel of a .gguf file."),
    ("My build is new enough and the model still fails to load. Why?",
     "A known architecture name is necessary, not sufficient. Later commits add tensors, metadata keys, tokenizer types or multimodal projectors for the same "
     "architecture, and re-uploaded GGUF files can depend on them. Use the newest build first; if it still fails, the cause is in the file or a missing "
     "feature, not the architecture table."),
    ("Can vLLM load any GGUF architecture?",
     "No. From vLLM v0.24.0 GGUF loading lives in the separate <code>vllm-gguf-plugin</code>, which maps GGUF tensors onto vLLM's own model classes. Its README "
     "lists the families covered by tests (%d architecture strings in the table above) and says other models may or may not work."
     % len(VLLM_TESTED)),
]

def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s))

FAQ_HTML = "\n".join("<dt>%s</dt>\n<dd>%s</dd>" % (e(q), a) for q, a in FAQ)
ORG = {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"}
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1, "description": DESC, "url": URL,
     "datePublished": PUBLISHED, "dateModified": MODIFIED, "inLanguage": "en", "author": ORG, "publisher": ORG,
     "about": ["GGUF", "llama.cpp", "Ollama", "vLLM"], "isBasedOn": URL + "archs.json"},
    {"@type": "WebApplication", "@id": URL + "#tool", "name": "GGUF architecture to minimum llama.cpp build and Ollama version lookup",
     "url": URL + "#lookup", "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (runs in the browser)",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
     "description": "Paste a GGUF load error or architecture name; get the first llama.cpp build and Ollama release that support it."},
    {"@type": "Dataset", "@id": URL + "#data", "name": "GGUF architecture strings: first llama.cpp build and first Ollama release",
     "description": "One record per general.architecture string known to llama.cpp %s: introducing commit, first release tag and date, "
                    "first Ollama release whose bundled llama.cpp contains it, and the llama.cpp build bundled by every Ollama release." % HEAD_TAG,
     "url": URL, "dateModified": AS_OF, "creator": ORG,
     "distribution": {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "archs.json"}},
    {"@type": "FAQPage", "@id": URL + "#faq",
     "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": strip_tags(a)}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": "GGUF architecture lookup", "item": URL}]},
]}
LD_JSON = json.dumps(ld)
assert "</" not in LD_JSON

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1c1a;--mut:#62605a;--line:#dcd9d1;--card:#fff;--acc:#0b6b5d;--warn:#a4500a;--bad:#a12a2a;--ok:#1d6b34;--code:#f1efe9}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fg:#eceae4;--mut:#a3a097;--line:#35332e;--card:#1e1e1b;--acc:#58c2b0;--warn:#e0a060;--bad:#ef8a8a;--ok:#7fd096;--code:#262521}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.65rem;line-height:1.25;margin:.2em 0 .4em}
h2{font-size:1.25rem;margin:2em 0 .5em;padding-top:.6em;border-top:1px solid var(--line)}
a{color:var(--acc)}
p,li,dd{max-width:72ch}
.lede{font-size:1.05rem}
.meta{color:var(--mut);font-size:.85rem}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.88em;background:var(--code);border-radius:4px}
code{padding:.1em .35em;overflow-wrap:anywhere}
pre{padding:12px;overflow-x:auto;line-height:1.45;white-space:pre-wrap;word-break:break-word}
pre code{padding:0;background:none}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 14px}
@media (max-width:560px){.grid{grid-template-columns:1fr}}
label{display:block;font-size:.82rem;color:var(--mut);margin-bottom:2px}
input,textarea{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);font:inherit}
textarea{min-height:64px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.88rem;margin-bottom:10px}
button{font:inherit;padding:9px 18px;border-radius:6px;border:1px solid var(--acc);background:var(--acc);color:#fff;cursor:pointer}
@media (prefers-color-scheme:dark){button{color:#10201d}}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:12px}
table{border-collapse:collapse;width:100%;font-size:.88rem;margin:10px 0}
th,td{border-bottom:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}
th{color:var(--mut);font-weight:600;font-size:.8rem}
.tw{overflow-x:auto}
.tw.wide{width:min(1080px,calc(100vw - 32px));margin-left:calc((100% - min(1080px,calc(100vw - 32px)))/2)}
#archs{min-width:860px}
#archs td:nth-child(1),#archs td:nth-child(2),#archs td:nth-child(5){white-space:nowrap}
#archs tr:target,#archs tr.hit{outline:2px solid var(--acc)}
.s{display:inline-block;font-weight:700;font-size:.8rem;white-space:nowrap}
.s.y{color:var(--ok)}.s.n{color:var(--bad)}
.verdict{font-weight:700;padding:10px 12px;border-radius:8px;border:1px solid var(--line);margin:12px 0}
.v-ok{border-color:var(--ok);color:var(--ok)}.v-load{border-color:var(--warn);color:var(--warn)}.v-bad{border-color:var(--bad);color:var(--bad)}
.verdict span{display:block;font-weight:400;color:var(--fg);margin-top:4px}
.note{font-size:.86rem;color:var(--mut)}
#status{color:var(--bad);font-size:.88rem}
dt{font-weight:600;margin-top:.8em}dd{margin:0}
#filter{max-width:320px}
#res .s{font-size:1em}
"""

JS = r"""
(function(){
var DATA=JSON.parse(document.getElementById("arch-data").textContent);
/* logic-begin */
function extractArch(text){
  var t=String(text||"").trim(),m;
  if(!t)return null;
  var pats=[/unknown (?:model )?architecture:?\s*['"`]?([A-Za-z0-9_.\-]+)/i,
    /architecture ['"`]?([A-Za-z0-9_.\-]+)['"`]? (?:is )?not supported/i,
    /general\.architecture\s*(?:str\s*)?[=:]\s*['"`]?([A-Za-z0-9_.\-]+)/i,
    /unsupported (?:model )?architecture:?\s*['"`]?([A-Za-z0-9_.\-]+)/i];
  for(var i=0;i<pats.length;i++){m=t.match(pats[i]);if(m)return m[1].replace(/[.]+$/,"").toLowerCase()}
  if(/^['"`]?[A-Za-z0-9_.\-]+['"`]?$/.test(t))return t.replace(/['"`]/g,"").toLowerCase();
  return null}
function parseBuild(s){s=String(s||"").trim();if(!s)return 0;
  var m=s.match(/^b?(\d{3,6})$/i)||s.match(/version:?\s*(\d{3,6})\b/i)||s.match(/\bb(\d{3,6})\b/);
  return m?parseInt(m[1],10):-1}
function parseOllama(s){s=String(s||"").trim();if(!s)return "";
  var m=s.match(/(\d+\.\d+\.\d+)/);return m?m[1]:null}
function cmpV(a,b){a=a.split(".");b=b.split(".");for(var i=0;i<3;i++){var x=parseInt(a[i],10),y=parseInt(b[i],10);if(x!==y)return x<y?-1:1}return 0}
function tagIndex(D,v){var best=-1;for(var i=0;i<D.ot.length;i++){if(cmpV(D.ot[i][0],v)<=0)best=i;else break}return best}
function lookup(D,inp){
  var name=extractArch(inp.text);
  if(!name)return {error:"arch"};
  var build=parseBuild(inp.build);if(build<0)return {error:"build"};
  var ov=parseOllama(inp.ollama);if(ov===null)return {error:"ollama"};
  var rec=null;for(var i=0;i<D.arch.length;i++){if(D.arch[i][0]===name){rec=D.arch[i];break}}
  var out={error:null,name:name,known:!!rec,build:build,ollama:ov};
  if(!rec){out.near=D.arch.filter(function(a){return a[0].indexOf(name)>=0||name.indexOf(a[0])>=0}).map(function(a){return a[0]}).slice(0,6);return out}
  out.min=rec[1];out.date=rec[2];out.olTag=rec[3];out.goFrom=rec[4];out.goTo=rec[5];out.vllm=!!rec[6];out.pre=!!rec[8];
  out.buildOk=build?build>=rec[1]:null;
  if(ov){var ix=tagIndex(D,ov);
    if(ix<0||!D.ot[ix][2]&&!rec[4]){out.olKnown=false}
    else{out.olKnown=true;out.olUsed=D.ot[ix][0];out.olBuild=D.ot[ix][2];
      var inRun=function(a,b){return ix>=tagIndex(D,a.slice(1))&&ix<=tagIndex(D,b.slice(1))};
      out.olLlamaOk=(!!rec[3]&&ix>=tagIndex(D,rec[3].slice(1)))||rec[7].some(function(w){return inRun(w[0],w[1])});
      var gi=rec[4]?[tagIndex(D,rec[4].slice(1)),tagIndex(D,rec[5].slice(1))]:null;
      out.olGoOk=!!gi&&ix>=gi[0]&&ix<=gi[1]}}
  return out}
/* logic-end */
var $=function(id){return document.getElementById(id)};
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
var LATEST=DATA.ot[DATA.ot.length-1];
function run(){
  var inp={text:$("q").value,build:$("b").value,ollama:$("o").value},r=lookup(DATA,inp),x="";
  Array.prototype.forEach.call(document.querySelectorAll("#archs tr.hit"),function(tr){tr.classList.remove("hit")});
  if(r.error){$("res").innerHTML="";$("status").textContent=r.error==="arch"?"Paste the error line, or type the architecture name (for example gemma4).":
    r.error==="build"?"llama.cpp build should look like b8637, 8637, or the line printed by llama-server --version.":"Ollama version should look like 0.30.0.";return}
  $("status").textContent="";
  if(!r.known){
    x+='<div class="verdict v-bad">"'+esc(r.name)+'" is not an architecture in upstream llama.cpp as of b'+DATA.head+' ('+esc(DATA.asof)+')<span>No upstream build can load it yet. Either support has not been merged, the file was made for a fork, or the name is misspelled.'+(r.near.length?' Similar names: '+r.near.map(function(n){return '<a href="#a-'+esc(n)+'"><code>'+esc(n)+'</code></a>'}).join(", ")+'.':'')+'</span></div>';
    $("res").innerHTML=x;return}
  var head='<code>'+esc(r.name)+'</code> needs llama.cpp <strong>b'+r.min+'</strong> or newer (tagged '+esc(r.date)+')';
  if(r.buildOk===false)x+='<div class="verdict v-bad">Your build b'+r.build+' is too old: '+head+'<span>Update llama.cpp, or the app that bundles it, to b'+r.min+' or newer.</span></div>';
  else if(r.buildOk===true)x+='<div class="verdict v-ok">Your build b'+r.build+' already knows this architecture: '+head+'<span>If loading still fails, the architecture table is not the cause. See "the build is new enough" below.</span></div>';
  else x+='<div class="verdict v-load">'+head+'<span>Check your build with <code>llama-server --version</code> (the number after "version:").</span></div>';
  x+="<p><strong>Ollama:</strong> ";
  if(!r.olTag)x+="no release bundles it yet. The latest release, "+esc(LATEST[0])+", bundles b"+LATEST[2]+".";
  else x+="the bundled llama.cpp has it from <strong>"+esc(r.olTag.slice(1))+"</strong>"+(r.pre?" or earlier":"")+".";
  if(r.goFrom)x+=" Ollama's own engine registered this name in "+esc(r.goFrom.slice(1))+"&ndash;"+esc(r.goTo.slice(1))+" (see the note on that engine below).";
  x+="</p>";
  if(r.ollama){
    if(!r.olKnown)x+='<p class="note">Ollama '+esc(r.ollama)+' is older than the first release this page can resolve.</p>';
    else{var same=r.olUsed===r.ollama?"":" (nearest release at or below: "+esc(r.olUsed)+")";
      if(r.olLlamaOk)x+='<p><span class="s y">Ollama '+esc(r.ollama)+' can load it</span>'+same+': it bundles b'+r.olBuild+'.</p>';
      else if(r.olGoOk)x+='<p><span class="s y">Ollama '+esc(r.ollama)+' registers it in its own engine</span>'+same+', but its bundled llama.cpp (b'+r.olBuild+') does not have it. Files that fall back to llama.cpp, such as a GGUF with a separate projector file, fail with "unknown model architecture".</p>';
      else x+='<p><span class="s n">Ollama '+esc(r.ollama)+' cannot load it</span>'+same+': it bundles '+(r.olBuild?'b'+r.olBuild:'a llama.cpp this page cannot resolve')+'.</p>'}}
  x+="<p><strong>vLLM:</strong> "+(r.vllm?"this family is in the tested list of <code>vllm-gguf-plugin</code>.":"not in the tested list of <code>vllm-gguf-plugin</code>; it may or may not load.")+"</p>";
  x+='<p class="note"><a href="#a-'+esc(r.name)+'">Row in the table</a></p>';
  $("res").innerHTML=x;
  var tr=document.getElementById("a-"+r.name);if(tr)tr.classList.add("hit");
  try{history.replaceState(null,"",location.pathname+"?arch="+encodeURIComponent(r.name)+(r.build?"&build="+r.build:"")+(r.ollama?"&ollama="+r.ollama:"")+"#lookup")}catch(err){}
}
$("go").addEventListener("click",run);
$("filter").addEventListener("input",function(){var f=this.value.trim().toLowerCase();
  Array.prototype.forEach.call(document.querySelectorAll("#archs tbody tr"),function(tr){tr.style.display=!f||tr.textContent.toLowerCase().indexOf(f)>=0?"":"none"})});
try{var sp=new URLSearchParams(location.search);
  if(sp.get("build"))$("b").value=sp.get("build");
  if(sp.get("ollama"))$("o").value=sp.get("ollama");
  if(sp.get("arch")){$("q").value=sp.get("arch");run()}}catch(err){}
})();
"""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@TITLE@@</title>
<meta name="description" content="@@DESC@@">
<link rel="canonical" href="@@URL@@">
<meta property="og:type" content="article">
<meta property="og:title" content="@@TITLE@@">
<meta property="og:description" content="@@DESC@@">
<meta property="og:url" content="@@URL@@">
<script type="application/ld+json">@@LD@@</script>
<style>@@CSS@@</style>
</head>
<body>
<main>
<p class="meta"><a href="/en/">Answers for LLM inference engineers</a></p>
<h1>@@H1@@</h1>
<p class="lede"><strong>"unknown model architecture: 'X'" means the llama.cpp inside your runtime is older than the commit that added X. The fix is a build at or above the number in the table below.</strong> For example, <code>gemma4</code> needs llama.cpp b@@G4B@@ (@@G4D@@) and <code>qwen35</code>, used by Qwen 3.5 and 3.6, needs b@@Q35B@@ (@@Q35D@@). Ollama's bundled llama.cpp has both from @@G4OL@@. llama.cpp @@HEAD@@ knows @@N@@ architecture strings, @@N2026@@ of them added in 2026. The latest Ollama, @@LO@@, bundles @@LOB@@@@NOTYET@@.</p>
<p class="meta">Published @@PUB@@ &middot; Data as of @@ASOF@@ &middot; llama.cpp up to @@HEAD@@ &middot; Ollama up to @@LO@@ &middot; read from git history, nothing was run</p>

<h2 id="lookup">Which build does my GGUF need?</h2>
<p>Paste the error line, or type the value of <code>general.architecture</code>. The two version fields are optional; fill them in to get a yes or no for your install.</p>
<div class="card">
<label for="q">Error message or architecture name</label>
<textarea id="q" placeholder="llama_model_load: error loading model: unknown model architecture: 'gemma4'" spellcheck="false"></textarea>
<div class="grid">
<div><label for="b">Your llama.cpp build (optional)</label><input id="b" placeholder="b8500" autocomplete="off"></div>
<div><label for="o">Your Ollama version (optional)</label><input id="o" placeholder="0.24.0" autocomplete="off"></div>
</div>
<div class="row"><button id="go" type="button">Look up</button><span id="status" role="status"></span></div>
<div id="res" aria-live="polite"></div>
</div>
<p class="note">Runs in your browser on the table below; nothing is sent anywhere. Build number: <code>llama-server --version</code>. Ollama version: <code>ollama --version</code>. Architecture of a file: <code>gguf-dump --no-tensors model.gguf</code> (<code>pip install gguf</code>).</p>

<h2 id="table">Which llama.cpp build first supports each GGUF architecture?</h2>
<p><strong>Each row is one <code>general.architecture</code> string, with the first llama.cpp release tag that contains the commit adding it.</strong> Any later build also has it. Newest first; @@N@@ rows. The Ollama column is the first release whose bundled llama.cpp has the string.</p>
<p><label for="filter">Filter the table</label><input id="filter" placeholder="qwen" autocomplete="off"></p>
<div class="tw wide"><table id="archs">
<thead><tr><th>general.architecture</th><th>llama.cpp from</th><th>Commit that added it</th><th>Ollama from (bundled llama.cpp)</th><th>Ollama's own engine</th><th>vLLM GGUF plugin</th></tr></thead>
<tbody>
@@ROWS@@
</tbody></table></div>
<dl>
<dt>llama.cpp from</dt><dd>The lowest <code>bNNNN</code> tag that contains the commit which first put this string into llama.cpp's architecture table (<code>LLM_ARCH_NAMES</code>, in <code>src/llama-arch.cpp</code> since January 2025 and in <code>llama.cpp</code> / <code>src/llama.cpp</code> before that). The date is the tag's commit date.</dd>
<dt>Ollama from (bundled llama.cpp)</dt><dd>The first Ollama release whose bundled llama.cpp, including Ollama's own patches, has the string, and from which every later release has it. "or earlier" marks architectures already present in the llama.cpp pinned by @@FP@@, the oldest release whose pin resolves to a build.</dd>
<dt>Ollama's own engine</dt><dd>The releases in which Ollama's Go engine registered a model under exactly this name (<code>model.Register</code> in <code>model/models</code>). That engine existed from @@GOF@@ to @@GOL@@. See the note below before relying on it.</dd>
<dt>vLLM GGUF plugin</dt><dd>"tested" means the family is in the "Tested model coverage" table of <code>vllm-gguf-plugin</code> v0.0.5. A dash means untested there, not known to fail.</dd>
</dl>
<p>The same data as JSON: <a href="archs.json">archs.json</a>.</p>

<h2 id="ollama">Which llama.cpp build is inside each Ollama release?</h2>
<p><strong>Ollama @@LO@@ bundles llama.cpp @@LOB@@. From @@FFP@@ the pin is a release tag in the file <code>LLAMA_CPP_VERSION</code>; before that it is a commit.</strong> Consecutive releases with the same pin are merged into one row. Where the pinned commit sits between two tags, the row shows the last tag before it.</p>
<div class="tw"><table>
<thead><tr><th>Ollama releases</th><th>First released</th><th>Bundled llama.cpp</th></tr></thead>
<tbody>
@@PINROWS@@
</tbody></table></div>
<p class="note">Check any release yourself: <code>https://github.com/ollama/ollama/blob/v&lt;version&gt;/LLAMA_CPP_VERSION</code>. Releases before @@FP@@ pin llama.cpp in ways this page did not resolve.</p>

<h2 id="go-engine">Why did Ollama say "unknown model architecture" for a model it listed as supported?</h2>
<p><strong>Between @@GOF@@ and @@GOL@@ Ollama had two loaders, and a file that its own engine could not take fell back to the older bundled llama.cpp.</strong> In that period @@NGO@@ architectures were registered in Ollama's own engine before the bundled llama.cpp knew them. <code>gemma4</code> is the clearest case: the own engine has it from @@G4GF@@, while the bundled llama.cpp stayed at b7437 until @@G4OL@@.</p>
<p>The loader at the <a href="@@OLREPO@@/blob/v0.24.0/llm/server.go#L148">v0.24.0 tag</a> tries the own engine for a fixed list of architectures, refuses models that come with a separate projector file ("split vision models aren't supported"), and on any failure switches to the bundled llama.cpp. So a model pulled from the Ollama library worked, while a Hugging Face GGUF with a separate <code>mmproj</code> file, or with a layout the own engine did not expect, reported "unknown model architecture" from the old llama.cpp. From @@NOGO@@ the own-engine model code is gone and the bundled llama.cpp column is the whole answer.</p>
<p class="note">Ollama's own engine also used its own names in places: it registered <code>gptoss</code> first and added the upstream spelling <code>gpt-oss</code> later. The column above only counts exact matches with the upstream string.</p>

<h2 id="still-fails">The build is new enough and the model still fails. What else is there?</h2>
<ul>
<li><strong>The app did not actually update its runtime.</strong> Desktop apps ship llama.cpp as a separate runtime package that can stay on an old version after the app updates. Check the runtime version the app reports, not the app version.</li>
<li><strong>The file was re-uploaded for a newer build.</strong> Converters change, and uploaders replace files. A GGUF published today can need tensors or metadata that the first supporting build did not read. Use the newest build before debugging anything else.</li>
<li><strong>Extra blocks in the file.</strong> GGUFs that embed multi-token-prediction (<code>nextn</code>) layers or a vision projector need support for that feature in addition to the base architecture.</li>
<li><strong>A fork-only architecture.</strong> If the lookup says the name is not in upstream llama.cpp, the file targets a fork or a pull request that is not merged. The model card usually names it.</li>
<li><strong>The file is incomplete.</strong> A truncated download fails earlier, with a magic-number or tensor-data error instead of an architecture error.</li>
</ul>

<h2 id="vllm">Does vLLM read the same architecture strings?</h2>
<p><strong>No. vLLM does not use llama.cpp; it maps GGUF tensors onto its own PyTorch model classes, so a GGUF that llama.cpp loads can still fail in vLLM.</strong> GGUF loading moved out of vLLM into <a href="https://github.com/vllm-project/vllm-gguf-plugin"><code>vllm-gguf-plugin</code></a> in v0.24.0 (2026-06-27). The plugin's README lists the families covered by its generation tests: Qwen 2.5, Qwen 3, Phi 3.5, GPT-2, StableLM, Gemma 3, OLMoE, Gemma 4, Qwen 3.5 and Qwen 3.6. It states that other vLLM-supported architectures may work when their tensor names map to the Hugging Face model, and that being a vLLM-supported model does not guarantee GGUF compatibility.</p>
<pre><code>uv pip install vllm-gguf-plugin
vllm serve unsloth/Qwen3-0.6B-GGUF:Q4_K_M --tokenizer Qwen/Qwen3-0.6B</code></pre>
<p class="note">On vLLM older than v0.24.0 the built-in loader relied on the Transformers GGUF parser, and the message was "GGUF model with architecture ... is not supported yet".</p>

<h2 id="method">How was this table built?</h2>
<ul>
<li><strong>Architecture strings:</strong> every <code>{ LLM_ARCH_*, "name" }</code> entry at llama.cpp @@HEAD@@ (@@ASOF@@).</li>
<li><strong>Introducing commit:</strong> the oldest commit whose diff adds the entry, following the table through the January 2025 file split back to its first appearance in August 2023.</li>
<li><strong>First build:</strong> <code>git describe --contains --match "b*"</code> on that commit.</li>
<li><strong>Ollama pin:</strong> at each of @@NOT@@ release tags, <code>LLAMA_CPP_VERSION</code>, or <code>FETCH_HEAD</code> in <code>Makefile.sync</code>, or <code>LLAMACPP_BASE_COMMIT</code> in <code>llama/vendoring</code>, or the <code>llm/llama.cpp</code> submodule commit, resolved against the llama.cpp history. @@NPIN@@ tags resolve.</li>
<li><strong>Ollama patches:</strong> the architecture table in the vendored, already patched source at @@VF@@ to @@VL@@, and added <code>LLM_ARCH</code> entries in the patch directories of the other releases. This moves @@NPATCH@@ rows earlier than the pin alone would.</li>
<li><strong>Own engine:</strong> <code>model.Register("...")</code> calls under <code>model/models</code> at each tag.</li>
<li><strong>vLLM:</strong> the plugin README at v0.0.5 and the vLLM commit that moved GGUF out of the main repository.</li>
</ul>

<h2 id="limits">What this page does not cover</h2>
<ul>
<li>No model was loaded for this page. It reports when a name entered the source, which is the condition for the "unknown model architecture" error and nothing more.</li>
<li>Ollama carries patches on top of its pinned llama.cpp. For releases that keep the patched source in the repository (@@VF@@ to @@VL@@) the table reads that source, and for the others it reads the architecture entries in Ollama's patch files; rows marked "Ollama patch" come from there. Other effects of those patches were not examined.</li>
<li>LM Studio, Jan, KoboldCpp, llama-cpp-python and other bundlers are not mapped. Each bundles some llama.cpp build; once you know that build number, the first table applies.</li>
<li>Architectures removed from llama.cpp before @@HEAD@@, and names that exist only in forks, are not listed.</li>
<li>Regenerated when new architectures land; the "as of" date at the top says how current it is.</li>
</ul>

<h2 id="faq">Questions</h2>
<dl>
@@FAQ@@
</dl>

<p class="note">Related: <a href="/en/vllm-torch-cuda-driver-matrix/">vLLM compatibility matrix: PyTorch, CUDA and driver by release</a>.</p>

<h2 id="sources">Sources</h2>
<ul>
<li>llama.cpp: <a href="@@LCREPO@@/blob/master/src/llama-arch.cpp">src/llama-arch.cpp</a>, <a href="@@LCREPO@@/releases">releases</a></li>
<li>Ollama: <a href="@@OLREPO@@/blob/main/LLAMA_CPP_VERSION">LLAMA_CPP_VERSION</a>, <a href="@@OLREPO@@/blob/main/llama/README.md">llama/README.md</a>, <a href="@@OLREPO@@/releases">releases</a>, <a href="@@OLREPO@@/blob/v0.24.0/llm/server.go">llm/server.go at v0.24.0</a></li>
<li>vLLM: <a href="https://docs.vllm.ai/en/latest/features/quantization/gguf/">GGUF page</a>, <a href="https://github.com/vllm-project/vllm-gguf-plugin">vllm-gguf-plugin</a>, issue <a href="https://github.com/vllm-project/vllm/issues/36456">#36456</a></li>
<li>Reports of the error: <a href="https://huggingface.co/unsloth/Qwen3.6-27B-GGUF/discussions">unsloth/Qwen3.6-27B-GGUF discussions</a>, LM Studio bug tracker <a href="https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1728">#1728</a>, Ollama <a href="https://github.com/ollama/ollama/issues/16282">#16282</a></li>
</ul>
</main>
<script type="application/json" id="arch-data">@@DATA@@</script>
<script>@@JS@@</script>
</body>
</html>
"""

notyet = ""
if not_in_ollama:
    notyet = ", so it cannot yet load " + ", ".join("<code>%s</code>" % e(a) for a in not_in_ollama) + " (b%d)" % min(BY[a]["b"] for a in not_in_ollama)
subs = {
    "TITLE": e(TITLE), "DESC": e(DESC), "URL": URL, "H1": e(H1), "LD": LD_JSON, "CSS": CSS.strip(), "JS": JS.strip(),
    "DATA": DATA_JSON, "ROWS": ROWS, "PINROWS": PINROWS, "FAQ": FAQ_HTML, "ASOF": AS_OF, "PUB": PUBLISHED,
    "N": str(len(A)), "N2026": str(N_2026), "HEAD": HEAD_TAG, "LO": LATEST_O["tag"][1:], "LOB": LATEST_O["pinned_build"], "NOTYET": notyet,
    "G4B": str(g4["b"]), "G4D": g4["d"], "G4OL": g4["ol"][1:], "G4GF": g4["gf"][1:], "Q35B": str(q35["b"]), "Q35D": q35["d"],
    "FP": FIRST_PIN["tag"][1:], "FFP": FIRST_FILE_PIN["tag"][1:], "GOF": FIRST_GO_TAG["tag"][1:], "GOL": LAST_GO_TAG["tag"][1:],
    "NOGO": FIRST_NO_GO["tag"][1:], "NGO": str(len(go_earlier)), "NOT": str(len(OT)), "NPIN": str(len(pinned)),
    "LCREPO": LC, "OLREPO": OL, "VF": "0.3.13", "VL": "0.24.0", "NPATCH": str(sum(1 for x in rows_data if x["patch"] or x["er"])),
}
page = PAGE
for k, v in subs.items():
    page = page.replace("@@" + k + "@@", v)
left = re.findall(r"@@[A-Z0-9_]+@@", page)
assert not left, left
page.encode("ascii")

out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
pub = {"as_of": AS_OF, "llama_cpp_head": HEAD_TAG, "ollama_latest": T["ollama_latest"],
       "architectures": [{"architecture": x["a"], "llama_cpp_first_build": "b%d" % x["b"], "llama_cpp_first_build_date": x["d"],
                          "llama_cpp_commit": next(r["llama_commit"] for r in A if r["arch"] == x["a"]),
                          "ollama_first_release_bundled_llama_cpp": x["ol"], "ollama_own_engine": [x["gf"], x["gl"]] if x["gf"] else None,
                          "vllm_gguf_plugin_tested": x["a"] in VLLM_TESTED} for x in rows_data],
       "ollama_releases": [{"release": t["tag"], "date": t["date"], "llama_cpp_build": t["pinned_build"], "pin": t["pin"], "pin_is_exact_tag": t["pin_exact"]} for t in pinned]}
(out_dir / "archs.json").write_text(json.dumps(pub, indent=1), encoding="ascii")
print("index.html", len(page), "bytes;", len(A), "archs;", len(ranges), "pin ranges; go-earlier", len(go_earlier), "; not in ollama", not_in_ollama)
