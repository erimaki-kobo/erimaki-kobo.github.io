#!/usr/bin/env python3
"""Build en/llama-cpp-removed-args-lookup/ (index.html + data.json) from data.json.

Usage: python3 -I build_page.py data.json <archs.json of the GGUF page> out_dir PUBLISHED MODIFIED
ASCII only. Every number and build in the prose comes from data.json and is asserted, so a new llama.cpp build
that changes the picture stops the build instead of leaving stale prose. style.css and tool.js sit next to this script.
"""
import html, json, re, shutil, sys
from pathlib import Path

data_p, archs_p, out_dir, PUB, MOD = sys.argv[1], sys.argv[2], Path(sys.argv[3]), sys.argv[4], sys.argv[5]
HERE = Path(__file__).resolve().parent
D = json.load(open(data_p))
ARCHS = json.load(open(archs_p))
F, E, OLD = D["flags"], D["envs"], D["old"]
L, FIRST, SW = D["latest"][0], D["first"][0], D["cli_switch"]
e = html.escape
URL = "https://erimaki-kobo.github.io/en/llama-cpp-removed-args-lookup/"
TITLE = 'llama.cpp "invalid argument": Removed Options by Build'
H1 = '"error: invalid argument" in llama.cpp: which build removed each llama-server and llama-cli option'
DESC = ('llama-server or llama-cli stops with "error: invalid argument: --name"? Paste the command to see which build '
        "removed each option and what replaced it.")
assert len(TITLE) <= 60 and 140 <= len(DESC) <= 160, (len(TITLE), len(DESC))


def bd(b):
    return "b%d (%s)" % (b, D["dates"][str(b)])


def rng(f, k):
    return f["any"] if f[k] == 1 else f[k]


def cur(f, k="any"):
    r = rng(f, k)
    return bool(r) and r[-1][1] is None


def code(s):
    return "<code>%s</code>" % e(s)


def names(ns):
    return " ".join(code(n) for n in sorted(ns, key=lambda n: (n.lstrip("-").lower(), n)))


def commit(rm):
    return '<a href="https://github.com/ggml-org/llama.cpp/commit/%s">%s</a>' % (rm[1], e(rm[2]))


gone = {n: f for n, f in F.items() if "rm" in f and "stub" not in f}
stubs = {n: f for n, f in F.items() if "stub" in f}
cli_lost = {n: f for n, f in F.items() if cur(f) and isinstance(f["cli"], list) and f["cli"] and f["cli"][-1][1]}
srv_lost = {n: f for n, f in F.items() if cur(f) and isinstance(f["srv"], list) and f["srv"] and f["srv"][-1][1]}
env_gone = {n: x for n, x in E.items() if x["r"][-1][1] and "stub" not in x}
env_stub = {n: x for n, x in E.items() if "stub" in x}
n_now = {k: sum(cur(f, k) for f in F.values()) for k in ("any", "srv", "cli", "cmp")}

# ---- facts the prose states ----
assert (len(gone), len(stubs), len(cli_lost), len(srv_lost), len(env_gone), len(env_stub), len(OLD)) == (50, 8, 22, 12, 38, 2, 24), \
    (len(gone), len(stubs), len(cli_lost), len(srv_lost), len(env_gone), len(env_stub), len(OLD))
LM = ["--mlock", "--mmap", "--no-mmap", "--direct-io", "--no-direct-io", "-dio", "-ndio"]
assert all(gone[n]["rm"][0] == 10875 for n in LM) and cur(F["--load-mode"]) and F["--load-mode"]["any"][0][0] == 10105 and F["--load-mode"]["al"] == ["-lm"]
assert gone["--mlock"]["hint"] == "DEPRECATED: --mlock is deprecated. use --load-mode mlock instead"
assert gone["--defrag-thold"]["rm"][0] == 12347 and "no longer necessary" in gone["--defrag-thold"]["hint"]
CNV = ["-cnv", "--conversation", "-no-cnv", "--no-conversation"]
assert all(cli_lost[n]["cli"][-1][1] == 10584 and cur(F[n], "cmp") for n in CNV)
at_switch = sorted(n for n, f in cli_lost.items() if f["cli"][-1][1] == SW)
assert SW == 7348 and len(at_switch) == 16 and all(cur(F[n], "cmp") for n in at_switch)
assert all(f["stub"][0] == 8955 for f in stubs.values()) and env_stub.keys() == {"LLAMA_ARG_DRAFT_MAX", "LLAMA_ARG_DRAFT_MIN"}
assert cur(F["--cache-idle-slots"]) and cur(F["--lazy-mode"]) and gone["--clear-idle"]["rm"][0] == 8852 and gone["--tensor-read-lazy"]["rm"][0] == 10700
assert F["-ngl"]["al"] == ["--gpu-layers", "--n-gpu-layers"] and cur(F["-ngl"], "srv") and "--ngl" not in F
assert rng(F["--embd-normalize"], "srv") == [[9193, None]] and rng(F["-p"], "srv")[-1][1] == 4443
assert D["neg_env_since"] == 7376
# Ollama: release -> bundled llama.cpp build, from the GGUF page's data
OR = {r["release"]: int(r["llama_cpp_build"][1:]) for r in ARCHS["ollama_releases"] if r["llama_cpp_build"]}
assert OR["v0.32.5"] == 10091 and OR["v0.32.6"] == 10242 and 10091 < F["--load-mode"]["any"][0][0] <= 10242
assert all(b < 10105 for r, b in OR.items() if [int(x) for x in r[1:].split(".")] <= [0, 32, 5])

# ---- tables ----
by_build = {}
for n, f in gone.items():
    by_build.setdefault(f["rm"][0], []).append(n)
USE = {8852: "Use <code>--cache-idle-slots</code>.", 10700: "Use <code>--lazy-mode</code> (<code>-lzm</code>).",
       10875: "Use <code>--load-mode</code> (<code>-lm</code>): <code>mlock</code>, <code>mmap</code>, <code>mmap+mlock</code>, <code>none</code> or <code>dio</code>."}
assert F["--lazy-mode"]["al"] == ["-lzm"]
rows = []
for b in sorted(by_build, reverse=True):
    ns = by_build[b]
    hints = sorted({gone[n]["hint"] for n in ns if gone[n].get("hint")})
    last = " ".join(code(h) for h in hints)
    rows.append('<tr id="b%d"><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
        b, bd(b), names(ns), commit(gone[ns[0]]["rm"]), " ".join(x for x in (USE.get(b, ""), last) if x)))
T_GONE = "\n".join(rows)
by_msg = {}
for n, f in stubs.items():
    by_msg.setdefault(f["stub"][1], []).append(n)
T_STUB = "\n".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (names(ns), bd(stubs[ns[0]]["stub"][0]), code("the argument has been removed. " + m))
                   for m, ns in sorted(by_msg.items()))


def who(f):
    return ", ".join(x for k, x in (("srv", "llama-server"), ("cli", "llama-cli"), ("cmp", "llama-completion")) if cur(f, k)) or \
        "other tools only (%s)" % ", ".join(x.lower() for x in (f["ex"] or []))


def lost_rows(lost, k):
    g = {}
    for n, f in lost.items():
        g.setdefault((f[k][-1][1], who(f)), []).append(n)
    return "\n".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (names(ns), bd(b), e(w)) for (b, w), ns in sorted(g.items(), key=lambda x: (-x[0][0], x[0][1])))


T_CLI, T_SRV = lost_rows(cli_lost, "cli"), lost_rows(srv_lost, "srv")
T_ENV = "\n".join('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (code(n), code(x["opt"]), bd(x["rm"][0]), commit(x["rm"]))
                  for n, x in sorted(env_gone.items(), key=lambda kv: (-kv[1]["rm"][0], kv[0])))
g = {}
for n, (a, b) in OLD.items():
    g.setdefault((a, b), []).append(n)
T_OLD = "\n".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (names(ns), bd(a), bd(b)) for (a, b), ns in sorted(g.items(), reverse=True))

FAQ = [
    ('What does "error: invalid argument: --mlock" mean in llama.cpp?',
     "The llama-server or llama-cli you ran does not have that option. --mlock, --mmap, --no-mmap and --direct-io were removed in build %s. "
     "Use --load-mode instead: --load-mode mlock, mmap, mmap+mlock, none or dio. --load-mode exists from %s."
     % (bd(10875), bd(10105))),
    ("Why does llama-cli say invalid argument for -cnv or -no-cnv?",
     "llama-cli was replaced by a new chat program in build %s, and -cnv / -no-cnv left it in %s. The previous program is still built as "
     "llama-completion, which accepts both." % (bd(SW), bd(10584))),
    ("Is --defrag-thold still needed?",
     "No. Its last warning said it is \"deprecated and no longer necessary to specify\", and build %s removed it. Delete it from the command line."
     % bd(12347)),
    ("What happens to a removed LLAMA_ARG_ environment variable?",
     "Nothing: llama.cpp reads only the variables of options it still has, so a removed one is ignored without an error or a warning. "
     "The exceptions are LLAMA_ARG_DRAFT_MAX and LLAMA_ARG_DRAFT_MIN, which stop startup since %s with \"the argument has been removed\"." % bd(8955)),
    ('Why does Ollama say "llama-server process has terminated ... invalid argument: --load-mode"?',
     "The llama-server that Ollama started is older than b10105, the first build with --load-mode. Ollama passes --load-mode from v0.32.6, which "
     "bundles llama.cpp b10242; v0.32.5 passes --no-mmap and bundles b10091. The program and the bundled server are from different installs: "
     "reinstall Ollama so that both come from one release."),
    ('What is the difference between "invalid argument" and "unknown argument"?',
     "The wording. Builds before %s parsed options by hand and printed \"error: unknown argument: NAME\"; from that build the options live in "
     "one table (common/arg.cpp) and the message is \"error: invalid argument: NAME\"." % bd(FIRST)),
]


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s))


FAQ_HTML = "\n".join("<dt>%s</dt>\n<dd>%s</dd>" % (e(q), e(a)) for q, a in FAQ)
ld = {"@context": "https://schema.org", "@graph": [
    {"@type": "TechArticle", "@id": URL + "#article", "headline": H1, "description": DESC, "url": URL, "datePublished": PUB, "dateModified": MOD,
     "inLanguage": "en", "author": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"},
     "publisher": {"@type": "Organization", "name": "Erimaki Kobo", "url": "https://erimaki-kobo.github.io/en/"},
     "about": ["llama.cpp", "llama-server", "llama-cli", "command-line options"], "isBasedOn": URL + "data.json"},
    {"@type": "WebApplication", "@id": URL + "#tool", "name": "llama.cpp option lookup by build", "url": URL + "#lookup",
     "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (runs in the browser)", "isAccessibleForFree": True,
     "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
     "description": "Paste a llama-server or llama-cli command line or its error; see for each option whether the newest build accepts it, the build that removed it and what replaced it."},
    {"@type": "Dataset", "@id": URL + "#data", "name": "llama.cpp command-line options and LLAMA_ARG environment variables by build",
     "description": "For each of %d option names and %d environment variables: the builds from b%d to b%d in which llama-server, llama-cli and "
                    "llama-completion accept it, and the commit that removed it." % (len(F), len(E), FIRST, L),
     "url": URL, "dateModified": D["asof"], "creator": {"@type": "Organization", "name": "Erimaki Kobo"},
     "license": "https://creativecommons.org/licenses/by/4.0/",
     "distribution": {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "data.json"}},
    {"@type": "FAQPage", "@id": URL + "#faq",
     "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
    {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Answers for LLM inference engineers", "item": "https://erimaki-kobo.github.io/en/"},
        {"@type": "ListItem", "position": 2, "name": "llama.cpp removed options", "item": URL}]},
]}
LD = json.dumps(ld)
assert "</" not in LD
DATA = json.dumps(D, separators=(",", ":"))
assert "</" not in DATA

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
<p class="lede"><strong><code>error: invalid argument: --name</code> means that the binary you ran has no such option in that build: it was removed, renamed, or it belongs to another llama.cpp tool.</strong> As of @@LB@@, @@NGONE@@ option names that llama.cpp accepted at some point since b@@FIRST@@ are gone, @@NSTUB@@ more only answer "the argument has been removed", and @@NCLI@@ still exist but llama-cli no longer takes them. Common cases: <code>--mlock</code>, <code>--mmap</code>, <code>--no-mmap</code> and <code>--direct-io</code> were removed in @@B10875@@ in favor of <code>--load-mode</code>; <code>--defrag-thold</code> was removed in @@B12347@@ and needs no replacement; <code>-cnv</code> and <code>-no-cnv</code> left llama-cli in @@B10584@@ and live on in llama-completion.</p>
<p class="meta">Published @@PUB@@ &middot; Data as of @@ASOF@@ &middot; llama.cpp b@@FIRST@@ to b@@L@@, every one of the @@NCOMMITS@@ commits that changed the option table &middot; read from source, nothing was run</p>

<h2 id="lookup">Which build removed my option?</h2>
<p>Paste the command line, or the error. Each option is checked against the newest build for the binary in the text. Add your build number, or your Ollama release, to see whether your own build has it.</p>
<div class="card">
<label for="q">Command line or error message</label>
<textarea id="q" spellcheck="false" placeholder="llama-server -m model.gguf --mlock --no-mmap --defrag-thold 0.1 -ngl 99"></textarea>
<div class="grid">
<div><label for="bin">Binary</label><select id="bin"><option value="auto">Detect from the text (llama-server if none)</option><option value="srv">llama-server</option><option value="cli">llama-cli</option><option value="cmp">llama-completion</option></select></div>
<div><label for="v">Your build or Ollama release (optional)</label><input id="v" placeholder="b10091 or 0.32.5" autocomplete="off"></div>
</div>
<div class="row"><button id="go" type="button">Check</button><span id="status" role="status"></span></div>
<div id="res" aria-live="polite"></div>
</div>
<p class="note"><code>llama-server --version</code> prints the build number: <code>version: 10091 (commit)</code> on older builds, <code>version: ... (build 12465, commit ...)</code> on current ones. The lookup runs in your browser on the data of this page; an Ollama release is translated to its bundled build with the table of the <a href="/en/gguf-arch-min-build-lookup/#ollama">GGUF lookup</a>. A name written with underscores after two dashes (<code>--ctx_size</code>) is read as <code>--ctx-size</code>, as llama.cpp itself does.</p>

<h2 id="removed">Which options were removed, and what replaces them?</h2>
<p><strong>@@NGONE@@ names in @@NGONEB@@ builds, newest first. From the build in the first column on, the name ends with <code>error: invalid argument</code>.</strong> The third column is the commit that deleted it. Where llama.cpp printed a deprecation warning before the removal, its text is quoted, because it names the replacement.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Removed in</th><th>Names</th><th>Commit</th><th>Instead</th></tr></thead>
<tbody>
@@T_GONE@@
</tbody></table></div>
<p class="note">Still accepted but spelled wrong is the other common case: <code>--ngl</code> is not an option; the names are <code>-ngl</code>, <code>--gpu-layers</code> and <code>--n-gpu-layers</code>. The lookup suggests the closest current names.</p>

<h2 id="stubs">Which options answer "the argument has been removed"?</h2>
<p><strong>@@NSTUB@@ names are still registered since @@B8955@@ only to stop with a message that names the replacement.</strong> The error reads <code>error while handling argument "--draft-max": the argument has been removed. use ...</code>.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Names</th><th>Stub since</th><th>Message</th></tr></thead>
<tbody>
@@T_STUB@@
</tbody></table></div>

<h2 id="binary">Which options exist, but not for my binary?</h2>
<p><strong>Every option is registered for a set of tools, and a tool rejects the others with the same <code>invalid argument</code> error.</strong> In b@@L@@, @@NANY@@ names exist; llama-server takes @@NSRV@@ of them, llama-cli @@NCLIN@@ and llama-completion @@NCMP@@. The largest change was @@BSW@@: llama-cli became a new chat program (commit "cli: new CLI experience", #17824) and the program it replaced continues as <code>llama-completion</code>. @@NSWITCH@@ names left llama-cli in that build, and all of them still work in llama-completion.</p>
<h3>No longer accepted by llama-cli (@@NCLI@@ names that still exist)</h3>
<div class="tw"><table class="flt">
<thead><tr><th>Names</th><th>llama-cli stopped taking it in</th><th>Accepted in b@@L@@ by</th></tr></thead>
<tbody>
@@T_CLI@@
</tbody></table></div>
<h3>No longer accepted by llama-server (@@NSRVLOST@@ names that still exist)</h3>
<div class="tw"><table class="flt">
<thead><tr><th>Names</th><th>llama-server stopped taking it in</th><th>Accepted in b@@L@@ by</th></tr></thead>
<tbody>
@@T_SRV@@
</tbody></table></div>
<p class="note">The reverse also happens: <code>--embd-normalize</code> existed for the embedding example long before llama-server accepted it in @@B9193@@.</p>

<h2 id="env">What happens to removed LLAMA_ARG_ environment variables?</h2>
<p><strong>Nothing, and that is the trap: llama.cpp reads only the variables of options it still has, so a removed variable is ignored without an error or a warning.</strong> @@NENV@@ variables stopped being read this way. Two are different: <code>LLAMA_ARG_DRAFT_MAX</code> and <code>LLAMA_ARG_DRAFT_MIN</code> still belong to stub options, so since @@B8955@@ setting them stops startup with <code>error while handling environment variable</code>. From @@B7376@@, an option that has a negated form also reads <code>LLAMA_ARG_NO_...</code> next to its <code>LLAMA_ARG_...</code> variable.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Variable</th><th>Belonged to</th><th>Ignored from</th><th>Commit</th></tr></thead>
<tbody>
@@T_ENV@@
</tbody></table></div>
<p><label for="filter">Filter all tables</label><input id="filter" placeholder="mmap" autocomplete="off"></p>

<h2 id="older">Before b@@FIRST@@: "error: unknown argument"</h2>
<p><strong>Builds before @@BFIRST@@ parsed options by hand and said <code>error: unknown argument: NAME</code>; the option table and the wording <code>invalid argument</code> start with that build.</strong> For the older period this page read the parser at one build in about every 250, from b@@OLD0@@ on, so the ranges are coarse: a name was still there in the first build of the row and gone by the second. @@NOLD@@ names from that period did not make it into the table.</p>
<div class="tw"><table class="flt">
<thead><tr><th>Names</th><th>Last seen in</th><th>Gone by</th></tr></thead>
<tbody>
@@T_OLD@@
</tbody></table></div>

<h2 id="ollama">Ollama: "llama-server process has terminated ... invalid argument"</h2>
<p><strong>Ollama starts a bundled llama-server with options it chooses, so this error means the server binary and the Ollama program are from different releases.</strong> Up to v0.32.5, Ollama's <code>llm/llama_server.go</code> passes <code>--no-mmap</code> and the release bundles llama.cpp b10091. From v0.32.6 it passes <code>--load-mode</code> and bundles b10242; <code>--load-mode</code> exists from @@B10105@@. <code>invalid argument: --load-mode</code> therefore comes from a llama-server older than b10105 started by an Ollama of v0.32.6 or newer. Reinstall so that both come from one release. The build inside every Ollama release is listed in the <a href="/en/gguf-arch-min-build-lookup/#ollama">GGUF lookup</a>.</p>

<h2 id="method">How was this built?</h2>
<ul>
<li><strong>Options:</strong> <code>common/arg.cpp</code> at each of the @@NCOMMITS@@ commits that changed it, from the commit that created it (@@BFIRST@@) to @@LB@@. Every <code>add_opt(common_arg(...))</code> gives the names, the negated names, <code>set_examples</code> / <code>set_excludes</code> (which tools register it) and <code>set_env</code>.</li>
<li><strong>Builds:</strong> each commit is mapped to the first <code>bNNNN</code> tag that contains it (@@NTAGS@@ tags). Dates are UTC dates of the tagged commit.</li>
<li><strong>Binaries:</strong> llama-server parses with <code>LLAMA_EXAMPLE_SERVER</code>; llama-cli with <code>LLAMA_EXAMPLE_MAIN</code> before b@@SW@@ and <code>LLAMA_EXAMPLE_CLI</code> from it; llama-completion with <code>LLAMA_EXAMPLE_COMPLETION</code>. An option without <code>set_examples</code>, or tagged <code>LLAMA_EXAMPLE_COMMON</code>, belongs to all three.</li>
<li><strong>Check:</strong> a second script searched the file at the build tags themselves for each quoted name, at the build where the data says it appeared or disappeared and at the build before: all @@NGONE@@ removals, the stubs, the removed variables and 60 additions agree.</li>
<li><strong>Ollama:</strong> <code>llm/llama_server.go</code> at the tags v0.32.5 and v0.32.6, and the bundled build of each release from the GGUF lookup's data.</li>
</ul>

<h2 id="limits">What this page does not cover</h2>
<ul>
<li>Nothing was compiled or run. The page says which names the parser registers, not whether an option still has an effect.</li>
<li>Options that changed meaning or default without changing name are not listed.</li>
<li>The lookup answers for llama-server, llama-cli and llama-completion. For the other tools that use the same table, the data file lists which tools each option is registered for. llama-bench parses its options itself and is not covered.</li>
<li>Before b@@FIRST@@ the ranges are coarse, and options that came and went between two of the builds read are missing.</li>
<li>Forks and wrappers (llama-cpp-python, LM Studio, koboldcpp) have their own option names.</li>
</ul>
<p>The same data as JSON: <a href="data.json">data.json</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>

<h2 id="faq">Questions</h2>
<dl>
@@FAQ@@
</dl>

<p class="note">Related: <a href="/en/gguf-arch-min-build-lookup/">"unknown model architecture": the llama.cpp build and Ollama release each GGUF needs</a> &middot; <a href="/en/vllm-removed-flags-lookup/">vLLM and SGLang: removed arguments and settings that silently stop working</a> &middot; <a href="/en/generation-stop-tokens-check/">Why a model does not stop generating: stop tokens by engine</a>.</p>

<h2 id="sources">Sources</h2>
<ul>
<li>llama.cpp: <a href="https://github.com/ggml-org/llama.cpp/commits/master/common/arg.cpp">history of common/arg.cpp</a>; <a href="https://github.com/ggml-org/llama.cpp/releases">build tags</a>; removal commits linked in the tables</li>
<li>llama.cpp before the option table: <code>common/common.cpp</code> and <code>examples/server/server.cpp</code> at the builds named above</li>
<li>Ollama: <a href="https://github.com/ollama/ollama/blob/v0.32.6/llm/llama_server.go">llm/llama_server.go at v0.32.6</a> and <a href="https://github.com/ollama/ollama/blob/v0.32.5/llm/llama_server.go">at v0.32.5</a></li>
<li>A report of the Ollama error: <a href="https://forum.langchain.com/t/llama-server-process-has-terminated-invalid-argument-load-mode-with-ollama-client-0-32-6-and-langchain-ollama-1-1-0/4320">LangChain forum thread 4320</a></li>
</ul>
</main>
<script type="application/json" id="la-data">@@DATA@@</script>
<script>@@JS@@</script>
</body>
</html>
"""
subs = {
    "TITLE": e(TITLE), "DESC": e(DESC), "URL": URL, "H1": e(H1), "LD": LD, "CSS": (HERE / "style.css").read_text(encoding="ascii").strip(),
    "JS": (HERE / "tool.js").read_text(encoding="ascii").strip(), "DATA": DATA, "FAQ": FAQ_HTML, "PUB": PUB, "ASOF": D["asof"],
    "LB": bd(L), "L": str(L), "FIRST": str(FIRST), "BFIRST": bd(FIRST), "SW": str(SW), "BSW": bd(SW),
    "NGONE": str(len(gone)), "NGONEB": str(len(by_build)), "NSTUB": str(len(stubs)), "NCLI": str(len(cli_lost)), "NSRVLOST": str(len(srv_lost)),
    "NENV": str(len(env_gone)), "NOLD": str(len(OLD)), "OLD0": str(D["old_snapshots"][0]), "NCOMMITS": str(D["n_commits"]), "NTAGS": "{:,}".format(D["n_tags"]),
    "NANY": str(n_now["any"]), "NSRV": str(n_now["srv"]), "NCLIN": str(n_now["cli"]), "NCMP": str(n_now["cmp"]), "NSWITCH": str(len(at_switch)),
    "B10875": bd(10875), "B12347": bd(12347), "B10584": bd(10584), "B8955": bd(8955), "B7376": bd(7376), "B9193": bd(9193), "B10105": bd(10105),
    "T_GONE": T_GONE, "T_STUB": T_STUB, "T_CLI": T_CLI, "T_SRV": T_SRV, "T_ENV": T_ENV, "T_OLD": T_OLD,
}
page = PAGE
for k, v in subs.items():
    page = page.replace("@@" + k + "@@", v)
left = re.findall(r"@@[A-Z0-9_]+@@", page)
assert not left, left
page.encode("ascii")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "index.html").write_text(page, encoding="ascii")
if (out_dir / "data.json").resolve() != Path(data_p).resolve():
    shutil.copyfile(data_p, out_dir / "data.json")
print("index.html", len(page), "bytes | gone", len(gone), "in", len(by_build), "builds | stubs", len(stubs), "| cli lost", len(cli_lost),
      "| srv lost", len(srv_lost), "| env", len(env_gone), "| now", n_now)
