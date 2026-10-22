"""
sunMoon.py  --  a "Sun & Moon" collision made entirely of text characters.

A glowing orange sun and a blue moon drift toward each other, crash together
into one blended blob (orange + blue = hot pink/white where they overlap, with
sparks flying), then pull apart and do it all over again. Everything is drawn
with characters chosen by brightness, on top of a field of twinkling stars.

Run:   python sunMoon.py
Keys:  SPACE = pause / resume          ESC = quit
       LEFT / RIGHT = slower / faster clash
       UP / DOWN    = faster / slower spin
Needs: Python 3 with tkinter (included with the standard Windows/macOS installer).
"""

import math
import random
import time
import tkinter as tk
import tkinter.font as tkfont

# ----------------------------------------------------------------------------
# Settings you can tweak
# ----------------------------------------------------------------------------
COLS, ROWS = 120, 50            # size of the character grid
FONT_FAMILY, FONT_SIZE = "Consolas", 9
FPS = 24
NUM_STARS = 80
RAMP = " .,:;irsXA253hMHGS#9B&@"   # dark -> bright characters

SUN_R_FRAC = 0.30               # sun radius as a fraction of window height
MOON_R_FRAC = 0.23              # moon radius as a fraction of window height
CLASH_SPEED = 0.5               # radians/second of the approach/retreat cycle
SPARK_CHANCE = 0.05             # chance a cell in the overlap throws a spark

BG = "#05070d"
STAR_COLOR = (170, 190, 255)
SPARK_COLOR = (255, 250, 235)

# (brightness, (r, g, b)) gradient stops, dark -> bright
SUN_STOPS = [(0.0, (90, 20, 5)), (0.45, (255, 110, 20)),
             (0.8, (255, 185, 70)), (1.0, (255, 246, 215))]
MOON_STOPS = [(0.0, (8, 16, 55)), (0.45, (55, 105, 255)),
              (0.8, (140, 185, 255)), (1.0, (225, 240, 255))]


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------
def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))


def to_hex(rgb):
    r, g, b = (max(0, min(255, int(v))) for v in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def ramp(v, stops):
    """Look up a color on a multi-stop gradient for brightness v in 0..1."""
    v = max(0.0, min(1.0, v))
    for (v0, c0), (v1, c1) in zip(stops, stops[1:]):
        if v <= v1:
            return mix(c0, c1, (v - v0) / (v1 - v0))
    return stops[-1][1]


def screen(a, b):
    """'Screen' blend two colors: the result is always brighter than both."""
    return tuple(255 - (255 - x) * (255 - y) / 255 for x, y in zip(a, b))


def surface(lon, lat):
    """Cheap 'crater/granulation' texture in 0..1 from longitude and latitude."""
    t = (math.sin(lon * 3 + math.sin(lat * 4) * 2) * 0.5
         + math.sin(lon * 7 - lat * 5) * 0.3
         + math.sin(lat * 9 + lon * 2) * 0.2)
    return max(0.0, min(1.0, (t + 1.0) / 2.0))


# ----------------------------------------------------------------------------
# Scene: builds one frame as two grids (characters + colors). No tkinter here,
# so it can be tested without opening a window.
# ----------------------------------------------------------------------------
class Scene:
    def __init__(self, cols, rows, cell_w, cell_h):
        self.cols, self.rows = cols, rows
        self.cw, self.ch = cell_w, cell_h
        self.W, self.H = cols * cell_w, rows * cell_h

        self.sun_r = SUN_R_FRAC * self.H
        self.moon_r = MOON_R_FRAC * self.H
        margin = 10
        # Where each body sits when the two are as far apart as they get.
        self.sun_far = margin + self.sun_r
        self.moon_far = self.W - margin - self.moon_r

        self.phase = 0.0            # 0 = far apart, pi = fully overlapped
        self.clash_speed = CLASH_SPEED
        self.spin = 0.0
        self.spin_speed = 0.3

        rnd = random.Random(7)
        # star = [col, row, phase, speed]
        self.stars = [[rnd.randrange(cols), rnd.randrange(rows),
                       rnd.uniform(0, math.tau), rnd.uniform(0.6, 2.4)]
                      for _ in range(NUM_STARS)]

    def advance(self, dt):
        self.phase += self.clash_speed * dt
        self.spin += self.spin_speed * dt

    def closeness(self):
        """0 when far apart, 1 when sitting on top of each other."""
        return 0.5 - 0.5 * math.cos(self.phase)

    # -- stars ---------------------------------------------------------------
    def stamp_stars(self, chars, colors, t):
        """Draw every star as a twinkling '.', '+', or a '|-+-|' cross."""
        for col, row, phase, speed in self.stars:
            b = 0.5 + 0.5 * math.sin(phase + speed * t)
            if b < 0.3:
                continue
            color = to_hex(tuple(v * (0.25 + 0.75 * b) for v in STAR_COLOR))
            if b < 0.6:
                self._put(chars, colors, row, col, ".", color)
            elif b < 0.85:
                self._put(chars, colors, row, col, "+", color)
            else:
                self._put(chars, colors, row, col, "+", color)
                self._put(chars, colors, row - 1, col, "|", color)
                self._put(chars, colors, row + 1, col, "|", color)
                self._put(chars, colors, row, col - 1, "-", color)
                self._put(chars, colors, row, col + 1, "-", color)

    def _put(self, chars, colors, r, c, ch, color):
        if 0 <= r < self.rows and 0 <= c < self.cols:
            chars[r][c] = ch
            colors[r][c] = color

    # -- one body ------------------------------------------------------------
    def paint_body(self, kind, cx, cy, R, t, light=None):
        """Return {(row, col): (brightness, rgb)} for every cell this body covers.

        kind is "sun" (glows by itself, with a fuzzy corona) or "moon"
        (lit from the direction given in `light`).
        """
        out = {}
        cw, ch = self.cw, self.ch
        reach = R * 1.2
        c0 = max(0, int((cx - reach) / cw))
        c1 = min(self.cols - 1, int((cx + reach) / cw) + 1)
        r0 = max(0, int((cy - reach) / ch))
        r1 = min(self.rows - 1, int((cy + reach) / ch) + 1)
        spin = self.spin if kind == "sun" else -0.6 * self.spin

        for r in range(r0, r1 + 1):
            dy = ((r + 0.5) * ch - cy) / R
            for c in range(c0, c1 + 1):
                dx = ((c + 0.5) * cw - cx) / R
                d2 = dx * dx + dy * dy
                if d2 <= 1.0:
                    nz = math.sqrt(1.0 - d2)
                    lon = math.atan2(dx, nz) + spin
                    lat = math.asin(max(-1.0, min(1.0, -dy)))
                    tex = surface(lon, lat)
                    if kind == "sun":
                        v = (0.50 + 0.50 * nz) * (0.65 + 0.35 * tex)
                        v *= 1.0 + 0.06 * math.sin(t * 4 + lon * 6)   # flicker
                        stops = SUN_STOPS
                    else:
                        lx, ly, lz = light
                        lam = max(0.0, dx * lx + (-dy) * ly + nz * lz)
                        v = (0.08 + 0.92 * lam) * (0.60 + 0.40 * tex) * (0.70 + 0.30 * nz)
                        stops = MOON_STOPS
                    v = round(max(0.0, min(1.0, v)) * 24) / 24    # fewer distinct colors
                    out[(r, c)] = (v, ramp(v, stops))
                elif kind == "sun":
                    d = math.sqrt(d2)
                    if d <= 1.2:                                  # fuzzy corona
                        s = (1.2 - d) / 0.2
                        if random.random() < 0.5 * s:
                            out[(r, c)] = (0.10 + 0.22 * s, ramp(0.25 + 0.3 * s, SUN_STOPS))
        return out

    # -- both bodies, blended ------------------------------------------------
    def stamp_bodies(self, chars, colors, t):
        k = self.closeness()
        sun_x = self.W / 2 + (self.sun_far - self.W / 2) * (1 - k)
        moon_x = self.W / 2 + (self.moon_far - self.W / 2) * (1 - k)
        sun_y = self.H / 2
        moon_y = self.H / 2 + 0.05 * self.H * math.sin(self.phase * 1.5)   # slight bob

        # The moon is lit from the side that faces the sun.
        ux, uy = sun_x - moon_x, sun_y - moon_y
        mag = math.hypot(ux, uy)
        if mag < 1.0:
            ux, uy, mag = -1.0, 0.0, 1.0
        light = (0.87 * ux / mag, -0.87 * uy / mag, 0.5)

        sun = self.paint_body("sun", sun_x, sun_y, self.sun_r, t)
        moon = self.paint_body("moon", moon_x, moon_y, self.moon_r, t, light)

        last = len(RAMP) - 1
        for key in sun.keys() | moon.keys():
            s, m = sun.get(key), moon.get(key)
            r, c = key
            if s and m:                                  # the clash zone
                v = min(1.0, 1 - (1 - s[0]) * (1 - m[0]) + 0.15)
                rgb = screen(s[1], m[1])
                idx = int(v * last) + random.choice((-2, -1, 0, 1, 2))
                ch = RAMP[max(1, min(last, idx))]
                if random.random() < SPARK_CHANCE:
                    ch, rgb = random.choice("*+x'"), SPARK_COLOR
            else:
                v, rgb = s if s else m
                idx = int(v * last) + random.choice((-1, 0, 0, 1))   # shimmer
                ch = RAMP[max(1, min(last, idx))]
            chars[r][c] = ch
            colors[r][c] = to_hex(rgb)

    def render(self, t):
        chars = [[" "] * self.cols for _ in range(self.rows)]
        colors = [[BG] * self.cols for _ in range(self.rows)]
        self.stamp_stars(chars, colors, t)
        self.stamp_bodies(chars, colors, t)
        return chars, colors


# ----------------------------------------------------------------------------
# Window
# ----------------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        root.title("Sun & Moon")
        root.configure(bg=BG)

        self.font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE)
        self.cw = self.font.measure("M")
        self.ch = self.font.metrics("linespace")

        self.canvas = tk.Canvas(root, width=COLS * self.cw, height=ROWS * self.ch,
                                bg=BG, highlightthickness=0)
        self.canvas.pack()

        self.scene = Scene(COLS, ROWS, self.cw, self.ch)
        self.items = [[self.canvas.create_text(c * self.cw, r * self.ch, text=" ",
                                               anchor="nw", font=self.font, fill=BG)
                       for c in range(COLS)] for r in range(ROWS)]
        self.prev = [[(" ", BG)] * COLS for _ in range(ROWS)]

        self.paused = False
        self.t = 0.0
        self.last = time.perf_counter()

        root.bind("<space>", lambda e: self.toggle_pause())
        root.bind("<Escape>", lambda e: root.destroy())
        root.bind("<Left>", lambda e: self.change_clash(-0.1))
        root.bind("<Right>", lambda e: self.change_clash(0.1))
        root.bind("<Up>", lambda e: self.change_spin(0.1))
        root.bind("<Down>", lambda e: self.change_spin(-0.1))

        self.tick()

    def toggle_pause(self):
        self.paused = not self.paused

    def change_clash(self, delta):
        self.scene.clash_speed = max(0.05, self.scene.clash_speed + delta)

    def change_spin(self, delta):
        self.scene.spin_speed += delta

    def tick(self):
        now = time.perf_counter()
        dt = now - self.last
        self.last = now

        if not self.paused:
            self.t += dt
            self.scene.advance(dt)

        chars, colors = self.scene.render(self.t)
        for r in range(ROWS):
            for c in range(COLS):
                state = (chars[r][c], colors[r][c])
                if state != self.prev[r][c]:           # only touch changed cells
                    self.canvas.itemconfigure(self.items[r][c],
                                              text=state[0], fill=state[1])
                    self.prev[r][c] = state

        self.root.after(int(1000 / FPS), self.tick)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
