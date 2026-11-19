"""Draw docs/figures_ar/system_overview.svg: Raspberry Pi + audio Pico + servo Pico (two pan/tilt heads)
+ two USB cameras."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _svg import BLK, BLU, GRN, GRY, ORG, P5V, PNK, RED, Svg  # noqa: E402

s = Svg(1800, 1180)
s.t(900, 48, "النظام الكامل: كيف تتصل القطع بالـ Raspberry Pi", 30, bold=True)
s.t(900, 82, "System overview – audio Pico, servo Pico with two pan/tilt heads, two USB cameras (Raspberry Pi 4 assumed)", 17, GRY)

# ---------------- Raspberry Pi with 4 USB ports
PX, PY, PW, PH = 560, 130, 680, 225
s.r(PX, PY, PW, PH, "#2e7d32", rx=16, sw=2)
s.t(PX + PW / 2, PY + 46, "Raspberry Pi (الحاسوب)", 26, "#fff", bold=True)
for k, line in enumerate(["يستقبل الصوت ويحسب الاتجاه (droneloc live)",
                          "يقرأ الكاميرتين مباشرة ويقيس الخطأ بالدرجات",
                          "يرسل للبيكو 2 زوايا الرأسين (Pan / Tilt)"]):
    s.t(PX + PW / 2, PY + 92 + k * 32, line, 17, "#fff")
ports = {}
for x, lab, sub, fill in [(640, "USB ①", "2.0 أسود", "#37474f"), (740, "USB ②", "2.0 أسود", "#37474f"),
                          (980, "USB ③", "3.0 أزرق", "#1565c0"), (1080, "USB ④", "3.0 أزرق", "#1565c0")]:
    s.r(x, PY + PH - 14, 76, 52, fill, "#263238", rx=4)
    s.t(x + 38, PY + PH + 6, lab, 13, "#fff", bold=True)
    s.t(x + 38, PY + PH + 26, sub.split()[0], 12, "#fff")
    ports[lab] = (x + 38, PY + PH + 40)
s.r(1340, 160, 300, 76, "#fff3e0", P5V, rx=10)
s.t(1490, 192, "مزوّد الباي الرسمي", 17, P5V, bold=True)
s.t(1490, 218, "USB-C · 5V · 3A", 15, P5V)
s.ln([(1340, 198), (PX + PW, 198)], P5V, 4)
s.arrow(PX + PW + 2, 198, -1, 0, P5V, 14)


def cable(pts, label=None, lx=None, ly=None, col="#555"):
    s.ln(pts, col, 6)
    x, y = pts[-1]
    s.arrow(x, y + 2, 0, -1, col, 16)
    if label:
        s.t(lx, ly, label, 13, col, "middle", bold=True)


# ---------------- Pico 1 (audio)
A = (60, 600, 360, 125)
s.r(*A, "#e8f5e9", "#2e7d32", rx=12, sw=2.5)
s.t(A[0] + A[2] / 2, A[1] + 40, "بيكو 1 — الصوت", 22, "#1b5e20", bold=True)
s.t(A[0] + A[2] / 2, A[1] + 72, "البرنامج: pico_mic_array.uf2", 15, BLK)
s.t(A[0] + A[2] / 2, A[1] + 100, "الاسم في الباي: «DroneLoc Mic Array»", 14, GRY)
cable([(240, 600), (240, 520), ports["USB ①"][0], 520][:0] or [(240, 600), (240, 520), (ports["USB ①"][0], 520), ports["USB ①"]],
      "micro-USB · صوت 12 قناة ↑", 440, 510)
s.r(80, 840, 320, 90, "#e3f2fd", "#1565c0", rx=10, sw=2)
s.t(240, 880, "12 × ميكروفون INMP441", 19, "#0d47a1", bold=True)
s.t(240, 908, "6 على الكرة + 5 مرجعية + 1 احتياط", 14, GRY)
for k, col in enumerate([GRN, ORG, BLU, RED, BLK]):
    s.ln([(160 + k * 40, 840), (160 + k * 40, 725)], col, 3)
s.t(80, 975, "أسلاك: SD×6 · SCK · WS · 3V3 · GND", 14, BLK, "start")

# ---------------- Pico 2 (servos only)
B = (500, 600, 360, 125)
s.r(*B, "#e8f5e9", "#2e7d32", rx=12, sw=2.5)
s.t(B[0] + B[2] / 2, B[1] + 40, "بيكو 2 — السيرفوهات", 22, "#1b5e20", bold=True)
s.t(B[0] + B[2] / 2, B[1] + 72, "البرنامج: pico_pointer.uf2 (سيُكتب)", 15, BLK)
s.t(B[0] + B[2] / 2, B[1] + 100, "الاسم في الباي: «DroneLoc Pointer»", 14, GRY)
cable([(ports["USB ②"][0], 600), ports["USB ②"]], "↓ زوايا الرأسين", ports["USB ②"][0] + 80, 560)

# ---------------- two heads
heads = [(980, 560, "الرأس العلوي: نصف الكرة العلوي", "سيرفو أفقي + سيرفو رأسي (MG995)", "كاميرا Brio 100 رقم 1", "GP16 · GP17"),
         (980, 820, "الرأس السفلي (مقلوب): النصف السفلي", "سيرفو أفقي + سيرفو رأسي (MG995)", "كاميرا Brio 100 رقم 2", "GP18 · GP19")]
for k, (x, y, title, l1, l2, pins) in enumerate(heads):
    s.r(x, y, 400, 150, "#fce4ec", PNK, rx=12, sw=2.5)
    s.t(x + 200, y + 38, title, 18, PNK, bold=True)
    s.t(x + 200, y + 72, l1, 15, BLK)
    s.r(x + 70, y + 92, 260, 40, "#e3f2fd", BLU, rx=8, sw=1.8)
    s.t(x + 200, y + 118, l2, 15, BLU, bold=True)
    # servo signal wires from Pico 2
    sy = 650 if k == 0 else 700
    if k == 0:
        s.ln([(860, sy), (x, sy)], PNK, 3)
    else:
        s.ln([(860, sy), (955, sy), (955, y + 60), (x, y + 60)], PNK, 3)
    s.t(915 if k == 0 else 900, sy - 10 if k == 0 else y + 64, pins, 13, PNK, "middle", bold=True)
# camera USB cables (straight to the Raspberry Pi, not through the Pico)
cable([(1180, 560), (1180, 470), (ports["USB ③"][0], 470), ports["USB ③"]], col=BLU)
cable([(1380, 895), (1440, 895), (1440, 450), (ports["USB ④"][0], 450), ports["USB ④"]], col=BLU)
s.t(1450, 520, "كابلا الكاميرتين", 14, BLU, "start", bold=True)
s.t(1450, 542, "إلى الباي مباشرة (USB 3)", 13, BLU, "start")

# ---------------- servo supplies, one per head
for k, (y, name) in enumerate([(1015, "مزوّد الرأس السفلي"), (1015, "مزوّد الرأس العلوي")]):
    x = 980 + k * 210
    s.r(x, y, 190, 80, "#fff3e0", P5V, rx=10, sw=2)
    s.t(x + 95, y + 30, name, 14, P5V, bold=True)
    s.t(x + 95, y + 56, "5V / 5A · 1000µF", 13, P5V)
s.ln([(1285, 1015), (1285, 995), (1500, 995), (1500, 690), (1380, 690)], P5V, 3.4)     # right supply -> upper head
s.ln([(1075, 1015), (1075, 970)], P5V, 3.4)                                              # left supply -> lower head
s.t(1510, 840, "تغذية الرأس العلوي", 13, P5V, "start", bold=True)
s.ln([(980, 1055), (820, 1055), (820, 725)], BLK, 3, dash="8,5")
s.t(830, 1085, "أرضي مشترك مع البيكو 2", 13, BLK, "middle", bold=True)

# ---------------- notes
notes = [("• كل بيكو يأخذ الكهرباء من كابل الـ USB نفسه.", BLK),
         ("• الكاميرتان توصلان بالباي مباشرة، وليس بالبيكو.", BLK),
         ("• البرنامج يميّز البيكوين بالاسم والكاميرتين بالرقم التسلسلي.", BLK),
         ("• الخطوط المتقاطعة دون نقطة غير موصولة ببعضها.", BLK),
         ("• لا تغذِّ السيرفو من البيكو أو من الباي.", RED)]
for k, (txt, col) in enumerate(notes):
    s.t(1780, 1025 + k * 30, txt, 15, col, "end", bold=(col == RED))
s.save(str(Path(__file__).with_suffix(".svg")))
