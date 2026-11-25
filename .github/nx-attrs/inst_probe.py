"""usage: <python with one networkx> inst_probe.py names.json > inst.json
probe.py reads class attributes; networkx 1.x set G.node, G.edge, G.adj on the object in __init__. This builds a small graph of
each class and runs hasattr for every class-member name in names.json."""
import json, sys, warnings
warnings.simplefilter("ignore")
import networkx as nx
OBJ = {}
for c in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
    g = getattr(nx, c)()
    g.add_edge(1, 2)
    OBJ["networkx:" + c] = g
out = {}
for k, names in json.load(open(sys.argv[1])).items():
    if k in OBJ:
        out[k] = {n: hasattr(OBJ[k], n) for n in names}
json.dump({"networkx": nx.__version__, "inst": out, "dir": {k: sorted(n for n in dir(g) if not n.startswith("_")) for k, g in OBJ.items()}}, sys.stdout)
