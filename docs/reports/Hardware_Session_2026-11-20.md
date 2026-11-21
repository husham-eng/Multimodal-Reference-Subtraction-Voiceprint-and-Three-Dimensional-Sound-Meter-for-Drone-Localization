# First real-hardware session - 20 Nov 2026

Raspberry Pi (Raspberry Pi OS bullseye, armhf user space, aarch64 kernel), accessed over TeamViewer.
Branch `claude/epic-ride-9fqd2p`.

## Results

| Part | Status | Notes |
|---|---|---|
| Pico 1, microphone array | Works | 6 sphere mics on GP2-GP4. Silence about -58..-55 dBFS (above 100 Hz); a clap lifts all six; blowing on +x lifts channel 0 only, and -x (sphere shadow) is lowest. |
| Pico 2, servo pointer | Works | 50 Hz pulses checked with `experiments/pulse_check.py`. |
| Servos (4 x MG995) | Work | All positional (180 deg). Measured range 600..2400 us on every channel, about 180 deg, smooth, no buzzing. Limits saved in `pointer_cal.json` on the Pi. |
| Cameras (2 x Logitech Brio 100) | Work | `cam_a` = serial 2629ZB52EJT8 = **upper head**; `cam_b` = serial 2629ZBT2TAK8 = **lower head**. The first frame is dark: use `fswebcam -S 30`. |
| MPU-6050 (heads base) | Works | 0x68 on I2C bus 1. Mounted about 31 deg roll / 6 deg pitch (zero it in calibration). Gyro bias about +6.4/+0.1/-3.0 deg/s; now removed at start. |
| BNO085 (sphere, Adafruit 4754) | Works | UART-RVC on /dev/serial0 (ttyS0), wired directly without a breadboard: VIN to pin 1, GND to pin 6, SDA to pin 10, **P0 to the board's own 3Vo**. Data at 100 Hz, follows tilting. |

Servo directions, with each servo released before every step:

| Ch | Servo | 600 us | 2400 us |
|---|---|---|---|
| 0 | upper pan (GP16, pin 21) | right | left |
| 1 | upper tilt (GP17, pin 22) | back | forward |
| 2 | lower pan (GP18, pin 24) | left | right |
| 3 | lower tilt (GP19, pin 25) | forward | back |

The lower head runs mirrored relative to the upper one, as expected for an inverted head. Confirm it during the camera calibration.

## Problems found and fixed

1. **All mic channels were full-scale noise.** The microphones were driving SD: the channels went silent when SCK or WS was removed. The raw words from `pico_mic_array_debug.uf2` showed that these INMP441s change SD shortly *after* the SCK rising edge, not on the falling edge. The firmware sampled right at the rising edge, so it caught every bit in mid-transition. Fixes in the firmware:
   - It samples about 117 ns after the rising edge.
   - It re-synchronises on every WS edge.
   - It uses soft SCK/WS edges.
   - It takes the sample from word bits 31..8, because the MSB is read at edge 0.
2. **Loose WS jumper on Pico 1:** pin 12 had lost contact.
3. **Servos limp:**
   - There was no common ground between the servo supply and Pico 2.
   - The power bank does not deliver power to the servos: it probably switches off at low load. A phone wall charger works for one servo at a time.
   - The power wiring inside the heads does not reach the servos. Each servo was tested with short direct wires.
4. `pyserial` and `smbus2` were missing from `requirements.txt`.
5. **BNO085 sent 0 bytes:** the P0 jumper was on the neighbouring BT pin, so the sensor stayed in I2C mode. A Pi UART loopback test (pin 8 to pin 10) proved the Pi side was fine. Note: BNO085 reads P0 only at power-up.
6. **MPU-6050 dropped out intermittently:** AD0 was floating. It is now tied to a Pi GND pin. Both sensors then read steadily together.
7. The Pi reported past under-voltage (`throttled=0x50000`): use the official 5 V 3 A supply.

## To do

- Repair the power wiring of both heads. Use a 5-6 V supply rated 5 A or more for all four servos, with its GND tied to Pico 2 GND.
- Run the head direction calibration with the cameras (runbook 3.4), then the live test (phase 6).
- Connect the reference microphones (channels 6-11).

## New tools

- `experiments/check_hardware.sh`: read-only check of every part. It writes `hw_check.txt`.
- `experiments/mic_diag.py`: per-channel statistics of a recording, and raw words from the debug build.
- `experiments/pulse_check.py`: measures servo pulses with a Pi GPIO.
- `python -m droneloc pointer limits CH MIN MAX`: sets a servo's range in `pointer_cal.json`.
- `python -m droneloc pointer sweep CH FROM TO STEP`: steps a servo without releasing it between steps.
