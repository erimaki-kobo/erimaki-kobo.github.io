#!/usr/bin/env python3
"""Regenerate en/model-arch-min-version/index.html from the page as published and a new data.json.

Usage: python3 -I build_page.py <index.html in> <data.json> <index.html out> <today YYYY-MM-DD>
The published page is the template: the three data tables are rendered again from data.json
(tables.py), and every number or version in the prose that comes from the data is replaced by pattern,
each pattern required to match exactly as many times as stated. The tool script and the CSS are untouched.
Run check_tables.py first: it proves tables.py reproduces the published tables from the published data.
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tables as T

src, data_p, out, today = sys.argv[1:5]
s = Path(src).read_text(encoding="ascii")
D = json.load(open(data_p))
VL, TF = D["vl_latest"], D["tf_latest"]
n_tf, n_vl = len(D["tf"]), len(D["vl"])
cnt = {c: sum(1 for v in D["vl"].values() if v[1] == c) for c in "nptgo"}
n_tf_removed = sum(1 for v in D["tf"].values() if v[1])
n_tf_tags = sum(1 for t in D["dates"] if re.match(r"v[1-9]", t))
n_vl_tags = sum(1 for t in D["dates"] if t.startswith("v0."))
BUILD = D["gguf_build"]

# ---- the examples the prose names must still be what the data says ----
def first(mt, cls, arch):
    return D["tf"][mt][0], D["vl"][cls][0], "b" + D["gg"][arch][0]
assert first("qwen3", "Qwen3ForCausalLM", "qwen3") == ("v4.51.0", "v0.8.4", "b5092")
assert first("qwen3_5", "Qwen3_5ForConditionalGeneration", "qwen35") == ("v5.2.0", "v0.17.0", "b7990")
assert first("gemma4", "Gemma4ForConditionalGeneration", "gemma4") == ("v5.5.0", "v0.19.0", "b8637")
assert D["dates"]["v4.51.0"] == "2025-04-05"                                   # FAQ: "released 2025-04-05"
assert D["vl"]["Olmo2ForCausalLM"] == ["v0.6.5", "t", "v0.25.1"] and D["vl"]["QWenLMHeadModel"][1:] == ["p", "v0.23.0"]
assert D["vl"]["BartForConditionalGeneration"][1] == "o" and n_tf_removed == 28
assert (D["tf"]["kimi_k25"][0], D["vl"]["KimiK25ForConditionalGeneration"][0]) == ("v5.13.0", "v0.15.0")
assert (D["tf"]["deepseek_v2"][0], D["vl"]["DeepseekV2ForCausalLM"][0]) == ("v4.54.0", "v0.5.1")
assert [D["h2g"][c][0] for c in ("MistralForCausalLM", "DeepseekV3ForCausalLM", "Qwen3_5ForConditionalGeneration")] == ["llama", "deepseek2", "qwen35"]
# Mistral Large 4: the Transformers class name is not registered; vLLM's own name is native from v0.34.0
ML4_TF, ML4_VL = "MistralLarge4ForConditionalGeneration", "MistralLarge4ForCausalLM"
assert D["tf"]["mistral_large4"][0] == "v5.22.0" and ML4_TF not in D["vl"] and D["vl"][ML4_VL] == ["v0.34.0", "n"]


def sub(pattern, repl, count=1):
    global s
    s, n = re.subn(pattern, repl, s)
    assert n == count, (pattern, n)


# ---- tables ----
s, _ = T.replace_tbody(s, "tft", T.tft_rows(D))
s, _ = T.replace_tbody(s, "vlt", T.vlt_rows(D))
_, fam_old = T.replace_tbody(s, "fam", "")
fam = []
for r in fam_old.split("\n"):
    c = re.findall(r"<td>(.*?)</td>", r)
    assert len(c) == 9, r
    mt, cls = re.sub(r"<[^>]+>", "", c[1]), re.sub(r"<[^>]+>", "", c[3])
    if cls == ML4_TF:
        c3, c5, c6, c7, c8, c9 = T.fam_cells(D, mt, cls, vl_name=ML4_VL)
        c6 = "native under that name only (Mistral-format <code>params.json</code>)"
    else:
        c3, c5, c6, c7, c8, c9 = T.fam_cells(D, mt, cls)
    fam.append("<tr>" + "".join("<td>%s</td>" % x for x in (c[0], c[1], c3, c[3], c5, c6, c7, c8, c9)) + "</tr>")
s, _ = T.replace_tbody(s, "fam", "\n".join(fam))
sub(r"<th>vLLM v[0-9.]+</th>", "<th>vLLM %s</th>" % VL)
sub(r"<th>In v[0-9.]+</th>", "<th>In %s</th>" % VL)

# ---- prose ----
sub(r"any of the \d+ model types Transformers has registered and the \d+ architecture names vLLM has used",
    "any of the %d model types Transformers has registered and the %d architecture names vLLM has used" % (n_tf, n_vl))
sub(r'<p class="meta">Published 2026-11-13 &middot; Corrected 2026-11-14: the Transformers fallback logs a warning &middot; (Corrected 2026-11-17[^&]*&middot; )?(Updated [0-9-]+ &middot; )?Data as of [0-9-]+ &middot; '
    r"Transformers up to v[0-9.]+ \([0-9-]+\) &middot; vLLM up to v[0-9.]+ \([0-9-]+\)",
    '<p class="meta">Published 2026-11-13 &middot; Corrected 2026-11-14: the Transformers fallback logs a warning &middot; Corrected 2026-11-17: dates are now PyPI upload dates '
    '(vLLM v0.10.2 was shown with the date of its git tag, 2025-10-07, instead of 2025-09-13) &middot; Updated %s &middot; Data as of %s &middot; '
    "Transformers up to %s (%s) &middot; vLLM up to %s (%s)" % (today, today, TF, D["dates"][TF], VL, D["dates"][VL]))
sub(r"Dates are the release tag dates[^<]*</p>|Dates are the day each release was uploaded to PyPI \(UTC\)\.</p>",
    "Dates are the day each release was uploaded to PyPI (UTC).</p>")
sub(r"Mistral Large 4 is in Transformers v5\.22\.0[^<]*(<code>[^<]*</code>[^<]*)*</p>",
    "Mistral Large 4 is in Transformers v5.22.0; vLLM had no native class for it up to v0.33.0, and v0.34.0 adds one under the name "
    "<code>%s</code>, which vLLM's loader for Mistral-format configs (<code>params.json</code>) assigns. The Transformers class name "
    "<code>%s</code> is still not in vLLM's registry.</p>" % (ML4_VL, ML4_TF))
sub(r"<li>\d+ names that vLLM once implemented itself now run through that backend on purpose",
    "<li>%d names that vLLM once implemented itself now run through that backend on purpose" % cnt["t"])
sub(r"<li>\d+ names were removed and raise", "<li>%d names were removed and raise" % cnt["p"])
sub(r"<li>\d+ names moved to plugins", "<li>%d names moved to plugins" % cnt["o"])
sub(r"converted from the generative class of the same model in v[0-9.]+; the lookup", "converted from the generative class of the same model in %s; the lookup" % VL)
sub(r"uses the converter at llama\.cpp b\d+ \(\d+ names\)", "uses the converter at llama.cpp %s (%d names)" % (BUILD, len(D["h2g"])))
sub(r"\(\d+ rows\), then vLLM by architecture name \(\d+ rows; \d+ native in v[0-9.]+\)",
    "(%d rows), then vLLM by architecture name (%d rows; %d native in %s)" % (n_tf, n_vl, cnt["n"], VL))
sub(r"at each of \d+ final release tags from v4\.0\.0 to v[0-9.]+,", "at each of %d final release tags from v4.0.0 to %s," % (n_tf_tags, TF))
sub(r"at each of \d+ final release tags from v0\.1\.0 to v[0-9.]+,", "at each of %d final release tags from v0.1.0 to %s," % (n_vl_tags, VL))
sub(r"removed and plugin lists of v[0-9.]+ give the status column", "removed and plugin lists of %s give the status column" % VL)
sub(r"tables in <code>modeling_auto\.py</code> at v[0-9.]+[^<]*</li>",
    "tables in <code>modeling_auto.py</code> at %s. A class that two model types share keeps the one that registered it first.</li>" % TF)
sub(r"<code>conversion/</code> package at b\d+, text models only", "<code>conversion/</code> package at %s, text models only" % BUILD)
# JSON-LD
_ld = r"Every model_type in Transformers v4\.0\.0 to v[0-9.]+ and every architecture name in vLLM v0\.1\.0 to v[0-9.]+,"
assert len(re.findall(_ld, s)) >= 1
s = re.sub(_ld, "Every model_type in Transformers v4.0.0 to %s and every architecture name in vLLM v0.1.0 to %s," % (TF, VL), s)
s = re.sub(r'("dateModified": ")\d{4}-\d\d-\d\d(")', lambda m: m.group(1) + today + m.group(2), s)
assert len(re.findall(r'"dateModified": "%s"' % today, s)) >= 1

# ---- nothing stale left outside the tables ----
a, b = s.index('<table id="tft">'), s.index("</table>", s.index('<table id="vlt">'))
rest = re.sub(r"<script>.*?</script>", "", s[:a] + s[b:], flags=re.S)
for old in ("v5.22.2", "b12352", " 816 ", " 471 "):
    assert old not in rest, (old, rest[max(0, rest.index(old) - 80):rest.index(old) + 80])
stale = re.findall(r"[^<>]{0,50}v0\.33\.0[^<>]{0,30}", rest)
assert all("up to v0.33.0" in x or "after v0.33.0" in x for x in stale), stale
s.encode("ascii")
Path(out).write_text(s, encoding="ascii")
print("index.html", len(s), "bytes | tf", n_tf, "| vl", n_vl, cnt, "| h2g", len(D["h2g"]), "| tags", n_tf_tags, n_vl_tags)
