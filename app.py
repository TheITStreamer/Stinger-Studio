#!/usr/bin/env python3
"""
app.py — Stinger Studio desktop app.

Opens a native window wrapping the HTML UI. The UI calls into the `Api` class
below via pywebview's JS bridge. The bridge saves uploaded emotes to a temp
folder, runs the render engine, and returns the finished file's path.

Presets live outside the temp folder (%APPDATA%/StingerStudio on Windows) so
they survive restarts.

Run directly:  python app.py
Build to exe:  see build.bat
"""
import base64
import json
import multiprocessing
import os
import shutil
import sys
import tempfile
import traceback

# CRITICAL on Windows / frozen exe: must run before anything spawns a process.
# Without this, each render worker re-launches the whole app window (fork bomb).
multiprocessing.freeze_support()

import webview

import engine


def resource_path(rel):
    """Resolve a path that works both in dev and inside a PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def locate_ffmpeg():
    """Prefer a bundled ffmpeg (next to the exe / in the bundle), else PATH."""
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    # bundled alongside the frozen exe
    candidates = [
        resource_path(os.path.join("bin", name)),
        resource_path(name),
    ]
    # also next to the actual executable when frozen
    if getattr(sys, "frozen", False):
        candidates.insert(0, os.path.join(os.path.dirname(sys.executable), "bin", name))
    for c in candidates:
        if os.path.isfile(c):
            return c
    return name  # fall back to PATH


def config_dir():
    """Per-user config folder, created on demand. Never the temp workdir."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    d = os.path.join(base, "StingerStudio")
    os.makedirs(d, exist_ok=True)
    return d


# Shipped presets. These always exist and can't be deleted.
BUILTIN_PRESETS = {
    "Fast punch": {
        "style": "burst", "duration": 0.8, "hold": 0.04, "density": 2.4,
        "emotePx": 150, "res": "1920x1080", "fps": 60, "quality": 26,
        "inFrac": 0.45, "easing": "overshoot", "direction": None,
        "outline": 0, "outlineColor": "#000000", "shadow": False, "fmt": "webm",
    },
    "Slow flood": {
        "style": "rain", "duration": 2.0, "hold": 0.16, "density": 2.6,
        "emotePx": 180, "res": "1920x1080", "fps": 30, "quality": 28,
        "inFrac": 0.55, "easing": "smooth", "direction": "down",
        "outline": 0, "outlineColor": "#000000", "shadow": True, "fmt": "webm",
    },
    "Curtain wipe": {
        "style": "wipe", "duration": 1.4, "hold": 0.1, "density": 2.2,
        "emotePx": 170, "res": "1920x1080", "fps": 60, "quality": 24,
        "inFrac": 0.5, "easing": "smooth", "direction": "right",
        "outline": 3, "outlineColor": "#ffffff", "shadow": False, "fmt": "webm",
    },
    "Chaos bounce": {
        "style": "swarm", "duration": 1.2, "hold": 0.06, "density": 3.0,
        "emotePx": 140, "res": "1920x1080", "fps": 60, "quality": 28,
        "inFrac": 0.4, "easing": "bounce", "direction": None,
        "outline": 2, "outlineColor": "#000000", "shadow": True, "fmt": "webm",
    },
}


class Api:
    """Methods here are callable from JS as window.pywebview.api.<name>(...)."""

    def __init__(self):
        self.workdir = tempfile.mkdtemp(prefix="stinger_app_")
        self.presets_path = os.path.join(config_dir(), "presets.json")
        self.batch_files = []
        engine.FFMPEG = locate_ffmpeg()

    # ---------------- capability probes ----------------
    def styles(self):
        return engine.STYLES

    def options(self):
        """Everything the UI needs to build its selects."""
        return {
            "styles": engine.STYLES,
            "directions": engine.DIRECTIONS,
            "directional": engine.DIRECTIONAL,
            "easings": engine.EASINGS,
            "formats": engine.FORMATS,
            "ext": engine.EXT,
        }

    def ffmpeg_ok(self):
        """Quick check the render backend is usable; surfaced in the UI."""
        import subprocess
        try:
            subprocess.run([engine.FFMPEG, "-version"],
                           capture_output=True, check=True,
                           **engine.sp_kwargs())
            return {"ok": True, "path": engine.FFMPEG}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------------- uploads ----------------
    def _save_emotes(self, emotes):
        """emotes: list of {name, dataUrl}. Returns list of file paths."""
        emdir = os.path.join(self.workdir, "emotes")
        shutil.rmtree(emdir, ignore_errors=True)
        os.makedirs(emdir, exist_ok=True)
        paths = []
        for i, em in enumerate(emotes):
            data = em["dataUrl"].split(",", 1)[1]
            raw = base64.b64decode(data)
            # keep extension from name if present, default png
            ext = os.path.splitext(em.get("name", ""))[1] or ".png"
            p = os.path.join(emdir, f"emote_{i:03d}{ext}")
            with open(p, "wb") as f:
                f.write(raw)
            paths.append(p)
        return paths

    def _save_audio(self, audio):
        """audio: {name, dataUrl} or None. Returns a path or None."""
        if not audio or not audio.get("dataUrl"):
            return None
        data = audio["dataUrl"].split(",", 1)[1]
        ext = os.path.splitext(audio.get("name", ""))[1] or ".mp3"
        p = os.path.join(self.workdir, f"audio{ext}")
        with open(p, "wb") as f:
            f.write(base64.b64decode(data))
        return p

    def _save_logo(self, logo):
        """logo: {name, dataUrl} or None. Returns a path or None."""
        if not logo or not logo.get("dataUrl"):
            return None
        data = logo["dataUrl"].split(",", 1)[1]
        ext = os.path.splitext(logo.get("name", ""))[1] or ".png"
        p = os.path.join(self.workdir, f"logo{ext}")
        with open(p, "wb") as f:
            f.write(base64.b64decode(data))
        return p

    # ---------------- rendering ----------------
    def _build_args(self, payload, paths, audio_path, logo_path=None):
        w, h = (int(x) for x in payload.get("res", "1920x1080").split("x"))
        seed = payload.get("seed")
        try:
            seed = int(seed) if seed not in (None, "") else None
        except (TypeError, ValueError):
            seed = None
        return dict(
            images=paths,
            width=w, height=h,
            fps=int(payload.get("fps", 30)),
            duration=float(payload.get("duration", 1.2)),
            hold=float(payload.get("hold", 0.08)),
            density=float(payload.get("density", 2.0)),
            emote_px=int(payload.get("emotePx", 160)),
            seed=seed,
            bg_test=False,
            in_frac=float(payload.get("inFrac", 0.5)),
            direction=payload.get("direction") or None,
            easing=payload.get("easing", "smooth"),
            quality=int(payload.get("quality", 28)),
            audio=audio_path,
            fmt=payload.get("fmt", "webm"),
            outline=int(payload.get("outline", 0) or 0),
            outline_color=payload.get("outlineColor", "#000000"),
            shadow=bool(payload.get("shadow", False)),
            logo=logo_path,
            logo_size=float(payload.get("logoSize", 22.0)),
            logo_anchor=payload.get("logoAnchor", "mc"),
            logo_dx=float(payload.get("logoDx", 0.0)),
            logo_dy=float(payload.get("logoDy", 0.0)),
            logo_in=payload.get("logoIn", "pop"),
            logo_out=payload.get("logoOut") or None,
        )

    def generate(self, payload):
        """Render a stinger. payload carries emotes + settings from the UI.

        Returns {ok, out, transition_ms, frames, count, seed} or {ok:False, error}.
        """
        try:
            emotes = payload.get("emotes", [])
            if not emotes:
                return {"ok": False, "error": "Add at least one emote first."}

            paths = self._save_emotes(emotes)
            audio_path = self._save_audio(payload.get("audio"))
            logo_path = self._save_logo(payload.get("logo"))
            args = self._build_args(payload, paths, audio_path, logo_path)

            fmt = args["fmt"]
            out = os.path.join(self.workdir, "stinger" + engine.EXT.get(fmt, ".webm"))

            def on_progress(stage, done, total):
                # push a progress event into the UI; ignore if window not ready
                try:
                    pct = int(done * 100 / total) if total else 0
                    window.evaluate_js(
                        f"window.__stingerProgress && window.__stingerProgress('{stage}',{pct})"
                    )
                except Exception:
                    pass

            r = engine.build(out=out, style=payload.get("style", "rain"),
                             progress=on_progress, **args)
            r["ok"] = True
            return r
        except Exception as e:
            return {"ok": False, "error": str(e),
                    "trace": traceback.format_exc()}

    def generate_all(self, payload):
        """Render the current settings once per style into the workdir.

        Emotes are uploaded and written once, then reused for all 12 renders.
        """
        try:
            emotes = payload.get("emotes", [])
            if not emotes:
                return {"ok": False, "error": "Add at least one emote first."}

            paths = self._save_emotes(emotes)
            audio_path = self._save_audio(payload.get("audio"))
            logo_path = self._save_logo(payload.get("logo"))
            args = self._build_args(payload, paths, audio_path, logo_path)
            fmt = args["fmt"]
            ext = engine.EXT.get(fmt, ".webm")

            # pin the seed once: otherwise an unset seed would be re-rolled for
            # every style and the 12 files wouldn't share a layout
            if args["seed"] is None:
                import random
                args["seed"] = random.randrange(2 ** 31)

            outdir = os.path.join(self.workdir, "batch")
            shutil.rmtree(outdir, ignore_errors=True)
            os.makedirs(outdir, exist_ok=True)

            styles = engine.STYLES
            total = len(styles)
            results = []
            self.batch_files = []

            for i, style in enumerate(styles):
                def on_progress(stage, done, tot, _i=i, _s=style):
                    try:
                        pct = int(done * 100 / tot) if tot else 0
                        window.evaluate_js(
                            "window.__stingerBatch && window.__stingerBatch("
                            f"{_i + 1},{total},'{_s}','{stage}',{pct})"
                        )
                    except Exception:
                        pass

                out = os.path.join(outdir, f"stinger_{style}{ext}")
                r = engine.build(out=out, style=style, progress=on_progress, **args)
                results.append({"style": style, "out": out,
                                "transition_ms": r["transition_ms"]})
                self.batch_files.append(out)

            return {"ok": True, "files": results, "count": len(results),
                    "seed": args["seed"], "format": fmt}
        except Exception as e:
            return {"ok": False, "error": str(e),
                    "trace": traceback.format_exc()}

    # ---------------- saving ----------------
    def save_as(self, src_path, fmt="webm"):
        """Open a native Save dialog and copy the rendered file there."""
        ext = engine.EXT.get(fmt, ".webm")
        filters = {
            ".webm": ("WebM video (*.webm)",),
            ".mov": ("QuickTime video (*.mov)",),
            ".zip": ("Zip archive (*.zip)",),
        }[ext]
        try:
            result = window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename="stinger" + ext,
                file_types=filters,
            )
            if not result:
                return {"ok": False, "cancelled": True}
            dest = result if isinstance(result, str) else result[0]
            if not dest.lower().endswith(ext):
                dest += ext
            shutil.copyfile(src_path, dest)
            return {"ok": True, "dest": dest}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def save_all(self):
        """Pick a folder and copy every file from the last batch render into it."""
        try:
            if not self.batch_files:
                return {"ok": False, "error": "Nothing to save — run a batch first."}
            result = window.create_file_dialog(webview.FOLDER_DIALOG)
            if not result:
                return {"ok": False, "cancelled": True}
            folder = result if isinstance(result, str) else result[0]
            saved = []
            for src in self.batch_files:
                if not os.path.isfile(src):
                    continue
                dest = os.path.join(folder, os.path.basename(src))
                shutil.copyfile(src, dest)
                saved.append(dest)
            return {"ok": True, "folder": folder, "saved": len(saved)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------------- presets ----------------
    def _read_presets(self):
        try:
            with open(self.presets_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, ValueError, OSError):
            return {}

    def _write_presets(self, data):
        with open(self.presets_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def list_presets(self):
        user = self._read_presets()
        merged = []
        for name, cfg in BUILTIN_PRESETS.items():
            merged.append({"name": name, "settings": cfg, "builtin": True})
        for name in sorted(user):
            merged.append({"name": name, "settings": user[name], "builtin": False})
        return {"ok": True, "presets": merged, "path": self.presets_path}

    def save_preset(self, name, settings):
        name = (name or "").strip()
        if not name:
            return {"ok": False, "error": "Give the preset a name."}
        if name in BUILTIN_PRESETS:
            return {"ok": False, "error": "That name belongs to a built-in preset."}
        try:
            data = self._read_presets()
            data[name] = settings
            self._write_presets(data)
            return self.list_presets()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def delete_preset(self, name):
        if name in BUILTIN_PRESETS:
            return {"ok": False, "error": "Built-in presets can't be deleted."}
        try:
            data = self._read_presets()
            data.pop(name, None)
            self._write_presets(data)
            return self.list_presets()
        except Exception as e:
            return {"ok": False, "error": str(e)}


window = None


def main():
    global window
    api = Api()
    window = webview.create_window(
        "Stinger Studio",
        url=resource_path("ui.html"),
        js_api=api,
        width=1180, height=820,
        min_size=(900, 680),
        background_color="#0d0f14",
    )
    webview.start()


if __name__ == "__main__":
    # Belt and suspenders: canonical placement, must be the first call.
    multiprocessing.freeze_support()
    main()
