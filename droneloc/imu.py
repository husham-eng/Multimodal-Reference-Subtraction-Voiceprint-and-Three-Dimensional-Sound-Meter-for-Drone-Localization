"""Orientation sensors that keep the sphere and the camera heads consistent.

* BNO085 on the sphere, in UART-RVC mode (P0 pin high): it sends yaw, pitch, roll
  and acceleration 100 times per second over one wire to the Raspberry Pi UART
  (115200 baud, /dev/serial0). Frame (19 bytes, little endian):
      0xAA 0xAA | u8 index | i16 yaw, pitch, roll [0.01 deg] | i16 ax, ay, az [mg] |
      3 reserved bytes | u8 checksum (sum of the bytes index..reserved, mod 256)
* MPU-6050 (GY-521) on the fixed base of the camera heads, on the Raspberry Pi I2C
  bus (address 0x68): roll and pitch from gravity; the gyro shows bumps. It has no
  compass, so the heads' heading (yaw) comes from the camera calibration instead,
  which is also more trustworthy than a compass a few cm from four servo motors.

    python -m droneloc imu                     # both sensors, twice a second
"""
from __future__ import annotations

import math
import struct

RVC_FRAME = 19


def parse_rvc(buf: bytearray) -> list[dict]:
    """Consume complete BNO08x UART-RVC frames from `buf` (in place); return the valid ones."""
    out = []
    while True:
        i = buf.find(b"\xaa\xaa")
        if i < 0:
            del buf[:max(0, len(buf) - 1)]
            return out
        if i:
            del buf[:i]
        if len(buf) < RVC_FRAME:
            return out
        frame = bytes(buf[:RVC_FRAME])
        if sum(frame[2:18]) & 0xFF != frame[18]:
            del buf[:1]                 # false header or corrupt frame: resync
            continue
        del buf[:RVC_FRAME]
        idx = frame[2]
        yaw, pitch, roll, ax, ay, az = struct.unpack_from("<6h", frame, 3)
        out.append({"index": idx, "yaw": yaw / 100, "pitch": pitch / 100, "roll": roll / 100,
                    "acc_g": (ax / 1000, ay / 1000, az / 1000)})


def make_rvc(index: int, yaw: float, pitch: float, roll: float, acc_g=(0.0, 0.0, 1.0)) -> bytes:
    """Build one RVC frame (used by the tests)."""
    body = struct.pack("<B6h3x", index & 0xFF, round(yaw * 100), round(pitch * 100), round(roll * 100),
                       *(round(a * 1000) for a in acc_g))
    return b"\xaa\xaa" + body + bytes([sum(body) & 0xFF])


def tilt_from_acc(ax: float, ay: float, az: float) -> tuple[float, float]:
    """Roll and pitch [deg] of a resting sensor from its accelerometer (any unit)."""
    roll = math.degrees(math.atan2(ay, az))
    pitch = math.degrees(math.atan2(-ax, math.hypot(ay, az)))
    return roll, pitch


class BNO085RVC:
    def __init__(self, port: str = "/dev/serial0"):
        import serial
        self.ser = serial.Serial(port, 115200, timeout=0.1)
        self.buf = bytearray()
        self.last = None
        self.n_bytes = 0            # bytes received so far (diagnosis: 0 = nothing on the wire)

    def read(self) -> dict | None:
        data = self.ser.read(self.ser.in_waiting or 1)
        self.n_bytes += len(data)
        self.buf += data
        frames = parse_rvc(self.buf)
        if frames:
            self.last = frames[-1]
        return self.last


class MPU6050:
    ADDR = 0x68

    def __init__(self, bus: int = 1, addr: int = ADDR):
        from smbus2 import SMBus
        self.bus, self.addr = SMBus(bus), addr
        self.bus.write_byte_data(addr, 0x6B, 0)       # wake up (PWR_MGMT_1)
        self.gyro_bias = (0.0, 0.0, 0.0)

    def calibrate_gyro(self, seconds: float = 1.0) -> tuple[float, float, float]:
        """Average the gyro while the base is still and subtract it from now on
        (an MPU-6050 typically reads a few deg/s at rest)."""
        import time
        acc, n, t0 = [0.0, 0.0, 0.0], 0, time.time()
        while time.time() - t0 < seconds:
            g = [v / 131 for v in self._words(0x43, 3)]
            acc = [a + b for a, b in zip(acc, g)]; n += 1
            time.sleep(0.005)
        self.gyro_bias = tuple(a / max(n, 1) for a in acc)
        return self.gyro_bias

    def _words(self, reg: int, n: int) -> list[int]:
        raw = self.bus.read_i2c_block_data(self.addr, reg, 2 * n)
        return [struct.unpack(">h", bytes(raw[2 * k:2 * k + 2]))[0] for k in range(n)]

    def read(self) -> dict:
        ax, ay, az = (v / 16384 for v in self._words(0x3B, 3))    # +-2 g
        gx, gy, gz = (v / 131 - b for v, b in zip(self._words(0x43, 3), self.gyro_bias))  # +-250 deg/s
        roll, pitch = tilt_from_acc(ax, ay, az)
        return {"roll": roll, "pitch": pitch, "acc_g": (ax, ay, az), "gyro_dps": (gx, gy, gz)}


def monitor(bno_port: str | None = "/dev/serial0", mpu_bus: int | None = 1, seconds: float | None = None) -> None:
    import time
    bno = BNO085RVC(bno_port) if bno_port else None
    mpu = MPU6050(mpu_bus) if mpu_bus is not None else None
    if mpu:
        b = mpu.calibrate_gyro()
        print(f"MPU-6050 gyro bias {b[0]:+.1f} {b[1]:+.1f} {b[2]:+.1f} deg/s (keep the heads base still at start)")
    t0 = time.time()
    print("sphere = BNO085 (yaw/pitch/roll) · heads base = MPU-6050 (roll/pitch, gyro). Ctrl+C to stop.")
    try:
        while seconds is None or time.time() - t0 < seconds:
            t1 = time.time()
            parts = []
            while time.time() - t1 < 0.5:
                b = bno.read() if bno else None
                time.sleep(0.005)
            if bno:
                parts.append(f"sphere: no data ({bno.n_bytes} bytes received)" if b is None else
                             f"sphere yaw {b['yaw']:7.2f} pitch {b['pitch']:6.2f} roll {b['roll']:6.2f}")
            if mpu:
                m = mpu.read()
                g = max(abs(v) for v in m["gyro_dps"])
                parts.append(f"heads roll {m['roll']:6.2f} pitch {m['pitch']:6.2f} gyro {g:5.1f} deg/s"
                             + ("  <- moving!" if g > 3 else ""))
            print(" | ".join(parts), flush=True)
    except KeyboardInterrupt:
        pass
