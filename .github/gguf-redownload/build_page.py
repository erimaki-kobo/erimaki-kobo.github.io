#!/usr/bin/env python3
"""Build en/gguf-redownload-check/index.html from survey.json (measured in a browser with survey.js).
Usage: build_page.py survey.json OUT_DIR. ASCII only; every count in the prose comes from survey.json."""
import html, json, os, sys
from pathlib import Path

SV, OUT = sys.argv[1:3]
S = json.load(open(SV))
out = Path(OUT); out.mkdir(parents=True, exist_ok=True)
HERE = Path(__file__).parent
PUBLISHED = "2026-11-26"
MODIFIED = os.environ.get("PAGE_MODIFIED") or PUBLISHED
SLUG = "gguf-redownload-check"
URL = "https://erimaki-kobo.github.io/en/%s/" % SLUG
e = html.escape
HF = "https://huggingface.co"

recs = S["repos"]
top = [r for r in recs if r["top"]]
steps = [s for r in recs for s in r["steps"]]
K = {k: sum(1 for s in steps if s["kind"] == k) for k in ("metadata", "weights", "tensors", "none")}
TPL = sum(1 for s in steps if "tokenizer.chat_template" in s["keys"])
TPL_ONLY = sum(1 for s in steps if s["kind"] == "metadata" and s["keys"] == ["tokenizer.chat_template"])
N_TOP = S["top_checked"]
TOP_REPL = sum(1 for r in top if r["steps"])
TOP_SINGLE = N_TOP - TOP_REPL
assert len(steps) == sum(K.values())

# worked example
EX = next(r for r in recs if r["id"] == "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF")
EX["versions"] = [None] * EX["n"]
assert [s["kind"] for s in EX["steps"]][:4] == ["metadata", "tensors", "weights", "weights"], [s["kind"] for s in EX["steps"]]

LABEL = {"metadata": '<span class="s y">metadata only</span>', "weights": '<span class="s n">weights changed</span>',
         "tensors": '<span class="s n">tensors changed</span>', "none": '<span class="s">no visible change</span>'}


def short(k):
    return k.replace("tokenizer.ggml.", "").replace("tokenizer.", "").replace("general.", "")


def stepcell(s):
    keys = [short(k) for k in s["keys"] if not k.startswith("general.") and not k.startswith("quantize.")]
    extra = []
    if s["kind"] == "tensors":
        a, rm, ty, sh = s["t"][:4]
        if a: extra.append("%d added" % a)
        if rm: extra.append("%d removed" % rm)
        if ty: extra.append("%d re-typed" % ty)
        if sh: extra.append("%d reshaped" % sh)
    if s["kind"] == "weights":
        extra.append("%d of %d sampled tensors differ" % (s["n"] - s["same"], s["n"]))
    if s.get("pre"):
        keys = [k if k != "pre" else "pre " + s["pre"].replace(">", " to ") for k in keys]
    g = [k for k in s["keys"] if k.startswith("general.") or k.startswith("quantize.")]
    if g and not keys:
        keys = ["general/quantize keys only"]
    txt = ", ".join(keys[:4]) + (" ..." if len(keys) > 4 else "")
    if extra:
        txt = (txt + "; " if txt else "") + ", ".join(extra)
    return "%s %s <span class=\"meta\">%s</span>" % (s["date"], LABEL[s["kind"]], e(txt))


rows = []
for r in sorted(recs, key=lambda r: (-len(r["steps"]), r["id"])):
    if not r["steps"]:
        continue
    link = '<a href="%s/%s">%s</a>' % (HF, r["id"], e(r["id"]))
    try_ = '<a href="?repo=%s&amp;file=%s">check</a>' % (e(r["id"]), e(r["file"]))
    rows.append("<tr><td>%s<br><code class=\"fn\">%s</code><br>%s</td><td>%d</td><td><ul class=\"st\">%s</ul></td></tr>" % (
        link, e(r["file"]), try_, r["n"], "".join("<li>%s</li>" % stepcell(s) for s in r["steps"])))
singles = sorted(S["single"])
old_single = sorted(S["nosteps"])
EXTRA_N = len([r for r in recs if not r["top"]]) + len(old_single)

TITLE = "Do I need to redownload this GGUF? Version check"
H1 = "Do I need to redownload my GGUF? Check which upload you have and what changed"
DESC = ("Paste a Hugging Face repo and your file's sha256 (or pick the file): see which upload you have and whether "
        "later re-uploads changed weights or only metadata.")
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))

faq = [
    ("Why do GGUF files on Hugging Face get re-uploaded?",
     "Most often to fix the chat template or tokenizer settings after a llama.cpp fix, and sometimes to re-quantize with a new importance matrix or after a conversion bug. "
     "In the %d re-uploads we checked, %d changed only metadata, %d changed tensor data with the same layout and %d changed the tensors themselves." % (len(steps), K["metadata"], K["weights"], K["tensors"])),
    ("How do I find the sha256 of my GGUF?",
     "Hugging Face cache: the file name under blobs/ is the sha256. Ollama: ollama show --modelfile prints FROM .../blobs/sha256-<hash>. Any other copy: sha256sum model.gguf. "
     "Or pick the file in the tool, which compares its header without hashing it."),
    ("Can I fix a chat template without downloading the GGUF again?",
     "Yes, when only metadata changed. gguf-new-metadata (pip install gguf) writes a copy with a new chat template, pre-tokenizer, special token ids, name or description; gguf-set-metadata changes a number or a boolean in place."),
    ("Does Ollama update a model pulled from hf.co automatically?",
     "No. ollama pull hf.co/<repo>:<quant> again fetches the current file; until then Ollama keeps the blob it downloaded."),
    ("Why does gguf-set-metadata set my boolean to True when I type false?",
     "It converts the text with numpy's bool, and any non-empty string is True. Pass an empty string ('') to set False. Checked with gguf 0.19.0."),
]
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1, "description": DESC, "url": URL, "datePublished": PUBLISHED, "dateModified": MODIFIED,
     "inLanguage": "en", "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"}, "about": ["GGUF", "Hugging Face Hub", "llama.cpp", "Ollama"]},
    {"@type": "WebApplication", "@id": URL + "#tool", "name": "GGUF redownload check", "url": URL + "#check", "applicationCategory": "DeveloperApplication",
     "operatingSystem": "Any (runs in the browser)", "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
     "description": "Lists every upload of a GGUF file on the Hugging Face Hub, finds yours by sha256 or by its header, and tells whether the newer uploads changed weights or only metadata, with the gguf-new-metadata command to patch metadata-only changes."},
    {"@type": "FAQPage", "@id": URL + "#faq", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": "GGUF redownload check", "item": URL}]}]}

CSS = (HERE / "style.css").read_text().strip()
JS = (HERE / "ggufhist.js").read_text().strip() + "\n" + (HERE / "ui.js").read_text().strip()
ex = EX["steps"]
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
<p class="lede"><strong>Redownload only if the tensors changed. If a re-upload changed only metadata (usually the chat template), patch your copy with <code>gguf-new-metadata</code> instead.</strong> The check below lists every upload of a file on the Hugging Face Hub, finds yours by sha256 or by reading its header, and compares the two files directly: metadata keys, tensor names, types and shapes, and sampled tensor bytes. In the {len(steps)} re-uploads we checked across {len(recs)} popular repositories, {K["metadata"]} changed only metadata ({TPL_ONLY} of them only the chat template), {K["weights"]} re-quantized the same tensors, {K["tensors"]} added, removed or re-typed tensors, and in {K["none"]} we found no difference in the metadata or the sampled bytes.</p>
<p class="meta">Published {PUBLISHED} &middot; Survey run {S["run_date"]} (UTC) &middot; runs in your browser against the public Hugging Face API</p>

<h2 id="check">Which upload do I have, and what changed since?</h2>
<div class="card">
<label for="repo">Hugging Face repository or file URL</label>
<div class="row"><input id="repo" placeholder="bartowski/Meta-Llama-3.1-8B-Instruct-GGUF" autocomplete="off" spellcheck="false"><button id="load" type="button">Load files</button></div>
<div id="step2" hidden>
<label for="files">File</label><select id="files"></select>
<p class="note">Then give one of these (the first one you fill in is used):</p>
<div class="grid">
<div><label for="sha">sha256 of your file</label><input id="sha" placeholder="431354b8f6066accf13219106f1956ecf9a212089dea1fd18b416454f28ba421" autocomplete="off" spellcheck="false"></div>
<div><label for="local">or your file (only its header is read)</label><input id="local" type="file" accept=".gguf"></div>
<div><label for="olltag">or the Ollama tag you pulled</label><input id="olltag" placeholder="Q4_K_M" autocomplete="off"></div>
</div>
<div class="row"><button id="go" type="button">Check</button></div>
</div>
<p id="status" role="status" class="note"></p>
<div id="res" aria-live="polite"></div>
<div id="vlist"></div>
</div>
<p class="note">Your file never leaves your computer: the browser reads the first megabytes of it locally. The page talks only to huggingface.co (public repositories; gated ones need a login this page does not have). Reading a header downloads 1 to 20 MB per version, because the vocabulary is stored there.</p>

<h2 id="sha256">Where do I find the sha256 of my GGUF?</h2>
<div class="tw"><table>
<thead><tr><th>Where your copy came from</th><th>How to get the sha256</th></tr></thead>
<tbody>
<tr><td><code>huggingface-cli download</code>, <code>hf_hub_download</code>, <code>llama-cpp-python</code> <code>from_pretrained</code></td><td>The cache keeps each file under <code>~/.cache/huggingface/hub/models--ORG--REPO/blobs/</code> named by its sha256; <code>snapshots/&lt;commit&gt;/</code> links to it. <code>ls -l ~/.cache/huggingface/hub/models--*/snapshots/*/*.gguf</code> shows which blob each file points to.</td></tr>
<tr><td>Ollama (<code>ollama pull hf.co/REPO:QUANT</code>)</td><td><code>ollama show --modelfile hf.co/REPO:QUANT</code> prints <code>FROM .../blobs/sha256-&lt;hash&gt;</code>. The Hugging Face registry serves the GGUF file as that blob, so the hash is the file's sha256 (we checked: the registry's model layer for bartowski/Meta-Llama-3.1-8B-Instruct-GGUF:Q4_K_M has the sha256 of the newest <code>Q4_K_M.gguf</code>). Or type the tag in the tool to see what a new pull would get.</td></tr>
<tr><td>LM Studio, a browser download, anything else</td><td><code>sha256sum model.gguf</code> (macOS: <code>shasum -a 256</code>, Windows: <code>certutil -hashfile model.gguf SHA256</code>), or pick the file in the tool: it matches the header and the size without hashing gigabytes.</td></tr>
</tbody></table></div>

<h2 id="survey">What did re-uploads change in popular GGUF repositories?</h2>
<p><strong>Of the {N_TOP} most downloaded GGUF repositories on the Hub ({S["run_date"]}), {TOP_REPL} had replaced the file we checked at least once; {TOP_SINGLE} never had.</strong> We added {EXTRA_N} older, widely used repositories, of which {len(old_single)} had never replaced the file. For each, we took one file (Q4_K_M where there is one), read every upload's header, and compared each upload with the one before. "Metadata only" means the same tensor names, types and shapes and identical first 4 KiB in all 16 sampled tensors.</p>
<div class="tw wide"><table id="sv">
<thead><tr><th>Repository and file</th><th>Uploads</th><th>Each re-upload, newest first</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table></div>
<p class="note">At most the 10 most recent uploads of each file were read. Never replaced: {", ".join("<code>%s</code>" % e(x) for x in singles + old_single)}.</p>

<h2 id="example">Example: Llama 3.1 8B Instruct Q4_K_M, uploaded {len(EX["versions"])} times</h2>
<p>bartowski's Q4_K_M file was uploaded {len(EX["versions"])} times in July 2024. Comparing each upload with the previous one:</p>
<ol reversed>
<li>{ex[0]["date"]}: only the chat template changed; the sampled tensor bytes are identical. A file from the previous upload can be patched with <code>gguf-new-metadata --chat-template-file</code>. This matches the answer in <a href="{HF}/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/discussions/6">discussion #6</a>, "Why were the quants updated 3 hours ago?".</li>
<li>{ex[1]["date"]}: a tensor was added ({e(", ".join(ex[1]["added"]))}) and the template changed. Redownload.</li>
<li>{ex[2]["date"]}: the pre-tokenizer changed ({e((ex[2].get("pre") or "").replace(">", " to "))}) and the tensor bytes differ. Redownload.</li>
<li>{ex[3]["date"]}: importance-matrix keys were added and the tensor bytes differ: re-quantized with an importance matrix. Redownload.</li>
</ol>

<h2 id="patch">How do I patch a metadata-only change?</h2>
<p><strong>When the tool says "metadata only", it prints the command.</strong> The tools come with <code>pip install gguf</code>:</p>
<div class="tw"><table>
<thead><tr><th>Changed key</th><th>Command</th></tr></thead>
<tbody>
<tr><td><code>tokenizer.chat_template</code></td><td><code>gguf-new-metadata old.gguf fixed.gguf --chat-template-file chat_template.jinja</code> (the tool can download the new template)</td></tr>
<tr><td><code>tokenizer.ggml.pre</code></td><td><code>--pre-tokenizer NAME</code> (see the <a href="/en/llama-cpp-pre-tokenizer-lookup/">pre-tokenizer lookup</a>)</td></tr>
<tr><td><code>tokenizer.ggml.bos_token_id</code>, <code>eos_token_id</code>, ...</td><td><code>--special-token-by-id eos 106</code></td></tr>
<tr><td><code>general.name</code>, <code>general.description</code></td><td><code>--general-name</code>, <code>--general-description</code></td></tr>
<tr><td>a key that was removed</td><td><code>--remove-metadata KEY</code></td></tr>
<tr><td>a number or a boolean, e.g. <code>tokenizer.ggml.add_bos_token</code></td><td><code>gguf-set-metadata fixed.gguf KEY VALUE</code> (in place). <strong>For False pass an empty string, <code>''</code></strong>: the text <code>false</code> becomes True, because the value goes through numpy's bool. We hit this with gguf 0.19.0.</td></tr>
</tbody></table></div>
<p>Other changed keys (a new array, a new architecture parameter) cannot be set with these tools; redownload, or keep your file if the key does not matter to you. A patched file has the same metadata as the new upload but a different sha256, because the keys are written in another order; pick it in the tool to confirm that nothing else differs. We tested the round trip on small generated GGUF files: after patching, the header comparison showed no difference.</p>

<h2 id="how">How does the check work?</h2>
<ul>
<li><strong>History</strong>: <code>POST /api/models/REPO/paths-info/REV</code> gives the file's sha256 and the last commit that changed it; asking again at that commit's parent gives the upload before, and so on. One request per upload.</li>
<li><strong>Headers</strong>: HTTP range requests on <code>/resolve/COMMIT/FILE</code>, parsed in the page (GGUF versions 2 and 3): every metadata key, and every tensor's name, type, shape and offset. Arrays such as the vocabulary are compared by a hash of their bytes.</li>
<li><strong>Tensor bytes</strong>: when the tensors have the same names, types and shapes, the first 4 KiB of 16 tensors (always the first and the last) are compared, each at its own offset. This catches re-quantization, but it is a sample: a change outside the sampled bytes shows as "no visible change".</li>
<li><strong>Your file</strong>: a sha256 is matched against the uploads' sha256; a picked file is matched by its header bytes and its size.</li>
</ul>

<h2 id="limits">What it does not do</h2>
<ul>
<li>Gated and private repositories (the page has no Hugging Face login).</li>
<li>Split files (<code>-00001-of-0000N</code>): it checks the part you pick; the header is in the first part.</li>
<li>Renamed files: a new file name has its own history. Repositories whose history was squashed show only the uploads that remain.</li>
<li>It does not say whether a new upload is better, only what changed.</li>
</ul>

<h2 id="faq">Questions</h2>
<dl>
{chr(10).join("<dt>%s</dt><dd>%s</dd>" % (e(q), e(a)) for q, a in faq)}
</dl>

<h2 id="related">Related</h2>
<ul>
<li><a href="/en/llama-cpp-pre-tokenizer-lookup/">"unknown pre-tokenizer type" and "BPE pre-tokenizer was not recognized": which llama.cpp build fixes it</a></li>
<li><a href="/en/gguf-arch-min-build-lookup/">"unknown model architecture": which llama.cpp build and Ollama version a GGUF needs</a></li>
<li><a href="/en/generation-stop-tokens-check/">Model does not stop generating: which token each engine stops on</a></li>
</ul>

<h2 id="sources">Sources</h2>
<ul>
<li>Hugging Face Hub API: <a href="https://huggingface.co/docs/hub/api">Hub API endpoints</a>, <a href="https://huggingface.co/docs/huggingface_hub/guides/manage-cache">cache layout (blobs named by sha256)</a>, <a href="https://huggingface.co/docs/hub/ollama">using Ollama with Hub GGUF files</a></li>
<li>GGUF: <a href="https://github.com/ggml-org/ggml/blob/master/docs/gguf.md">file format specification</a>; gguf-py <a href="https://github.com/ggml-org/llama.cpp/blob/master/gguf-py/gguf/scripts/gguf_new_metadata.py">gguf_new_metadata.py</a>, <a href="https://github.com/ggml-org/llama.cpp/blob/master/gguf-py/gguf/scripts/gguf_set_metadata.py">gguf_set_metadata.py</a>, <a href="https://pypi.org/project/gguf/">gguf on PyPI</a></li>
<li>Re-upload questions: <a href="{HF}/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/discussions/6">bartowski Llama 3.1 discussion #6</a>, and the repositories in the survey table</li>
</ul>
</main>
<script>
{JS}
</script>
</body>
</html>
"""
doc.encode("ascii")
(out / "index.html").write_text(doc)
print("wrote", len(doc), "bytes; repos", len(recs), "steps", len(steps), K, "tpl", TPL, "tpl only", TPL_ONLY)
