#!/usr/bin/env python3
"""
app.py — Stinger Studio desktop app.

Opens a native window wrapping the HTML UI. The UI calls into the `Api` class
below via pywebview's JS bridge. The bridge saves uploaded images to a temp
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
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
import urllib.request
import webbrowser

# CRITICAL on Windows / frozen exe: must run before anything spawns a process.
# Without this, each render worker re-launches the whole app window (fork bomb).
multiprocessing.freeze_support()

import webview

import engine

# Bump this when you cut a release. The app compares it against the newest tag
# on the Releases page and shows a banner when there is a newer one.
APP_VERSION = "1.0.0"

REPO = "TheITStreamer/Stinger-Studio"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_LIST = f"https://api.github.com/repos/{REPO}/releases?per_page=20"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
# open_url only ever opens links on this host, so a bad reply from the API
# can't be used to send someone somewhere else
ALLOWED_URL_PREFIX = f"https://github.com/{REPO}"


def parse_version(s):
    """'v1.2.3' -> (1, 2, 3). Stops at the first part that isn't a number, so
    tags like 1.2.0-beta compare as 1.2.0."""
    s = (s or "").strip().lstrip("vV")
    parts = []
    for chunk in re.split(r"[.\-+_]", s):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            break
    return tuple(parts) or (0,)


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
        "volume": 100, "fadeOut": False,
    },
    "Slow flood": {
        "style": "rain", "duration": 2.0, "hold": 0.16, "density": 2.6,
        "emotePx": 180, "res": "1920x1080", "fps": 30, "quality": 28,
        "inFrac": 0.55, "easing": "smooth", "direction": "down",
        "outline": 0, "outlineColor": "#000000", "shadow": True, "fmt": "webm",
        "volume": 100, "fadeOut": True,
    },
    "Curtain wipe": {
        "style": "wipe", "duration": 1.4, "hold": 0.1, "density": 2.2,
        "emotePx": 170, "res": "1920x1080", "fps": 60, "quality": 24,
        "inFrac": 0.5, "easing": "smooth", "direction": "right",
        "outline": 3, "outlineColor": "#ffffff", "shadow": False, "fmt": "webm",
        "volume": 100, "fadeOut": True,
    },
    "Chaos bounce": {
        "style": "swarm", "duration": 1.2, "hold": 0.06, "density": 3.0,
        "emotePx": 140, "res": "1920x1080", "fps": 60, "quality": 28,
        "inFrac": 0.4, "easing": "bounce", "direction": None,
        "outline": 2, "outlineColor": "#000000", "shadow": True, "fmt": "webm",
        "volume": 100, "fadeOut": False,
    },
    "Popcorn pop": {
        "style": "popcorn", "duration": 1.1, "hold": 0.08, "density": 2.6,
        "emotePx": 160, "res": "1920x1080", "fps": 60, "quality": 26,
        "inFrac": 0.5, "easing": "smooth", "direction": None,
        "outline": 0, "outlineColor": "#000000", "shadow": False, "fmt": "webm",
        "volume": 100, "fadeOut": True,
    },
    "Glass break": {
        "style": "shatter", "duration": 1.6, "hold": 0.1, "density": 2.4,
        "emotePx": 170, "res": "1920x1080", "fps": 60, "quality": 26,
        "inFrac": 0.45, "easing": "smooth", "direction": None,
        "outline": 0, "outlineColor": "#000000", "shadow": True, "fmt": "webm",
        "volume": 100, "fadeOut": False,
    },
}


class Api:
    """Methods here are callable from JS as window.pywebview.api.<name>(...)."""

    def __init__(self):
        self.workdir = tempfile.mkdtemp(prefix="stinger_app_")
        self.presets_path = os.path.join(config_dir(), "presets.json")
        self.settings_path = os.path.join(config_dir(), "settings.json")
        self.batch_files = []
        # content hash -> file on disk, so an image crosses the bridge once
        self.assets = {}
        self.assetdir = os.path.join(self.workdir, "emotes")
        os.makedirs(self.assetdir, exist_ok=True)
        engine.FFMPEG = locate_ffmpeg()

    # ---------------- version / updates ----------------
    def version(self):
        return {"version": APP_VERSION, "releases": RELEASES_PAGE}

    @staticmethod
    def _get_json(url):
        req = urllib.request.Request(url, headers={
            "User-Agent": f"StingerStudio/{APP_VERSION}",
            "Accept": "application/vnd.github+json",
        })
        with urllib.request.urlopen(req, timeout=6) as r:
            return json.load(r)

    def check_update(self):
        """Ask GitHub for the newest release and say whether it beats this one.

        Never raises and never blocks the UI for long. Anything that goes wrong
        comes back as {"ok": False} with a plain reason, so the banner stays
        hidden but the version chip can still tell you what happened."""
        data = None
        why = ""
        try:
            data = self._get_json(RELEASES_API)
        except Exception as e:
            why = str(e)

        # /releases/latest ignores pre-releases and drafts, so a test release
        # marked pre-release looks exactly like no release at all. Fall back to
        # the full list and take the highest version number in it.
        if not data:
            try:
                items = [i for i in (self._get_json(RELEASES_LIST) or [])
                         if not i.get("draft")]
                if items:
                    data = max(items, key=lambda i: parse_version(
                        i.get("tag_name") or ""))
                    why = ""
            except Exception as e:
                why = why or str(e)

        if not data:
            if "404" in why:
                why = ("No releases found. A private repo, or a release still "
                       "saved as a draft, both look like this.")
            return {"ok": False, "error": why or "No releases found."}

        tag = (data.get("tag_name") or "").strip()
        if not tag:
            return {"ok": False, "error": "That release has no tag."}
        url = data.get("html_url") or RELEASES_PAGE
        if not url.startswith(ALLOWED_URL_PREFIX):
            url = RELEASES_PAGE
        return {
            "ok": True,
            "update": parse_version(tag) > parse_version(APP_VERSION),
            "current": APP_VERSION,
            "latest": tag.lstrip("vV"),
            "tag": tag,
            "url": url,
            "prerelease": bool(data.get("prerelease")),
            "skipped": self._read_settings().get("skipUpdate") == tag,
        }

    def skip_update(self, tag):
        """Remember that this version was dismissed so it stops nagging."""
        try:
            data = self._read_settings()
            data["skipUpdate"] = tag
            self._write_settings(data)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_url(self, url):
        """Open a link in the real browser, not inside the app window."""
        try:
            if not str(url).startswith(ALLOWED_URL_PREFIX):
                return {"ok": False, "error": "That link is not allowed."}
            webbrowser.open(url)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

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
    # Files cross the bridge once and are then addressed by content hash.
    # Re-rendering with the same images sends no image data at all.
    def have_hashes(self, hashes):
        """Tell the UI which of these it still needs to upload."""
        missing = [h for h in (hashes or []) if h and h not in self.assets]
        return {"ok": True, "missing": missing}

    def sync_assets(self, items):
        """items: [{hash, name, dataUrl}]. Only new hashes need a dataUrl."""
        try:
            for it in items or []:
                h = it.get("hash")
                if not h or h in self.assets:
                    continue
                data_url = it.get("dataUrl")
                if not data_url:
                    continue
                raw = base64.b64decode(data_url.split(",", 1)[1])
                ext = os.path.splitext(it.get("name", ""))[1] or ".bin"
                p = os.path.join(self.assetdir, h[:32] + ext)
                with open(p, "wb") as f:
                    f.write(raw)
                self.assets[h] = p
            return {"ok": True, "have": len(self.assets)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _missing(self, hashes):
        return [h for h in hashes if h and h not in self.assets]

    def _resolve(self, payload):
        """Turn the payload's hash lists into file paths.

        Returns (paths, audio_path, logo_path) or raises KeyError listing what
        the UI has to send again."""
        em_hashes = payload.get("emoteHashes") or []
        audio_h = payload.get("audioHash") or None
        logo_h = payload.get("logoHash") or None
        miss = self._missing(list(em_hashes) + [audio_h, logo_h])
        if miss:
            raise KeyError(miss)
        return ([self.assets[h] for h in em_hashes],
                self.assets.get(audio_h) if audio_h else None,
                self.assets.get(logo_h) if logo_h else None)

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
            direction_out=payload.get("directionOut") or None,
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
            size_variety=float(payload.get("sizeVariety", 0) or 0) / 100.0,
            weights=payload.get("weights") or None,
            volume=float(payload.get("volume", 100) or 0) / 100.0,
            fade_out=bool(payload.get("fadeOut", False)),
        )

    def generate(self, payload):
        """Render a stinger. payload carries images + settings from the UI.

        Returns {ok, out, transition_ms, frames, count, seed} or {ok:False, error}.
        """
        try:
            if not payload.get("emoteHashes"):
                return {"ok": False, "error": "Add at least one image first."}
            try:
                paths, audio_path, logo_path = self._resolve(payload)
            except KeyError as miss:
                return {"ok": False, "missing": miss.args[0],
                        "error": "Image data went missing — sending it again."}
            args = self._build_args(payload, paths, audio_path, logo_path)

            fmt = args["fmt"]
            if fmt == "png":
                args["audio"] = None
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
            r["audio_dropped"] = bool(audio_path) and fmt == "png"
            return r
        except Exception as e:
            return {"ok": False, "error": str(e),
                    "trace": traceback.format_exc()}

    def generate_all(self, payload):
        """Render the current settings once per style into the workdir.

        Images are uploaded and written once, then reused for all 12 renders.
        """
        try:
            if not payload.get("emoteHashes"):
                return {"ok": False, "error": "Add at least one image first."}
            try:
                paths, audio_path, logo_path = self._resolve(payload)
            except KeyError as miss:
                return {"ok": False, "missing": miss.args[0],
                        "error": "Image data went missing — sending it again."}
            args = self._build_args(payload, paths, audio_path, logo_path)
            fmt = args["fmt"]
            if fmt == "png":
                args["audio"] = None
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
                    "seed": args["seed"], "format": fmt,
                    "audio_dropped": bool(audio_path) and fmt == "png"}
        except Exception as e:
            return {"ok": False, "error": str(e),
                    "trace": traceback.format_exc()}

    # ---------------- saving ----------------
    def _read_settings(self):
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, ValueError, OSError):
            return {}

    def _write_settings(self, data):
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def _last_dir(self):
        d = self._read_settings().get("lastSaveDir")
        return d if d and os.path.isdir(d) else None

    def _remember_dir(self, path):
        d = path if os.path.isdir(path) else os.path.dirname(path)
        if d and os.path.isdir(d):
            data = self._read_settings()
            data["lastSaveDir"] = d
            self._write_settings(data)

    def open_folder(self, path):
        """Show a saved file's folder in the system file manager."""
        try:
            d = path if os.path.isdir(path) else os.path.dirname(path)
            if not d or not os.path.isdir(d):
                return {"ok": False, "error": "Folder not found."}
            if os.name == "nt":
                os.startfile(d)                             # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", d])
            else:
                subprocess.Popen(["xdg-open", d])
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def save_as(self, src_path, fmt="webm"):
        """Open a native Save dialog and copy the rendered file there."""
        ext = engine.EXT.get(fmt, ".webm")
        filters = {
            ".webm": ("WebM video (*.webm)",),
            ".mov": ("QuickTime video (*.mov)",),
            ".zip": ("Zip archive (*.zip)",),
        }[ext]
        try:
            kw = {}
            last = self._last_dir()
            if last:
                kw["directory"] = last
            result = window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename="stinger" + ext,
                file_types=filters,
                **kw
            )
            if not result:
                return {"ok": False, "cancelled": True}
            dest = result if isinstance(result, str) else result[0]
            if not dest.lower().endswith(ext):
                dest += ext
            shutil.copyfile(src_path, dest)
            self._remember_dir(dest)
            return {"ok": True, "dest": dest, "folder": os.path.dirname(dest)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def save_all(self):
        """Pick a folder and copy every file from the last batch render into it."""
        try:
            if not self.batch_files:
                return {"ok": False, "error": "Nothing to save — run a batch first."}
            kw = {}
            last = self._last_dir()
            if last:
                kw["directory"] = last
            result = window.create_file_dialog(webview.FOLDER_DIALOG, **kw)
            if not result:
                return {"ok": False, "cancelled": True}
            folder = result if isinstance(result, str) else result[0]
            self._remember_dir(folder)
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
        f"Stinger Studio {APP_VERSION}",
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
