"""Record all channels of the array interface (e.g. miniDSP MCHStreamer) to one WAV file.

    pip install sounddevice soundfile
    python experiments/record.py --list                       # find the device number
    python experiments/record.py --device 3 --channels 12 --seconds 30 --out run01.wav

All channels come from one interface, i.e. one sampling clock (required: the
simulation shows that 20 ppm clock skew between channels breaks reference
cancellation). Channel order must match the geometry file (array mics first,
reference mics after them).
"""
import argparse

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--list", action="store_true")
ap.add_argument("--device", type=int)
ap.add_argument("--channels", type=int, default=8)
ap.add_argument("--fs", type=int, default=48000)
ap.add_argument("--seconds", type=float, default=30)
ap.add_argument("--out", default="recording.wav")
a = ap.parse_args()
import sounddevice as sd  # noqa: E402
import soundfile as sf  # noqa: E402

if a.list:
    print(sd.query_devices())
else:
    print(f"recording {a.channels} ch at {a.fs} Hz for {a.seconds} s ...")
    x = sd.rec(int(a.seconds * a.fs), samplerate=a.fs, channels=a.channels, device=a.device, dtype="float32")
    sd.wait()
    sf.write(a.out, x, a.fs, subtype="FLOAT")
    print(f"saved {a.out}; per-channel RMS (dBFS):", np.round(20 * np.log10(np.sqrt(np.mean(x ** 2, 0)) + 1e-12), 1))
