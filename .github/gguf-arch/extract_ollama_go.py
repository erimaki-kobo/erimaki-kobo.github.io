#!/usr/bin/env python3
"""Exact architecture names the Ollama Go engine registers (model.Register("<arch>")),
per release tag. git grep is slow on a blobless clone, so only run it once per
distinct model/models directory listing and reuse for tags with the same listing.
Reads ollama_tags.json, writes ollama_go_registry.json (tag -> [archs])."""
import json, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
OL = ROOT / "ollama"
tags = json.loads((ROOT / "ollama_tags.json").read_text())["tags"]
cache = {}
out = {}
for r in tags:
    dirs = tuple(r["go_engine_archs"])
    if not dirs:
        out[r["tag"]] = []
        continue
    if dirs not in cache:
        s = subprocess.run(["git", "-C", str(OL), "grep", "-h", r'model\.Register("', r["tag"], "--", "model/models"],
                           capture_output=True, text=True).stdout
        names = sorted(set(re.findall(r'model\.Register\("([^"]+)"', s)))
        cache[dirs] = names
        print(r["tag"], len(dirs), "dirs ->", len(names), "registered", file=sys.stderr)
    out[r["tag"]] = cache[dirs]
(ROOT / "ollama_go_registry.json").write_text(json.dumps(out, indent=1))
print("distinct listings:", len(cache), file=sys.stderr)
