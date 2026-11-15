"""Collect run_select.py output (out/*.jsonl) into one compact data.json for the page.
usage: python3 build_data.py <dir with out/ and wt_<tag>/> <vllm git dir>"""
import json, glob, re, subprocess, os, sys
RUN, GIT = sys.argv[1], sys.argv[2]
R = {}
for f in sorted(glob.glob(f'{RUN}/out/v*.jsonl')) + sorted(glob.glob(f'{RUN}/out/fix_*.jsonl')):
    for l in open(f):
        r = json.loads(l); R[(r['tag'], r['cap'], r['scenario'])] = r
tags = sorted({k[0] for k in R}, key=lambda t: [int(x) for x in t[1:].split('.')])
dates = {}
for t in tags:
    # tag date (same convention as the other vLLM pages on the site)
    dates[t] = subprocess.run(['git', '-C', GIT, 'for-each-ref', '--format=%(creatordate:short)', f'refs/tags/{t}'], capture_output=True, text=True).stdout.strip()
    assert re.fullmatch(r'\d{4}-\d\d-\d\d', dates[t]), t
caps = sorted({k[1] for k in R})
SC = ['nvfp4', 'fp8_block', 'fp8_tensor', 'ct_fp8_channel', 'ct_fp8_tensor_static', 'modelopt_fp8', 'mxfp4_gptoss']
strings = []; sidx = {}
def S(x):
    if x is None: return -1
    if x not in sidx: sidx[x] = len(strings); strings.append(x)
    return sidx[x]
def order_of(r):
    for m in r.get('log') or []:
        mm = re.search(r"potential backends: \[(.*)\]", m)
        if mm: return [S(x.strip().strip("'")) for x in mm.group(1).split(',')]
    return None
res = {}
CT = {}; MT = {}
missing = []
for t in tags:
    for c in caps:
        for s in SC:
            r = R.get((t, c, s))
            if r is None: missing.append((t, c, s)); continue
            if not r.get('ok'):
                res[f"{t}|{c}|{s}"] = {"e": S(r['error'] + ': ' + r['msg'])}
                continue
            cand = {S(b): S(v) for b, v in (r.get('candidates') or {}).items() if not b.startswith('_') and not v.startswith('no kernel class')}
            mp = r.get('map') or {}
            mp = {S(k): (S(v) if isinstance(v, str) else [S(x) for x in v]) for k, v in mp.items() if not k.startswith('_') and v}
            ck = json.dumps(cand, sort_keys=True); mk = json.dumps(mp, sort_keys=True)
            if ck not in CT: CT[ck] = len(CT)
            if mk not in MT: MT[mk] = len(MT)
            res[f"{t}|{c}|{s}"] = {"b": S(r['backend']), "o": order_of(r), "c": CT[ck], "m": MT[mk]}
print("missing", missing, file=sys.stderr)
# --moe-backend exists from v0.17.0 (FusedMoEConfig.moe_backend / KernelConfig)
flag = [t for t in tags if os.path.exists(f'{RUN}/wt_{t}/vllm/config/kernel.py') and 'moe_backend' in open(f'{RUN}/wt_{t}/vllm/config/kernel.py').read()]
out = {"tags": [[t, dates[t]] for t in tags], "caps": caps, "S": strings, "r": res,
       "CT": [json.loads(k) for k in CT], "MT": [json.loads(k) for k in MT], "flag": flag}
json.dump(out, open(f'{RUN}/data.json', 'w'), separators=(',', ':'))
print(len(json.dumps(out, separators=(',', ':'))), "bytes", len(strings), "strings", file=sys.stderr)
