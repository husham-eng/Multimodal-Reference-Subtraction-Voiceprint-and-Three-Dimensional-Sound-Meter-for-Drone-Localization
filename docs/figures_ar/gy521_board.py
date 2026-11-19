"""Draw docs/figures_ar/gy521_board.svg: what a GY-521 (MPU-6050) board looks like, with its pins."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _svg import BLK, BLU, GRY, PUR, RED, Svg  # noqa: E402

s = Svg(1500, 720)
s.t(750, 48, "لوحة MPU-6050 (GY-521): كيف تبدو وما أطرافها", 30, bold=True)
s.t(750, 82, "Illustration (not a photo) – about 21 x 16 mm, blue board, 8 pins in one row", 17, GRY)

# board drawn 20 px per mm
X, Y, W, H = 400, 140, 21 * 20, 16 * 20
s.r(X, Y, W, H, "#1565c0", "#0d3c78", rx=10, sw=2.5)
for cx, cy in [(X + 30, Y + 30), (X + W - 30, Y + 30)]:          # mounting holes
    s.c(cx, cy, 15, "#fff", "#c0a060", 4)
s.r(X + W / 2 - 40, Y + 95, 80, 80, "#222", "#000", rx=4)          # MPU-6050 chip (4 x 4 mm QFN)
s.c(X + W / 2 - 30, Y + 105, 3.5, "#666")
s.t(X + W / 2, Y + 142, "MPU-6050", 12, "#ddd", bold=True)
s.r(X + 40, Y + 105, 50, 34, "#333", "#000", rx=2); s.t(X + 65, Y + 127, "LDO", 10, "#ccc")   # regulator
s.r(X + W - 80, Y + 110, 20, 12, "#e53935", "#600", rx=2); s.t(X + W - 70, Y + 140, "LED", 10, "#fff")
s.t(X + W / 2, Y + 70, "GY-521", 18, "#fff", bold=True)
# axes printed on the board
ax, ay = X + W - 95, Y + 180
s.ln([(ax, ay), (ax + 55, ay)], "#fff", 2.5); s.arrow(ax + 57, ay, 1, 0, "#fff", 10); s.t(ax + 70, ay + 5, "X", 13, "#fff", bold=True)
s.ln([(ax, ay), (ax, ay - 55)], "#fff", 2.5); s.arrow(ax, ay - 57, 0, -1, "#fff", 10); s.t(ax, ay - 64, "Y", 13, "#fff", bold=True)
# pins along the bottom edge
pins = [("VCC", RED, "الطرف 17 (3V3)"), ("GND", BLK, "الطرف 9 (GND)"), ("SCL", PUR, "الطرف 5 (SCL)"),
        ("SDA", BLU, "الطرف 3 (SDA)"), ("XDA", GRY, "لا يوصل"), ("XCL", GRY, "لا يوصل"),
        ("AD0", BLK, "GND (أو يُترك)"), ("INT", GRY, "لا يوصل")]
step = W / 8
for k, (name, col, to) in enumerate(pins):
    px = X + step * (k + 0.5)
    s.r(px - 9, Y + H - 34, 18, 18, "#d4af37", "#8a6d00", rx=3)
    s.c(px, Y + H - 25, 4.5, "#5d4037")
    s.t(px, Y + H - 46, name, 12, "#fff", bold=True)
    s.ln([(px, Y + H), (px, Y + H + 40 + (k % 2) * 46)], col, 3)
    ty = Y + H + 64 + (k % 2) * 46
    s.t(px, ty, name, 15, col, bold=True)
    s.t(px, ty + 20, to, 12, col if col != GRY else GRY)
# side notes
notes = [("كيف تميّزها:", BLK, True), ("• لوحة زرقاء صغيرة مكتوب عليها GY-521", BLK, False),
         ("• شريحة سوداء مربعة صغيرة في الوسط (MPU-6050)", BLK, False), ("• صف واحد من 8 أطراف", BLK, False),
         ("• سهمان X وY مطبوعان على اللوحة", BLK, False), ("", BLK, False),
         ("للمشروع نحتاج 4 أطراف فقط:", BLK, True), ("VCC · GND · SCL · SDA", BLU, True),
         ("وAD0 إلى GND (العنوان 0x68)", BLK, False), ("", BLK, False),
         ("XDA وXCL وINT: تبقى فارغة", GRY, False)]
for k, (txt, col, b) in enumerate(notes):
    s.t(1460, 160 + k * 32, txt, 16, col, "end", bold=b)
s.t(750, 690, "ثبّتها على القاعدة الثابتة للرأسين، وسهماها X وY موازيان لمحوري الحامل، بعيداً 10–15 سم عن السيرفوهات.", 16, BLK)
s.save(str(Path(__file__).with_suffix(".svg")))
