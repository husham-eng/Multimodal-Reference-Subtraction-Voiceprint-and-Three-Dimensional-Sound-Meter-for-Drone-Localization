"""Draw docs/figures_ar/pins_diagram.svg: Pico pinout (used pins highlighted), INMP441 pins and one SD pair.
Render to PNG with a browser for correct Arabic shaping."""
o = []
RED, BLK, ORG, BLU, GRN, GRY = "#d62728", "#222", "#ff8c00", "#1f6fd1", "#1a9a3a", "#9a9a9a"


def t(x, y, s, size=16, c=BLK, anchor="middle", bold=False):
    w = ' font-weight="bold"' if bold else ''
    if any("؀" <= ch <= "ۿ" for ch in s):
        w += ' direction="rtl" unicode-bidi="embed"'
        anchor = {"start": "end", "end": "start"}.get(anchor, anchor)
    o.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{c}" text-anchor="{anchor}"{w}>{s}</text>')


def r(x, y, w, h, fill, stroke=BLK, rx=6, sw=1.5):
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def c(x, y, rr, fill, stroke="#555", sw=1):
    o.append(f'<circle cx="{x}" cy="{y}" r="{rr}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def ln(pts, col, w=2.5):
    o.append(f'<polyline points="{" ".join(f"{a},{b}" for a, b in pts)}" fill="none" stroke="{col}" stroke-width="{w}"/>')


W, H = 1760, 1130
t(W / 2, 46, "مخطط الأطراف: Raspberry Pi Pico و INMP441", 30, bold=True)
t(W / 2, 80, "Pin diagram – Pico seen from the top, USB connector up", 17, GRY)

# ---------------- Pico pinout
left = ["GP0", "GP1", "GND", "GP2", "GP3", "GP4", "GP5", "GND", "GP6", "GP7",
        "GP8", "GP9", "GND", "GP10", "GP11", "GP12", "GP13", "GND", "GP14", "GP15"]
right = ["VBUS", "VSYS", "GND", "3V3_EN", "3V3(OUT)", "ADC_VREF", "GP28", "GND", "GP27", "GP26",
         "RUN", "GP22", "GND", "GP21", "GP20", "GP19", "GP18", "GND", "GP17", "GP16"]   # pins 40 .. 21
use = {"GP2": ("SD1 → ch0, ch1", GRN), "GP3": ("SD2 → ch2, ch3", GRN), "GP4": ("SD3 → ch4, ch5", GRN),
       "GP5": ("SD4 → ch6, ch7", GRN), "GP6": ("SD5 → ch8, ch9", GRN), "GP7": ("SD6 → ch10, ch11", GRN),
       "GP8": ("SCK (clock)", ORG), "GP9": ("WS (word select)", BLU)}
PX, PY, PW, step = 430, 130, 190, 27
r(PX, PY, PW, 20 * step + 30, "#2e7d32", rx=10)
r(PX + PW / 2 - 28, PY - 18, 56, 28, "#c0c0c0", "#555", 3); t(PX + PW / 2, PY + 2, "USB", 12)
r(PX + 30, PY + 40, 30, 20, "#fafafa", "#555", 2); t(PX + 45, PY + 76, "BOOTSEL", 10, "#fff")
r(PX + 70, PY + 230, 60, 60, "#222", rx=3); t(PX + 100, PY + 265, "RP2040", 11, "#ddd")
t(PX + PW / 2, PY + 20 * step + 12, "Raspberry Pi Pico", 13, "#fff", bold=True)
for k in range(20):
    y = PY + 28 + k * step
    # left column: pins 1..20
    name, pin = left[k], k + 1
    col = use[name][1] if name in use else (BLK if name == "GND" and pin == 3 else None)
    c(PX + 14, y, 7, col or "#f5f5f5", "#333" if col else "#999")
    t(PX - 12, y + 5, f"{name}  ({pin})", 14, col or GRY, "end", bold=bool(col))
    if name in use:
        ln([(PX - 110, y), (PX - 190, y)], use[name][1], 3)
        t(PX - 198, y + 5, use[name][0], 14, use[name][1], "end", bold=True)
    # right column: pins 40..21
    name, pin = right[k], 40 - k
    col = RED if name == "3V3(OUT)" else (BLK if name == "GND" and pin == 38 else None)
    c(PX + PW - 14, y, 7, col or "#f5f5f5", "#333" if col else "#999")
    t(PX + PW + 12, y + 5, f"({pin})  {name}", 14, col or GRY, "start", bold=bool(col))
    if col:
        lab = "تغذية 3.3 فولت لكل الميكروفونات" if name == "3V3(OUT)" else "الأرضي المشترك (GND)"
        ln([(PX + PW + 125, y), (PX + PW + 175, y)], col, 3)
        t(PX + PW + 183, y + 5, lab, 14, col, "start", bold=True)
t(PX + PW / 2, PY + 20 * step + 70, "الأطراف الملوّنة فقط مستخدمة — الباقي يبقى فارغاً", 16, BLK)
t(PX + PW / 2, PY + 20 * step + 96, "(أي طرف GND يصلح؛ الرسم يستخدم الطرف 38)", 14, GRY)

# ---------------- INMP441 module
MX, MY = 1380, 400
r(MX, MY, 300, 150, "#1565c0", "#0d3c78", rx=12, sw=2)
c(MX + 210, MY + 75, 34, "#cfd8dc", "#555", 1.5); c(MX + 210, MY + 75, 6, "#333")
t(MX + 210, MY + 135, "فتحة الصوت", 13, "#fff")
pins = [("VDD", RED, "3.3 فولت"), ("GND", BLK, "الأرضي"), ("L/R", "#7b1fa2", "يختار القناة"),
        ("WS", BLU, "GP9"), ("SCK", ORG, "GP8"), ("SD", GRN, "خط البيانات")]
for k, (p, col, d) in enumerate(pins):
    y = MY + 22 + k * 21
    c(MX + 22, y, 6, "#d4af37", "#8a6d00")
    t(MX + 36, y + 5, p, 14, "#fff", "start", bold=True)
    ln([(MX - 10, y), (MX - 60, y)], col, 3)
    t(MX - 68, y + 5, d, 14, col, "end", bold=True)
t(MX + 150, MY + 185, "وحدة الميكروفون INMP441 (الأطراف الستة)", 18, bold=True)
t(MX + 150, MY + 212, "ميكروفون رقمي: يخرج 24 بت عبر I2S، تيار ~1.4 مللي أمبير", 14, GRY)

# ---------------- one SD pair (two mics on one data line)
QX, QY = 980, 720
t(QX + 300, QY, "كيف يشترك ميكروفونان في خط بيانات واحد (مثال: ch0 و ch1 على GP2)", 18, bold=True)
for k, (lr, lab, col) in enumerate([("GND", "ch0 — يسار (L/R → GND)", BLK), ("3V3", "ch1 — يمين (L/R → 3V3)", RED)]):
    y = QY + 40 + k * 120
    r(QX + 360, y, 230, 90, "#eef3fb", "#2a4a7a", rx=8)
    t(QX + 475, y + 35, "INMP441", 16, "#2a4a7a", bold=True); t(QX + 475, y + 62, lab, 13, col)
    ln([(QX + 360, y + 20), (QX + 200, y + 20)], GRN, 3)       # SD
    ln([(QX + 360, y + 45), (QX + 230, y + 45)], ORG, 3)       # SCK
    ln([(QX + 360, y + 70), (QX + 260, y + 70)], BLU, 3)       # WS
    ln([(QX + 590, y + 45), (QX + 640, y + 45)], col, 3); t(QX + 645, y + 50, f"L/R → {lr}", 13, col, "start")
for xx, col, lab in [(QX + 200, GRN, "SD → GP2"), (QX + 230, ORG, "SCK → GP8"), (QX + 260, BLU, "WS → GP9")]:
    ln([(xx, QY + 60), (xx, QY + 230)], col, 3)
for k, (xx, col, lab) in enumerate([(QX + 200, GRN, "SD → GP2"), (QX + 230, ORG, "SCK → GP8"), (QX + 260, BLU, "WS → GP9")]):
    c(xx, QY + 60, 4, col, col); c(xx, QY + 180, 4, col, col)
    t(xx - 8, QY + 262 + k * 22, lab, 14, col, "end", bold=True)
    ln([(xx, QY + 230), (xx, QY + 256 + k * 22 - 5), (xx - 4, QY + 256 + k * 22 - 5)], col, 2)
# timing sketch
TY = QY + 340
t(QX + 300, TY, "إطار I2S واحد (64 نبضة SCK): نصف للقناة اليسرى ونصف لليمنى", 16, bold=True)
x0, x1 = QX + 30, QX + 590
ln([(x0, TY + 45), (x0 + 5, TY + 45), (x0 + 5, TY + 25), ((x0 + x1) / 2, TY + 25), ((x0 + x1) / 2, TY + 45), (x1, TY + 45)], BLU, 2.5)
t(x0 - 8, TY + 40, "WS", 14, BLU, "end", bold=True)
r(x0 + 10, TY + 60, (x1 - x0) / 2 - 20, 30, "#e8f5e9", GRN, 4); t((x0 + (x0 + x1) / 2) / 2 + 5, TY + 81, "بيانات ch0 (يسار)", 14, GRN)
r((x0 + x1) / 2 + 10, TY + 60, (x1 - x0) / 2 - 20, 30, "#fde8e8", RED, 4); t(((x0 + x1) / 2 + x1) / 2 + 5, TY + 81, "بيانات ch1 (يمين)", 14, RED)
t(x0 - 8, TY + 81, "SD", 14, GRN, "end", bold=True)
t(QX + 300, TY + 118, "الميكروفون الذي ليس دوره يفصل خرجه (high-Z)، لذلك لا يحدث تعارض على الخط.", 14, GRY)
t(QX + 300, TY + 142, "SCK = 2.0 MHz ← 31250 إطاراً/ثانية ← بعد الترشيح والتقسيم 15625 عينة/ثانية لكل قناة", 14, GRY)

# legend
LY = H - 40
for k, (col, s) in enumerate([(RED, "3V3"), (BLK, "GND"), (ORG, "SCK"), (BLU, "WS"), (GRN, "SD"), ("#7b1fa2", "L/R")]):
    x = 420 + k * 160
    ln([(x, LY), (x + 40, LY)], col, 5); t(x + 50, LY + 5, s, 15, col, "start", bold=True)

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'font-family="DejaVu Sans, sans-serif"><rect width="100%" height="100%" fill="#fff"/>{"".join(o)}</svg>')
open(__file__.replace(".py", ".svg"), "w").write(svg)
