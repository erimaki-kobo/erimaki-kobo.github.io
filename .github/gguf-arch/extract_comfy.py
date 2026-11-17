#!/usr/bin/env python3
"""Read the GGUF architecture allowlists of ComfyUI-GGUF and two forks from git history -> comfy.json.

The ComfyUI custom node city96/ComfyUI-GGUF refuses a file whose general.architecture is not in
IMG_ARCH_LIST (Unet Loader) or TXT_ARCH_LIST (CLIPLoader) with "Unexpected [text model] architecture
type in GGUF file: 'X'". That is a different check from llama.cpp's "unknown model architecture".
For each loader this walks the first-parent history of its default branch, parses loader.py (and
nodes.py before the December 2024 split) with ast, and records the first commit at which each name
is on a list. Nothing from the repositories is imported or run.

Usage: python3 -I extract_comfy.py [PREVIOUS_archs.json]
Expects clones in ./comfy-city96, ./comfy-leejet, ./comfy-chriscoletech (see run.sh).
If one repository cannot be read, its rows are taken from PREVIOUS_archs.json and marked stale,
so that a renamed or deleted fork does not stop the llama.cpp and Ollama tables from refreshing.
"""
import ast, datetime, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREV = Path(sys.argv[1]) if len(sys.argv) > 1 else None

LOADERS = [
    {"id": "city96", "repo": "city96/ComfyUI-GGUF", "dir": "comfy-city96", "ref": "origin/main",
     "registry_ref": "origin/stable", "registry_package": "comfyui-gguf", "registry_skip": {"2.0.0"},
     "name": "city96/ComfyUI-GGUF", "kind": "original"},
    {"id": "leejet", "repo": "leejet/ComfyUI-GGUF", "dir": "comfy-leejet", "ref": "origin/HEAD",
     "registry_ref": None, "registry_package": None, "registry_skip": set(), "name": "leejet/ComfyUI-GGUF", "kind": "fork"},
    {"id": "chriscoletech", "repo": "ChrisColeTech/ComfyUI-GGUF-Loader", "dir": "comfy-chriscoletech", "ref": "origin/HEAD",
     "registry_ref": "origin/HEAD", "registry_package": "comfyui-gguf-loader", "registry_skip": set(),
     "name": "ChrisColeTech/ComfyUI-GGUF-Loader", "kind": "fork"},
]
# registry_package: the [project] name under which the repository publishes to the Comfy Registry; versions
# carried in pyproject.toml under another name (history inherited from the original) are not its releases.
# registry_skip: city96 keeps the placeholder 2.0.0 on main ("2.0.0 = GitHub main, 1.X.X = ComfyUI Registry").
# Before the lists were split (city96 0a1723b, 2024-12-20) one inline set held both kinds.
INLINE_TEXT = {"t5", "t5encoder"}
NAME_OK = re.compile(r"[A-Za-z0-9_.\-]{1,40}\Z")


def git(d, *a, check=True):
    r = subprocess.run(["git", "-C", str(ROOT / d), *a], capture_output=True, text=True)
    if r.returncode != 0:
        if check:
            raise RuntimeError("git %s failed in %s: %s" % (" ".join(a), d, r.stderr.strip()[:300]))
        return None
    return r.stdout


def utc_date(iso):
    return datetime.datetime.fromisoformat(iso).astimezone(datetime.timezone.utc).date().isoformat()


def str_set(node):
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)) and node.elts and all(
            isinstance(x, ast.Constant) and isinstance(x.value, str) for x in node.elts):
        return {x.value for x in node.elts}
    return None


def lists_in(source):
    """Return (image_names, text_names) for one version of a file, or None if it has no allowlist."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    img = txt = None
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            if n.targets[0].id == "IMG_ARCH_LIST":
                img = str_set(n.value)
            elif n.targets[0].id == "TXT_ARCH_LIST":
                txt = str_set(n.value)
    if img is not None and txt is not None:
        return img, txt
    if img is not None or txt is not None:
        raise RuntimeError("only one of IMG_ARCH_LIST / TXT_ARCH_LIST could be read")
    for n in ast.walk(tree):  # the inline form: if arch_str not in {"flux", ...}:
        if (isinstance(n, ast.Compare) and isinstance(n.left, ast.Name) and n.left.id == "arch_str"
                and len(n.ops) == 1 and isinstance(n.ops[0], ast.NotIn)):
            s = str_set(n.comparators[0])
            if s:
                return s - INLINE_TEXT, s & INLINE_TEXT
    return None


def version_in(d, commit):
    """(package name, version) from pyproject.toml at a commit, or (None, None)."""
    s = git(d, "show", "%s:pyproject.toml" % commit, check=False) or ""
    n = re.search(r'^name\s*=\s*"([^"]+)"', s, re.M)
    m = re.search(r'^version\s*=\s*"([^"]+)"', s, re.M)
    return (n.group(1) if n else None, m.group(1) if m else None)


def walk(d, ref):
    """Yield (commit, iso_date, subject, (img, txt) or None) along the first-parent history, oldest first."""
    log = git(d, "log", "--first-parent", "--reverse", "--format=%H%x09%cI%x09%s", ref)
    cache = {}
    for line in log.splitlines():
        c, iso, subj = line.split("\t", 2)
        found = None
        for path in ("loader.py", "nodes.py"):
            blob = git(d, "rev-parse", "-q", "--verify", "%s:%s" % (c, path), check=False)
            if not blob:
                continue
            blob = blob.strip()
            if blob not in cache:
                cache[blob] = lists_in(git(d, "show", blob))
            if cache[blob]:
                found = cache[blob]
                break
        yield c, iso, subj, found


def first_seen(d, ref):
    """{(kind, name): {...first commit...}} for names on the list at the head of ref, plus head info."""
    first, head, last = {}, None, None
    for c, iso, subj, found in walk(d, ref):
        head = (c, iso, subj)
        if not found:
            continue
        last = found
        for kind, names in (("image", found[0]), ("text", found[1])):
            for n in names:
                first.setdefault((kind, n), {"commit": c, "date": utc_date(iso), "subject": subj})
        # a name that left the list and came back counts from its return
        for key in [k for k in first if k[1] not in (found[0] if k[0] == "image" else found[1])]:
            del first[key]
    if last is None:
        raise RuntimeError("no allowlist found anywhere in the history of %s %s" % (d, ref))
    for kind, n in first:
        if not NAME_OK.match(n):
            raise RuntimeError("unexpected name %r" % n)
    return first, head


def registry_versions(d, ref, package, skip):
    """{(kind, name): {"version", "date", "commit"}}: the first published version whose tree lists the name.
    Both repositories publish to the Comfy Registry when pyproject.toml changes on this branch, so a
    version is the tree of the commit that set it."""
    out, prev, latest = {}, None, None
    for c, iso, subj, found in walk(d, ref):
        name, v = version_in(d, c)
        if v is None or (name or "").lower() != package or v in skip or v == prev:  # the name's case varies
            continue
        prev = v
        latest = {"version": v, "date": utc_date(iso), "commit": c}
        if not found:
            continue
        cur = {("image", n) for n in found[0]} | {("text", n) for n in found[1]}
        for key in cur:
            out.setdefault(key, dict(latest))
        for key in [k for k in out if k not in cur]:
            del out[key]
    return out, latest


def read_loader(L):
    first, head = first_seen(L["dir"], L["ref"])
    reg, reg_latest = (registry_versions(L["dir"], L["registry_ref"], L["registry_package"], L["registry_skip"])
                       if L["registry_ref"] else ({}, None))
    rows = []
    for (kind, n), f in sorted(first.items()):
        r = {"list": kind, "name": n, "date": f["date"], "commit": f["commit"], "subject": f["subject"]}
        if (kind, n) in reg:
            r["registry_version"] = reg[(kind, n)]["version"]
            r["registry_date"] = reg[(kind, n)]["date"]
        rows.append(r)
    return {"id": L["id"], "name": L["name"], "repo": L["repo"], "kind": L["kind"], "stale": False,
            "head_commit": head[0], "head_date": utc_date(head[1]), "head_subject": head[2],
            "registry_latest": reg_latest, "names": rows}


prev = {}
if PREV and PREV.exists():
    prev = {x["id"]: x for x in json.loads(PREV.read_text()).get("comfyui_gguf", {}).get("loaders", [])}

loaders = []
for L in LOADERS:
    try:
        loaders.append(read_loader(L))
    except Exception as ex:  # keep the last good rows instead of failing the whole refresh
        print("WARNING: could not read %s: %s" % (L["repo"], ex), file=sys.stderr)
        if L["id"] not in prev:
            raise
        old = dict(prev[L["id"]])
        old["stale"] = True
        loaders.append(old)

c96 = next(x for x in loaders if x["id"] == "city96")
have = {(r["list"], r["name"]) for r in c96["names"]}
orig = {(r["list"], r["name"]): r["commit"] for r in c96["names"]}
for x in loaders:  # a fork's row is "inherited" when it is the very commit that added the name upstream
    for r in x["names"]:
        r["inherited"] = x["kind"] == "fork" and orig.get((r["list"], r["name"])) == r["commit"]
assert {("text", "t5"), ("text", "llama"), ("image", "flux"), ("image", "sdxl")} <= have, "city96 lists look wrong"
out = {"loaders": loaders}
(ROOT / "comfy.json").write_text(json.dumps(out, indent=1))
for x in loaders:
    print("%-34s head %s %s  text %d  image %d%s" % (
        x["name"], x["head_commit"][:7], x["head_date"], sum(1 for r in x["names"] if r["list"] == "text"),
        sum(1 for r in x["names"] if r["list"] == "image"), "  STALE" if x["stale"] else ""))
