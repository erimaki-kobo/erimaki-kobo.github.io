#!/usr/bin/env python3
"""Decide whether the rebuilt page replaces the published one; if so, copy it into the site.

Usage: python3 -I finish.py OUT_DIR SITE_ROOT [--force]
Publishes when the architecture table, the Ollama table or the ComfyUI-GGUF lists changed, when the published data is
7 or more days old, or with --force. Refuses (exit 1) if either table shrank, because that means
the extraction broke or upstream removed something a person should look at.
Prints publish=true|false and message=... lines (for GITHUB_OUTPUT).
"""
import datetime, json, re, shutil, sys
from pathlib import Path

out, site = Path(sys.argv[1]), Path(sys.argv[2])
force = "--force" in sys.argv[3:]
dst = site / "en" / "gguf-arch-min-build-lookup"
URL = "https://erimaki-kobo.github.io/en/gguf-arch-min-build-lookup/"

new = json.loads((out / "archs.json").read_text())
old = json.loads((dst / "archs.json").read_text())

def names(d):
    return {a["architecture"] for a in d["architectures"]}

def releases(d):
    return {r["release"] for r in d["ollama_releases"]}

gone_archs = sorted(names(old) - names(new))
gone_rel = sorted(releases(old) - releases(new))
if gone_archs or gone_rel:
    print("refusing to publish: missing from the new build:", gone_archs, gone_rel, file=sys.stderr)
    sys.exit(1)

def comfy(d):
    """{loader id: {(list, name)}} of the ComfyUI-GGUF allowlists; empty for a page built before they were added."""
    return {x["id"]: {(r["list"], r["name"]) for r in x["names"]} for x in d.get("comfyui_gguf", {}).get("loaders", [])}

def comfy_rows(d):
    return [(x["id"], x["head_commit"], x["names"]) for x in d.get("comfyui_gguf", {}).get("loaders", [])]

# A name leaving a ComfyUI-GGUF list is possible upstream (unlike a llama.cpp architecture), so it is reported, not refused.
for lid, names in comfy(old).items():
    gone = sorted(names - comfy(new).get(lid, set()))
    if gone:
        print("note: no longer on the %s list:" % lid, gone, file=sys.stderr)
if comfy(old) and set(comfy(old)) - set(comfy(new)):
    print("refusing to publish: ComfyUI-GGUF loader missing from the new build:", sorted(set(comfy(old)) - set(comfy(new))), file=sys.stderr)
    sys.exit(1)

changed = ((new["architectures"], new["ollama_releases"], comfy_rows(new))
           != (old["architectures"], old["ollama_releases"], comfy_rows(old)))
today = datetime.datetime.now(datetime.timezone.utc).date()
age = (today - datetime.date.fromisoformat(old["as_of"])).days
publish = force or changed or age >= 7
added = sorted(names(new) - names(old))
print("changed:", changed, "| new architectures:", added, "| new releases:", sorted(releases(new) - releases(old)),
      "| published data age (days):", age, "| force:", force, file=sys.stderr)

if publish:
    for f in ("index.html", "archs.json"):
        shutil.copyfile(out / f, dst / f)
    page = (dst / "index.html").read_text(encoding="ascii")
    m = re.search(r'"dateModified": "(\d{4}-\d{2}-\d{2})", "inLanguage"', page)
    sm = site / "sitemap.xml"
    s = sm.read_text(encoding="utf-8")
    s2, n = re.subn(r"(<loc>" + re.escape(URL) + r"</loc>\s*<lastmod>)[^<]*(</lastmod>)", lambda k: k.group(1) + m.group(1) + k.group(2), s)
    assert n == 1, "sitemap entry not found"
    sm.write_text(s2, encoding="utf-8")

print("publish=%s" % ("true" if publish else "false"))
print("message=en: refresh GGUF architecture lookup (llama.cpp %s, Ollama %s)" % (new["llama_cpp_head"], new["ollama_latest"]["tag"][1:]))
