# Stinger Studio

Make OBS stinger transitions out of your own images. Drop in emotes, logos, stickers
or anything else, pick a style, hit Generate. Out comes a transparent WebM that goes
straight into OBS. Everything runs locally on your PC.

<!-- SCREENSHOT: the main window with a transition mid preview -->

## A.I Disclaimer

I do not claim to be a programmer or having made this. Yes, I prompted Claude and
reviewed, tested, self QA'd and tweaked. I knew what the outcomes should be and
understand the issues enough to be able to redirect Claude to be able to fix as I do
have an IT background. I completely understand if you do not trust this project but I
wanted to make it clear that I orginally made this for just myself and decided to share
incase someone else was interested. I do not claim to be the creator, I just gave
prompts and if it was good, I went with it.

## What it does

- **Any images** - drop in PNGs, GIFs or animated WebP. Transparent backgrounds look
  best. Animated ones keep playing while they fly across the screen.
<!-- SCREENSHOT: the Images box with a few thumbnails loaded -->

- **Fifteen styles** - rain, burst, swipe, spiral, swarm, rows, columns, downpour,
  zoom, wipe, shockwave, vortex, popcorn, wave and shatter. Rain, swipe, wipe, wave
  and downpour can be aimed left, right, up or down. The first four also take a
  separate direction out, so they can come in from the left and leave downward.
<!-- SCREENSHOT: the style buttons -->

- **Live preview** - runs the same maths as the real render, so what you see is what
  you get. Scrub through it or let it loop.
<!-- SCREENSHOT: the preview area with the play bar and transition point readout -->

- **Size and amount** - sliders for how big the images are, how many of them, how long
  the clip runs, and how random the sizes should be.
<!-- SCREENSHOT: the Adjust group -->

- **Logo** - drop a logo that lands on top at the moment the screen is covered, then
  leaves with everything else. Ten entry animations and a nine point placement grid.
<!-- SCREENSHOT: the Logo group with a logo loaded -->

- **Sound** - add an mp3 or wav with volume and fade out. It plays along with the
  preview so you can line it up before you render.
<!-- SCREENSHOT: the Sound row -->

- **Weighting** - click an image thumbnail to make it show up two or three times as
  often as the others.

- **Presets** - save every setting under a name. Six come built in.

- **Update check** - the app looks at the Releases page when it starts and puts a
  banner across the top when there is a newer version. Hit Not now and it stops asking
  about that one.
<!-- SCREENSHOT: the update banner across the top of the window -->

- **Render all styles** - renders your settings once per style so you can pick the one
  you like, then saves all fifteen to a folder.
<!-- SCREENSHOT: the result panel after a batch render -->

The app tells you the transition point in milliseconds, which is the one number OBS
needs. There is a Copy button next to it.

## Install

1. Download **StingerStudio.exe** from [Releases](https://github.com/TheITStreamer/Stinger-Studio/releases/latest).
2. Run it. Windows may warn about an unknown publisher, this is normal for a small
   unsigned app.
3. The app checks for new versions on startup and shows a banner when one is out.

### Building it yourself

You only need this if you would rather build from source. Install Python 3 from
python.org, tick **Add python.exe to PATH** on the first installer screen, then double
click **build.bat**. It installs what it needs, downloads ffmpeg and builds the app.
You end up with `dist\StingerStudio.exe`, which is the whole app with ffmpeg inside it.

The exe icon comes from `S.png`. Swap that file for your own and build again, or run
`python make_icon.py` to rebuild `icon.ico` on its own.

## Use it

1. Double click **StingerStudio.exe**. Nothing to install, it just opens.
2. Drag your images into the box.
3. Pick a style and set the sliders. Watch the preview.
4. Click **Generate**, then **Save file...**.
5. In OBS: **Scene Transitions > + > Stinger**, pick the file, and paste in the
   transition point the app showed you.

<!-- SCREENSHOT: the OBS stinger settings with the transition point filled in -->

## Good to know

- Output is a VP9 WebM with alpha, which is what OBS stingers want. MOV (ProRes 4444)
  and a zipped PNG sequence are also there if you are taking it into an editor.
- Resolutions go up to 4K, frame rates up to 120.
- The seed number decides the layout. Same seed and same settings gives you the exact
  same file every time. Hit the dice to roll a new one.
- Your presets live at `%APPDATA%\StingerStudio\presets.json` and survive restarts.
- The last folder you saved to is remembered at `%APPDATA%\StingerStudio\settings.json`.
- A PNG sequence has no audio track, so a sound gets skipped for that format. The app
  tells you when that happens.
- If the ffmpeg download during the build fails, grab
  `ffmpeg-master-latest-win64-gpl.zip` from the BtbN FFmpeg-Builds releases page and
  copy `bin\ffmpeg.exe` into a folder called `bin` next to build.bat, then run
  build.bat again.
- Windows only. The same code can target Mac but a Mac app has to be built on a Mac.

## Running from source

```
pip install pillow pywebview
python app.py
```

**NOTE:** Needs ffmpeg on your PATH, or an `ffmpeg.exe` in a `bin` folder next to
`app.py`.

The render engine also runs on its own without the window:

```
python engine.py --images a.png b.png --style wave --out stinger.webm \
    --direction right --direction-out down
```

`python engine.py --help` lists every option.
