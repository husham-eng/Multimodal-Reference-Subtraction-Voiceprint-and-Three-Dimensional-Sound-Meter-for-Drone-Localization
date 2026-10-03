"""Physically motivated synthesis of drone and ambient sounds.

All generators return sound pressure in pascal. Drone signals are scaled to the
profile's SPL at 1 m, so propagating them with 1/r spreading gives realistic
levels at the microphones.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, lfilter, sosfilt

from .catalog import DroneProfile
from .dsp import db_to_pa, rms


def smooth_noise(n: int, fs: int, rng: np.random.Generator, cutoff_hz: float) -> np.ndarray:
    """Slowly varying zero-mean, unit-std random process."""
    step = max(1, int(fs / cutoff_hz))
    coarse = rng.standard_normal(n // step + 4)
    x = np.interp(np.arange(n) / step, np.arange(coarse.size), coarse)
    x = uniform_filter1d(x, min(step, n), mode="nearest")
    return (x - x.mean()) / max(x.std(), 1e-12)


def synthesize_drone(profile: DroneProfile, duration: float, fs: int = 16000,
                     rng: np.random.Generator | None = None,
                     throttle: np.ndarray | None = None) -> np.ndarray:
    """Rotor noise: blade-passing harmonics + shaft imbalance + motor whine + turbulence.

    ``throttle`` is an optional per-sample RPM multiplier (1.0 = hover).
    """
    rng = rng or np.random.default_rng()
    n = int(round(duration * fs))
    tim = profile.timbre()
    thr = np.ones(n) if throttle is None else np.asarray(throttle, float)[:n]
    tonal = np.zeros(n)
    whine = np.zeros(n)
    phase0 = None
    B = profile.n_blades
    for r in range(profile.n_rotors):
        mod = 1 + profile.rpm_jitter * smooth_noise(n, fs, rng, 1.5)
        f_shaft = profile.hover_rpm / 60 * (1 + tim.rotor_offsets[r]) * mod * thr
        phase = 2 * np.pi * np.cumsum(f_shaft) / fs + rng.uniform(0, 2 * np.pi)
        if phase0 is None:
            phase0 = phase
        f_max = f_shaft.max()
        for k in range(1, profile.n_harmonics + 1):
            if k * B * f_max > 0.45 * fs:
                break
            tonal += tim.harmonic_gains[k - 1] * np.sin(k * B * phase + rng.uniform(0, 2 * np.pi))
        for k, g in enumerate(tim.shaft_gains, start=1):
            if k % B:
                tonal += g * np.sin(k * phase + rng.uniform(0, 2 * np.pi))
        for k in range(1, 4):
            if k * profile.pole_pairs * f_max < 0.45 * fs:
                whine += np.sin(k * profile.pole_pairs * phase + rng.uniform(0, 2 * np.pi)) / k
    tonal /= max(rms(tonal), 1e-12)
    whine *= 10 ** (profile.whine_db / 20) / max(rms(whine), 1e-12)

    b, a = butter(1, min(profile.broadband_corner_hz / (fs / 2), 0.99))
    bb = lfilter(b, a, rng.standard_normal(n))
    bb *= 1 + 0.6 * np.sin(B * phase0)  # blade-passage amplitude modulation
    bb *= 10 ** (profile.broadband_db / 20) / max(rms(bb), 1e-12)

    x = tonal + whine + bb
    return x * db_to_pa(profile.level_1m_db) / rms(x)


# --------------------------------------------------------------------------- ambient

def _scale(x: np.ndarray, level_db: float) -> np.ndarray:
    return x * db_to_pa(level_db) / max(rms(x), 1e-20)


def wind_noise(n: int, fs: int, rng: np.random.Generator, level_db: float = 45.0) -> np.ndarray:
    """Low-frequency, gusty wind noise (incoherent between microphones)."""
    sos = butter(2, 250 / (fs / 2), output="sos")
    x = sosfilt(sos, rng.standard_normal(n))
    x *= np.exp(0.7 * smooth_noise(n, fs, rng, 0.4))
    return _scale(x, level_db)


def pink_noise(n: int, rng: np.random.Generator, level_db: float = 30.0) -> np.ndarray:
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.arange(spec.size)
    spec[1:] /= np.sqrt(f[1:])
    spec[0] = 0
    return _scale(np.fft.irfft(spec, n), level_db)


def station_machinery(n: int, fs: int, rng: np.random.Generator, level_1m_db: float = 72.0,
                      mains_hz: float = 50.0) -> np.ndarray:
    """Battery-swap station noise: transformer hum, cooling fan, actuator whine bursts.

    Its tones overlap the drone band, which is what reference subtraction removes.
    """
    t = np.arange(n) / fs
    hum = sum(np.sin(2 * np.pi * k * mains_hz * t + rng.uniform(0, 6.3)) / k for k in (2, 4, 6, 8))
    fan_f = 2600 / 60 * 7 * (1 + 0.01 * smooth_noise(n, fs, rng, 0.5))
    fan_ph = 2 * np.pi * np.cumsum(fan_f) / fs
    fan = sum(0.8 ** k * np.sin(k * fan_ph + rng.uniform(0, 6.3)) for k in range(1, 8))
    # actuator (servo / lead-screw) bursts with gliding whine
    gate = (smooth_noise(n, fs, rng, 0.3) > 0.3).astype(float)
    gate = uniform_filter1d(gate, min(int(0.05 * fs), n), mode="nearest")
    act_f = np.clip(600 + 250 * smooth_noise(n, fs, rng, 0.8), 300, 1100)
    act = gate * sum(np.sin(k * 2 * np.pi * np.cumsum(act_f) / fs) / k for k in (1, 2, 3))
    sos = butter(2, [200 / (fs / 2), 3000 / (fs / 2)], btype="band", output="sos")
    broad = 0.3 * sosfilt(sos, rng.standard_normal(n))
    x = 0.6 * hum / rms(hum) + fan / rms(fan) + 1.2 * act / max(rms(act), 1e-9) + broad / rms(broad) * 0.4
    return _scale(x, level_1m_db)


def bird_chirps(n: int, fs: int, rng: np.random.Generator, level_db: float = 40.0,
                rate_hz: float = 0.8) -> np.ndarray:
    x = np.zeros(n)
    for _ in range(rng.poisson(rate_hz * n / fs)):
        L = int(rng.uniform(0.05, 0.2) * fs)
        s = rng.integers(0, max(1, n - L))
        tt = np.arange(L) / fs
        f0, f1 = rng.uniform(2000, 6000, 2)
        ph = 2 * np.pi * (f0 * tt + (f1 - f0) * tt ** 2 / (2 * tt[-1]))
        x[s:s + L] += np.sin(ph) * np.hanning(L)
    return _scale(x, level_db) if np.any(x) else x
