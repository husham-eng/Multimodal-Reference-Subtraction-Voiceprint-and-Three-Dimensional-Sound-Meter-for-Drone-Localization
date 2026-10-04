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

    def cross_spectra(self, frame: np.ndarray, f0: float | None, band: tuple | None = None) -> np.ndarray:
        X = stft(frame, self.n_fft, self.hop)
        i, j = self.pairs.T
        G = np.mean(X[i] * X[j].conj(), axis=-1)
        if band is not None:
            w = ((self.freqs >= band[0]) & (self.freqs <= band[1])).astype(float)
        else:
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


def _local_cap(u: np.ndarray, max_deg: float, n: int = 400) -> np.ndarray:
    """Quasi-uniform directions inside a spherical cap around u."""
    from .dsp import fibonacci_sphere
    pts = fibonacci_sphere(int(n * 2 / (1 - np.cos(np.radians(max_deg)))))
    pts = pts[pts[:, 2] >= np.cos(np.radians(max_deg))]          # cap around +z
    z = np.array([0, 0, 1.0])
    v = np.cross(z, u); s_, c_ = np.linalg.norm(v), z @ u
    if s_ < 1e-9:
        return pts if c_ > 0 else -pts
    k = v / s_
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    Rm = np.eye(3) + s_ * K + (1 - c_) * K @ K                    # rotation z -> u
    return pts @ Rm.T


class PhaseSRP:
    """Frequency-domain SRP-PHAT with free-field or rigid-sphere steering.

    SRP(u) = sum_{i<j} sum_f W(f) Re{ G_ij(f)/|G_ij(f)| * conj(Phi_i(f,u)) Phi_j(f,u) }
    where Phi_m is the unit-modulus phase of the microphone's response to a
    plane wave from u (free field: exp(j 2 pi f p_m.u / c); sphere: rigid-sphere
    Rayleigh series). A coarse grid is refined on a fine local cap, so the
    result is not limited by the grid spacing.
    """

    def __init__(self, gcc: GccPhat, model: str = "free", n_dirs: int = 3000,
                 min_elevation_deg: float = -30.0, refine_deg: float = 8.0,
                 fmin: float = 0.0, fmax: float = F_MAX):
        self.gcc, self.model, self.refine_deg = gcc, model, refine_deg
        self.fmask = (gcc.freqs > fmin) & (gcc.freqs <= fmax)
        self.f = gcc.freqs[self.fmask]
        self.dirs = fibonacci_sphere(n_dirs, min_elevation_deg)
        self.phi = self._phases(self.dirs)
        if model == "sphere":
            from .sphere import rigid_sphere_response
            self._cos_grid = np.linspace(-1, 1, 721)
            self._table = rigid_sphere_response(self.f, self._radius(), self._cos_grid)

    def _radius(self) -> float:
        return float(np.linalg.norm(self.gcc.array.positions, axis=1).mean())

    def _phases(self, dirs: np.ndarray) -> np.ndarray:
        pos = self.gcc.array.positions
        if self.model == "free":
            ph = np.exp(2j * np.pi * self.f[None, None, :] * (pos @ dirs.T)[..., None] / SPEED_OF_SOUND)
            return ph.astype(np.complex64)
        from .sphere import rigid_sphere_response
        normals = pos / np.linalg.norm(pos, axis=1, keepdims=True)
        cos = np.clip(normals @ dirs.T, -1, 1)
        H = rigid_sphere_response(self.f, self._radius(), cos.ravel()).reshape(cos.shape + (self.f.size,))
        return (H / np.abs(H)).astype(np.complex64)

    def _power(self, Gw: np.ndarray, phi: np.ndarray) -> np.ndarray:
        out = np.zeros(phi.shape[1])
        for p, (i, j) in enumerate(self.gcc.pairs):
            out += np.real(np.einsum("f,df,df->d", Gw[p], np.conj(phi[i]), phi[j]))
        return out

    def locate(self, G: np.ndarray, prior: np.ndarray | None = None,
               prior_deg: float = 180.0) -> tuple[np.ndarray, float]:
        """G: PHAT-weighted (and comb-weighted) cross-spectra from GccPhat.cross_spectra.

        With ``prior`` (a unit vector, e.g. the intensity estimate) the peak is
        searched only within ``prior_deg`` of it, which removes the spurious
        far-away peaks that dominate SRP outliers at low SNR."""
        Gw = G[:, self.fmask].astype(np.complex64)
        p = self._power(Gw, self.phi)
        if prior is not None:
            p = np.where(self.dirs @ prior >= np.cos(np.radians(prior_deg)), p, -np.inf)
        b = int(np.argmax(p))
        cap = _local_cap(self.dirs[b], self.refine_deg)
        pc = self._power(Gw, self._phases(cap))
        k = int(np.argmax(pc))
        return cap[k], float(pc[k] / len(G))


class SoundMeter3D:
    """Direction (SRP-PHAT) + range (level drop vs. the voiceprint's 1 m level).

    ``steering`` selects the direction model: "lag" (time-domain GCC lookup,
    free field), "free" (frequency-domain, free field) or "sphere" (rigid-sphere
    diffraction model of the 160 mm sensor).
    """

    def __init__(self, array: MicArray, fs: int, level_1m_db: float, steering: str = "lag", **gcc_kw):
        self.gcc = GccPhat(array, fs, **gcc_kw)
        self.steering = steering
        self.srp = SRPPHAT(self.gcc) if steering == "lag" else PhaseSRP(self.gcc, steering)
        self.fs, self.level_1m_db = fs, level_1m_db

    def measure(self, frame: np.ndarray, f0: float | None) -> dict:
        G = self.gcc.cross_spectra(frame, f0)
        cc = self.gcc.correlations(G)
        u, peak = self.srp.locate(cc) if self.steering == "lag" else self.srp.locate(G)
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
