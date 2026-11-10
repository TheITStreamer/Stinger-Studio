"""
effects.py - stinger styles that need no images.

Every effect here is drawn from maths alone: noise, waves, circles. Each one
reaches full, solid cover at the transition point and clears afterwards, the
same as the image styles.

The UI preview runs a line for line copy of this code (see EFFECTS in
ui.html), using the same integer hash, so a seed looks the same in the preview
and in the render. If you change a formula here, change it there too.

Effects:
  static     TV snow that floods in and breaks up again
  glitch     bands of broken colour blocks with an RGB split
  smoke      thick smoke rolls up from the bottom and drifts away
  water      the screen fills with water, then drains
  circle     two coloured circles open out, then a hole opens in the middle
  ink        drops of ink land and spread until they join up
  lightning  a storm rolls in, bolts strike, white flash at the cut
  pixelate   big coloured blocks pop in, then smaller ones fill the gaps
  vhs        lines of a blue VHS screen slide in with tracking noise
  crt        an old TV switching on and off: a line, then the whole screen
  glass      shards of coloured glass appear with bright cracks between them
  splatter   splats of paint in different colours until nothing is left uncovered
  warp       star streaks fly out from the middle as space closes in
  blinds     venetian blinds close, then open
  diamond    diamonds grow in a wave across the screen
  portal     a swirling portal opens from the middle and fills the screen
"""
import math

import numpy as np
from PIL import Image

EFFECTS = ["static", "glitch", "smoke", "water", "circle", "ink",
           "lightning", "pixelate", "vhs", "crt", "glass", "splatter", "warp",
           "blinds", "diamond", "portal",
           "clouds", "rainglass", "snow", "bubbles", "sand", "matrix", "hologram",
           "signal", "datamosh", "filmburn", "grain", "channel", "bitwipe", "iris",
           "page", "curtain", "tiles", "radial", "zoomblur", "liquid", "bars",
           "blobs", "aurora", "speed", "energy", "loading", "health", "lag"]

# Effects that are mostly grey, so hue and saturation barely touch them.
# These also get a tint colour.
TINT_EFFECTS = ("static", "smoke", "snow")

# Each effect is worked out on a smaller grid and scaled up to the output size.
# Smoke and light are soft, so a quarter size grid looks the same and is far
# quicker. Static uses a fixed grid so its grain is the same size at any
# resolution. The second value says how to scale up.
GRID = {
    "static":    (("rows", 270), Image.NEAREST),
    "glitch":    (("frac", 0.5), Image.NEAREST),
    "smoke":     (("frac", 0.25), Image.BILINEAR),
    "water":     (("frac", 0.5), Image.BILINEAR),
    "circle":    (("frac", 0.5), Image.BILINEAR),
    "ink":       (("frac", 0.5), Image.BILINEAR),
    "lightning": (("frac", 0.5), Image.BILINEAR),
    "pixelate":  (("frac", 0.5), Image.NEAREST),
    "vhs":       (("rows", 240), Image.BILINEAR),
    "crt":       (("frac", 0.5), Image.BILINEAR),
    "glass":     (("frac", 0.5), Image.BILINEAR),
    "splatter":  (("frac", 0.5), Image.BILINEAR),
    "warp":      (("frac", 0.5), Image.BILINEAR),
    "blinds":    (("frac", 0.5), Image.BILINEAR),
    "diamond":   (("frac", 0.5), Image.BILINEAR),
    "portal":    (("frac", 0.5), Image.BILINEAR),
    "clouds":     (("frac", 0.25), Image.BILINEAR),
    "rainglass":  (("frac", 0.5), Image.BILINEAR),
    "snow":       (("frac", 0.5), Image.BILINEAR),
    "bubbles":    (("frac", 0.5), Image.BILINEAR),
    "sand":       (("frac", 0.5), Image.BILINEAR),
    "matrix":     (("frac", 0.5), Image.NEAREST),
    "hologram":   (("frac", 0.5), Image.BILINEAR),
    "signal":     (("frac", 0.5), Image.NEAREST),
    "datamosh":   (("frac", 0.5), Image.NEAREST),
    "filmburn":   (("frac", 0.25), Image.BILINEAR),
    "grain":      (("frac", 0.5), Image.NEAREST),
    "channel":    (("frac", 0.5), Image.BILINEAR),
    "bitwipe":    (("frac", 0.5), Image.NEAREST),
    "iris":       (("frac", 0.5), Image.BILINEAR),
    "page":       (("frac", 0.5), Image.BILINEAR),
    "curtain":    (("frac", 0.5), Image.BILINEAR),
    "tiles":      (("frac", 0.5), Image.BILINEAR),
    "radial":     (("frac", 0.5), Image.BILINEAR),
    "zoomblur":   (("frac", 0.5), Image.BILINEAR),
    "liquid":     (("frac", 0.5), Image.BILINEAR),
    "bars":       (("frac", 0.5), Image.NEAREST),
    "blobs":      (("frac", 0.5), Image.BILINEAR),
    "aurora":     (("frac", 0.25), Image.BILINEAR),
    "speed":      (("frac", 0.5), Image.BILINEAR),
    "energy":     (("frac", 0.5), Image.BILINEAR),
    "loading":    (("frac", 0.5), Image.BILINEAR),
    "health":     (("frac", 0.5), Image.BILINEAR),
    "lag":        (("frac", 0.5), Image.NEAREST),
}

# Effects with their own colour pickers. The values are the defaults, in
# order: circle is first circle then second, diamond is the two checker
# colours, blinds is top then bottom of the gradient.
DEFAULT_COLOURS = {
    "circle": ["#5cc8ff", "#ff5c8a"],
    "diamond": ["#ff5c8a", "#d94073"],
    "blinds": ["#ff5c8a", "#7340d9"],
    "iris": ["#0d0f14", "#ff5c8a"],
    "page": ["#f4efe6"],
    "curtain": ["#a3122a", "#e8b84a"],
    "tiles": ["#5cc8ff", "#7340d9"],
    "radial": ["#ff5c8a", "#5cc8ff"],
    "loading": ["#5cc8ff", "#2e8bd9"],
    "health": ["#e5383b", "#ffd166"],
}

# Effects that can be aimed, the way each one moves by default, and the
# directions on offer. Direction means which way the effect travels.
EFFECT_DIRS = {
    "water": ["up", "down", "left", "right"],
    "smoke": ["up", "down", "left", "right"],
    "blinds": ["down", "up", "right", "left"],
    "diamond": ["right", "left", "down", "up"],
    "vhs": ["left", "right"],
    "clouds": ["right", "left"],
    "hologram": ["down", "up"],
    "matrix": ["down", "up"],
    "page": ["left", "right"],
    "liquid": ["down", "up"],
    "loading": ["right", "left"],
    "health": ["right", "left"],
}
NATURAL_DIR = {e: d[0] for e, d in EFFECT_DIRS.items()}
# these three are turned by remapping the coordinates; blinds and diamond
# handle direction themselves so their shapes don't get stretched
REMAP_EFFECTS = ("water", "smoke", "vhs", "clouds", "hologram", "matrix",
                 "page", "liquid", "loading", "health")

# How many drops ink and splatter use, and the grid each count is spread on.
# One drop per cell keeps every pixel close to a drop, which is what lets
# them promise full cover at the transition point.
DROP_GRIDS = {1: (1, 1), 2: (2, 1), 3: (3, 1), 4: (2, 2), 6: (3, 2),
              8: (4, 2), 9: (3, 3), 12: (4, 3)}

_M32 = 0xFFFFFFFF


# --------------------------------------------------------------------------
# noise. Integer hash with 32 bit wraparound, matched in JS with Math.imul.
# --------------------------------------------------------------------------
def _u32(x):
    return (np.asarray(x, dtype=np.int64) & _M32).astype(np.uint32)


def hash2(x, y, s):
    """Hash two integer coordinates and a salt to a float in [0, 1)."""
    x = _u32(x)
    y = _u32(y)
    s = np.uint32((int(s) * 2246822519) & _M32)
    with np.errstate(over="ignore"):
        h = x * np.uint32(374761393) + y * np.uint32(668265263) + s
        h = (h ^ (h >> np.uint32(13))) * np.uint32(1274126177)
        h = h ^ (h >> np.uint32(16))
    return h.astype(np.float64) / 4294967296.0


def vnoise(x, y, s):
    """Smooth value noise in [0, 1)."""
    xi = np.floor(x)
    yi = np.floor(y)
    xf = x - xi
    yf = y - yi
    xi = xi.astype(np.int64)
    yi = yi.astype(np.int64)
    u = xf * xf * (3.0 - 2.0 * xf)
    v = yf * yf * (3.0 - 2.0 * yf)
    a = hash2(xi, yi, s)
    b = hash2(xi + 1, yi, s)
    c = hash2(xi, yi + 1, s)
    d = hash2(xi + 1, yi + 1, s)
    top = a + (b - a) * u
    bot = c + (d - c) * u
    return top + (bot - top) * v


def fbm(x, y, s, octaves=4):
    """Layered noise, normalised back to [0, 1)."""
    total = 0.0
    amp = 0.5
    norm = 0.0
    f = 1.0
    for i in range(octaves):
        total = total + vnoise(x * f, y * f, s + i * 17) * amp
        norm += amp
        amp *= 0.5
        f *= 2.0
    return total / norm


def _c01(x):
    return np.clip(x, 0.0, 1.0)


def _mix(a, b, f):
    return a + (b - a) * f


# --------------------------------------------------------------------------
# the effects. Each takes pixel centre coordinates U (0..aspect) and
# V (0..1), plus a state dict, and returns (r, g, b, alpha) as float arrays.
# --------------------------------------------------------------------------
def fx_static(U, V, st):
    s, sec, k = st["salt"], st["sec"], st["k"]
    rows = st["gh"]
    ci = np.floor(U * rows)
    cj = np.floor(V * rows)
    frame = int(math.floor(sec * 24.0))
    n = hash2(ci, cj, s + frame * 3)
    lum = 0.12 + 0.88 * n
    lum = np.where(cj.astype(np.int64) % 2 == 1, lum * 0.78, lum)
    roll = V - (sec * 0.7 - math.floor(sec * 0.7))
    lum = np.minimum(1.0, lum + np.exp(-(roll * 8.0) ** 2) * 0.25)
    m = (0.65 * vnoise(U * 5.0, V * 5.0 + sec * 3.0, s + 101)
         + 0.35 * hash2(cj, 0, s + 202 + frame * 7))
    e = 0.12
    a = _c01((k * (1.0 + e) - m) / e)
    return lum, lum, lum, a


GLITCH_PAL = np.array([
    [0.04, 0.04, 0.08],
    [0.09, 0.05, 0.16],
    [0.15, 0.10, 0.30],
    [1.00, 0.36, 0.54],
    [0.36, 0.78, 1.00],
    [0.95, 0.95, 0.98],
])
# cumulative pick thresholds for the palette above, mostly dark
GLITCH_CUT = (0.30, 0.52, 0.68, 0.82, 0.94)


def _glitch_pick(h):
    idx = np.zeros(h.shape, dtype=np.int64)
    for c in GLITCH_CUT:
        idx = idx + (h >= c)
    return idx


def fx_glitch(U, V, st):
    s, sec, k = st["salt"], st["sec"], st["k"]
    step = int(math.floor(sec * 14.0))
    b = np.floor(V * 14.0)
    b2 = np.floor(V * 70.0)
    jump = hash2(b, step, s + 1) > 0.55
    shift = (np.where(jump, (hash2(b, step, s + 2) - 0.5) * 0.35, 0.0)
             + (hash2(b2, step, s + 3) - 0.5) * 0.02)
    split = 0.004 + 0.012 * hash2(b2, step, s + 4)
    widths = 6.0 + 10.0 * hash2(b, 0, s + 5)
    out = []
    for ch, off in enumerate((1.0, 0.0, -1.0)):
        uu = U + shift + off * split
        bx = np.floor(uu * widths)
        idx = _glitch_pick(hash2(bx, b, s + 6 + step))
        out.append(GLITCH_PAL[idx, ch])
    grain = 0.85 + 0.15 * hash2(np.floor(U * 200.0), b2, s + 10 + step)
    bx0 = np.floor((U + shift) * 8.0)
    m = (0.5 * hash2(b, 1, s + 7) + 0.3 * hash2(b2, step, s + 8)
         + 0.2 * hash2(bx0, b2, s + 9 + step))
    a = (m < k).astype(np.float64)
    return out[0] * grain, out[1] * grain, out[2] * grain, a


def fx_smoke(U, V, st):
    s, sec, k = st["salt"], st["sec"], st["k"]
    px = U * 2.2
    py = V * 2.2 + sec * 0.35
    q1 = fbm(px + 1.7, py + 9.2 + sec * 0.15, s + 10)
    q2 = fbm(px + 8.3, py + 2.8, s + 11)
    n = fbm(px + 1.8 * q1, py + 1.8 * q2, s + 12)
    # comes in from the bottom, clears from the bottom on the way out
    side = (1.0 - V) if st["entering"] else V
    m = 0.55 * n + 0.45 * side
    e = 0.22
    a = _c01((k * (1.0 + e) - m) / e)
    shade = _c01(0.15 + 0.6 * n + 0.25 * q1)
    shade = shade * (0.75 + 0.25 * a)
    return shade * 0.92, shade * 0.94, shade * 1.0, a


def fx_water(U, V, st):
    s, sec, k = st["salt"], st["sec"], st["k"]
    fill = k * 1.3 - 0.1
    ph = st["seedf"] * 6.283
    ys = (1.0 - fill
          + 0.035 * np.sin(U * 7.0 + sec * 5.0 + ph)
          + 0.018 * np.sin(U * 15.3 - sec * 8.0)
          + 0.03 * (vnoise(U * 3.0, np.full_like(U, sec * 1.5), s + 20) - 0.5))
    d = V - ys
    a = _c01(d / 0.004 + 0.5)
    f = _c01(d * 1.6)
    r = _mix(0.18, 0.02, f)
    g = _mix(0.62, 0.12, f)
    bl = _mix(0.92, 0.34, f)
    c1 = vnoise(U * 9.0 + sec * 0.8, V * 9.0 - sec * 0.5, s + 21)
    c2 = vnoise(U * 9.0 - sec * 0.6 + 3.1, V * 9.0 + sec * 0.4, s + 22)
    caus = _c01(1.0 - np.abs(c1 - c2) * 5.0) ** 3 * 0.35 * (1.0 - f * 0.6)
    r, g, bl = r + caus, g + caus, bl + caus
    foam = _c01(1.0 - d / 0.018) * (d > 0) * 0.8
    r = _mix(r, 0.85, foam)
    g = _mix(g, 0.95, foam)
    bl = _mix(bl, 1.0, foam)
    return r, g, bl, a


def fx_circle(U, V, st):
    k, asp = st["k"], st["aspect"]
    d = np.sqrt((U - asp / 2.0) ** 2 + (V - 0.5) ** 2)
    R = math.sqrt(asp * asp + 1.0) / 2.0 + 0.02
    ew = 0.003
    if st["entering"]:
        ra = R * min(1.0, max(0.0, k * 1.25)) - ew
        rb = R * min(1.0, max(0.0, k * 1.25 - 0.25)) - ew
        aa = _c01((ra - d) / ew + 0.5)
        ab = _c01((rb - d) / ew + 0.5)
    else:
        w = 1.0 - k
        ha = R * min(1.0, max(0.0, w * 1.25 - 0.25)) - ew
        hb = R * min(1.0, max(0.0, w * 1.25)) - ew
        aa = _c01((d - ha) / ew + 0.5)
        ab = _c01((d - hb) / ew + 0.5)
    shadeb = 0.85 + 0.15 * (1.0 - _c01(d / R))
    a = ab + aa * (1.0 - ab)
    safe = np.maximum(a, 1e-6)
    wa = aa * (1.0 - ab)
    ca, cb = st["cols"][0], st["cols"][1]
    r = (cb[0] * shadeb * ab + ca[0] * wa) / safe
    g = (cb[1] * shadeb * ab + ca[1] * wa) / safe
    b = (cb[2] * shadeb * ab + ca[2] * wa) / safe
    return r, g, b, a


def _frac(x):
    return x - np.floor(x)


def drop_points(st, off, count=None):
    """One point per grid cell, jittered inside the middle half of the cell.
    Every pixel is then within 0.75 of a cell diagonal of a point, which is
    what lets ink and splatter promise full cover. Order matters: the preview
    walks it the same way. Returns (points, that distance)."""
    s, asp = st["salt"], st["aspect"]
    cols, rows = DROP_GRIDS[count or st["drops"]]
    cw, ch = asp / cols, 1.0 / rows
    out = []
    for j in range(rows):
        for i in range(cols):
            hx = float(hash2(i, j, s + off))
            hy = float(hash2(i, j, s + off + 1))
            hd = float(hash2(i, j, s + off + 2))
            out.append(((i + 0.25 + 0.5 * hx) * cw, (j + 0.25 + 0.5 * hy) * ch,
                        hd, j * cols + i))
    return out, 0.75 * math.sqrt(cw * cw + ch * ch)


def fx_ink(U, V, st):
    s, k = st["salt"], st["k"]
    f = np.full_like(U, 9.0)
    for cx, cy, hd, n in st["pts"]:
        d = np.sqrt((U - cx) ** 2 + (V - cy) ** 2) * (1.0 + 0.8 * hd)
        f = np.minimum(f, d)
    # worst case is the drop distance times 1.8, plus 0.07 of noise
    f = f + 0.14 * (fbm(U * 5.0, V * 5.0, s + 42) - 0.5)
    fmax = st["reach"] * 1.8 + 0.1
    # spread slowly at first so the drops read as drops before they join
    T = k ** 1.6 * (fmax + 0.07) - 0.08
    a = _c01((T - f) / 0.008 + 0.5)
    rim = 1.0 - 0.5 * _c01(1.0 - (T - f) / 0.035)
    core = _c01(f / fmax)
    return (_mix(0.05, 0.16, core) * rim, _mix(0.04, 0.12, core) * rim,
            _mix(0.16, 0.45, core) * rim, a)


def fx_lightning(U, V, st):
    s, sec, k, t, asp = st["salt"], st["sec"], st["k"], st["t"], st["aspect"]
    step = int(math.floor(sec * 12.0))
    glow = np.zeros_like(U)
    core = np.zeros_like(U)
    for j in range(3):
        if float(hash2(j, step, s + 51)) >= 0.35 + 0.65 * k:
            continue
        x0 = (0.15 + 0.7 * float(hash2(j, step, s + 52))) * asp
        row = np.full_like(V, float(j + step * 3))
        x = (x0 + 0.15 * (vnoise(V * 6.0, row, s + 53) - 0.5)
             + 0.05 * (vnoise(V * 22.0, row, s + 54) - 0.5))
        dx = np.abs(U - x)
        core = core + np.exp(-(dx / 0.006) ** 2)
        glow = glow + np.exp(-(dx / 0.05) ** 2) * 0.5
    flash = math.exp(-((t - st["in_frac"]) / 0.06) ** 2)
    fl = 0.25 * k if float(hash2(step, 9, s + 55)) > 0.7 else 0.0
    r = 0.06 + fl * 0.5 + glow * 0.35 + core * 0.9 + flash * 0.85
    g = 0.06 + fl * 0.55 + glow * 0.4 + core * 0.92 + flash * 0.88
    b = 0.16 + fl * 0.8 + glow * 0.8 + core + flash
    a = _c01(k * 1.5 - 0.5 + (glow + core) * k * 1.5)
    return r, g, b, a


PIX_A = (1.00, 0.36, 0.54)
PIX_C = (0.45, 0.25, 0.85)
PIX_B = (0.36, 0.78, 1.00)


def fx_pixelate(U, V, st):
    s, k, asp = st["salt"], st["k"], st["aspect"]
    cx = np.floor(U * 9.0)
    cy = np.floor(V * 9.0)
    hf = hash2(np.floor(U * 27.0), np.floor(V * 27.0), s + 61)
    m = 0.5 * hash2(cx, cy, s + 60) + 0.5 * hf
    a = (m < k).astype(np.float64)
    g = _c01(((cx + 0.5) / 9.0 / asp + (cy + 0.5) / 9.0) * 0.5) * 2.0
    w1 = _c01(g)
    w2 = _c01(g - 1.0)
    shade = 0.8 + 0.2 * hf
    out = [(PIX_A[c] + (PIX_C[c] - PIX_A[c]) * w1
            + (PIX_B[c] - PIX_C[c]) * w2) * shade for c in range(3)]
    return out[0], out[1], out[2], a


def fx_vhs(U, V, st):
    s, sec, k, asp = st["salt"], st["sec"], st["k"], st["aspect"]
    step = int(math.floor(sec * 30.0))
    row = np.floor(V * 240.0)
    hr = hash2(row, 0, s + 70)
    jit = ((hash2(np.floor(V * 30.0), step // 2, s + 71) - 0.5) * 0.02
           + (hash2(row, step, s + 72) - 0.5) * 0.004)
    c = _c01((k - 0.6 * hr) / 0.4)
    # jitter only while a line is part way in, so it can't poke in early
    # or leave a gap once it is home
    a = (U > (asp + 0.02) * (1.0 - c) + jit * c * (1.0 - c) * 4.0).astype(np.float64)
    uu = U + jit
    ln = 0.85 + 0.15 * hash2(row, step, s + 73)
    ln = np.where(row.astype(np.int64) % 2 == 1, ln * 0.85, ln)
    r, g, b = 0.05 * ln, 0.18 * ln, 0.80 * ln
    streak = (hash2(np.floor(uu * 40.0 + hr * 40.0), row, s + 74 + step)
              > 0.985).astype(np.float64)
    pos = sec * 0.45 - math.floor(sec * 0.45)
    band = (np.abs(V - pos) < 0.04) * 0.85
    noise = hash2(np.floor(uu * 300.0), row, s + 75 + step)
    r = _mix(_mix(r, 0.9, streak), noise, band)
    g = _mix(_mix(g, 0.9, streak), noise, band)
    b = _mix(_mix(b, 0.9, streak), noise, band)
    return r, g, b, a


def fx_crt(U, V, st):
    k, asp = st["k"], st["aspect"]
    ew = 0.004
    a1 = min(1.0, k / 0.3)
    b1 = min(1.0, max(0.0, (k - 0.3) / 0.7))
    hw = a1 * (asp / 2.0 + 0.02) - ew
    hh = 0.003 + b1 * 0.52
    du = np.abs(U - asp / 2.0)
    dv = np.abs(V - 0.5)
    a = _c01((hw - du) / ew + 0.5) * _c01((hh - dv) / ew + 0.5)
    edge = np.exp(-((hh - dv) / 0.01) ** 2) * (0.6 * (1.0 - b1) + 0.25)
    scan = np.where(np.floor(V * 270.0).astype(np.int64) % 2 == 1, 0.7, 1.0)
    base = (0.02 + 0.06 * np.exp(-(du * du + dv * dv) * 3.0)) * scan
    lum = base + (1.0 - b1) + edge
    return lum * 0.9, lum * 0.95, lum + 0.02, a


def fx_glass(U, V, st):
    s, k = st["salt"], st["k"]
    cs = 0.2
    gx = np.floor(U / cs)
    gy = np.floor(V / cs)
    d1 = np.full_like(U, 9.0)
    d2 = np.full_like(U, 9.0)
    ix = np.zeros_like(U)
    iy = np.zeros_like(U)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx = gx + ox
            cy = gy + oy
            px = (cx + 0.15 + 0.7 * hash2(cx, cy, s + 80)) * cs
            py = (cy + 0.15 + 0.7 * hash2(cx, cy, s + 81)) * cs
            d = np.sqrt((U - px) ** 2 + (V - py) ** 2)
            near = d < d1
            d2 = np.where(near, d1, np.minimum(d2, d))
            d1 = np.where(near, d, d1)
            ix = np.where(near, cx, ix)
            iy = np.where(near, cy, iy)
    hs = hash2(ix, iy, s + 82)
    a = (hs < k).astype(np.float64)
    pop = _c01(1.0 - (k - hs) / 0.08) * a
    crack = _c01(1.0 - (d2 - d1) / 0.006)
    shade = 0.55 + 0.45 * hash2(ix, iy, s + 84)
    sheen = 0.2 * hash2(ix, iy, s + 85) * _c01(1.0 - d1 / 0.2)
    lift = crack * 0.9 + pop * 0.6 + sheen
    return (_mix(0.25, 0.65, V) * shade + lift, _mix(0.55, 0.35, V) * shade + lift,
            0.95 * shade + lift, a)


SPLAT_COLS = ((1.00, 0.36, 0.54), (0.36, 0.78, 1.00), (1.00, 0.82, 0.25),
              (0.55, 0.30, 0.95), (1.00, 0.55, 0.20), (0.30, 0.90, 0.60))


def fx_splatter(U, V, st):
    s, k = st["salt"], st["k"]
    pr = np.zeros_like(U)
    pg = np.zeros_like(U)
    pb = np.zeros_like(U)
    A = np.zeros_like(U)
    full = st["reach"] * 1.15 + 0.14
    for cx, cy, hd, n in st["pts"]:
        rad = full * min(1.0, max(0.0, (k - hd * 0.5) / 0.5))
        if rad <= 0.0:
            continue
        d = (np.sqrt((U - cx) ** 2 + (V - cy) ** 2)
             * (0.85 + 0.3 * vnoise(U * 5.0 + n * 3.1, V * 5.0, s + 91)))
        ai = _c01((rad - 0.005 - d) / 0.005 + 0.5)
        col = SPLAT_COLS[n % 6]
        gloss = (0.85 + 0.15 * _c01(1.0 - d / rad)) * ai
        keep = 1.0 - ai
        pr = col[0] * gloss + pr * keep
        pg = col[1] * gloss + pg * keep
        pb = col[2] * gloss + pb * keep
        A = ai + A * keep
    safe = np.maximum(A, 1e-6)
    return pr / safe, pg / safe, pb / safe, A


def fx_warp(U, V, st):
    s, sec, k, asp = st["salt"], st["sec"], st["k"], st["aspect"]
    du = U - asp / 2.0
    dv = V - 0.5
    r = np.sqrt(du * du + dv * dv)
    tn = np.arctan2(dv, du) / (2.0 * math.pi) + 0.5
    R = math.sqrt(asp * asp + 1.0) / 2.0
    streak = np.zeros_like(U)
    for layer, (nsl, off) in enumerate(((180, 90), (97, 95))):
        sl = np.floor(tn * nsl)
        h1 = hash2(sl, layer, s + off)
        sp = 0.4 + 1.2 * hash2(sl, layer, s + off + 1)
        pos = _frac(h1 + sec * sp * 0.7)
        ps = pos * pos * R * 1.1
        ln = (0.02 + 0.3 * pos) * (0.3 + 0.7 * k)
        inside = _c01((r - ps) / 0.01) * _c01((ps + ln - r) / 0.01)
        line = _c01(1.0 - np.abs(_frac(tn * nsl) - 0.5) * 3.0)
        streak = streak + inside * line * (0.4 + 0.6 * pos)
    glow = np.exp(-(r / (0.05 + 0.5 * k)) ** 2) * k
    a = _c01(k * 1.5 - 0.5 + streak * k * 1.5 + glow)
    return (0.02 + glow * 0.5 + streak * 0.85, 0.03 + glow * 0.7 + streak * 0.9,
            0.10 + glow + streak, a)


def fx_blinds(U, V, st):
    k, asp, d = st["k"], st["aspect"], st["direction"]
    n = 12
    if d == "up":
        x01 = 1.0 - V
    elif d == "right":
        x01 = U / asp
    elif d == "left":
        x01 = 1.0 - U / asp
    else:
        x01 = V
    sl = np.floor(x01 * n)
    ly = x01 * n - sl
    ks = _c01(k * 1.3 - 0.3 * (sl / (n - 1)))
    ew = 0.05
    thr = ks * (1.0 + 2.0 * ew) - ew
    x = ly if st["entering"] else 1.0 - ly
    a = _c01((thr - x) / ew + 0.5)
    tc = sl / (n - 1) if st["gradient"] else sl * 0.0
    shade = (0.7 + 0.3 * (1.0 - ly)) * np.where(ly > 0.94, 0.6, 1.0)
    c0, c1 = st["cols"][0], st["cols"][1]
    return (_mix(c0[0], c1[0], tc) * shade, _mix(c0[1], c1[1], tc) * shade,
            _mix(c0[2], c1[2], tc) * shade, a)


def fx_diamond(U, V, st):
    k, asp = st["k"], st["aspect"]
    cs = 0.125
    cx = np.floor(U / cs)
    cy = np.floor(V / cs)
    lx = U / cs - cx - 0.5
    ly = V / cs - cy - 0.5
    dm = np.abs(lx) + np.abs(ly)
    d = st["direction"]
    if d in ("down", "up"):
        dl = _c01((cy + 0.5) * cs)
    else:
        dl = _c01((cx + 0.5) * cs / asp)
    if d in ("left", "up"):
        dl = 1.0 - dl
    if not st["entering"]:
        dl = 1.0 - dl        # keep the wave moving the same way on the way out
    kc = _c01((k - dl * 0.5) / 0.5)
    ew = 0.04
    thr = kc * (1.0 + 2.0 * ew) - ew
    a = _c01((thr - dm) / ew + 0.5)
    odd = (cx + cy).astype(np.int64) % 2 == 1
    shine = 0.85 + 0.15 * (1.0 - dm)
    c0, c1 = st["cols"][0], st["cols"][1]
    return (np.where(odd, c1[0], c0[0]) * shine, np.where(odd, c1[1], c0[1]) * shine,
            np.where(odd, c1[2], c0[2]) * shine, a)


def fx_portal(U, V, st):
    s, sec, k, asp = st["salt"], st["sec"], st["k"], st["aspect"]
    du = U - asp / 2.0
    dv = V - 0.5
    r = np.sqrt(du * du + dv * dv)
    th = np.arctan2(dv, du)
    R = math.sqrt(asp * asp + 1.0) / 2.0
    wob = 0.08 * np.sin(th * 3.0 + r * 10.0 - sec * 5.0)
    if st["entering"]:
        inside = k * (R + 0.2) - 0.1 + wob - r
    else:
        inside = r - ((1.0 - k) * (R + 0.2) - 0.1 + wob)
    a = _c01(inside / 0.004 + 0.5)
    w = 0.5 + 0.5 * np.sin(th * 4.0 + r * 14.0 - sec * 7.0
                           + 2.0 * fbm(du * 3.0, dv * 3.0, s + 100))
    rim = _c01(1.0 - np.abs(inside) / 0.05)
    core = np.exp(-(r / 0.08) ** 2) * 0.8
    return (_mix(0.12, 0.85, w) + rim * 0.16 + core,
            _mix(0.02, 0.25, w) + rim * 0.36 + core,
            _mix(0.28, 0.95, w) + rim * 0.40 + core, a)



# --------------------------------------------------------------------------
# second batch. Helpers first: _wipe and _dissolve are the two ways an
# effect promises full cover. For x in [0, 1], _wipe is fully on at kc = 1
# and fully off at kc = 0. For m in [0, 1), _dissolve is the same with k.
# --------------------------------------------------------------------------
def _wipe(kc, x, ew):
    thr = kc * (1.0 + 2.0 * ew) - ew
    return _c01((thr - x) / ew + 0.5)


def _dissolve(k, m, e):
    return _c01((k * (1.0 + e) - m) / e)


def _halfdiag(asp):
    return math.sqrt(asp * asp + 1.0) / 2.0


def _polar(U, V, asp):
    du = U - asp / 2.0
    dv = V - 0.5
    return du, dv, np.sqrt(du * du + dv * dv), np.arctan2(dv, du) / (2.0 * math.pi) + 0.5


def fx_clouds(U, V, st):
    s, sec, k, asp = st["salt"], st["sec"], st["k"], st["aspect"]
    n = fbm(U * 1.8 - sec * 0.25, V * 2.5, s + 200)
    n2 = fbm(U * 4.0 - sec * 0.4, V * 4.0, s + 201)
    side = U / asp if st["entering"] else 1.0 - U / asp
    a = _dissolve(k, 0.55 * n + 0.45 * side, 0.2)
    lift = _c01(n * 1.6 - 0.25)
    shade = 0.78 + 0.22 * n2
    return (_mix(0.55, 1.0, lift) * shade, _mix(0.70, 1.0, lift) * shade,
            _mix(0.95, 1.0, lift) * shade, a)


def fx_rainglass(U, V, st):
    s, sec, k = st["salt"], st["sec"], st["k"]
    n = fbm(U * 3.0, V * 3.0, s + 210)
    side = V if st["entering"] else 1.0 - V
    a = _dissolve(k, 0.6 * n + 0.4 * side, 0.15)
    base = 0.32 + 0.18 * fbm(U * 6.0, V * 6.0, s + 211)
    cx = np.floor(U * 20.0)
    cy = np.floor(V * 20.0)
    px = (cx + 0.2 + 0.6 * hash2(cx, cy, s + 212)) / 20.0
    py = (cy + 0.2 + 0.6 * hash2(cx, cy, s + 213)) / 20.0
    rad = 0.006 + 0.012 * hash2(cx, cy, s + 214)
    d = np.sqrt((U - px) ** 2 + (V - py) ** 2)
    drop = np.where(hash2(cx, cy, s + 215) > 0.35, _c01(1.0 - d / rad), 0.0)
    col = np.floor(U * 70.0)
    head = _frac(hash2(col, 1, s + 216)
                 + sec * (0.3 + 0.5 * hash2(col, 2, s + 216))) * 1.3
    tail = head - V
    streak = np.where((hash2(col, 0, s + 216) > 0.8) & (tail > 0.0),
                      _c01(1.0 - tail / 0.25)
                      * _c01(1.0 - np.abs(_frac(U * 70.0) - 0.5) * 4.0), 0.0)
    lum = base + drop * 0.35 + streak * 0.3
    return lum * 0.85, lum * 0.95, lum * 1.1, a


def fx_snow(U, V, st):
    s, sec, k = st["salt"], st["sec"], st["k"]
    flakes = np.zeros_like(U)
    for L in range(3):
        cs = 1.0 / (10.0 + 8.0 * L)
        vv = V - sec * (0.12 + 0.08 * L)
        uu = U + 0.03 * np.sin(sec * 1.5 + V * 6.0 + L)
        cx = np.floor(uu / cs)
        cy = np.floor(vv / cs)
        px = (cx + 0.2 + 0.6 * hash2(cx, cy, s + 220 + L)) * cs
        py = (cy + 0.2 + 0.6 * hash2(cx, cy, s + 223 + L)) * cs
        rad = cs * (0.06 + 0.08 * hash2(cx, cy, s + 226 + L))
        d = np.sqrt((uu - px) ** 2 + (vv - py) ** 2)
        flakes = np.maximum(flakes, _c01(1.0 - d / rad) * 1.5)
    flakes = _c01(flakes)
    top = (1.08 - k * 1.25
           + 0.1 * (vnoise(U * 3.0, np.full_like(U, 0.5), s + 229) - 0.5))
    pile = _c01((V - top) / 0.006 + 0.5)
    fog = _c01(k * 1.6 - 0.6)
    a = np.maximum(np.maximum(fog, pile), flakes * min(1.0, k * 4.0))
    return 0.88 + 0.12 * flakes, 0.92 + 0.08 * flakes, np.ones_like(U), a


def fx_bubbles(U, V, st):
    s, sec, k = st["salt"], st["sec"], st["k"]
    n = fbm(U * 2.5, V * 2.5 + sec * 0.4, s + 230)
    side = (1.0 - V) if st["entering"] else V
    fill = _dissolve(k, 0.5 * n + 0.5 * side, 0.15)
    ring = np.zeros_like(U)
    inner = np.zeros_like(U)
    cs = 1.0 / 6.0
    vv = V + sec * 0.35
    gx = np.floor(U / cs)
    gy = np.floor(vv / cs)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx = gx + ox
            cy = gy + oy
            px = (cx + 0.25 + 0.5 * hash2(cx, cy, s + 231)) * cs
            py = (cy + 0.25 + 0.5 * hash2(cx, cy, s + 232)) * cs
            rad = cs * (0.15 + 0.45 * hash2(cx, cy, s + 233))
            d = np.sqrt((U - px) ** 2 + (vv - py) ** 2)
            ring = np.maximum(ring, _c01(1.0 - np.abs(d - rad) / 0.006))
            inner = np.maximum(inner, _c01(1.0 - d / rad) * 0.3)
    mixb = _c01(ring * 0.9 + inner)
    bub = _c01(ring + inner) * min(1.0, k * 3.0)
    a = np.maximum(fill, bub)
    return (_mix(0.06, 0.75, mixb), _mix(0.35, 0.95, mixb),
            _mix(0.65, 1.0, mixb), a)


def fx_sand(U, V, st):
    s, sec, k, asp = st["salt"], st["sec"], st["k"], st["aspect"]
    grain = hash2(np.floor(U * 400.0), np.floor(V * 400.0), s + 240)
    dune = fbm(U * 3.0, V * 3.0, s + 241)
    if st["entering"]:
        top = (1.0 - (k * 1.3 - 0.1) + 0.05 * np.sin(U * 3.0 + st["seedf"] * 6.283)
               + 0.04 * (vnoise(U * 2.0, np.full_like(U, 0.5), s + 242) - 0.5))
        a = _c01((V - top) / 0.004 + 0.5)
    else:
        # blows away to the right
        m = (0.55 * (1.0 - U / asp)
             + 0.45 * (0.7 * fbm(U * 4.0 + sec, V * 4.0, s + 243) + 0.3 * grain))
        a = _dissolve(k, m, 0.08)
    shade = (0.8 + 0.2 * dune) * (0.85 + 0.15 * grain)
    return 0.86 * shade, 0.70 * shade, 0.45 * shade, a


def fx_matrix(U, V, st):
    s, sec, k, asp = st["salt"], st["sec"], st["k"], st["aspect"]
    col = np.floor(U / asp * 60.0)
    row = np.floor(V * 34.0)
    kc = _c01(k * 1.3 - 0.3 * hash2(col, 0, s + 250))
    a = _wipe(kc, V if st["entering"] else 1.0 - V, 0.02)
    spd = 0.4 + 0.8 * hash2(col, 1, s + 250)
    head = _frac(hash2(col, 2, s + 250) + sec * spd) * 1.5 - 0.25
    tr = head - V
    bright = np.where(tr >= 0.0, np.exp(-np.abs(tr) * 5.0), 0.0)
    lx = np.floor(_frac(U / asp * 60.0) * 3.0)
    ly = np.floor(_frac(V * 34.0) * 5.0)
    glyph = np.floor(sec * 6.0 + hash2(col, row, s + 251) * 10.0)
    bit = hash2(col * 7.0 + lx + glyph * 31.0, row * 5.0 + ly, s + 252) > 0.45
    on = np.where(bit, bright, 0.0)
    hd = np.where(np.abs(tr) < 1.0 / 34.0, on, 0.0)
    return (0.02 + on * 0.2 + hd * 0.7, 0.03 + on * 0.9 + hd * 0.1,
            0.02 + on * 0.35 + hd * 0.6, a)


def fx_hologram(U, V, st):
    s, sec, k = st["salt"], st["sec"], st["k"]
    x = V if st["entering"] else 1.0 - V
    ew = 0.01
    thr = k * (1.0 + 2.0 * ew) - ew
    a = _c01((thr - x) / ew + 0.5)
    edge = _c01(1.0 - (thr - x) / 0.04) * a
    grid = np.where((_frac(U * 16.0) < 0.05) | (_frac(V * 16.0) < 0.05), 0.3, 0.0)
    scan = np.where(np.floor(V * 270.0).astype(np.int64) % 2 == 1, 0.65, 1.0)
    flick = 0.85 + 0.15 * float(hash2(int(math.floor(sec * 15.0)), 0, s + 260))
    wave = 0.5 + 0.5 * np.sin(V * 40.0 - sec * 8.0)
    lum = (0.5 + grid + 0.2 * wave) * scan * flick
    return lum * 0.3 + edge, lum * 0.85 + edge, lum + edge, a


def fx_signal(U, V, st):
    s, sec, k = st["salt"], st["sec"], st["k"]
    step = int(math.floor(sec * 10.0))
    bx = np.floor(U * 9.0)
    by = np.floor(V * 9.0)
    m = 0.7 * hash2(bx, by, s + 270) + 0.3 * hash2(bx, by, s + 271 + step)
    a = (m < k).astype(np.float64)
    fine = 0.8 + 0.2 * hash2(np.floor(U * 160.0), np.floor(V * 160.0), s + 272 + step)
    tear = hash2(np.floor(V * 90.0), step, s + 273) > 0.93
    out = [np.where(tear, 0.95, (0.15 + 0.6 * hash2(bx, by, s + 274 + c * 13 + step)) * fine)
           for c in range(3)]
    return out[0], out[1], out[2], a


THREE_A = (1.00, 0.36, 0.54)
THREE_B = (0.45, 0.25, 0.85)
THREE_C = (0.36, 0.78, 1.00)


def _three(g):
    """g in [0, 2]: pink to purple to blue."""
    w1 = _c01(g)
    w2 = _c01(g - 1.0)
    return [THREE_A[c] + (THREE_B[c] - THREE_A[c]) * w1
            + (THREE_C[c] - THREE_B[c]) * w2 for c in range(3)]


def fx_datamosh(U, V, st):
    s, sec, k = st["salt"], st["sec"], st["k"]
    bx = np.floor(U * 12.0)
    by = np.floor(V * 7.0)
    a = (hash2(bx, by, s + 280) < k).astype(np.float64)
    dx = (hash2(bx, by, s + 281) - 0.5) * 0.6
    dy = (hash2(bx, by, s + 282) - 0.5) * 0.6 + 0.3
    q = np.floor(V * 60.0) / 60.0
    f = fbm((U - dx * sec) * 2.0, (q - dy * sec) * 2.0, s + 283)
    out = _three(_c01(f * 2.2 - 0.6) * 2.0)
    return out[0], out[1], out[2], a


def fx_filmburn(U, V, st):
    s, sec, k, asp = st["salt"], st["sec"], st["k"], st["aspect"]
    n = fbm(U * 2.5, V * 2.5 + sec * 0.3, s + 290)
    m = 0.6 * n + 0.4 * (U / asp)
    e = 0.3
    dd = k * (1.0 + e) - m
    a = _c01(dd / e)
    heat = _c01(dd / 0.6)
    char = _c01(1.0 - dd / 0.06) * a
    dim = 1.0 - 0.5 * char
    return (1.0 - 0.25 * char, _mix(0.35, 0.95, heat) * dim,
            _mix(0.05, 0.8, heat * heat) * dim, a)


def fx_grain(U, V, st):
    s, sec, k, asp = st["salt"], st["sec"], st["k"], st["aspect"]
    frame = int(math.floor(sec * 24.0))
    du = U - asp / 2.0
    dv = V - 0.5
    rr = np.sqrt(du * du + dv * dv) / _halfdiag(asp)
    gr = hash2(np.floor(U * 270.0), np.floor(V * 270.0), s + 300 + frame)
    side = (1.0 - rr) if st["entering"] else rr
    a = _dissolve(k, 0.7 * side + 0.3 * gr, 0.1)
    flick = 0.9 + 0.1 * float(hash2(frame, 0, s + 301))
    lum = (0.8 + 0.2 * gr) * flick * (1.0 - 0.45 * rr * rr)
    mark = ((hash2(np.floor(U * 300.0), frame // 3, s + 302) > 0.996)
            | (hash2(np.floor(U * 200.0), np.floor(V * 120.0), s + 303 + frame) > 0.997))
    lum = np.where(mark, lum * 0.25, lum)
    return 0.78 * lum, 0.64 * lum, 0.46 * lum, a


CH_COLS = np.array([[1.00, 0.36, 0.54], [0.36, 0.78, 1.00],
                    [0.55, 0.30, 0.95], [1.00, 0.82, 0.25]])


def fx_channel(U, V, st):
    s, sec, k, asp = st["salt"], st["sec"], st["k"], st["aspect"]
    step = int(math.floor(sec * 8.0))
    band = np.floor(V * 24.0)
    kb = _c01(k * 1.3 - 0.3 * hash2(band, 0, s + 310))
    xl = U / asp
    x = np.where(band.astype(np.int64) % 2 == 0, xl, 1.0 - xl)
    if not st["entering"]:
        x = 1.0 - x
    a = _wipe(kb, x, 0.01)
    ci = np.floor(hash2(band, step, s + 311) * 4.0).astype(np.int64)
    tex = 0.75 + 0.25 * hash2(np.floor(U * 200.0), band, s + 312 + step)
    scan = np.where(np.floor(V * 270.0).astype(np.int64) % 2 == 1, 0.85, 1.0)
    return (CH_COLS[ci, 0] * tex * scan, CH_COLS[ci, 1] * tex * scan,
            CH_COLS[ci, 2] * tex * scan, a)


BIT_COLS = np.array([[0.13, 0.13, 0.20], [0.35, 0.20, 0.60],
                     [1.00, 0.36, 0.54], [1.00, 0.82, 0.25]])


def fx_bitwipe(U, V, st):
    s, k, asp = st["salt"], st["k"], st["aspect"]
    bx = np.floor(U * 16.0)
    by = np.floor(V * 16.0)
    diag = _c01((bx / (asp * 16.0) + by / 16.0) * 0.5)
    h = hash2(bx, by, s + 320)
    m = 0.85 * (diag if st["entering"] else 1.0 - diag) + 0.15 * h
    a = (m < k).astype(np.float64)
    ci = np.floor(hash2(bx, by, s + 321) * 4.0).astype(np.int64)
    lx = _frac(U * 16.0)
    ly = _frac(V * 16.0)
    sh = np.where((lx < 0.15) | (ly < 0.15), 1.25,
                  np.where((lx > 0.85) | (ly > 0.85), 0.7, 1.0))
    return BIT_COLS[ci, 0] * sh, BIT_COLS[ci, 1] * sh, BIT_COLS[ci, 2] * sh, a


def fx_iris(U, V, st):
    k, asp = st["k"], st["aspect"]
    d = np.sqrt((U - asp / 2.0) ** 2 + (V - 0.5) ** 2)
    R = _halfdiag(asp) + 0.02
    ew = 0.003
    hr = (R + ew) * (1.0 - k) - ew
    a = _c01((d - hr) / ew + 0.5)
    ring = _c01(1.0 - np.abs(d - hr) / 0.012) * a * min(1.0, max(0.0, hr / 0.02))
    c0, c1 = st["cols"][0], st["cols"][1]
    return (_mix(c0[0], c1[0], ring), _mix(c0[1], c1[1], ring),
            _mix(c0[2], c1[2], ring), a)


def fx_page(U, V, st):
    k, asp = st["k"], st["aspect"]
    p = (asp - U) / asp * 0.85 + V * 0.15
    x = p if st["entering"] else 1.0 - p
    ew = 0.006
    thr = k * (1.0 + 2.0 * ew) - ew
    a = _c01((thr - x) / ew + 0.5)
    inside = thr - x
    fold = min(1.0, (1.0 - k) * 10.0)      # flat page once it has landed
    curl = np.where((inside > 0.0) & (inside < 0.06),
                    1.0 - fold * 0.25 * (1.0 - np.sin(inside / 0.06 * math.pi)), 1.0)
    shadow = np.where(x > thr, 0.35 * _c01(1.0 - (x - thr) / 0.05), 0.0) * min(1.0, k * 10.0)
    A = a + shadow * (1.0 - a)
    safe = np.maximum(A, 1e-6)
    lines = np.where(_frac(V * 24.0) < 0.04, 0.93, 1.0)
    c = st["cols"][0]
    f = curl * lines * a / safe
    return c[0] * f, c[1] * f, c[2] * f, A


def fx_curtain(U, V, st):
    sec, k, asp = st["sec"], st["k"], st["aspect"]
    du = np.abs(U - asp / 2.0)
    x = _c01(1.0 - du / (asp / 2.0) + 0.03 * np.sin(V * 3.0 + sec * 2.0) * k * (1.0 - k))
    ew = 0.006
    thr = k * (1.0 + 2.0 * ew) - ew
    a = _c01((thr - x) / ew + 0.5)
    folds = (0.62 + 0.38 * np.sin(du * 38.0) ** 2) * (0.85 + 0.15 * (1.0 - V))
    trim = _c01(1.0 - (thr - x) / 0.015) * a
    c0, c1 = st["cols"][0], st["cols"][1]
    return (_mix(c0[0] * folds, c1[0], trim), _mix(c0[1] * folds, c1[1], trim),
            _mix(c0[2] * folds, c1[2], trim), a)


def fx_tiles(U, V, st):
    k, asp = st["k"], st["aspect"]
    tx = np.floor(U * 6.0)
    ty = np.floor(V * 6.0)
    lx = U * 6.0 - tx - 0.5
    delay = _c01((tx / (asp * 6.0) + ty / 6.0) * 0.5)
    if not st["entering"]:
        delay = 1.0 - delay
    kc = _c01((k - delay * 0.5) / 0.5)
    x = np.abs(lx) * 2.0
    a = _wipe(kc, x, 0.04)
    odd = (tx + ty).astype(np.int64) % 2 == 1
    sh = (0.6 + 0.4 * kc) * np.where(x > 0.92, 0.75, 1.0)
    c0, c1 = st["cols"][0], st["cols"][1]
    return (np.where(odd, c1[0], c0[0]) * sh, np.where(odd, c1[1], c0[1]) * sh,
            np.where(odd, c1[2], c0[2]) * sh, a)


def fx_radial(U, V, st):
    k, asp = st["k"], st["aspect"]
    ang = _frac(np.arctan2(U - asp / 2.0, 0.5 - V) / (2.0 * math.pi))
    x = ang if st["entering"] else 1.0 - ang
    ew = 0.003
    a = _wipe(k, x, ew)
    thr = k * (1.0 + 2.0 * ew) - ew
    edge = _c01(1.0 - np.abs(thr - x) / 0.01) * a * 0.3 * min(1.0, (1.0 - k) * 10.0)
    g = 0.5 - 0.5 * np.cos(ang * 2.0 * math.pi)     # round trip, so no seam
    c0, c1 = st["cols"][0], st["cols"][1]
    return (_mix(c0[0], c1[0], g) + edge, _mix(c0[1], c1[1], g) + edge,
            _mix(c0[2], c1[2], g) + edge, a)


def fx_zoomblur(U, V, st):
    s, sec, k, asp = st["salt"], st["sec"], st["k"], st["aspect"]
    du, dv, r, tn = _polar(U, V, asp)
    sl = np.floor(tn * 140.0)
    xn = (r / (_halfdiag(asp) + 0.02) + 0.07 * hash2(sl, 0, s + 330)) / 1.07
    a = _wipe(k, xn if st["entering"] else 1.0 - xn, 0.03)
    c = (0.5 + 0.5 * np.sin(r * 30.0 - sec * 14.0)) * (0.75 + 0.25 * hash2(sl, 1, s + 330))
    return _mix(0.36, 1.0, c), _mix(0.25, 0.36, c), _mix(0.85, 0.54, c), a


def fx_liquid(U, V, st):
    s, sec, k = st["salt"], st["sec"], st["k"]
    col = np.floor(U * 8.0)
    lu = U * 8.0 - col
    drip = hash2(col, 0, s + 340) ** 2 * np.sqrt(np.sin(lu * math.pi))
    x = (V - 0.25 * drip + 0.25) / 1.25
    a = _wipe(k, x if st["entering"] else 1.0 - x, 0.006)
    sh = 0.8 + 0.2 * fbm(U * 3.0, V * 3.0 - sec * 0.5, s + 341)
    return sh, 0.36 * sh, 0.54 * sh, a


SMPTE = np.array([[0.75, 0.75, 0.75], [0.75, 0.75, 0.0], [0.0, 0.75, 0.75],
                  [0.0, 0.75, 0.0], [0.75, 0.0, 0.75], [0.75, 0.0, 0.0],
                  [0.0, 0.0, 0.75]])
SMPTE_LOW = np.array([[0.0, 0.0, 0.75], [0.07, 0.07, 0.07], [0.75, 0.0, 0.75],
                      [0.07, 0.07, 0.07], [0.0, 0.75, 0.75], [0.07, 0.07, 0.07],
                      [0.75, 0.75, 0.75]])


def fx_bars(U, V, st):
    k, asp = st["k"], st["aspect"]
    idx = np.minimum(np.floor(U / asp * 7.0), 6.0)
    kc = _c01(k * 1.4 - 0.4 * idx / 6.0)
    a = _wipe(kc, V if st["entering"] else 1.0 - V, 0.01)
    ix = idx.astype(np.int64)
    low = V > 0.75
    return (np.where(low, SMPTE_LOW[ix, 0], SMPTE[ix, 0]),
            np.where(low, SMPTE_LOW[ix, 1], SMPTE[ix, 1]),
            np.where(low, SMPTE_LOW[ix, 2], SMPTE[ix, 2]), a)


def fx_blobs(U, V, st):
    sec, k = st["sec"], st["k"]
    kk = 0.15
    f = None
    for cx, cy, hd, n in st["pts"]:
        ox = cx + 0.05 * math.sin(sec * (1.0 + hd) + n)
        oy = cy + 0.05 * math.cos(sec * (1.3 + hd) + n * 2.0)
        d = np.sqrt((U - ox) ** 2 + (V - oy) ** 2) * (1.0 + 0.4 * hd)
        if f is None:
            f = d
        else:
            # smooth minimum: never more than the plain minimum, so the
            # cover bound still holds, and never below it by more than kk/4
            h = _c01(0.5 + 0.5 * (d - f) / kk)
            f = d + (f - d) * h - kk * h * (1.0 - h)
    fmax = (st["reach"] + 0.05) * 1.4
    T = k ** 1.8 * (fmax + 0.07) - 0.06
    a = _c01((T - f) / 0.006 + 0.5)
    inner = _c01((T - f) / 0.25)
    rim = _c01(1.0 - (T - f) / 0.02) * 0.3
    return 1.0 + rim, _mix(0.36, 0.6, inner) + rim, _mix(0.54, 0.2, inner) + rim, a


def fx_aurora(U, V, st):
    s, sec, k = st["salt"], st["sec"], st["k"]
    n = fbm(U * 2.0, V * 2.0, s + 360)
    side = V if st["entering"] else 1.0 - V
    a = _dissolve(k, 0.5 * n + 0.5 * side, 0.2)
    glow = np.zeros_like(U)
    for i in range(3):
        yb = (0.25 + 0.18 * i
              + 0.1 * np.sin(U * (1.5 + i * 0.7) + sec * (0.6 + 0.2 * i) + i * 2.0)
              + 0.08 * (fbm(U * 1.5 + i * 5.0, np.full_like(U, sec * 0.3), s + 361 + i) - 0.5))
        dy = V - yb
        band = np.exp(-(dy / np.where(dy > 0.0, 0.05, 0.18)) ** 2)
        rays = 0.7 + 0.3 * np.sin(U * 23.0 + sec * 1.5 + 6.0 * n)
        glow = glow + band * rays
    stars = np.where(hash2(np.floor(U * 300.0), np.floor(V * 300.0), s + 365) > 0.996, 0.8, 0.0)
    tv = _c01(V * 1.4)
    return (_mix(0.01, 0.04, V) + glow * _mix(0.55, 0.15, tv) + stars,
            _mix(0.02, 0.08, V) + glow * _mix(0.25, 0.95, tv) + stars,
            _mix(0.08, 0.20, V) + glow * _mix(0.95, 0.55, tv) + stars, a)


def fx_speed(U, V, st):
    s, sec, k, asp = st["salt"], st["sec"], st["k"], st["aspect"]
    du, dv, r, tn = _polar(U, V, asp)
    R = _halfdiag(asp) + 0.02
    fill = _wipe(k, 1.0 - r / R, 0.01)
    step = int(math.floor(sec * 12.0))
    sl = np.floor(tn * 160.0)
    ri = R * (1.0 - k * (0.4 + 0.9 * hash2(sl, step, s + 370)))
    line = np.where((r > ri) & (hash2(sl, step, s + 371) > 0.35),
                    _c01(1.0 - np.abs(_frac(tn * 160.0) - 0.5) * 4.0), 0.0)
    a = np.maximum(fill, line * min(1.0, k * 4.0))
    return _mix(0.08, 1.0, line), _mix(0.08, 1.0, line), _mix(0.12, 1.0, line), a


def fx_energy(U, V, st):
    s, sec, k, asp = st["salt"], st["sec"], st["k"], st["aspect"]
    du, dv, r, tn = _polar(U, V, asp)
    step = int(math.floor(sec * 20.0))
    sl = np.floor(tn * 90.0)
    xn = (r / (_halfdiag(asp) + 0.02) + 0.08 * hash2(sl, step, s + 380)) / 1.08
    x = xn if st["entering"] else 1.0 - xn
    ew = 0.02
    thr = k * (1.0 + 2.0 * ew) - ew
    a = _c01((thr - x) / ew + 0.5)
    depth = _c01((thr - x) / 0.35)
    rings = 0.85 + 0.15 * np.sin(r * 40.0 - sec * 20.0)
    return (rings + 0.0 * depth, _mix(0.45, 0.98, depth) * rings,
            _mix(0.1, 0.85, depth * depth) * rings, a)


def fx_loading(U, V, st):
    sec, k, asp = st["sec"], st["k"], st["aspect"]
    xl = U / asp
    seg = np.floor(xl * 20.0)
    xc = (seg + 0.5) / 20.0
    lim = k * 1.05
    a = (xc < lim).astype(np.float64)
    stripe = _frac((U + V) * 8.0 - sec * 2.0) < 0.5
    lf = _frac(xl * 20.0)
    sh = ((0.8 + 0.2 * (1.0 - V)) * np.where((lf < 0.04) | (lf > 0.96), 0.55, 1.0)
          * np.where(xc >= lim - 0.05, 1.3, 1.0))
    c0, c1 = st["cols"][0], st["cols"][1]
    return (np.where(stripe, c0[0], c1[0]) * sh, np.where(stripe, c0[1], c1[1]) * sh,
            np.where(stripe, c0[2], c1[2]) * sh, a)


def fx_health(U, V, st):
    k, asp = st["k"], st["aspect"]
    xl = U / asp
    ew = 0.004
    a = _wipe(k, xl, ew)
    am = _wipe(_c01(k * 1.15 - 0.15), xl, ew)
    sh = (np.where(_frac(xl * 10.0) < 0.008, 0.6, 1.0)
          * np.where(V < 0.18, 1.2, np.where(V > 0.85, 0.7, 1.0)))
    c0, c1 = st["cols"][0], st["cols"][1]
    return (_mix(c1[0], c0[0], am) * sh, _mix(c1[1], c0[1], am) * sh,
            _mix(c1[2], c0[2], am) * sh, a)


def fx_lag(U, V, st):
    s, sec, k, asp = st["salt"], st["sec"], st["k"], st["aspect"]
    step = int(math.floor(sec * 6.0))
    kq = math.floor(k * 8.0) / 8.0
    bx = np.floor(U / asp * 16.0)
    by = np.floor(V * 9.0)
    a = (hash2(bx, by, s + 390) < kq).astype(np.float64)
    ox = (hash2(bx, by, s + 391 + step) - 0.5) * 0.1
    f = _frac((U + ox) * 3.0 + V * 2.0)
    fr = _frac((U + ox + 0.01) * 3.0 + V * 2.0)
    red = hash2(bx, by, s + 392 + step) > 0.85
    r = np.where(red, 0.9, 0.12 + 0.15 * fr)
    g = np.where(red, 0.2, 0.12 + 0.15 * f)
    b = np.where(red, 0.25, 0.2 + 0.2 * f)
    d = np.sqrt((U - asp / 2.0) ** 2 + (V - 0.5) ** 2)
    seg = np.floor(_frac(np.arctan2(V - 0.5, U - asp / 2.0) / (2.0 * math.pi) + step / 8.0) * 8.0)
    ring = np.abs(d - 0.07) < 0.012
    lum = 0.25 + 0.75 * seg / 7.0
    return np.where(ring, lum, r), np.where(ring, lum, g), np.where(ring, lum, b), a


FX = {"static": fx_static, "glitch": fx_glitch, "smoke": fx_smoke,
      "water": fx_water, "circle": fx_circle, "ink": fx_ink,
      "lightning": fx_lightning, "pixelate": fx_pixelate, "vhs": fx_vhs,
      "crt": fx_crt, "glass": fx_glass, "splatter": fx_splatter,
      "warp": fx_warp, "blinds": fx_blinds, "diamond": fx_diamond,
      "portal": fx_portal}
FX.update({e: globals()["fx_" + e] for e in EFFECTS if e not in FX})

# A fixed salt per effect, mixed with the seed, so two effects with the same
# seed don't share a pattern.
SALT = {"static": 11, "glitch": 23, "smoke": 37, "water": 41, "circle": 67,
        "ink": 79, "lightning": 83, "pixelate": 89, "vhs": 97,
        "crt": 101, "glass": 103, "splatter": 107, "warp": 109, "blinds": 113,
        "diamond": 127, "portal": 131}
SALT.update(dict(zip(EFFECTS[EFFECTS.index("clouds"):], (
    137, 139, 149, 151, 157, 163, 167, 173, 179, 181, 191, 193, 197, 199,
    211, 223, 227, 229, 233, 239, 241, 251, 257, 263, 269, 271, 277, 281))))


# --------------------------------------------------------------------------
# colour: hue turn and saturation, using the same matrices as the CSS
# hue-rotate() and saturate() filters, then an optional tint
# --------------------------------------------------------------------------
def colour_matrix(hue_deg, sat):
    a = math.cos(math.radians(hue_deg))
    b = math.sin(math.radians(hue_deg))
    hm = np.array([
        [0.213 + a * 0.787 - b * 0.213, 0.715 - a * 0.715 - b * 0.715,
         0.072 - a * 0.072 + b * 0.928],
        [0.213 - a * 0.213 + b * 0.143, 0.715 + a * 0.285 + b * 0.140,
         0.072 - a * 0.072 - b * 0.283],
        [0.213 - a * 0.213 - b * 0.787, 0.715 - a * 0.715 + b * 0.715,
         0.072 + a * 0.928 + b * 0.072],
    ])
    s = float(sat)
    sm = np.array([
        [0.213 + 0.787 * s, 0.715 - 0.715 * s, 0.072 - 0.072 * s],
        [0.213 - 0.213 * s, 0.715 + 0.285 * s, 0.072 - 0.072 * s],
        [0.213 - 0.213 * s, 0.715 - 0.715 * s, 0.072 + 0.928 * s],
    ])
    return sm @ hm


def remap(U, V, asp, natural, want):
    """Turn an effect drawn for one direction so it travels another way.

    s is how far a pixel is from the edge the effect starts at, c is the
    position across. The effect is then handed coordinates as if it were
    moving its usual way."""
    if want == natural:
        return U, V
    if want == "up":
        s = 1.0 - V
    elif want == "down":
        s = V
    elif want == "right":
        s = U / asp
    else:
        s = 1.0 - U / asp
    c = U / asp if want in ("up", "down") else V
    if natural in ("up", "down"):
        return c * asp, (1.0 - s) if natural == "up" else s
    return (s if natural == "right" else 1.0 - s) * asp, c


def _hex01(c):
    c = str(c or "").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(x * 2 for x in c)
    try:
        n = int(c, 16)
    except ValueError:
        n = 0xFFFFFF
    return (((n >> 16) & 255) / 255.0, ((n >> 8) & 255) / 255.0,
            (n & 255) / 255.0)


def grid_size(effect, w, h):
    (kind, val), _ = GRID[effect]
    gh = int(val) if kind == "rows" else max(16, int(round(h * val)))
    gw = max(16, int(round(gh * w / float(h))))
    return gw, gh


def render_effect(effect, w, h, t, sec, k, entering, seed,
                  hue=0.0, sat=1.0, tint=(255, 255, 255), in_frac=0.5,
                  colours=None, gradient=True, direction=None, drops=12):
    """Draw one frame of an effect as a w x h RGBA PIL image.

    k is the eased cover amount (0 = clear, 1 = fully covered). entering is
    True up to the transition point and False after it."""
    gw, gh = grid_size(effect, w, h)
    ii = (np.arange(gw, dtype=np.float64) + 0.5) / gh
    jj = (np.arange(gh, dtype=np.float64) + 0.5) / gh
    U, V = np.meshgrid(ii, jj)
    seed = int(seed) % 4294967296
    st = {
        "t": float(t), "sec": float(sec),
        "k": min(1.0, max(0.0, float(k))),
        "entering": bool(entering),
        "salt": (seed * 7 + SALT[effect] * 1000003) & _M32,
        "seedf": (seed % 10007) / 10007.0,
        "aspect": w / float(h), "gh": gh, "in_frac": float(in_frac),
    }
    dirs = EFFECT_DIRS.get(effect)
    st["direction"] = (direction if dirs and direction in dirs
                       else NATURAL_DIR.get(effect))
    st["gradient"] = bool(gradient)
    st["drops"] = int(drops) if int(drops or 0) in DROP_GRIDS else 12
    defs = DEFAULT_COLOURS.get(effect, [])
    given = list(colours or [])
    st["cols"] = [_hex01(given[i] if i < len(given) and given[i] else d)
                  for i, d in enumerate(defs)]
    if effect == "ink":
        st["pts"], st["reach"] = drop_points(st, 43)
    elif effect == "splatter":
        st["pts"], st["reach"] = drop_points(st, 92)
    elif effect == "blobs":
        st["pts"], st["reach"] = drop_points(st, 350, 6)
    if effect in REMAP_EFFECTS:
        U, V = remap(U, V, st["aspect"], NATURAL_DIR[effect], st["direction"])
    r, g, b, a = FX[effect](U, V, st)
    rgb = np.stack([r, g, b], axis=-1)
    if effect in TINT_EFFECTS:
        rgb = rgb * (np.array(tint[:3], dtype=np.float64) / 255.0)
    if abs(hue) > 1e-6 or abs(sat - 1.0) > 1e-6:
        rgb = rgb @ colour_matrix(hue, sat).T
    rgba = np.concatenate([np.clip(rgb, 0.0, 1.0), _c01(a)[..., None]], axis=-1)
    arr = np.clip(rgba * 255.0 + 0.5, 0, 255).astype(np.uint8)
    im = Image.fromarray(arr, "RGBA")
    if (gw, gh) != (w, h):
        resample = GRID[effect][1]
        if resample == Image.NEAREST:
            im = im.resize((w, h), Image.NEAREST)
        else:
            # premultiply first or the clear edges pick up a dark fringe
            im = im.convert("RGBa").resize((w, h), resample).convert("RGBA")
    return im
