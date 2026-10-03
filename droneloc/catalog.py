"""Library of drone sound sources: synthetic drone profiles and public datasets.

Two kinds of "libraries" are offered:

* ``DRONE_PROFILES`` - parametric rotor-noise models that run fully offline.
  The numbers are representative values (blade count, hover RPM, level) and
  should be re-tuned against real recordings of the drone you actually fly.
* ``DATASETS`` - public drone / background audio collections. Those marked
  ``auto_download`` can be fetched with ``python -m droneloc download <key>``;
  the others must be downloaded manually from the listed page.
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class DroneProfile:
    key: str
    name: str
    n_rotors: int
    n_blades: int
    hover_rpm: float
    rotor_spread: float = 0.03      # +- fractional RPM difference between rotors
    rpm_jitter: float = 0.015       # slow thrust-control RPM fluctuation (fraction)
    pole_pairs: int = 7             # BLDC motor pole pairs (motor whine)
    harmonic_decay_db: float = 3.0  # dB drop per blade-passing harmonic
    n_harmonics: int = 20
    whine_db: float = -22.0         # motor whine relative to the BPF tone
    broadband_db: float = -8.0      # broadband (turbulence) relative to tonal part
    broadband_corner_hz: float = 1500.0
    level_1m_db: float = 80.0       # SPL at 1 m while hovering [dB re 20 uPa]
    mass_kg: float = 1.0

    @property
    def bpf_hz(self) -> float:
        """Blade-passing frequency at hover - the fundamental of the voiceprint."""
        return self.hover_rpm / 60.0 * self.n_blades

    def timbre(self) -> "Timbre":
        """Deterministic per-model details that make the voiceprint unique."""
        rng = np.random.default_rng(zlib.crc32(self.key.encode()))
        k = np.arange(self.n_harmonics)
        gains_db = -self.harmonic_decay_db * k + rng.normal(0, 4.0, self.n_harmonics)
        gains_db[0] = 0.0
        offsets = rng.uniform(-self.rotor_spread, self.rotor_spread, self.n_rotors)
        shaft_db = -18 + rng.normal(0, 3, 4)
        return Timbre(10 ** (gains_db / 20), offsets, 10 ** (shaft_db / 20))


@dataclass(frozen=True)
class Timbre:
    harmonic_gains: np.ndarray
    rotor_offsets: np.ndarray
    shaft_gains: np.ndarray


# Parrot RPMs were tuned to the BPFs measured in DroneAudioDataset (Bebop ~395 Hz, Mambo ~613 Hz).
DRONE_PROFILES: dict[str, DroneProfile] = {p.key: p for p in [
    DroneProfile("dji_mini", "DJI Mini (sub-250 g)", 4, 2, 9600, harmonic_decay_db=3.5,
                 level_1m_db=70, mass_kg=0.25, broadband_corner_hz=2500),
    DroneProfile("dji_mavic", "DJI Mavic class", 4, 2, 6600, level_1m_db=76, mass_kg=0.9),
    DroneProfile("dji_phantom4", "DJI Phantom 4", 4, 2, 5400, harmonic_decay_db=2.5,
                 level_1m_db=80, mass_kg=1.4),
    DroneProfile("parrot_bebop2", "Parrot Bebop 2", 4, 3, 7900, harmonic_decay_db=4.0,
                 pole_pairs=6, level_1m_db=75, mass_kg=0.5),
    DroneProfile("parrot_mambo", "Parrot Mambo (toy)", 4, 2, 18400, harmonic_decay_db=4.5,
                 pole_pairs=3, level_1m_db=68, mass_kg=0.06, broadband_corner_hz=3500),
    DroneProfile("dji_matrice300", "DJI Matrice 300 (heavy)", 4, 2, 3300, harmonic_decay_db=2.0,
                 pole_pairs=12, level_1m_db=88, mass_kg=6.3, broadband_corner_hz=900),
    DroneProfile("hexa_swap", "Battery-swap hexacopter (custom)", 6, 2, 4500,
                 harmonic_decay_db=2.5, pole_pairs=12, level_1m_db=84, mass_kg=3.0,
                 broadband_corner_hz=1100),
]}


@dataclass(frozen=True)
class DatasetInfo:
    key: str
    name: str
    url: str
    content: str
    use: str
    drones: dict[str, str] = field(default_factory=dict)  # folder keyword -> profile key
    auto_download: bool = False
    git_url: str | None = None
    sparse_paths: tuple[str, ...] = ()


DATASETS: dict[str, DatasetInfo] = {d.key: d for d in [
    DatasetInfo(
        "droneaudio", "DroneAudioDataset (Al-Emadi et al., 2019)",
        "https://github.com/saraalemadi/DroneAudioDataset",
        "1 s mono clips, 16 kHz: Parrot Bebop, Parrot Mambo ('membo') and 'unknown' background.",
        "Voiceprint training for Bebop / Mambo; background negatives.",
        drones={"bebop": "parrot_bebop2", "membo": "parrot_mambo", "mambo": "parrot_mambo"},
        auto_download=True, git_url="https://github.com/saraalemadi/DroneAudioDataset",
        sparse_paths=("Multiclass_Drone_Audio/bebop_1", "Multiclass_Drone_Audio/membo_1",
                      "Multiclass_Drone_Audio/unknown"),
    ),
    DatasetInfo(
        "svanstrom", "Drone detection dataset (Svanstrom et al., 2021)",
        "https://github.com/DroneDetectionThesis/Drone-detection-dataset",
        "Audio clips of drones, helicopters and background (plus IR / visible video).",
        "Extra drone vs. non-drone voiceprint data; multimodal (audio + video) experiments.",
        auto_download=True, git_url="https://github.com/DroneDetectionThesis/Drone-detection-dataset",
        sparse_paths=("Data/Audio",),
    ),
    DatasetInfo(
        "esc50", "ESC-50 environmental sounds (Piczak, 2015)",
        "https://github.com/karolpiczak/ESC-50",
        "2000 x 5 s clips in 50 classes (wind, rain, birds, engine, helicopter ...).",
        "Background / interference library for the reference-subtraction stage.",
        auto_download=True, git_url="https://github.com/karolpiczak/ESC-50", sparse_paths=("audio", "meta"),
    ),
    DatasetInfo(
        "dregon", "DREGON (Strauss et al., 2018)",
        "http://dregon.inria.fr",
        "8-mic array mounted on a quadrotor; ego-noise and sources with ground-truth positions.",
        "Validating ego-noise subtraction and GCC-PHAT / SRP-PHAT localization on real data.",
    ),
    DatasetInfo(
        "spcup2019", "IEEE Signal Processing Cup 2019 (drone-embedded sound localization)",
        "https://signalprocessingsociety.org (search: 'Signal Processing Cup 2019')",
        "Recordings from a drone-mounted 8-mic array with direction labels (built on DREGON).",
        "Benchmarking the 3D direction estimator.",
    ),
    DatasetInfo(
        "salford_dronenoise", "DroneNoise Database (Univ. of Salford)",
        "https://salford.figshare.com (search: 'DroneNoise Database')",
        "Calibrated outdoor measurements of several commercial drones in different manoeuvres.",
        "Calibrating the 1 m reference level used by the 3D sound meter (range from level).",
    ),
]}


def describe() -> str:
    lines = ["Synthetic drone profiles (offline, choose one with --drone):", ""]
    lines.append(f"  {'key':16s} {'name':34s} {'rotors':>6s} {'blades':>6s} {'RPM':>6s} {'BPF[Hz]':>8s} {'dB@1m':>6s}")
    for p in DRONE_PROFILES.values():
        lines.append(f"  {p.key:16s} {p.name:34s} {p.n_rotors:6d} {p.n_blades:6d} {p.hover_rpm:6.0f} "
                     f"{p.bpf_hz:8.1f} {p.level_1m_db:6.0f}")
    lines += ["", "Public datasets (use with --dataset):", ""]
    for d in DATASETS.values():
        tag = "auto-download" if d.auto_download else "manual download"
        lines.append(f"  [{d.key}] {d.name}  ({tag})")
        lines.append(f"      {d.url}")
        lines.append(f"      content: {d.content}")
        lines.append(f"      use:     {d.use}")
        if d.drones:
            lines.append(f"      drones:  {', '.join(sorted(set(d.drones.values())))}")
    return "\n".join(lines)
