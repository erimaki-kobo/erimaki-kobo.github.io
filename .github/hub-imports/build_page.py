#!/usr/bin/env python3
"""Build en/huggingface-hub-import-name-version-lookup/ (index.html; data.json is copied next to it).

Usage: python3 -I build_page.py data.json out_dir PUBLISHED MODIFIED checks.json
ASCII only. Numbers come from data.json; the facts the prose names are asserted, so a release that changes one of
them stops the build. style.css is shared with .github/llama-args; tool.js is inlined.
"""
import html, json, shutil, sys
from pathlib import Path

data_p, out_dir, PUB, MOD = sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4]
checks = json.load(open(sys.argv[5]))
HERE = Path(__file__).resolve().parent
D = json.load(open(data_p))
R, N = D["releases"], len(D["releases"])
e = html.escape
URL = "https://erimaki-kobo.github.io/en/huggingface-hub-import-name-version-lookup/"
TITLE = "cannot import name 'cached_download' from huggingface_hub"
H1 = "ImportError: cannot import name 'cached_download' (or HfFolder, or any name) from 'huggingface_hub': which releases have it"
DESC = ("cached_download left huggingface_hub in 0.26.0, HfFolder in 1.0.0. Paste the error: get the releases with the "
        "name, the pin and the fixed diffusers version.")
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))
LABEL = {"top": "huggingface_hub", "utils": "huggingface_hub.utils", "errors": "huggingface_hub.errors"}
LIBNAME = {"diffusers": "diffusers", "sentence-transformers": "sentence-transformers", "gradio": "gradio", "datasets": "datasets", "peft": "peft"}


def pairs(kind, name):
    r = D[kind][name]
    r = r[1:] if kind == "top" else r
    return list(zip(r[::2], r[1::2]))


def span(kind, name):
    ps = pairs(kind, name)
    return R[ps[-1][0]][0], (R[ps[-1][1]][0] if ps[-1][1] else None)


def minor(v):
    return ".".join(v.split(".")[:2]) + ".x"


def range_text(p):
    if p[1] == 0:
        return "from <strong>%s</strong> (%s), still in %s" % (R[p[0]][0], R[p[0]][1], D["latest"])
    return "<strong>%s</strong> through <strong>%s</strong>; gone in %s (%s)" % (R[p[0]][0], R[p[1] - 1][2], R[p[1]][0], R[p[1]][1])


# replacements, each from the deprecation message or docstring of the last release that had the name
HINTS = {
    "top:cached_download": "<code>hf_hub_download</code> (its deprecation message: \"Use `hf_hub_download` instead.\"). It takes a repo id and a file name, not a URL.",
    "top:InferenceApi": "<code>InferenceClient</code> (its deprecation message: \"deprecated in favor of the more feature-complete `InferenceClient`\").",
    "top:Repository": "the HTTP-based methods of <code>HfApi</code>, such as <code>upload_file</code>, <code>upload_folder</code> and <code>snapshot_download</code> (its docstring: \"deprecated in favor of the http-based alternatives implemented in `HfApi`\").",
    "top:HfFolder": "<code>login()</code> to store a token (the note in its source: \"Use `huggingface_hub.login` instead\") and <code>get_token()</code> to read one.",
    "utils:HfFolder": "<code>huggingface_hub.login()</code> to store a token and <code>huggingface_hub.get_token()</code> to read one.",
    "top:ModelFilter": "pass the filter parameters as keyword arguments directly to <code>list_models</code> (its deprecation message).",
    "top:DatasetFilter": "pass the filter parameters as keyword arguments directly to <code>list_datasets</code> (its deprecation message).",
    "top:update_repo_visibility": "<code>update_repo_settings</code> (its deprecation message).",
}
assert span("top", "cached_download") == ("0.10.0", "0.26.0") or span("top", "cached_download")[1] == "0.26.0"
for n in ("HfFolder", "InferenceApi", "Repository", "update_repo_visibility", "configure_http_backend"):
    assert span("top", n)[1] == "1.0.0", n
assert span("top", "ModelFilter")[1] == "0.24.0" and span("top", "DatasetFilter")[1] == "0.24.0"
assert span("top", "hf_hub_download")[1] is None and span("top", "get_token") == ("0.20.0", None) and span("top", "update_repo_settings")[1] is None
assert span("top", "InferenceClient") == ("0.15.0", None)

U = D["users"]


def users_text(key):
    u = U.get(key)
    if not u:
        return ""
    parts = []
    for lib in sorted(u):
        for a, b, f, nxt in u[lib]:
            parts.append("<strong>%s</strong> %s to %s%s" % (lib, a, minor(b), (", not from %s" % nxt) if nxt else ", still"))
    return "<br>Imported at module level by: " + "; ".join(parts) + "."


def urun(key, lib):
    rr = U[key][lib]
    assert len(rr) == 1, (key, lib, rr)
    return rr[0]


cd_d, cd_s = urun("top:cached_download", "diffusers"), urun("top:cached_download", "sentence-transformers")
hf_g, hf_ds = urun("top:HfFolder", "gradio"), urun("top:HfFolder", "datasets")
assert (cd_d[0], cd_d[1], cd_d[3]) == ("0.1.0", "0.28.0", "0.29.0") and (cd_s[1], cd_s[3]) == ("2.2.0", "2.3.0")
assert (hf_g[0], hf_g[1], hf_g[3]) == ("4.9.0", "5.7.0", "5.8.0") and (hf_ds[1], hf_ds[3]) == ("2.15.0", "2.16.0")
i26 = [i for i in range(N) if R[i][0] == "0.26.0"][0]
i10 = [i for i in range(N) if R[i][0] == "1.0.0"][0]
last25, last0 = R[i26 - 1][2], R[i10 - 1][2]

COMMON = [("top", n) for n in """cached_download HfFolder Repository InferenceApi ModelFilter DatasetFilter ModelSearchArguments
update_repo_visibility configure_http_backend list_files_info hf_hub_download snapshot_download InferenceClient get_token
split_torch_state_dict_into_shards DDUFEntry HfFileSystem file_exists list_repo_tree is_offline_mode hf_raise_for_status
set_client_factory""".split()]
COMMON += [("utils", n) for n in "OfflineModeIsEnabled HfHubHTTPError EntryNotFoundError HfFolder is_hf_transfer_available httpx".split()]
COMMON += [("errors", n) for n in "EntryNotFoundError RepositoryNotFoundError HfHubHTTPError OfflineModeIsEnabled HFValidationError".split()]


def common_row(kind, name):
    assert name in D[kind], (kind, name)
    ps = pairs(kind, name)
    now = ps[-1][1] == 0
    key = "%s:%s" % (kind, name)
    h = HINTS.get(key, "") if not now else ""
    return "<tr><td><code>%s</code><br><span class=\"note\">%s</span></td><td><span class=\"s %s\">%s</span></td><td>%s%s%s</td></tr>" % (
        e(name), LABEL[kind], "y" if now else "n", "imports" if now else "gone", "; ".join(range_text(p) for p in ps),
        ("<br>Instead: " + h) if h else "", users_text(key) if not now else "")


common_rows = "\n".join(common_row(k, n) for k, n in COMMON)

GONE = {}
for n in D["top"]:
    for a, b in pairs("top", n):
        if b:
            GONE.setdefault(b, []).append(n)
NOTES = {"1.0.0": "the git-based <code>Repository</code>, the legacy <code>InferenceApi</code>, <code>HfFolder</code>, the Keras and TensorFlow helpers, and the <code>requests</code>-based <code>configure_http_backend</code>",
         "0.26.0": "<code>cached_download</code> and four generated inference types"}
rows_gone = []
for i in sorted(GONE, reverse=True):
    names = sorted(GONE[i])
    rows_gone.append("<tr><td>%s</td><td>%s</td><td>%d</td><td>%s%s</td></tr>" % (
        R[i][0], R[i][1], len(names), ", ".join("<code>%s</code>" % e(n) for n in names),
        ("<br><span class=\"note\">%s</span>" % NOTES[R[i][0]]) if R[i][0] in NOTES else ""))
n_top, n_now = len(D["top"]), sum(1 for n in D["top"] if pairs("top", n)[-1][1] == 0)
n_gone = n_top - n_now
assert n_gone == len({n for v in GONE.values() for n in v if pairs("top", n)[-1][1]})


def needs_rows(lib):
    out = []
    nd = D["needs"][lib]
    for a, b, lo, lo_n, hi, hi_n in nd["runs"]:
        low = ("&ge; %s <span class=\"note\">(<code>%s</code>)</span>" % (R[lo][0], e(lo_n))) if lo_n else "any"
        high = ("&lt; %s <span class=\"note\">(<code>%s</code>)</span>" % (R[hi][0], e(hi_n))) if hi else "no upper limit from imports"
        cls = "n" if hi else "y"
        out.append("<tr><td>%s</td><td>%s</td><td>%s</td><td><span class=\"s %s\">%s</span></td></tr>" % (
            lib if not out else "", a if a == b else "%s to %s" % (a, minor(b)), low, cls, high))
    return "\n".join(out)


needs_html = "\n".join(needs_rows(lib) for lib in ("diffusers", "sentence-transformers", "gradio", "datasets", "peft"))
libs_latest = ", ".join("%s %s" % (l, D["needs"][l]["latest"]) for l in ("diffusers", "sentence-transformers", "gradio", "datasets", "peft"))
n_lib_versions = sum(len(D["needs"][l]["dates"]) for l in D["needs"])
assert not any(r[4] for r in D["needs"]["peft"]["runs"])
assert set(D["not_names"]) <= {"top:constants", "utils:insecure_hashlib"}, D["not_names"]

FAQ = [
    ("Which huggingface_hub version removed cached_download?",
     "huggingface_hub 0.26.0 (%s). cached_download is importable through %s. Its deprecation message names the replacement: "
     "hf_hub_download, which takes a repo id and a file name where cached_download took a URL." % (R[i26][1], last25)),
    ("How do I fix \"cannot import name 'cached_download' from 'huggingface_hub'\" with diffusers or sentence-transformers?",
     "Upgrade the library that asks for it: diffusers imports cached_download at module level from 0.1.0 to 0.28.x and stops in 0.29.0, "
     "sentence-transformers from 2.0.0 to 2.2.x and stops in 2.3.0. If you cannot upgrade it, pin the hub instead: "
     "pip install \"huggingface_hub<0.26.0\" (%s is the last release that has the name)." % last25),
    ("Why can't I import HfFolder from huggingface_hub?",
     "huggingface_hub 1.0.0 (%s) removed HfFolder; %s is the last release that has it. Use login() to store a token and get_token() to "
     "read one. gradio imports HfFolder at module level from 4.9.0 to 5.7.x and stops in 5.8.0; datasets from 1.13.0 to 2.15.x and "
     "stops in 2.16.0." % (R[i10][1], last0)),
    ("Does pinning huggingface_hub break anything else?",
     "It can. Newer releases of the same libraries import names that old hub releases do not have: for example diffusers 0.33.0 and later "
     "need huggingface_hub 0.27.0 or newer for DDUFEntry. Pick a hub release inside the range of every library you have installed; the "
     "table on this page gives that range per library version."),
    ("The name in my error is not cached_download or HfFolder. Does this page cover it?",
     "Yes. The lookup covers every name that huggingface_hub, huggingface_hub.utils and huggingface_hub.errors have exported from %s to "
     "%s: %d top-level names, of which %d are gone from the newest release." % (R[0][0], D["latest"], n_top, n_gone)),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1, "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "about": ["huggingface_hub", "ImportError", "diffusers", "sentence-transformers", "gradio"],
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/"},
     "mainEntityOfPage": URL, "isBasedOn": URL + "data.json"},
    {"@type": "WebApplication", "name": "huggingface_hub import name lookup", "url": URL + "#lookup",
     "description": "Paste an ImportError or a name and get the huggingface_hub releases that export it, the range to pin, and the library versions that still import it.",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
     "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}},
    {"@type": "Dataset", "name": "Names importable from huggingface_hub by release", "url": URL + "data.json", "dateModified": MOD,
     "description": "For %d releases of huggingface_hub (%s to %s): the names importable from huggingface_hub, huggingface_hub.utils and "
                    "huggingface_hub.errors as release ranges, and the releases of diffusers, sentence-transformers, gradio, datasets and peft "
                    "that import them at module level. Read from the source of each release tag." % (N, R[0][0], D["latest"]),
     "license": "https://creativecommons.org/licenses/by/4.0/", "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "data.json"}},
    {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": TITLE, "item": URL}]},
]}
LD = json.dumps(ld)
assert "</" not in LD
css = (HERE.parent / "llama-args" / "style.css").read_text(encoding="ascii")
css += "\n.s.p{color:var(--warn)}.pin code{white-space:nowrap}.ex button{font-size:.82rem;padding:3px 9px;margin:0 4px 6px 0;background:transparent;color:var(--acc)}\n#res td:first-child{min-width:9em}\n"
js = (HERE / "tool.js").read_text(encoding="ascii")
assert "</script" not in js
faq_html = "\n".join("<h3>%s</h3>\n<p>%s</p>" % (e(q, quote=False), e(a, quote=False)) for q, a in FAQ)
EX = [("ImportError: cannot import name 'cached_download' from 'huggingface_hub' (/usr/local/lib/python3.10/site-packages/huggingface_hub/__init__.py)", "", "cached_download"),
      ("from huggingface_hub import HfFolder, Repository, hf_hub_url, cached_download", "1.0.0", "old app on 1.0.0"),
      ("cannot import name 'OfflineModeIsEnabled' from 'huggingface_hub.utils'", "0.19.4", "utils, hub too old"),
      ("cannot import name 'DDUFEntry' from 'huggingface_hub'", "0.25.2", "pinned too low"),
      ("ModelFilter", "", "ModelFilter")]
ex_html = "".join('<button type="button" data-ex="%s" data-v="%s">%s</button>' % (e(q), v, e(l)) for q, v, l in EX)
G = "https://github.com/huggingface/huggingface_hub/blob/"

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
<p class="lede"><strong><code>cached_download</code> was removed in huggingface_hub 0.26.0 ({R[i26][1]}); the last release that has it is {last25}. <code>HfFolder</code>, <code>Repository</code> and <code>InferenceApi</code> were removed in 1.0.0 ({R[i10][1]}); the last release that has them is {last0}.</strong> The error means a library written for an older hub is running against a newer one. Fix it by upgrading that library (diffusers 0.29.0 or later and sentence-transformers 2.3.0 or later no longer import <code>cached_download</code>; gradio 5.8.0 or later and datasets 2.16.0 or later no longer import <code>HfFolder</code>), or by pinning the hub below the release that dropped the name: <code>pip install "huggingface_hub&lt;0.26.0"</code> or <code>"huggingface_hub&lt;1.0.0"</code>. For any other name, paste the error below.</p>
<p class="meta">Published {PUB} &middot; Data as of {D["asof"]} &middot; huggingface_hub {R[0][0]} to {D["latest"]}, the first release of each of {N} minor versions &middot; read from the source of each release tag, nothing was installed or run (<a href="#how">how</a>, <a href="#limits">limits</a>)</p>

<div class="card" id="lookup">
<label for="q">The ImportError line, the import statement, or just the names</label>
<textarea id="q" spellcheck="false" placeholder="ImportError: cannot import name 'cached_download' from 'huggingface_hub' (/usr/lib/python3/site-packages/huggingface_hub/__init__.py)"></textarea>
<div class="grid">
<div><label for="v">Your huggingface_hub version (optional; <code>pip show huggingface_hub</code>)</label><input id="v" inputmode="decimal" placeholder="for example 0.36.0"></div>
<div class="row"><button type="button" id="go">Look up</button> <span id="status" role="status"></span></div>
</div>
<p class="ex note">Examples: {ex_html}</p>
<div id="res" aria-live="polite"></div>
<p class="note">Runs in your browser on <a href="data.json">data.json</a> ({Path(data_p).stat().st_size // 1024} KB); nothing you paste is sent anywhere. Covers <code>huggingface_hub</code>, <code>huggingface_hub.utils</code> and <code>huggingface_hub.errors</code>: {n_top} top-level names, {n_now} of them in {D["latest"]}.</p>
</div>

<h2 id="libs">Which huggingface_hub does my diffusers, sentence-transformers, gradio, datasets or peft need?</h2>
<p><strong>Each library version imports a fixed set of hub names at module level, and those names fix the range of hub releases with which all of its files import.</strong> "At least" is the newest first-release among the names it imports; "below" is the first hub release that dropped one of them. The name in parentheses is the one that sets the limit. The range is about imports only: a library's own dependency declaration can be narrower, and pip follows that.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Library</th><th>Versions</th><th>huggingface_hub at least</th><th>huggingface_hub below</th></tr></thead>
<tbody>
{needs_html}
</tbody></table></div>
<p class="note">Read at the first release of each minor version of each library ({n_lib_versions} releases; newest read: {libs_latest}). "0.28.x" means the 0.28 series. An import inside a <code>try</code> block, a function or <code>if TYPE_CHECKING:</code> is not counted, because it does not stop the library from importing. All files of the package are counted, including ones a library loads only on demand (diffusers loads most pipeline files that way), so "at least" can be stricter than what a plain <code>import</code> of the library needs; "below" for <code>cached_download</code> and <code>HfFolder</code> is confirmed by the public error reports linked under Sources.</p>

<h2 id="common">Which release has the names people ask about most?</h2>
<p><strong>The table gives the releases that export each name, the replacement named by the library's own deprecation message, and the libraries that import the name.</strong> "Through" is the last patch release before the name disappeared.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Name</th><th>In {D["latest"]}</th><th>Releases that have it</th></tr></thead>
<tbody>
{common_rows}
</tbody></table></div>

<h2 id="removed">What did each huggingface_hub release remove?</h2>
<p><strong>{n_gone} of the {n_top} top-level names are gone from {D["latest"]}; this is every one of them, by the release that dropped it.</strong> Most are generated inference types that were renamed; the ones that break other libraries are in 0.26.0 and 1.0.0.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Release</th><th>Date (PyPI)</th><th>Names</th><th>Gone from the top level</th></tr></thead>
<tbody>
{chr(10).join(rows_gone)}
</tbody></table></div>
<p class="note"><code>login</code> and <code>logout</code> are listed at 0.10.0 because that release did not export them; they are back from 0.11.0 and are in {D["latest"]}.</p>

<h2 id="read">How do I read the error?</h2>
<ul>
<li><strong>The traceback</strong> names the file that asked for the name, a few lines above the error. If it is inside <code>site-packages/diffusers/</code>, <code>sentence_transformers/</code>, <code>gradio/</code> or another library, that library is older than your hub: upgrade it, or pin the hub.</li>
<li><strong>The path in parentheses</strong> is the copy of huggingface_hub that was imported. Check that it is the version you expect: <code>python -c "import huggingface_hub as h; print(h.__version__, h.__file__)"</code>.</li>
<li><strong>On a Space</strong>, the hub version is whatever the Space's SDK and <code>requirements.txt</code> resolve to at build time, so an app that worked can break on a rebuild. Pin <code>huggingface_hub</code> in <code>requirements.txt</code>, or raise the pins of the libraries that import the old name.</li>
<li><strong>"Did you mean: 'hf_hub_download'?"</strong> at the end is Python's spelling suggestion, not advice from the library; for <code>cached_download</code> it happens to name the real replacement.</li>
</ul>

<h2 id="how">How was this read, and how was it checked?</h2>
<p><strong>From the source of each release tag, with Python's <code>ast</code> module; no release was installed or imported.</strong></p>
<ul>
<li>huggingface_hub up to 0.7.x imports its names eagerly in <code>__init__.py</code>; from 0.8.1 the top level is lazy and serves the names of one table (<code>_SUBMOD_ATTRS</code>), which is read. The module-level <code>__getattr__</code> has no other rule; the build stops if a release adds one.</li>
<li><code>huggingface_hub.utils</code> and <code>huggingface_hub.errors</code>: the names the module binds, plus the lazy table of <code>utils</code> where it has one.</li>
<li>The five libraries: every <code>.py</code> file of the package at the first release of each minor version, looking for <code>from huggingface_hub import ...</code>, <code>from huggingface_hub.utils import ...</code> and <code>from huggingface_hub.errors import ...</code> at module level.</li>
<li>Dates and yanked releases come from PyPI. Where the <code>.0</code> release of a minor version was yanked or never uploaded, the first release pip installs is used.</li>
</ul>
<p>Checks, all by a second reading: (1) every lazy release carries a generated static copy of its table for type checkers; in all {checks["CHK_LAZY"]} lazy releases that have one, the copy and our reading are identical ({checks["CHK_SAME"]} of {checks["CHK_LAZY"]}). (2) For each of the {checks["CHK_RUNS"]} "library imports a removed name" ranges, a plain-text search of the library's files finds the import at both ends of the range and no module-level import in the version after it. (3) {checks["CHK_ANCHORS"]} facts from deprecation messages and release notes hold (for example <code>cached_download</code> carries <code>@_deprecate_method(version="0.26")</code> in 0.25.0 and is gone in 0.26.0).</p>

<h2 id="limits">Limits</h2>
<ul>
<li>Nothing was installed or run. The library ranges say which hub releases let the library's files import; they do not say every feature works across that range.</li>
<li>Only the first release of each minor version was read, for the hub and for the libraries. A change made in a patch release is attributed to the next minor.</li>
<li>A module-level import in a file that the library itself only loads on demand does not break <code>import library</code>, only the feature that loads that file. The lookup names one such file per range in <a href="data.json">data.json</a>.</li>
<li>Submodules of the hub other than <code>utils</code> and <code>errors</code> are not covered (<code>huggingface_hub.constants</code>, <code>huggingface_hub.file_download</code>, <code>huggingface_hub.inference</code> and so on), and libraries other than the five are not read.</li>
<li>"Instead" is given only where the hub's own deprecation message or docstring names a replacement.</li>
</ul>

<h2 id="faq">Questions</h2>
{faq_html}

<h2 id="sources">Sources</h2>
<ul>
<li>huggingface/huggingface_hub, release tags v{R[0][0]} to v{D["latest"]}: <a href="{G}v{D["latest"]}/src/huggingface_hub/__init__.py">src/huggingface_hub/__init__.py</a>, <a href="{G}v{D["latest"]}/src/huggingface_hub/utils/__init__.py">utils/__init__.py</a>, <a href="{G}v{D["latest"]}/src/huggingface_hub/errors.py">errors.py</a>.</li>
<li>Deprecation messages quoted for replacements: <a href="{G}v0.25.0/src/huggingface_hub/file_download.py">file_download.py at 0.25.0</a> (<code>cached_download</code>), <a href="{G}v0.36.0/src/huggingface_hub/inference_api.py">inference_api.py at 0.36.0</a>, <a href="{G}v0.36.0/src/huggingface_hub/repository.py">repository.py at 0.36.0</a>, <a href="{G}v0.36.0/src/huggingface_hub/utils/_hf_folder.py">utils/_hf_folder.py at 0.36.0</a>, <a href="{G}v0.23.0/src/huggingface_hub/utils/endpoint_helpers.py">utils/endpoint_helpers.py at 0.23.0</a> (<code>ModelFilter</code>, <code>DatasetFilter</code>), <a href="{G}v0.36.0/src/huggingface_hub/hf_api.py">hf_api.py at 0.36.0</a> (<code>update_repo_visibility</code>).</li>
<li>Release tags of <a href="https://github.com/huggingface/diffusers">huggingface/diffusers</a>, <a href="https://github.com/UKPLab/sentence-transformers">UKPLab/sentence-transformers</a>, <a href="https://github.com/gradio-app/gradio">gradio-app/gradio</a>, <a href="https://github.com/huggingface/datasets">huggingface/datasets</a> and <a href="https://github.com/huggingface/peft">huggingface/peft</a>; release dates from PyPI.</li>
<li>Reports of the error this page answers: <a href="https://huggingface.co/spaces/ymzhang319/FoleyCrafter/discussions/6">a Space fixed by changing requirements.txt</a>, <a href="https://huggingface.co/spaces/SemanticTypography/Word-As-Image/commit/632c5578ef4a6c86f6fcf16e2ee7ed50af158f40">a Space pinning huggingface_hub==0.25.2</a>, <a href="https://huggingface.co/spaces/facebook/EdgeTAM/discussions/1">HfFolder with Gradio</a>.</li>
</ul>
<p>The same data as JSON: <a href="data.json">data.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
<p class="note">Related: <a href="/en/transformers-import-name-version-lookup/">"cannot import name ... from 'transformers'": the releases that have each name</a> &middot; <a href="/en/peft-trl-args-version-lookup/">"got an unexpected keyword argument": PEFT, TRL and TrainingArguments by version</a> &middot; <a href="/en/model-arch-min-version/">"does not recognize this architecture": the version each model needs</a>.</p>
</main>
<script>window.TF_HINTS = {json.dumps(HINTS)}; window.TF_GROUPS = [];</script>
<script>
{js}</script>
</body>
</html>
"""
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
if (out_dir / "data.json").resolve() != Path(data_p).resolve():
    shutil.copyfile(data_p, out_dir / "data.json")
print("index.html %d bytes | top %d, now %d, gone %d | library versions %d | rows %d + %d" % (len(page), n_top, n_now, n_gone, n_lib_versions, len(COMMON), len(rows_gone)), file=sys.stderr)
