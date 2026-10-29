"""Draw docs/figures_ar/system_overview.svg: Raspberry Pi + audio Pico + camera/pointer Pico."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _svg import BLK, BLU, GRN, GRY, ORG, P5V, PNK, RED, Svg  # noqa: E402

s = Svg(1700, 1130)
s.t(850, 48, "النظام الكامل: كيف يتصل كل بيكو بالـ Raspberry Pi", 30, bold=True)
s.t(850, 82, "System overview – two Picos, each on its own USB cable; no other wires to the Raspberry Pi", 17, GRY)

# ---------------- Raspberry Pi
PX, PY, PW, PH = 575, 150, 550, 250
s.r(PX, PY, PW, PH, "#2e7d32", rx=16, sw=2)
s.t(PX + PW / 2, PY + 50, "Raspberry Pi (الحاسوب)", 26, "#fff", bold=True)
for k, line in enumerate(["يستقبل الصوت ويحسب الاتجاه (droneloc live)", "يستقبل صور الكاميرا ويعرضها ويسجّلها",
                          "يرسل للبيكو 2 أمر: «وجّه الحامل إلى السمت والارتفاع»"]):
    s.t(PX + PW / 2, PY + 100 + k * 34, line, 17, "#fff")
ports = {}
for k, (x, lab, used) in enumerate([(640, "USB 1", True), (725, "USB 2", False), (910, "USB 3", True), (995, "USB 4", False)]):
    s.r(x, PY + PH - 10, 70, 46, "#cfd8dc" if used else "#eceff1", "#455a64", rx=4)
    s.t(x + 35, PY + PH + 20, lab, 13, BLK if used else GRY, bold=used)
    ports[lab] = (x + 35, PY + PH + 36)
# power for the Pi
s.r(1240, 175, 300, 80, "#fff3e0", P5V, rx=10)
s.t(1390, 208, "مزوّد الباي الرسمي", 17, P5V, bold=True)
s.t(1390, 235, "USB-C · 5V · 3A", 15, P5V)
s.ln([(1240, 215), (PX + PW, 215)], P5V, 4)
s.arrow(PX + PW + 2, 215, -1, 0, P5V, 14)

# ---------------- Pico 1 (audio)
A = (110, 610, 380, 130)
s.r(*A, "#e8f5e9", "#2e7d32", rx=12, sw=2.5)
s.t(A[0] + A[2] / 2, A[1] + 42, "بيكو 1 — الصوت", 22, "#1b5e20", bold=True)
s.t(A[0] + A[2] / 2, A[1] + 74, "البرنامج: pico_mic_array.uf2", 15, BLK)
s.t(A[0] + A[2] / 2, A[1] + 102, "يظهر في الباي باسم «DroneLoc Mic Array»", 14, GRY)
s.r(140, 850, 320, 90, "#e3f2fd", "#1565c0", rx=10, sw=2)
s.t(300, 890, "12 × ميكروفون INMP441", 19, "#0d47a1", bold=True)
s.t(300, 918, "6 على الكرة + 5 مرجعية + 1 احتياط", 14, GRY)
for k, col in enumerate([GRN, ORG, BLU, RED, BLK]):
    x = 220 + k * 40
    s.ln([(x, 850), (x, 740)], col, 3)
s.t(495, 800, "أسلاك: SD×6 · SCK · WS · 3V3 · GND", 14, BLK, "start")
# cable to USB 1
ux, uy = ports["USB 1"]
s.ln([(300, 610), (300, 545), (ux, 545), (ux, uy)], "#555", 6)
s.arrow(ux, uy + 2, 0, -1, "#555", 16)
s.r(318, 492, 286, 44, "#fff", "#bbb", rx=6, sw=1)
s.t(461, 512, "كابل micro-USB ← USB-A (بيانات)", 14, BLK)
s.t(461, 530, "صوت 12 قناة ← 375 كيلوبايت/ثانية ↑", 13, GRN, bold=True)

# ---------------- Pico 2 (camera + pointer)
B = (1210, 610, 380, 130)
s.r(*B, "#e8f5e9", "#2e7d32", rx=12, sw=2.5)
s.t(B[0] + B[2] / 2, B[1] + 42, "بيكو 2 — المشاهدة", 22, "#1b5e20", bold=True)
s.t(B[0] + B[2] / 2, B[1] + 74, "البرنامج: pico_pointer.uf2 (سيُكتب)", 15, BLK)
s.t(B[0] + B[2] / 2, B[1] + 102, "يظهر في الباي باسم «DroneLoc Pointer»", 14, GRY)
ux, uy = ports["USB 3"]
s.ln([(1400, 610), (1400, 545), (ux, 545), (ux, uy)], "#555", 6)
s.arrow(ux, uy + 2, 0, -1, "#555", 16)
s.r(1012, 492, 330, 44, "#fff", "#bbb", rx=6, sw=1)
s.t(1177, 512, "↑ صور 160×120 · ↓ أوامر السيرفو والليزر", 14, BLK)
s.t(1177, 530, "كابل micro-USB ← USB-A (بيانات)", 13, GRY)
# peripherals of Pico 2
for (x, w, title, sub, col, fill) in [(1070, 200, "كاميرا OV7670", "18 طرفاً · 3.3V", BLU, "#e3f2fd"),
                                      (1300, 200, "2 × سيرفو MG90S", "Pan + Tilt", PNK, "#fce4ec"),
                                      (1520, 160, "ليزر", "أقل من 1mW", RED, "#ffebee")]:
    s.r(x, 850, w, 90, fill, col, rx=10, sw=2)
    s.t(x + w / 2, 890, title, 17, col, bold=True)
    s.t(x + w / 2, 918, sub, 14, GRY)
    s.ln([(x + w / 2, 850), (x + w / 2, 795), (1400, 795), (1400, 740)], col, 3)
s.t(1180, 788, "16 سلكاً", 13, BLU, "end")
# servo supply
s.r(1300, 990, 380, 70, "#fff3e0", P5V, rx=10, sw=2)
s.t(1490, 1020, "مزوّد منفصل 5V / 2A للسيرفو والليزر", 16, P5V, bold=True)
s.t(1490, 1045, "+ مكثف 470µF", 14, P5V)
s.ln([(1400, 990), (1400, 940)], P5V, 4)
s.ln([(1600, 990), (1600, 940)], P5V, 4)
s.ln([(1300, 1035), (1286, 1035), (1286, 740)], BLK, 3, dash="8,5")
s.t(1258, 1090, "أرضي مشترك مع البيكو 2 (الخط المتقطع)", 14, BLK, "start", bold=True)

# ---------------- notes
y = 990
for k, (txt, col) in enumerate([
        ("• كل بيكو يأخذ الكهرباء من كابل الـ USB نفسه، فلا يحتاج مصدراً آخر.", BLK),
        ("• لا توجد أسلاك أخرى بين البيكو والباي، ولا بين البيكوين.", BLK),
        ("• البرنامج يميّز البيكوين بالاسم، فلا يهم أي منفذ USB تستخدم.", BLK),
        ("• لا تغذِّ السيرفو من البيكو أو من الباي.", RED)]):
    s.t(1180, y + k * 30, txt, 15, col, "end", bold=(col == RED))
s.save(str(Path(__file__).with_suffix(".svg")))
