#!/usr/bin/env python3
"""
make_icon.py — turn S.png into the icon.ico that gets stamped on the exe.

Windows picks a different size out of the .ico depending on where it's showing
the app, so a single 256px image looks rough in the taskbar. This writes all
seven sizes into one file.

The .ico is written by hand rather than with Pillow's ICO saver, because that
saver stores every size as PNG. Windows only reads PNG icons at 256px. At the
smaller sizes the shell wants an old style BMP, and when it doesn't find one it
falls back to the generic exe icon in Explorer, even though the taskbar looks
fine. So: BMP below 256, PNG at 256.

Run it again whenever S.png changes:  python make_icon.py
"""
import io
import os
import struct
import sys

from PIL import Image

SRC = "S.png"
OUT = "icon.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]
# artwork usually has empty space around it; trim that off and leave a small
# even margin, so the icon fills more of the square at 16 and 32 px
MARGIN = 0.04
# above this, Windows expects PNG and a BMP would balloon the file
PNG_FROM = 256


def _bmp_entry(im):
    """One icon image as a BITMAPINFOHEADER, bottom up BGRA, plus an AND mask."""
    w, h = im.size
    stride = w * 4
    raw = im.tobytes("raw", "BGRA")
    rows = [raw[y * stride:(y + 1) * stride] for y in range(h)]
    xor = b"".join(reversed(rows))          # DIBs are stored bottom row first

    # 1 bit per pixel mask, rows padded to 4 bytes. 1 means transparent.
    alpha = im.split()[3].tobytes()
    mask_stride = ((w + 31) // 32) * 4
    mask_rows = []
    for y in range(h):
        bits = bytearray(mask_stride)
        base = y * w
        for x in range(w):
            if alpha[base + x] == 0:
                bits[x // 8] |= 0x80 >> (x % 8)
        mask_rows.append(bytes(bits))
    and_mask = b"".join(reversed(mask_rows))

    header = struct.pack(
        "<IiiHHIIiiII",
        40,                 # header size
        w, h * 2,           # height counts the colour rows and the mask rows
        1, 32,              # planes, bits per pixel
        0,                  # BI_RGB, no compression
        len(xor) + len(and_mask),
        0, 0, 0, 0,
    )
    return header + xor + and_mask


def _png_entry(im):
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


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

    blobs = []
    for s in SIZES:
        frame = canvas.resize((s, s), Image.LANCZOS)
        blobs.append((s, _png_entry(frame) if s >= PNG_FROM
                      else _bmp_entry(frame)))

    offset = 6 + 16 * len(blobs)
    head = struct.pack("<HHH", 0, 1, len(blobs))
    entries, data = b"", b""
    for s, blob in blobs:
        entries += struct.pack(
            "<BBBBHHII",
            0 if s >= 256 else s,       # 0 means 256 in the directory
            0 if s >= 256 else s,
            0, 0,                       # palette count, reserved
            1, 32,                      # planes, bits per pixel
            len(blob), offset,
        )
        data += blob
        offset += len(blob)

    with open(out_path, "wb") as f:
        f.write(head + entries + data)
    return out_path


if __name__ == "__main__":
    p = build(*sys.argv[1:3])
    print(f"wrote {p}")
