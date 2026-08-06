#!/usr/bin/env python3
"""
fetch_ffmpeg.py — download a static Windows ffmpeg and place ffmpeg.exe in ./bin

Used once by build.bat. Pulls BtbN's "latest" Windows build (a .zip, so Python's
stdlib can extract it — no 7-Zip needed) and copies out just ffmpeg.exe.
"""
import io
import os
import sys
import urllib.request
import zipfile

URL = ("https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
       "ffmpeg-master-latest-win64-gpl.zip")
OUT_DIR = "bin"
OUT_EXE = os.path.join(OUT_DIR, "ffmpeg.exe")


def main():
    if os.path.isfile(OUT_EXE):
        print(f"[OK] {OUT_EXE} already exists.")
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"Downloading: {URL}")
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "stinger-build"})
        with urllib.request.urlopen(req) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            buf = io.BytesIO()
            read = 0
            chunk = 1 << 16
            while True:
                data = resp.read(chunk)
                if not data:
                    break
                buf.write(data)
                read += len(data)
                if total:
                    pct = read * 100 // total
                    sys.stdout.write(f"\r  {pct}%  ({read // (1<<20)}MB / {total // (1<<20)}MB)")
                    sys.stdout.flush()
        print()
    except Exception as e:
        print(f"[X] Download failed: {e}")
        print("    Check your connection, or manually place an ffmpeg.exe in a 'bin' folder.")
        return 1

    # find ffmpeg.exe inside the zip (it's under <build>/bin/ffmpeg.exe)
    try:
        zf = zipfile.ZipFile(buf)
        member = None
        for name in zf.namelist():
            if name.replace("\\", "/").endswith("/bin/ffmpeg.exe"):
                member = name
                break
        if not member:
            print("[X] ffmpeg.exe not found inside the archive.")
            return 1
        with zf.open(member) as src, open(OUT_EXE, "wb") as dst:
            dst.write(src.read())
        print(f"[OK] Extracted ffmpeg.exe -> {OUT_EXE} ({os.path.getsize(OUT_EXE)//(1<<20)}MB)")
    except Exception as e:
        print(f"[X] Extraction failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
