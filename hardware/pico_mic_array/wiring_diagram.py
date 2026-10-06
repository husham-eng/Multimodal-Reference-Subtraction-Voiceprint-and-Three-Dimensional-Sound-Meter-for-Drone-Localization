"""Draw the wiring diagram of the Pico microphone array (wiring.svg).

    python hardware/pico_mic_array/wiring_diagram.py
"""
from pathlib import Path

RED, BLK, ORG, BLU, GRN, GRY = "#d62728", "#222222", "#ff8c00", "#1f6fd1", "#1a9a3a", "#9a9a9a"
F = "DejaVu Sans, Arial, sans-serif"
o = []


def line(pts, c, w=2.2):
    o.append(f'<polyline points="{" ".join(f"{x},{y}" for x, y in pts)}" fill="none" stroke="{c}" '
             f'stroke-width="{w}" stroke-linejoin="round"/>')


def dot(x, y, c):
    o.append(f'<circle cx="{x}" cy="{y}" r="4.2" fill="{c}"/>')


def text(x, y, s, size=13, c=BLK, anchor="start", bold=False, rtl=False):
    extra = (' direction="rtl" unicode-bidi="embed"' if rtl else "") + (' font-weight="bold"' if bold else "")
    o.append(f'<text x="{x}" y="{y}" font-family="{F}" font-size="{size}" fill="{c}" text-anchor="{anchor}"'
             f'{extra}>{s}</text>')


def rect(x, y, w, h, fill, stroke=BLK, rx=6, sw=1.5):
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


W, H = 1180, 1800
# ------------------------------------------------------------------ title
text(W / 2, 40, "مخطط توصيل مصفوفة الميكروفونات: Raspberry Pi Pico + 12 × INMP441", 24, anchor="middle", bold=True, rtl=True)
text(W / 2, 66, "Wiring diagram – one shared clock (SCK/WS) for all 12 microphones", 15, GRY, "middle")

# ------------------------------------------------------------------ Pico block (used pins only)
PX, PY = 60, 120
pins = [("GP9  (WS)", 12, BLU), ("GP8  (SCK)", 11, ORG), ("GND", 38, BLK), ("3V3(OUT)", 36, RED),
        ("GP2  (SD1)", 4, GRN), ("GP3  (SD2)", 5, GRN), ("GP4  (SD3)", 6, GRN),
        ("GP5  (SD4)", 7, GRN), ("GP6  (SD5)", 9, GRN), ("GP7  (SD6)", 10, GRN)]
pin_y = [PY + 50 + 28 * k for k in range(len(pins))]
rect(PX, PY, 240, pin_y[-1] - PY + 40, "#e8f3e8", "#2d6a2d", 10, 2)
text(PX + 120, PY + 28, "Raspberry Pi Pico", 17, "#2d6a2d", "middle", True)
for (name, num, c), y in zip(pins, pin_y):
    text(PX + 228, y + 5, name, 13, c, "end", True)
    text(PX + 14, y + 5, f"pin {num}", 11, GRY)
    o.append(f'<rect x="{PX + 236}" y="{y - 5}" width="10" height="10" fill="{c}"/>')

X0 = PX + 246
RAIL = {"3V3": (410, RED), "GND": (450, BLK), "SCK": (490, ORG), "WS": (530, BLU)}
SDX = [380 - 12 * i for i in range(6)]   # SD line i vertical (right to left, avoids crossings)

# ------------------------------------------------------------------ microphones
MX, MY0, PIN = 640, 470, 11
names = ["VDD", "GND", "SCK", "WS", "SD", "L/R"]
roles = ["Sphere +x", "Sphere −x", "Sphere +y", "Sphere −y", "Sphere +z (top)", "Sphere −z (bottom)",
         "Rotor ref 1", "Rotor ref 2", "Rotor ref 3", "Rotor ref 4", "Station ref", "Spare"]
rail_bottom = {}
sd_span = {}
for ch in range(12):
    i, j = divmod(ch, 2)
    y0 = MY0 + i * 196 + j * 84
    rect(MX, y0, 150, 74, "#eef3fb", "#3a5a8c", 6, 1.6)
    text(MX + 98, y0 + 30, "INMP441", 13, "#3a5a8c", "middle", True)
    text(MX + 98, y0 + 50, f"ch {ch}", 15, BLK, "middle", True)
    ys = [y0 + 10 + PIN * k for k in range(6)]
    for k, (nm, y) in enumerate(zip(names, ys)):
        text(MX + 6, y + 4, nm, 9.5, GRY)
    tgt = {"VDD": "3V3", "GND": "GND", "SCK": "SCK", "WS": "WS", "L/R": "GND" if j == 0 else "3V3"}
    for nm, y in zip(names, ys):
        if nm == "SD":
            line([(MX, y), (SDX[i], y)], GRN); dot(SDX[i], y, GRN)
            sd_span.setdefault(i, []).append(y)
            continue
        rx, c = RAIL[tgt[nm]]
        line([(MX, y), (rx, y)], RED if nm == "L/R" and j else (BLK if nm == "L/R" else c), 1.6 if nm == "L/R" else 2.0)
        dot(rx, y, c)
        rail_bottom[tgt[nm]] = max(rail_bottom.get(tgt[nm], 0), y)
    side = "L/R → GND  (left)" if j == 0 else "L/R → 3V3  (right)"
    text(MX + 166, y0 + 26, roles[ch], 14, BLK, bold=True)
    text(MX + 166, y0 + 46, side, 12, BLK if j == 0 else RED)
    if j == 0:
        text(MX + 166, y0 + 66 + 0, f"SD line {i + 1} → GP{2 + i}", 12, GRN)

# rails from Pico pins
for (name, num, c), y in zip(pins[:4], pin_y[:4]):
    key = {"GP9  (WS)": "WS", "GP8  (SCK)": "SCK", "GND": "GND", "3V3(OUT)": "3V3"}[name]
    rx, _ = RAIL[key]
    line([(X0, y), (rx, y), (rx, rail_bottom[key])], c, 2.6)
    dot(rx, y, c)
    o.append(f'<text x="{rx}" y="452" font-family="{F}" font-size="13" font-weight="bold" fill="{c}" text-anchor="middle" '
             f'stroke="#ffffff" stroke-width="5" paint-order="stroke">{key}</text>')
# SD lines
for i, ((name, num, c), y) in enumerate(zip(pins[4:], pin_y[4:])):
    lo, hi = min(sd_span[i] + [y]), max(sd_span[i] + [y])
    line([(X0, y), (SDX[i], y)], GRN, 2.2)
    line([(SDX[i], lo), (SDX[i], hi)], GRN, 2.2)
    dot(SDX[i], y, GRN)

# ------------------------------------------------------------------ physical pinout inset
IX, IY, PS = 760, 100, 15
L = ["GP0", "GP1", "GND", "GP2", "GP3", "GP4", "GP5", "GND", "GP6", "GP7", "GP8", "GP9", "GND",
     "GP10", "GP11", "GP12", "GP13", "GND", "GP14", "GP15"]
R = ["VBUS", "VSYS", "GND", "3V3_EN", "3V3(OUT)", "ADC_VREF", "GP28", "GND", "GP27", "GP26", "RUN",
     "GP22", "GND", "GP21", "GP20", "GP19", "GP18", "GND", "GP17", "GP16"]
use = {"GP2": GRN, "GP3": GRN, "GP4": GRN, "GP5": GRN, "GP6": GRN, "GP7": GRN, "GP8": ORG, "GP9": BLU,
       "3V3(OUT)": RED}
text(IX + 160, IY - 14, "مواقع الأطراف على اللوحة (منظر علوي، USB للأعلى)", 13, BLK, "middle", True, rtl=True)
rect(IX + 100, IY, 120, 20 * PS + 16, "#2e7d32", "#1b4d1e", 6)
rect(IX + 140, IY - 8, 40, 16, "#bdbdbd", "#666", 2)
text(IX + 160, IY + 4, "USB", 9, BLK, "middle")
o.append(f'<rect x="{IX + 130}" y="{IY + 40}" width="22" height="14" fill="#f5f5f5" stroke="#666"/>')
text(IX + 160, IY + 70, "BOOTSEL", 9, "#ffffff", "middle")
for k in range(20):
    y = IY + 14 + k * PS
    for side, lab, num in ((0, L[k], k + 1), (1, R[k], 40 - k)):
        x = IX + 100 + (8 if side == 0 else 112)
        c = use.get(lab, BLK if lab == "GND" and ((side == 0 and k == 2) or (side == 1 and k == 2)) else None)
        o.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{c or "#e0e0e0"}" stroke="#555" stroke-width="0.8"/>')
        tx = IX + 92 if side == 0 else IX + 228
        text(tx, y + 4, f"{lab} ({num})", 10.5, c or GRY, "end" if side == 0 else "start", bool(c))

# ------------------------------------------------------------------ legend + system strip
LY = H - 120
for k, (lab, c) in enumerate([("3V3 (red)", RED), ("GND (black)", BLK), ("SCK – clock (orange)", ORG),
                              ("WS – word select (blue)", BLU), ("SD – data (green)", GRN)]):
    line([(60 + k * 215, LY), (95 + k * 215, LY)], c, 4)
    text(102 + k * 215, LY + 5, lab, 12.5, c, bold=True)
text(60, LY + 34, "• A dot = connection. Crossing lines without a dot are NOT connected.", 13)
text(60, LY + 56, "• Keep SCK/WS wires &lt; 20 cm (or add 33–100 Ω in series at the Pico). Each SD wire is shared by exactly two mics.", 13)
text(60, LY + 78, "• Pico → USB → laptop (ground tests) or → Raspberry Pi USB port (later, on the drone). No other wires to the Raspberry Pi.", 13)
text(W - 60, LY + 104, "النقطة = توصيل. الخطوط المتقاطعة بلا نقطة غير موصولة. اللوحة تتصل بالحاسوب أو Raspberry Pi بكابل USB فقط.", 13, "#555", "start", rtl=True)

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
       f'<rect width="{W}" height="{H}" fill="#ffffff"/>' + "".join(o) + "</svg>")
out = Path(__file__).with_name("wiring.svg")
out.write_text(svg, encoding="utf-8")
print("written", out)
