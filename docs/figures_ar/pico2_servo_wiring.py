"""Draw docs/figures_ar/pico2_servo_wiring.svg: Pico 2 driving two pan/tilt heads (4 x MG995)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _svg import BLK, GRY, ORG, P5V, PNK, RED, Svg  # noqa: E402

BRN = "#6d4c41"
s = Svg(1800, 1210)
s.t(900, 48, "مخطط توصيل البيكو 2: أربعة سيرفوهات MG995 (رأسان)", 30, bold=True)
s.t(900, 82, "Pico 2 wiring – upper head (GP16 pan, GP17 tilt) and inverted lower head (GP18 pan, GP19 tilt)", 17, GRY)

# ---------------- Pico 2
rows = [("GP16", 21, PNK), ("GP17", 22, PNK), ("GND", 23, BLK), ("GP18", 24, PNK), ("GP19", 25, PNK)]
ys = [200, 240, 280, 320, 360]
s.r(60, 150, 270, 250, "#e8f5e9", "#2e7d32", rx=12, sw=2.5)
s.t(195, 138, "Raspberry Pi Pico (البيكو 2)", 18, "#1b5e20", bold=True)
for (pn, num, col), y in zip(rows, ys):
    s.t(80, y + 5, f"pin {num}", 13, GRY, "start")
    s.t(312, y + 5, pn, 15, col, "end", bold=True)
    s.r(322, y - 6, 12, 12, col, col, rx=2)
s.t(195, 430, "USB إلى الباي (البيانات والكهرباء)", 13, GRY)


def servo(x, y, title, sub):
    s.r(x, y, 240, 120, "#fce4ec", PNK, rx=10, sw=2)
    s.t(x + 120, y + 30, title, 16, PNK, bold=True)
    s.t(x + 120, y + 54, sub, 13, BLK)
    for j, (lab, col) in enumerate([("إشارة: برتقالي", ORG), ("+5V: أحمر", RED), ("GND: بني", BRN)]):
        s.t(x + 120, y + 76 + j * 16, lab, 12, col)


def supply(x, y, title):
    s.r(x, y, 280, 100, "#fff3e0", P5V, rx=10, sw=2)
    s.t(x + 140, y + 32, title, 16, P5V, bold=True)
    s.t(x + 140, y + 58, "5V / 5A", 15, P5V, bold=True)
    s.t(x + 140, y + 82, "+5V (أعلى) · GND (أسفل)", 12, GRY)


def cap(x, yp, yg):
    s.c(x, yp, 5, P5V); s.c(x, yg, 5, BLK)
    m = (yp + yg) / 2
    s.ln([(x, yp), (x, m - 5)], P5V, 2); s.ln([(x - 13, m - 5), (x + 13, m - 5)], BLK, 3)
    s.ln([(x - 13, m + 4), (x + 13, m + 4)], BLK, 3); s.ln([(x, m + 4), (x, yg)], BLK, 2)
    s.t(x - 18, m + 5, "1000µF", 12, BLK, "end", bold=True)


# ---------------- upper head (servo boxes above their buses)
s.t(1300, 135, "الرأس العلوي — نصف الكرة العلوي (الكاميرا 1)", 18, PNK, bold=True)
servo(700, 150, "سيرفو Tilt العلوي", "يحرّك الكاميرا رأسياً")
servo(1000, 150, "سيرفو Pan العلوي", "يدور أفقياً (x,y)")
UP5, UPG = 330, 370
s.ln([(620, UP5), (1450, UP5)], P5V, 3.4); s.ln([(620, UPG), (1450, UPG)], BLK, 3.4)
s.t(628, UP5 - 8, "+5V", 13, P5V, "start", bold=True); s.t(628, UPG + 18, "GND", 13, BLK, "start", bold=True)
supply(1450, 290, "مزوّد الرأس العلوي")
cap(1400, UP5, UPG)
for bx in (700, 1000):
    s.ln([(bx + 160, 270), (bx + 160, UP5)], P5V, 2.6); s.c(bx + 160, UP5, 5, P5V)
    s.ln([(bx + 200, 270), (bx + 200, UPG)], BRN, 2.6); s.c(bx + 200, UPG, 5, BLK)
# signals: GP17 straight into the near (tilt) servo, GP16 over the top to the far (pan) servo
s.ln([(334, ys[1]), (700, ys[1])], PNK, 2.6); s.c(700, ys[1], 4, PNK)
s.ln([(334, ys[0]), (560, ys[0]), (560, 125), (1060, 125), (1060, 150)], PNK, 2.6); s.c(1060, 150, 4, PNK)

# ---------------- lower head (inverted: buses above the servo boxes)
LO5, LOG = 600, 560
s.t(1300, 530, "الرأس السفلي (مقلوب) — نصف الكرة السفلي (الكاميرا 2)", 18, PNK, bold=True)
s.ln([(620, LOG), (1450, LOG)], BLK, 3.4); s.ln([(620, LO5), (1450, LO5)], P5V, 3.4)
s.t(628, LOG - 8, "GND", 13, BLK, "start", bold=True); s.t(628, LO5 + 18, "+5V", 13, P5V, "start", bold=True)
supply(1450, 545, "مزوّد الرأس السفلي")
cap(1400, LO5, LOG)
servo(700, 650, "سيرفو Pan السفلي", "يدور أفقياً (x,y)")
servo(1000, 650, "سيرفو Tilt السفلي", "يحرّك الكاميرا رأسياً")
for bx in (700, 1000):
    s.ln([(bx + 160, 650), (bx + 160, LO5)], P5V, 2.6); s.c(bx + 160, LO5, 5, P5V)
    s.ln([(bx + 200, 650), (bx + 200, LOG)], BRN, 2.6); s.c(bx + 200, LOG, 5, BLK)
s.ln([(334, ys[3]), (500, ys[3]), (500, 700), (700, 700)], PNK, 2.6); s.c(700, 700, 4, PNK)
s.ln([(334, ys[4]), (460, ys[4]), (460, 820), (1060, 820), (1060, 770)], PNK, 2.6); s.c(1060, 770, 4, PNK)

# ---------------- common ground
s.ln([(334, ys[2]), (590, ys[2]), (590, UPG), (620, UPG)], BLK, 2.6, dash="8,5")
s.ln([(590, UPG), (590, LOG), (620, LOG)], BLK, 2.6, dash="8,5")
s.c(590, UPG, 4, BLK)
s.t(600, 470, "أرضي مشترك", 13, BLK, "start", bold=True)

# ---------------- pin labels on the wires
for (x, y, lab) in [(450, ys[1] - 8, "GP17 → upper tilt"), (450, 117, "GP16 → upper pan"),
                    (600, 692, "GP18 → lower pan"), (760, 840, "GP19 → lower tilt")]:
    s.t(x, y, lab, 13, PNK, "middle", bold=True)

# ---------------- mapping and rules
Y = 900
s.ln([(40, Y - 20), (1760, Y - 20)], "#ddd", 2)
s.t(1760, Y + 12, "كيف يُحوَّل الاتجاه (السمت az، الارتفاع el) إلى زوايا السيرفو:", 17, BLK, "end", bold=True)
lines = [("upper head (el ≥ 0):  az in [0,180):  pan = az,  tilt = el   |   az in [180,360):  pan = az − 180,  tilt = 180 − el", BLK),
         ("lower head (inverted, el < 0):  az' = −az,  el' = −el,  then the same rule with az', el'", BLK),
         ("tilt 0° = horizontal along the pan direction, 90° = straight up (down for the lower head), 180° = horizontal behind", GRY)]
for k, (txt, col) in enumerate(lines):
    s.t(60, Y + 50 + k * 28, txt, 15, col, "start")
rules = [("• اختيار الرأس: الارتفاع فوق +5° للعلوي، وتحت −5° للسفلي، وبينهما يبقى الرأس الحالي (حتى لا يتذبذب عند الأفق).", BLK),
         ("• المعايرة تحدد إزاحة الصفر واتجاه دوران كل رأس؛ الرأس المقلوب يدور فيه Pan بالعكس.", BLK),
         ("• كل MG995 قد يسحب 2–2.5A عند البدء: مزوّد 5V/5A لكل رأس، وأسلاك تغذية سميكة.", BLK),
         ("• لا تُوصل 5V بأي طرف في البيكو؛ الإشارة 3.3V من البيكو تكفي عادةً لـ MG995.", RED)]
for k, (txt, col) in enumerate(rules):
    s.t(1760, Y + 150 + k * 28, txt, 15, col, "end", bold=(col == RED))
s.save(str(Path(__file__).with_suffix(".svg")))
