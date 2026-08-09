#!/usr/bin/env python3
"""
make_icon.py — turn S.png into the icon.ico that gets stamped on the exe.

Windows picks a different size out of the .ico depending on where it's showing
the app, so a single 256px image looks rough in the taskbar. This writes all
seven sizes into one file.

Run it again whenever S.png changes:  python make_icon.py
"""
import os
import sys

from PIL import Image

SRC = "S.png"
OUT = "icon.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]
# artwork usually has empty space around it; trim that off and leave a small
# even margin, so the icon fills more of the square at 16 and 32 px
MARGIN = 0.04


def build(src=SRC, out=OUT):
    here = os.path.dirname(os.path.abspath(__file__))
    src_path = src if os.path.isabs(src) else os.path.join(here, src)
    out_path = out if os.path.isabs(out) else os.path.join(here, out)

    im = Image.open(src_path).convert("RGBA")

    box = im.split()[3].getbbox()
    if box:
        im = im.crop(box)

    side = max(im.size)
    pad = int(round(side * MARGIN))
    canvas = Image.new("RGBA", (side + pad * 2, side + pad * 2), (0, 0, 0, 0))
    canvas.paste(im, ((canvas.width - im.width) // 2,
                      (canvas.height - im.height) // 2))

    big = canvas.resize((SIZES[-1], SIZES[-1]), Image.LANCZOS)
    big.save(out_path, format="ICO", sizes=[(s, s) for s in SIZES])
    return out_path


if __name__ == "__main__":
    p = build(*sys.argv[1:3])
    print(f"wrote {p}")
