"""Collect outputs/revision/*.json into one summary used by the manuscript and the response letter."""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
R = Path("outputs/revision")


def load(n):
    p = R / f"{n}.json"
    return json.loads(p.read_text()) if p.exists() else None


out = {}
m1 = load("m1")
if m1:
    out["m1"] = {k: {kk: v[kk] for kk in ("label", "angle_median", "angle_p90", "range_err_median_pct", "n")} for k, v in m1.items()}
m4 = load("m4")
if m4:
    out["m4"] = m4
m5 = load("m5")
if m5:
    out["m5"] = m5
m6 = load("m6")
if m6:
    out["m6"] = {"summary": m6["summary"], "n_runs": m6["n_runs"],
                 "runs": [{k: r[k] for k in ("machinery_db", "wind_db", "snr_in", "snr_out", "detection", "angle_median", "track_median")} for r in m6["runs"]]}
m2 = load("m2")
if m2:
    out["m2"] = {"budget": m2["budget"], "absorption": m2["absorption_db_per_m"], "window": m2["window"],
                 "loop": {k: {kk: v[kk] for kk in ("success", "success_ci", "false_arrivals", "mean_time", "median_dir_err")} for k, v in m2["loop"].items()},
                 "loop_coherent": {k: {kk: v[kk] for kk in ("success", "success_ci", "false_arrivals", "mean_time", "median_dir_err")} for k, v in m2.get("loop_coherent", {}).items()}}
pipe = Path("outputs/rev_pipeline/report.json")
if pipe.exists():
    p = json.loads(pipe.read_text()); p.pop("frames", None)
    out["pipeline"] = p


def clean(o):
    """Strict JSON: NaN -> null, +/-inf -> +/-1e9 (JavaScript cannot parse NaN/Infinity)."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, float):
        if o != o:
            return None
        if o in (float("inf"), float("-inf")):
            return 1e9 if o > 0 else -1e9
    return o


(R / "summary.json").write_text(json.dumps(clean(out), indent=1, default=float, allow_nan=False))
print("parts:", list(out))
