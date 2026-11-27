import subprocess, sys, re
# usage: bisect_tag.py gitdir tagregex regex path1 [path2 ...]
g, tagre, pat = sys.argv[1], sys.argv[2], re.compile(sys.argv[3])
paths = sys.argv[4:]
def key(t):
    return [int(x) for x in re.findall(r'\d+', t)]
tags = sorted([t for t in subprocess.run(['git','-C',g,'tag'],capture_output=True,text=True).stdout.split() if re.fullmatch(tagre,t)], key=key)
def has(t):
    for p in paths:
        r = subprocess.run(['git','-C',g,'show',f'{t}:{p}'],capture_output=True,text=True)
        if r.returncode==0 and pat.search(r.stdout): return True
    return False
if not has(tags[-1]): print('not in latest', tags[-1]); sys.exit()
lo, hi = 0, len(tags)-1
while lo < hi:
    m = (lo+hi)//2
    if has(tags[m]): hi = m
    else: lo = m+1
print(tags[lo], '(previous', tags[lo-1] if lo else None, ')', 'latest', tags[-1])
