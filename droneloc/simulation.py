"""Outdoor acoustic simulation of a battery-swap station listening to a drone.

The scene contains:

* a six-microphone spherical (octahedral) array on the station,
* the target drone moving along a trajectory (moving-source propagation with
  delay, 1/r spreading, Doppler and an optional ground reflection),
* station machinery near the array (the interference to subtract),
* two reference sensors for multimodal reference subtraction: an acoustic
  reference microphone at the machinery and a vibration sensor on its frame,
* incoherent wind at each microphone, bird chirps and sensor self-noise.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy.signal import butter, resample_poly, sosfilt

from .dsp import SPEED_OF_SOUND, db_to_pa
from .datasets import SourceBank
from .synth import bird_chirps, smooth_noise, station_machinery, wind_noise

Trajectory = Callable[[np.ndarray], np.ndarray]


@dataclass
class MicArray:
    positions: np.ndarray            # (M, 3) relative to the array centre [m]
    center: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 1.0]))

    @property
    def n_mics(self) -> int:
        return len(self.positions)

    @property
    def absolute(self) -> np.ndarray:
        return self.positions + self.center

    @property
    def pairs(self) -> list[tuple[int, int]]:
        m = self.n_mics
        return [(i, j) for i in range(m) for j in range(i + 1, m)]

    @property
    def max_tdoa(self) -> float:
        d = self.positions[:, None] - self.positions[None]
        return float(np.linalg.norm(d, axis=-1).max() / SPEED_OF_SOUND)


def octahedral_array(radius: float = 0.08, center=(0.0, 0.0, 1.0)) -> MicArray:
    """Six microphones on a sphere at +-x, +-y, +-z."""
    pos = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)
    return MicArray(pos * radius, np.asarray(center, float))


def static(position) -> Trajectory:
    p = np.asarray(position, float)
    return lambda t: np.broadcast_to(p, (len(t), 3))


def homing_trajectory(duration: float, start=(30.0, 17.0, 18.0), end=(1.5, -1.0, 3.0),
                      spiral_radius: float = 6.0, turns: float = 1.5) -> Trajectory:
    """Spiral descent from far away to just above the station (an approach to land)."""
    start, end = np.asarray(start, float), np.asarray(end, float)

    def f(t):
        s = np.clip(t / duration, 0, 1)
        s = s * s * (3 - 2 * s)  # smoothstep: accelerate, cruise, slow down
        base = start + (end - start) * s[:, None]
        ang = 2 * np.pi * turns * s
        rad = spiral_radius * (1 - s)
        off = np.stack([rad * np.cos(ang), rad * np.sin(ang), 0.8 * np.sin(3 * ang) * (1 - s)], 1)
        return base + off
    return f


@dataclass
class Scene:
    array: MicArray = field(default_factory=lambda: octahedral_array(0.08))
    fs: int = 16000
    drone: str = "hexa_swap"
    trajectory: Trajectory | None = None
    machinery_pos: tuple = (0.7, 0.4, 0.5)
    machinery_level_db: float = 74.0
    ref_mic_offset: tuple = (0.05, 0.0, 0.05)
    use_vibration_sensor: bool = True
    wind_level_db: float = 40.0
    bird_level_db: float = 36.0
    ground_reflection: float = 0.5        # reflection coefficient, 0 disables
    sensor_noise_db: float = 18.0
    bank: SourceBank | None = None
    # --- realism options (reviewer comments M1, M4) ---
    scattering: bool = False              # rigid-sphere diffraction instead of free-field points
    pos_err_mm: float = 0.0               # std of microphone position error (per axis)
    gain_err_db: float = 0.0              # std of microphone sensitivity mismatch
    delay_err_us: float = 0.0             # std of per-channel timing (phase) mismatch
    clock_ppm: float = 0.0                # std of per-channel sampling-clock skew
    calibration_seed: int = 1234          # fixed hardware: same errors in every recording
    ref_wind_db: float | None = None      # wind at the reference microphone (default: wind_level_db)
    ref_gain_db: float = 0.0              # reference-microphone gain (drift between calibration and test)
    machinery_motion_m: float = 0.0       # amplitude of machinery movement (time-varying paths)


@dataclass
class Recording:
    fs: int
    mics: np.ndarray        # (M, n) array microphones
    refs: np.ndarray        # (R, n) reference sensors (ref mic [, vibration])
    target: np.ndarray      # (M, n) drone component only (ground truth)
    positions: np.ndarray   # (n, 3) drone position (nan if absent)

    @property
    def t(self) -> np.ndarray:
        return np.arange(self.mics.shape[1]) / self.fs


class _Propagator:
    """Moving point source -> receiver via fractional delay on an upsampled signal."""

    def __init__(self, src: np.ndarray, fs: int, preroll: int, up: int = 4):
        self.src = resample_poly(src, up, 1)
        self.fs, self.pre, self.up = fs, preroll, up

    def to(self, src_pos: np.ndarray, rcv: np.ndarray, n: int, gain: float = 1.0) -> np.ndarray:
        dist = np.maximum(np.linalg.norm(src_pos - rcv, axis=-1), 0.05)
        t_emit = np.arange(n) / self.fs - dist / SPEED_OF_SOUND
        idx = (t_emit * self.fs + self.pre) * self.up
        y = np.interp(idx, np.arange(self.src.size), self.src, left=0.0, right=0.0)
        return gain * y / dist

    def with_ground(self, src_pos, rcv, n, coef):
        y = self.to(src_pos, rcv, n)
        if coef > 0:
            img = np.array(src_pos, float, copy=True)
            img[..., 2] *= -1
            y += self.to(img, rcv, n, coef)
        return y


def _hardware_errors(scene: Scene):
    """Fixed per-unit calibration errors (same draw for every recording of a scene)."""
    r = np.random.default_rng(scene.calibration_seed)
    M = scene.array.n_mics
    return dict(dpos=r.normal(0, scene.pos_err_mm * 1e-3, (M, 3)),
                gain=10 ** (r.normal(0, scene.gain_err_db, M) / 20),
                delay=r.normal(0, scene.delay_err_us * 1e-6, M),
                skew=r.normal(0, scene.clock_ppm * 1e-6, M))


class _SphereFilter:
    """Applies direction-dependent rigid-sphere responses frame by frame (STFT)."""

    def __init__(self, scene: Scene, n_fft: int = 512, hop: int = 128, n_cos: int = 721):
        from .sphere import rigid_sphere_response
        arr = scene.array
        self.n_fft, self.hop, self.fs = n_fft, hop, scene.fs
        self.freqs = np.fft.rfftfreq(n_fft, 1 / scene.fs)
        self.normals = arr.positions / np.linalg.norm(arr.positions, axis=1, keepdims=True)
        self.radius = float(np.linalg.norm(arr.positions, axis=1).mean())
        self.cos_grid = np.linspace(-1, 1, n_cos)
        self.table = rigid_sphere_response(self.freqs, self.radius, self.cos_grid)  # (C, F)

    def response(self, cos: np.ndarray) -> np.ndarray:
        x = (np.clip(cos, -1, 1) + 1) / 2 * (len(self.cos_grid) - 1)
        i0 = np.minimum(np.floor(x).astype(int), len(self.cos_grid) - 2)
        w = (x - i0)[..., None]
        return self.table[i0] * (1 - w) + self.table[i0 + 1] * w

    def apply(self, x_centre: np.ndarray, dirs: np.ndarray, dpos: np.ndarray) -> np.ndarray:
        """x_centre: free-field signal at the sphere centre; dirs: (n,3) unit vectors to the source."""
        from .dsp import istft, stft
        n = x_centre.size
        X = stft(x_centre, self.n_fft, self.hop)                       # (F, T)
        T = X.shape[1]
        idx = np.clip(np.arange(T) * self.hop - self.n_fft // 2 + self.n_fft // 2, 0, n - 1)
        u = dirs[idx]                                                  # (T, 3)
        cos = u @ self.normals.T                                       # (T, M)
        H = self.response(cos)                                         # (T, M, F)
        # position errors: extra plane-wave delay -(dp.u)/c
        tau = -(u @ dpos.T) / SPEED_OF_SOUND                           # (T, M)
        H = H * np.exp(-2j * np.pi * self.freqs[None, None, :] * tau[..., None])
        Y = np.einsum("tmf,ft->mft", H, X)
        return istft(Y, self.n_fft, self.hop, n)


def render(scene: Scene, duration: float, drone_on: bool = True,
           rng: np.random.Generator | None = None) -> Recording:
    rng = rng or np.random.default_rng()
    fs, arr = scene.fs, scene.array
    n = int(round(duration * fs))
    pre = int(0.5 * fs)
    t = np.arange(n) / fs
    err = _hardware_errors(scene)
    centre = arr.center
    mics_pos = arr.absolute + err["dpos"]          # true (perturbed) positions
    mach0 = np.asarray(scene.machinery_pos, float)
    if scene.machinery_motion_m > 0:
        mach_pos = mach0 + scene.machinery_motion_m * np.stack(
            [np.sin(2 * np.pi * t / 3.0), np.cos(2 * np.pi * t / 4.0), 0 * t], 1)
    else:
        mach_pos = mach0
    ref_pos = mach0 + np.asarray(scene.ref_mic_offset, float)
    M = arr.n_mics
    mics = np.zeros((M, n))
    ref = np.zeros(n)
    target = np.zeros((M, n))
    positions = np.full((n, 3), np.nan)
    sph = _SphereFilter(scene) if scene.scattering else None

    def to_array(prop: _Propagator, src_pos, coef: float) -> np.ndarray:
        """Signals at the six microphones from one (possibly moving) source, with ground image."""
        out = np.zeros((M, n))
        paths = [(np.asarray(src_pos, float), 1.0)]
        if coef > 0:
            img = np.array(src_pos, float, copy=True)
            img[..., 2] *= -1
            paths.append((img, coef))
        for pos, g in paths:
            if sph is None:
                for m in range(M):
                    out[m] += prop.to(pos, mics_pos[m], n, g)
            else:
                xc = prop.to(pos, centre, n, g)
                d = np.broadcast_to(pos, (n, 3)) - centre
                d = d / np.linalg.norm(d, axis=1, keepdims=True)
                out += sph.apply(xc, d, err["dpos"])
        return out

    if drone_on:
        traj = scene.trajectory or homing_trajectory(duration)
        positions = np.asarray(traj(t), float)
        throttle = 1 + 0.03 * smooth_noise(n + pre, fs, rng, 0.5)
        bank = scene.bank or SourceBank(fs)
        src = bank.get(scene.drone, (n + pre) / fs, rng, throttle)
        prop = _Propagator(src, fs, pre)
        target = to_array(prop, positions, scene.ground_reflection)
        ref += prop.with_ground(positions, ref_pos, n, scene.ground_reflection)
        mics += target

    mach = station_machinery(n + pre, fs, rng, scene.machinery_level_db)
    prop = _Propagator(mach, fs, pre)
    mics += to_array(prop, mach_pos, scene.ground_reflection)
    ref += prop.with_ground(mach0, ref_pos, n, scene.ground_reflection)

    birds_pos = np.array([rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(3, 10)])
    birds = _Propagator(bird_chirps(n + pre, fs, rng, scene.bird_level_db + 20), fs, pre)
    mics += to_array(birds, birds_pos, 0.0)
    for m in range(M):
        mics[m] += wind_noise(n, fs, rng, scene.wind_level_db)
        mics[m] += db_to_pa(scene.sensor_noise_db) * rng.standard_normal(n)
    ref_wind = scene.wind_level_db if scene.ref_wind_db is None else scene.ref_wind_db
    ref += wind_noise(n, fs, rng, ref_wind) + db_to_pa(scene.sensor_noise_db) * rng.standard_normal(n)
    ref *= 10 ** (scene.ref_gain_db / 20)
    refs = [ref]

    # per-channel hardware errors: gain, timing offset and sampling-clock skew
    if scene.gain_err_db or scene.delay_err_us or scene.clock_ppm:
        for m in range(M):
            tt = (np.arange(n) - err["delay"][m] * fs) * (1 + err["skew"][m])
            for sig in (mics, target):
                sig[m] = err["gain"][m] * np.interp(tt, np.arange(n), sig[m], left=0.0, right=0.0)

    if scene.use_vibration_sensor:
        # structure-borne path: machinery excitation seen through the frame (no airborne leakage)
        sos = butter(2, [40 / (fs / 2), 2500 / (fs / 2)], btype="band", output="sos")
        vib = sosfilt(sos, mach[pre:])
        vib += 0.03 * np.std(vib) * rng.standard_normal(n)
        # scaled with the machinery level so that a quiet machine gives a quiet vibration signal
        refs.append(vib / np.std(vib) * db_to_pa(scene.machinery_level_db - 14))
    return Recording(fs, mics, np.vstack(refs), target, positions)
