"""Voiceprint evaluation without leakage (experiment M5).

Synthetic data are generated as *recordings* (continuous realisations with
their own unit, RPM, background and SNR) cut into 1 s segments, so that the
split can be made by recording instead of by segment. Real DroneAudioDataset
clips are grouped by recording session and by campaign.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .catalog import DRONE_PROFILES
from .dsp import rms
from .stats import wilson
from .synth import synthesize_drone
from .voiceprint import BACKGROUND, _background, features

FS = 16000


def make_recordings(drones, n_rec=10, rec_s=12, units=range(4), rpm_range=0.12, seed=0, unit_override=None):
    """Return X, y, groups (recording id), unit id, rpm offset per segment."""
    rng = np.random.default_rng(seed)
    X, y, g, u, off = [], [], [], [], []
    rid = 0
    n = rec_s * FS
    for label in list(drones) + [BACKGROUND]:
        for r in range(n_rec):
            bg = _background(n, FS, rng)
            unit = unit_override if unit_override is not None else int(rng.choice(list(units)))
            o = rng.uniform(-rpm_range, rpm_range)
            if label == BACKGROUND:
                x = bg
            else:
                thr = 1 + o + 0.03 * np.sin(np.linspace(0, rng.uniform(4, 20), n))
                src = synthesize_drone(DRONE_PROFILES[label], rec_s, FS, rng, thr, unit=unit)
                snr = rng.uniform(-3, 25)
                x = src / rms(src) * rms(bg) * 10 ** (snr / 20) + bg
            for s in range(rec_s):
                X.append(features(x[s * FS:(s + 1) * FS], FS)[0]); y.append(label); g.append(rid); u.append(unit); off.append(o)
            rid += 1
    return np.array(X), np.array(y), np.array(g), np.array(u), np.array(off)


def clf():
    return make_pipeline(StandardScaler(), RandomForestClassifier(300, random_state=0, n_jobs=-1))


def cv_accuracy(X, y, groups=None, k=5, seed=0):
    """Pooled out-of-fold accuracy with Wilson CI."""
    splitter = GroupKFold(k) if groups is not None else StratifiedKFold(k, shuffle=True, random_state=seed)
    correct = 0
    for tr, te in splitter.split(X, y, groups):
        m = clf().fit(X[tr], y[tr])
        correct += int(np.sum(m.predict(X[te]) == y[te]))
    return {"acc": correct / len(y), "ci": wilson(correct, len(y)), "n": len(y)}


def run_m5(seed: int = 0, out: Path = Path("outputs/results")) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    drones = list(DRONE_PROFILES)
    res = {}

    # 1) random segment split vs split by recording (same data)
    X, y, g, u, off = make_recordings(drones, seed=seed)
    res["random_split"] = cv_accuracy(X, y)
    res["recording_split"] = cv_accuracy(X, y, g)
    print(f"  M5 random segment split   : {res['random_split']['acc']:.3f} {res['random_split']['ci']}", flush=True)
    print(f"  M5 split by recording     : {res['recording_split']['acc']:.3f} {res['recording_split']['ci']}", flush=True)

    # 2) held-out physical units: train on units 0-3, test on unit 4 (never seen)
    Xt, yt, *_ = make_recordings(drones, n_rec=6, units=[4], seed=seed + 1)
    m = clf().fit(X, y)
    k = int(np.sum(m.predict(Xt) == yt))
    res["heldout_unit"] = {"acc": k / len(yt), "ci": wilson(k, len(yt)), "n": len(yt)}
    print(f"  M5 held-out unit          : {res['heldout_unit']['acc']:.3f} {res['heldout_unit']['ci']}", flush=True)

    # 3) RPM excursions beyond the training range, with narrow (+-12%) and wide (+-30%) training
    res["rpm"] = {}
    Xw, yw, *_ = make_recordings(drones, rpm_range=0.30, seed=seed + 2)
    models = {"train_pm12": m, "train_pm30": clf().fit(Xw, yw)}
    for o in (0.0, 0.10, 0.20, 0.30):
        # synthesise unseen-unit recordings at a fixed throttle offset of +o and -o
        accs = {}
        for name, mm in models.items():
            corr = tot = 0
            for sign in (+1, -1):
                Xs, ys = _fixed_offset(drones, sign * o, seed=seed + 20 + int(o * 100) + (sign > 0))
                corr += int(np.sum(mm.predict(Xs) == ys)); tot += len(ys)
            accs[name] = {"acc": corr / tot, "ci": wilson(corr, tot), "n": tot}
        res["rpm"][f"{int(o * 100)}%"] = accs
        print(f"  M5 RPM offset +-{int(o*100):2d}%     : narrow {accs['train_pm12']['acc']:.3f}  wide {accs['train_pm30']['acc']:.3f}", flush=True)

    # 4) can individual units of the same model be told apart? (biometric sense of "voiceprint")
    Xu, yu, gu = [], [], []
    rng = np.random.default_rng(seed + 3)
    for unit in range(5):
        Xa, ya, ga, _, _ = make_recordings(["hexa_swap"], n_rec=8, units=[unit], seed=seed + 100 + unit)
        keep = ya != BACKGROUND
        Xu.append(Xa[keep]); yu += [f"unit{unit}"] * int(keep.sum()); gu.append(ga[keep] + 1000 * unit)
    Xu, yu, gu = np.vstack(Xu), np.array(yu), np.concatenate(gu)
    res["unit_identification"] = cv_accuracy(Xu, yu, gu)
    print(f"  M5 unit identification (5 hexacopter units, chance 0.20): {res['unit_identification']['acc']:.3f} "
          f"{res['unit_identification']['ci']}", flush=True)

    # 5) real recordings: Bebop vs Mambo with random, session and campaign splits
    res["real"] = run_real()
    (out / "m5.json").write_text(json.dumps(res, indent=1, default=float))
    return res


def _fixed_offset(drones, o, seed, n_rec=4):
    rng = np.random.default_rng(seed)
    X, y = [], []
    n = 6 * FS
    for label in drones:
        for _ in range(n_rec):
            bg = _background(n, FS, rng)
            thr = 1 + o + 0.03 * np.sin(np.linspace(0, rng.uniform(4, 20), n))
            src = synthesize_drone(DRONE_PROFILES[label], 6, FS, rng, thr, unit=4)
            x = src / rms(src) * rms(bg) * 10 ** (rng.uniform(-3, 25) / 20) + bg
            for s in range(6):
                X.append(features(x[s * FS:(s + 1) * FS], FS)[0]); y.append(label)
    return np.array(X), np.array(y)


def run_real(root: Path = Path("data/droneaudio/Multiclass_Drone_Audio")) -> dict:
    from .datasets import read_wav
    files = [(p, lab) for lab, d in (("bebop", "bebop_1"), ("mambo", "membo_1")) for p in sorted((root / d).glob("*.wav"))]
    if not files:
        print("  M5 real: DroneAudioDataset not found, skipped", flush=True)
        return {}
    X, y, sess, camp = [], [], [], []
    for p, lab in files:
        x = read_wav(p, FS)
        X.append(features(x, FS)[0]); y.append(lab)
        s = p.name.split("-")[0]
        if s.startswith("extra_"):
            s = "extra_membo_D2"
        sess.append(s)
        camp.append(s.rstrip("0123456789").rstrip("_"))
    X, y = np.array(X), np.array(y)
    sess_id = np.unique(sess, return_inverse=True)[1]
    camp_names, camp_id = np.unique(camp, return_inverse=True)
    out = {"n_files": len(y), "n_sessions": int(sess_id.max() + 1), "campaigns": list(map(str, camp_names)),
           "random_split": cv_accuracy(X, y), "session_split": cv_accuracy(X, y, sess_id)}
    # leave-one-campaign-out is only meaningful when both classes remain in training
    correct = total = 0
    for c in range(len(camp_names)):
        te = camp_id == c
        if len(np.unique(y[~te])) < 2:
            continue
        mm = clf().fit(X[~te], y[~te])
        correct += int(np.sum(mm.predict(X[te]) == y[te])); total += int(te.sum())
    out["campaign_split"] = {"acc": correct / total, "ci": wilson(correct, total), "n": total}
    for k in ("random_split", "session_split", "campaign_split"):
        print(f"  M5 real Bebop vs Mambo, {k:15s}: {out[k]['acc']:.3f} {out[k]['ci']}", flush=True)
    return out
