#!/usr/bin/env python3
"""
engine.py — generate WebM stinger transitions for OBS from emote images.

Outputs a VP9 WebM with alpha (yuva420p) sized for an OBS stinger transition:
  scene A visible -> emotes flood and cover the screen -> emotes clear -> scene B visible.

Alternative outputs: ProRes 4444 MOV (alpha) and a zipped PNG sequence.

The "transition point" (full-coverage frame, in ms) is printed at the end so you can
paste it into OBS's stinger transition settings.

Animation styles:
  rain       emotes pour from the top, pile up to full coverage, then fall away
  burst      emotes explode outward from center, fill screen, then implode/fade
  swipe      a dense wall of emotes sweeps across the screen and back
  spiral     emotes spiral inward to cover, then spiral out
  swarm      emotes scatter in from all edges, converge, then scatter out
  rows       alternating horizontal lines slide in from opposite sides
  columns    alternating vertical lines slide in from top and bottom
  downpour   a continuous fall with no pause, packed at the transition point
  zoom       emotes rush toward the camera from a point, scaling up to fill
  wipe       a staggered diagonal band sweeps across like a curtain pull
  shockwave  emotes ripple outward from center in concentric rings
  vortex     everything spins into the center and drains away, then back out

Usage:
  python3 engine.py --images a.png b.png c.png --style rain --out stinger.webm
"""
import argparse
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import zipfile
from multiprocessing import Pool, cpu_count

from PIL import Image, ImageChops, ImageFilter, ImageSequence

STYLES = ["rain", "burst", "swipe", "spiral", "swarm",
          "rows", "columns", "downpour", "zoom", "wipe", "shockwave", "vortex"]

DIRECTIONS = ["left", "right", "up", "down"]

# Styles that respond to the direction option, and the default that reproduces
# the original motion. Direction always means "which way the emotes travel".
DIRECTIONAL = {"rain": "down", "swipe": "right", "wipe": "right",
               "rows": "right", "columns": "down", "downpour": "down"}

EASINGS = ["smooth", "linear", "overshoot", "bounce"]

# Optional logo that lands on top of the emotes at the transition point.
LOGO_ANIMS = ["pop", "slam", "spin", "fade", "drop", "rise", "flip", "swing",
              "glitch", "zoom", "none"]
LOGO_ANCHORS = ["tl", "tc", "tr", "ml", "mc", "mr", "bl", "bc", "br"]
# how the logo's on-screen time is split: enter, sit still, leave
LOGO_ENTRY = 0.4
LOGO_EXIT = 0.4

FORMATS = ["webm", "mov", "png"]

EXT = {"webm": ".webm", "mov": ".mov", "png": ".zip"}

# Fraction of the timeline given over to per-sprite stagger (wipe / rain).
STAGGER = 0.4

# ffmpeg binary location. The app overrides this to point at the bundled copy;
# falls back to "ffmpeg" on PATH when run as a plain script.
FFMPEG = os.environ.get("STINGER_FFMPEG", "ffmpeg")


def sp_kwargs():
    """Keep ffmpeg from flashing a console window out of the windowed exe."""
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


# --------------------------------------------------------------------------
# rng
# --------------------------------------------------------------------------
class Rng:
    """Small LCG, bit-for-bit reproducible in JavaScript.

    The UI preview runs this same generator so a given seed produces the same
    layout in the preview and in the render. Every intermediate value stays
    under 2**53, so double-precision JS math matches Python exactly.
    """

    __slots__ = ("s",)

    def __init__(self, seed):
        self.s = int(seed) % 4294967296

    def next(self):
        self.s = (self.s * 1664525 + 1013904223) % 4294967296
        return self.s / 4294967296.0

    def uniform(self, a, b):
        return a + self.next() * (b - a)

    def index(self, n):
        return int(self.next() * n) % n

    def shuffle(self, seq):
        """Fisher-Yates, matching the preview's loop exactly."""
        for i in range(len(seq) - 1, 0, -1):
            j = int(self.next() * (i + 1))
            seq[i], seq[j] = seq[j], seq[i]


# --------------------------------------------------------------------------
# emote loading (+ effects, + animation)
# --------------------------------------------------------------------------
def parse_color(c, default=(0, 0, 0)):
    if not c:
        return default
    if isinstance(c, (tuple, list)):
        return tuple(int(x) for x in c[:3])
    c = str(c).strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return default
    try:
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    except ValueError:
        return default


def apply_outline(im, width, color):
    """Colored stroke derived from the alpha channel by dilation."""
    width = int(width)
    if width <= 0:
        return im
    pad = width + 2
    big = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    big.paste(im, (pad, pad))
    alpha = big.split()[3]
    # MaxFilter needs an odd kernel; step up in 2s for widths beyond one pass.
    grown = alpha
    remaining = width
    while remaining > 0:
        k = min(remaining, 4)
        grown = grown.filter(ImageFilter.MaxFilter(2 * k + 1))
        remaining -= k
    grown = grown.filter(ImageFilter.SMOOTH)
    stroke = Image.new("RGBA", big.size, tuple(color) + (255,))
    stroke.putalpha(grown)
    return Image.alpha_composite(stroke, big)


def apply_shadow(im, offset, blur, opacity, color=(0, 0, 0)):
    """Soft drop shadow: blurred alpha, offset, partially transparent."""
    ox, oy = offset
    pad = int(blur * 3 + max(abs(ox), abs(oy)) + 2)
    size = (im.width + pad * 2, im.height + pad * 2)
    base = Image.new("RGBA", size, (0, 0, 0, 0))
    base.paste(im, (pad, pad))
    alpha = base.split()[3].filter(ImageFilter.GaussianBlur(blur))
    alpha = alpha.point(lambda v: int(v * opacity))
    shadow = Image.new("RGBA", size, tuple(color) + (255,))
    shadow.putalpha(alpha)
    shadow = shadow.transform(
        size, Image.AFFINE, (1, 0, -ox, 0, 1, -oy), resample=Image.BILINEAR)
    return Image.alpha_composite(shadow, base)


def _read_frames(path):
    """Return ([RGBA frames], [durations ms]). Static images give one frame."""
    im = Image.open(path)
    n = getattr(im, "n_frames", 1)
    if n <= 1:
        return [im.convert("RGBA")], [0.0]
    frames, durs = [], []
    for fr in ImageSequence.Iterator(im):
        d = fr.info.get("duration", 0) or 0
        frames.append(fr.convert("RGBA").copy())
        durs.append(float(d) if d > 0 else 100.0)
    return frames, durs


def load_emotes(paths, target_px, outline=0, outline_color=(0, 0, 0),
                shadow=False, shadow_blur=None, shadow_offset=None,
                shadow_opacity=0.5):
    """Load, scale and (once, here) bake in outline / shadow effects.

    Returns a list of emote dicts: {frames, durations, total_ms}. Effects are
    applied at load time so there is no per-frame cost during rendering.
    """
    outline_color = parse_color(outline_color)
    if shadow_blur is None:
        shadow_blur = max(2.0, target_px * 0.05)
    if shadow_offset is None:
        off = max(2, int(target_px * 0.035))
        shadow_offset = (off, off)

    emotes = []
    for p in paths:
        frames, durs = _read_frames(p)
        # scale so the larger side == target_px, using the first frame's size
        scale = target_px / max(frames[0].size)
        out_frames = []
        for fr in frames:
            new = (max(1, int(fr.width * scale)), max(1, int(fr.height * scale)))
            fr = fr.resize(new, Image.LANCZOS)
            if outline:
                fr = apply_outline(fr, outline, outline_color)
            if shadow:
                fr = apply_shadow(fr, shadow_offset, shadow_blur, shadow_opacity)
            out_frames.append(fr)
        emotes.append({
            "frames": out_frames,
            "durations": durs,
            "total_ms": float(sum(durs)),
        })
    return emotes


def emote_frame(em, t_ms, phase):
    """Pick the animation frame for this sprite at this moment."""
    frames = em["frames"]
    if len(frames) == 1:
        return frames[0]
    total = em["total_ms"]
    if total <= 0:
        return frames[0]
    pos = (phase * total + t_ms) % total
    acc = 0.0
    for fr, d in zip(frames, em["durations"]):
        acc += d
        if pos < acc:
            return fr
    return frames[-1]


# --------------------------------------------------------------------------
# timing
# --------------------------------------------------------------------------
def clamp01(v):
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


def ease_in_out(t):
    return 0.5 - 0.5 * math.cos(math.pi * t)


def ease_linear(t):
    return t


def ease_overshoot(t):
    """Back-out: passes home by ~8%, then settles."""
    c1 = 1.5
    c3 = c1 + 1.0
    u = t - 1.0
    return 1.0 + c3 * u * u * u + c1 * u * u


def ease_bounce(t):
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


EASE_FN = {
    "smooth": ease_in_out,
    "linear": ease_linear,
    "overshoot": ease_overshoot,
    "bounce": ease_bounce,
}


def timing_windows(hold, in_frac):
    """Resolve the rise/fall windows, clamped so both always exist.

    Returns (in_frac, up_end, down_start). Coverage rises across [0, up_end],
    holds across [up_end, down_start], and falls across [down_start, 1].
    """
    in_frac = min(0.95, max(0.05, float(in_frac)))
    half = max(0.0, float(hold)) / 2.0
    # a large hold with an off-center transition point would otherwise leave no
    # room on the short side, so clamp against whichever side is tighter
    half = min(half, in_frac * 0.9, (1.0 - in_frac) * 0.9)
    return in_frac, in_frac - half, in_frac + half


def coverage_curve(t, hold, in_frac=0.5):
    """t in [0,1]. Returns 0..1..0 coverage with a flat hold at peak.

    hold is the fraction of the timeline held at full coverage; in_frac is
    where that peak sits, so the rise and fall can be different lengths."""
    _, up_end, down_start = timing_windows(hold, in_frac)
    if t < up_end:
        return ease_in_out(t / up_end)
    if t > down_start:
        return ease_in_out((1.0 - t) / (1.0 - down_start))
    return 1.0


def stagger(cov, delay, amount=STAGGER):
    """Delay one sprite's share of the coverage curve.

    delay is 0..1 (0 = leads, 1 = trails). Every sprite still reaches 1 when
    cov reaches 1, so full coverage at the transition point is preserved."""
    if amount <= 0:
        return cov
    return clamp01((cov - delay * amount) / (1.0 - amount))


def resolve_direction(style, direction):
    """Fill in the per-style default and coerce axis-locked styles."""
    d = direction if direction in DIRECTIONS else None
    d = d or DIRECTIONAL.get(style, "down")
    if style == "rows" and d in ("up", "down"):
        d = "right" if d == "down" else "left"
    elif style == "columns" and d in ("left", "right"):
        d = "down" if d == "right" else "up"
    elif style == "downpour" and d in ("left", "right"):
        d = "down"
    return d


# --------------------------------------------------------------------------
# layout
# --------------------------------------------------------------------------
def make_sprite_layout(emotes, w, h, emote_px, density, rng):
    """Assign each sprite a 'home' cell on a grid that fully tiles the screen at peak.

    density (>=1) oversamples the grid so emotes overlap and guarantee 100% cover.
    The draw order of rng calls here is mirrored exactly by the UI preview.
    Returns (sprites, count)."""
    # cell size smaller than emote so rotated emotes overlap and leave no gaps
    cell = max(8.0, emote_px * 0.62 / max(1.0, density ** 0.5))
    cols = int(math.ceil(w / cell)) + 1
    rows = int(math.ceil(h / cell)) + 1
    sprites = []
    for r in range(rows):
        for c in range(cols):
            idx = rng.index(len(emotes))
            hx = c * cell + cell / 2 + rng.uniform(-cell * 0.25, cell * 0.25)
            hy = r * cell + cell / 2 + rng.uniform(-cell * 0.25, cell * 0.25)
            sprites.append({
                "em": emotes[idx],
                "hx": hx,
                "hy": hy,
                "row": r,
                "col": c,
                "rows": rows,
                "cols": cols,
                "seed": rng.next(),
                "rot": rng.uniform(0, 360),
                "spin": rng.uniform(-120, 120),
                "ang": rng.uniform(0, 2 * math.pi),
                "dist": rng.uniform(0.5, 1.0),
                "delay": rng.next(),
                "phase": rng.next(),
            })
    rng.shuffle(sprites)
    return sprites, len(sprites)


# --------------------------------------------------------------------------
# sprite compositing
# --------------------------------------------------------------------------
# Transformed-sprite memo. resize + rotate dominate render time, so quantize
# rotation to 15 deg and scale to ~5% relative steps and reuse the results.
_XFORM_CACHE = {}
_XFORM_LIMIT = 6000
_ALPHA_LUTS = {}

ROT_STEPS = 24                      # 360 / 15
SCALE_BASE = 1.05                   # ~1/20 relative steps


def _alpha_lut(step):
    lut = _ALPHA_LUTS.get(step)
    if lut is None:
        a = step / 64.0
        lut = [int(v * a) for v in range(256)]
        _ALPHA_LUTS[step] = lut
    return lut


def _transformed(key, img, rot_q, scale_q):
    ck = (key, rot_q, scale_q)
    hit = _XFORM_CACHE.get(ck)
    if hit is not None:
        return hit
    out = img
    scale = SCALE_BASE ** scale_q
    if abs(scale - 1.0) > 1e-6:
        nw = max(1, int(img.width * scale))
        nh = max(1, int(img.height * scale))
        out = out.resize((nw, nh), Image.BILINEAR)
    rot = rot_q * (360.0 / ROT_STEPS)
    if rot > 0.5:
        out = out.rotate(rot, expand=True, resample=Image.BILINEAR)
    if len(_XFORM_CACHE) >= _XFORM_LIMIT:
        _XFORM_CACHE.clear()
    _XFORM_CACHE[ck] = out
    return out


def paste_rgba(canvas, sprite_img, cx, cy, rot, alpha, scale=1.0, key=None):
    if alpha <= 0.01 or scale <= 0.02:
        return
    # cull before doing any transform work: a rotated sprite can never reach
    # further than its own half-diagonal from its center
    reach = math.hypot(sprite_img.width, sprite_img.height) * scale * 0.5
    if (cx + reach < 0 or cy + reach < 0
            or cx - reach > canvas.width or cy - reach > canvas.height):
        return

    rot_q = int(round((rot % 360.0) / (360.0 / ROT_STEPS))) % ROT_STEPS
    scale_q = 0 if abs(scale - 1.0) < 1e-6 else int(
        round(math.log(scale) / math.log(SCALE_BASE)))
    img = _transformed(key if key is not None else id(sprite_img),
                       sprite_img, rot_q, scale_q)

    if alpha < 0.99:
        step = max(1, int(round(alpha * 64)))
        if step < 64:
            a = img.split()[3].point(_alpha_lut(step))
            img = img.copy()
            img.putalpha(a)

    x = int(cx - img.width / 2)
    y = int(cy - img.height / 2)
    canvas.alpha_composite(img, (x, y))


# --------------------------------------------------------------------------
# logo overlay
# --------------------------------------------------------------------------
def load_logo(path, canvas_w, size_pct):
    """Load the logo (static or animated) scaled to size_pct% of canvas width."""
    frames, durs = _read_frames(path)
    target_w = max(8.0, canvas_w * float(size_pct) / 100.0)
    scale = target_w / frames[0].width
    out = [fr.resize((max(1, int(fr.width * scale)), max(1, int(fr.height * scale))),
                     Image.LANCZOS) for fr in frames]
    return {"frames": out, "durations": durs, "total_ms": float(sum(durs))}


def logo_phase(t, hold, in_frac):
    """Where the logo is in its life, or None when it isn't on screen.

    The logo lives inside the hold window — the stretch where the emotes have
    the screen fully covered — so it is never seen floating over a live scene.
    Returns (mode, p) with p=1 meaning fully arrived."""
    _, a, b = timing_windows(hold, in_frac)
    span = b - a
    if span <= 1e-9:
        return None
    u = (t - a) / span
    if u < 0.0 or u > 1.0:
        return None
    if u < LOGO_ENTRY:
        return ("in", u / LOGO_ENTRY)
    if u > 1.0 - LOGO_EXIT:
        return ("out", (1.0 - u) / LOGO_EXIT)
    return ("hold", 1.0)


def _eo_cubic(p):
    return 1.0 - (1.0 - p) ** 3


def _eo_quart(p):
    return 1.0 - (1.0 - p) ** 4


def _eo_quint(p):
    return 1.0 - (1.0 - p) ** 5


def logo_transform(anim, p, jit=0.0):
    """Transform for a logo that is p of the way to settled (p=1 = at rest).

    Every animation resolves to the identity at p=1, so the logo always ends
    up square in its anchor spot. Mirrored in the UI preview."""
    sx = sy = 1.0
    rot = 0.0
    dx = dy = 0.0
    a = 1.0
    split = 0.0

    if anim == "none":
        a = 1.0 if p > 0 else 0.0
    elif anim == "fade":
        a = p
    elif anim == "pop":
        sx = sy = ease_overshoot(p)
        a = min(1.0, p * 2)
    elif anim == "slam":
        sx = sy = 2.5 - 1.5 * _eo_quint(p)
        a = min(1.0, p * 3)
    elif anim == "spin":
        e = _eo_cubic(p)
        rot = (1.0 - e) * 720.0
        sx = sy = e
        a = min(1.0, p * 2)
    elif anim == "drop":
        dy = -(1.0 - ease_bounce(p)) * 0.7
        a = min(1.0, p * 3)
    elif anim == "rise":
        dy = (1.0 - _eo_cubic(p)) * 0.7
        a = min(1.0, p * 3)
    elif anim == "flip":
        sx = max(0.02, abs(math.cos((1.0 - p) * math.pi * 1.5)))
        a = min(1.0, p * 2)
    elif anim == "swing":
        rot = math.sin((1.0 - p) * math.pi * 3.0) * 30.0 * (1.0 - p)
        a = min(1.0, p * 2)
    elif anim == "glitch":
        amp = 1.0 - p
        a = 1.0 if p > 0.15 else p / 0.15
        dx = (jit - 0.5) * 0.06 * amp
        dy = ((jit * 7.0) % 1.0 - 0.5) * 0.04 * amp
        split = amp * 0.02
    elif anim == "zoom":
        sx = sy = 0.15 + 0.85 * _eo_quart(p)
        a = min(1.0, p * 2.5)
    return {"sx": sx, "sy": sy, "rot": rot, "dx": dx, "dy": dy,
            "alpha": a, "split": split}


def anchor_point(anchor, w, h, iw, ih, margin=0.05):
    """Centre point for the settled logo, given a 9-point anchor."""
    if anchor not in LOGO_ANCHORS:
        anchor = "mc"
    mx, my = w * margin, h * margin
    row, col = anchor[0], anchor[1]
    x = {"l": mx + iw / 2.0, "c": w / 2.0, "r": w - mx - iw / 2.0}[col]
    y = {"t": my + ih / 2.0, "m": h / 2.0, "b": h - my - ih / 2.0}[row]
    return x, y


def _rgb_split(im, px):
    """Cheap chromatic aberration for the glitch entry."""
    px = int(round(px))
    if px == 0:
        return im
    r, g, b, a = im.split()
    r = ImageChops.offset(r, px, 0)
    b = ImageChops.offset(b, -px, 0)
    return Image.merge("RGBA", (r, g, b, a))


def render_logo(canvas, logo, t, cfg):
    """Composite the logo on top of the emote layer. No-op when there's none."""
    if not logo:
        return
    ph = logo_phase(t, cfg["hold"], cfg["in_frac"])
    if ph is None:
        return
    mode, p = ph
    if mode == "out":
        anim = cfg.get("logo_out") or cfg.get("logo_in") or "pop"
    else:
        anim = cfg.get("logo_in") or "pop"

    n = max(2, cfg.get("n_frames", 2))
    idx = int(round(t * (n - 1)))
    jit = Rng((int(cfg.get("seed", 0)) + idx * 7919) % 4294967296).next()

    tr = logo_transform(anim, p, jit)
    if tr["alpha"] <= 0.01 or tr["sx"] <= 0.01 or tr["sy"] <= 0.01:
        return

    base = emote_frame(logo, t * cfg["duration_ms"], 0.0)
    w, h = canvas.size
    # anchor on the settled size so the logo doesn't drift while it scales
    ax, ay = anchor_point(cfg.get("logo_anchor", "mc"), w, h,
                          base.width, base.height)
    ax += tr["dx"] * w + float(cfg.get("logo_dx", 0.0)) / 100.0 * w
    ay += tr["dy"] * h + float(cfg.get("logo_dy", 0.0)) / 100.0 * h

    img = base
    nw = max(1, int(round(img.width * tr["sx"])))
    nh = max(1, int(round(img.height * tr["sy"])))
    if (nw, nh) != img.size:
        img = img.resize((nw, nh), Image.BILINEAR)
    if abs(tr["rot"]) > 0.01:
        img = img.rotate(tr["rot"], expand=True, resample=Image.BICUBIC)
    if tr["split"] > 0:
        img = _rgb_split(img, tr["split"] * base.width)
    if tr["alpha"] < 0.99:
        step = max(1, int(round(tr["alpha"] * 64)))
        if step < 64:
            alpha = img.split()[3].point(_alpha_lut(step))
            img = img.copy()
            img.putalpha(alpha)

    canvas.alpha_composite(img, (int(ax - img.width / 2),
                                 int(ay - img.height / 2)))


# --------------------------------------------------------------------------
# frame rendering
# --------------------------------------------------------------------------
def render_frame(t, sprites, cfg, logo=None):
    """t in [0,1]. cov=coverage_curve drives convergence: 0=dispersed, 1=full grid.

    Most styles move each sprite between a 'far' (dispersed) position and its grid
    'home', converging to full coverage at the transition point. Two styles —
    downpour and zoom — use their own motion and are handled separately."""
    style = cfg["style"]
    w, h = cfg["width"], cfg["height"]
    hold, in_frac = cfg["hold"], cfg["in_frac"]
    direction = cfg["direction"]
    ease = EASE_FN.get(cfg["easing"], ease_in_out)
    t_ms = t * cfg["duration_ms"]

    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cov = coverage_curve(t, hold, in_frac)
    cx, cy = w / 2.0, h / 2.0
    diag = math.hypot(w, h)

    # ---- continuous downpour: no pause, screen packed mid-fall ----
    if style == "downpour":
        up = direction == "up"
        for s in sprites:
            img = emote_frame(s["em"], t_ms, s["phase"])
            # Each sprite falls across the screen, passing through its own grid
            # home exactly at the transition point — so the densest moment is a
            # fully tiled screen rather than a random scatter that can leave
            # gaps. The sideways drift is zeroed at that instant for the same
            # reason.
            vy = (h + 2 * img.height) * 1.25
            y = s["hy"] + (t - in_frac) * (-vy if up else vy)
            wob = s["seed"] * 6.28
            x = s["hx"] + (math.sin(t * 5 + wob) - math.sin(in_frac * 5 + wob)) * 10
            rot = s["rot"] + s["spin"] * t * 2
            a = 1.0
            if y < -img.height * 0.5 or y > h + img.height * 0.5:
                a = 0.0
            paste_rgba(canvas, img, x, y, rot, a, key=id(img))
        render_logo(canvas, logo, t, cfg)
        return canvas

    # ---- zoom: rush toward the camera, scaling up from a point ----
    if style == "zoom":
        for s in sprites:
            img = emote_frame(s["em"], t_ms, s["phase"])
            # direction from center toward this sprite's home
            dx, dy = s["hx"] - cx, s["hy"] - cy
            k = ease(cov)
            # at cov=0 sprite sits near center, tiny; at cov=1 it's home, full size
            x = cx + dx * k
            y = cy + dy * k
            scale = 0.05 + 0.95 * k
            rot = s["rot"] + s["spin"] * (1 - cov)
            a = min(1.0, cov * 1.6)
            paste_rgba(canvas, img, x, y, rot, a, scale=scale, key=id(img))
        render_logo(canvas, logo, t, cfg)
        return canvas

    # ---- converge-family: all share the far->home interpolation ----
    for s in sprites:
        img = emote_frame(s["em"], t_ms, s["phase"])
        iw, ih = img.width, img.height
        hx, hy = s["hx"], s["hy"]

        # per-sprite coverage: most styles move as one, wipe and rain stagger
        if style == "wipe":
            hxn, hyn = hx / w, hy / h
            X, Y = (w + iw) * 1.4, (h + ih) * 1.4
            if direction == "left":
                far_x, far_y = hx + X, hy + Y
                delay = 1.0 - (hxn + hyn) / 2.0
            elif direction == "down":
                far_x, far_y = hx + X, hy - Y
                delay = ((1.0 - hxn) + hyn) / 2.0
            elif direction == "up":
                far_x, far_y = hx - X, hy + Y
                delay = (hxn + (1.0 - hyn)) / 2.0
            else:  # right (default): sweeps down-right from the top-left corner
                far_x, far_y = hx - X, hy - Y
                delay = (hxn + hyn) / 2.0
            cov_s = stagger(cov, clamp01(delay))
        elif style == "rain":
            cov_s = stagger(cov, s["delay"])
            reach = 1.0 + s["seed"]
            if direction == "up":
                far_x, far_y = hx, hy + (h + ih) * reach
            elif direction == "left":
                far_x, far_y = hx + (w + iw) * reach, hy
            elif direction == "right":
                far_x, far_y = hx - (w + iw) * reach, hy
            else:  # down
                far_x, far_y = hx, hy - (h + ih) * reach
        else:
            cov_s = cov

        if style == "burst":
            ang = s["ang"]
            r = diag * (0.6 + 0.6 * s["dist"])
            far_x = cx + math.cos(ang) * r
            far_y = cy + math.sin(ang) * r
        elif style == "swipe":
            if direction == "left":
                far_x, far_y = hx + (w + iw) * 1.2, hy
            elif direction == "up":
                far_x, far_y = hx, hy + (h + ih) * 1.2
            elif direction == "down":
                far_x, far_y = hx, hy - (h + ih) * 1.2
            else:  # right
                far_x, far_y = hx - (w + iw) * 1.2, hy
        elif style == "spiral":
            ang = s["ang"] + (1 - cov_s) * 7.0
            r = diag * 0.7 * s["dist"]
            far_x = cx + math.cos(ang) * r
            far_y = cy + math.sin(ang) * r
        elif style == "swarm":
            ang = s["ang"]
            r = diag * (0.7 + 0.5 * s["dist"])
            far_x = cx + math.cos(ang) * r
            far_y = cy + math.sin(ang) * r
        elif style == "rows":
            # alternating horizontal lines slide in from opposite sides
            lead = (s["row"] % 2 == 0) == (direction == "right")
            far_x = hx - (w + iw) * 1.3 if lead else hx + (w + iw) * 1.3
            far_y = hy
        elif style == "columns":
            # alternating vertical lines slide in from top/bottom
            lead = (s["col"] % 2 == 0) == (direction == "down")
            far_y = hy - (h + ih) * 1.3 if lead else hy + (h + ih) * 1.3
            far_x = hx
        elif style == "shockwave":
            # concentric rings ripple out: far radius scaled by home distance
            dx, dy = hx - cx, hy - cy
            dist = math.hypot(dx, dy) or 1.0
            ang = math.atan2(dy, dx)
            far_r = dist + diag * 0.6
            far_x = cx + math.cos(ang) * far_r
            far_y = cy + math.sin(ang) * far_r
        elif style == "vortex":
            # spin into / out of the center like a drain
            dx, dy = hx - cx, hy - cy
            base_ang = math.atan2(dy, dx)
            dist = math.hypot(dx, dy)
            ang = base_ang + (1 - cov_s) * 9.0
            r = dist + (1 - cov_s) * diag * 0.5
            far_x = cx + math.cos(ang) * r
            far_y = cy + math.sin(ang) * r
        elif style not in ("rain", "wipe", "swipe"):
            far_x, far_y = hx, hy

        k = ease(cov_s)
        x = far_x + (hx - far_x) * k
        y = far_y + (hy - far_y) * k
        rot = s["rot"] + s["spin"] * (1 - cov_s)
        a = min(1.0, cov_s * 1.6)
        paste_rgba(canvas, img, x, y, rot, a, key=id(img))

    render_logo(canvas, logo, t, cfg)
    return canvas


# --------------------------------------------------------------------------
# worker plumbing
# --------------------------------------------------------------------------
# Workers rebuild the sprite layout once at startup from the seed rather than
# receiving pickled PIL images with every task.
_W = {}


def _init_worker(cfg):
    emotes = load_emotes(
        cfg["images"], cfg["emote_px"],
        outline=cfg["outline"], outline_color=cfg["outline_color"],
        shadow=cfg["shadow"])
    rng = Rng(cfg["seed"])
    sprites, _ = make_sprite_layout(
        emotes, cfg["width"], cfg["height"], cfg["emote_px"],
        cfg["layout_density"], rng)
    _W["cfg"] = cfg
    _W["sprites"] = sprites
    _W["logo"] = (load_logo(cfg["logo_path"], cfg["width"], cfg["logo_size"])
                  if cfg.get("logo_path") else None)


def _render_index(i):
    cfg = _W["cfg"]
    return _render_bytes(i, _W["sprites"], cfg, _W.get("logo"))


def _render_bytes(i, sprites, cfg, logo=None):
    n = cfg["n_frames"]
    t = i / (n - 1) if n > 1 else 0.0
    frame = render_frame(t, sprites, cfg, logo)
    if cfg["bg_test"]:
        bg = Image.new("RGBA", (cfg["width"], cfg["height"]), (40, 160, 60, 255))
        bg.alpha_composite(frame)
        frame = bg
    return frame.tobytes()


# --------------------------------------------------------------------------
# encoding
# --------------------------------------------------------------------------
def ffmpeg_cmd(fmt, w, h, fps, out, quality, audio):
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-nostats",
           "-f", "rawvideo", "-pix_fmt", "rgba",
           "-s", f"{w}x{h}", "-framerate", str(fps), "-i", "-"]
    if audio:
        cmd += ["-i", audio]
    if fmt == "mov":
        cmd += ["-c:v", "prores_ks", "-profile:v", "4444",
                "-pix_fmt", "yuva444p10le"]
    else:
        cmd += ["-c:v", "libvpx-vp9",
                "-pix_fmt", "yuva420p",
                "-metadata:s:v:0", "alpha_mode=1",
                "-b:v", "0", "-crf", str(int(quality)),
                "-auto-alt-ref", "0",
                "-row-mt", "1", "-cpu-used", "4",
                "-tile-columns", "2", "-threads", "0"]
    if audio:
        cmd += ["-map", "0:v:0", "-map", "1:a:0"]
        # opus is a webm codec; mov needs aac
        cmd += (["-c:a", "aac", "-b:a", "192k"] if fmt == "mov"
                else ["-c:a", "libopus", "-b:a", "128k"])
        cmd += ["-shortest"]
    # without this the muxer stamps a random SegmentUID and the encoder date,
    # so the same seed would produce files that differ byte-wise
    cmd += ["-fflags", "+bitexact", "-flags:v", "+bitexact"]
    cmd += ["-r", str(fps), out]
    return cmd


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------
def build(images, out, style="rain", width=1920, height=1080, fps=30,
          duration=1.2, hold=0.08, density=2.0, emote_px=160, seed=None,
          bg_test=False, in_frac=0.5, direction=None, easing="smooth",
          quality=28, audio=None, fmt="webm", outline=0,
          outline_color="#000000", shadow=False,
          logo=None, logo_size=22.0, logo_anchor="mc", logo_dx=0.0,
          logo_dy=0.0, logo_in="pop", logo_out=None, progress=None):
    """Render a stinger. Returns a dict with the transition point and metadata.

    progress(stage, done, total): optional callback. stage is 'render' or
    'encode'. Safe to pass None."""
    def report(stage, done, total):
        if progress:
            try:
                progress(stage, done, total)
            except Exception:
                pass

    if style not in STYLES:
        raise ValueError(f"unknown style: {style}")
    if fmt not in FORMATS:
        raise ValueError(f"unknown format: {fmt}")

    # a concrete seed, so the workers and the caller all agree on the layout
    if seed is None or seed == "":
        seed = random.randrange(2 ** 31)
    seed = int(seed) % 4294967296

    n_frames = max(2, int(round(fps * duration)))
    # downpour has inherent gaps between falling emotes, so pack it denser
    # internally to keep the screen covered at the transition point.
    layout_density = density * 1.5 if style == "downpour" else density
    in_frac, _, _ = timing_windows(hold, in_frac)

    cfg = {
        "style": style, "width": width, "height": height,
        "hold": hold, "in_frac": in_frac,
        "direction": resolve_direction(style, direction),
        "easing": easing if easing in EASE_FN else "smooth",
        "duration_ms": duration * 1000.0,
        "n_frames": n_frames, "bg_test": bg_test,
        "images": list(images), "emote_px": emote_px, "seed": seed,
        "layout_density": layout_density,
        "outline": int(outline or 0), "outline_color": outline_color,
        "shadow": bool(shadow),
        "logo_path": logo or None,
        "logo_size": float(logo_size), "logo_anchor": logo_anchor,
        "logo_dx": float(logo_dx), "logo_dy": float(logo_dy),
        "logo_in": logo_in if logo_in in LOGO_ANIMS else "pop",
        "logo_out": logo_out if logo_out in LOGO_ANIMS else None,
    }

    emotes = load_emotes(images, emote_px, outline=cfg["outline"],
                         outline_color=outline_color, shadow=cfg["shadow"])
    sprites, count = make_sprite_layout(
        emotes, width, height, emote_px, layout_density, Rng(seed))
    logo_obj = load_logo(logo, width, logo_size) if logo else None

    transition_ms = int(round(n_frames * in_frac / fps * 1000))
    nproc = max(1, min(cpu_count(), 8))
    use_pool = nproc > 1 and n_frames > 3

    report("render", 0, n_frames)

    if fmt == "png":
        _build_png_sequence(out, cfg, sprites, nproc, use_pool, report, logo_obj)
    else:
        _build_video(out, cfg, sprites, nproc, use_pool, report,
                     fps, quality, audio, fmt, logo_obj)

    return {"out": out, "transition_ms": transition_ms, "frames": n_frames,
            "count": count, "seed": seed, "format": fmt,
            "direction": cfg["direction"]}


def _frame_stream(cfg, sprites, nproc, use_pool, report, logo=None):
    """Yield finished frames as raw RGBA bytes, strictly in order."""
    n = cfg["n_frames"]
    if use_pool:
        # imap (ordered) — frames must reach the encoder in sequence
        with Pool(nproc, initializer=_init_worker, initargs=(cfg,)) as pool:
            done = 0
            for buf in pool.imap(_render_index, range(n), chunksize=1):
                done += 1
                report("render", done, n)
                yield buf
    else:
        for i in range(n):
            buf = _render_bytes(i, sprites, cfg, logo)
            report("render", i + 1, n)
            yield buf


def _build_video(out, cfg, sprites, nproc, use_pool, report,
                 fps, quality, audio, fmt, logo=None):
    cmd = ffmpeg_cmd(fmt, cfg["width"], cfg["height"], fps, out, quality, audio)
    # stderr goes to a file, not a pipe: nothing reads it while we are busy
    # feeding frames, and a full pipe buffer would deadlock the encoder.
    log = tempfile.TemporaryFile()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=log,
                            **sp_kwargs())
    try:
        for buf in _frame_stream(cfg, sprites, nproc, use_pool, report, logo):
            proc.stdin.write(buf)
    except BrokenPipeError:
        pass                                    # ffmpeg died; surfaced below
    finally:
        try:
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    report("encode", 0, 1)
    rc = proc.wait()
    if rc != 0:
        log.seek(0)
        msg = log.read().decode("utf-8", "replace").strip()
        log.close()
        raise RuntimeError(f"ffmpeg failed (exit {rc}):\n{msg[-2000:]}")
    log.close()
    report("encode", 1, 1)


def _build_png_sequence(out, cfg, sprites, nproc, use_pool, report, logo=None):
    """Write the frames as PNGs and zip them."""
    w, h, n = cfg["width"], cfg["height"], cfg["n_frames"]
    tmp = tempfile.mkdtemp(prefix="stinger_png_")
    try:
        paths = []
        for i, buf in enumerate(_frame_stream(cfg, sprites, nproc, use_pool,
                                              report, logo)):
            p = os.path.join(tmp, f"frame_{i:05d}.png")
            Image.frombytes("RGBA", (w, h), buf).save(p)
            paths.append(p)
        report("encode", 0, 1)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for p in paths:
                z.write(p, os.path.basename(p))
        report("encode", 1, 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Make OBS WebM stinger transitions from emote images.")
    ap.add_argument("--images", nargs="+", required=True, help="emote image files (PNG/GIF/WebP; transparency ideal)")
    ap.add_argument("--out", default="stinger.webm")
    ap.add_argument("--style", choices=STYLES, default="rain")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--duration", type=float, default=1.2, help="seconds")
    ap.add_argument("--hold", type=float, default=0.08, help="fraction of timeline held fully covered (0-0.5)")
    ap.add_argument("--in-frac", type=float, default=0.5, dest="in_frac",
                    help="where peak coverage lands, 0.2-0.8 (0.5 = halfway)")
    ap.add_argument("--density", type=float, default=2.0, help="coverage multiplier; higher = more emotes / fuller cover")
    ap.add_argument("--emote-px", type=int, default=160, help="emote size in px (longest side)")
    ap.add_argument("--direction", choices=DIRECTIONS, default=None,
                    help="travel direction for rain/swipe/wipe/rows/columns/downpour")
    ap.add_argument("--easing", choices=EASINGS, default="smooth")
    ap.add_argument("--quality", type=int, default=28, help="VP9 crf, 18 (best) - 40 (smallest)")
    ap.add_argument("--audio", default=None, help="optional audio file to mux in")
    ap.add_argument("--format", choices=FORMATS, default="webm", dest="fmt",
                    help="webm (VP9 alpha), mov (ProRes 4444), png (zipped sequence)")
    ap.add_argument("--outline", type=int, default=0, help="outline width in px (0 = off)")
    ap.add_argument("--outline-color", default="#000000")
    ap.add_argument("--shadow", action="store_true", help="soft drop shadow on each emote")
    ap.add_argument("--logo", default=None, help="optional logo image that lands at the transition point")
    ap.add_argument("--logo-size", type=float, default=22.0, help="logo width as %% of the canvas")
    ap.add_argument("--logo-anchor", choices=LOGO_ANCHORS, default="mc",
                    help="9-point placement: t/m/b + l/c/r (default mc = centre)")
    ap.add_argument("--logo-dx", type=float, default=0.0, help="nudge the logo horizontally, %% of width")
    ap.add_argument("--logo-dy", type=float, default=0.0, help="nudge the logo vertically, %% of height")
    ap.add_argument("--logo-in", choices=LOGO_ANIMS, default="pop", help="logo entry animation")
    ap.add_argument("--logo-out", choices=LOGO_ANIMS, default=None,
                    help="logo exit animation (default: the entry, reversed)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--bg-test", action="store_true", help="composite on green bg to preview (NOT for OBS)")
    args = ap.parse_args()

    for p in args.images:
        if not os.path.isfile(p):
            print(f"missing image: {p}", file=sys.stderr)
            sys.exit(1)
    if args.audio and not os.path.isfile(args.audio):
        print(f"missing audio: {args.audio}", file=sys.stderr)
        sys.exit(1)
    if args.logo and not os.path.isfile(args.logo):
        print(f"missing logo: {args.logo}", file=sys.stderr)
        sys.exit(1)

    out = args.out
    want = EXT[args.fmt]
    if not out.lower().endswith(want):
        out = os.path.splitext(out)[0] + want

    r = build(
        images=args.images, out=out, style=args.style,
        width=args.width, height=args.height, fps=args.fps,
        duration=args.duration, hold=args.hold, density=args.density,
        emote_px=args.emote_px, seed=args.seed, bg_test=args.bg_test,
        in_frac=args.in_frac, direction=args.direction, easing=args.easing,
        quality=args.quality, audio=args.audio, fmt=args.fmt,
        outline=args.outline, outline_color=args.outline_color,
        shadow=args.shadow,
        logo=args.logo, logo_size=args.logo_size, logo_anchor=args.logo_anchor,
        logo_dx=args.logo_dx, logo_dy=args.logo_dy,
        logo_in=args.logo_in, logo_out=args.logo_out,
    )
    print(f"wrote {r['out']}  ({r['frames']} frames, {r['count']} emotes, "
          f"style={args.style}, seed={r['seed']})")
    print(f"OBS transition point: {r['transition_ms']} ms")


if __name__ == "__main__":
    main()
