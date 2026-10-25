"""Real product photos (phones, batteries) as die-cut stickers for the collage shots.

The photos are CC BY / CC0 images listed in props.json with their attribution (CREDITS.md has the
lines to publish with the video); `fetch_footage.py props` downloads them into props/. Each one is
cut out with BiRefNet-general (cached next to the photo, like the subject mattes), cropped, turned
black-and-white and given the same white die-cut border as the subject, plus a soft drop shadow.
Fast moves are drawn with motion blur by averaging the prop along its path inside the shutter.
"""
import json
import os

import cv2
import numpy as np

import cutout
from gfx import place

HERE = os.path.dirname(os.path.abspath(__file__))
PROPS_DIR = os.environ.get("PROPS_DIR", os.path.join(HERE, "props"))
SIZE = 300     # longest side of a prop at scale 1.0, border included
BORDER = 7     # white die-cut border at scale 1.0
SHADOW = (9, 13, 0.55)  # drop shadow offset x, y (px at scale 1.0) and strength

_cache = {}
META = json.load(open(os.path.join(HERE, "props.json")))


def load(name, size=SIZE):
    """(lum, alpha, shadow) arrays for prop `name`, bounded by `size` px (SIZE unless a close-up needs more).
    The layout scales with `size`, so positions given as fractions of the prop (props.json "screen")
    hold at any size."""
    if (name, size) in _cache:
        return _cache[(name, size)]
    path = os.path.join(PROPS_DIR, name + ".jpg")
    bgr = cv2.imread(path)
    if bgr is None:
        raise FileNotFoundError(f"{path} missing: run `python3 fetch_footage.py props`")
    m = cv2.imread(cutout.cached(path, "general"), 0).astype(np.float32) / 255
    m = cv2.resize(m, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_LINEAR)
    keep = META.get(name, {}).get("keep")  # optional box (fractions) around the object, for photos with extras
    if keep:
        h, w = m.shape
        box = np.zeros_like(m)
        box[int(keep[1] * h):int(keep[3] * h), int(keep[0] * w):int(keep[2] * w)] = 1
        m *= box
    m = cutout.clean(m, keep_ratio=0.2)
    ys, xs = np.nonzero(m > 0.5)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    gray = cv2.cvtColor(bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    m = m[y0:y1, x0:x1]
    border = BORDER * size / SIZE
    pad = int(round((BORDER + 3) * size / SIZE))
    inner = size - 2 * pad
    k = inner / max(gray.shape)
    dims = (max(1, int(round(gray.shape[1] * k))), max(1, int(round(gray.shape[0] * k))))
    gray = cv2.resize(gray, dims, interpolation=cv2.INTER_AREA)
    m = cv2.resize(m, dims, interpolation=cv2.INTER_AREA)
    # photographic B&W: gentle S-curve, a touch of local contrast, no posterising (keeps it a photo)
    gray = np.clip((gray - 0.5) * 1.2 + 0.5, 0, 1)
    gray = np.clip(gray + 0.3 * (gray - cv2.GaussianBlur(gray, (0, 0), 2)), 0, 1)
    gray = cv2.copyMakeBorder(gray, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    m = cv2.copyMakeBorder(m, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    rb = int(round(border))
    ring = cv2.dilate((m > 0.5).astype(np.float32), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rb + 1, 2 * rb + 1)))
    ring = np.clip(cv2.GaussianBlur(ring, (0, 0), 0.9 * size / SIZE), 0, 1)
    lum = gray * m + 0.95 * (1 - m)          # white border where the ring extends past the object
    shadow = cv2.GaussianBlur(ring, (0, 0), 6 * size / SIZE)
    _cache[(name, size)] = (lum.astype(np.float32), ring.astype(np.float32), shadow.astype(np.float32))
    return _cache[(name, size)]


def upright(name):
    """Rotation (degrees, OpenCV sense) that stands the prop's long axis vertical."""
    _, alpha, _ = load(name)
    ys, xs = np.nonzero(alpha > 0.5)
    w, v = np.linalg.eigh(np.cov(np.stack([xs - xs.mean(), ys - ys.mean()])))
    phi = np.degrees(np.arctan2(v[1, np.argmax(w)], v[0, np.argmax(w)])) % 180
    return float((phi - 90 + 90) % 180 - 90)


def draw(dst, name, x, y, scale, angle=0.0, opacity=1.0, soft=0.0, size=SIZE):
    """Prop with its shadow, centred at (x, y). `scale` is relative to SIZE whatever `size` the prop is
    loaded at (a bigger `size` only adds detail for props drawn large). `soft` blurs it slightly."""
    lum, alpha, shadow = load(name, size)
    scale = scale * SIZE / size
    if soft > 0.2:
        lum, alpha = cv2.GaussianBlur(lum, (0, 0), soft), cv2.GaussianBlur(alpha, (0, 0), soft)
    sx, sy, strength = SHADOW
    place(dst, np.zeros_like(shadow), shadow * strength, x + sx * scale, y + sy * scale, scale, angle, opacity)
    place(dst, lum, alpha, x, y, scale, angle, opacity)


def draw_moving(dst, name, path, t, shutter=0.8, step=3.0, max_samples=10, soft=0.0, size=SIZE):
    """Prop following path(t) -> (x, y, scale, angle, opacity), motion-blurred over the shutter."""
    a, b = path(t - shutter / 2), path(t + shutter / 2)
    travel = max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]) * SIZE, abs(a[3] - b[3]) * SIZE / 60)
    n = int(min(max(np.ceil(travel / step), 1), max_samples))
    if n == 1:
        draw(dst, name, *path(t), soft=soft, size=size)
        return
    acc = np.zeros_like(dst)
    for tt in np.linspace(t - shutter / 2, t + shutter / 2, n):
        layer = dst.copy()
        draw(layer, name, *path(tt), soft=soft, size=size)
        acc += layer
    dst[:] = acc / n
