"""Small SVG helpers shared by the Arabic figures (render the SVG with a browser for Arabic shaping)."""
RED, BLK, ORG, BLU, GRN, GRY, PUR, PNK, P5V, CYN = ("#d62728", "#222", "#ff8c00", "#1f6fd1", "#1a9a3a", "#8a8a8a",
                                                   "#7b1fa2", "#c2185b", "#b23c00", "#0097a7")


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.o = w, h, []

    def t(self, x, y, s, size=16, c=BLK, anchor="middle", bold=False):
        a = ' font-weight="bold"' if bold else ''
        if any("؀" <= ch <= "ۿ" for ch in s):
            a += ' direction="rtl" unicode-bidi="embed"'
            anchor = {"start": "end", "end": "start"}.get(anchor, anchor)
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.o.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{c}" text-anchor="{anchor}"{a}>{s}</text>')

    def r(self, x, y, w, h, fill, stroke=BLK, rx=8, sw=1.6, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        self.o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def c(self, x, y, rr, fill, stroke="none", sw=1):
        self.o.append(f'<circle cx="{x}" cy="{y}" r="{rr}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def ln(self, pts, col, w=2.4, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        self.o.append(f'<polyline points="{" ".join(f"{a},{b}" for a, b in pts)}" fill="none" stroke="{col}" '
                      f'stroke-width="{w}" stroke-linejoin="round"{d}/>')

    def arrow(self, x, y, dx, dy, col, size=9):
        import math
        a = math.atan2(dy, dx)
        p = [(x, y), (x - size * math.cos(a - 0.45), y - size * math.sin(a - 0.45)),
             (x - size * math.cos(a + 0.45), y - size * math.sin(a + 0.45))]
        self.o.append(f'<polygon points="{" ".join(f"{u},{v}" for u, v in p)}" fill="{col}"/>')

    def resistor(self, x, y1, y2, label, col=BLK):
        """Vertical resistor between y1 (top) and y2 (bottom) at x."""
        m = (y1 + y2) / 2
        self.ln([(x, y1), (x, m - 22)], col, 2)
        self.r(x - 7, m - 22, 14, 44, "#fff8e1", col, rx=2, sw=1.6)
        self.ln([(x, m + 22), (x, y2)], col, 2)
        self.t(x + 12, m + 5, label, 13, col, "start", bold=True)

    def save(self, path):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
               f'viewBox="0 0 {self.w} {self.h}" font-family="DejaVu Sans, sans-serif">'
               f'<rect width="100%" height="100%" fill="#fff"/>{"".join(self.o)}</svg>')
        open(path, "w").write(svg)
