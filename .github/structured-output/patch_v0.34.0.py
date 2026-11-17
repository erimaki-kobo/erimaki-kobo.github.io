#!/usr/bin/env python3
"""Extend en/vllm-structured-output-backend-cost/index.html from v0.33.0 to v0.34.0.

Usage: python3 -I patch_v0.34.0.py <index.html> <vllm.git> <today YYYY-MM-DD>
Run only after same_rules.py shows that the functions that pick and validate the backend are
unchanged between the two tags (this script checks the ones the page depends on again), and
requirements/common.txt pins the same backend libraries. Every replacement is counted, so the
script fails instead of half-patching a page it does not recognise. It is not idempotent.
"""
import ast, json, re, subprocess, sys
from pathlib import Path

page, repo, today = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
OLD, NEW = "v0.33.0", "v0.34.0"


def show(tag, path):
    return subprocess.run(["git", "-C", repo, "show", "%s:%s" % (tag, path)], capture_output=True, text=True, check=True).stdout


def fn(tag, path, qual):
    node = ast.parse(show(tag, path))
    for part in qual.split("."):
        node = next(n for n in ast.iter_child_nodes(node) if getattr(n, "name", None) == part)
    return ast.dump(node)


# 1. the rules the checker reproduces are the same code in both tags
MUST_MATCH = [
    ("vllm/sampling_params.py", "SamplingParams._validate_structured_outputs"),
    ("vllm/sampling_params.py", "StructuredOutputsParams.__post_init__"),
    ("vllm/v1/structured_output/backend_xgrammar.py", "has_xgrammar_unsupported_json_features"),
    ("vllm/v1/structured_output/backend_xgrammar.py", "validate_xgrammar_grammar"),
    ("vllm/v1/structured_output/backend_guidance.py", "validate_guidance_grammar"),
    ("vllm/v1/structured_output/backend_guidance.py", "has_guidance_unsupported_json_features"),
    ("vllm/v1/structured_output/backend_outlines.py", "validate_structured_output_request_outlines"),
    ("vllm/config/structured_outputs.py", "StructuredOutputsConfig._validate_structured_output_config"),
]
for path, qual in MUST_MATCH:
    assert fn(OLD, path, qual) == fn(NEW, path, qual), (path, qual)
pins = lambda t: sorted(l.split(";")[0].strip() for l in show(t, "requirements/common.txt").splitlines()
                        if re.match(r"(xgrammar|llguidance|outlines_core|lm-format-enforcer|lark)\b", l))
assert pins(OLD) == pins(NEW) and len(pins(NEW)) >= 4, (pins(OLD), pins(NEW))
assert "v0.35.0" in show(NEW, "vllm/config/structured_outputs.py") + show(NEW, "vllm/v1/structured_output/__init__.py") \
    + show(NEW, "vllm/v1/structured_output/backend_lm_format_enforcer.py"), "lm-format-enforcer removal notice changed"

# 2. dates: the day each release was uploaded to PyPI, taken from the compatibility matrix's data
MX = {"v" + r["v"]: r["pypi_date"] for r in json.loads((page.parent.parent / "vllm-torch-cuda-driver-matrix" / "matrix.json").read_text())["releases"]}


def tag_date(v):
    assert re.fullmatch(r"\d{4}-\d\d-\d\d", MX[v]), v
    return MX[v]


s = page.read_text(encoding="ascii")
m = re.search(r'(<script type="application/json" id="so-data">)(.*?)(</script>)', s, re.S)
D = json.loads(m.group(2))
assert D["versions"][0][0] == OLD and len(D["versions"]) == 45
vers = [[NEW, tag_date(NEW)]] + [[v, tag_date(v)] for v, _ in D["versions"]]
redated = sum(1 for (v, d), (_, d0) in zip(vers[1:], D["versions"]) if d != d0)
D = {"asof": today, "versions": vers}
dj = json.dumps(D)
assert "</" not in dj
s = s[:m.start(2)] + dj + s[m.end(2):]


def rep(old, new, count):
    global s
    assert s.count(old) == count, (old, s.count(old))
    s = s.replace(old, new)


rep("v0.32.0 &ndash; v0.33.0", "v0.32.0 &ndash; v0.34.0", 3)
rep("v0.30.0 &ndash; v0.33.0", "v0.30.0 &ndash; v0.34.0", 1)
rep("blob/v0.33.0/", "blob/v0.34.0/", 5)
rep("It still works in v0.33.0 but logs", "It still works in v0.34.0 but logs", 2)
rep('"dateModified": "2026-11-11"', '"dateModified": "%s"' % today, 1)
rep("<p class=\"meta\">Published 2026-11-11 &middot; vLLM v0.8.5 to v0.33.0 (45 releases) &middot; read from vLLM's source at each release tag; "
    "the checker's rules were compared with vLLM's own code on 3,000 generated schemas for every release, with no differences &middot; "
    "speed was not measured for this page</p>",
    "<p class=\"meta\">Published 2026-11-11 &middot; Updated %s &middot; vLLM v0.8.5 to v0.34.0 (46 releases; the dates in the version list are PyPI upload dates) &middot; read from vLLM's source at each release tag; "
    "the checker's rules were compared with vLLM's own code on 3,000 generated schemas for every release up to v0.33.0, with no differences; "
    "in v0.34.0 the functions that choose and validate the backend are the same code as in v0.33.0 (compared as syntax trees) and the backend libraries "
    "are pinned to the same versions &middot; speed was not measured for this page</p>" % today, 1)
left = re.findall(r"[^<>]{0,12}v0\.33\.0[^<]{0,30}", re.sub(r"<script.*?</script>", "", s, flags=re.S))
assert len(left) == 3 and all(("up to v0.33.0" in x) or ("as in v0.33.0" in x) or ("v0.33.0 marks lm-format-enforcer" in x) for x in left), left
s.encode("ascii")
page.write_text(s, encoding="ascii")
print("patched: 46 versions, newest %s (%s); %d older dates changed to the PyPI upload date" % (NEW, vers[0][1], redated))
