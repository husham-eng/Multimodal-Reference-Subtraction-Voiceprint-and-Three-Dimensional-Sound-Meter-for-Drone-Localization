"""Rigid-sphere scattering for microphones mounted flush on a sphere.

The free-field model treats the six microphones as points in air. On the real
160 mm sensor they sit on a rigid body, which (i) delays sound reaching the
shadowed side (it has to diffract around the sphere) and (ii) boosts the
pressure on the illuminated side. Both effects grow with ka.

For a plane wave arriving from direction u, the pressure at a surface point
whose outward normal makes angle Theta with u is (Rayleigh's series, e.g.
Duda & Martens, JASA 104(5), 1998)

    H(ka, Theta) = (1 / (ka)^2) * sum_n  i^(n+1) (2n+1) P_n(cos Theta) / h_n'(ka)

normalised to the free-field pressure at the sphere centre. The series is
written here for the e^{+j w t} time convention used by numpy FFTs, so that
an illuminated microphone shows a phase lead (negative group delay).
"""
from __future__ import annotations

import numpy as np
from scipy.special import eval_legendre, spherical_jn, spherical_yn

from .dsp import SPEED_OF_SOUND


def rigid_sphere_response(freqs: np.ndarray, radius: float, cos_theta: np.ndarray,
                          c: float = SPEED_OF_SOUND) -> np.ndarray:
    """Complex surface-pressure transfer, shape (len(cos_theta), len(freqs)).

    ``cos_theta`` is the cosine between the microphone normal and the
    direction *towards* the source (1 = microphone faces the source).
    """
    freqs = np.asarray(freqs, float)
    ct = np.atleast_1d(np.asarray(cos_theta, float))
    ka = np.maximum(2 * np.pi * freqs * radius / c, 1e-6)
    n_max = int(np.ceil(ka.max() + 4 * ka.max() ** (1 / 3) + 6))
    out = np.zeros((ct.size, freqs.size), complex)
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        for n in range(n_max + 1):
            # derivative of the spherical Hankel function of the second kind
            dh = spherical_jn(n, ka, derivative=True) - 1j * spherical_yn(n, ka, derivative=True)
            term = (1j ** (n + 1)) * (2 * n + 1) / dh
            out += eval_legendre(n, ct)[:, None] * np.nan_to_num(term)[None, :]
    out /= ka[None, :] ** 2
    out[:, freqs <= 0] = 1.0
    return out


def mic_responses(freqs: np.ndarray, mic_normals: np.ndarray, directions: np.ndarray,
                  radius: float) -> np.ndarray:
    """H[m, d, f] for unit mic normals (M,3) and source directions (D,3)."""
    cos = np.clip(mic_normals @ directions.T, -1, 1)          # (M, D)
    flat = rigid_sphere_response(freqs, radius, cos.ravel())  # (M*D, F)
    return flat.reshape(cos.shape + (len(freqs),))


def group_delay(freqs: np.ndarray, h: np.ndarray) -> np.ndarray:
    """-d(phase)/d(omega) along the last axis [s]."""
    ph = np.unwrap(np.angle(h), axis=-1)
    return -np.gradient(ph, 2 * np.pi * freqs, axis=-1)
