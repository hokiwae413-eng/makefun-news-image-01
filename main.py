#!/usr/bin/env python3
"""news-image-01: one image summing up the world news of Friday 13 Nov 2026.

A newspaper front page drawn procedurally with the Python standard library
only (zlib + struct for the PNG container). No network, no randomness, no
clock: every run writes byte-identical output to /output/entry.png.

Stories (all reported on 13 Nov 2026, from that day's news briefings):
  1. Ukraine fires nearly 1,200 drones at Russia; peace talks widen to
     European security, Russia agrees to European participation.
  2. U.S. forces down two Iranian drones headed for Bahrain; a tanker
     hits a mine in the Strait of Hormuz.
  3. Nvidia chief Jensen Huang resigns; shares fall 16% as a chip-control
     row splits Washington.
  4. Microsoft 365 outage enters its second day worldwide.
  5. Taiwan reports China's large unannounced military drills across the
     western Pacific.
  6. Israeli strike hits Nasser hospital in Khan Younis, Gaza: six killed.
  7. IEA forecasts a Q4 oil surplus of 1.7 million barrels a day.
"""

import math
import os
import struct
import zlib

# ---------------------------------------------------------------- font -----
# 5x7 bitmap font, one row per int, bit 4 = leftmost pixel. All text in the
# image is uppercase, so only capitals, digits and punctuation are needed.
FONT = {
    "A": (14, 17, 17, 31, 17, 17, 17), "B": (30, 17, 17, 30, 17, 17, 30),
    "C": (14, 17, 16, 16, 16, 17, 14), "D": (30, 17, 17, 17, 17, 17, 30),
    "E": (31, 16, 16, 30, 16, 16, 31), "F": (31, 16, 16, 30, 16, 16, 16),
    "G": (14, 17, 16, 23, 17, 17, 15), "H": (17, 17, 17, 31, 17, 17, 17),
    "I": (14, 4, 4, 4, 4, 4, 14),       "J": (7, 2, 2, 2, 2, 18, 12),
    "K": (17, 18, 20, 24, 20, 18, 17), "L": (16, 16, 16, 16, 16, 16, 31),
    "M": (17, 27, 21, 21, 17, 17, 17), "N": (17, 25, 21, 19, 17, 17, 17),
    "O": (14, 17, 17, 17, 17, 17, 14), "P": (30, 17, 17, 30, 16, 16, 16),
    "Q": (14, 17, 17, 17, 21, 18, 13), "R": (30, 17, 17, 30, 20, 18, 17),
    "S": (15, 16, 16, 14, 1, 1, 30),   "T": (31, 4, 4, 4, 4, 4, 4),
    "U": (17, 17, 17, 17, 17, 17, 14), "V": (17, 17, 17, 17, 17, 10, 4),
    "W": (17, 17, 17, 21, 21, 21, 10), "X": (17, 17, 10, 4, 10, 17, 17),
    "Y": (17, 17, 10, 4, 4, 4, 4),     "Z": (31, 1, 2, 4, 8, 16, 31),
    "0": (14, 17, 19, 21, 25, 17, 14), "1": (4, 12, 4, 4, 4, 4, 14),
    "2": (14, 17, 1, 6, 8, 16, 31),    "3": (31, 2, 4, 2, 1, 17, 14),
    "4": (2, 6, 10, 18, 31, 2, 2),     "5": (31, 16, 30, 1, 1, 17, 14),
    "6": (6, 8, 16, 30, 17, 17, 14),   "7": (31, 1, 2, 4, 8, 8, 8),
    "8": (14, 17, 17, 14, 17, 17, 14), "9": (14, 17, 17, 15, 1, 2, 12),
    " ": (0, 0, 0, 0, 0, 0, 0),        ".": (0, 0, 0, 0, 0, 12, 12),
    ",": (0, 0, 0, 0, 12, 4, 8),       ":": (0, 12, 12, 0, 12, 12, 0),
    ";": (0, 12, 12, 0, 12, 4, 8),     "'": (4, 4, 8, 0, 0, 0, 0),
    "-": (0, 0, 0, 14, 0, 0, 0),       "!": (4, 4, 4, 4, 4, 0, 4),
    "/": (1, 2, 2, 4, 8, 8, 16),       "&": (12, 18, 20, 8, 21, 18, 13),
    "(": (2, 4, 8, 8, 8, 4, 2),        ")": (8, 4, 2, 2, 2, 4, 8),
    "%": (25, 26, 2, 4, 8, 11, 19),    "?": (14, 17, 1, 2, 4, 0, 4),
    "+": (0, 4, 4, 14, 4, 4, 0),       "=": (0, 0, 14, 0, 14, 0, 0),
    "•": (0, 0, 12, 12, 12, 0, 0),
}

CHAR_W, CHAR_H = 6, 7  # glyph cell: 5 px + 1 px gap


def text_width(text, scale):
    """Pixel width of text at the given scale (no trailing gap)."""
    return len(text) * CHAR_W * scale - scale


def wrap_text(text, max_chars):
    """Greedy word wrap; returns a list of lines, each <= max_chars."""
    lines, cur = [], ""
    for word in text.split(" "):
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= max_chars:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# -------------------------------------------------------------- canvas -----
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bytes(bg)) * (w * h)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = c

    def rect(self, x, y, w, h, c):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def hline(self, x, y, w, c):
        self.rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.rect(x, y, 1, h, c)

    def line(self, x0, y0, x1, y1, c):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def disc(self, cx, cy, r, c):
        for dy in range(-r, r + 1):
            dx = int((r * r - dy * dy) ** 0.5)
            self.rect(cx - dx, cy + dy, 2 * dx + 1, 1, c)

    def ring(self, cx, cy, r, t, c):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                d2 = dx * dx + dy * dy
                if (r - t) * (r - t) <= d2 <= r * r:
                    self.set(cx + dx, cy + dy, c)

    def border(self, x, y, w, h, t, c):
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)

    def text(self, x, y, s, scale, c):
        s = s.upper()
        for ci, ch in enumerate(s):
            glyph = FONT.get(ch, FONT[" "])
            ox = x + ci * CHAR_W * scale
            for row in range(CHAR_H):
                bits = glyph[row]
                for col in range(5):
                    if bits >> (4 - col) & 1:
                        self.rect(ox + col * scale, y + row * scale,
                                  scale, scale, c)

    def text_center(self, cx, y, s, scale, c):
        self.text(cx - text_width(s, scale) // 2, y, s, scale, c)


# -------------------------------------------------------------- png out -----
def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data +
            struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def encode_png(w, h, px):
    raw = b"".join(b"\x00" + bytes(px[y * w * 3:(y + 1) * w * 3])
                   for y in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) +
            _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b""))


# -------------------------------------------------------------- palette -----
PAPER = bytes((245, 240, 225))
INK = bytes((26, 26, 46))
NAVY = bytes((24, 38, 66))
NAVY_DK = bytes((16, 26, 46))
RED = bytes((179, 57, 46))
BLUE = bytes((36, 86, 166))
SKY = bytes((126, 178, 224))
GOLD = bytes((201, 162, 39))
TEAL = bytes((38, 132, 120))
GREEN = bytes((74, 140, 74))
LIGHT = bytes((233, 226, 208))
WHITE = bytes((255, 255, 255))
GREY = bytes((120, 116, 104))
SEA = bytes((44, 110, 142))

W, H = 1024, 1024


# -------------------------------------------------------------- icons -------
# Each icon draws inside a (x, y, w, h) box on a coloured band.
def icon_drones(cv, x, y, w, h):
    cv.rect(x, y, w, h, NAVY_DK)
    # ground silhouette
    for i, (bx, bw, bh) in enumerate([(0, 34, 16), (40, 26, 26), (72, 30, 12),
                                      (108, 24, 22), (138, 34, 14), (178, 28, 20)]):
        cv.rect(x + bx, y + h - bh, bw, bh, INK)
    # drone swarm: dots with motion trails, denser top-right
    dots = [(18, 22), (44, 14), (66, 28), (88, 10), (112, 24), (134, 12),
            (156, 30), (178, 16), (30, 44), (58, 38), (96, 48), (124, 40),
            (150, 52), (172, 44), (76, 60), (110, 64), (140, 58)]
    for dx, dy in dots:
        cv.disc(x + dx, y + dy, 3, WHITE)
        cv.hline(x + dx - 9, y + dy, 6, GOLD)
    # one red flare
    cv.disc(x + 196, y + 26, 5, RED)
    cv.ring(x + 196, y + 26, 9, 2, GOLD)


def icon_ship(cv, x, y, w, h):
    cv.rect(x, y, w, h, SEA)
    cv.rect(x, y + h - 26, w, 26, bytes((30, 78, 104)))
    # tanker hull + bridge
    cv.rect(x + 30, y + h - 52, 150, 26, INK)
    cv.rect(x + 150, y + h - 72, 30, 20, INK)
    cv.vline(x + 60, y + h - 78, 26, INK)
    cv.rect(x + 44, y + h - 78, 34, 8, RED)
    # mine blast star above the bow
    bx, by = x + 196, y + 30
    for ang in range(0, 360, 30):
        r = 16
        ex = bx + int(r * math.cos(math.radians(ang)))
        ey = by + int(r * math.sin(math.radians(ang)))
        cv.line(bx, by, ex, ey, GOLD)
    cv.disc(bx, by, 7, RED)


def icon_chip(cv, x, y, w, h):
    cv.rect(x, y, w, h, NAVY)
    # chip body
    cx, cy = x + w // 2 - 34, y + 16
    cv.rect(cx, cy, 68, 56, INK)
    cv.rect(cx + 12, cy + 12, 44, 32, TEAL)
    cv.rect(cx + 24, cy + 22, 20, 12, WHITE)
    for px in range(cx - 6, cx + 74, 14):
        cv.rect(px, cy - 8, 6, 8, GOLD)
        cv.rect(px, cy + 56, 6, 8, GOLD)
    for py in range(cy - 2, cy + 58, 14):
        cv.rect(cx - 8, py, 8, 6, GOLD)
        cv.rect(cx + 68, py, 8, 6, GOLD)
    # red down arrow on the right
    ax = x + w - 34
    cv.rect(ax, y + 14, 10, 44, RED)
    cv.line(ax - 8, y + 58, ax + 5, y + 78, RED)
    cv.line(ax + 18, y + 58, ax + 5, y + 78, RED)


def icon_cloud(cv, x, y, w, h):
    cv.rect(x, y, w, h, BLUE)
    cx, cy = x + w // 2, y + h // 2 - 6
    cv.disc(cx - 34, cy + 8, 22, WHITE)
    cv.disc(cx, cy - 10, 28, WHITE)
    cv.disc(cx + 34, cy + 8, 22, WHITE)
    cv.rect(cx - 52, cy - 2, 104, 26, WHITE)
    # red X over the cloud
    cv.line(cx - 22, cy - 26, cx + 22, cy + 18, RED)
    cv.line(cx + 22, cy - 26, cx - 22, cy + 18, RED)


def icon_island(cv, x, y, w, h):
    cv.rect(x, y, w, h, SKY)
    cv.rect(x, y + h - 30, w, 30, SEA)
    # island
    cv.disc(x + 100, y + h - 34, 34, GREEN)
    cv.rect(x + 66, y + h - 40, 68, 12, GREEN)
    # two warships
    for sx in (28, 150):
        cv.rect(x + sx, y + h - 22, 44, 10, INK)
        cv.rect(x + sx + 14, y + h - 32, 16, 10, INK)
        cv.vline(x + sx + 22, y + h - 44, 12, INK)
    # dashed patrol arc
    for i in range(0, 9):
        cv.disc(x + 20 + i * 20, y + 26 + (i % 2) * 6, 3, RED)


def icon_hospital(cv, x, y, w, h):
    cv.rect(x, y, w, h, LIGHT)
    # hospital building
    cv.rect(x + 52, y + 14, 110, h - 28, WHITE)
    cv.border(x + 52, y + 14, 110, h - 28, 3, INK)
    # windows
    for wx in (66, 92, 118, 144):
        for wy in (y + 52, y + 74):
            cv.rect(x + wx, wy, 12, 12, BLUE)
    # red cross sign
    cv.rect(x + 92, y + 22, 30, 10, RED)
    cv.rect(x + 102, y + 12, 10, 30, RED)


def icon_barrel(cv, x, y, w, h):
    cv.rect(x, y, w, h, bytes((232, 222, 190)))
    # oil barrel: flat top edge instead of a domed disc
    bx, by = x + 62, y + 18
    cv.rect(bx, by, 64, h - 36, INK)
    cv.rect(bx - 4, by, 72, 6, GOLD)
    cv.rect(bx - 4, by + 8, 72, 6, GOLD)
    cv.rect(bx - 4, by + h - 50, 72, 6, GOLD)
    # green down arrow: surplus pushes prices down
    ax = x + w - 52
    cv.rect(ax, y + 16, 10, 40, GREEN)
    cv.line(ax - 8, y + 56, ax + 5, y + 74, GREEN)
    cv.line(ax + 18, y + 56, ax + 5, y + 74, GREEN)


ICONS = {"drones": icon_drones, "ship": icon_ship, "chip": icon_chip,
         "cloud": icon_cloud, "island": icon_island,
         "hospital": icon_hospital, "barrel": icon_barrel}


# -------------------------------------------------------------- layout ------
def draw_masthead(cv):
    cv.rect(24, 24, 976, 104, NAVY)
    cv.text_center(512, 34, "THE WORLD", 9, WHITE)
    cv.text_center(512, 106, "FRIDAY, 13 NOVEMBER 2026", 2, GOLD)
    cv.rect(24, 132, 976, 6, RED)
    cv.text_center(512, 146, "ONE DAY IN THE NEWS", 2, INK)


def draw_lead(cv):
    x, y, w, h = 24, 172, 976, 236
    cv.rect(x, y, w, h, LIGHT)
    cv.border(x, y, w, h, 3, INK)
    cv.text(x + 20, y + 16, "LEAD STORY  -  EUROPE", 2, RED)
    cv.text(x + 20, y + 44, "UKRAINE'S BIGGEST", 5, INK)
    cv.text(x + 20, y + 84, "DRONE NIGHT", 5, INK)
    sub = ("Nearly 1,200 drones in one of the war's largest aerial "
           "attacks, as peace talks widen to all of Europe.")
    lines = wrap_text(sub, 46)
    for i, ln in enumerate(lines):
        cv.text(x + 20, y + 138 + i * 18, ln, 2, INK)
    cv.text(x + 20, y + 206, "KYIV  •  MOSCOW  •  DUBLIN", 2, GREY)
    # drone-swarm picture on the right
    icon_drones(cv, x + 640, y + 16, 316, 204)


def draw_panel(cv, x, y, w, h, story):
    cv.rect(x, y, w, h, WHITE)
    cv.border(x, y, w, h, 3, INK)
    ICONS[story["icon"]](cv, x + 3, y + 3, w - 6, 104)
    cv.text(x + 12, y + 118, story["kicker"], 2, RED)
    head_lines = wrap_text(story["headline"], 16)
    for i, ln in enumerate(head_lines[:2]):
        cv.text(x + 12, y + 140 + i * 22, ln, 3, INK)
    cap_lines = wrap_text(story["caption"], 24)
    for i, ln in enumerate(cap_lines[:4]):
        cv.text(x + 12, y + 192 + i * 17, ln, 2, INK)


# -------------------------------------------------------------- stories -----
STORIES = [
    {"kicker": "THE GULF", "icon": "ship",
     "headline": "U.S. DOWNS IRANIAN DRONES",
     "caption": ("Two attack drones headed for Bahrain intercepted; "
                 "a tanker hits a mine in Hormuz.")},
    {"kicker": "TECH - BUSINESS", "icon": "chip",
     "headline": "NVIDIA CHIEF RESIGNS",
     "caption": ("Jensen Huang steps down; shares fall 16% as a "
                 "chip-control row splits Washington.")},
    {"kicker": "TECH - OUTAGE", "icon": "cloud",
     "headline": "MICROSOFT 365 DOWN WORLDWIDE",
     "caption": ("Outlook and Teams offline for a second day; "
                 "businesses, courts and 911 calls hit.")},
    {"kicker": "ASIA - TAIWAN", "icon": "island",
     "headline": "CHINA'S PACIFIC DRILLS",
     "caption": ("Taiwan reports a huge unannounced military exercise "
                 "across the western Pacific.")},
    {"kicker": "MIDDLE EAST - GAZA", "icon": "hospital",
     "headline": "STRIKE HITS GAZA HOSPITAL",
     "caption": ("Six killed at Nasser hospital in Khan Younis, "
                 "including a surgeon.")},
    {"kicker": "ENERGY - OIL", "icon": "barrel",
     "headline": "OIL SURPLUS LOOMS",
     "caption": ("IEA sees supply beating demand by 1.7 million "
                 "barrels a day in Q4.")},
]


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    cv = Canvas(W, H, PAPER)
    cv.border(8, 8, W - 16, H - 16, 3, INK)
    draw_masthead(cv)
    draw_lead(cv)
    for i, story in enumerate(STORIES):
        x = 24 + (i % 3) * 329
        y = 424 + (i // 3) * 280
        draw_panel(cv, x, y, 317, 264, story)
    cv.text_center(512, 984, "COMPILED FROM THE DAY'S REPORTS", 2, GREY)
    data = encode_png(W, H, cv.px)
    with open(os.path.join(out_dir, "entry.png"), "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
