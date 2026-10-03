"""3D sound meter: direction from GCC-PHAT / SRP-PHAT, range from calibrated level.

Both estimators are *voiceprint-guided*: the PHAT-weighted cross-spectra and
the level are computed only on a comb around the drone's blade-passing
harmonics, so residual interference and wind outside the comb are ignored.

* ``SoundMeter3D``    - model-based: SRP-PHAT direction + range from the drop
                        of the harmonic-band level relative to its 1 m value.
* ``NeuralLocalizer`` - learned: an MLP trained in simulation that maps GCC-PHAT
                        lag features and band levels to direction and range.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import median_filter
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .dsp import P_REF, SPEED_OF_SOUND, fibonacci_sphere, harmonic_weights, stft, welch_psd
from .simulation import MicArray

F_MAX = 4000.0


def harmonic_level_db(x: np.ndarray, fs: int, f0: float | None, n_fft: int = 4096) -> np.ndarray:
    """SPL [dB] of the harmonic comb of ``f0`` (noise floor removed), per channel."""
    psd = welch_psd(x, n_fft, n_fft // 4)
    freqs = np.fft.rfftfreq(n_fft, 1 / fs)
    floor = median_filter(psd, size=(1,) * (psd.ndim - 1) + (41,), mode="nearest")
    w = harmonic_weights(freqs, f0, min(F_MAX, fs / 2), rel_bw=0.02, min_bw=4)
    p = np.sum(w * np.clip(psd - floor, 0, None), axis=-1)
    return 10 * np.log10(np.maximum(p, 1e-20) / P_REF ** 2)


class GccPhat:
    """Voiceprint-weighted GCC-PHAT for all microphone pairs."""

    def __init__(self, array: MicArray, fs: int, n_fft: int = 1024, hop: int = 256, interp: int = 8):
        self.array, self.fs, self.n_fft, self.hop, self.interp = array, fs, n_fft, hop, interp
        self.freqs = np.fft.rfftfreq(n_fft, 1 / fs)
        self.pairs = np.array(array.pairs)
        self.N = n_fft * interp
        self.max_lag = int(np.ceil(array.max_tdoa * fs * interp)) + 2

    def cross_spectra(self, frame: np.ndarray, f0: float | None) -> np.ndarray:
        X = stft(frame, self.n_fft, self.hop)
        i, j = self.pairs.T
        G = np.mean(X[i] * X[j].conj(), axis=-1)
        w = harmonic_weights(self.freqs, f0, min(F_MAX, self.fs / 2))
        return G / (np.abs(G) + 1e-30) * w

    def correlations(self, G: np.ndarray) -> np.ndarray:
        """Circular cross-correlations, shape (P, N) with lag resolution 1/(fs*interp)."""
        return np.fft.irfft(G, n=self.N, axis=-1)

    def lag_window(self, cc: np.ndarray) -> np.ndarray:
        k = self.max_lag
        return np.concatenate([cc[:, -k:], cc[:, :k + 1]], axis=1)

    def tdoas(self, cc: np.ndarray) -> np.ndarray:
        """Peak lag of each pair [s] (classic GCC-PHAT TDOA)."""
        win = self.lag_window(cc)
        return (np.argmax(win, axis=1) - self.max_lag) / (self.fs * self.interp)


class SRPPHAT:
    """Steered response power over a grid of 3D directions."""

    def __init__(self, gcc: GccPhat, n_dirs: int = 12000, min_elevation_deg: float = -30.0):
        self.gcc = gcc
        self.dirs = fibonacci_sphere(n_dirs, min_elevation_deg)
        pos = gcc.array.positions
        i, j = gcc.pairs.T
        tau = (pos[j] - pos[i]) @ self.dirs.T / SPEED_OF_SOUND        # (P, D)
        self.idx = (tau * gcc.fs * gcc.interp) % gcc.N

    def power(self, cc: np.ndarray) -> np.ndarray:
        i0 = np.floor(self.idx).astype(int)
        frac = self.idx - i0
        i1 = (i0 + 1) % self.gcc.N
        rows = np.arange(cc.shape[0])[:, None]
        return np.sum(cc[rows, i0] * (1 - frac) + cc[rows, i1] * frac, axis=0)

    def locate(self, cc: np.ndarray) -> tuple[np.ndarray, float]:
        p = self.power(cc)
        b = int(np.argmax(p))
        near = self.dirs @ self.dirs[b] > np.cos(np.radians(6))
        w = np.clip(p[near] - np.percentile(p, 90), 0, None) + 1e-12
        u = (self.dirs[near] * w[:, None]).sum(0)
        return u / np.linalg.norm(u), float(p[b] / len(cc))


class SoundMeter3D:
    """Direction (SRP-PHAT) + range (level drop vs. the voiceprint's 1 m level)."""

    def __init__(self, array: MicArray, fs: int, level_1m_db: float, **gcc_kw):
        self.gcc = GccPhat(array, fs, **gcc_kw)
        self.srp = SRPPHAT(self.gcc)
        self.fs, self.level_1m_db = fs, level_1m_db

    def measure(self, frame: np.ndarray, f0: float | None) -> dict:
        G = self.gcc.cross_spectra(frame, f0)
        cc = self.gcc.correlations(G)
        u, peak = self.srp.locate(cc)
        level = float(np.mean(harmonic_level_db(frame, self.fs, f0)))
        r = 10 ** ((self.level_1m_db - level) / 20)
        return {"direction": u, "range": r, "position": self.gcc.array.center + u * r,
                "level_db": level, "srp_peak": peak, "tdoa": self.gcc.tdoas(cc)}


class NeuralLocalizer:
    """MLP: [GCC-PHAT lag windows, band levels] -> [unit direction, log10 range]."""

    def __init__(self, array: MicArray, fs: int, level_1m_db: float, interp: int = 4, **gcc_kw):
        self.gcc = GccPhat(array, fs, interp=interp, **gcc_kw)
        self.fs, self.level_1m_db = fs, level_1m_db
        self.model = make_pipeline(StandardScaler(), MLPRegressor(
            hidden_layer_sizes=(256, 128), alpha=1e-3, learning_rate_init=1e-3, max_iter=400,
            early_stopping=True, n_iter_no_change=20, random_state=0))

    def features(self, frame: np.ndarray, f0: float | None) -> np.ndarray:
        cc = self.gcc.lag_window(self.gcc.correlations(self.gcc.cross_spectra(frame, f0)))
        cc = cc / (np.abs(cc).max(axis=1, keepdims=True) + 1e-12)
        lv = harmonic_level_db(frame, self.fs, f0)
        return np.concatenate([cc.ravel(), lv - lv.mean(), [lv.mean() - self.level_1m_db]])

    def fit(self, X: np.ndarray, positions: np.ndarray) -> "NeuralLocalizer":
        v = positions - self.gcc.array.center
        r = np.linalg.norm(v, axis=1)
        Y = np.column_stack([v / r[:, None], np.log10(r)])
        self.model.fit(X, Y)
        return self

    def predict(self, feats: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        out = self.model.predict(np.atleast_2d(feats))
        u = out[:, :3] / np.linalg.norm(out[:, :3], axis=1, keepdims=True)
        return u, 10 ** out[:, 3]
