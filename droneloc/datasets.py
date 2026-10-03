"""Download public datasets and serve drone source signals (real or synthetic)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import butter, resample_poly, sosfiltfilt

from .catalog import DATASETS, DRONE_PROFILES
from .dsp import db_to_pa, rms
from .synth import synthesize_drone

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def download(key: str, dest: Path = DATA_DIR) -> Path:
    """Sparse, shallow git clone of an auto-downloadable dataset."""
    info = DATASETS[key]
    if not info.auto_download:
        raise SystemExit(f"'{key}' must be downloaded manually from {info.url} into {dest / key}")
    target = dest / key
    if target.exists():
        print(f"{target} already exists")
        return target
    dest.mkdir(parents=True, exist_ok=True)
    run = lambda *a, **kw: subprocess.run(a, check=True, **kw)  # noqa: E731
    run("git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", info.git_url, str(target))
    run("git", "-C", str(target), "sparse-checkout", "set", *info.sparse_paths)
    print(f"downloaded {info.name} -> {target}")
    return target


def read_wav(path: Path, fs: int) -> np.ndarray:
    import soundfile as sf

    x, sr = sf.read(str(path), always_2d=True)
    x = x.mean(axis=1)
    if sr != fs:
        g = np.gcd(int(sr), int(fs))
        x = resample_poly(x, fs // g, int(sr) // g)
    return x


def find_clips(key: str, drone: str, root: Path = DATA_DIR) -> list[Path]:
    """WAV files of a dataset whose folder name maps to the requested profile key."""
    info = DATASETS[key]
    folder = root / key
    if not folder.exists():
        return []
    words = [w for w, p in info.drones.items() if p == drone] or [drone]
    return sorted(p for p in folder.rglob("*.wav")
                  if any(w in part.lower() for part in p.parent.parts[-2:] for w in words))


class SourceBank:
    """Supplies 1 m reference signals of a drone, from recordings when available."""

    def __init__(self, fs: int = 16000, dataset: str | None = None, root: Path = DATA_DIR):
        self.fs, self.dataset, self.root = fs, dataset, root
        self._cache: dict[str, np.ndarray] = {}

    def recorded(self, drone: str) -> np.ndarray | None:
        if self.dataset is None:
            return None
        if drone not in self._cache:
            clips = find_clips(self.dataset, drone, self.root)
            if not clips:
                return None
            x = np.concatenate([read_wav(p, self.fs) for p in clips])
            # remove handling / wind rumble below the rotor band
            x = sosfiltfilt(butter(4, 80 / (self.fs / 2), "high", output="sos"), x)
            self._cache[drone] = x / max(rms(x), 1e-12)
        return self._cache[drone]

    def get(self, drone: str, duration: float, rng: np.random.Generator,
            throttle: np.ndarray | None = None) -> np.ndarray:
        profile = DRONE_PROFILES[drone]
        rec = self.recorded(drone)
        if rec is None:
            return synthesize_drone(profile, duration, self.fs, rng, throttle)
        n = int(round(duration * self.fs))
        reps = int(np.ceil(n / rec.size)) + 1
        start = rng.integers(0, rec.size)
        x = np.tile(rec, reps)[start:start + n]
        # recordings are uncalibrated: assume the profile's 1 m level
        return x * db_to_pa(profile.level_1m_db) / max(rms(x), 1e-12)
