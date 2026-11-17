#!/usr/bin/env python3
"""Decide whether the rebuilt llama-cpp-removed-args-lookup replaces the published one; if so, copy it in.

Usage: python3 -I finish.py OUT_DIR SITE_ROOT [--force]      (OUT_DIR holds index.html and data.json)
Publishes when the option tables changed, when the published data is 7 or more days old, or with --force.
Refuses (exit 1) if an option, an environment variable or an old-era flag that the published page lists is
missing from the new data: history does not shrink, so that means the extraction broke.
Prints publish=true|false and message=... lines (for GITHUB_OUTPUT).
"""
import datetime, json, re, shutil, sys
from pathlib import Path

out, site = Path(sys.argv[1]), Path(sys.argv[2])
force = "--force" in sys.argv[3:]
dst = site / "en" / "llama-cpp-removed-args-lookup"
URL = "https://erimaki-kobo.github.io/en/llama-cpp-removed-args-lookup/"
new = json.loads((out / "data.json").read_text())
old = json.loads((dst / "data.json").read_text())

TABLES = ("flags", "envs", "old", "old_snapshots", "first", "cli_switch", "neg_env_since")
for k in ("flags", "envs", "old"):
    gone = sorted(set(old[k]) - set(new[k]))
    if gone:
        print("refusing to publish: missing from the new %s:" % k, gone[:20], file=sys.stderr)
        sys.exit(1)
changed = any(new[k] != old[k] for k in TABLES)
today = datetime.datetime.now(datetime.timezone.utc).date()
age = (today - datetime.date.fromisoformat(old["asof"])).days
publish = force or changed or age >= 7
print("changed:", changed, "| new options:", sorted(set(new["flags"]) - set(old["flags"])),
      "| new env:", sorted(set(new["envs"]) - set(old["envs"])), "| latest build: b%d -> b%d" % (old["latest"][0], new["latest"][0]),
      "| published data age (days):", age, "| force:", force, file=sys.stderr)
if publish:
    for f in ("index.html", "data.json"):
        shutil.copyfile(out / f, dst / f)
    page = (dst / "index.html").read_text(encoding="ascii")
    m = re.search(r'"dateModified": "(\d{4}-\d{2}-\d{2})"', page)
    sm = site / "sitemap.xml"
    s = sm.read_text(encoding="utf-8")
    s2, n = re.subn(r"(<loc>" + re.escape(URL) + r"</loc>\s*<lastmod>)[^<]*(</lastmod>)", lambda k: k.group(1) + m.group(1) + k.group(2), s)
    assert n == 1, "sitemap entry not found"
    sm.write_text(s2, encoding="utf-8")
print("publish=%s" % ("true" if publish else "false"))
print("message=en: refresh llama.cpp removed-args lookup (b%d)" % new["latest"][0])
