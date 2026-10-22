"""
sunMoon.py  --  a "Sun & Moon" collision made entirely of text characters.

A boiling, spotted sun and a cratered blue-silver moon drift toward each other,
crash together into one blended blob (orange + blue = hot pink/white where they
overlap, with sparks flying), then pull apart and do it all over again. Every
pixel is a character chosen by brightness, over a field of twinkling stars.

  Sun  : churning granulation, sunspots, darker edges, flickering corona rays,
         and prominence arcs that rise and fall off its rim.
  Moon : dark seas (maria), craters with lit rims and shadowed walls, a bright
         rayed crater, lit from whichever side faces the sun.

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

SUN_R_FRAC = 0.29               # sun radius as a fraction of window height
MOON_R_FRAC = 0.25              # moon radius as a fraction of window height
CLASH_SPEED = 0.5               # radians/second of the approach/retreat cycle
SPARK_CHANCE = 0.05             # chance a cell in the overlap throws a spark

BG = "#05070d"
STAR_COLOR = (170, 190, 255)
SPARK_COLOR = (255, 250, 235)

# (brightness, (r, g, b)) gradient stops, dark -> bright
SUN_STOPS = [(0.0, (60, 8, 2)), (0.25, (170, 40, 8)), (0.5, (255, 105, 15)),
             (0.75, (255, 170, 50)), (0.92, (255, 225, 130)), (1.0, (255, 248, 225))]
MOON_STOPS = [(0.0, (6, 10, 28)), (0.25, (35, 48, 95)), (0.55, (105, 125, 185)),
              (0.8, (180, 198, 235)), (1.0, (238, 246, 255))]

MAP_W, MAP_H = 256, 128         # resolution of the moon's surface maps
BUMP_EPS = 0.05                 # how far (radians) to look when shading craters


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


# ----------------------------------------------------------------------------
# The moon's surface, built once at startup
# ----------------------------------------------------------------------------
def build_moon_maps(seed=11):
    """Make the moon's surface.

    Returns (height, albedo): two MAP_H x MAP_W grids covering longitude 0..2pi
    and latitude -pi/2..pi/2. Height holds the craters (a bowl with a raised rim);
    albedo holds how bright the ground is (dark seas, bright highlands, bright
    young craters and the rays thrown out of one big crater).
    """
    rnd = random.Random(seed)
    lons = [(i + 0.5) / MAP_W * math.tau for i in range(MAP_W)]
    lats = [-math.pi / 2 + (j + 0.5) / MAP_H * math.pi for j in range(MAP_H)]
    cl = [math.cos(x) for x in lons]
    sl = [math.sin(x) for x in lons]
    sla = [math.sin(x) for x in lats]
    cla = [math.cos(x) for x in lats]

    def footprint(lon0, lat0, rad):
        """Yield (j, i, d) for every map pixel within angular distance rad of a point."""
        s0, c0 = math.sin(lat0), math.cos(lat0)
        cl0, sl0 = math.cos(lon0), math.sin(lon0)
        cos_rad = math.cos(min(rad, math.pi))
        j0 = max(0, math.floor((lat0 - rad + math.pi / 2) / math.pi * MAP_H))
        j1 = min(MAP_H - 1, math.floor((lat0 + rad + math.pi / 2) / math.pi * MAP_H) + 1)
        for j in range(j0, j1 + 1):
            if cla[j] < 0.05 or rad / cla[j] >= math.pi:
                cols = range(MAP_W)
            else:
                half = rad / cla[j]
                lo = math.floor((lon0 - half) / math.tau * MAP_W)
                hi = math.floor((lon0 + half) / math.tau * MAP_W) + 1
                cols = (i % MAP_W for i in range(lo, hi + 1))
            for i in cols:
                cosd = sla[j] * s0 + cla[j] * c0 * (cl[i] * cl0 + sl[i] * sl0)
                if cosd >= cos_rad:
                    yield j, i, math.acos(min(1.0, cosd))

    # Bright highlands with gentle mottling.
    A = [[0.92 + 0.06 * math.sin(lons[i] * 5 + lats[j] * 3) * math.cos(lons[i] * 2 - lats[j] * 4)
          for i in range(MAP_W)] for j in range(MAP_H)]
    H = [[0.0] * MAP_W for _ in range(MAP_H)]

    # Dark "seas" (maria): irregular patches of darker ground.
    maria = [(0.6, 0.35, 0.55), (1.5, 0.10, 0.42), (2.2, 0.50, 0.48), (3.1, 0.00, 0.40),
             (3.9, 0.30, 0.60), (4.7, -0.15, 0.45), (5.5, 0.40, 0.50), (1.0, -0.45, 0.30),
             (4.2, -0.50, 0.25)]
    mare = [[0.0] * MAP_W for _ in range(MAP_H)]
    for lon0, lat0, rad in maria:
        for j, i, d in footprint(lon0, lat0, rad * 1.45):
            wobble = 1.0 + 0.22 * math.sin(4 * lons[i] + 2 * lats[j]) \
                         + 0.12 * math.sin(9 * lons[i] - 3 * lats[j])
            m = max(0.0, min(1.0, (rad - d / wobble) / (0.3 * rad)))
            if m > mare[j][i]:
                mare[j][i] = m
    for j in range(MAP_H):
        for i in range(MAP_W):
            A[j][i] *= 1.0 - 0.62 * mare[j][i]

    # Craters: lots of small ones, a few big ones, a handful of young bright ones.
    craters = [(rnd.uniform(0, math.tau), math.asin(rnd.uniform(-1, 1)),
                0.08 + 0.30 * rnd.random() ** 2.6) for _ in range(80)]
    craters.sort(key=lambda c: -c[2])
    fresh = set(rnd.sample(range(40), 8))
    for n, (lon0, lat0, R) in enumerate(craters):
        young = n in fresh
        for j, i, d in footprint(lon0, lat0, R * (2.6 if young else 1.3)):
            if d < R:
                H[j][i] -= 0.28 * R * (1 - (d / R) ** 2)       # the bowl
                A[j][i] *= 0.93
            rim = math.exp(-((d - R) / (0.16 * R)) ** 2)        # the raised rim
            H[j][i] += 0.15 * R * rim
            A[j][i] *= 1 + 0.12 * rim
            if young and d >= R:
                A[j][i] *= 1 + 0.45 * math.exp(-((d - R) / (0.9 * R)) ** 2)

    # One big young crater with rays splashed out across the surface.
    t_lon, t_lat, t_R = 2.0, -0.7, 0.14
    for j, i, d in footprint(t_lon, t_lat, 1.1):
        if d < t_R:
            H[j][i] -= 0.22 * t_R * (1 - (d / t_R) ** 2)
        rim = math.exp(-((d - t_R) / (0.16 * t_R)) ** 2)
        H[j][i] += 0.12 * t_R * rim
        if d >= t_R:
            bearing = math.atan2(math.sin(lons[i] - t_lon) * cla[j], lats[j] - t_lat)
            ray = abs(math.cos(3.5 * bearing)) ** 10
            fade = math.exp(-(d - t_R) / 0.45)
            halo = math.exp(-((d - t_R) / (0.8 * t_R)) ** 2)
            A[j][i] *= 1 + 0.6 * ray * fade + 0.5 * halo
    return H, A


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

        self.moon_H, self.moon_A = build_moon_maps()

        # sunspot = (lon, sin lat, cos lat, umbra radius, penumbra radius, cos penumbra)
        spots = [(0.60, 0.25, 0.18), (0.95, 0.15, 0.11), (3.00, -0.30, 0.20),
                 (4.60, 0.35, 0.14), (5.70, -0.15, 0.12)]
        self.sunspots = [(lon, math.sin(lat), math.cos(lat), ru, 2.0 * ru, math.cos(2.0 * ru))
                         for lon, lat, ru in spots]
        # prominence = (angle on the rim, half-width, height in sun radii, phase, speed)
        self.prominences = [(0.7, 0.30, 0.45, 0.0, 1.1), (1.9, 0.20, 0.30, 2.2, 1.4),
                            (2.9, 0.26, 0.38, 1.7, 0.8), (4.1, 0.32, 0.50, 3.1, 0.9),
                            (5.3, 0.22, 0.34, 4.4, 1.3)]

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
        """Return {(row, col): (brightness, rgb, solid)} for every cell this body touches.

        kind is "sun" (glows by itself, with corona and prominences) or "moon"
        (cratered, lit from the direction given in `light`). `solid` is True for
        cells on the body itself and False for glow around it.
        """
        out = {}
        cw, ch = self.cw, self.ch
        reach = R * (1.65 if kind == "sun" else 1.2)
        c0 = max(0, int((cx - reach) / cw))
        c1 = min(self.cols - 1, int((cx + reach) / cw) + 1)
        r0 = max(0, int((cy - reach) / ch))
        r1 = min(self.rows - 1, int((cy + reach) / ch) + 1)
        spin = self.spin if kind == "sun" else 0.4 * self.spin

        if kind == "moon":
            lx, ly, lz = light
            lh = math.hypot(lx, ly) or 1.0
            lxn, lyn = lx / lh, ly / lh
            Hmap, Amap = self.moon_H, self.moon_A

        for r in range(r0, r1 + 1):
            dy = ((r + 0.5) * ch - cy) / R
            for c in range(c0, c1 + 1):
                dx = ((c + 0.5) * cw - cx) / R
                d2 = dx * dx + dy * dy

                if d2 <= 1.0:                                     # on the body
                    nz = math.sqrt(1.0 - d2)
                    lon = math.atan2(dx, nz) + spin
                    lat = math.asin(max(-1.0, min(1.0, -dy)))

                    if kind == "sun":
                        # Churning convection cells that drift over time.
                        g1 = (math.sin(lon * 9 + math.sin(lat * 6 + t * 0.5) * 2.0)
                              * math.sin(lat * 8 - lon * 3 + t * 0.7))
                        g2 = math.sin(lon * 17 + lat * 13 - t * 1.3)
                        tex = max(0.0, min(1.0, 0.5 + 0.28 * g1 + 0.18 * g2))
                        limb = 1.0 - 0.7 * (1.0 - nz)             # edges are darker/redder
                        v = limb * (0.68 + 0.42 * tex)
                        sin_lat, cos_lat = -dy, math.sqrt(max(0.0, 1.0 - dy * dy))
                        for lon0, s0, c0_, ru, rp, cos_rp in self.sunspots:
                            cosd = sin_lat * s0 + cos_lat * c0_ * math.cos(lon - lon0)
                            if cosd > cos_rp:
                                dd = math.acos(min(1.0, cosd))
                                if dd <= ru:
                                    v *= 0.22                     # dark umbra
                                else:
                                    v *= 0.22 + 0.78 * min(1.0, (dd - ru) / (rp - ru))
                        v *= 1.0 + 0.05 * math.sin(t * 4 + lon * 6)   # shimmer
                        stops = SUN_STOPS
                    else:
                        i = int((lon % math.tau) / math.tau * MAP_W) % MAP_W
                        j = min(MAP_H - 1, max(0, int((lat + math.pi / 2) / math.pi * MAP_H)))
                        # Look a little toward the light: terrain that drops away
                        # that way faces the light (bright), terrain that rises
                        # blocks it (dark). That is what makes craters pop.
                        lon2 = lon + BUMP_EPS * lxn / max(0.3, math.cos(lat))
                        i2 = int((lon2 % math.tau) / math.tau * MAP_W) % MAP_W
                        j2 = min(MAP_H - 1, max(0, int((lat + BUMP_EPS * lyn + math.pi / 2)
                                                       / math.pi * MAP_H)))
                        bump = max(-1.0, min(1.0, -(Hmap[j2][i2] - Hmap[j][i]) / BUMP_EPS * 1.2))
                        lam = dx * lx + (-dy) * ly + nz * lz
                        # Wrapped lighting: the shadow edge is soft, and a faint
                        # "earthshine" keeps the dark side from vanishing.
                        lam_eff = max(0.0, (lam + 0.3) / 1.3 + 0.6 * bump)
                        v = Amap[j][i] * (0.10 + 0.90 * min(1.0, lam_eff)) * (0.88 + 0.12 * nz)
                        v = max(0.0, v) ** 0.85
                        stops = MOON_STOPS

                    v = round(max(0.0, min(1.0, v)) * 32) / 32    # fewer distinct colors
                    out[(r, c)] = (v, ramp(v, stops), True)

                else:                                             # glow around the body
                    d = math.sqrt(d2)
                    if kind == "sun" and d <= 1.6:
                        theta = math.atan2(-dy, dx)
                        placed = False
                        for th0, width, height, ph, sp in self.prominences:
                            delta = (theta - th0 - 0.04 * t + math.pi) % math.tau - math.pi
                            if abs(delta) < width:
                                f = math.sqrt(1.0 - (delta / width) ** 2)
                                outer = 1.0 + height * (0.65 + 0.35 * math.sin(t * sp + ph)) * f
                                if outer - 0.12 <= d <= outer and random.random() < 0.9:
                                    out[(r, c)] = (0.70 + 0.30 * random.random(),
                                                   ramp(0.70 + 0.25 * random.random(), SUN_STOPS),
                                                   False)
                                    placed = True
                                    break
                        if not placed and d <= 1.5:               # flickering corona rays
                            s = (1.5 - d) / 0.5
                            ray = 0.5 + 0.5 * math.sin(theta * 9 + t * 0.7 + math.sin(theta * 3 + t))
                            if random.random() < 0.5 * s * (0.35 + 0.65 * ray):
                                out[(r, c)] = (0.10 + 0.24 * s,
                                               ramp(0.22 + 0.38 * s, SUN_STOPS), False)
                    elif kind == "moon" and d <= 1.1:             # faint glow on the lit side
                        facing = (dx * lxn + (-dy) * lyn) / d
                        if facing > 0:
                            s = (1.1 - d) / 0.1
                            if random.random() < 0.35 * s * facing:
                                out[(r, c)] = (0.10 + 0.14 * s,
                                               ramp(0.2 + 0.25 * s, MOON_STOPS), False)
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
            if s and m:                                  # the two overlap here
                clash = s[2] and m[2]                    # real collision, not just glow
                v = min(1.0, 1 - (1 - s[0]) * (1 - m[0]) + (0.15 if clash else 0.0))
                rgb = screen(s[1], m[1])
                jitter = (-2, -1, 0, 1, 2) if clash else (-1, 0, 0, 1)
                ch = RAMP[max(1, min(last, int(v * last) + random.choice(jitter)))]
                if clash and random.random() < SPARK_CHANCE:
                    ch, rgb = random.choice("*+x'"), SPARK_COLOR
            else:
                v, rgb, _ = s or m
                ch = RAMP[max(1, min(last, int(v * last) + random.choice((-1, 0, 0, 1))))]
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
