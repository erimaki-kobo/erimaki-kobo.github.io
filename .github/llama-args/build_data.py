#!/usr/bin/env python3
"""args_hist.json + old_flags.json -> data.json for en/llama-cpp-removed-args-lookup.

Usage: python3 -I build_data.py args_hist.json old_flags.json > data.json
For every option name: the builds in which llama-server, llama-cli and llama-completion accept it, the build that
removed it and that commit's subject, and whether it is now a stub that prints "the argument has been removed".
Ranges are [first build that has it, first build that no longer has it or null].
"""
import json, sys

H, OLD = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
C = H["commits"]
CLI_SWITCH = next(c["build"][0] for c in C if any("CLI" in (o["ex"] or []) for o in c["options"]))   # llama-cli: MAIN before, CLI from here
assert CLI_SWITCH == 7348, CLI_SWITCH
assert all(c["underscore"] for c in C)
for c in C:                                            # the two-list (positive, negative) form only exists together with the LLAMA_ARG_NO_ fallback
    assert c["neg_env"] or not any(o["neg"] for o in c["options"]), c["commit"]
    has_cli = any("CLI" in (o["ex"] or []) for o in c["options"])
    assert has_cli == (c["build"][0] >= CLI_SWITCH) and has_cli != any("MAIN" in (o["ex"] or []) for o in c["options"]), c["commit"]


def scopes(c, o):
    """Which of the three binaries accept this option at this commit."""
    def ok(ex):
        # arg.cpp: an option is kept when it names this example or LLAMA_EXAMPLE_COMMON (no set_examples = COMMON), unless excluded
        return (o["ex"] is None or ex in o["ex"] or "COMMON" in o["ex"]) and ex not in o["exc"]
    late = c["build"][0] >= CLI_SWITCH
    return {"any": True, "srv": ok("SERVER"), "cli": ok("CLI" if late else "MAIN"), "cmp": late and ok("COMPLETION")}


def state(c):
    names, envs = {}, {}
    for o in c["options"]:
        sc = scopes(c, o)
        for n, neg in [(x, 0) for x in o["names"]] + [(x, 1) for x in o["neg"]]:
            names[n] = {"sc": sc, "stub": o["removed"], "o": o, "neg": neg}
        if o["env"] and not o["removed"]:
            envs[o["env"]] = {"o": o, "derived": 0}
            if o["neg"] and c["neg_env"]:
                envs.setdefault(o["env"].replace("LLAMA_ARG_", "LLAMA_ARG_NO_"), {"o": o, "derived": 1})
    return names, envs


dates = {}
flags, envs = {}, {}
prev_names, prev_envs = {}, {}
for c in C:
    b, d = c["build"]
    dates[b] = d
    names, ev = state(c)
    for n in set(names) | set(prev_names):
        f = flags.setdefault(n, {"any": [], "srv": [], "cli": [], "cmp": []})
        cur = names.get(n)
        for k in ("any", "srv", "cli", "cmp"):
            on = bool(cur and not cur["stub"] and cur["sc"][k])
            r = f[k]
            if on and (not r or r[-1][1] is not None):
                if r and r[-1][1] == b:
                    r[-1][1] = None                    # removed and restored inside one build: no gap
                else:
                    r.append([b, None])
            elif not on and r and r[-1][1] is None:
                r[-1][1] = b
                if k == "any":
                    f["rm"] = [b, c["commit"][:10], c["subject"]]
        if cur:
            o = cur["o"]
            f["al"] = [x for x in (o["neg"] if cur["neg"] else o["names"]) if x != n]
            f["pair"] = o["names"] if cur["neg"] else o["neg"]
            f["neg"] = cur["neg"]
            f["ex"], f["exc"], f["env"] = o["ex"], o["exc"], o["env"]
            f["dep"] = int(o["deprecated"])
            f["hint"] = (o["warn"] or o["help"]) if o["deprecated"] else None      # upstream's own words about the replacement
            if cur["stub"]:
                if "stub" not in f:
                    f["stub"] = [b, cur["stub"]]
            else:
                f.pop("stub", None)
    for n in set(ev) | set(prev_envs):
        e = envs.setdefault(n, {"r": []})
        on = n in ev
        r = e["r"]
        if on and (not r or r[-1][1] is not None):
            if r and r[-1][1] == b:
                r[-1][1] = None
            else:
                r.append([b, None])
        elif not on and r and r[-1][1] is None:
            r[-1][1] = b
            e["rm"] = [b, c["commit"][:10], c["subject"]]
        if on:
            e["opt"] = ev[n]["o"]["names"][-1]
            e["derived"] = ev[n]["derived"]
    prev_names, prev_envs = names, ev
for f in flags.values():
    f["any"] = [r for r in f["any"] if r[0] != r[1]]
    for k in ("srv", "cli", "cmp"):
        f[k] = [r for r in f[k] if r[0] != r[1]]
        if f[k] == f["any"]:
            f[k] = 1                                   # same as "any"
    if f["any"] and f["any"][-1][1] is None:
        f.pop("rm", None)
for e in envs.values():
    if e["r"][-1][1] is None:
        e.pop("rm", None)
# an environment variable that still belongs to a stub is not ignored: its handler throws "the argument has been removed"
for o in C[-1]["options"]:
    if o["removed"] and o["env"]:
        envs[o["env"]]["stub"] = [flags[o["names"][0]]["stub"][0], o["removed"]]
for v in OLD["flags"].values():
    dates[v["last_seen"][0]], dates[v["gone_by"][0]] = v["last_seen"][1], v["gone_by"][1]
dates[H["latest_build"][0]] = H["latest_build"][1]
out = {"about": "llama.cpp command-line options by build, read from common/arg.cpp at every commit that touched it. CC BY 4.0, erimaki-kobo.github.io/en/llama-cpp-removed-args-lookup/",
       "asof": H["head_date"], "head": H["head"][:10], "latest": H["latest_build"], "first": C[0]["build"], "cli_switch": CLI_SWITCH,
       "n_commits": len(C), "n_tags": H["n_tags"], "neg_env_since": next(c["build"][0] for c in C if c["neg_env"]), "dates": {str(k): v for k, v in sorted(dates.items())},
       "flags": dict(sorted(flags.items())), "envs": dict(sorted(envs.items())),
       "old": {k: [v["last_seen"][0], v["gone_by"][0]] for k, v in OLD["flags"].items()}, "old_snapshots": [s[0] for s in OLD["snapshots"]]}
json.dump(out, sys.stdout, separators=(",", ":"))
cur = [n for n, f in flags.items() if f["any"] and f["any"][-1][1] is None]
print("names", len(flags), "current", len(cur), "stubs", sum("stub" in f for f in flags.values()),
      "gone", sum(1 for f in flags.values() if "rm" in f and "stub" not in f), "| envs", len(envs), "current", sum(e["r"][-1][1] is None for e in envs.values()),
      "| old", len(OLD["flags"]), file=sys.stderr)
