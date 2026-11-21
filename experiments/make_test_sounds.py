"""Test sounds for the physical array, to be played from a phone or a loudspeaker.

    python experiments/make_test_sounds.py               # writes test_sounds/*.wav and test_sounds/index.csv

All drone sounds are synthetic (droneloc.synth, no third-party recordings), so they can be
used and shared without licence restrictions, and the blade-passing frequency (BPF) of each
file is known exactly. 44.1 kHz, 16-bit mono WAV, RMS -18 dBFS (peak at most -1 dBFS),
0.5 s fades. Phone speakers reproduce little below ~300 Hz: the rotor fundamental of the
heavier drones is weak, but the harmonics carry the BPF and the direction.
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from droneloc.catalog import DRONE_PROFILES  # noqa: E402
from droneloc.synth import pink_noise, station_machinery, synthesize_drone  # noqa: E402

FS = 44100


def finish(x: np.ndarray, fade_s: float = 0.5, rms_db: float = -18.0, peak_db: float = -1.0) -> np.ndarray:
    x = x - x.mean()
    x = x * 10 ** (rms_db / 20) / (np.sqrt(np.mean(x ** 2)) + 1e-12)
    peak = np.abs(x).max()
    if peak > 10 ** (peak_db / 20):
        x *= 10 ** (peak_db / 20) / peak
    n = int(fade_s * FS)
    ramp = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n))
    x[:n] *= ramp
    x[-n:] *= ramp[::-1]
    return x


def bandpass_noise(n: int, lo: float, hi: float, rng) -> np.ndarray:
    X = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / FS)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, n)


def chirp_train(n: int, lo: float = 3000, hi: float = 6000, dur: float = 0.05) -> np.ndarray:
    """The active-mode beacon (droneloc/exp_active.py): 50 ms linear chirp 3-6 kHz, repeated."""
    t = np.arange(int(dur * FS)) / FS
    c = np.sin(2 * np.pi * (lo * t + 0.5 * (hi - lo) / dur * t ** 2)) * np.hanning(t.size) ** 0.25
    return np.tile(c, n // c.size + 1)[:n]


def log_sweeps(n_rep: int = 3, f0: float = 100, f1: float = 7000, dur: float = 5.0, gap: float = 1.0) -> np.ndarray:
    t = np.arange(int(dur * FS)) / FS
    k = np.log(f1 / f0)
    s = np.sin(2 * np.pi * f0 * dur / k * (np.exp(t * k / dur) - 1))
    return np.concatenate([np.concatenate([np.zeros(int(gap * FS)), s]) for _ in range(n_rep)] + [np.zeros(int(gap * FS))])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="test_sounds")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    import soundfile as sf

    rng = np.random.default_rng(a.seed)
    n = int(a.seconds * FS)
    rows = []

    def write(name, x, purpose, bpf=None, search=None, command=""):
        sf.write(out / f"{name}.wav", finish(x), FS, subtype="PCM_16")
        rows.append({"file": f"{name}.wav", "purpose": purpose, "bpf_hz": f"{bpf:.1f}" if bpf else "",
                     "bpf_search_hz": search or "", "suggested_command": command})
        print(f"{name}.wav  {purpose}")

    for k, (key, p) in enumerate(DRONE_PROFILES.items(), start=1):
        lo, hi = 0.7 * p.bpf_hz, 1.3 * p.bpf_hz
        write(f"{k:02d}_{key}_hover", synthesize_drone(p, a.seconds, FS, rng),
              f"{p.name}, hover (BPF {p.bpf_hz:.0f} Hz)", p.bpf_hz, f"{lo:.0f},{hi:.0f}",
              f"python -m droneloc live --bpf {lo:.0f},{hi:.0f} --steering sphere")
    p = DRONE_PROFILES["hexa_swap"]
    t = np.arange(n) / FS
    # approach: level rises as 1/r from 40 m to 2 m (26 dB), small throttle changes
    r = 40 * (2 / 40) ** (t / t[-1])
    thr = 1 + 0.04 * np.sin(2 * np.pi * t / 7)
    write("08_hexa_swap_approach_40m_to_2m", synthesize_drone(p, a.seconds, FS, rng, throttle=thr) * (2 / r),
          "Battery-swap hexacopter approaching: level +26 dB over the file", p.bpf_hz, "105,200",
          "python -m droneloc live --bpf 105,200 --steering sphere --log approach.csv")
    # RPM sweep +-30 %: BPF tracking and its effect on the direction (reviewer comment R2-2)
    thr = 1 + 0.3 * np.sin(2 * np.pi * t / t[-1])
    write("09_hexa_swap_rpm_sweep_pm30pct", synthesize_drone(p, a.seconds, FS, rng, throttle=thr),
          "Battery-swap hexacopter, RPM swept +-30 % (BPF 105-195 Hz)", p.bpf_hz, "95,210",
          "python -m droneloc live --bpf 95,210 --steering sphere --log rpm_sweep.csv")
    write("10_broadband_noise_3-6kHz", bandpass_noise(n, 3000, 6000, rng),
          "Broadband reference source 3-6 kHz: direction ground-truth tests", None, "",
          "python -m droneloc live --band 3000,6000 --steering sphere")
    write("11_beacon_chirp_3-6kHz", chirp_train(n),
          "Active-mode beacon: 50 ms chirps 3-6 kHz, back to back", None, "",
          "python -m droneloc live --band 3000,6000 --steering sphere")
    write("12_log_sweeps_100Hz-7kHz", log_sweeps(),
          "Three 5 s log sweeps: speaker / microphone response check", None, "", "")
    write("13_pink_noise", pink_noise(n, rng), "Pink noise: level and channel-gain check", None, "", "")
    write("14_station_machinery", station_machinery(n, FS, rng),
          "Station machinery (hum, cooling fan, actuator): interference from a second speaker", None, "",
          "python -m droneloc live --refs 6,7,8,9,10 --cal 3 --bpf 105,200 --steering sphere")
    with open(out / "index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} files in {out}/ (index.csv lists the BPF and a command for each)")


if __name__ == "__main__":
    main()
