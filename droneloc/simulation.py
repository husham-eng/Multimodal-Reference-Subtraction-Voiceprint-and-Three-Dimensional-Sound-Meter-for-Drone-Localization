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


def render(scene: Scene, duration: float, drone_on: bool = True,
           rng: np.random.Generator | None = None) -> Recording:
    rng = rng or np.random.default_rng()
    fs, arr = scene.fs, scene.array
    n = int(round(duration * fs))
    pre = int(0.5 * fs)
    t = np.arange(n) / fs
    mics_pos = arr.absolute
    mach_pos = np.asarray(scene.machinery_pos, float)
    ref_pos = mach_pos + np.asarray(scene.ref_mic_offset, float)
    M = arr.n_mics
    mics = np.zeros((M, n))
    ref = np.zeros(n)
    target = np.zeros((M, n))
    positions = np.full((n, 3), np.nan)

    if drone_on:
        traj = scene.trajectory or homing_trajectory(duration)
        positions = np.asarray(traj(t), float)
        throttle = 1 + 0.03 * smooth_noise(n + pre, fs, rng, 0.5)
        bank = scene.bank or SourceBank(fs)
        src = bank.get(scene.drone, (n + pre) / fs, rng, throttle)
        prop = _Propagator(src, fs, pre)
        for m in range(M):
            target[m] = prop.with_ground(positions, mics_pos[m], n, scene.ground_reflection)
        ref += prop.with_ground(positions, ref_pos, n, scene.ground_reflection)
        mics += target

    mach = station_machinery(n + pre, fs, rng, scene.machinery_level_db)
    prop = _Propagator(mach, fs, pre)
    for m in range(M):
        mics[m] += prop.with_ground(mach_pos, mics_pos[m], n, scene.ground_reflection)
    ref += prop.with_ground(mach_pos, ref_pos, n, scene.ground_reflection)

    birds_pos = np.array([rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(3, 10)])
    birds = _Propagator(bird_chirps(n + pre, fs, rng, scene.bird_level_db + 20), fs, pre)
    for m in range(M):
        mics[m] += birds.to(birds_pos, mics_pos[m], n)
        mics[m] += wind_noise(n, fs, rng, scene.wind_level_db)
        mics[m] += db_to_pa(scene.sensor_noise_db) * rng.standard_normal(n)
    ref += wind_noise(n, fs, rng, scene.wind_level_db) + db_to_pa(scene.sensor_noise_db) * rng.standard_normal(n)
    refs = [ref]

    if scene.use_vibration_sensor:
        # structure-borne path: machinery excitation seen through the frame (no airborne leakage)
        sos = butter(2, [40 / (fs / 2), 2500 / (fs / 2)], btype="band", output="sos")
        vib = sosfilt(sos, mach[pre:])
        vib += 0.03 * np.std(vib) * rng.standard_normal(n)
        refs.append(vib / np.std(vib) * db_to_pa(60))  # scaled to a pressure-like unit
    return Recording(fs, mics, np.vstack(refs), target, positions)
