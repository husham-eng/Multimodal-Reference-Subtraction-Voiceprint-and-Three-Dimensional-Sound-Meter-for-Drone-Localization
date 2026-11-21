#!/usr/bin/env bash
# Read-only hardware check for the Raspberry Pi session.
# Nothing here moves a servo: the pointer is only asked for its status.
# Usage (from the code folder, venv active):  bash experiments/check_hardware.sh
# The full report is also saved to hw_check.txt.

cd "$(dirname "$0")/.." || exit 1
exec > >(tee hw_check.txt) 2>&1

sec() { echo; echo "===== $1 ====="; }

sec "System"
date
uname -m
python --version
git log --oneline -1
vcgencmd get_throttled 2>/dev/null || echo "vcgencmd not available"

sec "1. USB devices (Picos 2e8a, cameras)"
lsusb
echo "-- Picos:"
lsusb | grep -i 2e8a || echo "NO PICO FOUND"
echo "-- serial ports:"
ls -l /dev/ttyACM* 2>/dev/null || echo "no /dev/ttyACM*"
python - <<'EOF'
try:
    from serial.tools import list_ports
    for p in list_ports.comports():
        if p.vid == 0x2E8A:
            print(f"{p.device}: {p.product!r} serial={p.serial_number}")
except Exception as e:
    print("pyserial error:", e)
EOF
id -nG | grep -qw dialout && echo "user in dialout: yes" || echo "user in dialout: NO (log out/in or reboot)"

sec "2. Pico 1 - microphones (5 s, stay quiet)"
timeout 5 python experiments/record_pico.py --check || true

sec "3. Pico 2 - servo pointer status (no movement)"
ls -l pointer_cal.json 2>/dev/null || echo "pointer_cal.json missing (run: python -m droneloc pointer init-cal)"
timeout 10 python -m droneloc pointer status || echo "pointer status FAILED"

sec "4. Cameras"
ls -l /dev/v4l/by-id/ 2>/dev/null || echo "no cameras in /dev/v4l/by-id"
for d in /dev/v4l/by-id/*index0; do
  [ -e "$d" ] || continue
  out="cam_$(basename "$d" | tr -c 'A-Za-z0-9' '_' | cut -c1-40).jpg"
  timeout 15 fswebcam -d "$d" -r 1280x720 --no-banner -q "$out" \
    && echo "OK  $out  ($(stat -c %s "$out") bytes)" || echo "FAILED $d"
done

sec "5. Orientation sensors"
echo "-- I2C bus 1 (MPU-6050 should show 68):"
i2cdetect -y 1 2>&1 || echo "i2cdetect failed (I2C enabled? i2c-tools installed?)"
echo "-- UART for BNO085:"
ls -l /dev/serial0 2>/dev/null || echo "/dev/serial0 missing (enable serial hardware in raspi-config)"
timeout 8 python -m droneloc imu --seconds 4 || echo "imu FAILED"

sec "Done - report saved to hw_check.txt"
