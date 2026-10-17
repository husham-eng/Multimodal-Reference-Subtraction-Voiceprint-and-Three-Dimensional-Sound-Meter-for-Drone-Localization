"""Time each step of one live direction estimate (run on the target computer, e.g. a Raspberry Pi).

    python experiments/profile_live.py live.wav --refs 6,7 --bpf 105,200 --steering sphere
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from droneloc import live  # noqa: E402
from droneloc.dsp import welch_psd  # noqa: E402
from droneloc.localization import _local_cap  # noqa: E402
from droneloc.voiceprint import estimate_bpf  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("wav")
ap.add_argument("--refs", default="6,7")
ap.add_argument("--cal", type=float, default=3.0)
ap.add_argument("--bpf", default="105,200")
ap.add_argument("--steering", default="sphere")
ap.add_argument("--n-dirs", type=int, default=1000)
a = ap.parse_args()
refs = [int(i) for i in a.refs.split(",")] if a.refs else []
bpf = tuple(float(v) for v in a.bpf.split(","))

x, fs = sf.read(a.wav, dtype="int16")
t0 = time.perf_counter()
L = live.LiveLocator(live.SPHERE_DIRS * 0.08, fs, refs=refs, cal_seconds=a.cal if refs else 0, bpf=bpf,
                     steering=a.steering, n_dirs=a.n_dirs)
print(f"{'startup':14s} {1000 * (time.perf_counter() - t0):7.0f} ms")
L.push(x[:int(a.cal * fs)])
end = int(a.cal * fs) + L.win + fs // 2
w = (x[end - L.win - L.pad:end, L.array_ch + L.refs].astype(float) / 32768).T
M = len(L.array_ch)
s = L.srp
total = 0.0


def step(name, f, n=5):
    global total
    t = time.perf_counter()
    for _ in range(n):
        r = f()
    dt = 1000 * (time.perf_counter() - t) / n
    total += dt
    print(f"{name:14s} {dt:7.1f} ms")
    return r


mics = step("cancel", lambda: L.canc.transform(w[:M], w[M:]) if L.canc else w[:M])[:, -L.win:]
f0, _ = step("bpf", lambda: estimate_bpf(welch_psd(mics[0], 4096, 1024), fs, *bpf))
G = step("cross-spectra", lambda: L.gcc.cross_spectra(mics, f0))
Gw = G[:, s.fmask].astype(np.complex64)
p = step("grid search", lambda: (s._grid @ Gw.ravel()).real)
cap = step("cap directions", lambda: _local_cap(s.dirs[int(np.argmax(p))], s.refine_deg, s.cap_n))
phi = step("cap phases", lambda: s._phases(cap))
step("cap power", lambda: s._power(Gw, phi))
print(f"{'total':14s} {total:7.1f} ms   (must stay below the hop, 250 ms by default)")
