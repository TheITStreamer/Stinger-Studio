# Stinger Studio — desktop app

A windowed app for making OBS stinger transitions out of emotes. Load images, set
size and amount with sliders, pick a style, hit **Generate**, save the file. The
default output is a transparent VP9 WebM that drops straight into OBS.

There are two stages: **you build the .exe once**, then **anyone runs the .exe with
nothing to install**.

---

## Part 1 — Build the .exe (you do this once, on Windows)

You need this only on the machine that builds the app. Friends never do any of it.

1. Install **Python 3** from python.org. On the first installer screen, tick
   **"Add python.exe to PATH"**.
2. Put all these files in one folder:
   `app.py`, `engine.py`, `ui.html`, `fetch_ffmpeg.py`, `StingerStudio.spec`, `build.bat`.
3. Double-click **`build.bat`**.

That script installs what it needs, downloads ffmpeg automatically, and builds the
app. When it finishes you'll have:

```
dist\StingerStudio.exe
```

That single file is the whole app — ffmpeg and everything is inside it.

> First build takes a few minutes (it downloads ffmpeg, ~80MB). After that it's quick.

### If the ffmpeg download fails
Some networks block the download. Workaround: grab
`ffmpeg-master-latest-win64-gpl.zip` from the BtbN FFmpeg-Builds releases page,
open it, and copy `bin\ffmpeg.exe` into a folder called `bin` next to `build.bat`.
Then run `build.bat` again — it'll skip the download.

---

## Part 2 — Use it (you or anyone)

1. Double-click **`StingerStudio.exe`**. A window opens. Nothing to install.
2. Drag your emotes into the box. PNGs with transparent backgrounds look best,
   and **animated GIF / WebP** work too — each emote plays as it falls.
3. Pick a **style**, then use the controls (below).
4. Watch the live preview. The checkerboard = transparent (your live scene shows
   through there). The preview uses the same seed and the same motion maths as
   the render, so what you see is what you get.
5. Click **Generate**, then **Save file…** to put it wherever you want.
6. In OBS: **Scene Transitions → + → Stinger**, choose the file, and set the
   **transition point** shown in the app (in milliseconds).

---

## Controls

**Adjust**

- **Emote size** — how big each emote is.
- **Amount** — how densely they flood the screen.
- **Duration** — total length of the clip.
- **Hold** — how long the screen stays fully covered at the peak.
- **Transition point** — where in the clip the screen is fully covered, as a
  percentage. 50% is centred; lower means a fast flood and a slow clear, higher
  the reverse. The millisecond readout follows this, so paste that into OBS.
- **Easing** — how sprites settle into place: `smooth` (default),
  `linear`, `overshoot` (passes home by ~8% then settles), `bounce`.

**Direction** — appears for the styles that can be aimed: `rain`, `swipe`,
`wipe`, `rows`, `columns`, `downpour`. It always means *which way the emotes
travel* — so `rain` + `up` floats them upward, and for `rows`/`columns` it picks
which side the even lines come from.

**Logo** — an optional logo that lands on top of the emotes at the moment the
screen is fully covered, then leaves with them. Load any image (animated GIF /
WebP work too) and you get:

- **Size** — logo width as a % of the screen.
- **Position** — a 9-point grid (corners, edges, centre), plus **Nudge X/Y** for
  fine placement.
- **Entry** — `pop`, `slam`, `spin`, `fade`, `drop`, `rise`, `flip`, `swing`,
  `glitch`, `zoom`, or `none` for a hard cut.
- **Exit** — defaults to the entry animation reversed; pick a different one if
  you want it to leave differently than it arrived.

The logo is only ever on screen while the emotes have the screen fully covered,
so it never floats over your live scene, and it can't affect the transition
point. Because of that its screen time comes out of **Hold** — loading a logo
raises Hold to 0.26 automatically if it's lower, otherwise the logo would only
flash for two or three frames.

**Emote effects** — applied once when the emotes load, so they cost nothing per
frame:

- **Outline** — a 1–4 px coloured stroke around each emote, with a colour picker.
- **Drop shadow** — a soft shadow behind each emote.

**Output**

- **Resolution** — 1920×1080, 2560×1440 or 1280×720.
- **FPS** — 24, 30, 48, 60, 90 or 120.
- **Quality** — VP9 crf from 18 (best looking, biggest file) to 40 (smallest).
  28 is a good default.
- **Format** — see below.
- **Sound** — optional audio file (mp3/wav/ogg) muxed into the clip. It's
  trimmed to the video length; if it's shorter, it just ends.
- **Seed** — the number that decides the random layout. The same seed and the
  same settings always produce the exact same file. Hit 🎲 to roll a new one.

**Presets** — save every setting (not the emotes themselves) under a name and
recall it later. Four are built in: *Fast punch*, *Slow flood*, *Curtain wipe*,
*Chaos bounce*. Your own are stored in `%APPDATA%\StingerStudio\presets.json`
and survive restarts.

**Render all styles** — renders your current settings once per style, shows
overall progress, then **Save all…** copies all twelve out to a folder you pick,
named `stinger_<style>.<ext>`. The emotes are only uploaded once.

---

## Output formats

| format | what it's for |
|--------|---------------|
| **WebM (VP9 alpha)** | the default — what OBS stingers want |
| **MOV (ProRes 4444)** | editing in Premiere / Resolve / After Effects, keeps alpha |
| **PNG sequence** | a `.zip` of numbered transparent PNGs, one per frame |

---

## Styles

- **rain** — emotes pour down from above, fill, then fall away
- **burst** — explode out from center, then implode
- **swipe** — a wall sweeps across and back
- **spiral** — spiral inward to cover, spiral out
- **swarm** — scatter in from all edges, converge, scatter out
- **rows** — alternating horizontal lines slide in from left and right
- **columns** — alternating vertical lines slide in from top and bottom
- **downpour** — a continuous fall with no pause, packing the screen at the
  transition point
- **zoom** — emotes rush toward you from a point, scaling up to fill
- **wipe** — a staggered diagonal band sweeps across like a curtain pull, each
  emote arriving a beat after the one behind it
- **shockwave** — emotes ripple outward from center in concentric rings
- **vortex** — everything spins into the center and drains away, then back out

All styles fully cover the screen at the transition point, so the cut between
scenes is always hidden.

---

## Command line

The engine runs standalone, with every option the app exposes:

```
python engine.py --images a.png b.gif c.webp --style wipe --out stinger.webm \
    --width 1920 --height 1080 --fps 60 --duration 1.2 \
    --hold 0.08 --in-frac 0.5 --density 2.0 --emote-px 160 \
    --direction right --easing overshoot --quality 28 \
    --outline 3 --outline-color "#ffffff" --shadow \
    --logo logo.png --logo-size 30 --logo-anchor mc --logo-in pop \
    --audio whoosh.mp3 --format webm --seed 12345
```

| flag | meaning |
|------|---------|
| `--images` | emote files (PNG / GIF / WebP), space separated — required |
| `--out` | output path; the extension is corrected to match `--format` |
| `--style` | one of the twelve styles above |
| `--width` / `--height` / `--fps` / `--duration` | clip geometry and length |
| `--hold` | fraction of the timeline held fully covered |
| `--in-frac` | where peak coverage lands, 0.2–0.8 (0.5 = halfway) |
| `--density` | coverage multiplier; higher = more emotes |
| `--emote-px` | emote size in px (longest side) |
| `--direction` | `left`, `right`, `up` or `down` for the directional styles |
| `--easing` | `smooth`, `linear`, `overshoot`, `bounce` |
| `--quality` | VP9 crf, 18 (best) to 40 (smallest) |
| `--audio` | audio file to mux in |
| `--format` | `webm`, `mov` or `png` |
| `--outline` / `--outline-color` | emote stroke width in px and its colour |
| `--shadow` | soft drop shadow on each emote |
| `--logo` | logo image to land at the transition point |
| `--logo-size` | logo width as a % of the canvas (default 22) |
| `--logo-anchor` | `tl` `tc` `tr` `ml` `mc` `mr` `bl` `bc` `br` (default `mc`) |
| `--logo-dx` / `--logo-dy` | nudge the logo, as a % of width / height |
| `--logo-in` | entry animation (see the Logo section) |
| `--logo-out` | exit animation; omit to mirror the entry |
| `--seed` | layout seed; omit for a random one |
| `--bg-test` | composite on a green background to check coverage (not for OBS) |

It prints the OBS transition point and the seed it used.

---

## Files in this kit

| file | what it is |
|------|-----------|
| `app.py` | the app window + bridge between UI and renderer |
| `engine.py` | the render engine (frames + ffmpeg alpha encode) |
| `ui.html` | the interface (sliders, preview, buttons) |
| `fetch_ffmpeg.py` | downloads ffmpeg during the build |
| `StingerStudio.spec` | PyInstaller bundle recipe |
| `build.bat` | one-click build script |

## Notes

- Frames are piped straight into ffmpeg instead of being written out as PNGs
  first, and rendering runs on every core — including in the built exe, which
  used to fall back to a single core.
- The preview is a fast approximation of the final *look*, but no longer of the
  *layout*: it runs the same seeded generator as the engine, so sprites land in
  the same places.
- The **saved file** is the real transparent render — that's what matters for OBS.
- Mac isn't covered by this build kit. The same code can target Mac, but a Mac
  `.app` has to be built on a Mac. Ask if you need that.
