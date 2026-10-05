"""Revision experiments for the passive (station) mode.

M1  sphere scattering and calibration errors          -> run_m1()
M4  reference-subtraction ablation and stress tests    -> run_m4()
M5  voiceprint with grouped splits and RPM excursions  -> run_m5()  (in exp_voiceprint.py)
M6  Monte Carlo over seeds, trajectories and SNR       -> run_m6()
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import numpy as np

from .catalog import DRONE_PROFILES
from .dsp import angle_between_deg, snr_db, welch_psd
from .localization import SoundMeter3D, harmonic_level_db
from .reference_subtraction import ReferenceCanceller
from .simulation import Scene, homing_trajectory, render, static
from .stats import bootstrap_ci, wilson
from .tracking import Kalman3D
from .voiceprint import N_FFT, estimate_bpf

FS = 16000
QUIET = dict(machinery_level_db=-100, wind_level_db=-100, bird_level_db=-100, sensor_noise_db=-100)


def calibrate_level(scene: Scene, rng, dist: float = 3.0, n_dirs: int = 6) -> float:
    """Measure L_1m the way it would be done with the physical sensor:
    record the drone alone at a known distance from several directions and
    scale to 1 m (spherical spreading)."""
    q = dataclasses.replace(scene, ground_reflection=0.0, **QUIET)
    f0 = DRONE_PROFILES[scene.drone].bpf_hz
    levels = []
    for k in range(n_dirs):
        az = 2 * np.pi * k / n_dirs
        q.trajectory = static(scene.array.center + dist * np.array([np.cos(az), np.sin(az), 0.3]) / np.linalg.norm([1, 0.3]))
        rec = render(q, 2.0, rng=rng)
        levels.append(np.mean(harmonic_level_db(rec.target, FS, f0)))
    return float(np.mean(levels) + 20 * np.log10(dist))


def random_positions(n: int, seed: int, r_lo=3.0, r_hi=40.0, el_lo=5.0, el_hi=70.0, centre=(0, 0, 1.0)):
    rng = np.random.default_rng(seed)
    r = 10 ** rng.uniform(np.log10(r_lo), np.log10(r_hi), n)
    az = rng.uniform(-np.pi, np.pi, n)
    el = np.radians(rng.uniform(el_lo, el_hi, n))
    return np.asarray(centre) + r[:, None] * np.stack([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)], 1)


def static_trial(scene: Scene, canc: ReferenceCanceller, meter: SoundMeter3D, pos, rng, frame_s=0.5):
    scene.trajectory = static(pos)
    rec = render(scene, frame_s, rng=rng)
    clean = canc.transform(rec.mics, rec.refs)
    p = DRONE_PROFILES[scene.drone]
    f0, _ = estimate_bpf(welch_psd(clean[0], N_FFT, N_FFT // 4), FS, 0.7 * p.bpf_hz, 1.35 * p.bpf_hz)
    m = meter.measure(clean, f0)
    v = np.asarray(pos) - scene.array.center
    return {"ang": float(angle_between_deg(m["direction"], v)),
            "rng_err": float(abs(m["range"] / np.linalg.norm(v) - 1)),
            "snr_in": snr_db(rec.target, rec.mics - rec.target), "snr_out": snr_db(rec.target, clean - rec.target)}


def summarise(rows: list[dict]) -> dict:
    a = [r["ang"] for r in rows]; e = [100 * r["rng_err"] for r in rows]
    return {"n": len(rows), "angle_median": bootstrap_ci(a), "angle_p90": bootstrap_ci(a, lambda x: np.percentile(x, 90)),
            "range_err_median_pct": bootstrap_ci(e)}


# ----------------------------------------------------------------------------- M1
M1_CONDITIONS = [
    ("A", "free-field simulation, lag-domain SRP (original)", dict(), "lag"),
    ("B", "free-field simulation, phase SRP with local refinement", dict(), "free"),
    ("C", "rigid-sphere simulation, free-field steering (model mismatch)", dict(scattering=True), "free"),
    ("D", "rigid-sphere simulation, rigid-sphere steering", dict(scattering=True), "sphere"),
    ("E", "D + hardware errors, common clock (1 mm, 0.5 dB, 5 us)", dict(scattering=True, pos_err_mm=1.0, gain_err_db=0.5, delay_err_us=5.0), "sphere"),
    ("F", "D + larger hardware errors, common clock (2 mm, 1 dB, 20 us)", dict(scattering=True, pos_err_mm=2.0, gain_err_db=1.0, delay_err_us=20.0), "sphere"),
    ("G", "E + 20 ppm clock skew (separate ADC clocks)", dict(scattering=True, pos_err_mm=1.0, gain_err_db=0.5, delay_err_us=5.0, clock_ppm=20.0), "sphere"),
]


def run_m1(n_pos: int = 60, seed: int = 0, out: Path = Path("outputs/revision")) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    pos = random_positions(n_pos, seed)
    res = {}
    for key, label, kw, steer in M1_CONDITIONS:
        rng = np.random.default_rng(seed + 1)
        scene = Scene(**kw)
        cal = render(scene, 8.0, drone_on=False, rng=rng)
        canc = ReferenceCanceller().fit(cal.mics, cal.refs)
        meter = SoundMeter3D(scene.array, FS, calibrate_level(scene, rng), steering=steer)
        rows = [static_trial(scene, canc, meter, p, rng) for p in pos]
        res[key] = {"label": label, **summarise(rows), "rows": rows}
        s = res[key]
        print(f"  M1-{key} {label}: angle median {s['angle_median'][0]:.2f} deg "
              f"[{s['angle_median'][1]:.2f}, {s['angle_median'][2]:.2f}], p90 {s['angle_p90'][0]:.2f}, "
              f"range err {s['range_err_median_pct'][0]:.0f}%", flush=True)
    (out / "m1.json").write_text(json.dumps(res, indent=1))
    return res


# ----------------------------------------------------------------------------- M4
M4_SCENARIOS = [
    ("baseline", "stationary machinery, equal wind", dict()),
    ("ref_wind", "strong wind on the reference microphone (+20 dB)", dict(ref_wind_db=60.0)),
    ("moving", "moving machinery (time-varying paths, +-0.15 m)", dict(machinery_motion_m=0.15)),
    ("drift", "reference-microphone gain drift of 3 dB after calibration", dict()),  # applied at test time
]
M4_REFS = [("none", None), ("acoustic", [0]), ("vibration", [1]), ("both", [0, 1])]


M4_METHODS = [
    ("none", None, None),
    ("fixed/acoustic", "fixed", [0]),
    ("fixed/vibration", "fixed", [1]),
    ("fixed/both", "fixed", [0, 1]),
    ("adaptive/both", "adaptive", [0, 1]),
    ("recalibrated/both", "recal", [0, 1]),
]


def _shadow_tdr(canc, kind, idx, scene, pos, seed):
    """Target-to-distortion ratio with the interference present: the filter
    run on the full mixture is re-applied to the drone component alone."""
    scene.trajectory = static(pos)
    full = render(scene, 2.0, rng=np.random.default_rng(seed))
    q = dataclasses.replace(scene, **QUIET)
    q.trajectory = static(pos)
    only = render(q, 2.0, rng=np.random.default_rng(seed))   # same drone realisation
    sl = slice(FS, None)
    if kind == "adaptive":
        canc.transform(full.mics, full.refs[idx], keep_weights=True)
        tgt = canc.apply_weights(only.target, only.refs[idx])
    else:
        tgt = canc.transform(only.target, only.refs[idx])
    return float(10 * np.log10(np.sum(only.target[:, sl] ** 2) / np.sum((tgt - only.target)[:, sl] ** 2)))


def run_m4(n_pos: int = 30, seed: int = 0, out: Path = Path("outputs/revision")) -> dict:
    """Reference-sensor ablation x canceller policy under stress conditions (M4).

    Scenarios: stationary machinery; +20 dB wind on the reference microphone;
    machinery moving +-0.15 m (time-varying paths); 3 dB gain drift of the
    reference microphone after calibration. Policies: fixed least-squares
    filter, continuously adapting NLMS filter, and fixed filter re-calibrated
    on a drone-free window (as triggered by the voiceprint) after the change.
    Metrics: interference reduction, SNR and direction error at 3-30 m, and the
    target-to-distortion ratio with the drone 3 m away."""
    from .reference_subtraction import AdaptiveReferenceCanceller
    out.mkdir(parents=True, exist_ok=True)
    pos = random_positions(n_pos, seed + 7, r_lo=3, r_hi=30)
    near = np.array([2.5, 1.0, 1.2])
    res = {}
    for key, label, kw in M4_SCENARIOS:
        rng = np.random.default_rng(seed + 11)
        scene = Scene(scattering=True, **kw)
        cal = render(scene, 8.0, drone_on=False, rng=rng)
        tscene = dataclasses.replace(scene, **(dict(ref_gain_db=3.0) if key == "drift" else {}))
        recal = render(tscene, 8.0, drone_on=False, rng=rng)
        val = render(tscene, 4.0, drone_on=False, rng=rng)
        meter = SoundMeter3D(scene.array, FS, calibrate_level(scene, rng), steering="sphere")
        f0 = DRONE_PROFILES[scene.drone].bpf_hz
        res[key] = {"label": label}
        for name, kind, idx in M4_METHODS:
            if kind is None:
                canc, red = None, 0.0
            else:
                train = recal if kind == "recal" else cal
                canc = (AdaptiveReferenceCanceller() if kind == "adaptive" else ReferenceCanceller()).fit(train.mics, train.refs[idx])
                red = canc.reduction_db(val.mics, val.refs[idx])
            rr = np.random.default_rng(seed + 99)
            angs, snrs = [], []
            for p in pos:
                tscene.trajectory = static(p)
                rec = render(tscene, 1.0, rng=rr)
                clean = rec.mics if canc is None else canc.transform(rec.mics, rec.refs[idx])
                sl = slice(FS // 2, FS)
                m = meter.measure(clean[:, sl], f0)
                angs.append(float(angle_between_deg(m["direction"], p - scene.array.center)))
                snrs.append(snr_db(rec.target[:, sl], clean[:, sl] - rec.target[:, sl]))
            tdr = float("inf") if canc is None else _shadow_tdr(canc, kind, idx, tscene, scene.array.center + near, seed + 5)
            res[key][name] = {"reduction_db": float(red), "snr_out_median": float(np.median(snrs)),
                              "angle_median": bootstrap_ci(angs), "angle_p90": float(np.percentile(angs, 90)),
                              "success_5deg": [int(np.sum(np.array(angs) < 5)), len(angs)], "tdr_db_3m": tdr}
            d = res[key][name]
            print(f"  M4 {key:9s} {name:18s} red {red:5.1f} dB | SNR {d['snr_out_median']:6.1f} dB | angle {d['angle_median'][0]:6.2f} "
                  f"(p90 {d['angle_p90']:6.1f}) | <5deg {d['success_5deg'][0]:2d}/{len(angs)} | TDR@3m {tdr:5.1f} dB", flush=True)
    (out / "m4.json").write_text(json.dumps(res, indent=1))
    return res


# ----------------------------------------------------------------------------- M6
def _random_trajectory(rng, duration):
    az0 = rng.uniform(-np.pi, np.pi)
    r0 = rng.uniform(25, 45)
    start = np.array([r0 * np.cos(az0), r0 * np.sin(az0), rng.uniform(10, 25)])
    end = np.array([rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(2.5, 4)])
    return homing_trajectory(duration, start=start, end=end, spiral_radius=rng.uniform(0, 8), turns=rng.uniform(0.5, 2))


def run_m6(n_runs: int = 30, duration: float = 30.0, seed: int = 0, out: Path = Path("outputs/revision"),
           vp=None, sensor_aug: bool = True, tag: str = "m6") -> dict:
    """Monte Carlo of the full passive pipeline over seeds, trajectories, interference level and wind."""
    out.mkdir(parents=True, exist_ok=True)
    from .voiceprint import VoiceprintModel
    vp = vp or VoiceprintModel.train("hexa_swap", n_per_class=80, seed=seed, verbose=False,
                                     **(dict(rpm_range=0.30, sensor_aug=True) if sensor_aug else {}))
    runs = []
    for k in range(n_runs):
        rng = np.random.default_rng(seed + 1000 + k)
        mach_db = rng.uniform(68, 80); wind_db = rng.uniform(35, 50)
        scene = Scene(scattering=True, machinery_level_db=mach_db, wind_level_db=wind_db,
                      pos_err_mm=1.0, gain_err_db=0.5, delay_err_us=5.0, calibration_seed=seed + k)
        cal = render(scene, 8.0, drone_on=False, rng=rng)
        canc = ReferenceCanceller().fit(cal.mics, cal.refs)
        meter = SoundMeter3D(scene.array, FS, calibrate_level(scene, rng), steering="sphere")
        scene.trajectory = _random_trajectory(rng, duration)
        rec = render(scene, duration, rng=rng)
        clean = canc.transform(rec.mics, rec.refs)
        frame, hop = FS // 2, FS // 4
        kf = Kalman3D(hop / FS); misses = 0
        angs, rerr, trk, det = [], [], [], []
        c = scene.array.center
        for end in range(FS, rec.mics.shape[1] + 1, hop):
            truth = rec.positions[end - frame // 2]
            ana = vp.analyse(clean[0, end - FS:end])
            kf.predict()
            ok = ana["is_target"]
            det.append(ok)
            if ok:
                m = meter.measure(clean[:, end - frame:end], ana["bpf_hz"])
                v = truth - c
                angs.append(float(angle_between_deg(m["direction"], v)))
                rerr.append(float(abs(m["range"] / np.linalg.norm(v) - 1)))
                acc = kf.update(m["position"], c)
                misses = 0 if acc else misses + 1
                if misses >= 8:
                    kf.x = None; kf.update(m["position"], c); misses = 0
            if kf.position is not None:
                trk.append(float(np.linalg.norm(kf.position - truth)))
        r = {"run": k, "machinery_db": mach_db, "wind_db": wind_db,
             "snr_in": snr_db(rec.target, rec.mics - rec.target), "snr_out": snr_db(rec.target, clean - rec.target),
             "detection": float(np.mean(det)), "angle_median": float(np.median(angs)) if angs else float("nan"),
             "angle_p90": float(np.percentile(angs, 90)) if angs else float("nan"),
             "range_err_median": float(np.median(rerr)) if rerr else float("nan"),
             "track_median": float(np.median(trk)) if trk else float("nan"),
             "track_final": trk[-1] if trk else float("nan")}
        runs.append(r)
        print(f"  M6 run {k:2d}: mach {mach_db:4.1f} dB wind {wind_db:4.1f} dB | SNR {r['snr_in']:6.1f}->{r['snr_out']:5.1f} | "
              f"det {100*r['detection']:3.0f}% | angle {r['angle_median']:5.2f} (p90 {r['angle_p90']:5.2f}) | "
              f"range {100*r['range_err_median']:4.0f}% | track {r['track_median']:5.2f} m", flush=True)
    keys = ["snr_in", "snr_out", "detection", "angle_median", "angle_p90", "range_err_median", "track_median", "track_final"]
    summary = {k: bootstrap_ci([r[k] for r in runs]) for k in keys}
    res = {"runs": runs, "summary": summary, "n_runs": n_runs}
    (out / f"{tag}.json").write_text(json.dumps(res, indent=1))
    return res
