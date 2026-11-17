#!/usr/bin/env python3
"""Independent check of args_hist.json. usage: python3 -I test_data.py args_hist.json HIST_DIR
args_hist.py reads the classes with ast. This file does not: for a sample of (class, argument) pairs it searches
the text of the file that defines the class for the argument as a declaration ("name:" at field level, or
"name" followed by ":", "=" or "," in the __init__ signature), at the first release (must be there) and at the
release before (must not be there), and the same around the last release for removed arguments."""
import json, random, re, subprocess, sys
D = json.load(open(sys.argv[1])); H = sys.argv[2]
random.seed(1117)
FILES = {  # class -> candidate paths, newest layout first
 ("peft", "LoraConfig"): ["src/peft/tuners/lora/config.py", "src/peft/tuners/lora.py", "src/peft/config.py", "src/peft/utils/config.py"],
 ("transformers", "TrainingArguments"): ["src/transformers/training_args.py"],
 ("transformers", "Trainer"): ["src/transformers/trainer.py"],
 ("trl", "SFTConfig"): ["trl/trainer/sft_config.py", "trl/trainer/base_config.py", "trl/trainer/_base_config.py"],
 ("trl", "SFTTrainer"): ["trl/trainer/sft_trainer.py"],
 ("trl", "DPOConfig"): ["trl/trainer/dpo_config.py", "trl/trainer/base_config.py", "trl/trainer/_base_config.py"],
 ("trl", "GRPOConfig"): ["trl/trainer/grpo_config.py", "trl/trainer/base_config.py", "trl/trainer/_base_config.py"],
}
def show(lib, tag, path):
    p = subprocess.run(["git", "-C", "%s/%s.git" % (H, lib), "show", "%s:%s" % (tag, path)], capture_output=True)
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else ""
def class_text(src, cls):
    """Text of `class cls` up to the next top-level statement (found by indentation, not by parsing)."""
    m = re.search(r"^class %s\b.*?:\s*$" % re.escape(cls), src, re.M)
    if not m:
        return ""
    rest = src[m.end():]
    n = re.search(r"^(?=\S)(?!#)", rest, re.M)
    return rest[:n.start()] if n else rest
def declared(lib, cls, tag, arg):
    txt = ""
    for path in FILES[(lib, cls)]:
        src = show(lib, tag, path)
        if not src:
            continue
        if cls.endswith("Trainer"):
            body = class_text(src, cls)
            m = re.search(r"def __init__\((.*?)\)\s*(->[^:]*)?:", body, re.S)
            txt += m.group(1) if m else ""
            return bool(re.search(r"(^|[\s,(*])%s\s*[:=,)]|(^|[\s,(*])%s\s*$" % (re.escape(arg), re.escape(arg)), txt, re.M))
        # config: the class itself in its own file, every dataclass in the shared base files
        txt += class_text(src, cls) if path == FILES[(lib, cls)][0] or "lora" in path else src
    return bool(re.search(r"^    %s\s*:" % re.escape(arg), txt, re.M))
fails = n = 0
for (lib, cls), _ in FILES.items():
    L = D[lib]; T = L["tags"]; C = L["classes"][cls]
    names = sorted(C["p"])
    for arg in random.sample(names, min(18, len(names))):
        r = C["p"][arg]; a, b = r[0][0], r[-1][1]
        checks = [("present at first", T[a], True)]
        if a > 0 and (not C["has"] or C["has"][0][0] < a): checks.append(("absent before first", T[a - 1], False))
        checks.append(("present at last", T[b], True))
        if b < len(T) - 1 and not any(k.split(">")[0] == arg for k in C["alias"]): checks.append(("absent after last", T[b + 1], False))
        for what, tag, want in checks:
            n += 1
            if declared(lib, cls, tag, arg) != want:
                fails += 1; print("FAIL", lib, cls, arg, what, tag)
print("%d/%d pass" % (n - fails, n)); sys.exit(1 if fails else 0)
