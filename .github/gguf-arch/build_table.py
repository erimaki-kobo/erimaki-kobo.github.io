#!/usr/bin/env python3
"""Merge llama_archs.json + ollama_tags.json + ollama_go_registry.json into table.json:
one row per GGUF architecture string with
  - llama.cpp: first commit, first bNNNN tag, date
  - Ollama: first release whose pinned llama.cpp already contains that commit
            ("via llama.cpp"), and/or first release whose Go engine registers the arch
            ("via Go engine"); the earlier of the two is the headline answer.
Ancestry is checked with git merge-base --is-ancestor only where build numbers tie."""
import json, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
LC = ROOT / "llama.cpp"

L = json.loads((ROOT / "llama_archs.json").read_text())
O = json.loads((ROOT / "ollama_tags.json").read_text())
G = json.loads((ROOT / "ollama_go_registry.json").read_text())
V = json.loads((ROOT / "ollama_vendored.json").read_text())
VEND, PATCH = V["vendored"], V["patch_adds_other_eras"]

def bnum(tag):
    return int(tag[1:]) if tag else None

def is_ancestor(a, b):
    return subprocess.run(["git", "-C", str(LC), "merge-base", "--is-ancestor", a, b]).returncode == 0

pin_commit_cache = {}
def pin_commit(pin):
    if pin not in pin_commit_cache:
        r = subprocess.run(["git", "-C", str(LC), "rev-parse", "-q", "--verify", pin + "^{commit}"], capture_output=True, text=True)
        pin_commit_cache[pin] = r.stdout.strip() if r.returncode == 0 else None
    return pin_commit_cache[pin]

otags = [t for t in O["tags"] if t["llama_build"] or G.get(t["tag"])]
rows = []
checks = 0
for a in L["archs"]:
    if a["arch"] == "(unknown)":
        continue
    fb = bnum(a["first_tag"])
    via_llama = None
    via_go = None
    runs = []
    for t in otags:
        # does this release's bundled llama.cpp (after Ollama's patches) know the architecture?
        ok = False
        how = None
        if VEND.get(t["tag"]):
            ok = a["arch"] in VEND[t["tag"]]
            how = "vendored source"
        elif t["llama_build"]:
            pb = bnum(t["llama_build"])
            if pb > fb or (pb == fb and t["llama_build_exact"]):
                ok = True
            elif pb == fb:
                pc = pin_commit(t["pin"])
                checks += 1
                ok = bool(pc) and is_ancestor(a["commit"], pc)
            how = "pin"
            if not ok and a["arch"] in PATCH.get(t["tag"], []):
                ok, how = True, "ollama patch"
        if VEND.get(t["tag"]) or t["llama_build"]:
            if ok and (not runs or runs[-1]["closed"]):
                runs.append({"from": t["tag"], "to": t["tag"], "date": t["date"], "pinned_build": t["llama_build"], "how": how, "closed": False})
            elif ok:
                runs[-1]["to"] = t["tag"]
            elif runs and not runs[-1]["closed"]:
                runs[-1]["closed"] = True
        if via_go is None and a["arch"] in G.get(t["tag"], []):
            via_go = {"tag": t["tag"], "date": t["date"]}
    for r_ in runs:
        r_.pop("closed")
    if runs:
        last = runs[-1]
        if last["to"] == otags[-1]["tag"]:
            via_llama = {"tag": last["from"], "date": last["date"], "pinned_build": last["pinned_build"], "how": last["how"]}
    earlier = runs[:-1] if via_llama else runs
    cands = [x for x in (via_llama, via_go) if x]
    first = min(cands, key=lambda x: x["date"]) if cands else None
    # Go engine removed later: note whether the arch is still registered at HEAD-ish (last tag with registry)
    rows.append({
        "arch": a["arch"], "enum": "LLM_ARCH_" + a["enum"],
        "llama_commit": a["commit"], "llama_commit_date": a["commit_date"], "llama_subject": a["subject"],
        "llama_first_build": a["first_tag"], "llama_first_build_date": a["tag_date"],
        "ollama_first": first["tag"] if first else None,
        "ollama_first_date": first["date"] if first else None,
        "ollama_via_llama": via_llama, "ollama_via_go": via_go,
        "ollama_earlier_runs": [[x["from"], x["to"], x["how"]] for x in earlier], "note": a.get("note"),
    })

latest_ollama = O["tags"][-1]
out = {
    "as_of": L["head_date"],
    "llama_head": L["head"], "llama_head_tag": L["head_tag"],
    "ollama_latest": {"tag": latest_ollama["tag"], "date": latest_ollama["date"], "pinned_build": latest_ollama["llama_build"]},
    "ollama_tags": [{"tag": t["tag"], "date": t["date"], "pinned_build": t["llama_build"], "pin": t["pin"],
                      "pin_exact": t["llama_build_exact"], "go_archs": G.get(t["tag"], [])} for t in O["tags"]],
    "archs": rows,
}
(ROOT / "table.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print("rows", len(rows), "ancestry checks", checks)
for r in rows:
    if r["arch"] in ("gemma4", "qwen35", "qwen3next", "gemma3", "gpt-oss", "lfm2", "glm4moe", "mistral3", "plamo2", "llama", "deepseek2", "qwen3"):
        print(f'{r["arch"]:10} llama {r["llama_first_build"]} {r["llama_first_build_date"]} | ollama {r["ollama_first"]} {r["ollama_first_date"]} via_llama={r["ollama_via_llama"] and r["ollama_via_llama"]["tag"]} via_go={r["ollama_via_go"] and r["ollama_via_go"]["tag"]}')
none = [r["arch"] for r in rows if not r["ollama_first"]]
print("no ollama release yet:", none)

print("earlier windows:", [(r["arch"], r["ollama_earlier_runs"], r["ollama_via_llama"] and r["ollama_via_llama"]["tag"]) for r in rows if r["ollama_earlier_runs"]])
print("via patch (bundled build older than upstream first build):", [(r["arch"], r["ollama_via_llama"]["tag"], r["ollama_via_llama"]["pinned_build"], r["llama_first_build"]) for r in rows if r["ollama_via_llama"] and r["ollama_via_llama"]["pinned_build"] and bnum(r["ollama_via_llama"]["pinned_build"]) < bnum(r["llama_first_build"])])
