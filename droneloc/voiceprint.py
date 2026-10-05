"""Drone voiceprint: features, blade-passing-frequency tracking and a classifier.

The voiceprint of a multirotor is dominated by its blade-passing frequency
(BPF = RPM/60 x blades) and the relative strength of its harmonics, shaft
imbalance lines and motor whine. Features are level-normalised so that the
identity does not depend on distance; level is handled by the sound meter.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .catalog import DRONE_PROFILES
from .dsp import mel_filterbank, rms, welch_psd
from .synth import bird_chirps, pink_noise, station_machinery, synthesize_drone, wind_noise

BACKGROUND = "background"
N_FFT = 4096
N_HARM = 12


def estimate_bpf(psd: np.ndarray, fs: int, f_lo: float = 60, f_hi: float = 700,
                 n_harm: int = 8) -> tuple[float, float]:
    """Harmonic-sum pitch estimate. Returns (f0 [Hz], salience)."""
    freqs = np.fft.rfftfreq(2 * (psd.size - 1), 1 / fs)
    floor = np.median(psd) + 1e-30
    logp = np.log1p(psd / floor)
    cands = np.arange(f_lo, f_hi, 0.5)
    score = np.zeros_like(cands)
    for k in range(1, n_harm + 1):
        fk = cands * k
        ok = fk < freqs[-1]
        score[ok] += np.interp(fk[ok], freqs, logp) * (1 - 0.03 * k)
    i = int(np.argmax(score))
    return float(cands[i]), float(score[i] / n_harm)


def features(x: np.ndarray, fs: int, f0_range: tuple[float, float] = (60, 700)) -> tuple[np.ndarray, float]:
    """Voiceprint feature vector and the BPF estimate of a mono segment."""
    psd = welch_psd(x, N_FFT, N_FFT // 4)
    freqs = np.fft.rfftfreq(N_FFT, 1 / fs)
    total = psd.sum() + 1e-30
    p = psd / total  # level-independent spectrum
    mel = np.log10(mel_filterbank(fs, N_FFT, 40, 50, min(7000, fs / 2)) @ p + 1e-12)
    mel -= mel.mean()
    f0, sal = estimate_bpf(psd, fs, *f0_range)
    harm = np.array([np.interp(k * f0, freqs, psd) if k * f0 < fs / 2 else 0.0 for k in range(1, N_HARM + 1)])
    harm_db = 10 * np.log10(harm / (harm.max() + 1e-30) + 1e-6)
    centroid = np.sum(freqs * p)
    flat = np.exp(np.mean(np.log(psd + 1e-30))) / (np.mean(psd) + 1e-30)
    roll = freqs[np.searchsorted(np.cumsum(p), 0.85)]
    feat = np.concatenate([mel, harm_db, [np.log(f0), sal, centroid / 1000, np.log(flat + 1e-12), roll / 1000]])
    return feat, f0


def _background(n: int, fs: int, rng: np.random.Generator) -> np.ndarray:
    return (wind_noise(n, fs, rng, rng.uniform(30, 50)) + pink_noise(n, rng, rng.uniform(20, 40))
            + station_machinery(n, fs, rng, rng.uniform(40, 60)) * rng.uniform(0, 1)
            + bird_chirps(n, fs, rng, rng.uniform(25, 45), rate_hz=2))


def _sensor_colouring(x: np.ndarray, fs: int, rng, table=None):
    """Filter a segment with the rigid-sphere response of a random incidence angle,
    i.e. the spectral colouring a microphone on the 160 mm sensor applies."""
    from .sphere import rigid_sphere_response
    f = np.fft.rfftfreq(x.size, 1 / fs)
    H = rigid_sphere_response(f, 0.08, np.array([rng.uniform(-1, 1)]))[0]
    return np.fft.irfft(np.fft.rfft(x) * H, x.size)


def make_training_set(drones: list[str], n_per_class: int = 120, seg: float = 1.0, fs: int = 16000,
                      rng: np.random.Generator | None = None, bank=None, rpm_range: float = 0.12,
                      sensor_aug: bool = False):
    """Simulated 1 s segments of each drone at random SNR, plus a background class.

    ``rpm_range`` sets the throttle augmentation (+-12% originally; +-30% is
    recommended, see the RPM-excursion test) and ``sensor_aug`` passes each
    segment through the rigid-sphere response of a random direction so that the
    classifier sees the spectral colouring of the physical sensor."""
    rng = rng or np.random.default_rng(0)
    n = int(seg * fs)
    X, y = [], []
    for label in drones + [BACKGROUND]:
        for _ in range(n_per_class):
            bg = _background(n, fs, rng)
            if label == BACKGROUND:
                x = bg
            else:
                thr = 1 + rng.uniform(-rpm_range, rpm_range) + 0.03 * np.sin(np.linspace(0, rng.uniform(1, 6), n))
                src = (bank.get(label, seg, rng, thr) if bank else
                       synthesize_drone(DRONE_PROFILES[label], seg, fs, rng, thr))
                snr = rng.uniform(-3, 25)
                x = src / rms(src) * rms(bg) * 10 ** (snr / 20) + bg
            if sensor_aug:
                x = _sensor_colouring(x, fs, rng)
            X.append(features(x, fs)[0])
            y.append(label)
    return np.array(X), np.array(y)


@dataclass
class VoiceprintModel:
    target: str
    classes: list[str]
    clf: object
    fs: int
    level_1m_db: float       # harmonic-band SPL of the target at 1 m (sound-meter calibration)

    @classmethod
    def train(cls, target: str, drones: list[str] | None = None, n_per_class: int = 120,
              fs: int = 16000, seed: int = 0, bank=None, verbose: bool = True,
              rpm_range: float = 0.12, sensor_aug: bool = False) -> "VoiceprintModel":
        drones = drones or list(DRONE_PROFILES)
        if target not in drones:
            drones = drones + [target]
        rng = np.random.default_rng(seed)
        X, y = make_training_set(drones, n_per_class, fs=fs, rng=rng, bank=bank, rpm_range=rpm_range, sensor_aug=sensor_aug)
        idx = rng.permutation(len(y))
        cut = int(0.8 * len(y))
        tr, te = idx[:cut], idx[cut:]
        clf = make_pipeline(StandardScaler(), RandomForestClassifier(300, random_state=seed, n_jobs=-1))
        clf.fit(X[tr], y[tr])
        pred = clf.predict(X[te])
        acc = accuracy_score(y[te], pred)
        labels = drones + [BACKGROUND]
        if verbose:
            print(f"  voiceprint classifier: {len(labels)} classes, held-out accuracy = {acc:.3f}")
            cm = confusion_matrix(y[te], pred, labels=labels)
            w = max(len(l) for l in labels)
            for l, row in zip(labels, cm):
                print(f"    {l:>{w}s} " + " ".join(f"{v:3d}" for v in row))
        clf.fit(X, y)
        model = cls(target, labels, clf, fs, 0.0)
        model.accuracy = acc
        model.level_1m_db = model.calibrate_level(bank, rng)
        return model

    def calibrate_level(self, bank, rng) -> float:
        """Harmonic-band level of the clean target at 1 m (used by the 3D sound meter)."""
        from .localization import harmonic_level_db

        src = (bank.get(self.target, 4.0, rng) if bank else
               synthesize_drone(DRONE_PROFILES[self.target], 4.0, self.fs, rng))
        f0 = DRONE_PROFILES[self.target].bpf_hz
        return float(harmonic_level_db(src[None], self.fs, f0)[0])

    @property
    def f0_range(self) -> tuple[float, float]:
        bpf = DRONE_PROFILES[self.target].bpf_hz
        return 0.7 * bpf, 1.35 * bpf

    def analyse(self, x: np.ndarray) -> dict:
        """Identify a mono segment. Returns label, P(target), BPF estimate."""
        feat, _ = features(x, self.fs)
        prob = self.clf.predict_proba(feat[None])[0]
        classes = list(self.clf.classes_)
        f0, _ = estimate_bpf(welch_psd(x, N_FFT, N_FFT // 4), self.fs, *self.f0_range)
        label = classes[int(np.argmax(prob))]
        # decision = most probable class (MAP); a fixed 0.5 threshold on the target
        # probability rejects correct decisions when the probability mass is spread
        # over eight classes
        return {"label": label, "is_target": label == self.target,
                "p_target": float(prob[classes.index(self.target)]),
                "bpf_hz": f0}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path: Path) -> "VoiceprintModel":
        with open(path, "rb") as f:
            return pickle.load(f)
