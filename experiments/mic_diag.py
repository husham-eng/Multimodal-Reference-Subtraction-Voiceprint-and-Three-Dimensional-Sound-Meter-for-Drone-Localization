"""Quick look inside a Pico recording, to tell real sound from wiring / timing garbage.

    python experiments/mic_diag.py test01.wav
"""
import sys

import numpy as np
import soundfile as sf

x, fs = sf.read(sys.argv[1], dtype="int16", always_2d=True)
print(f"{x.shape[0]} frames, {x.shape[1]} channels, {fs} Hz")
print("ch   min    max  clip%  mean    rms_dBFS  zc/s   peak_Hz  corr(next)  first samples (hex)")
for ch in range(x.shape[1]):
    v = x[:, ch].astype(float)
    if not v.any():
        print(f"{ch:2d}  all zero")
        continue
    clip = 100 * np.mean(np.abs(x[:, ch]) >= 32767)
    ac = v - v.mean()
    rms = 20 * np.log10(np.sqrt(np.mean(ac ** 2)) / 32768 + 1e-12)
    zc = np.mean(np.diff(np.sign(ac)) != 0) * fs
    spec = np.abs(np.fft.rfft(ac * np.hanning(len(ac))))
    peak = np.fft.rfftfreq(len(ac), 1 / fs)[np.argmax(spec[1:]) + 1]
    nxt = ch + 1 if ch % 2 == 0 else ch - 1
    w = x[:, nxt].astype(float)
    corr = np.corrcoef(ac, w - w.mean())[0, 1] if w.std() > 0 else float("nan")
    hexs = " ".join(f"{int(s) & 0xFFFF:04x}" for s in x[1000:1008, ch])
    print(f"{ch:2d} {int(v.min()):6d} {int(v.max()):6d} {clip:5.1f} {v.mean():7.0f} {rms:8.1f} "
          f"{zc:6.0f} {peak:8.0f} {corr:10.2f}  {hexs}")

# Debug firmware (pico_mic_array_debug.uf2): channels 6..9 = raw I2S words of data line 0.
if x.shape[1] >= 10 and x[:, 6:10].any():
    u = x[:, 6:10].astype(np.int64) & 0xFFFF
    for name, hi, lo in (("L (x+)", 0, 1), ("R (x-)", 2, 3)):
        w = (u[:, hi] << 16) | u[:, lo]
        print(f"\nraw words, line 0 {name}: bits 31..8 = sample (MSB first), 7..0 should be 0")
        for v in w[1000:1012]:
            b = f"{int(v):032b}"
            print(f"  {b[:24]} {b[24:]}")
        print(f"  low 8 bits non-zero in {100 * np.mean((w & 0xFF) != 0):.0f}% of words")
