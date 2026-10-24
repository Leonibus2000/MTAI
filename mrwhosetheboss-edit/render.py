"""Render the Mrwhosetheboss edit.

For each shot it uses footage/<shot id>.mp4 when that clip exists (pre-trimmed by
fetch_footage.py). Otherwise it renders a clearly labelled placeholder subject, so
timing, effects and graphics can be reviewed before footage is available.

usage: python3 render.py [--out out.mp4] [--audio ref.mp4] [--debug-frames DIR]
"""
import argparse
import math
import os
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw

import gfx
from gfx import W, place, sticker
from timeline import FPS, N_FRAMES, SHOTS, TRANSITIONS

HERE = os.path.dirname(os.path.abspath(__file__))
FOOTAGE = os.environ.get("FOOTAGE_DIR", os.path.join(HERE, "footage"))
rng = np.random.default_rng(11)


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * min(max(t, 0), 1))


# ---------------------------------------------------------------- subject sources
class Footage:
    CROP = {"ecu": (1.9, 0.05), "cu": (2.9, 0.35), "mcu": (4.0, 0.9), "ms": (5.6, 1.5)}

    def __init__(self, path, framing):
        from rembg import new_session
        self.seg = new_session("u2net_human_seg")
        self._still = None
        if path.endswith(".jpg"):  # pre-cropped square still: the camera moves supply the motion
            f = cv2.imread(path)
            self.frames, self.box = [f], (0, 0, min(f.shape[:2]))
            return
        self.frames = []
        cap = cv2.VideoCapture(path)
        while True:
            ok, f = cap.read()
            if not ok:
                break
            self.frames.append(f)
        if not self.frames:
            raise RuntimeError(f"no frames in {path}")
        self.box = self._crop_box(self.frames[0], framing)

    def _mask(self, f):
        from rembg import remove
        m = remove(Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)), session=self.seg, only_mask=True)
        return np.asarray(m, np.float32) / 255

    def _crop_box(self, f, framing):
        """Frame the head from the person mask (top of silhouette = top of head)."""
        h, w = f.shape[:2]
        m = self._mask(f) > 0.5
        rows = np.where(m.any(1))[0]
        if len(rows) == 0:
            s = min(h, w)
            return (w - s) // 2, (h - s) // 2, s
        y = rows[0]
        band = m[y:y + max(4, int(0.12 * (rows[-1] - y)))]
        xs = np.where(band.any(0))[0]
        fw = max(xs[-1] - xs[0], h // 12)
        fh = fw * 1.3
        x = xs.mean() - fw / 2
        mult, dy = self.CROP[framing]
        s = int(min(fh * mult, h, w))
        cx, cy = x + fw / 2, y + fh / 2 + dy * fh
        x0 = int(np.clip(cx - s / 2, 0, w - s))
        y0 = int(np.clip(cy - s / 2, 0, h - s))
        return x0, y0, s

    def get(self, k):
        if len(self.frames) == 1 and self._still is not None:
            return self._still
        f = self.frames[min(k, len(self.frames) - 1)]
        x0, y0, s = self.box
        f = cv2.resize(f[y0:y0 + s, x0:x0 + s], (W, W), interpolation=cv2.INTER_AREA)
        mask = self._mask(f)
        lum = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
        self._still = (lum, mask, False)
        return self._still


class Placeholder:
    """Neutral mannequin silhouette, labelled so it can't be mistaken for real footage."""
    GEOM = {"ecu": (230, 300), "cu": (140, 245), "mcu": (100, 215), "ms": (68, 170)}

    def __init__(self, shot):
        self.shot = shot
        self.r, self.cy = self.GEOM[shot["framing"]]

    def get(self, k):
        r, cy = self.r, self.cy + 4 * math.sin(k * 0.35)
        cx = 288 + 6 * math.sin(k * 0.21)
        yy, xx = np.mgrid[0:W, 0:W].astype(np.float32)
        head = ((xx - cx) / (r * 0.82)) ** 2 + ((yy - cy) / r) ** 2 < 1
        neck = (np.abs(xx - cx) < r * 0.38) & (yy > cy) & (yy < cy + r * 1.35)
        sh_y = cy + r * 1.25
        body = ((xx - cx) / (r * 2.6)) ** 2 + ((yy - sh_y - r * 1.6) / (r * 1.7)) ** 2 < 1
        mask = (head | neck | body).astype(np.float32)
        mask = cv2.GaussianBlur(mask, (0, 0), 1.2)
        light = 0.35 + 0.45 * np.clip(1 - np.hypot(xx - cx + r * 0.4, yy - cy + r * 0.4) / (r * 2.2), 0, 1)
        lum = light * (1 - 0.35 * (yy > sh_y)) * mask
        hair = head & (yy < cy - r * 0.45)
        lum[hair] *= 0.35
        return lum.astype(np.float32), mask, True


def subject_for(shot):
    if shot["framing"] is None:
        return None
    for ext in (".mp4", ".jpg"):
        p = os.path.join(FOOTAGE, shot["id"] + ext)
        if os.path.exists(p):
            return Footage(p, shot["framing"])
    return Placeholder(shot)


# ---------------------------------------------------------------- looks
def stylize(lum, look):
    lum = np.clip((lum - 0.5) * 1.3 + 0.52, 0, 1).astype(np.float32)
    if look.get("poster"):
        n = look["poster"]
        sm = cv2.bilateralFilter(lum, 7, 0.15, 5)
        lum = 0.6 * np.round(sm * (n - 1)) / (n - 1) + 0.4 * sm
    if look.get("halftone"):
        lum = gfx.halftone(lum, 6, look["halftone"])
    return lum


def outline(mask, k, width=6):
    m = (mask > 0.5).astype(np.float32)
    # jitter the cut line so it reads as a hand-cut sticker edge
    n = cv2.resize(rng.standard_normal((24, 24)).astype(np.float32), (W, W)) * 3 if k % 3 == 0 else None
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (width * 2 + 1, width * 2 + 1))
    d = cv2.dilate(m, ker)
    if n is not None:
        mx, my = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(W, dtype=np.float32))
        d = cv2.remap(d, mx + n, my + n.T, cv2.INTER_LINEAR)
    return np.clip(cv2.GaussianBlur(d, (0, 0), 0.8), 0, 1)


# ---------------------------------------------------------------- overlays
STK = {k: sticker(k, 200) for k in ["phone", "phone_back", "bolt", "chip", "battery", "lens", "wifi", "cpu_badge"]}
STRIPED = gfx.striped_phone(300)
TITLE = gfx.text_layer([("ARUN", 1.0), ("the", 0.7), ("BOSS", 1.15)], "anton", 150, spacing=0.82)
BADGE = gfx.text_layer([("WHO?", 1.0)], "silkscreen", 88, stroke=5)


def draw_rect_outline(dst, cx, cy, w, h, ang, thick=3, val=0.95):
    pts = cv2.boxPoints(((cx, cy), (w, h), ang)).astype(np.int32)
    layer = np.zeros_like(dst)
    cv2.polylines(layer, [pts], True, 1.0, thick, cv2.LINE_AA)
    dst[:] = dst * (1 - layer) + val * layer


def behind(shot, f, k, img):
    o = shot["overlays"]
    if "striped_phones" in o:
        place(img, *STRIPED, 470 + k * 0.8, 190, 0.95, -18)
        place(img, *STRIPED, 520 - k * 0.5, 470, 0.75, -24)
    if "icon_field" in o or "icon_orbit" in o:
        t = f / FPS
        for i, (name, x, y, s) in enumerate([("phone_back", 420, 140, 0.55), ("bolt", 400, 400, 0.5),
                                             ("chip", 110, 330, 0.5), ("battery", 150, 120, 0.4)]):
            ang = 20 * math.sin(t * 2 + i) - 25
            if "icon_orbit" in o:
                x, y, s = 288 + 230 * math.cos(t * 1.6 + i * 1.57), 300 + 200 * math.sin(t * 1.6 + i * 1.57), s * 0.8
            place(img, *STK[name], x + 30 * math.sin(t * 3 + i), y + 20 * math.cos(t * 2.5 + i), s, ang)
    if "pixel_stairs" in o:
        for side in (0, 1):
            for i in range(9):
                x = 8 + i * 9 if side == 0 else W - 30 - i * 9
                y0 = 40 + i * 38 + int(k * 1.5)
                cv2.rectangle(img, (x, y0), (x + 20, y0 + 60), 0.95, -1)


def front(shot, f, k, img):
    o, n = shot["overlays"], shot["end"] - shot["start"]
    if "tilt_rect" in o:
        draw_rect_outline(img, 205, 215, 330, 330, -22 + k * 0.3)
    if "tilt_rect2" in o:
        draw_rect_outline(img, 300, 260, 560, 470, 6 - k * 0.2)
    if "title_text" in o:
        p = ease(k / 14)
        x = -360 + 330 * p
        tl, ta = TITLE
        tmp_l = np.zeros((W, W), np.float32)
        a = place(tmp_l, tl, ta, x + tl.shape[1] / 2, 250, 0.82, 0)
        if k < 18 or k % 5 == 0:  # glitch slices while sliding in, then periodic stutter
            for _ in range(6):
                y = rng.integers(0, W - 30)
                hgt, sh = rng.integers(6, 30), int(rng.integers(-40, 40))
                tmp_l[y:y + hgt] = np.roll(tmp_l[y:y + hgt], sh, axis=1)
                a[y:y + hgt] = np.roll(a[y:y + hgt], sh, axis=1)
        img[:] = img * (1 - a) + tmp_l * a
    if "icons_pop" in o and k >= 16:
        for i, (name, x, y, ang) in enumerate([("phone_back", 470, 95, 25), ("bolt", 500, 470, -10),
                                               ("wifi", 80, 480, 0)]):
            kk = k - 16 - i
            if kk >= 0:
                s = 0.55 * min(1.25, 0.3 + kk * 0.35) if kk < 3 else 0.55
                place(img, *STK[name], x, y, s, ang + kk * 2)
    if "phones_fly_in" in o and f >= 116:
        kk = f - 116
        p = 1 - (1 - min(kk / 5, 1)) ** 3
        for side in (-1, 1):
            x = 288 + side * (520 - 340 * p) + side * 8 * math.sin(kk * 0.8)
            place(img, *STK["phone"], x, 300 + 30 * side, 1.3, side * 18 + kk * side * 0.6)
    if "badge" in o and k < 14:
        s = 0.5 + 0.5 * min(k / 2, 1)
        fade = 1.0 if k < 10 else (14 - k) / 4
        place(img, *STK["cpu_badge"], 288, 330, s * 0.9, 0, fade)
        place(img, *BADGE, 288, 380, s, 0, fade)
    if "tear" in o:
        tear(img, k)
    if "lens_zoom" in o and k >= n - 4:
        kk = k - (n - 4)
        place(img, *STK["lens"], 300, 300, 0.4 * (2.2 ** kk), 40 + kk * 25)
    if "crash_zoom" in o and isinstance(SRC, Placeholder):  # give the crash zoom a device to land on
        place(img, *STK["phone_back"], 360, 430, 0.8, 70)
    if "held_phone" in o and isinstance(SRC, Placeholder):
        place(img, *STK["phone_back"], 430, 430, 0.75, -12 + 4 * math.sin(k * 0.5))


_tear_path = None


def tear(img, k):
    global _tear_path
    if _tear_path is None:
        r = np.random.default_rng(5)
        ys = np.arange(0, W + 8, 8)
        _tear_path = np.stack([ys, np.cumsum(r.normal(0, 3, len(ys))) + r.normal(0, 4, len(ys))], 1)
    ys, jitter = _tear_path[:, 0], _tear_path[:, 1]
    xs = 480 - ys * 0.6 + jitter
    yy, xx = np.mgrid[0:W, 0:W].astype(np.float32)
    edge = np.interp(yy[:, 0], ys, xs)[:, None]
    right = xx > edge
    shifted = np.roll(np.roll(img, 10, axis=1), -6, axis=0)
    img[:] = np.where(right, shifted * 0.8, img)
    width = 22 + 7 * np.sin(yy / 7) + 4 * np.sin(yy / 2.3)
    band = ((xx - edge > -2) & (xx - edge < width)).astype(np.float32)
    img[:] = np.maximum(img, band * 0.97)


# ---------------------------------------------------------------- camera & transitions
def warp(img, z, rot, dx, dy, center=(W / 2, W / 2)):
    M = cv2.getRotationMatrix2D(center, rot, z)
    M[0, 2] += dx
    M[1, 2] += dy
    return cv2.warpAffine(img, M, (W, W), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def line_blur(img, length, ang):
    length = int(length)
    if length < 2:
        return img
    k = np.zeros((length, length), np.float32)
    c = (length - 1) / 2
    a = math.radians(ang)
    cv2.line(k, (int(c - c * math.cos(a)), int(c - c * math.sin(a))),
             (int(c + c * math.cos(a)), int(c + c * math.sin(a))), 1.0, 1)
    return cv2.filter2D(img, -1, k / k.sum(), borderType=cv2.BORDER_REFLECT)


def zoom_blur(img, amount, steps=10):
    acc = np.zeros_like(img)
    for i in range(steps):
        acc += warp(img, 1 + amount * i / steps, 0, 0, 0)
    return acc / steps


def transition_state(f):
    """Returns (kind, intensity 0..1, angle, phase 'out'|'in') for frame f, or None."""
    for c, kind, pre, post, ang in TRANSITIONS:
        if c - pre <= f < c:
            return kind, (f - (c - pre) + 1) / (pre + 0.5), ang, "out"
        if c <= f < c + post:
            return kind, 1 - (f - c) / (post + 0.3), ang, "in"
    return None


def apply_transition(img, f):
    st = transition_state(f)
    if st is None:
        return img
    kind, I, ang, phase = st
    I = min(max(I, 0), 1)
    sign = 1 if phase == "out" else -1
    if kind.startswith("whip"):
        a = math.radians(ang)
        img = warp(img, 1 + 0.15 * I, 0, sign * 110 * I * math.cos(a), sign * 110 * I * math.sin(a))
        img = line_blur(img, 8 + 95 * I, ang)
        if kind == "whip_flash":
            img = img + 0.45 * I
    elif kind == "zoom":
        img = warp(img, 1 + (0.5 if phase == "out" else 0.25) * I, 0, 0, 0)
        img = zoom_blur(img, 0.35 * I)
    elif kind == "glitch":
        img = img.copy()
        for _ in range(int(10 * I) + 3):
            y = rng.integers(0, W - 40)
            h, s = rng.integers(8, 60), int(rng.integers(-80, 80) * I)
            img[y:y + h] = np.roll(img[y:y + h], s, axis=1)
        img = line_blur(img, 30 * I, 0)
    return img


# ---------------------------------------------------------------- frame assembly
SRC = None


def render_frame(shot, src, f):
    global SRC
    SRC = src
    k = f - shot["start"]
    n = shot["end"] - shot["start"]
    t = k / max(n - 1, 1)
    if src is not None:
        lum, mask, is_ph = src.get(k)
        sub = stylize(lum, shot["look"])
        bg_src = lum * (1 - mask) if not is_ph else None
    else:
        sub = mask = None
        is_ph = False
        bg_src = None
    img = gfx.background(shot["bg"], k, bg_src).astype(np.float32)
    behind(shot, f, k, img)
    if sub is not None:
        ring = outline(mask, k)
        img = img * (1 - ring) + 0.96 * ring
        img = img * (1 - mask) + sub * mask
        if is_ph:
            label(img, shot)
    front(shot, f, k, img)

    cam = shot["cam"]
    z = cam["z"][0] + (cam["z"][1] - cam["z"][0]) * ease(t)
    rot = cam["rot"][0] + (cam["rot"][1] - cam["rot"][0]) * ease(t)
    sx, sy = rng.normal(0, cam["shake"], 2)
    center = (W / 2, W / 2)
    if "crash_zoom" in shot["overlays"] and k >= 13:
        kk = k - 12
        z *= 1 + 0.45 * kk
        center = (360, 420) if isinstance(SRC, Placeholder) else tuple(shot.get("zoom_to", (280, 500)))
        img = warp(img, z, rot, sx, sy, center)
        img = zoom_blur(img, 0.12 * kk)
    else:
        img = warp(img, z, rot, sx, sy, center)
    img = apply_transition(img, f)
    return finish(img, f)


def label(img, shot):
    """Burn a 'placeholder' slate into the subject so previews can't be mistaken for real footage."""
    pil = Image.new("L", (W, 64), 0)
    d = ImageDraw.Draw(pil)
    d.text((W / 2, 18), f"{shot['id']}  ·  PLACEHOLDER  ·  footage needed", font=gfx.font("anton", 26), fill=255, anchor="mm")
    d.text((W / 2, 46), shot["need"][:62], font=gfx.font("anton", 19), fill=200, anchor="mm")
    lab = np.asarray(pil, np.float32) / 255
    y = 470
    img[y:y + 64] = img[y:y + 64] * 0.25
    img[y:y + 64] = np.maximum(img[y:y + 64], lab)


_vign = None


def finish(img, f):
    global _vign
    if _vign is None:
        yy, xx = np.mgrid[0:W, 0:W].astype(np.float32)
        _vign = 1 - 0.35 * (np.hypot(xx - W / 2, yy - W / 2) / (W * 0.7)) ** 2
    img = np.clip(img, 0, 1) * _vign
    grain = cv2.GaussianBlur(rng.standard_normal((W, W)).astype(np.float32), (0, 0), 0.7) * 0.05
    img = img + grain
    img = np.clip(img, 0, 1) ** 1.05
    return (img * 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out.mp4"))
    ap.add_argument("--audio", default=None, help="file whose audio track is used (the reference edit)")
    ap.add_argument("--debug-frames", default=None)
    a = ap.parse_args()

    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{W}",
           "-r", str(FPS), "-i", "-"]
    if a.audio:
        cmd += ["-i", a.audio, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-crf", "17", "-preset", "slow", "-pix_fmt", "yuv420p",
            "-t", f"{N_FRAMES / FPS:.3f}", "-movflags", "+faststart", a.out]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    if a.debug_frames:
        os.makedirs(a.debug_frames, exist_ok=True)
    for shot in SHOTS:
        src = subject_for(shot)
        kind = "none" if src is None else type(src).__name__
        print(f"{shot['id']} f{shot['start']}-{shot['end'] - 1} source={kind}", flush=True)
        for f in range(shot["start"], shot["end"]):
            fr = render_frame(shot, src, f)
            enc.stdin.write(fr.tobytes())
            if a.debug_frames:
                cv2.imwrite(os.path.join(a.debug_frames, f"f{f:03d}.png"), fr)
    enc.stdin.close()
    enc.wait()
    print("wrote", a.out)


if __name__ == "__main__":
    main()
