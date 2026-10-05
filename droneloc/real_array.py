"""Evaluate the direction estimators on real multichannel recordings.

Works with any array: DREGON / SP Cup 2019 recordings (8-mic cube on a
quadrotor), or recordings made with the physical 160 mm sphere.

Inputs
------
--wav        multichannel WAV (array channels first, optional reference channels after them)
--geometry   CSV with one row per array microphone: x,y,z in metres (array frame)
--truth      CSV with columns t_start,t_end,azimuth_deg,elevation_deg[,range_m]
             (directions in the array frame; one row per segment to evaluate)
--refs       indices of reference channels (e.g. "6,7"), optional
--cal        "t0,t1" seconds of a target-free part of the recording used to train
             the reference canceller (required with --refs)
--band       "lo,hi" Hz for a beacon / broadband source, or
--bpf        "lo,hi" Hz search range for a rotor blade-passing frequency (harmonic comb)
--steering   free | sphere (sphere requires the octahedral 160 mm sensor)

Example (own sensor, loudspeaker bench test):
    python -m droneloc evaluate-array --wav bench.wav --geometry sphere160.csv \
        --truth bench_truth.csv --band 3000,6000 --steering sphere

Example (DREGON, after converting its ground truth to the CSV format above):
    python -m droneloc evaluate-array --wav dregon_flight.wav --geometry dregon_mics.csv \
        --truth dregon_truth.csv --band 300,4000 --steering free
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

from .dsp import angle_between_deg, welch_psd
from .localization import GccPhat, PhaseSRP
from .reference_subtraction import ReferenceCanceller
from .simulation import MicArray
from .stats import bootstrap_ci, wilson
from .voiceprint import estimate_bpf


def load_geometry(path: Path) -> np.ndarray:
    rows = [r for r in csv.reader(open(path)) if r and not r[0].startswith("#")]
    if not rows[0][0].replace(".", "", 1).replace("-", "", 1).replace("e", "", 1).isdigit():
        rows = rows[1:]  # header
    return np.array([[float(v) for v in r[:3]] for r in rows])


def load_truth(path: Path) -> list[dict]:
    with open(path) as f:
        return [{k: float(v) for k, v in r.items() if v not in ("", None)} for r in csv.DictReader(f)]


def unit(az_deg: float, el_deg: float) -> np.ndarray:
    a, e = np.radians(az_deg), np.radians(el_deg)
    return np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])


def evaluate(wav: Path, geometry: Path, truth: Path, refs: list[int] | None = None, cal: tuple | None = None,
             band: tuple | None = None, bpf: tuple | None = None, steering: str = "free", fs_proc: int = 16000,
             out_csv: Path | None = None) -> dict:
    import soundfile as sf

    x, fs = sf.read(str(wav), always_2d=True)
    x = x.T
    if fs != fs_proc:
        g = np.gcd(int(fs), fs_proc)
        x = resample_poly(x, fs_proc // g, int(fs) // g, axis=1)
    pos = load_geometry(geometry)
    M = len(pos)
    mics, ref_sig = x[:M], (x[refs] if refs else None)
    centre = pos.mean(0)
    arr = MicArray(pos - centre, centre)
    if refs:
        if not cal:
            raise SystemExit("--cal t0,t1 (a target-free segment) is required with --refs")
        a, b = int(cal[0] * fs_proc), int(cal[1] * fs_proc)
        canc = ReferenceCanceller().fit(mics[:, a:b], ref_sig[:, a:b])
        mics = canc.transform(mics, ref_sig)
    fmax = band[1] if band else 4000.0
    fmin = band[0] if band else 0.0
    gcc = GccPhat(arr, fs_proc, n_fft=1024, hop=256)
    srp = PhaseSRP(gcc, steering, n_dirs=4000, min_elevation_deg=-90, fmin=fmin, fmax=fmax)
    rows = []
    for seg in load_truth(truth):
        a, b = int(seg["t_start"] * fs_proc), int(seg["t_end"] * fs_proc)
        frame = mics[:, a:b]
        f0 = None
        if bpf:
            f0, _ = estimate_bpf(welch_psd(frame[0], 4096, 1024), fs_proc, *bpf)
        G = gcc.cross_spectra(frame, f0, band=band if not bpf else None)
        u, _ = srp.locate(G)
        truth_u = unit(seg["azimuth_deg"], seg["elevation_deg"])
        err = float(angle_between_deg(u, truth_u))
        az = float(np.degrees(np.arctan2(u[1], u[0]))); el = float(np.degrees(np.arcsin(np.clip(u[2], -1, 1))))
        rows.append({**seg, "est_azimuth_deg": az, "est_elevation_deg": el, "error_deg": err, "bpf_hz": f0 or ""})
    errs = [r["error_deg"] for r in rows]
    summary = {"segments": len(rows), "median_error": bootstrap_ci(errs),
               "within_10deg": wilson(int(np.sum(np.array(errs) <= 10)), len(errs)),
               "frac_within_10deg": float(np.mean(np.array(errs) <= 10))}
    if out_csv:
        with open(out_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader(); w.writerows(rows)
    print(f"segments: {len(rows)} | median error {summary['median_error'][0]:.2f} deg "
          f"[{summary['median_error'][1]:.2f}, {summary['median_error'][2]:.2f}] | "
          f"within 10 deg: {100 * summary['frac_within_10deg']:.0f}%")
    return {**summary, "rows": rows}


def write_sphere_geometry(path: Path, radius: float = 0.08) -> None:
    """Geometry file of the octahedral sensor in the channel order +x,-x,+y,-y,+z,-z."""
    pos = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]]) * radius
    with open(path, "w") as f:
        f.write("x,y,z\n")
        for p in pos:
            f.write(f"{p[0]:.4f},{p[1]:.4f},{p[2]:.4f}\n")


def multiple_coherence(wav: Path, array_ch: list[int], ref_ch: list[int], band: tuple = (3000, 6000),
                       n_fft: int = 2048) -> dict:
    """How much of the array noise is predictable from the reference sensors.

    For each array channel m and frequency f the multiple coherence
    gamma^2 = r_yx R_xx^-1 r_xy / S_yy gives the best possible cancellation by
    *any* linear reference canceller: -10 log10(1 - gamma^2) dB. Record the
    drone with motors running (no beacon) and run this to decide whether
    silence windows are needed (low coherence) or reference cancellation is
    enough (high coherence)."""
    import soundfile as sf
    from .dsp import stft

    x, fs = sf.read(str(wav), always_2d=True)
    x = x.T
    Y = stft(x[array_ch], n_fft, n_fft // 4)
    X = stft(x[ref_ch], n_fft, n_fft // 4)
    f = np.fft.rfftfreq(n_fft, 1 / fs)
    sel = (f >= band[0]) & (f <= band[1])
    Y, X = Y[:, sel], X[:, sel]
    Rxx = np.einsum("rft,sft->frs", X, X.conj())
    Ryx = np.einsum("mft,sft->fms", Y, X.conj())
    Syy = np.einsum("mft,mft->fm", Y, Y.conj()).real
    R = len(ref_ch)
    Rinv = np.linalg.inv(Rxx + 1e-9 * np.trace(Rxx, axis1=1, axis2=2)[:, None, None] * np.eye(R))
    pred = np.einsum("fmr,frs,fms->fm", Ryx, Rinv, Ryx.conj()).real
    g2 = np.clip(pred / np.maximum(Syy, 1e-30), 0, 0.9999)
    total = float(10 * np.log10(np.sum(Syy) / np.sum(Syy - pred)))
    res = {"band": band, "mean_coherence": float(g2.mean()), "max_cancellation_db_in_band": total,
           "per_channel_db": [float(10 * np.log10(np.sum(Syy[:, m]) / np.sum(Syy[:, m] - pred[:, m]))) for m in range(len(array_ch))]}
    print(f"multiple coherence in {band[0]:.0f}-{band[1]:.0f} Hz: mean {res['mean_coherence']:.2f} | "
          f"best possible ego-noise cancellation {total:.1f} dB")
    return res
