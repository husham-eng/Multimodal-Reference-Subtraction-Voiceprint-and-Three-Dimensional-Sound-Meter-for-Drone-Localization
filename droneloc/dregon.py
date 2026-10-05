"""Run the direction estimator on the DREGON recordings in one command.

    python -m droneloc dregon --data path/to/DREGON --out outputs/dregon

The folder may hold any number of unzipped DREGON recordings (best: each in its own
sub-folder, as the zip files unpack). For every 8-channel WAV the command looks, in
the same folder, for the two MATLAB files of that recording: one holding ``audio_timestamps`` (one entry per audio sample) and one
holding the struct ``source_position`` (timestamps, azimuth, elevation, distance
of the loudspeaker in the UAV frame, from the Vicon system). It then

1. writes the array geometry (micPos of the DREGON cube, in metres),
2. cuts the recording into segments and interpolates the true direction at the
   centre of each segment,
3. runs the same SRP-PHAT estimator as the paper (free-field steering, since the
   DREGON microphones are not on a sphere), and
4. writes per-segment results, a per-recording summary and ``dregon_summary.json``.

Recordings without ``source_position`` (motors only) are listed and skipped.
Nothing is tuned on the data: the band is fixed by the source type in the file
name (speech 300-4000 Hz, broadband sources 300-7000 Hz) unless --band is given.

The frame-convention check at the end only reports how the median error would
change under other azimuth/elevation conventions (sign or 90 deg offsets); it
never alters the reported result. A large improvement under another convention
means the geometry and ground truth are expressed in different frames, which
must be resolved from the dataset documentation before the numbers are used.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from .real_array import evaluate, unit
from .stats import bootstrap_ci, wilson

# DREGON / SP Cup 2019 microphone positions [m], array frame centred on the cube
# (Chutlhu/SPCUP19, plot_structure.m; channel order 0-7 as in the WAV files).
DREGON_MICS = np.array([
    [0.0420, 0.0615, -0.0410],
    [-0.0420, 0.0615, 0.0410],
    [-0.0615, 0.0420, -0.0410],
    [-0.0615, -0.0420, 0.0410],
    [-0.0420, -0.0615, -0.0410],
    [0.0420, -0.0615, 0.0410],
    [0.0615, -0.0420, -0.0410],
    [0.0615, 0.0420, 0.0410],
])


def _load_mat(path: Path) -> dict:
    """Load a .mat file (v5 via scipy, v7.3/HDF5 via h5py) into plain numpy arrays."""
    try:
        from scipy.io import loadmat
        m = loadmat(str(path), squeeze_me=True, struct_as_record=False)
        out = {}
        for k, v in m.items():
            if k.startswith("__"):
                continue
            if hasattr(v, "_fieldnames"):
                out[k] = {f: np.atleast_1d(np.asarray(getattr(v, f), float)) for f in v._fieldnames}
            else:
                out[k] = np.atleast_1d(np.asarray(v))
        return out
    except NotImplementedError:  # MATLAB v7.3
        import h5py
        out = {}
        with h5py.File(path, "r") as f:
            for k, v in f.items():
                if isinstance(v, h5py.Group):
                    out[k] = {kk: np.asarray(vv).ravel().astype(float) for kk, vv in v.items()}
                else:
                    out[k] = np.asarray(v).ravel()
        return out


def _mats_for(wav: Path) -> list[Path]:
    """The .mat files belonging to a WAV: all of them if the WAV is alone in its folder,
    otherwise only those whose name starts with the WAV name (or vice versa)."""
    mats = sorted(wav.parent.glob("*.mat"))
    if len(list(wav.parent.glob("*.wav"))) == 1:
        return mats
    s = wav.stem.lower()
    return [p for p in mats if p.stem.lower().startswith(s) or s.startswith(p.stem.lower())]


def _find(wav: Path, key: str) -> dict | np.ndarray | None:
    """First .mat file of this recording that contains `key`."""
    for p in _mats_for(wav):
        try:
            m = _load_mat(p)
        except Exception:  # noqa: BLE001 - unreadable or unrelated file
            continue
        for k, v in m.items():
            if k.lower() == key.lower():
                return v
    return None


def _to_degrees(x: np.ndarray, units: str) -> np.ndarray:
    if units == "deg" or (units == "auto" and np.nanmax(np.abs(x)) > 2 * np.pi + 0.1):
        return x
    return np.degrees(x)


def _band_for(name: str) -> tuple[float, float]:
    n = name.lower()
    if "speech" in n:
        return (300.0, 4000.0)
    return (300.0, 7000.0)


def write_geometry(path: Path) -> None:
    with open(path, "w") as f:
        f.write("x,y,z\n")
        for p in DREGON_MICS:
            f.write(f"{p[0]:.4f},{p[1]:.4f},{p[2]:.4f}\n")


def prepare_truth(wav: Path, out_csv: Path, segment: float = 0.5, units: str = "auto") -> dict | None:
    """Truth CSV (t_start,t_end,azimuth_deg,elevation_deg,range_m) for one recording, or None."""
    import soundfile as sf

    info = sf.info(str(wav))
    src = _find(wav, "source_position")
    if src is None:
        return None
    ats = _find(wav, "audio_timestamps")
    fs, n = info.samplerate, info.frames
    t_src = np.asarray(src["timestamps"], float)
    az = _to_degrees(np.asarray(src["azimuth"], float), units)
    el = _to_degrees(np.asarray(src["elevation"], float), units)
    dist = np.asarray(src.get("distance", np.full_like(t_src, np.nan)), float)
    if ats is not None and len(ats) >= n:
        t_audio = np.asarray(ats, float)[:n]
    else:  # no per-sample timestamps: assume the source track starts with the audio
        t_audio = t_src[0] + np.arange(n) / fs
    # interpolate the direction as a unit vector (avoids the +-180 deg wrap)
    U = np.array([unit(a, e) for a, e in zip(az, el)])
    ok = np.all(np.isfinite(U), axis=1)
    rows = []
    for t0 in np.arange(0.0, n / fs - segment, segment):
        tc = np.interp(t0 + segment / 2, np.arange(n) / fs, t_audio)
        if tc < t_src[ok][0] or tc > t_src[ok][-1]:
            continue
        u = np.array([np.interp(tc, t_src[ok], U[ok, i]) for i in range(3)])
        u /= np.linalg.norm(u)
        rows.append({"t_start": round(t0, 4), "t_end": round(t0 + segment, 4),
                     "azimuth_deg": float(np.degrees(np.arctan2(u[1], u[0]))),
                     "elevation_deg": float(np.degrees(np.arcsin(np.clip(u[2], -1, 1)))),
                     "range_m": float(np.interp(tc, t_src[ok], dist[ok])) if np.isfinite(dist[ok]).any() else ""})
    if not rows:
        return None
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    return {"segments": len(rows), "fs": fs, "channels": info.channels,
            "azimuth_range_raw": [float(np.nanmin(src["azimuth"])), float(np.nanmax(src["azimuth"]))],
            "elevation_range_raw": [float(np.nanmin(src["elevation"])), float(np.nanmax(src["elevation"]))],
            "audio_timestamps": ats is not None}


def _convention_check(rows: list[dict]) -> list[dict]:
    """Median error if the ground truth were in another azimuth/elevation convention (report only)."""
    est = np.array([unit(r["est_azimuth_deg"], r["est_elevation_deg"]) for r in rows])
    res = []
    for sa in (1, -1):
        for off in (0, 90, 180, 270):
            for se in (1, -1):
                tru = np.array([unit(sa * r["azimuth_deg"] + off, se * r["elevation_deg"]) for r in rows])
                err = np.degrees(np.arccos(np.clip(np.sum(est * tru, 1), -1, 1)))
                res.append({"azimuth": f"{'+' if sa > 0 else '-'}az{'+' + str(off) if off else ''}",
                            "elevation": "+el" if se > 0 else "-el", "median_error": float(np.median(err))})
    return sorted(res, key=lambda r: r["median_error"])


def run(data: Path, out: Path, segment: float = 0.5, band: tuple | None = None, units: str = "auto") -> dict:
    out.mkdir(parents=True, exist_ok=True)
    geom = out / "dregon_mics.csv"
    write_geometry(geom)
    wavs = sorted(p for p in data.rglob("*.wav"))
    if not wavs:
        raise SystemExit(f"no .wav files under {data}")
    per, skipped, all_rows = {}, [], []
    for wav in wavs:
        name = wav.stem
        truth = out / f"{name}_truth.csv"
        meta = prepare_truth(wav, truth, segment, units)
        if meta is None:
            skipped.append(name)
            print(f"skip {name}: no source_position (motors only or files missing)")
            continue
        if meta["channels"] < 8:
            skipped.append(name)
            print(f"skip {name}: {meta['channels']} channels, expected 8")
            continue
        b = band or _band_for(name)
        print(f"{name}: {meta['segments']} segments, band {b[0]:.0f}-{b[1]:.0f} Hz")
        s = evaluate(wav, geom, truth, band=b, steering="free", out_csv=out / f"{name}_result.csv")
        rows = s.pop("rows")
        all_rows += rows
        per[name] = {**meta, "band": b, **s}
    if not all_rows:
        raise SystemExit("no recording with ground truth was evaluated")
    errs = np.array([r["error_deg"] for r in all_rows])
    summary = {
        "recordings": per, "skipped": skipped, "segment_s": segment,
        "all": {"segments": len(errs), "median_error": bootstrap_ci(errs),
                "within_10deg": [int(np.sum(errs <= 10)), len(errs), *wilson(int(np.sum(errs <= 10)), len(errs))],
                "within_20deg": [int(np.sum(errs <= 20)), len(errs), *wilson(int(np.sum(errs <= 20)), len(errs))]},
        "frame_convention_check": _convention_check(all_rows)[:4],
    }
    (out / "dregon_summary.json").write_text(json.dumps(summary, indent=1, default=float))
    a = summary["all"]
    print(f"\nALL: {a['segments']} segments | median error {a['median_error'][0]:.1f} deg "
          f"[{a['median_error'][1]:.1f}, {a['median_error'][2]:.1f}] | within 10 deg "
          f"{a['within_10deg'][0]}/{a['within_10deg'][1]} | within 20 deg {a['within_20deg'][0]}/{a['within_20deg'][1]}")
    best = summary["frame_convention_check"][0]
    print(f"frame check (report only): best convention {best['azimuth']} {best['elevation']} -> "
          f"median {best['median_error']:.1f} deg")
    print(f"results written to {out}/ (send dregon_summary.json and the *_result.csv files)")
    return summary
