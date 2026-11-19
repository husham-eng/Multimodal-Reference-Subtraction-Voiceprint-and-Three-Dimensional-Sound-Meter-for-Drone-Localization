"""Draw docs/figures_ar/servo_pico_wiring.svg: the four MG995 servos of the two camera heads on Pico 2,
named as in the CAD drawing (X,Y servo = pan, Z servo = tilt)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _svg import BLK, GRY, ORG, P5V, PNK, RED, Svg  # noqa: E402

BRN = "#6d4c41"
s = Svg(1800, 1000)
s.t(900, 46, "توصيل السيرفوهات الأربعة بالبيكو 2 (بأسماء التصميم: سيرفو X,Y وسيرفو Z)", 28, bold=True)
s.t(900, 80, "Pico 2 drawn rotated (USB connector at the bottom) so that pins 21-25 face the servos in the same order", 16, GRY)

# ---------------- Pico 2, rotated 180 deg: left column = pins 21..40 from the top
PX, PY, PW = 1270, 150, 200
ys = [200 + k * 32 for k in range(20)]
s.r(PX, PY, PW, ys[-1] - PY + 50, "#2e7d32", "#1b5e20", rx=12, sw=2.5)
s.r(PX + PW / 2 - 28, ys[-1] + 38, 56, 26, "#c0c0c0", "#555", rx=3); s.t(PX + PW / 2, ys[-1] + 57, "USB", 12)
s.t(PX + PW / 2, PY - 14, "البيكو 2 (مقلوب)", 18, "#1b5e20", bold=True)
left = {21: ("GP16", PNK), 22: ("GP17", PNK), 23: ("GND", BLK), 24: ("GP18", PNK), 25: ("GP19", PNK),
        28: ("GND", BLK), 33: ("GND", BLK), 38: ("GND", BLK), 36: ("3V3(OUT)", None), 40: ("VBUS", None)}
pin_y = {}
for k, y in enumerate(ys):
    n = 21 + k
    name, col = left.get(n, (f"GP{[None]*0 or ''}", None))
    used = n in (21, 22, 24, 25, 38)
    s.c(PX + 18, y, 7, (col or "#e0e0e0") if used else "#e0e0e0", "#333")
    s.t(PX + 34, y + 5, f"{n}" + (f"  {name}" if n in left else ""), 12, "#fff" if used else "#c8e6c9", "start", bold=used)
    s.c(PX + PW - 18, y, 7, "#e0e0e0", "#333")
    s.t(PX + PW - 30, y + 5, str(20 - k), 12, "#c8e6c9", "end")
    pin_y[n] = y

# ---------------- servos (named as in the CAD drawing)
servos = [("سيرفو X,Y العلوي", "Pan · القناة 0", 130, 21, 1240),
          ("سيرفو Z العلوي", "Tilt · القناة 1", 275, 22, 1060),
          ("سيرفو X,Y السفلي", "Pan · القناة 2", 505, 24, 1110),
          ("سيرفو Z السفلي", "Tilt · القناة 3", 645, 25, 1160)]
SX, SW, SH = 330, 270, 110
for title, sub, y0, pin, lane in servos:
    s.r(SX, y0, SW, SH, "#fce4ec", PNK, rx=10, sw=2)
    s.t(SX + SW / 2, y0 + 38, title, 17, PNK, bold=True)
    s.t(SX + SW / 2, y0 + 64, sub, 14, BLK)
    s.t(SX + SW / 2, y0 + 90, "MG995 (180°)", 13, GRY)
    ty = y0 + SH / 2
    # signal (orange wire of the servo) to the Pico pin, on its own vertical lane
    s.ln([(SX + SW, ty), (lane, ty), (lane, pin_y[pin]), (PX + 11, pin_y[pin])], ORG, 3)
    s.c(SX + SW, ty, 5, ORG); s.c(PX + 11, pin_y[pin], 4, ORG)
    s.t(SX + SW + 18, ty - 10, f"برتقالي ← طرف {pin} ({left[pin][0]})", 13, ORG, "start", bold=True)
    # power on the left edge
    for dy, col, lab in [(35, RED, "+5V"), (75, BRN, "GND")]:
        s.c(SX, y0 + dy, 5, col)
        s.t(SX + 8, y0 + dy + 5, lab, 12, col, "start", bold=True)

# ---------------- one 5 V / 5 A supply per head, with its capacitor
for (y0, y1, name) in [(130, 385, "مزوّد الرأس العلوي"), (505, 755, "مزوّد الرأس السفلي")]:
    s.r(40, y0 + 40, 160, y1 - y0 - 80, "#fff3e0", P5V, rx=10, sw=2)
    mid = (y0 + y1) / 2
    s.t(120, mid - 22, name, 13, P5V, bold=True)
    s.t(120, mid + 2, "5V / 5A", 15, P5V, bold=True)
    s.t(120, mid + 26, "+ 1000µF", 12, P5V)
    s.ln([(200, y0 + 60), (240, y0 + 60), (240, y1 - 20)], RED, 3.2)      # +5V bar
    s.ln([(200, y1 - 60), (275, y1 - 60), (275, y0 + 20)], BRN, 3.2)      # GND bar
    s.t(236, y0 + 52, "+5V", 12, RED, "end", bold=True)
for title, sub, y0, pin, lane in servos:
    s.ln([(240, y0 + 35), (SX, y0 + 35)], RED, 2.6); s.c(240, y0 + 35, 4.5, RED)
    s.ln([(275, y0 + 75), (SX, y0 + 75)], BRN, 2.6); s.c(275, y0 + 75, 4.5, BRN)

# ---------------- common ground: Pico GND (pin 38) to both supplies
gy = pin_y[38]
s.ln([(PX + 11, gy), (PX - 30, gy), (PX - 30, 880), (20, 880), (20, 345 - 20), (40, 325)], BLK, 2.6, dash="8,5")
s.ln([(20, 695), (40, 695)], BLK, 2.6, dash="8,5")
s.c(20, 695, 4, BLK)
s.t(640, 870, "أرضي مشترك: أي طرف GND في البيكو 2 (هنا الطرف 38، أو الطرف 23) ← أرضي المزوّدين", 14, BLK, "middle", bold=True)

# ---------------- notes
notes = [("• كل سيرفو له 3 أسلاك: البرتقالي = الإشارة إلى البيكو، والأحمر = +5V من مزوّد رأسه، والبني = GND.", BLK),
         ("• لا يوصل الأحمر بالبيكو أبداً. ولكل رأس مزوّده، وأرضيّ المزوّدين موصولان بأرضي البيكو 2.", RED),
         ("• الخطوط المتقاطعة دون نقطة غير موصولة. البيكو مرسوم مقلوباً فقط لتوضيح الرسم.", GRY)]
for k, (txt, col) in enumerate(notes):
    s.t(1780, 915 + k * 28, txt, 14, col, "end", bold=(col == RED))
s.save(str(Path(__file__).with_suffix(".svg")))
