"""Draw docs/figures_ar/imu_wiring.svg: BNO085 (sphere, UART-RVC) and MPU-6050 GY-521 (heads base, I2C)
on the Raspberry Pi 40-pin header."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _svg import BLK, BLU, GRN, GRY, ORG, PUR, RED, Svg  # noqa: E402

s = Svg(1800, 1080)
s.t(900, 48, "توصيل البوصلتين بالـ Raspberry Pi", 30, bold=True)
s.t(900, 82, "BNO085 on the sphere (UART-RVC → RXD) · MPU-6050 GY-521 on the heads base (I2C)", 17, GRY)

# Raspberry Pi header, pins 1..20 (odd left, even right), pin 1 at the top
names = {1: "3V3", 2: "5V", 3: "GPIO2 SDA", 4: "5V", 5: "GPIO3 SCL", 6: "GND", 7: "GPIO4", 8: "GPIO14 TXD",
         9: "GND", 10: "GPIO15 RXD", 11: "GPIO17", 12: "GPIO18", 13: "GPIO27", 14: "GND", 15: "GPIO22",
         16: "GPIO23", 17: "3V3", 18: "GPIO24", 19: "GPIO10", 20: "GND"}
used = {1: RED, 6: BLK, 10: ORG, 17: RED, 9: BLK, 3: BLU, 5: PUR}
HX, HY, DY = 760, 170, 46
s.r(HX - 150, HY - 50, 300, 10 * DY + 70, "#2e7d32", rx=14, sw=2)
s.t(HX, HY - 22, "Raspberry Pi — الأطراف 1 إلى 20", 15, "#fff", bold=True)
pin_xy = {}
for n in range(1, 21):
    row, right = (n - 1) // 2, n % 2 == 0
    x, y = HX + (22 if right else -22), HY + 15 + row * DY
    col = used.get(n)
    s.c(x, y, 9, col or "#e0e0e0", "#333", 1.5)
    s.t(x, y + 5, str(n), 10, "#fff" if col else "#333", bold=True)
    s.t(x + (34 if right else -34), y + 5, names[n], 13, col or "#c8e6c9", "start" if right else "end", bold=bool(col))
    pin_xy[n] = (x + (9 if right else -9), y)
s.t(HX, HY + 10 * DY + 40, "الطرف 1 بجانب فتحة بطاقة الذاكرة (المربع)", 13, GRY)

# ---------------- BNO085 (left) on the sphere
BX, BY = 70, 160
s.r(BX, BY, 470, 330, "#ede7f6", "#4527a0", rx=12, sw=2.5)
s.t(BX + 235, BY + 32, "BNO085 (Adafruit 4754)", 18, "#4527a0", bold=True)
s.t(BX + 235, BY + 58, "على كرة الميكروفونات", 15, BLK, bold=True)
bpins = [("VIN", RED, "طرف 1 (3V3)"), ("GND", BLK, "طرف 6 (GND)"), ("SDA (خرج RVC)", ORG, "طرف 10 (RXD)"),
         ("P0", RED, "إلى 3V3 (مع VIN)")]
for k, (lab, col, to) in enumerate(bpins):
    y = BY + 110 + k * 50
    s.r(BX + 30, y - 8, 16, 16, col, col, rx=3)
    s.t(BX + 58, y + 6, lab, 15, col, "start", bold=True)
    s.ln([(BX + 230, y), (BX + 300, y)], col, 3); s.arrow(BX + 306, y, 1, 0, col, 12)
    s.t(BX + 455, y + 6, to, 15, col, "end", bold=True)
s.t(BX + 235, BY + 305, "P0 إلى 3V3 يختار نمط UART-RVC", 13, GRY)

# ---------------- MPU-6050 GY-521 (right) on the heads base
MX, MY = 1260, 160
s.r(MX, MY, 470, 330, "#e3f2fd", "#1565c0", rx=12, sw=2.5)
s.t(MX + 235, MY + 32, "MPU-6050 (GY-521)", 18, "#1565c0", bold=True)
s.t(MX + 235, MY + 58, "على القاعدة الثابتة للرأسين", 15, BLK, bold=True)
mpins = [("VCC", RED, "طرف 17 (3V3)"), ("GND", BLK, "طرف 9 (GND)"), ("SDA", BLU, "طرف 3 (SDA)"),
         ("SCL", PUR, "طرف 5 (SCL)"), ("AD0", BLK, "GND (العنوان 0x68)")]
for k, (lab, col, to) in enumerate(mpins):
    y = MY + 100 + k * 44
    s.r(MX + 30, y - 8, 16, 16, col, col, rx=3)
    s.t(MX + 58, y + 6, lab, 15, col, "start", bold=True)
    s.ln([(MX + 150, y), (MX + 220, y)], col, 3); s.arrow(MX + 226, y, 1, 0, col, 12)
    s.t(MX + 455, y + 6, to, 15, col, "end", bold=True)

# ---------------- notes
Y = 700
s.ln([(40, Y - 30), (1760, Y - 30)], "#ddd", 2)
notes = [("قبل التوصيل: فعّل I2C والمنفذ التسلسلي في الباي (sudo raspi-config ← Interface Options)، ثم أعد التشغيل.", BLK, True),
         ("• BNO085: نمط UART-RVC يرسل الاتجاه الجاهز (yaw/pitch/roll) 100 مرة/ثانية بسرعة 115200 على سلك واحد إلى RXD (الطرف 10).", BLK, False),
         ("• تأكد من دليل Adafruit للوحة 4754 أن خرج RVC هو طرف SDA في لوحتك، وأن P0 يوصل إلى 3V3.", GRY, False),
         ("• MPU-6050: الميل (roll/pitch) من الجاذبية، والجيروسكوب يكشف أي اهتزاز أو حركة للحامل. العنوان 0x68.", BLK, False),
         ("• ثبّت BNO085 بإحكام على الكرة ومحاوره موازية لـ x,y,z، وMPU-6050 على القاعدة الثابتة وليس على الأجزاء المتحركة.", BLK, False),
         ("• أبعد البوصلتين 10–15 سم على الأقل عن السيرفوهات وأسلاك تغذيتها، واجعل أسلاك I2C أقصر من 1 م.", BLK, False),
         ("• التغذية 3.3V فقط من الباي (الطرفان 1 و17)، وليس 5V.", RED, True)]
for k, (txt, col, b) in enumerate(notes):
    s.t(1760, Y + k * 40, txt, 15, col, "end", bold=b)
s.save(str(Path(__file__).with_suffix(".svg")))
