"""Shared signal-processing helpers (STFT, filterbanks, levels)."""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

P_REF = 20e-6  # reference pressure for dB SPL [Pa]
SPEED_OF_SOUND = 343.0  # [m/s]


def hann(n: int) -> np.ndarray:
    """Periodic Hann window."""
    return 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)


def stft(x: np.ndarray, n_fft: int = 1024, hop: int = 256) -> np.ndarray:
    """STFT along the last axis. Returns array of shape (..., F, T)."""
    x = np.asarray(x, dtype=float)
    pad = [(0, 0)] * (x.ndim - 1) + [(n_fft // 2, n_fft // 2 + n_fft)]
    xp = np.pad(x, pad)
    frames = sliding_window_view(xp, n_fft, axis=-1)[..., ::hop, :]
    spec = np.fft.rfft(frames * hann(n_fft), axis=-1)
    return np.swapaxes(spec, -1, -2)


def istft(spec: np.ndarray, n_fft: int, hop: int, length: int) -> np.ndarray:
    """Inverse of :func:`stft` (weighted overlap-add)."""
    win = hann(n_fft)
    frames = np.fft.irfft(np.swapaxes(spec, -1, -2), n=n_fft, axis=-1) * win
    n_frames = frames.shape[-2]
    total = n_fft + hop * (n_frames - 1)
    out = np.zeros(frames.shape[:-2] + (total,))
    norm = np.zeros(total)
    for i in range(n_frames):
        s = i * hop
        out[..., s:s + n_fft] += frames[..., i, :]
        norm[s:s + n_fft] += win ** 2
    out /= np.maximum(norm, 1e-8)
    return out[..., n_fft // 2:n_fft // 2 + length]


def welch_psd(x: np.ndarray, n_fft: int = 4096, hop: int | None = None) -> np.ndarray:
    """Averaged power spectrum along the last axis, shape (..., F)."""
    hop = hop or n_fft // 2
    if x.shape[-1] < n_fft:
        x = np.pad(x, [(0, 0)] * (x.ndim - 1) + [(0, n_fft - x.shape[-1])])
    frames = sliding_window_view(x, n_fft, axis=-1)[..., ::hop, :]
    win = hann(n_fft)
    spec = np.fft.rfft(frames * win, axis=-1)
    # Scale so that sum(psd) ~= mean(x**2)
    return np.mean(np.abs(spec) ** 2, axis=-2) / (np.sum(win ** 2) * n_fft / 2)


def rms(x: np.ndarray, axis=-1) -> np.ndarray:
    return np.sqrt(np.mean(np.square(x), axis=axis))


def spl_db(x: np.ndarray, axis=-1) -> np.ndarray:
    """Sound pressure level of a pressure signal [Pa] in dB re 20 uPa."""
    return 20 * np.log10(np.maximum(rms(x, axis), 1e-12) / P_REF)


def db_to_pa(level_db: float) -> float:
    return P_REF * 10 ** (level_db / 20)


def snr_db(signal: np.ndarray, noise: np.ndarray) -> float:
    return float(10 * np.log10(np.sum(signal ** 2) / max(np.sum(noise ** 2), 1e-20)))


def hz_to_mel(f):
    return 2595 * np.log10(1 + np.asarray(f) / 700)


def mel_to_hz(m):
    return 700 * (10 ** (np.asarray(m) / 2595) - 1)


def mel_filterbank(fs: int, n_fft: int, n_mels: int = 40, fmin: float = 50, fmax: float | None = None) -> np.ndarray:
    fmax = fmax or fs / 2
    freqs = np.fft.rfftfreq(n_fft, 1 / fs)
    edges = mel_to_hz(np.linspace(hz_to_mel(fmin), hz_to_mel(fmax), n_mels + 2))
    fb = np.zeros((n_mels, freqs.size))
    for i in range(n_mels):
        lo, c, hi = edges[i:i + 3]
        fb[i] = np.clip(np.minimum((freqs - lo) / (c - lo), (hi - freqs) / (hi - c)), 0, None)
    return fb / np.maximum(fb.sum(axis=1, keepdims=True), 1e-12)


def harmonic_weights(freqs: np.ndarray, f0: float | None, fmax: float = 4000.0,
                     rel_bw: float = 0.03, min_bw: float = 6.0) -> np.ndarray:
    """Soft comb mask (0..1) that passes the harmonics k*f0 of a rotor tone."""
    if f0 is None or not np.isfinite(f0) or f0 <= 0:
        return ((freqs >= 80) & (freqs <= fmax)).astype(float)
    w = np.zeros_like(freqs, dtype=float)
    for k in range(1, int(fmax // f0) + 1):
        fk = k * f0
        bw = max(min_bw, rel_bw * fk)
        w = np.maximum(w, np.exp(-0.5 * ((freqs - fk) / bw) ** 2))
    return w


def fibonacci_sphere(n: int, min_elevation_deg: float = -90.0) -> np.ndarray:
    """Quasi-uniform unit vectors on the sphere, optionally above an elevation."""
    i = np.arange(n) + 0.5
    z = 1 - 2 * i / n
    phi = np.pi * (1 + 5 ** 0.5) * i
    r = np.sqrt(1 - z ** 2)
    pts = np.stack([r * np.cos(phi), r * np.sin(phi), z], axis=1)
    return pts[pts[:, 2] >= np.sin(np.radians(min_elevation_deg))]


def cart_to_sph(v: np.ndarray):
    """Return azimuth [deg], elevation [deg], range for vectors (...,3)."""
    v = np.asarray(v, dtype=float)
    r = np.linalg.norm(v, axis=-1)
    az = np.degrees(np.arctan2(v[..., 1], v[..., 0]))
    el = np.degrees(np.arcsin(np.clip(v[..., 2] / np.maximum(r, 1e-12), -1, 1)))
    return az, el, r


def angle_between_deg(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = a / np.linalg.norm(a, axis=-1, keepdims=True)
    b = b / np.linalg.norm(b, axis=-1, keepdims=True)
    return np.degrees(np.arccos(np.clip(np.sum(a * b, axis=-1), -1, 1)))
