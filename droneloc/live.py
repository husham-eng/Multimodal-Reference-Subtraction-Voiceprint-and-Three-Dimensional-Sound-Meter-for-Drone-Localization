"""Live direction finding from the Pico microphone array (hardware/pico_mic_array).

    python -m droneloc live --refs 6,7,8,9,10 --cal 3 --bpf 105,200 --steering sphere
    python -m droneloc live --wav run01.wav --band 3000,6000      # replay a recording, no hardware

The byte stream (USB serial, or a WAV file cut into the same "MICA" packets) is
parsed by `PacketReader`; `LiveLocator` keeps a sliding window of the array
channels and, every `hop` seconds, estimates the source direction with the
same GCC-PHAT / PhaseSRP chain as `evaluate-array`. With reference channels the
first `cal` seconds (keep the target away, machinery / motors running) train
the reference canceller, which is then applied to every window.
"""
from __future__ import annotations

import csv
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import numpy as np

from .dsp import welch_psd
from .localization import GccPhat, PhaseSRP
from .pico import PacketReader, make_packet
from .reference_subtraction import ReferenceCanceller
from .simulation import MicArray
from .voiceprint import estimate_bpf

SPHERE_DIRS = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)


class LiveLocator:
    """Streaming direction estimator. Feed int16 frames (n, channels) with `push`."""

    def __init__(self, positions: np.ndarray, fs: int, array_ch: list[int] | None = None,
                 refs: list[int] | None = None, cal_seconds: float = 0.0, window: float = 0.5,
                 hop: float = 0.25, band: tuple | None = None, bpf: tuple | None = None,
                 steering: str = "free", n_dirs: int = 2000, min_level_db: float = -80.0):
        if refs and cal_seconds <= 0:
            raise ValueError("reference channels need a calibration time (cal_seconds > 0)")
        self.fs, self.band, self.bpf, self.min_level_db = fs, band, bpf, min_level_db
        self.array_ch = list(array_ch) if array_ch is not None else list(range(len(positions)))
        self.refs = list(refs or [])
        self.win, self.hop = int(window * fs), int(hop * fs)
        self.n_cal = int(cal_seconds * fs) if self.refs else 0
        centre = positions.mean(0)
        self.gcc = GccPhat(MicArray(positions - centre, centre), fs, n_fft=1024, hop=256)
        fmin, fmax = band if band else (0.0, min(4000.0, fs / 2))
        self.srp = PhaseSRP(self.gcc, steering, n_dirs=n_dirs, min_elevation_deg=-90, fmin=fmin, fmax=fmax, fast=True)
        self.canc: ReferenceCanceller | None = None
        self.pad = ReferenceCanceller().n_fft if self.refs else 0
        self.cal_buf: list[np.ndarray] = []
        self.cal_have = 0
        self.buf = np.zeros((0, len(self.array_ch) + len(self.refs)))
        self.pending: list[np.ndarray] = []
        self.t = 0          # samples consumed after calibration (time of the window end)
        self.next_at = self.win

    @property
    def calibrating(self) -> bool:
        return self.n_cal > 0 and self.canc is None

    def push(self, frames: np.ndarray) -> list[dict]:
        x = frames[:, self.array_ch + self.refs].astype(float) / 32768.0
        if self.calibrating:
            self.cal_buf.append(x)
            self.cal_have += len(x)
            if self.cal_have < self.n_cal:
                return []
            c = np.concatenate(self.cal_buf)
            M = len(self.array_ch)
            self.canc = ReferenceCanceller().fit(c[:self.n_cal, :M].T, c[:self.n_cal, M:].T)
            x, self.cal_buf = c[self.n_cal:], []
        self.pending.append(x)
        self.t += len(x)
        if self.t < self.next_at:
            return []
        # join the packets only when an estimate is due (a copy per USB packet is slow on a Pi)
        self.buf = np.concatenate([self.buf] + self.pending)
        self.pending = []
        out = []
        while self.t >= self.next_at:
            end = len(self.buf) - (self.t - self.next_at)
            if end >= self.win:
                # the canceller also gets `pad` samples of history, so its STFT edges fall outside the window
                w = self.buf[max(0, end - self.win - self.pad):end].T
                out.append(self._estimate(w, (self.next_at + self.n_cal) / self.fs))
            self.next_at += self.hop
        self.buf = self.buf[-(self.pad + self.win):]
        return out

    def _estimate(self, w: np.ndarray, t: float) -> dict:
        M = len(self.array_ch)
        mics = w[:M]
        if self.canc is not None:
            mics = self.canc.transform(mics, w[M:])
        mics = mics[:, -self.win:]
        level = float(10 * np.log10(np.mean(mics ** 2) + 1e-20))
        res = {"t": t, "level_dbfs": level, "azimuth_deg": None, "elevation_deg": None, "power": None,
               "bpf_hz": None}
        if level < self.min_level_db:
            return res
        f0 = None
        if self.bpf:
            f0, _ = estimate_bpf(welch_psd(mics[0], 4096, 1024), self.fs, *self.bpf)
        G = self.gcc.cross_spectra(mics, f0, band=self.band if not self.bpf else None)
        u, p = self.srp.locate(G)
        res.update(azimuth_deg=float(np.degrees(np.arctan2(u[1], u[0]))),
                   elevation_deg=float(np.degrees(np.arcsin(np.clip(u[2], -1, 1)))), power=p, bpf_hz=f0)
        return res


def serial_bytes(port: str | None) -> Iterator[bytes]:
    import serial
    from .pico import find_port

    port = port or find_port()
    if not port:
        raise SystemExit("Pico not found: is it plugged in and flashed with pico_mic_array.uf2? (or give --port)")
    ser = serial.Serial(port, timeout=0.2)
    try:
        ser.dtr = True  # the Pico only streams while DTR is set
    except OSError:
        pass
    print(f"reading {port} ...", file=sys.stderr)
    try:
        while True:
            yield ser.read(8192)
    finally:
        ser.close()


def wav_bytes(path: Path, realtime: bool = False, nf: int = 64) -> Iterator[bytes]:
    """A WAV file cut into Pico packets, so a recording goes through exactly the live path."""
    import soundfile as sf

    x, fs = sf.read(str(path), always_2d=True, dtype="int16")
    for seq, i in enumerate(range(0, len(x) - nf + 1, nf)):
        if realtime:
            time.sleep(nf / fs)
        yield make_packet(seq, x[i:i + nf], fs=int(fs))


def run(source: Iterator[bytes], positions: np.ndarray, seconds: float | None = None,
        log: Path | None = None, quiet: bool = False, **kw) -> list[dict]:
    rd, loc, rows = PacketReader(), None, []
    writer = None
    f = open(log, "w", newline="") if log else None
    try:
        for chunk in source:
            for _, _, fs, frames in rd.feed(chunk):
                if loc is None:
                    loc = LiveLocator(positions, fs, **kw)
                    if loc.calibrating and not quiet:
                        print(f"calibrating reference canceller for {loc.n_cal / fs:.1f} s "
                              "(keep the target away) ...", file=sys.stderr)
                for r in loc.push(frames):
                    rows.append(r)
                    if f and writer is None:
                        writer = csv.DictWriter(f, fieldnames=list(r)); writer.writeheader()
                    if writer:
                        writer.writerow(r)
                    if not quiet:
                        print(_fmt(r, rd), flush=True)
            if seconds and rows and rows[-1]["t"] >= seconds:
                break
    except KeyboardInterrupt:
        pass
    finally:
        if f:
            f.close()
    return rows


def _fmt(r: dict, rd: PacketReader) -> str:
    s = f"t={r['t']:7.2f} s  level {r['level_dbfs']:6.1f} dBFS  "
    if r["azimuth_deg"] is None:
        return s + "(too quiet)"
    s += f"az {r['azimuth_deg']:7.1f}  el {r['elevation_deg']:6.1f}  power {r['power']:.2f}"
    if r["bpf_hz"]:
        s += f"  BPF {r['bpf_hz']:.0f} Hz"
    return s + (f"  | lost {rd.lost} bad {rd.bad}" if rd.lost or rd.bad else "")
