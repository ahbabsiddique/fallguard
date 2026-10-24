import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
FG = LinearSegmentedColormap.from_list("fg", ["#F6FAF9", "#99D6CF", "#0F766E", "#0B3B3C"])
ROOT = "Data/UT_HAR"
with open(f"{ROOT}/data/X_test.csv", "rb") as f: X = np.load(f).reshape(-1, 250, 90)
with open(f"{ROOT}/label/y_test.csv", "rb") as f: y = np.load(f).reshape(-1)
plt.rcParams.update({"font.family": "sans-serif", "font.size": 9})
fig, axes = plt.subplots(3, 1, figsize=(5, 5.4))
for ax, (c, name, pick) in zip(axes, [(2, "Walking", np.argmax), (1, "Falling", np.argmax), (0, "Lying down", np.argmin)]):
    idx = np.where(y == c)[0]
    i = idx[pick(X[idx].std(axis=(1, 2)))]
    ax.imshow(X[i].T, aspect="auto", cmap=FG, origin="lower")
    ax.set_title(name, loc="left", fontsize=10, color="#0B3B3C", pad=4)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_color("#D7E7E4")
plt.tight_layout(); plt.savefig("what_wifi_sees.png", dpi=150, facecolor="white")
print("saved")
