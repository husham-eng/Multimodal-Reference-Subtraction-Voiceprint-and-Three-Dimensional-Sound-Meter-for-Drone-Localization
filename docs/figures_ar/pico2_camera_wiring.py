"""Draw docs/figures_ar/pico2_camera_wiring.svg: Pico 2 + OV7670 (no FIFO) + pan/tilt servos + laser."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _svg import BLK, BLU, CYN, GRN, GRY, ORG, P5V, PNK, PUR, RED, Svg  # noqa: E402

s = Svg(1800, 1440)
s.t(900, 48, "مخطط توصيل البيكو 2: كاميرا OV7670 + سيرفوهان + ليزر", 30, bold=True)
s.t(900, 82, "Pico 2 wiring – camera (no FIFO, 18 pins), pan/tilt servos and laser", 17, GRY)

# rows: (pico pin label, pin number, camera/part pin, colour)
rows = [("3V3(OUT)", 36, "3V3", RED), ("GND", 38, "GND", BLK),
        ("GP13", 17, "SIOC", PUR), ("GP12", 16, "SIOD", PUR),
        ("GP10", 14, "VSYNC", BLU), ("GP9", 12, "HREF", BLU), ("GP8", 11, "PCLK", ORG), ("GP21", 27, "XCLK", ORG),
        ("GP7", 10, "D7", GRN), ("GP6", 9, "D6", GRN), ("GP5", 7, "D5", GRN), ("GP4", 6, "D4", GRN),
        ("GP3", 5, "D3", GRN), ("GP2", 4, "D2", GRN), ("GP1", 2, "D1", GRN), ("GP0", 1, "D0", GRN),
        ("GP14", 19, "RESET", GRY)]
X0, Y0, DY = 330, 150, 38
PXR = X0                     # right edge of the Pico block
CX = 1120                    # left edge of the camera block
ys = [Y0 + 30 + k * DY for k in range(len(rows))]
ypw = ys[-1] + DY            # PWDN row (camera only, to GND)
# Pico block (part 1)
s.r(60, Y0, PXR - 60, ypw - Y0 + 20, "#e8f5e9", "#2e7d32", rx=12, sw=2.5)
s.t(195, Y0 - 12, "Raspberry Pi Pico (البيكو 2)", 19, "#1b5e20", bold=True)
# camera block
s.r(CX, Y0, 230, ypw - Y0 + 20, "#e3f2fd", "#1565c0", rx=12, sw=2.5)
s.t(CX + 115, Y0 - 12, "OV7670 (دون FIFO)", 19, "#0d47a1", bold=True)
for (pn, num, cp, col), y in zip(rows, ys):
    s.t(80, y + 5, f"pin {num}", 13, GRY, "start")
    s.t(PXR - 18, y + 5, pn, 15, col, "end", bold=True)
    s.r(PXR - 8, y - 6, 12, 12, col, col, rx=2)
    s.ln([(PXR + 4, y), (CX - 4, y)], col, 2.6)
    s.r(CX - 6, y - 6, 12, 12, col, col, rx=2)
    s.t(CX + 18, y + 5, cp, 15, col, "start", bold=True)
# PWDN to GND
s.t(CX + 18, ypw + 5, "PWDN", 15, BLK, "start", bold=True)
s.r(CX - 6, ypw - 6, 12, 12, BLK, BLK, rx=2)
s.ln([(1010, ys[1]), (1010, ypw), (CX - 4, ypw)], BLK, 2.6)
s.c(1010, ys[1], 5, BLK)
s.t(1002, ypw + 5, "PWDN ← GND (تشغيل دائم)", 13, BLK, "end")
# pull-ups on SIOC / SIOD from 3V3
for x, y, lab in [(820, ys[2], "4.7kΩ"), (900, ys[3], "4.7kΩ")]:
    s.c(x, ys[0], 5, RED)
    s.resistor(x, ys[0], y, lab, RED)
    s.c(x, y, 5, PUR)
s.t(860, ys[0] - 14, "مقاومتا رفع إلى 3.3V", 14, RED, bold=True)
# camera notes
cn = [("وظائف الأطراف:", BLK, True), ("SIOC/SIOD: إعداد الكاميرا (مثل I2C)", PUR, False),
      ("VSYNC: بداية الإطار · HREF: بداية السطر", BLU, False), ("PCLK: ساعة البكسل (من الكاميرا)", ORG, False),
      ("XCLK: الساعة الرئيسية 12–24 MHz (من البيكو)", ORG, False), ("D0–D7: بيانات البكسل (8 بت)", GRN, False),
      ("RESET: إعادة التشغيل (فعّال عند 0)", GRY, False), ("PWDN: إيقاف (فعّال عند 1) ← GND", BLK, False)]
for k, (txt, col, b) in enumerate(cn):
    s.t(1780, Y0 + 40 + k * 28, txt, 14, col, "end", bold=b)

# ---------------- servos and laser (part 2)
Y2 = ypw + 120
s.ln([(40, Y2 - 60), (1760, Y2 - 60)], "#ddd", 2)
s.t(900, Y2 - 25, "السيرفوهان والليزر — على البيكو 2 نفسه، وبتغذية 5V منفصلة", 20, bold=True)
srows = [("GP16", 21, PNK, "إشارة سيرفو Pan (السفلي: x,y)"), ("GP17", 22, PNK, "إشارة سيرفو Tilt (العلوي: z)"),
         ("GP18", 24, CYN, "تشغيل الليزر"), ("GND", 23, BLK, "أرضي مشترك")]
s.r(60, Y2, PXR - 60, 40 + DY * len(srows), "#e8f5e9", "#2e7d32", rx=12, sw=2.5)
sy = [Y2 + 35 + k * DY for k in range(len(srows))]
for (pn, num, col, lab), y in zip(srows, sy):
    s.t(80, y + 5, f"pin {num}", 13, GRY, "start")
    s.t(PXR - 18, y + 5, pn, 15, col, "end", bold=True)
    s.r(PXR - 8, y - 6, 12, 12, col, col, rx=2)
# 5V supply bus
BUS5, BUSG = Y2 + 260, Y2 + 300
s.r(1480, BUS5 - 40, 270, 110, "#fff3e0", P5V, rx=10, sw=2)
s.t(1615, BUS5 - 8, "مزوّد 5V / 5A", 18, P5V, bold=True)
s.t(1615, BUS5 + 20, "للسيرفو والليزر فقط", 14, P5V)
s.t(1615, BUS5 + 46, "+5V (أعلى) · GND (أسفل)", 13, GRY)
s.ln([(420, BUS5), (1480, BUS5)], P5V, 3.4)
s.ln([(420, BUSG), (1480, BUSG)], BLK, 3.4)
s.t(430, BUS5 - 8, "+5V", 14, P5V, "start", bold=True)
s.t(430, BUSG + 20, "GND", 14, BLK, "start", bold=True)
# capacitor
cx = 1460
s.c(cx, BUS5, 5, P5V); s.c(cx, BUSG, 5, BLK)
s.ln([(cx, BUS5), (cx, BUS5 + 13)], P5V, 2); s.ln([(cx - 14, BUS5 + 13), (cx + 14, BUS5 + 13)], BLK, 3)
s.ln([(cx - 14, BUS5 + 22), (cx + 14, BUS5 + 22)], BLK, 3); s.ln([(cx, BUS5 + 22), (cx, BUSG)], BLK, 2)
s.t(cx - 20, BUS5 + 24, "1000µF", 13, BLK, "end", bold=True)
# Pico GND to bus GND
s.ln([(PXR + 4, sy[3]), (380, sy[3]), (380, BUSG), (420, BUSG)], BLK, 2.6, dash="8,5")
s.t(390, sy[3] + 70, "أرضي مشترك", 13, BLK, "start", bold=True)
# servos
for k, (y, name) in enumerate([(sy[0], "سيرفو Pan (MG995)"), (sy[1], "سيرفو Tilt (MG995)")]):
    bx = 620 + k * 330
    s.r(bx, Y2 + 10, 240, 120, "#fce4ec", PNK, rx=10, sw=2)
    s.t(bx + 120, Y2 + 40, name, 16, PNK, bold=True)
    for j, (lab, col) in enumerate([("إشارة (برتقالي)", ORG), ("+5V (أحمر)", RED), ("GND (بني)", "#6d4c41")]):
        s.t(bx + 120, Y2 + 70 + j * 22, lab, 13, col)
    if k == 0:   # Pan: straight into the left edge of its box
        s.ln([(PXR + 4, y), (bx, y)], PNK, 2.6); s.c(bx, y, 4, PNK)
    else:        # Tilt: under the Pan box, into the bottom of its own box
        s.ln([(PXR + 4, y), (590, y), (590, Y2 + 155), (bx + 60, Y2 + 155), (bx + 60, Y2 + 130)], PNK, 2.6)
        s.c(bx + 60, Y2 + 130, 4, PNK)
    s.ln([(bx + 160, Y2 + 130), (bx + 160, BUS5)], P5V, 2.6); s.c(bx + 160, BUS5, 5, P5V)
    s.ln([(bx + 200, Y2 + 130), (bx + 200, BUSG)], "#6d4c41", 2.6); s.c(bx + 200, BUSG, 5, BLK)
# laser driver: GP18 -> 1k -> NPN base; collector -> laser(-); laser(+) -> +5V
LX = 1290
s.ln([(PXR + 4, sy[2]), (560, sy[2]), (560, Y2 + 190), (1150, Y2 + 190)], CYN, 2.6)
s.r(1150, Y2 + 182, 50, 16, "#fff8e1", CYN, rx=2)
s.t(1175, Y2 + 175, "1kΩ", 13, CYN, bold=True)
s.ln([(1200, Y2 + 190), (LX - 22, Y2 + 190)], CYN, 2.6)
s.c(LX, Y2 + 190, 22, "#fff", BLK, 2)
s.ln([(LX - 8, Y2 + 176), (LX - 8, Y2 + 204)], BLK, 2.5)
s.ln([(LX - 22, Y2 + 190), (LX - 8, Y2 + 190)], BLK, 2)
s.ln([(LX - 8, Y2 + 182), (LX + 10, Y2 + 168), (LX + 10, Y2 + 140)], BLK, 2)     # collector up
s.ln([(LX - 8, Y2 + 198), (LX + 10, Y2 + 212), (LX + 10, BUSG)], BLK, 2)        # emitter down
s.c(LX + 10, BUSG, 5, BLK)
s.t(LX + 30, Y2 + 195, "NPN (2N2222 / S8050)", 13, BLK, "start", bold=True)
s.t(LX + 30, Y2 + 215, "B قاعدة · C مجمّع · E باعث", 12, GRY, "start")
s.r(LX - 30, Y2 + 30, 110, 70, "#ffebee", RED, rx=8, sw=2)
s.t(LX + 25, Y2 + 58, "ليزر", 15, RED, bold=True)
s.t(LX + 25, Y2 + 82, "أقل من 1mW", 12, RED)
s.ln([(LX + 10, Y2 + 140), (LX + 10, Y2 + 100)], BLK, 2)
s.t(LX + 16, Y2 + 125, "(−)", 12, BLK, "start")
s.ln([(LX + 60, Y2 + 100), (LX + 60, Y2 + 130), (LX + 120, Y2 + 130), (LX + 120, BUS5)], P5V, 2.6)
s.c(LX + 120, BUS5, 5, P5V)
s.t(LX + 66, Y2 + 122, "(+)", 12, P5V, "start")

# ---------------- notes
notes = [("• الأسلاك بين الكاميرا والبيكو أقصر من 15 سم (خاصة PCLK وXCLK وD0–D7).", BLK),
         ("• وصّل أطراف الكاميرا بالاسم المطبوع بجانبها؛ ترتيبها يختلف بين المصنّعين.", BLK),
         ("• الخط المتقطع = أرضي البيكو مع أرضي مزوّد 5V. بدونه لا يفهم السيرفو الإشارة.", BLK),
         ("• لا تُوصل 5V بأي طرف في البيكو أو الكاميرا: الكاميرا 3.3V فقط.", RED)]
for k, (txt, col) in enumerate(notes):
    s.t(1760, BUSG + 60 + k * 28, txt, 15, col, "end", bold=(col == RED))
s.save(str(Path(__file__).with_suffix(".svg")))
