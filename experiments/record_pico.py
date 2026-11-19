"""Record the low-cost Pico microphone array (hardware/pico_mic_array) to one WAV file.

    pip install pyserial soundfile numpy
    python experiments/record_pico.py --check                 # live level of every channel
    python experiments/record_pico.py --seconds 30 --out run01.wav

All 12 channels come from one Pico with one shared I2S clock, so they are
sample-synchronous (required for reference cancellation). Channel order:
0-5 sphere mics (+x, -x, +y, -y, +z, -z), 6-9 rotor references, 10 station
reference, 11 spare. The WAV is at 15625 Hz; droneloc resamples it itself.
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from droneloc.pico import PacketReader, find_port, level_db  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--port", help="serial port (default: auto-detect the Pico, e.g. COM5 or /dev/ttyACM0)")
ap.add_argument("--seconds", type=float, default=30)
ap.add_argument("--out", default="recording.wav")
ap.add_argument("--check", action="store_true", help="print the level of every channel twice a second")
a = ap.parse_args()

import serial  # noqa: E402

port = a.port or find_port()
if not port:
    sys.exit("Pico not found: is it plugged in and flashed with pico_mic_array.uf2? (or give --port)")
ser = serial.Serial(port, timeout=0.2)
try:
    ser.dtr = True  # the Pico only streams while the port is open (DTR set)
except OSError:
    pass
rd = PacketReader()
print(f"reading {port} ...")

if a.check:
    print("channel levels in dBFS (silence ~ -70..-55, speaking near the mic ~ -40..-20, "
          "-90 or lower = mic not connected / wrong wiring). Ctrl+C to stop.")
    try:
        while True:
            blk, t0 = [], time.time()
            while time.time() - t0 < 0.5:
                blk += [f for _, _, _, f in rd.feed(ser.read(4096))]
            if not blk:
                print("no data from the Pico"); continue
            lv = level_db(np.concatenate(blk))
            print(" ".join(f"{i:2d}:{v:6.1f}" for i, v in enumerate(lv)),
                  f"| lost {rd.lost} bad {rd.bad}")
    except KeyboardInterrupt:
        pass
    sys.exit(0)

import soundfile as sf  # noqa: E402

frames, fs, n, dropped0, dropped = [], None, 0, None, 0
t_end = None
while True:
    for seq, dr, f_s, f in rd.feed(ser.read(8192)):
        if fs is None:
            fs, dropped0 = f_s, dr
            t_end = time.time() + a.seconds
            print(f"{f.shape[1]} channels at {fs} Hz, recording {a.seconds} s ...")
        dropped = dr - dropped0
        frames.append(f); n += len(f)
    if fs is not None and n >= a.seconds * fs:
        break
    if fs is None and rd.bad > 50:
        sys.exit("only corrupt data received; check the USB cable / port")
    if t_end and time.time() > t_end + 5:
        print("warning: the Pico delivered less data than expected"); break
ser.close()
x = np.concatenate(frames)[: int(a.seconds * fs)]
sf.write(a.out, x, fs, subtype="PCM_16")
print(f"wrote {a.out}: {x.shape[0]} samples x {x.shape[1]} channels at {fs} Hz")
print(f"packets lost on USB: {rd.lost} | corrupt: {rd.bad} | frames dropped on the Pico: {dropped}")
if rd.lost or dropped:
    print("WARNING: data were lost (filled with zeros). Use a direct USB port (no hub) and close other programs.")
