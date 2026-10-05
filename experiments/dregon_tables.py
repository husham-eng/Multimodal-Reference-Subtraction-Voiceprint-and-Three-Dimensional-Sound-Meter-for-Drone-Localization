"""Tables and figure for the DREGON evaluation from the per-segment CSVs in docs/revision/dregon."""
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")
from droneloc.stats import bootstrap_ci, wilson  # noqa: E402

D = Path("docs/revision/dregon")
REC = [("silent-flight_whitenoise-low", "Motors off, white noise (low)"),
       ("free-flight_whitenoise-high", "Free flight, white noise (high)"),
       ("free-flight_whitenoise-low", "Free flight, white noise (low)"),
       ("free-flight_speech-high", "Free flight, speech (high)"),
       ("free-flight_speech-low", "Free flight, speech (low)")]
SOURCE_ON = {"silent-flight_whitenoise-low": 12.5}  # loudspeaker silent before this (dataset: 10 s room silence)


def load(name, variant):
    f = D / f"DREGON_{name}_room1_result{'' if variant == 'plain' else '_' + variant}.csv"
    return [{k: float(v) if v not in ("",) else None for k, v in r.items()} for r in csv.DictReader(open(f))]


def stats(rows):
    e = np.array([r["error_deg"] for r in rows])
    k = int(np.sum(e <= 10))
    return {"n": len(e), "median": bootstrap_ci(e), "k10": k, "ci10": wilson(k, len(e)), "k20": int(np.sum(e <= 20))}


out = {}
for key, label in REC:
    out[key] = {"label": label}
    for v in ("plain", "noise_sub"):
        rows = load(key, v)
        out[key][v] = stats(rows)
        if key in SOURCE_ON:
            out[key][v + "_source_on"] = stats([r for r in rows if r["t_start"] >= SOURCE_ON[key]])
# pooled in-flight white noise
for v in ("plain", "noise_sub"):
    rows = load("free-flight_whitenoise-high", v) + load("free-flight_whitenoise-low", v)
    out.setdefault("pooled_whitenoise_flight", {})[v] = stats(rows)
# systematic offset on successful in-flight white-noise segments (noise_sub)
rows = [r for r in load("free-flight_whitenoise-high", "noise_sub") + load("free-flight_whitenoise-low", "noise_sub")
        if r["error_deg"] <= 10]
daz = [((r["est_azimuth_deg"] - r["azimuth_deg"] + 180) % 360) - 180 for r in rows]
dele = [r["est_elevation_deg"] - r["elevation_deg"] for r in rows]
out["offset_success"] = {"az_median": float(np.median(daz)), "el_median": float(np.median(dele)), "n": len(rows)}
# where failures point: elevation of the estimate for failed in-flight segments (plain)
fails = [r for k, _ in REC[1:] for r in load(k, "plain") if r["error_deg"] > 20]
out["fail_elev_plain"] = {"n": len(fails), "frac_above_30": float(np.mean([r["est_elevation_deg"] > 30 for r in fails]))}
(D / "dregon_table.json").write_text(json.dumps(out, indent=1, default=float))
print(json.dumps({k: (v.get("plain", {}).get("k10"), v.get("noise_sub", {}).get("k10")) for k, v in out.items() if isinstance(v, dict)}, default=str))
print(out["offset_success"], out["fail_elev_plain"])

# figure: azimuth and elevation tracks, white noise high and low (fixed noise subtraction)
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
fig, ax = plt.subplots(2, 2, figsize=(10, 5.6), sharex="col")
for j, key in enumerate(["free-flight_whitenoise-high", "free-flight_whitenoise-low"]):
    for v, mk, col, lab in (("plain", "x", "#c0392b", "no pre-processing"), ("noise_sub", "o", "#1f6fb2", "noise cross-spectra subtracted")):
        rows = load(key, v)
        t = [(r["t_start"] + r["t_end"]) / 2 for r in rows]
        ax[0, j].plot(t, [r["est_azimuth_deg"] for r in rows], mk, ms=3.5, color=col, label=lab, alpha=0.8)
        ax[1, j].plot(t, [r["est_elevation_deg"] for r in rows], mk, ms=3.5, color=col, alpha=0.8)
    rows = load(key, "plain")
    t = [(r["t_start"] + r["t_end"]) / 2 for r in rows]
    ax[0, j].plot(t, [r["azimuth_deg"] for r in rows], "-", color="k", lw=1.3, label="ground truth (Vicon)")
    ax[1, j].plot(t, [r["elevation_deg"] for r in rows], "-", color="k", lw=1.3)
    ax[0, j].set_title(dict(REC)[key] + (" (−11.8 dB)" if "high" in key else ""), fontsize=10)
    ax[1, j].set_xlabel("time [s]")
ax[0, 0].set_ylabel("azimuth [°]"); ax[1, 0].set_ylabel("elevation [°]")
h, l = ax[0, 0].get_legend_handles_labels()
fig.legend(h, l, fontsize=8, loc="upper center", ncol=3, frameon=False)
for a in ax.ravel():
    a.grid(alpha=0.3)
fig.tight_layout(rect=(0, 0, 1, 0.94))
for ext in ("png", "pdf"):
    fig.savefig(f"outputs/revision/figs/fig11_dregon.{ext}", dpi=600 if ext == "png" else None)
print("saved fig11_dregon")
