"""Draws the MTAI logo (the purple conic tile from ui/style.css .logo) as packaging/mtai.ico.
Run: python packaging/make_icon.py   (needs Pillow)"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
S = 1024                                        # drawn big, scaled down for each icon size

# conic-gradient(from 200deg, deep, accent2, accent2-l, accent, deep)
STOPS = ["#7c3aed", "#c084fc", "#f0abfc", "#8b5cf6", "#7c3aed"]
BG = (7, 6, 11)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def conic(size):
    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    cols = [rgb(c) for c in STOPS]
    r = size                                     # pie slices bigger than the tile, so corners are covered
    for deg in range(720):
        a = deg / 2
        t = a / 360 * (len(cols) - 1)
        i = min(int(t), len(cols) - 2)
        c = mix(cols[i], cols[i + 1], t - i)
        start = 200 + a - 90                     # CSS 0deg is up, PIL 0deg is right
        d.pieslice([size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r], start, start + 0.6, fill=c)
    return img


def tile():
    pad = int(S * 0.04)
    box = S - 2 * pad
    rad = int(box * 9 / 26)                      # border-radius 9px on a 26px tile
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle([pad, pad, S - pad, S - pad], rad, fill=(139, 92, 246, 150))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(S * 0.02)))

    grad = conic(box).convert("RGBA")
    mask = Image.new("L", (box, box), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, box - 1, box - 1], rad, fill=255)
    img.paste(grad, (pad, pad), mask)

    hi = Image.new("RGBA", (S, S), (0, 0, 0, 0))   # inset 0 1px 0 rgba(255,255,255,.4)
    ImageDraw.Draw(hi).rounded_rectangle([pad, pad, S - pad, S - pad], rad, outline=(255, 255, 255, 90),
                                         width=max(2, S // 120))
    img.alpha_composite(hi)

    inset = int(box * 7 / 26)                    # .logo::after inset 7px, radius 4px, opacity .85
    ir = int(box * 4 / 26)
    inner = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(inner).rounded_rectangle([pad + inset, pad + inset, S - pad - inset, S - pad - inset], ir,
                                            fill=BG + (217,))
    img.alpha_composite(inner)
    return img


if __name__ == "__main__":
    big = tile()
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    big.resize((256, 256), Image.LANCZOS).save(HERE / "mtai.ico", sizes=sizes)
    big.resize((512, 512), Image.LANCZOS).save(HERE / "mtai.png")
    print("wrote", HERE / "mtai.ico", "and", HERE / "mtai.png")
