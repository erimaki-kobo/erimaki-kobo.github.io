"""usage: <python with one matplotlib> inst_probe.py names.json > inst.json
probe.py reads class attributes; attributes set in __init__ (Legend.legendHandles before 3.7) are only on objects.
This builds one object of each class (Agg canvas, no display) and runs hasattr for every class-member name in names.json."""
import json, sys, warnings
warnings.simplefilter("ignore")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib import animation, cm
import mpl_toolkits.mplot3d  # noqa: registers projection="3d"
fig = plt.figure()
ax = fig.add_subplot(1, 2, 1)
ln, = ax.plot([0, 1], [0, 1], label="a")
leg = ax.legend()
sm = cm.ScalarMappable(cmap="viridis")
sm.set_array([0, 1])
cb = fig.colorbar(sm, ax=ax)
tx = ax.text(0, 0, "t")
ax3 = fig.add_subplot(1, 2, 2, projection="3d")
anim = animation.FuncAnimation(fig, lambda i: [ln], frames=2, blit=False)
OBJ = {"matplotlib.figure:Figure": fig, "matplotlib.axes:Axes": ax, "matplotlib.backends.backend_agg:FigureCanvasAgg": FigureCanvasAgg(fig),
       "matplotlib.colorbar:Colorbar": cb, "matplotlib.legend:Legend": leg, "matplotlib.text:Text": tx, "matplotlib.lines:Line2D": ln,
       "matplotlib.colors:Colormap": plt.get_cmap("viridis"), "mpl_toolkits.mplot3d.axes3d:Axes3D": ax3, "matplotlib.animation:FuncAnimation": anim}
fig.canvas.draw()
out = {}
for k, names in json.load(open(sys.argv[1])).items():
    if k in OBJ:
        out[k] = {n: hasattr(OBJ[k], n) for n in names}
json.dump({"matplotlib": matplotlib.__version__, "inst": out}, sys.stdout)
