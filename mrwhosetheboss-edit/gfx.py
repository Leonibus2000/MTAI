"""Procedural tech stickers, backgrounds and text, all monochrome float arrays in [0,1]."""
import math
import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W = 576
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, f"{name}-latin-400-normal.ttf"), size)


# ---------------------------------------------------------------- stickers
def _finish(mask, detail, fill=0.72, ring=10):
    """mask/detail: uint8 L images. Returns (lum, alpha) with white die-cut outline."""
    m = np.asarray(mask, np.float32) / 255
    d = np.asarray(detail, np.float32) / 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ring * 2 + 1, ring * 2 + 1))
    outer = cv2.dilate(m, k)
    shade = np.linspace(1.08, 0.82, m.shape[0])[:, None]
    lum = np.where(m > 0.5, fill * shade * (1 - 0.75 * d), 1.0)
    lum = lum * outer + (1 - outer)
    alpha = outer
    s = m.shape[0] // 2
    lum = cv2.resize(lum, (s, s), interpolation=cv2.INTER_AREA)
    alpha = cv2.resize(alpha, (s, s), interpolation=cv2.INTER_AREA)
    return np.clip(lum, 0, 1), np.clip(alpha, 0, 1)


def sticker(kind, size=220):
    S = size * 2
    mask = Image.new("L", (S, S), 0)
    det = Image.new("L", (S, S), 0)
    dm, dd = ImageDraw.Draw(mask), ImageDraw.Draw(det)
    c = S / 2
    if kind == "phone":
        w, h = S * 0.42, S * 0.82
        box = (c - w / 2, c - h / 2, c + w / 2, c + h / 2)
        dm.rounded_rectangle(box, radius=w * 0.18, fill=255)
        dd.rounded_rectangle((box[0] + 14, box[1] + 14, box[2] - 14, box[3] - 14), radius=w * 0.14, fill=140)
        dd.ellipse((c - 10, box[1] + 26, c + 10, box[1] + 46), fill=255)
    elif kind == "phone_back":
        w, h = S * 0.42, S * 0.82
        box = (c - w / 2, c - h / 2, c + w / 2, c + h / 2)
        dm.rounded_rectangle(box, radius=w * 0.18, fill=255)
        bx, by = box[0] + 18, box[1] + 18
        dd.rounded_rectangle((bx, by, bx + w * 0.55, by + w * 0.55), radius=30, fill=110)
        r = w * 0.11
        for ox, oy in [(0.17, 0.17), (0.38, 0.17), (0.17, 0.38)]:
            x, y = bx + w * ox, by + w * oy
            dd.ellipse((x - r, y - r, x + r, y + r), fill=255)
        dd.ellipse((c - 26, c + 40, c + 26, c + 92), outline=150, width=8)
    elif kind == "bolt":
        pts = [(0.58, 0.08), (0.24, 0.56), (0.47, 0.56), (0.36, 0.92), (0.78, 0.4), (0.54, 0.4), (0.66, 0.08)]
        dm.polygon([(x * S, y * S) for x, y in pts], fill=255)
        dd.line([(0.5 * S, 0.2 * S), (0.36 * S, 0.47 * S)], fill=90, width=8)
    elif kind == "chip":
        a = S * 0.26
        for i in range(5):
            t = c - a * 0.8 + i * a * 0.4
            for (x0, y0, x1, y1) in [(t - 9, c - a - 40, t + 9, c - a), (t - 9, c + a, t + 9, c + a + 40),
                                     (c - a - 40, t - 9, c - a, t + 9), (c + a, t - 9, c + a + 40, t + 9)]:
                dm.rectangle((x0, y0, x1, y1), fill=255)
        dm.rounded_rectangle((c - a, c - a, c + a, c + a), radius=20, fill=255)
        dd.rounded_rectangle((c - a * 0.6, c - a * 0.6, c + a * 0.6, c + a * 0.6), radius=12, outline=200, width=10)
        f = font("anton", int(a * 0.7))
        dd.text((c, c), "AI", font=f, fill=200, anchor="mm")
    elif kind == "battery":
        w, h = S * 0.36, S * 0.7
        box = (c - w / 2, c - h / 2 + 20, c + w / 2, c + h / 2 + 20)
        dm.rounded_rectangle(box, radius=24, fill=255)
        dm.rectangle((c - w * 0.18, box[1] - 30, c + w * 0.18, box[1] + 4), fill=255)
        for i in range(3):
            y = box[3] - 24 - (i + 1) * h * 0.26
            dd.rectangle((box[0] + 20, y, box[2] - 20, y + h * 0.2), fill=150)
    elif kind == "lens":
        r = S * 0.44
        dm.ellipse((c - r, c - r, c + r, c + r), fill=255)
        for i, rr in enumerate([0.8, 0.6, 0.4]):
            dd.ellipse((c - r * rr, c - r * rr, c + r * rr, c + r * rr), outline=170, width=14)
        for i in range(3):
            y = c - r * 0.35 + i * r * 0.28
            dd.rectangle((c - r * 0.55, y, c + r * 0.55, y + r * 0.14), fill=255)
        dd.rectangle((c - r * 0.07, c - r * 0.6, c + r * 0.07, c + r * 0.5), fill=255)
    elif kind == "wifi":
        for i, rr in enumerate([0.42, 0.3, 0.18]):
            box = (c - S * rr, c - S * rr + 60, c + S * rr, c + S * rr + 60)
            dm.arc(box, 220, 320, fill=255, width=34)
        dm.ellipse((c - 26, c + 120, c + 26, c + 172), fill=255)
    elif kind == "cpu_badge":  # stand-in for the 'gem' sticker under the pixel badge
        pts = [(0.5, 0.1), (0.85, 0.45), (0.78, 0.86), (0.22, 0.86), (0.15, 0.45)]
        dm.polygon([(x * S, y * S) for x, y in pts], fill=255)
        dd.line([(0.5 * S, 0.12 * S), (0.5 * S, 0.84 * S)], fill=80, width=6)
    return _finish(mask, det)


def striped_phone(h=420):
    """Big striped phone silhouette: tech stand-in for the striped rook graphics."""
    S = h * 2
    w = int(S * 0.5)
    img = Image.new("L", (w + 40, S + 40), 0)
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((20, 20, w + 20, S + 20), radius=w * 0.2, fill=255)
    stripes = Image.new("L", img.size, 0)
    ds = ImageDraw.Draw(stripes)
    for y in range(-w, S + w, 70):
        ds.polygon([(0, y), (w + 40, y - 60), (w + 40, y - 30), (0, y + 30)], fill=255)
    m = np.asarray(m, np.float32) / 255
    st = np.asarray(stripes, np.float32) / 255
    inner = cv2.erode(m, np.ones((36, 36)))
    lum = np.where(inner > 0.5, 0.15 + 0.7 * st, 0.78) * m
    lum = cv2.resize(lum, (img.size[0] // 2, img.size[1] // 2), interpolation=cv2.INTER_AREA)
    a = cv2.resize(m, (img.size[0] // 2, img.size[1] // 2), interpolation=cv2.INTER_AREA)
    return lum, a


def text_layer(lines, fontname, size, spacing=0.9, fill=1.0, stroke=0):
    f = font(fontname, size)
    widths = [f.getbbox(t)[2] for t, _ in lines]
    H = int(size * spacing * len(lines) + size)
    Wd = max(widths) + 40
    img = Image.new("L", (Wd, H), 0)
    a = Image.new("L", (Wd, H), 0)
    d, da = ImageDraw.Draw(img), ImageDraw.Draw(a)
    y = 10
    for (t, scale), _ in zip(lines, widths):
        ff = font(fontname, int(size * scale))
        d.text((20, y), t, font=ff, fill=int(255 * fill), stroke_width=stroke, stroke_fill=0)
        da.text((20, y), t, font=ff, fill=255, stroke_width=stroke, stroke_fill=255)
        y += int(size * scale * spacing)
    return np.asarray(img, np.float32) / 255, np.asarray(a, np.float32) / 255


def watermark(text):
    """Tall, thin pixel lettering, white with a black keyline (styled after the reference's editor tag)."""
    f = font("vt323", 120)
    w = f.getbbox(text)[2] + 40
    img = Image.new("L", (w, 140), 0)
    a = Image.new("L", (w, 140), 0)
    ImageDraw.Draw(img).text((20, 4), text, font=f, fill=255, stroke_width=4, stroke_fill=0)
    ImageDraw.Draw(a).text((20, 4), text, font=f, fill=255, stroke_width=7, stroke_fill=255)
    lum = np.asarray(img, np.float32) / 255
    alpha = np.asarray(a, np.float32) / 255
    # inner black vertical hairlines, like the reference tag's letterforms
    cols = (np.arange(w) % 9 == 4)[None, :] & (lum > 0.9)
    lum = np.where(cols, 0.0, lum)
    size = (int(w * 1.05), int(140 * 1.45))
    return cv2.resize(lum, size, interpolation=cv2.INTER_AREA), cv2.resize(alpha, size, interpolation=cv2.INTER_AREA)


# ---------------------------------------------------------------- placement
def place(dst, lum, alpha, cx, cy, scale=1.0, angle=0.0, opacity=1.0):
    h, w = lum.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
    M[0, 2] += cx - w / 2
    M[1, 2] += cy - h / 2
    L = cv2.warpAffine(lum, M, (W, W), flags=cv2.INTER_LINEAR, borderValue=0)
    A = cv2.warpAffine(alpha, M, (W, W), flags=cv2.INTER_LINEAR, borderValue=0) * opacity
    dst[:] = dst * (1 - A) + L * A
    return A


# ---------------------------------------------------------------- backgrounds
_rng = np.random.default_rng(7)
_cache = {}


def dot_screen(cell=9, phase=0.0):
    yy, xx = np.mgrid[0:W, 0:W].astype(np.float32)
    u = (xx + yy) / math.sqrt(2) / cell + phase
    v = (xx - yy) / math.sqrt(2) / cell
    return np.sqrt((u - np.round(u)) ** 2 + (v - np.round(v)) ** 2)  # 0 center .. ~0.7 corner


def halftone(lum, cell=7, strength=0.5):
    d = dot_screen(cell)
    dots = (d < 0.62 * np.sqrt(np.clip(1 - lum, 0, 1))).astype(np.float32)
    ht = 1 - dots * 0.85
    mid = np.clip(1 - np.abs(lum - 0.45) * 2.2, 0, 1)  # halftone mostly in midtones
    return lum * (1 - strength * mid) + np.minimum(lum, ht) * strength * mid


def circuit_texture():
    if "circuit" in _cache:
        return _cache["circuit"]
    img = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(img)
    r = np.random.default_rng(3)
    for _ in range(90):
        x, y = r.integers(0, W, 2)
        pts = [(int(x), int(y))]
        for _ in range(r.integers(2, 5)):
            if r.random() < 0.5:
                x = int(np.clip(x + r.integers(-160, 160), 0, W))
            else:
                y = int(np.clip(y + r.integers(-160, 160), 0, W))
            pts.append((x, y))
        d.line(pts, fill=int(r.integers(60, 140)), width=int(r.integers(2, 5)))
        ex, ey = pts[-1]
        d.ellipse((ex - 6, ey - 6, ex + 6, ey + 6), outline=150, width=3)
    _cache["circuit"] = np.asarray(img, np.float32) / 255
    return _cache["circuit"]


def background(kind, k, src_bg):
    """k: frame index within shot. src_bg: darkened source background or None."""
    base = src_bg * 0.55 if src_bg is not None else np.full((W, W), 0.08, np.float32)
    yy, xx = np.mgrid[0:W, 0:W].astype(np.float32)
    if kind == "dots":
        d = dot_screen(10, phase=k * 0.04)
        g = (d < 0.18).astype(np.float32) * 0.35
        return np.maximum(base, g)
    if kind == "stripes":
        s = ((xx + yy + k * 6) % 64 < 22).astype(np.float32)
        return np.maximum(base * 0.7, s * 0.55)
    if kind == "circuit":
        return np.maximum(base * 0.8, circuit_texture() * 0.9)
    if kind == "dark":
        n = cv2.GaussianBlur(_rng.random((W // 8, W // 8)).astype(np.float32), (0, 0), 2)
        return 0.12 + 0.12 * cv2.resize(n, (W, W))
    if kind == "app_grid":
        key = "app_grid"
        if key not in _cache:
            img = Image.new("L", (W * 2, W * 2), 40)
            d = ImageDraw.Draw(img)
            cell = 128
            for i in range(0, W * 2, cell):
                for j in range(0, W * 2, cell):
                    v = 200 if ((i + j) // cell) % 2 == 0 else 90
                    d.rounded_rectangle((i + 14, j + 14, i + cell - 14, j + cell - 14), radius=28, fill=v)
            _cache[key] = cv2.resize(np.asarray(img, np.float32) / 255, (W, W), interpolation=cv2.INTER_AREA)
        g = np.roll(_cache[key], k * 2, axis=1)
        return np.maximum(base * 0.5, g * 0.75)
    if kind == "text_wall":
        key = "text_wall"
        if key not in _cache:
            img = Image.new("L", (W * 2, W), 30)
            d = ImageDraw.Draw(img)
            f = font("anton", 120)
            for row in range(5):
                d.text((-row * 90, row * 118 - 20), "TECH  TECH  TECH  TECH", font=f, fill=95)
            _cache[key] = np.asarray(img, np.float32) / 255
        t = _cache[key][:, (k * 4) % W:(k * 4) % W + W]
        return np.maximum(base * 0.6, t)
    if kind == "light_bars":
        bars = ((xx // 36) % 2 == 0).astype(np.float32) * np.exp(-((yy - 260) / 120) ** 2)
        bars *= 0.7 + 0.3 * np.sin(k * 0.6 + xx / 50)
        return np.maximum(base * 0.5, bars * 0.95)
    if kind == "phone_wall":
        key = "phone_wall"
        if key not in _cache:
            canvas = np.full((W, W), 0.1, np.float32)
            l, a = sticker("phone_back", 170)
            for i in range(-1, 6):
                for j in range(-1, 4):
                    place(canvas, l * 0.6, a, i * 110 + (j % 2) * 55, j * 190 + 40, 1.0, 0)
            _cache[key] = canvas
        return np.maximum(base * 0.5, _cache[key])
    return base
