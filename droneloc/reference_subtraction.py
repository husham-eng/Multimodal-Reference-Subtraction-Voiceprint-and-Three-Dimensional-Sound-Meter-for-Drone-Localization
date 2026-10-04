"""Multimodal reference subtraction.

Each array microphone ``y_m`` hears the drone plus interference that is also
observed (through different paths) by R reference sensors ``x_r`` - here an
acoustic reference microphone at the station machinery and a vibration sensor
on its frame. During a training window without the drone the canceller learns,
per frequency bin, the multichannel Wiener / least-squares transfer

    H(f) = R_yx(f) (R_xx(f) + lambda I)^-1          (M x R)

and later subtracts the predicted interference ``E = Y - H X``. The filter is
linear and identical across time, so the inter-microphone phase of the drone
(needed by GCC-PHAT) is preserved.
"""
from __future__ import annotations

import numpy as np

from .dsp import istft, stft


class ReferenceCanceller:
    def __init__(self, n_fft: int = 2048, hop: int = 512, reg: float = 1e-3):
        self.n_fft, self.hop, self.reg = n_fft, hop, reg
        self.H: np.ndarray | None = None

    def fit(self, mics: np.ndarray, refs: np.ndarray) -> "ReferenceCanceller":
        """Train on an interference-only recording (drone absent)."""
        Y = stft(mics, self.n_fft, self.hop)
        X = stft(refs, self.n_fft, self.hop)
        T = X.shape[-1]
        Rxx = np.einsum("rft,sft->frs", X, X.conj()) / T
        Ryx = np.einsum("mft,sft->fms", Y, X.conj()) / T
        R = Rxx.shape[-1]
        load = self.reg * np.trace(Rxx, axis1=1, axis2=2).real / R + 1e-30
        self.H = Ryx @ np.linalg.inv(Rxx + load[:, None, None] * np.eye(R))
        return self

    def transform(self, mics: np.ndarray, refs: np.ndarray) -> np.ndarray:
        if self.H is None:
            raise RuntimeError("call fit() first")
        Y = stft(mics, self.n_fft, self.hop)
        X = stft(refs, self.n_fft, self.hop)
        E = Y - np.einsum("fmr,rft->mft", self.H, X)
        return istft(E, self.n_fft, self.hop, mics.shape[-1])

    def reduction_db(self, mics: np.ndarray, refs: np.ndarray) -> float:
        """Interference power reduction on an interference-only recording."""
        out = self.transform(mics, refs)
        return float(10 * np.log10(np.sum(mics ** 2) / np.sum(out ** 2)))


class AdaptiveReferenceCanceller(ReferenceCanceller):
    """Frequency-domain multichannel NLMS canceller that keeps adapting.

    It starts from the least-squares solution learned in the calibration
    window and then tracks time-varying paths (moving machinery) and sensor
    drift. For every bin f and frame t:

        e_t = y_t - W x_t
        W  <- W + mu * e_t x_t^H / (x_t^H x_t + delta)

    Because all reference sensors are adapted jointly, a reference that becomes
    unreliable (drift, wind) is automatically down-weighted in favour of the
    others, which is where a second sensing modality pays off.
    """

    def __init__(self, n_fft: int = 1024, hop: int = 256, reg: float = 1e-3, mu: float = 0.2,
                 floor: float = 1.0, gate: float = 0.1):
        super().__init__(n_fft, hop, reg)
        self.mu, self.floor, self.gate = mu, floor, gate
        self.weights: np.ndarray | None = None
        self.cal_power: np.ndarray | None = None

    def fit(self, mics: np.ndarray, refs: np.ndarray) -> "AdaptiveReferenceCanceller":
        super().fit(mics, refs)
        X = stft(refs, self.n_fft, self.hop)
        # per-bin reference power seen during calibration: the regulariser keeps
        # the update small whenever the interference is weaker than at calibration,
        # so the filter does not start fitting the drone leaking into the reference
        self.cal_power = np.sum(np.mean(np.abs(X) ** 2, axis=2), axis=0)
        return self

    def transform(self, mics: np.ndarray, refs: np.ndarray, f0: float | None = None,
                  fs: int = 16000, keep_weights: bool = False) -> np.ndarray:
        """Cancel the interference while adapting.

        ``f0`` is the drone blade-passing frequency from the voiceprint. When it
        is given, the bins on the drone's harmonic comb are *protected*: they are
        not adapted (the drone leaks into the reference microphone and would be
        cancelled), and their filter is interpolated across frequency from the
        neighbouring adapted bins, which is valid because the acoustic transfer
        paths vary smoothly with frequency.

        Adaptation is also *gated*: a bin is updated only while its reference
        power is at least ``gate`` times the calibration power, i.e. while the
        references are dominated by the interference they were installed to
        observe rather than by drone sound leaking into them.
        """
        if self.H is None:
            raise RuntimeError("call fit() first")
        Y = stft(mics, self.n_fft, self.hop)          # (M, F, T)
        X = stft(refs, self.n_fft, self.hop)          # (R, F, T)
        W = self.H.copy()                             # (F, M, R)
        delta = self.floor * self.cal_power + 1e-30
        F = Y.shape[1]
        upd = np.ones(F, bool)
        if f0:
            from .dsp import harmonic_weights
            freqs = np.fft.rfftfreq(self.n_fft, 1 / fs)
            upd = harmonic_weights(freqs, f0, 4000.0, rel_bw=0.01, min_bw=8) < 0.05
            ok = np.flatnonzero(upd)
            bad = np.flatnonzero(~upd)
            r = np.clip(np.searchsorted(ok, bad), 1, len(ok) - 1)
            lo, hi = ok[r - 1], ok[r]
            wr = np.clip((bad - lo) / np.maximum(hi - lo, 1), 0, 1)[:, None, None]
        E = np.empty_like(Y)
        hist = np.empty((Y.shape[2],) + W.shape, W.dtype) if keep_weights else None
        for t in range(Y.shape[2]):
            x = X[:, :, t].T                          # (F, R)
            if keep_weights:
                hist[t] = W
            e = Y[:, :, t].T - np.einsum("fmr,fr->fm", W, x)
            E[:, :, t] = e.T
            px = np.sum(np.abs(x) ** 2, axis=1)
            norm = px + delta
            step = self.mu * np.einsum("fm,fr->fmr", e, x.conj()) / norm[:, None, None]
            live = upd & (px >= self.gate * self.cal_power)
            W[live] += step[live]
            if f0:
                W[bad] = W[lo] * (1 - wr) + W[hi] * wr
        self.weights = hist
        return istft(E, self.n_fft, self.hop, mics.shape[-1])

    def apply_weights(self, mics: np.ndarray, refs: np.ndarray) -> np.ndarray:
        """Re-apply the weight trajectory of the last ``transform`` call to other
        signals (e.g. the drone component alone) to measure target distortion."""
        Y = stft(mics, self.n_fft, self.hop)
        X = stft(refs, self.n_fft, self.hop)
        E = Y - np.einsum("tfmr,rft->mft", self.weights, X)
        return istft(E, self.n_fft, self.hop, mics.shape[-1])
