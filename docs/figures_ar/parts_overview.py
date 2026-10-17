"""Draw docs/figures_ar/parts_overview.svg (render to PNG with a browser for correct Arabic shaping)."""
# Draws the parts overview (Raspberry Pi computer vs Pico board vs INMP441), to scale (5 px per mm).
S = 5
o = []
def t(x, y, s, size=18, c="#222", anchor="middle", bold=False):
    w = ' font-weight="bold"' if bold else ''
    if any("\u0600" <= ch <= "\u06ff" for ch in s):   # Arabic: right-to-left paragraph
        w += ' direction="rtl" unicode-bidi="embed"'
        anchor = {"start": "end", "end": "start"}.get(anchor, anchor)
    o.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{c}" text-anchor="{anchor}"{w}>{s}</text>')
def r(x, y, w, h, fill, stroke="#333", rx=4, sw=1.5):
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
def c(x, y, rr, fill, stroke="none", sw=1):
    o.append(f'<circle cx="{x}" cy="{y}" r="{rr}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

W, H = 1500, 960
t(W/2, 50, "ما هي «لوحة البيكو»؟ — القطع الثلاث في المشروع (بالحجم النسبي الحقيقي)", 30, bold=True)
t(W/2, 85, "The three parts of the array, drawn to the same scale", 18, "#888")

# ---------------- 1. Raspberry Pi 4 computer (85 x 56 mm)
X, Y = 70, 170
w, h = 85*S, 56*S
r(X, Y, w, h, "#2e7d32", rx=14)
for i in range(20):  # 40-pin header (2 x 20)
    for j in range(2):
        c(X+40+i*12.5, Y+18+j*12, 3.5, "#d4af37")
r(X+40, Y+90, 70, 70, "#bbb", "#555")            # CPU
t(X+75, Y+130, "CPU", 13, "#333")
r(X+150, Y+100, 60, 45, "#222")                  # RAM
for k in range(2):                                # USB ports
    r(X+w-55, Y+30+k*70, 65, 55, "#ccc", "#555", 3)
    t(X+w-22, Y+63+k*70, "USB", 12, "#333")
r(X+w-55, Y+175, 65, 70, "#cfd8dc", "#555", 3); t(X+w-22, Y+214, "LAN", 12)
for k in range(2): r(X+60+k*90, Y+h-22, 40, 26, "#999", "#555", 2)
t(X+w/2, Y+h-40, "Raspberry Pi 4", 20, "#fff", bold=True)
t(X+w/2, Y+h+45, "١. الحاسوب: Raspberry Pi", 24, bold=True)
t(X+w/2, Y+h+78, "✓ عندك الآن — عليه نظام لينكس وكود المشروع", 18, "#2e7d32")
t(X+w/2, Y+h+106, "85 × 56 مم — يعالج الصوت ويحسب الاتجاه", 17, "#555")

# ---------------- 2. Raspberry Pi Pico (51 x 21 mm)
X2, Y2 = 640, 260
w2, h2 = 51*S, 21*S
r(X2, Y2, w2, h2, "#2e7d32", rx=6)
r(X2-14, Y2+h2/2-20, 30, 40, "#c0c0c0", "#555", 3)                        # micro-USB
t(X2-30, Y2+h2/2+6, "USB", 13, "#333", "end")
for i in range(20):
    c(X2+14+i*12.1, Y2+8, 3.6, "#f5f5f5", "#999"); c(X2+14+i*12.1, Y2+h2-8, 3.6, "#f5f5f5", "#999")
r(X2+120, Y2+33, 40, 40, "#222", rx=2); t(X2+140, Y2+58, "RP2040", 9, "#ddd")
r(X2+45, Y2+38, 20, 14, "#fafafa", "#555", 2)                              # BOOTSEL
t(X2+55, Y2+68, "BOOTSEL", 10, "#fff")
c(X2+30, Y2+75, 4, "#7CFC00")                                               # LED
t(X2+w2/2+25, Y2+92, "Raspberry Pi Pico", 13, "#fff", bold=True)
# callouts
def call(x1, y1, x2, y2, s, anchor="start"):
    o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#c62828" stroke-width="1.6"/>')
    c(x1, y1, 3.5, "#c62828"); t(x2 + (6 if anchor=="start" else -6), y2+6, s, 15, "#c62828", anchor)
call(X2+55, Y2+45, X2+30, Y2-60, "زر BOOTSEL (لتحميل البرنامج)", "start")
call(X2+140, Y2+53, X2+200, Y2-25, "المعالج RP2040", "start")
call(X2+30, Y2+75, X2+10, Y2+165, "ضوء أخضر (LED)", "start")
call(X2+14+19*12.1, Y2+h2-8, X2+w2+20, Y2+165, "40 طرفاً (تُوصَّل بها الميكروفونات)", "start")
t(X2+w2/2, 170+56*S+45, "٢. لوحة البيكو: Raspberry Pi Pico", 24, bold=True)
t(X2+w2/2, 170+56*S+78, "⏳ إن لم تكن عندك: اطلبها (4–6 دولار)", 18, "#e65100")
t(X2+w2/2, 170+56*S+106, "51 × 21 مم — متحكم صغير، ليس حاسوباً:", 17, "#555")
t(X2+w2/2, 170+56*S+130, "يقرأ الميكروفونات الـ12 بساعة واحدة ويرسلها بالـUSB", 17, "#555")

# ---------------- 3. INMP441 module (~14 mm)
X3, Y3 = 1230, 270
d = 14*S
c(X3+d/2, Y3+d/2, d/2, "#1565c0", "#0d3c78", 2)
c(X3+d/2, Y3+d/2, 9, "#cfd8dc", "#555"); c(X3+d/2, Y3+d/2, 2.5, "#333")
for i, p in enumerate(["L/R", "WS", "SCK", "SD", "VDD", "GND"]):
    yy = Y3 + d + 18 + i*0
for i, p in enumerate(["SCK", "SD", "WS", "L/R", "GND", "VDD"]):
    xx = X3 - 30 + i*26
    c(xx, Y3+d+22, 4, "#d4af37"); t(xx, Y3+d+45, p, 10, "#333")
t(X3+d/2, 170+56*S+45, "٣. الميكروفون INMP441", 24, bold=True)
t(X3+d/2, 170+56*S+78, "⏳ يصل 1 نوفمبر — 12 قطعة", 18, "#e65100")
t(X3+d/2, 170+56*S+106, "~14 مم — ميكروفون رقمي (I2S)", 17, "#555")
t(X3+d/2, 170+56*S+130, "فتحة الصوت في الوسط", 17, "#555")

# ---------------- chain
YC = 700
o.append('<line x1="60" y1="645" x2="1440" y2="645" stroke="#ddd" stroke-width="2"/>')
t(W/2, 680, "كيف تتصل ببعضها", 24, bold=True)
boxes = [(1150, "12 × INMP441", "#e3f2fd", "#1565c0"), (650, "Raspberry Pi Pico", "#e8f5e9", "#2e7d32"),
         (150, "Raspberry Pi (الحاسوب)", "#e8f5e9", "#2e7d32")]
for x, s, fill, st in boxes:
    r(x, YC+20, 260, 70, fill, st, rx=10, sw=2); t(x+130, YC+63, s, 20, "#222", bold=True)
def arrow(x1, x2, y, s):
    o.append(f'<line x1="{x1}" y1="{y}" x2="{x2+12}" y2="{y}" stroke="#444" stroke-width="3"/>')
    o.append(f'<polygon points="{x2},{y} {x2+16},{y-8} {x2+16},{y+8}" fill="#444"/>')
    t((x1+x2)/2, y-14, s, 16, "#444")
arrow(1150, 910, YC+55, "أسلاك (SCK, WS, SD, 3V3, GND)")
arrow(650, 410, YC+55, "كابل USB واحد")
t(W/2, YC+150, "البيكو هو «الوسيط»: الحاسوب لا يستطيع قراءة 12 ميكروفون I2S مباشرة وبتزامن تام، فيقوم البيكو بذلك ويرسل الصوت كاملاً عبر USB.", 17, "#555")
t(W/2, YC+180, "طريقة التمييز: Pico صغير بطول إصبع تقريباً، عليه زر أبيض BOOTSEL ومنفذ micro‑USB، ومكتوب عليه «Raspberry Pi Pico».", 17, "#555")
t(W/2, YC+210, "انتبه عند الشراء: اطلب Pico أو Pico H (معالج RP2040). البرنامج الحالي لا يعمل على Pico 2 (RP2350).", 17, "#c62828", bold=True)

svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Noto Sans Arabic, DejaVu Sans, sans-serif"><rect width="100%" height="100%" fill="#fff"/>{"".join(o)}</svg>'
open("/home/user/drone/docs/figures_ar/parts_overview.svg", "w").write(svg)
