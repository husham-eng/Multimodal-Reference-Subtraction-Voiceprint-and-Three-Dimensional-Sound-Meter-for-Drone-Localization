"""Draw docs/figures_ar/bno085_board.svg: the Adafruit BNO085 board (product 4754) and its UART-RVC wiring
to the Raspberry Pi."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _svg import BLK, GRY, ORG, RED, Svg  # noqa: E402

s = Svg(1500, 840)
s.t(750, 48, "توصيل BNO085 (Adafruit 4754) بالـ Raspberry Pi — نمط UART-RVC", 28, bold=True)
s.t(750, 82, "Illustration (not a photo) – connect by the names printed next to the pins; their order can differ", 16, GRY)

X, Y, W, H = 330, 175, 480, 480
s.r(X, Y, W, H, "#212121", "#000", rx=18, sw=2.5)
for cx, cy in [(X + 40, Y + 40), (X + W - 40, Y + 40), (X + 40, Y + H - 40), (X + W - 40, Y + H - 40)]:
    s.c(cx, cy, 20, "#fff", "#c9a227", 6)
for (sx, sy) in [(X - 10, Y + 190), (X + W - 60, Y + 190)]:            # STEMMA QT connectors
    s.r(sx, sy, 70, 90, "#eeeeee", "#999", rx=4)
s.t(X + 25, Y + 300, "STEMMA QT", 11, "#ccc"); s.t(X + W - 25, Y + 300, "STEMMA QT", 11, "#ccc")
s.r(X + W / 2 - 45, Y + 190, 90, 90, "#111", "#555", rx=4)
s.t(X + W / 2, Y + 242, "BNO085", 14, "#ddd", bold=True)
s.t(X + W / 2, Y + 160, "BNO08x 9-DOF", 16, "#fff", bold=True)
s.t(X + W / 2, Y + 330, "★ adafruit · 4754", 14, "#bbb")
top = ["BT", "P0", "P1", "RST", "DI", "CS"]
bot = ["VIN", "3Vo", "GND", "SCL", "SDA", "INT"]
use = {"VIN": (RED, "الطرف 1 (3V3)"), "GND": (BLK, "الطرف 6 (GND)"), "SDA": (ORG, "الطرف 10 (RXD)"),
       "P0": (RED, "إلى 3V3 (مع VIN)")}
step = (W - 120) / 6
for row, names, y in [(0, top, Y + 95), (1, bot, Y + H - 95)]:
    for k, n in enumerate(names):
        x = X + 60 + step * (k + 0.5)
        col = use.get(n, (None, None))[0]
        s.c(x, y, 13, "#c9a227", "#7a5d00", 2)
        s.c(x, y, 6, "#3e2723")
        on_board = "#fff" if col == BLK else col
        s.t(x, y + (36 if row == 0 else -24), n, 14, on_board or "#bbb", bold=bool(col))
        if col:
            ty = Y - 55 if row == 0 else Y + H + 45
            wire = "#9e9e9e" if col == BLK else col
            s.ln([(x, y + (-13 if row == 0 else 13)), (x, Y - 12 if row == 0 else ty - 24)], wire, 3)
            s.t(x, ty + (0 if row == 0 else 0), n, 15, col, bold=True)
            s.t(x, ty + 20, use[n][1], 13, col)
# side panel
notes = [("الأطراف المستخدمة (4 فقط):", BLK, True),
         ("VIN ← الطرف 1 في الباي (3V3)", RED, True), ("GND ← الطرف 6 في الباي (GND)", BLK, True),
         ("SDA ← الطرف 10 في الباي (GPIO15 RXD)", ORG, True), ("P0 ← 3V3 (يختار نمط UART-RVC)", RED, True),
         ("", BLK, False),
         ("باقي الأطراف تبقى فارغة:", GRY, True), ("3Vo · SCL · INT · BT · P1 · RST · DI · CS", GRY, False),
         ("", BLK, False),
         ("في نمط UART-RVC يرسل BNO085 الاتجاه الجاهز", BLK, False), ("(yaw/pitch/roll) 100 مرة/ثانية على طرف SDA.", BLK, False),
         ("تأكد من ذلك ومن P0 في دليل Adafruit للوحة 4754.", GRY, False),
         ("", BLK, False),
         ("قبل التشغيل: فعّل المنفذ التسلسلي في الباي:", BLK, True),
         ("sudo raspi-config ← Interface ← Serial Port", BLK, False),
         ("login shell: No · hardware: Yes ← ثم أعد التشغيل", BLK, False)]
for k, (txt, col, b) in enumerate(notes):
    s.t(1470, 150 + k * 32, txt, 15, col, "end", bold=b)
s.t(750, 815, "ثبّت اللوحة بإحكام على الكرة، ومحاورها موازية لمحاور الميكروفونات (x للأمام، y لليسار، z للأعلى).", 16, BLK)
s.save(str(Path(__file__).with_suffix(".svg")))
