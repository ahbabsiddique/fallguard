import os, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
FG = LinearSegmentedColormap.from_list("fg", ["#F6FAF9", "#99D6CF", "#0F766E", "#0B3B3C"])
CLASSES = ["lie down", "fall", "walk", "pick up", "run", "sit down", "stand up"]
ROOT = "Data/UT_HAR"
with open(f"{ROOT}/data/X_test.csv", "rb") as f: X = np.load(f).reshape(-1, 250, 90)
with open(f"{ROOT}/label/y_test.csv", "rb") as f: y = np.load(f).reshape(-1)
os.makedirs("signals", exist_ok=True)
for c, name in enumerate(CLASSES):
    idx = np.where(y == c)[0]
    s = X[idx].std(axis=(1, 2))
    i = idx[np.argmin(s)] if name == "lie down" else idx[np.argmax(s)]
    fig, ax = plt.subplots(figsize=(6, 2.4))
    ax.imshow(X[i].T, aspect="auto", cmap=FG, origin="lower")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_visible(False)
    plt.subplots_adjust(0, 0, 1, 1)
    plt.savefig(f"signals/{name.replace(' ', '_')}.png", dpi=150)
    plt.close(fig)
print(sorted(os.listdir("signals")))
