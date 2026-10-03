"""End-to-end experiment: train every stage and run a homing mission in simulation.

1. Voiceprint   - train a drone-type classifier (target + other drones + background)
                  and calibrate the target's 1 m harmonic level.
2. Subtraction  - train the multimodal reference canceller on a drone-free window.
3. 3D meter     - train the neural localizer on simulated static positions;
                  the SRP-PHAT + level meter needs no training beyond step 1.
4. Mission      - the drone spirals in to land; every frame is cleaned, verified
                  by the voiceprint, localized in 3D and tracked by a Kalman filter.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from .catalog import DRONE_PROFILES
from .datasets import SourceBank
from .dsp import angle_between_deg, snr_db, welch_psd
from .localization import NeuralLocalizer, SoundMeter3D
from .reference_subtraction import ReferenceCanceller
from .simulation import Scene, homing_trajectory, octahedral_array, render, static
from .tracking import Kalman3D
from .voiceprint import N_FFT, VoiceprintModel, estimate_bpf


def _train_neural(scene: Scene, canceller, vp: VoiceprintModel, n: int, rng, frame_s: float):
    loc = NeuralLocalizer(scene.array, scene.fs, vp.level_1m_db)
    X, P = [], []
    for _ in range(n):
        r = 10 ** rng.uniform(np.log10(2), np.log10(60))
        az, el = rng.uniform(-np.pi, np.pi), np.radians(rng.uniform(5, 70))
        p = scene.array.center + r * np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
        scene.trajectory = static(p)
        rec = render(scene, frame_s, rng=rng)
        clean = canceller.transform(rec.mics, rec.refs)
        f0, _ = estimate_bpf(welch_psd(clean[0], N_FFT, N_FFT // 4), scene.fs, *vp.f0_range)
        X.append(loc.features(clean, f0))
        P.append(p)
    X, P = np.array(X), np.array(P)
    cut = int(0.85 * n)
    loc.fit(X[:cut], P[:cut])
    u, rr = loc.predict(X[cut:])
    v = P[cut:] - scene.array.center
    ang = angle_between_deg(u, v)
    rel = np.abs(rr / np.linalg.norm(v, axis=1) - 1)
    print(f"  neural localizer: {cut} train / {n - cut} test frames, "
          f"median angle error {np.median(ang):.1f} deg, median range error {100 * np.median(rel):.0f} %")
    loc.fit(X, P)
    return loc


def run(drone: str = "hexa_swap", dataset: str | None = None, duration: float = 40.0,
        seed: int = 0, out_dir: str | Path = "outputs", n_voiceprint: int = 120,
        n_neural: int = 1200, plots: bool = True, array_radius: float = 0.08) -> dict:
    if drone not in DRONE_PROFILES:
        raise SystemExit(f"unknown drone '{drone}'. Choose from: {', '.join(DRONE_PROFILES)}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    fs = 16000
    bank = SourceBank(fs, dataset)
    prof = DRONE_PROFILES[drone]
    src = "recordings from '" + dataset + "'" if bank.recorded(drone) is not None else "synthetic rotor model"
    print(f"Target drone: {prof.name}  (BPF {prof.bpf_hz:.0f} Hz, source: {src})")
    t0 = time.time()

    print("[1/4] Training drone voiceprint ...")
    vp = VoiceprintModel.train(drone, n_per_class=n_voiceprint, fs=fs, seed=seed, bank=bank)
    print(f"  calibrated harmonic level at 1 m: {vp.level_1m_db:.1f} dB")

    print("[2/4] Training multimodal reference subtraction (drone-free window) ...")
    scene = Scene(array=octahedral_array(array_radius), fs=fs, drone=drone, bank=bank)
    cal = render(scene, 8.0, drone_on=False, rng=rng)
    canceller = ReferenceCanceller().fit(cal.mics, cal.refs)
    val = render(scene, 4.0, drone_on=False, rng=rng)
    red = canceller.reduction_db(val.mics, val.refs)
    red_mic = ReferenceCanceller().fit(cal.mics, cal.refs[:1]).reduction_db(val.mics, val.refs[:1])
    print(f"  interference reduction: {red:.1f} dB (acoustic reference only: {red_mic:.1f} dB)")

    print("[3/4] Training 3D sound meter (neural localizer) in simulation ...")
    neural = _train_neural(scene, canceller, vp, n_neural, rng, 0.5)
    meter = SoundMeter3D(scene.array, fs, vp.level_1m_db)

    print(f"[4/4] Homing mission ({duration:.0f} s) ...")
    scene.trajectory = homing_trajectory(duration)
    rec = render(scene, duration, rng=rng)
    clean = canceller.transform(rec.mics, rec.refs)
    snr_in = snr_db(rec.target, rec.mics - rec.target)
    snr_out = snr_db(rec.target, clean - rec.target)
    print(f"  array SNR before / after subtraction: {snr_in:.1f} / {snr_out:.1f} dB")

    frame, hop, vp_len = int(0.5 * fs), int(0.25 * fs), fs
    kf = Kalman3D(hop / fs)
    misses = 0
    rows = []
    center = scene.array.center
    for end in range(vp_len, rec.mics.shape[1] + 1, hop):
        t = end / fs
        truth = rec.positions[end - frame // 2]
        seg = slice(end - frame, end)
        ana = vp.analyse(clean[0, end - vp_len:end])
        kf.predict()
        row = {"t": t, "truth": truth.tolist(), "p_target": ana["p_target"], "bpf": ana["bpf_hz"],
               "label": ana["label"]}
        if ana["p_target"] >= 0.5:
            m = meter.measure(clean[:, seg], ana["bpf_hz"])
            raw = meter.measure(rec.mics[:, seg], ana["bpf_hz"])
            u_n, r_n = neural.predict(neural.features(clean[:, seg], ana["bpf_hz"]))
            accepted = kf.update(m["position"], center)
            misses = 0 if accepted else misses + 1
            if misses >= 8:  # lost track: restart from the current measurement
                kf.x = None
                kf.update(m["position"], center)
                misses = 0
            row.update(meter=m["position"].tolist(), raw=raw["position"].tolist(),
                       neural=(center + u_n[0] * r_n[0]).tolist())
        if kf.position is not None:
            row["track"] = kf.position.tolist()
        rows.append(row)

    report = _evaluate(rows, center, drone)
    report.update(drone=drone, dataset=dataset, array_radius_m=array_radius, interference_reduction_db=red,
                  interference_reduction_ref_mic_only_db=red_mic, snr_in_db=snr_in, snr_out_db=snr_out,
                  voiceprint_accuracy=vp.accuracy, level_1m_db=vp.level_1m_db, runtime_s=time.time() - t0)
    _print_report(report)
    vp.save(out / "models" / f"voiceprint_{drone}.pkl")
    (out / "report.json").write_text(json.dumps({**report, "frames": rows}, indent=1))
    if plots:
        from .plots import save_all
        save_all(out, rec, clean, rows, center, fs, prof)
    print(f"Results written to {out}/")
    return report


def _evaluate(rows, center, drone) -> dict:
    rep = {"frames": len(rows), "detection_rate": float(np.mean([r["p_target"] >= 0.5 for r in rows]))}
    for key in ("raw", "meter", "neural", "track"):
        sel = [r for r in rows if key in r]
        if not sel:
            continue
        est = np.array([r[key] for r in sel]) - center
        tru = np.array([r["truth"] for r in sel]) - center
        ang = angle_between_deg(est, tru)
        rng_err = np.abs(np.linalg.norm(est, axis=1) / np.linalg.norm(tru, axis=1) - 1)
        pos = np.linalg.norm(est - tru, axis=1)
        rep[key] = {"median_angle_deg": float(np.median(ang)), "median_range_err_pct": float(100 * np.median(rng_err)),
                    "median_pos_err_m": float(np.median(pos)), "p90_pos_err_m": float(np.percentile(pos, 90)),
                    "final_pos_err_m": float(pos[-1])}
    return rep


def _print_report(rep: dict) -> None:
    names = {"raw": "SRP + level, no subtraction", "meter": "3D sound meter (cleaned)",
             "neural": "neural localizer (cleaned)", "track": "Kalman track"}
    print(f"  voiceprint detection rate: {100 * rep['detection_rate']:.0f} % of frames")
    print(f"  {'method':32s} {'angle':>8s} {'range':>8s} {'pos med':>8s} {'pos p90':>8s} {'final':>7s}")
    for k, name in names.items():
        if k in rep:
            r = rep[k]
            print(f"  {name:32s} {r['median_angle_deg']:7.1f}° {r['median_range_err_pct']:7.0f}% "
                  f"{r['median_pos_err_m']:7.2f}m {r['p90_pos_err_m']:7.2f}m {r['final_pos_err_m']:6.2f}m")
