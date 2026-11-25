#!/usr/bin/env python3
"""Build en/pydantic-import-name-version-lookup/ (index.html; pydantic.json is copied next to it).

Usage: python3 -I build_page.py <dir with pydantic.json> out_dir PUBLISHED MODIFIED chk.json anchors.json mig.json
ASCII only. The facts the prose names are asserted. style.css is shared with .github/llama-args; tool.js is the shared
lookup of .github/pta-imports, inlined with LOOKUP_LIBS = ["pydantic"]. mig.json is written by mig_hist.py.
"""
import html, json, re, shutil, sys
from pathlib import Path

src, out_dir, PUB, MOD = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
CHK, ANC, MIG = (json.load(open(a)) for a in sys.argv[5:8])
HERE = Path(__file__).resolve().parent
D = json.load(open(src / "pydantic.json"))
R, T, N, LATEST = D["releases"], D["ranges"], len(D["releases"]), D["latest"]
e = html.escape
URL = "https://erimaki-kobo.github.io/en/pydantic-import-name-version-lookup/"
TITLE = "cannot import name 'BaseSettings' from 'pydantic' and other v2 errors"
H1 = "ImportError: cannot import name 'BaseSettings' (or ModelMetaclass, field_validator, any name) from 'pydantic...': which pydantic releases have it"
DESC = ("pydantic 2.0 moved BaseSettings to pydantic-settings and removed 197 names, which raise PydanticImportError. "
        "The v1 API stays in pydantic.v1. Paste the error.")
assert len(TITLE) <= 70 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))

def pairs(ri):
    r = T[ri]
    return list(zip(r[::2], r[1::2]))


def span(m, n):
    a, b = pairs(D["names"][m][n])[-1]
    return R[a][0], (R[b][0] if b else None)


def mspan(m):
    a, b = pairs(D["mods"][m])[-1]
    return [(R[a][0], R[b][0] if b else None)]


def first(m, n):
    return R[pairs(D["names"][m][n])[0][0]][0]


def idx(v):
    return [k for k, r in enumerate(R) if r[0] == v][0]


date_of = lambda v: R[idx(v)][1]
last_before = lambda v: R[idx(v) - 1][2]

alive = lambda m, n: n in D["names"].get(m, {}) and not pairs(D["names"][m][n])[-1][1]
gone_at = lambda m, n: n in D["names"].get(m, {}) and R[pairs(D["names"][m][n])[-1][1]][0] if pairs(D["names"][m][n])[-1][1] else None
LM = MIG["v" + LATEST]
REMOVED = LM["removed"]
key = lambda v: tuple(int(x) for x in v.split("."))
LAST1 = last_before("2.0")   # the last patch of 1.10
d2 = date_of("2.0")
assert span("", "BaseSettings") == ("0.0.2", "2.0") and last_before("2.0") == "1.10.27" and "pydantic:BaseSettings" in REMOVED
assert span("", "field_validator") == ("2.0", None) and span("", "model_validator") == ("2.0", None) and span("", "TypeAdapter") == ("2.0", None)
assert span("", "validator")[1] is None and span("", "root_validator")[1] is None   # still importable, deprecated
assert span("main", "ModelMetaclass") == ("1.0", "2.0") and span("fields", "ModelField") == ("1.0", "2.0") and span("", "Required")[1] == "2.0"
assert span("", "ConfigDict")[0] == "1.10.0" and span("", "with_config") == ("2.7.0", None) and mspan("v1") == [("2.0", None)]
assert len(REMOVED) == 197 and LM["moved"]["pydantic.generics:GenericModel"] == ["pydantic.BaseModel", "MOVED_IN_V2"]
assert LM["moved"]["pydantic:PyObject"][0] == "pydantic.types:ImportString" and LM["moved"]["pydantic.utils:deep_update"][0] == "pydantic.v1.utils:deep_update"
assert all(a["text"] and (a["data"] is None or a["data"] == a["expected"]) for a in ANC) and len(ANC) == 19
assert [a["expected"] for a in ANC if a["module"] == "v1" and a["data"] is None] == [False, True]
n_moved = len(LM["moved"])

HINTS = {}
def add(m, n, h):
    if n in D["names"].get(m, {}) and pairs(D["names"][m][n])[-1][1] and ("pydantic:%s:%s" % (m, n)) not in HINTS:
        HINTS["pydantic:%s:%s" % (m, n)] = h
add("", "BaseSettings", "<code>pip install pydantic-settings</code>, then <code>from pydantic_settings import BaseSettings, SettingsConfigDict</code>. Or pin <code>pydantic&lt;2</code>.")
add("main", "ModelMetaclass", "private in 2.x: <code>from pydantic._internal._model_construction import ModelMetaclass</code>; the 1.x one is <code>from pydantic.v1.main import ModelMetaclass</code>.")
add("fields", "ModelField", "2.x keeps field information in <code>pydantic.fields.FieldInfo</code> (<code>Model.model_fields</code>); the 1.x one is <code>from pydantic.v1.fields import ModelField</code>.")
v1_now = lambda m, n: alive("v1" + ("." + m if m else ""), n)
for path in REMOVED:
    mod, n = path.split(":")
    m = mod[len("pydantic."):] if mod != "pydantic" else ""
    alt = (" The 1.x one: <code>from pydantic.v1%s import %s</code>." % ("." + m if m else "", n)) if v1_now(m, n) else ""
    add(m, n, "raises PydanticImportError from 2.0: <code>`%s` has been removed in V2.</code>%s" % (path, alt))
for m, names in D["names"].items():
    if m.startswith(("v1", "_internal", "deprecated")):
        continue
    for n in names:
        if gone_at(m, n) == "2.0" and v1_now(m, n) and not n.startswith("_"):
            add(m, n, "the 1.x one: <code>from pydantic.v1%s import %s</code> (pydantic 2.0 and later)." % ("." + m if m else "", n))
for k in HINTS:
    l, m, n = k.split(":")
    assert pairs(D["names"][m][n])[-1][1], k
assert len(HINTS) > 150, len(HINTS)
n_mods, n_pairs = len(D["mods"]), sum(len(v) for v in D["names"].values())
kb = (src / "pydantic.json").stat().st_size // 1024

ROWS = [("BaseSettings", "<code>pip install pydantic-settings</code>; <code>from pydantic_settings import BaseSettings</code>"),
        ("validator, root_validator (still import, deprecated)", "<code>field_validator</code>, <code>model_validator</code>"),
        ("class Config: inside a model", "<code>model_config = ConfigDict(...)</code>"),
        ("parse_obj_as, schema_of (still import, deprecated)", "<code>TypeAdapter(T).validate_python(...)</code>, <code>.json_schema()</code>"),
        ("pydantic.main.ModelMetaclass", "private: <code>pydantic._internal._model_construction.ModelMetaclass</code>"),
        ("pydantic.fields.ModelField", "<code>pydantic.fields.FieldInfo</code>, <code>Model.model_fields</code>"),
        ("Required, ConstrainedStr, constr-style classes, stricturl, parse_raw_as and 190 more", "raise PydanticImportError; <code>pydantic.v1</code> keeps them"),
        ("PyObject", "<code>ImportString</code> (redirected with a warning from 2.1.0)"),
        ("pydantic.generics.GenericModel", "<code>BaseModel</code> with <code>Generic[T]</code> (redirected with a warning from 2.1.0)")]
for name, ok in [("", "field_validator"), ("", "model_validator"), ("", "ConfigDict"), ("", "TypeAdapter"), ("", "ImportString"), ("fields", "FieldInfo")]:
    assert alive(name, ok), ok
for nm in ("parse_obj_as", "schema_of", "validate_arguments"):
    assert alive("", nm) or alive("tools", nm), nm
assert "pydantic:ConstrainedStr" in REMOVED and "pydantic:stricturl" in REMOVED and "pydantic:parse_raw_as" in REMOVED
fix_rows = "\n".join("<tr><td>%s</td><td>%s</td></tr>" % (a if "<" in a else "<code>%s</code>" % a if " " not in a else e(a), b) for a, b in ROWS)

FAQ = [
    ("How do I fix \"cannot import name 'BaseSettings' from 'pydantic'\"?",
     "pydantic 2.0 (%s) moved it to its own package: pip install pydantic-settings, then from pydantic_settings import BaseSettings. "
     "In 2.x the error is PydanticImportError: \"`BaseSettings` has been moved to the `pydantic-settings` package.\" To keep old code "
     "unchanged, pin pip install \"pydantic<2\" (%s is the last 1.x)." % (d2, LAST1)),
    ("What does \"PydanticImportError: `pydantic:Required` has been removed in V2\" mean?",
     "%d names (in %s) are listed in pydantic's migration table as removed; importing one raises this error. Each has a 2.x "
     "replacement (Required becomes a field without a default, ConstrainedStr becomes Annotated[str, StringConstraints(...)], "
     "parse_raw_as becomes TypeAdapter(T).validate_json). To keep the 1.x behaviour, import it from pydantic.v1, which carries the "
     "whole 1.x API from 2.0 on." % (len(REMOVED), LATEST)),
    ("How do I fix \"cannot import name 'ModelMetaclass' from 'pydantic.main'\"?",
     "pydantic 2.0 moved the metaclass to the private module pydantic._internal._model_construction. Code that needs it on 2.x "
     "imports it from there (it can change without notice); code written for 1.x can use from pydantic.v1.main import ModelMetaclass."),
    ("How do I fix \"cannot import name 'field_validator' from 'pydantic'\"?",
     "You have pydantic 1.x: field_validator, model_validator, TypeAdapter and computed_field are new in 2.0. pip install "
     "\"pydantic>=2\", or keep validator and root_validator, which work in both."),
    ("Can one codebase import from pydantic.v1 on both 1.x and 2.x?",
     "Yes, from pydantic 1.10.15: that release added a pydantic.v1 module that aliases the 1.x namespace, so from pydantic.v1 import "
     "BaseModel works on 1.10.15 and later and on every 2.x."),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1[:110], "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["pydantic", "ImportError", "PydanticImportError", "pydantic-settings"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"}, "mainEntityOfPage": URL},
    {"@type": "WebApplication", "name": "pydantic import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError, a PydanticImportError or an import statement and get the pydantic releases in which that name can be imported from that module, the range to pin, and what to import instead.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from pydantic, by release", "url": URL + "pydantic.json", "dateModified": MOD,
     "description": "For %d pydantic releases (%s to %s): the names importable from every module as release ranges, including those served by the 2.x migration table." % (N, R[0][0], LATEST),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "pydantic.json"}]},
    {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
LD = json.dumps(ld)
assert "</" not in LD
css = (HERE.parent / "llama-args" / "style.css").read_text(encoding="ascii")
css += "\n.pin code{white-space:nowrap}.ex button{font-size:.82rem;padding:3px 9px;margin:0 4px 6px 0;background:transparent;color:var(--acc)}\n#res td:first-child{min-width:9em}td code,p code,li code,h1,h2,h3{overflow-wrap:anywhere}main p,main li{overflow-wrap:break-word}\n"
js = (HERE.parent / "pta-imports" / "tool.js").read_text(encoding="ascii")
assert "</script" not in js and "window.LOOKUP_LIBS" in js
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
EX = [("ImportError: cannot import name 'BaseSettings' from 'pydantic' (/usr/lib/python3/site-packages/pydantic/__init__.py)", "2.10.0", "BaseSettings"),
      ("pydantic.errors.PydanticImportError: `pydantic:Required` has been removed in V2.", "", "Required"),
      ("from pydantic.main import ModelMetaclass", "2.5.0", "ModelMetaclass"),
      ("from pydantic import field_validator, model_validator", "1.10.0", "field_validator"),
      ("from pydantic.fields import ModelField", "", "ModelField")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(lb)) for q, v, lb in EX)
GH = "https://github.com/pydantic/pydantic/blob/"
a_rows = "\n".join("<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>" % (
    e("pydantic." + a["module"] + ("." + a["name"] if a["name"] else "") if a["module"] else "pydantic." + a["name"]), a["release"],
    ("importable" if a["expected"] else "not importable") + ("" if a["data"] is not None else " (text only)")) for a in ANC)
hint_kb = max(1, len(json.dumps(HINTS)) // 1024)

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
<p class="lede"><strong>pydantic 2.0 ({d2}) moved <code>BaseSettings</code> to the separate <code>pydantic-settings</code> package and removed {len(REMOVED)} names, which now raise <code>PydanticImportError</code>; {LAST1} is the last 1.x.</strong> Fix the first with <code>pip install pydantic-settings</code> and <code>from pydantic_settings import BaseSettings</code>. For the others, either move to the 2.x API (table below) or import the old name from <code>pydantic.v1</code>, which carries the whole 1.x API in every 2.x release (and, as an alias, in 1.10.15 and later). <code>validator</code> and <code>root_validator</code> still import in {LATEST}, with a deprecation warning. For any other name, paste the error below.</p>
<p class="meta">Published {PUB} &middot; Data as of {D["asof"]} &middot; the first release of every minor, pydantic {R[0][0]} to {LATEST} ({N} releases) &middot; read from the release tags, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The error line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'BaseSettings' from 'pydantic'"></textarea>
<div class="grid">
<div><label for="v">Your pydantic (optional; <code>pip show pydantic</code>)</label><input id="v" inputmode="decimal" placeholder="for example 2.10.0"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="pydantic.json">pydantic.json</a> ({kb} KB) and {hint_kb} KB of hints in this page; nothing you paste is sent anywhere. Covers {n_pairs:,} module-and-name pairs in {n_mods} modules.</p>
</div>

<h2 id="v2">What replaces the 1.x names in 2.x?</h2>
<div class="tw"><table class="flt">
<thead><tr><th>1.x</th><th>2.x</th></tr></thead>
<tbody>
{fix_rows}
</tbody></table></div>
<p>Moved names are listed in <code>pydantic/_migration.py</code>: {n_moved} of them still import from the old place in {LATEST} and warn (for example <code>pydantic.utils.deep_update</code>, served from <code>pydantic.v1.utils</code>); the {len(REMOVED)} removed ones raise. The lookup counts the first group as importable and gives the message for the second.</p>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the Python files at the release tags of pydantic/pydantic (the first release of every minor, plus the latest), parsed with Python's <code>ast</code> module.</strong> The tags match the wheels on PyPI (every <code>.py</code> file compared by git blob hash at 1.10.0, 2.0, 2.7.0 and {LATEST}). A module's names are everything it binds at module level, what <code>from .x import *</code> brings in, the names of the lazy-import table that <code>pydantic/__init__.py</code> serves through <code>__getattr__</code> from 2.0, and the moved names of the migration table in each module that installs <code>getattr_migration</code>.</p>
<p>Checks: (1) the top-level names are found as plain text in <code>pydantic/__init__.py</code> (or its migration table) in every release of their range ({CHK["CHK_TOP_PAIRS"]:,} name-and-release pairs) and are not bound on either side ({CHK["CHK_TOP_EDGES"]} edges). (2) A regular expression finds {CHK["CHK_DEFS"]:,} definitions in {CHK["CHK_DEF_FILES"]:,} file versions; all are among the names read. (3) {len(ANC)} release checks by text search in the tagged files agree:</p>
<div class="tw"><table>
<thead><tr><th>Name</th><th>Release</th><th>Text and data</th></tr></thead>
<tbody>
{a_rows}
</tbody></table></div>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed or run. "Has it" means the import statement resolves in the Python files of that release.</li>
<li>Patch releases are not read: a name added or removed in x.y.1 shows up at the next minor. pydantic-settings and pydantic-core are not covered.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>pydantic/pydantic: <a href="{GH}v{LATEST}/pydantic/_migration.py">pydantic/_migration.py at v{LATEST}</a> (the moved and removed names and the messages), <a href="{GH}v1.10.15/pydantic/v1.py">pydantic/v1.py at v1.10.15</a>, and the release tags.</li>
<li><a href="https://pypi.org/project/pydantic/#history">pydantic on PyPI</a> (release dates, and the wheels compared with the tags) and <a href="https://pypi.org/project/pydantic-settings/">pydantic-settings</a>.</li>
</ul>
<p>The same data as JSON: <a href="pydantic.json">pydantic.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/langchain-import-name-version-lookup/">"cannot import name ... from 'langchain'"</a> &middot; <a href="/en/openai-python-import-name-version-lookup/">"... from 'openai'"</a> &middot; <a href="/en/llama-index-import-name-version-lookup/">"... from 'llama_index'"</a>.</p>
</main>
<script>window.LOOKUP_LIBS = ["pydantic"]; window.PTA_HINTS = {json.dumps(HINTS)};</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
shutil.copyfile(src / "pydantic.json", out_dir / "pydantic.json")
print("index.html %d bytes | hints %d | modules %d | pairs %d" % (len(page), len(HINTS), n_mods, n_pairs), file=sys.stderr)
