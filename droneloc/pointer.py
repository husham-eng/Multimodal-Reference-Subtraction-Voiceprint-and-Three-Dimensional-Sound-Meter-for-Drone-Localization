"""Two pan/tilt camera heads driven by the Pico pointer board (hardware/pico_pointer).

The upper head covers the upper hemisphere; the lower head is mounted upside down
(rotated 180 deg about the x axis) and covers the lower one. With 180-deg servos
one head reaches its whole hemisphere: for az in [0, 180) pan = az, tilt = el; for
az in [180, 360) pan = az - 180 and tilt = 180 - el (the tilt servo leans back over
the top). Tilt 0 is horizontal along the pan direction, 90 is the head's zenith.

    python -m droneloc pointer status
    python -m droneloc pointer servo 0 1500          # one channel to a pulse width [us]
    python -m droneloc pointer point 30 20           # direction az, el [deg] in the array frame
    python -m droneloc pointer release
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

PRODUCT = "DroneLoc Pointer"
CHANNELS = {"U": (0, 1), "L": (2, 3)}     # (pan, tilt) channel of the upper and lower head


def hemisphere_angles(az_deg: float, el_deg: float, prefer: int | None = None,
                      margin_deg: float = 5.0) -> tuple[float, float, int]:
    """Pan/tilt [deg, 0..180] and branch for a direction in the head's own frame (el >= 0).

    Branch 0 (az in [0, 180]): pan = az, tilt = el. Branch 1 (az in [180, 360]):
    pan = az - 180, tilt = 180 - el. Near az = 0 or 180 both branches point the same
    way but differ by a 180-deg pan swing, so the `prefer`red branch (the one in use) is
    kept while the pan stays within `margin_deg` outside 0..180 (clipped there)."""
    az = az_deg % 360.0
    el = float(np.clip(el_deg, 0.0, 90.0))
    d0 = az if az <= 180.0 + margin_deg else az - 360.0
    e = az - 180.0
    d1 = e if e >= -margin_deg else e + 360.0
    ok = [-margin_deg <= d0 <= 180.0 + margin_deg, -margin_deg <= d1 <= 180.0 + margin_deg]
    branch = prefer if prefer in (0, 1) and ok[prefer] else (0 if az < 180.0 else 1)
    if branch == 0:
        return float(np.clip(d0, 0, 180)), el, 0
    return float(np.clip(d1, 0, 180)), 180.0 - el, 1


@dataclass
class HeadCalibration:
    """How a head is mounted relative to the array frame, found by pointing at known sources."""
    pan_offset_deg: float = 0.0      # pan angle that points along the array +x axis (after mirroring)
    tilt_offset_deg: float = 0.0     # tilt angle that is horizontal
    pan_sign: int = 1                # +1 or -1: direction of rotation of the pan servo
    tilt_sign: int = 1
    limits_us: list = field(default_factory=lambda: [[1200, 1800], [1200, 1800]])  # pan, tilt


@dataclass
class Calibration:
    upper: HeadCalibration = field(default_factory=HeadCalibration)
    lower: HeadCalibration = field(default_factory=HeadCalibration)
    # head position relative to the sphere centre [m], for the parallax correction
    upper_pos_m: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    lower_pos_m: list = field(default_factory=lambda: [0.0, 0.0, 0.0])

    @staticmethod
    def load(path: Path) -> "Calibration":
        d = json.loads(Path(path).read_text())
        return Calibration(HeadCalibration(**d["upper"]), HeadCalibration(**d["lower"]),
                           d.get("upper_pos_m", [0, 0, 0]), d.get("lower_pos_m", [0, 0, 0]))

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=1))


def unit(az_deg: float, el_deg: float) -> np.ndarray:
    a, e = np.radians(az_deg), np.radians(el_deg)
    return np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])


def az_el(v: np.ndarray) -> tuple[float, float]:
    v = np.asarray(v, float) / np.linalg.norm(v)
    return float(np.degrees(np.arctan2(v[1], v[0]))), float(np.degrees(np.arcsin(np.clip(v[2], -1, 1))))


def head_command(az_deg: float, el_deg: float, head: str, cal: Calibration,
                 range_m: float | None = None, prefer: int | None = None) -> tuple[float, float, int]:
    """Pan/tilt servo angles [deg] and branch that point `head` ("U" or "L") along the array
    direction (az, el). With `range_m`, the direction is corrected for the head's offset from
    the sphere centre (parallax): the head aims at the point range_m away from the sphere.
    `prefer` is the branch in use (see hemisphere_angles)."""
    c, pos = (cal.upper, cal.upper_pos_m) if head == "U" else (cal.lower, cal.lower_pos_m)
    v = unit(az_deg, el_deg)
    if range_m:
        v = v * range_m - np.asarray(pos, float)
    az, el = az_el(v)
    if head == "L":                  # upside down: rotated 180 deg about x
        az, el = -az, -el
    pan, tilt, branch = hemisphere_angles(az, el, prefer)
    pan = c.pan_offset_deg + c.pan_sign * pan
    tilt = c.tilt_offset_deg + c.tilt_sign * tilt
    return float(np.clip(pan, 0, 180)), float(np.clip(tilt, 0, 180)), branch


class HeadSelector:
    """Upper head above +margin, lower head below -margin, keep the current one in between."""

    def __init__(self, margin_deg: float = 5.0):
        self.margin, self.head = margin_deg, "U"

    def __call__(self, el_deg: float) -> str:
        if el_deg > self.margin:
            self.head = "U"
        elif el_deg < -self.margin:
            self.head = "L"
        return self.head


class Pointer:
    """Serial client of the pointer firmware."""

    def __init__(self, port: str | None = None, cal: Calibration | None = None, timeout_s: int = 5):
        import serial
        from .pico import find_port

        port = port or find_port(PRODUCT)
        if not port:
            raise SystemExit("pointer Pico not found: is it plugged in and flashed with pico_pointer.uf2? (or give --port)")
        self.ser = serial.Serial(port, timeout=0.5)
        try:
            self.ser.dtr = True
        except OSError:
            pass
        self.cal = cal or Calibration()
        self.selector = HeadSelector()
        self.last: dict[str, tuple] = {}
        self.send(f"T {timeout_s}")
        for head, (p, t) in CHANNELS.items():
            hc = self.cal.upper if head == "U" else self.cal.lower
            self.send(f"LIM {p} {hc.limits_us[0][0]} {hc.limits_us[0][1]}")
            self.send(f"LIM {t} {hc.limits_us[1][0]} {hc.limits_us[1][1]}")

    def send(self, cmd: str) -> list[str]:
        self.ser.write((cmd + "\n").encode())
        lines, t0 = [], time.time()
        n = 5 if cmd.strip() == "?" else 1
        while len(lines) < n and time.time() - t0 < 1.0:
            ln = self.ser.readline().decode(errors="replace").strip()
            if ln:
                lines.append(ln)
        return lines

    def point(self, az_deg: float, el_deg: float, range_m: float | None = None,
              min_step_deg: float = 2.5) -> str | None:
        """Aim the right head; skip the command if it would move less than min_step_deg."""
        head = self.selector(el_deg)
        prev = self.last.get(head)
        pan, tilt, branch = head_command(az_deg, el_deg, head, self.cal, range_m, prev[2] if prev else None)
        if prev and max(abs(pan - prev[0]), abs(tilt - prev[1])) < min_step_deg:
            self.send("P")
            return None
        self.last[head] = (pan, tilt, branch)
        self.send(f"H {head} {pan:.1f} {tilt:.1f}")
        return head

    def release(self) -> None:
        self.send("X *")
