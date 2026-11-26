#!/usr/bin/env python3
"""Build en/llama-cpp-pre-tokenizer-lookup/index.html and pretok.json.
Usage: build_page.py pretok_raw.json bundles.json groups.json dups.json paths.json validate.json OUT_DIR
ASCII only. Every build number, date and version on the page comes from the inputs.
PAGE_MODIFIED (YYYY-MM-DD) sets dateModified; default is the publish date."""
import html, json, os, re, sys
from pathlib import Path

RAW, BUN, GRP, DUP, PTH, VAL, OUT = sys.argv[1:8]
PTHS = json.load(open(PTH))
VALN = json.load(open(VAL))["tags_checked"]
R = json.load(open(RAW))
B = json.load(open(BUN))
G = json.load(open(GRP))
DUPS = json.load(open(DUP))
out = Path(OUT)
out.mkdir(parents=True, exist_ok=True)
PUBLISHED = "2026-11-26"
MODIFIED = os.environ.get("PAGE_MODIFIED") or PUBLISHED
SLUG = "llama-cpp-pre-tokenizer-lookup"
URL = "https://erimaki-kobo.github.io/en/%s/" % SLUG
LC = "https://github.com/ggml-org/llama.cpp"
e = html.escape
HEAD_TAG, HEAD_DATE = R["head_tag"], R["head_tag_date"]
OL_LATEST = B["ollama_latest"]
LCP_LATEST = B["llama_cpp_python_latest"]


def bn(t):
    return int(t[1:])


def ov(tag):
    return tag[1:] if tag and tag.startswith("v") else tag


# ---------- records ----------
hashes = []
for h, x in R["hashes"].items():
    cur = x["spans"][-1]
    rec = {"h": h, "name": x["name"], "ref": x["ref"], "build": cur["added_build"], "date": cur["added_build_date"] or cur["added_date"],
           "commit": cur["added"], "subject": cur["added_subject"], "renames": x.get("renames", []),
           "gaps": [[s["added_build"], s["removed_build"]] for s in x["spans"][:-1]]}
    hashes.append(rec)
names = []
group_of = {}
for gi, members in enumerate(G):
    for m in members:
        group_of[m] = gi
for n, x in R["names"].items():
    cur = x["spans"][-1]
    bu = B["names"].get(n, {})
    names.append({"n": n, "build": cur["added_build"], "date": cur["added_build_date"] or cur["added_date"], "commit": cur["added"], "subject": cur["added_subject"],
                  "ollama": bu.get("ollama"), "lcp": bu.get("llama_cpp_python"),
                  "same": [m for m in G[group_of[n]] if m != n] if n in group_of else [],
                  "gaps": [[s["added_build"], s["removed_build"]] for s in x["spans"][:-1]]})


def sortkey(r):
    return (bn(r["build"]) if r["build"] else 10 ** 9, r["date"], r.get("h") or r.get("n"))


hashes.sort(key=sortkey, reverse=True)
names.sort(key=sortkey, reverse=True)
H_REL = [r for r in hashes if r["build"]]
N_REL = [r for r in names if r["build"]]
H_NEW = [r for r in hashes if not r["build"]]
N_NEW = [r for r in names if not r["build"]]
NBY = {r["n"]: r for r in names}
HBY = {r["h"]: r for r in hashes}
H26 = sum(1 for r in H_REL if r["date"] >= "2026-01-01")
N26 = sum(1 for r in N_REL if r["date"] >= "2026-01-01")
# names written by the converter that the loader does not check (WPM / non-BPE vocab)
HASH_ONLY = sorted({r["name"] for r in hashes} - set(NBY))
FIRST = min(N_REL, key=lambda r: bn(r["build"]))

# worked examples (asserted so the prose stays true)
FORUM = "1444df51289cfa8063b96f0e62b1125440111bc79a52003ea14b6eac7016fd5f"
Q35 = NBY["qwen35"]
F = HBY[FORUM]
assert F["name"] == "qwen35", F
SL = "32d85c31273f8019248f2559fed492d929ea28b17e51d81d3bb36fff23ca72b3"
assert [x[0] for x in DUPS[SL]] == ["stablelm2", "domyn-edge"], DUPS[SL]
DE = NBY["domyn-edge"]
SLN = NBY["stablelm2"]
assert "qwen2" in DE["same"] and "stablelm2" not in DE["same"]
REN_SL = [x for x in HBY[SL]["renames"] if x["to"] == "domyn-edge"][0]
SL_SWITCH = re.match(r"(b\d+)", os.popen("git -C llama.cpp describe --contains --match 'b*' %s" % REN_SL["commit"]).read()).group(1)
G5, G4 = NBY["glm5"], NBY["glm4"]
assert "glm4" in G5["same"]
for k, v in [("Q35", Q35), ("F", F)]:
    assert v["build"], k

# ---------- JSON for the tool and for download ----------
data = {
    "as_of": HEAD_DATE, "llama_cpp_latest_build": HEAD_TAG,
    "ollama_latest": {"version": ov(OL_LATEST["tag"]), "date": OL_LATEST["date"], "bundled_build": OL_LATEST["build"]},
    "llama_cpp_python_latest": {"version": ov(LCP_LATEST["tag"]), "date": LCP_LATEST["date"], "bundled_build": LCP_LATEST["build"]},
    "chkhsh": {r["h"]: {"name": r["name"], "ref": r["ref"], "first_build": r["build"], "date": r["date"], "commit": r["commit"],
                        "absent_in": r["gaps"]} for r in hashes},
    "names": {r["n"]: {"first_build": r["build"], "date": r["date"], "commit": r["commit"],
                       "ollama": r["ollama"] and {"version": ov(r["ollama"]["tag"]), "date": r["ollama"]["date"], "how": r["ollama"]["how"]},
                       "llama_cpp_python": r["lcp"] and {"version": ov(r["lcp"]["tag"]), "date": r["lcp"]["date"], "bundled_build": r["lcp"]["build"]},
                       "same_handling_as": r["same"], "absent_in": r["gaps"]} for r in names},
    "shared_chkhsh": {h: [{"name": n, "ref": u} for n, u in v] for h, v in DUPS.items()},
    "ollama_releases": [{"version": ov(r["tag"]), "date": r["date"], "bundled_build": r["build"], "vendored_source": r["vendored"]} for r in B["ollama_releases"]],
    "llama_cpp_python_releases": [{"version": ov(r["tag"]), "date": r["date"], "bundled_build": r["build"]} for r in B["llama_cpp_python_releases"]],
}
(out / "pretok.json").write_text(json.dumps(data, indent=1, ensure_ascii=True) + "\n")
compact = {"h": {r["h"]: [r["name"], r["ref"] or "", r["build"] or "", r["date"]] for r in hashes},
           "n": {r["n"]: [r["build"] or "", r["date"], r["ollama"] and ov(r["ollama"]["tag"]) or "", r["lcp"] and ov(r["lcp"]["tag"]) or "", r["same"]] for r in names},
           "head": HEAD_TAG, "ol": ov(OL_LATEST["tag"]), "olb": OL_LATEST["build"], "lcp": ov(LCP_LATEST["tag"]), "lcpb": LCP_LATEST["build"],
           "dup": {h: [n for n, _ in v] for h, v in DUPS.items()}, "hashonly": HASH_ONLY}

# ---------- text ----------
TITLE = "llama.cpp pre-tokenizer lookup: chkhsh and unknown type"
H1 = "\"BPE pre-tokenizer was not recognized\" and \"unknown pre-tokenizer type\": which llama.cpp build fixes it"
DESC = ("Paste a chkhsh or a tokenizer.ggml.pre name: the first llama.cpp build, Ollama and llama-cpp-python "
        "release that accept it. From git history; %d hashes." % len(H_REL))
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))


def blink(t):
    return '<a href="%s/releases/tag/%s"><strong>%s</strong></a>' % (LC, t, t) if t else "<em>after %s</em>" % HEAD_TAG


def clink(c):
    return '<a class="note" href="%s/commit/%s">%s</a>' % (LC, c, c[:10])


def rlink(u):
    if not u:
        return ""
    lab = u.replace("https://huggingface.co/", "")
    return '<a href="%s">%s</a>' % (e(u), e(lab))


def olink(o):
    if not o:
        return '<span class="meta">not yet</span>'
    return '<a href="https://github.com/ollama/ollama/releases/tag/%s">%s</a><br><span class="meta">%s</span>' % (o["tag"], ov(o["tag"]), o["date"])


def plink(p):
    if not p:
        return '<span class="meta">not yet</span>'
    return '<a href="https://github.com/abetlen/llama-cpp-python/releases/tag/%s">%s</a><br><span class="meta">%s</span>' % (p["tag"], ov(p["tag"]), p["date"])


hrows = []
for r in hashes:
    extra = ""
    if r["h"] in DUPS:
        extra = '<br><span class="note">also listed for %s; the last entry wins</span>' % ", ".join("<code>%s</code>" % e(n) for n, _ in DUPS[r["h"]] if n != r["name"])
    if r["gaps"]:
        extra += '<br><span class="note">also present %s</span>' % "; ".join("%s to before %s" % (a, b) for a, b in r["gaps"])
    hrows.append('<tr id="h-%s" data-k="%s %s %s"><td><code class="hh">%s</code></td><td><code>%s</code>%s</td><td>%s<br><span class="meta">%s</span></td><td>%s</td></tr>' % (
        r["h"][:16], r["h"], e(r["name"]), e((r["ref"] or "").lower()), r["h"], e(r["name"]), extra, blink(r["build"]), r["date"], rlink(r["ref"])))
nrows = []
for r in names:
    same = ", ".join("<code>%s</code>" % e(m) for m in r["same"]) or '<span class="meta">-</span>'
    note = ""
    if r["gaps"]:
        note = '<br><span class="note">also %s</span>' % "; ".join("%s to before %s (reverted)" % (a, b) for a, b in r["gaps"])
    nrows.append('<tr id="n-%s" data-k="%s"><td><code>%s</code></td><td>%s<br><span class="meta">%s</span>%s</td><td>%s<br>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
        re.sub(r"[^a-z0-9]+", "-", r["n"].lower()), e(r["n"]), e(r["n"]), blink(r["build"]), r["date"], note, e(r["subject"]), clink(r["commit"]),
        olink(r["ollama"]), plink(r["lcp"]), same))

# Ollama releases that changed the bundled build (for the bundle table)
seen, orows = None, []
for r in B["ollama_releases"]:
    if r["build"] and r["build"] != seen:
        orows.append((r["tag"], r["date"], r["build"]))
        seen = r["build"]
seen, prows = None, []
for r in B["llama_cpp_python_releases"]:
    if r["build"] and r["build"] != seen:
        prows.append((r["tag"], r["date"], r["build"]))
        seen = r["build"]

faq = [
    ("What does \"BPE pre-tokenizer was not recognized - update get_vocab_base_pre()\" mean?",
     "The converter encodes a fixed test string with your tokenizer, hashes the token ids (the chkhsh) and looks the hash up in a list. "
     "Your hash is not in the list of the convert_hf_to_gguf.py you ran. If the hash is in the table on this page, a newer llama.cpp checkout knows it; "
     "if it is not, your tokenizer differs from every tokenizer llama.cpp has registered."),
    ("What does \"unknown pre-tokenizer type\" mean when loading a GGUF?",
     "The file's tokenizer.ggml.pre value is a name your llama.cpp build does not accept. Use a build at or above the one listed for that name, "
     "or the Ollama or llama-cpp-python release listed next to it."),
    ("I fine-tuned a model and now the chkhsh is unknown. Why?",
     "The hash covers the whole tokenizer behaviour, so added tokens, a changed normalizer or pre-tokenizer, or a tokenizer.json saved by a different transformers version can change it. "
     "Convert with the base model's tokenizer files if you did not mean to change the tokenizer."),
    ("Can I rename tokenizer.ggml.pre instead of upgrading?",
     "Only to a name that the current loader handles identically, listed in the \"same handling as\" column, and only if your build knows that name. "
     "gguf_new_metadata.py --pre-tokenizer writes a copy of the file with the new value. Check the tokenization afterwards."),
    ("What does \"missing pre-tokenizer type, using: 'default'\" mean?",
     "The GGUF has a BPE vocabulary but no tokenizer.ggml.pre, usually because it was converted before %s (PR #6920). llama.cpp falls back to a generic split and warns that quality will be degraded. Re-convert or download a newer conversion." % FIRST["build"]),
]
faq_html = "\n".join("<dt>%s</dt><dd>%s</dd>" % (e(q), e(a)) for q, a in faq)

ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1, "description": DESC, "url": URL,
     "datePublished": PUBLISHED, "dateModified": MODIFIED, "inLanguage": "en",
     "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"},
     "about": ["GGUF", "llama.cpp", "tokenizer", "Ollama", "llama-cpp-python"], "isBasedOn": URL + "pretok.json"},
    {"@type": "WebApplication", "@id": URL + "#tool", "name": "llama.cpp chkhsh and pre-tokenizer name lookup", "url": URL + "#lookup",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (runs in the browser)", "isAccessibleForFree": True,
     "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
     "description": "Paste a convert_hf_to_gguf.py warning, a chkhsh or a tokenizer.ggml.pre name; get the first llama.cpp build, Ollama and llama-cpp-python release that accept it."},
    {"@type": "Dataset", "@id": URL + "#data", "name": "llama.cpp BPE pre-tokenizer hashes and names with first release",
     "description": "Every chkhsh in llama.cpp's converter and every tokenizer.ggml.pre name its loader accepts, as of %s, with the first release tag, plus the first Ollama and llama-cpp-python release that bundles each name." % HEAD_TAG,
     "url": URL + "pretok.json", "license": "https://creativecommons.org/licenses/by/4.0/", "isAccessibleForFree": True,
     "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "distribution": {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "pretok.json"}},
    {"@type": "FAQPage", "@id": URL + "#faq", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": "llama.cpp pre-tokenizer lookup", "item": URL}]}]}

CSS = open(Path(__file__).with_name("style.css")).read().strip()
JS = open(Path(__file__).with_name("tool.js")).read().strip()

ex_hash = FORUM
doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(TITLE)}</title>
<meta name="description" content="{e(DESC)}">
<link rel="canonical" href="{URL}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(TITLE)}">
<meta property="og:description" content="{e(DESC)}">
<meta property="og:url" content="{URL}">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=True)}</script>
<style>{CSS}</style>
</head>
<body>
<main>
<p class="meta"><a href="/en/">Answers for LLM inference engineers</a></p>
<h1>{e(H1)}</h1>
<p class="lede"><strong>Both errors usually mean your llama.cpp is older than the commit that added your tokenizer. When converting, look up the <code>chkhsh</code> printed above the error; when loading, look up the <code>tokenizer.ggml.pre</code> name in the error. Use a build at or above the one in the table.</strong> For example, the chkhsh <code>{FORUM[:12]}...</code> that a fine-tuned Qwen3.5-4B printed is recognized from {F["build"]} ({F["date"]}), and a GGUF with <code>qwen35</code> loads from {Q35["build"]} ({Q35["date"]}), Ollama {ov(Q35["ollama"]["tag"])} and llama-cpp-python {ov(Q35["lcp"]["tag"])}. llama.cpp {HEAD_TAG} knows {len(H_REL)} hashes and {len(N_REL)} names; {N26} of the names were added in 2026.</p>
<p class="meta">Published {PUBLISHED} &middot; Data as of {HEAD_DATE} &middot; llama.cpp up to {HEAD_TAG} &middot; Ollama up to {ov(OL_LATEST["tag"])} &middot; llama-cpp-python up to {ov(LCP_LATEST["tag"])} &middot; read from git history &middot; dates are UTC</p>

<h2 id="lookup">Which build fixes my error?</h2>
<p>Paste the warning block from <code>convert_hf_to_gguf.py</code>, the load error, a 64-character chkhsh or a pre-tokenizer name. The version fields are optional; fill one in to get a yes or no for your install.</p>
<div class="card">
<label for="q">Error, chkhsh or tokenizer.ggml.pre name</label>
<textarea id="q" placeholder="** chkhsh:  {ex_hash}" spellcheck="false"></textarea>
<div class="grid">
<div><label for="b">Your llama.cpp build (optional)</label><input id="b" placeholder="b8500" autocomplete="off"></div>
<div><label for="o">Your Ollama version (optional)</label><input id="o" placeholder="0.24.0" autocomplete="off"></div>
<div><label for="p">Your llama-cpp-python version (optional)</label><input id="p" placeholder="0.3.16" autocomplete="off"></div>
</div>
<div class="row"><button id="go" type="button">Look up</button><span id="status" role="status"></span></div>
<div id="res" aria-live="polite"></div>
</div>
<p class="note">Runs in your browser on the tables below; nothing is sent anywhere. Build number: <code>llama-server --version</code>. The name inside a file: <code>gguf-dump --no-tensors model.gguf | grep tokenizer.ggml.pre</code> (<code>pip install gguf</code>).</p>

<h2 id="two-errors">Two errors, one list each</h2>
<div class="tw"><table>
<thead><tr><th>When</th><th>What you see</th><th>What it checks</th><th>Look up</th></tr></thead>
<tbody>
<tr><td>Converting (<code>convert_hf_to_gguf.py</code>)</td><td><code>WARNING: The BPE pre-tokenizer was not recognized!</code> &hellip; <code>chkhsh: &lt;64 hex&gt;</code>, then <code>NotImplementedError: BPE pre-tokenizer was not recognized - update get_vocab_base_pre()</code></td><td>The converter encodes a fixed test string with your Hugging Face tokenizer and hashes the token ids. The hash must be in <code>get_vocab_base_pre()</code>; the match decides the name it writes to <code>tokenizer.ggml.pre</code>.</td><td><a href="#hashes">chkhsh table</a></td></tr>
<tr><td>Loading (llama.cpp, Ollama, LM Studio, llama-cpp-python...)</td><td><code>error loading model vocabulary: unknown pre-tokenizer type: 'qwen35'</code></td><td>The loader compares <code>tokenizer.ggml.pre</code> with the names it knows and picks the split rules for that name.</td><td><a href="#names">name table</a></td></tr>
<tr><td>Loading an old file</td><td><code>missing pre-tokenizer type, using: 'default'</code> &hellip; <code>GENERATION QUALITY WILL BE DEGRADED!</code></td><td>A BPE vocabulary without <code>tokenizer.ggml.pre</code>: converted before {FIRST["build"]} ({FIRST["date"]}, PR #6920), when the key was introduced.</td><td>Re-convert, or download a newer conversion</td></tr>
</tbody></table></div>
<p>Only BPE vocabularies have a pre-tokenizer. SentencePiece (<code>llama</code>) and WordPiece (<code>bert</code>) files never show these errors. Names written by the converter but not checked by the loader, because those models use WordPiece: {", ".join("<code>%s</code>" % n for n in HASH_ONLY)}. A few model classes skip the hash and write a fixed name (for example <code>whitespace</code>, <code>tekken-num3</code>, <code>zonos3</code>); they never raise the converter error but can still raise the load error.</p>

<h2 id="hashes">Which llama.cpp build recognizes each chkhsh?</h2>
<p><strong>Each row is one hash in <code>get_vocab_base_pre()</code>, with the name it writes and the first release tag whose converter contains it.</strong> Newest first; {len(hashes)} rows. The model column is the <code># ref:</code> comment in the source, the tokenizer the hash was taken from. The list lives in <code>conversion/base.py</code> from {PTHS["conversion/base.py"]}, in <code>convert_hf_to_gguf.py</code> from {PTHS["convert_hf_to_gguf.py"]}, and in <code>convert-hf-to-gguf.py</code> before that.</p>
<p><label for="fh">Filter the hashes</label><input id="fh" placeholder="qwen" autocomplete="off"></p>
<div class="tw wide"><table id="ht">
<thead><tr><th>chkhsh</th><th>Writes tokenizer.ggml.pre</th><th>Converter from</th><th>Tokenizer it was taken from</th></tr></thead>
<tbody>
{chr(10).join(hrows)}
</tbody></table></div>

<h2 id="names">Which llama.cpp, Ollama and llama-cpp-python release loads each tokenizer.ggml.pre name?</h2>
<p><strong>Each row is one name the loader accepts, with the first llama.cpp release tag that has it and the first Ollama and llama-cpp-python release whose bundled llama.cpp has it.</strong> Any later release also has it. Newest first; {len(names)} rows. "Same handling as" lists the names the current loader treats identically (same split rules and flags).</p>
<p><label for="fn">Filter the names</label><input id="fn" placeholder="glm" autocomplete="off"></p>
<div class="tw wide"><table id="nt">
<thead><tr><th>tokenizer.ggml.pre</th><th>llama.cpp from</th><th>Commit that added it</th><th>Ollama from</th><th>llama-cpp-python from</th><th>Same handling as</th></tr></thead>
<tbody>
{chr(10).join(nrows)}
</tbody></table></div>

<h2 id="not-listed">My chkhsh is not in the table. What now?</h2>
<p><strong>Then no llama.cpp version recognizes your tokenizer yet, and upgrading does not help.</strong> The hash changes whenever the token ids for the test string change. Common causes:</p>
<ul>
<li><strong>You changed the tokenizer while fine-tuning</strong>: added tokens, a different normalizer or pre-tokenizer, or a <code>tokenizer.json</code> re-saved by another transformers version. If you did not mean to, copy the base model's <code>tokenizer.json</code>, <code>tokenizer_config.json</code> and <code>special_tokens_map.json</code> into the folder and convert again.</li>
<li><strong>The model family is new</strong> and llama.cpp has no entry yet. Wait for the model support PR, or add the model to <code>convert_hf_to_gguf_update.py</code> and regenerate, which is what that PR does.</li>
<li><strong>Your tokenizer is a known one with a small difference.</strong> If you are sure the split rules are the same as a listed model's, you can add your hash to your local copy of <code>get_vocab_base_pre()</code> with that model's name. A wrong choice gives a file that loads and tokenizes slightly differently from Transformers, so compare token ids on a few strings afterwards.</li>
</ul>
<p>The tool above answers in the same way: a hash that is not listed gets "not recognized by any build up to {HEAD_TAG}".</p>

<h2 id="rename">Can I rename the pre-tokenizer instead of upgrading?</h2>
<p><strong>Sometimes. The current loader treats some names identically, so a file tagged with a new name can be re-tagged with an older name that your runtime already knows.</strong> For example, <code>glm5</code> ({G5["build"]}) has the same handling as <code>glm4</code> ({G4["build"]}):</p>
<pre><code>pip install gguf
gguf-new-metadata --pre-tokenizer glm4 model.gguf model-glm4pre.gguf</code></pre>
<p>Three conditions: the target name must be in the "same handling as" column; your build must know the target name; and your build must also know the model architecture, which is often the real blocker (see <a href="/en/gguf-arch-min-build-lookup/">the architecture lookup</a>). "Same handling" is read from the current source; an older build may have had different rules for the same name. Compare the token ids with Transformers on a few strings after re-tagging.</p>

<h2 id="shared">Two names for one hash: the last entry wins</h2>
<p><strong>A few tokenizers give the same chkhsh as another model. <code>get_vocab_base_pre()</code> is a list of plain <code>if</code> statements, so the last matching entry decides the name.</strong> At {HEAD_TAG}:</p>
<ul>
{chr(10).join("<li><code>%s...</code>: %s; the converter writes <code>%s</code></li>" % (h[:12], ", then ".join("<code>%s</code> (%s)" % (e(n), rlink(u)) for n, u in v), e(v[-1][0])) for h, v in DUPS.items())}
</ul>
<p>The newest case matters for StableLM 2: since {SL_SWITCH} ({REN_SL["date"]}), converting a StableLM 2 checkpoint writes <code>domyn-edge</code> instead of <code>stablelm2</code>. Runtimes older than {DE["build"]} then refuse the file with <code>unknown pre-tokenizer type: 'domyn-edge'</code>; Ollama has the name from {ov(DE["ollama"]["tag"])} and llama-cpp-python from {ov(DE["lcp"]["tag"])}. The split rules are the same, but <code>domyn-edge</code> is handled like <code>qwen2</code> (spaces are not cleaned up when decoding), not like <code>stablelm2</code>. To keep the old behaviour: <code>gguf-new-metadata --pre-tokenizer stablelm2 in.gguf out.gguf</code>. This is read from the source; we did not convert a StableLM 2 model.</p>

<h2 id="bundled">Which llama.cpp build is inside Ollama and llama-cpp-python?</h2>
<p><strong>Both ship a fixed llama.cpp, so the name must be in that build.</strong> The latest Ollama, {ov(OL_LATEST["tag"])}, bundles {OL_LATEST["build"]}; the latest llama-cpp-python, {ov(LCP_LATEST["tag"])}, bundles {LCP_LATEST["build"]}. Below: every release where the bundled build changed, newest first.</p>
<details><summary>Ollama ({len(orows)} changes)</summary>
<div class="tw"><table><thead><tr><th>Ollama</th><th>Date</th><th>Bundled llama.cpp</th></tr></thead><tbody>
{chr(10).join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (ov(t), d, b) for t, d, b in reversed(orows))}
</tbody></table></div></details>
<details><summary>llama-cpp-python ({len(prows)} changes)</summary>
<div class="tw"><table><thead><tr><th>llama-cpp-python</th><th>Date</th><th>Bundled llama.cpp</th></tr></thead><tbody>
{chr(10).join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (ov(t), d, b) for t, d, b in reversed(prows))}
</tbody></table></div></details>
<p class="note">Ollama: the build named by <code>LLAMA_CPP_VERSION</code>, <code>Makefile.sync</code> or the submodule, or the vendored source itself where Ollama kept a patched copy in the repository. Some Ollama releases from 2025 to 2026 ran certain models on Ollama's own Go engine, which does its own tokenization; for those models this table does not apply. LM Studio, Jan and KoboldCpp also embed llama.cpp; compare the llama.cpp version their release notes give with the table.</p>

<h2 id="method">How was this built?</h2>
<p>From the llama.cpp repository: every first-parent commit since 2024-04 that touched the converter (<code>convert-hf-to-gguf.py</code>, <code>convert_hf_to_gguf.py</code>, <code>conversion/base.py</code>) or the loader's name list (<code>llama.cpp</code>, <code>src/llama.cpp</code>, <code>src/llama-model.cpp</code>, <code>src/llama-vocab.cpp</code>), {R["commits_walked"]} commits. For each commit we parsed the full list of hashes (including <code>if chkhsh == A or chkhsh == B</code>) and names, so a hash that was added, removed and added again is dated from its last addition. The first release is the first <code>bNNNN</code> tag that contains the commit (<code>git describe --contains</code>). As a check, the lists implied by the history were compared with the source of {VALN} sampled release tags; all matched. Ollama and llama-cpp-python: the llama.cpp commit each release pins, tested with <code>git merge-base --is-ancestor</code> against the commit that added the name. Download: <a href="pretok.json">pretok.json</a>.</p>

<h2 id="limits">What this page does not cover</h2>
<ul>
<li>Whether tokenization matches Transformers token for token. A recognized name only means llama.cpp picked a split rule; bugs in that rule are separate issues.</li>
<li>Models whose GGUF vocabulary is not BPE.</li>
<li>Forks and apps with their own patches, beyond Ollama's vendored copies.</li>
<li>Commits after {HEAD_TAG}: {", ".join("<code>%s</code>" % e(r["n"]) for r in N_NEW) or "none"} {"is" if len(N_NEW) == 1 else "are"} on master but in no release yet.</li>
</ul>

<h2 id="faq">Questions</h2>
<dl>
{faq_html}
</dl>

<h2 id="related">Related</h2>
<ul>
<li><a href="/en/gguf-arch-min-build-lookup/">"unknown model architecture": which llama.cpp build and Ollama version a GGUF needs</a></li>
<li><a href="/en/generation-stop-tokens-check/">Model does not stop generating: which token each engine stops on</a></li>
<li><a href="/en/llama-cpp-removed-args-lookup/">llama-server and llama-cli arguments removed by build</a></li>
</ul>

<h2 id="sources">Sources</h2>
<ul>
<li>llama.cpp: <a href="{LC}/blob/master/conversion/base.py">conversion/base.py</a> (<code>get_vocab_base_pre</code>), <a href="{LC}/blob/master/convert_hf_to_gguf_update.py">convert_hf_to_gguf_update.py</a>, <a href="{LC}/blob/master/src/llama-vocab.cpp">src/llama-vocab.cpp</a>, <a href="{LC}/blob/master/gguf-py/gguf/scripts/gguf_new_metadata.py">gguf_new_metadata.py</a>, <a href="{LC}/pull/6920">PR #6920</a>, <a href="{LC}/releases">releases</a></li>
<li>Ollama: <a href="https://github.com/ollama/ollama/blob/main/LLAMA_CPP_VERSION">LLAMA_CPP_VERSION</a>, <a href="https://github.com/ollama/ollama/releases">releases</a></li>
<li>llama-cpp-python: <a href="https://github.com/abetlen/llama-cpp-python/tree/main/vendor">vendor/llama.cpp</a>, <a href="https://github.com/abetlen/llama-cpp-python/releases">releases</a></li>
<li>Reports of the errors: <a href="https://discuss.huggingface.co/t/the-bpe-pre-tokenizer-was-not-recognized/175714">Hugging Face forum, fine-tuned Qwen3.5-4B</a>, <a href="https://github.com/ollama/ollama/issues/4529">Ollama #4529 (qwen2)</a>, <a href="https://huggingface.co/bartowski/aya-23-8B-GGUF/discussions/1">aya-23 GGUF (command-r)</a>, <a href="https://huggingface.co/unsloth/grok-2-GGUF/discussions/5">grok-2 GGUF</a>, <a href="https://huggingface.co/mradermacher/model_requests/discussions/2467">mradermacher model_requests #2467</a></li>
</ul>
</main>
<script>
const D={json.dumps(compact, ensure_ascii=True, separators=(",", ":"))};
{JS}
</script>
</body>
</html>
"""
doc.encode("ascii")
(out / "index.html").write_text(doc)
print("wrote", out / "index.html", len(doc), "bytes; hashes", len(hashes), "names", len(names), "ollama rows", len(orows), "lcp rows", len(prows))
