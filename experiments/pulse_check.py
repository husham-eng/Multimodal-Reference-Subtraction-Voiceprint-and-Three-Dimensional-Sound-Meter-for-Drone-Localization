"""Measure servo pulses with the Raspberry Pi itself (no multimeter needed).

Wire a Pico 2 servo output (e.g. pin 21 = GP16) to Pi GPIO17 (physical pin 11).
The Pico and the Pi already share ground through the USB cable.
Then, in another terminal, drive the channel (e.g. pointer servo 0 1300 --hold 10)
and run, with the system Python that has RPi.GPIO:

    /usr/bin/python3 experiments/pulse_check.py            # GPIO17, 3 s
    /usr/bin/python3 experiments/pulse_check.py 27 5       # GPIO27, 5 s

Expected while a channel is driven: ~50 pulses/s, width = the commanded us (e.g. 1300).
"""
import sys
import time

import RPi.GPIO as GPIO

pin = int(sys.argv[1]) if len(sys.argv) > 1 else 17
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
GPIO.setmode(GPIO.BCM)
GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
edges = []
GPIO.add_event_detect(pin, GPIO.BOTH, callback=lambda ch: edges.append((time.perf_counter(), GPIO.input(ch))))
time.sleep(secs)
GPIO.remove_event_detect(pin)
level = GPIO.input(pin)
GPIO.cleanup(pin)

rises = [t for t, v in edges if v == 1]
widths = []
for (t0, v0), (t1, v1) in zip(edges, edges[1:]):
    if v0 == 1 and v1 == 0:
        widths.append((t1 - t0) * 1e6)
print(f"GPIO{pin}: {len(edges)} edges in {secs:.0f} s, {len(rises) / secs:.1f} pulses/s, line now {'HIGH' if level else 'LOW'}")
if widths:
    widths.sort()
    print(f"pulse width: median {widths[len(widths) // 2]:.0f} us (min {widths[0]:.0f}, max {widths[-1]:.0f})")
else:
    print("no pulses seen: the Pico output does not reach this pin (wrong pin / broken wire / channel not driven)")
