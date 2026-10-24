import numpy as np, torch, torch.nn as nn, pandas as pd
from datetime import datetime, timedelta

CLASSES = ["lie down", "fall", "walk", "pick up", "run", "sit down", "stand up"]
ROOT = "Data/UT_HAR"
torch.manual_seed(0); np.random.seed(0)

def load(split):
    with open(f"{ROOT}/data/X_{split}.csv", "rb") as f:
        X = np.load(f).reshape(-1, 250 * 90).astype(np.float32)
    with open(f"{ROOT}/label/y_{split}.csv", "rb") as f:
        y = np.load(f).astype(np.int64).reshape(-1)
    return X, y

Xtr, ytr = load("train"); Xva, yva = load("val"); Xte, yte = load("test")
Xtr = np.concatenate([Xtr, Xva]); ytr = np.concatenate([ytr, yva])
lo, hi = Xtr.min(), Xtr.max()
norm = lambda X: (X - lo) / (hi - lo)
Xtr, Xte = norm(Xtr), norm(Xte)
print("Class counts (test):", np.bincount(yte))

dev = "mps" if torch.backends.mps.is_available() else "cpu"
model = nn.Sequential(
    nn.Linear(22500, 1024), nn.ReLU(), nn.Dropout(0.2),
    nn.Linear(1024, 128), nn.ReLU(), nn.Linear(128, 7)).to(dev)
opt = torch.optim.Adam(model.parameters(), lr=1e-3)
lossf = nn.CrossEntropyLoss()
Xt, yt = torch.tensor(Xtr).to(dev), torch.tensor(ytr).to(dev)

for epoch in range(60):
    model.train(); perm = torch.randperm(len(Xt))
    for i in range(0, len(Xt), 64):
        idx = perm[i:i + 64]
        opt.zero_grad(); loss = lossf(model(Xt[idx]), yt[idx]); loss.backward(); opt.step()
    if (epoch + 1) % 10 == 0:
        print(f"epoch {epoch + 1}, loss {loss.item():.3f}")

model.eval()
with torch.no_grad():
    probs = torch.softmax(model(torch.tensor(Xte).to(dev)), 1).cpu().numpy()
pred = probs.argmax(1)
print(f"\nTEST ACCURACY: {(pred == yte).mean():.3f}")
for c in range(7):
    m = yte == c
    print(f"  {CLASSES[c]:>9}: {(pred[m] == c).mean():.3f}")
torch.save(model.state_dict(), "fallguard_mlp.pt")

# ---- Build a demo "day" from real test recordings ----
pool = {c: [i for i in range(len(yte)) if yte[i] == c and pred[i] == c] or
           [i for i in range(len(yte)) if yte[i] == c] for c in range(7)}
story = [  # (start time, class index, number of 1-minute readings)
    ("07:00", 0, 5), ("07:05", 6, 1), ("07:06", 2, 6), ("07:12", 5, 1),
    ("09:30", 6, 1), ("09:31", 2, 5), ("09:36", 3, 1), ("09:37", 2, 4), ("09:41", 5, 1),
    ("12:30", 6, 1), ("12:31", 2, 6), ("12:37", 5, 1),
    ("14:05", 6, 1), ("14:06", 2, 8), ("14:14", 1, 1), ("14:15", 0, 10),
]
rows, rng = [], np.random.default_rng(0)
for start, c, n in story:
    t0 = datetime.strptime(f"2026-10-24 {start}", "%Y-%m-%d %H:%M")
    for k in range(n):
        i = int(rng.choice(pool[c]))
        p = int(pred[i])
        rows.append({"TS": (t0 + timedelta(minutes=k)).strftime("%Y-%m-%d %H:%M:%S"),
                     "ROOM": "Bedroom", "ACTIVITY": CLASSES[p],
                     "CONFIDENCE": round(float(probs[i, p]), 3), "IS_FALL": int(p == 1)})
pd.DataFrame(rows).to_csv("activity_log.csv", index=False)
print(f"\nWrote activity_log.csv with {len(rows)} rows")
