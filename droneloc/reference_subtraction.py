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
