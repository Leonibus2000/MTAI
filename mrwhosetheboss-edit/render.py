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
import tempfile
import wave

import cv2
import numpy as np
from PIL import Image, ImageDraw

import camera
import cutout
import gfx
import props
import transitions
from gfx import W, place, sticker
from timeline import CUTS, FPS, N_FRAMES, SHOTS

HERE = os.path.dirname(os.path.abspath(__file__))
FOOTAGE = os.environ.get("FOOTAGE_DIR", os.path.join(HERE, "footage"))
rng = np.random.default_rng(11)


# ---------------------------------------------------------------- subject sources
_seg = None


def seg_session():
    global _seg
    if _seg is None:
        from rembg import new_session
        _seg = new_session("u2net_human_seg")
    return _seg


class Footage:
    CROP = {"ecu": (1.9, 0.05), "cu": (2.9, 0.35), "mcu": (4.0, 0.9), "ms": (5.6, 1.5)}

    def __init__(self, path, framing, scale=1.0, mode="person", drop=(), erase=(), inpaint=None, add=(), offset=(0, 0)):
        self.scale = scale
        self.offset = offset
        self._still = None
        self._matte = None
        if path.endswith(".jpg"):  # pre-cropped square still: the camera moves supply the motion
            f = cv2.imread(path)
            if inpaint:
                f = paint_out(f, **inpaint)
            self.frames, self.box = [f], (0, 0, min(f.shape[:2]))
            self._matte = cutout.matte(path, mode, W, drop, erase, add)
            return
        self.seg = seg_session()
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
        mask = self._matte if self._matte is not None else cutout.clean(self._mask(f))
        lum = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
        if self.scale != 1.0 or any(self.offset):
            # shrink (anchored bottom-centre so the body still meets the frame edge) and/or move the subject
            M = cv2.getRotationMatrix2D((W / 2, W), 0, self.scale)
            M[:, 2] += self.offset
            lum = cv2.warpAffine(lum, M, (W, W), borderValue=0)
            mask = cv2.warpAffine(mask, M, (W, W), borderValue=0)
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
            mode = os.environ.get("CUTOUT_MODE") or shot.get("cutout", "person")  # override for quick previews
            src = Footage(p, shot["framing"], shot.get("subject_scale", 1.0), mode, shot.get("drop", ()),
                          shot.get("erase", ()), shot.get("inpaint"), shot.get("add", ()), shot.get("subject_offset", (0, 0)))
            shot.setdefault("focus", head_focus(src.get(0)[1]))
            return src
    return Placeholder(shot)


def paint_out(bgr, hue, sat, val, region):
    """Remove a saturated graphic (e.g. a neon line baked into a thumbnail) inside region (576-px coords)."""
    h, w = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hit = (hsv[..., 0] >= hue[0]) & (hsv[..., 0] <= hue[1]) & (hsv[..., 1] >= sat) & (hsv[..., 2] >= val)
    area = np.zeros((h, w), np.uint8)
    cv2.fillPoly(area, [(np.array(region, np.float32) * (w / W)).astype(np.int32)], 1)
    m = cv2.dilate((hit & (area > 0)).astype(np.uint8) * 255, np.ones((7, 7), np.uint8))
    return cv2.inpaint(bgr, m, 7, cv2.INPAINT_TELEA)


def head_focus(mask):
    """Zoom centre: middle of the head, i.e. the top quarter of the silhouette."""
    rows = np.where((mask > 0.5).any(1))[0]
    if len(rows) == 0:
        return (W / 2, W / 2)
    y0, y1 = rows[0], rows[0] + max(20, (rows[-1] - rows[0]) // 4)
    ys, xs = np.nonzero(mask[y0:y1] > 0.5)
    return (float(xs.mean()), float(y0 + ys.mean()))


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
STK = {k: sticker(k, 200) for k in ["phone_back", "cpu_badge"]}
STRIPED = gfx.striped_phone(300)
TITLE_TOP = gfx.glow_title([("ARUN", 1.0), ("the", 0.72)], size=90)
TITLE_BOSS = gfx.glow_title([("BOSS", 1.0)], size=90)
TITLE_SCALE = 1.0
WATERMARK = gfx.watermark("MTD")

# Real product photos (props.py) in place of drawn icons.
# Stickers that slam in at the end of the title shot: name, x, y, scale, angle, direction they fly in from
POP = [("phone_iphone_modern", 470, 92, 1.0, 34, (0.4, -1)), ("battery_duracell_aa", 112, 528, 0.85, 16, (-1, 0.5)),
       ("battery_powerbank_silver", 505, 500, 0.85, -16, (1, 0.6))]
# Dark interlude: batteries drifting (name, start xy, end xy, scale, angles), then two phones whip in
# from the sides and hold at the frame edges where the reference has two hands
FLOAT = [("battery_9v_trio", (418, 142), (452, 120), 0.74, (-20, -11)),
         ("battery_duracell_green", (118, 270), (100, 236), 0.8, (14, 26)),
         ("battery_lipo_large", (430, 440), (468, 426), 0.72, (-8, 4))]
FLY_AT = 115
FLY = [("phone_iphone12pro_standing", -1, 330, 1.3, -12), ("phone_galaxy_s7_front", 1, 300, 1.32, 53)]  # tops lean in
# S07: two small props flanking the MTD badge in front of him (the reference has a stopwatch and a rocket there)
FLANK = [("battery_powerbank_silver", 122, 330, 0.36, 24), ("battery_duracell_aa_vertical", 462, 330, 0.34, -18)]


def float_pose(i, f, k, n):
    """Pose (x, y, scale, angle) of interlude battery i at frame f (k frames into the n-frame shot): drifts,
    sways, then pulls back toward the middle once the phones arrive."""
    name, (xa, ya), (xb, yb), s, (aa, ab) = FLOAT[i]
    shrink = ease((f - FLY_AT) / 6)
    q = k / max(n - 1, 1)
    x, y = xa + (xb - xa) * q, ya + (yb - ya) * q
    x, y = x + (288 - x) * 0.35 * shrink, y + (300 - y) * 0.3 * shrink
    return x + 6 * math.sin(f * 0.21 + i), y + 5 * math.cos(f * 0.17 + i), s * (1 - 0.38 * shrink), aa + (ab - aa) * q


def fly_pose(idx, t):
    """Pose (x, y, scale, angle, opacity) of interlude phone `idx` at time t: whips in from the side over
    2.5 frames, then holds at the frame edge with a slight sway."""
    name, side, y, s, ang = FLY[idx]
    u = t - FLY_AT
    if u < 0:
        return 288 + side * 560, y, s, ang, 0.0
    p = 1 - (1 - min(u / 2.5, 1)) ** 3
    x = 288 + side * (560 - 340 * p) + side * 7 * math.sin(u * 0.7)
    return x, y + 6 * math.cos(u * 0.6 + side), s, ang + 3 * math.sin(u * 0.5 + side), 1.0


def ease(t):
    """Smoothstep from 0 to 1 over t in [0, 1]."""
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def draw_rect_outline(dst, cx, cy, w, h, ang, thick=3, val=0.95):
    pts = cv2.boxPoints(((cx, cy), (w, h), ang)).astype(np.int32)
    layer = np.zeros_like(dst)
    cv2.polylines(layer, [pts], True, 1.0, thick, cv2.LINE_AA)
    dst[:] = dst * (1 - layer) + val * layer


def behind(shot, f, k, img):
    o = shot["overlays"]
    if "title_text" in o:  # behind him, like the reference: his head covers the end of the name
        title(shot, f, k, img)
    if "striped_phones" in o:
        place(img, *STRIPED, 470 + k * 0.8, 190, 0.95, -18)
        place(img, *STRIPED, 520 - k * 0.5, 470, 0.75, -24)
    if "icon_field" in o:
        for i, (name, *_) in enumerate(FLOAT):
            props.draw(img, name, *float_pose(i, f, k, shot["end"] - shot["start"]), soft=1.1)

    if "pixel_stairs" in o:
        for side in (0, 1):
            for i in range(9):
                x = 8 + i * 9 if side == 0 else W - 30 - i * 9
                y0 = 40 + i * 38 + int(k * 1.5)
                cv2.rectangle(img, (x, y0), (x + 20, y0 + 60), 0.95, -1)


def front(shot, f, k, img):
    o = shot["overlays"]
    if "tilt_rect" in o:
        draw_rect_outline(img, 205, 215, 330, 330, -22 + k * 0.3)
    if "tilt_rect2" in o:
        draw_rect_outline(img, 300, 260, 560, 470, 6 - k * 0.2)
    if "phones_fly_in" in o and f >= FLY_AT - 1:
        for idx, (name, *_) in enumerate(FLY):
            props.draw_moving(img, name, lambda t, idx=idx: fly_pose(idx, t), f)
    if "icon_orbit" in o:
        for i, (name, x, y, s, ang) in enumerate(FLANK):
            pop = (0.5, 1.12)[k] if k < 2 else 1.0
            props.draw(img, name, x + 10 * math.sin(f * 0.45 + 2 * i), y + 8 * math.cos(f * 0.38 + 2 * i), s * pop,
                       ang + 6 * math.sin(f * 0.3 + i))
    if "badge" in o and k < 16:
        # editor tag: pops in over 2 frames, holds, then breaks up into vertical strips
        s = (0.55, 1.12, 1.0)[k] if k < 3 else 1.0
        wl, wa = WATERMARK
        if k >= 11:
            keep = np.random.default_rng(k).random(wa.shape[1] // 3 + 1) > (k - 10) / 5.5
            wa = wa * np.repeat(keep, 3)[:wa.shape[1]][None, :]
            wl = wl * (0.4 + 0.6 * np.repeat(keep, 3)[:wa.shape[1]][None, :])
        place(img, *STK["cpu_badge"], 288, 300, s * 0.75, 0, 1.0 if k < 11 else max(0, (15 - k) / 4))
        place(img, wl, wa, 288, 340, s * 0.95, 0)
    if "tear" in o:
        tear(img, k)
    if "crash_zoom" in o and isinstance(SRC, Placeholder):  # give the crash zoom a device to land on
        place(img, *STK["phone_back"], 360, 430, 0.8, 70)
    if "held_phone" in o and isinstance(SRC, Placeholder):
        place(img, *STK["phone_back"], 430, 430, 0.75, -12 + 4 * math.sin(k * 0.5))


def screen(shot, f, img):
    """Graphics stuck to the screen rather than the scene, drawn after the camera (they ignore its zoom)."""
    if "icons_pop" in shot["overlays"] and f >= shot["icons_at"] - 1:
        # real phone and batteries slam in around the frame edge, half off screen, like the reference's at 2.97 s
        for i, (name, x, y, s, ang, (dx, dy)) in enumerate(POP):
            def path(t, i=i, x=x, y=y, s=s, ang=ang, dx=dx, dy=dy):
                u = t - shot["icons_at"] - i
                if u < 0:
                    return x, y, s, ang, 0.0
                if u < 1:      # flies in from off screen and overshoots
                    m, off = 0.5 + 0.65 * u, 1 - u
                elif u < 2:
                    m, off = 1.15 - 0.15 * (u - 1), 0.0
                else:
                    m, off = 1.0, 0.0
                return (x + dx * 150 * off + 5 * math.sin(t * 0.9 + i), y + dy * 150 * off + 4 * math.cos(t * 1.1 + i),
                        s * m, ang + 12 * off + 3 * math.sin(t * 0.7 + i), 1.0)
            props.draw_moving(img, name, path, f)


def title(shot, f, k, img):
    """'ARUN / the' on screen from the cut (flickering with the glitch frames); 'BOSS' lands with the zoom."""
    cfg = shot["title"]
    if k in cfg["off"]:
        return
    s = TITLE_SCALE
    x0 = 22 + 0.6 * k  # the words fill the space left of him; he overlaps their last letter a little
    layer = np.zeros((W, W), np.float32)
    tl, ta = TITLE_TOP
    a = place(layer, tl, ta, x0 + s * tl.shape[1] / 2, 26 + s * tl.shape[0] / 2, s, 0)
    if k >= cfg["boss_at"] and k not in cfg["boss_off"]:
        bl, ba = TITLE_BOSS
        pop = {0: 0.75, 1: 1.08}.get(k - cfg["boss_at"], 1.0)
        bx, by = x0 + s * bl.shape[1] / 2, 212 + s * bl.shape[0] / 2
        a = np.maximum(a, place(layer, bl, ba, bx, by, s * pop, 0))
    g = cfg["glitch"].get(k, 1.0 if k == cfg["boss_at"] else 0.0)
    if g:  # sliced rows and a horizontal ghost on the lettering only
        r = np.random.default_rng(f)
        for _ in range(int(4 + 6 * g)):
            y = int(r.integers(0, W - 30))
            h, sh = int(r.integers(6, 34)), int(r.integers(-44, 44) * g)
            layer[y:y + h] = np.roll(layer[y:y + h], sh, axis=1)
            a[y:y + h] = np.roll(a[y:y + h], sh, axis=1)
        if g > 0.3:
            layer = np.maximum(layer, 0.8 * line_blur(layer, 34 * g, 0))
            a = np.maximum(a, 0.8 * line_blur(a, 34 * g, 0))
    img[:] = np.maximum(img * (1 - a) + layer, img)  # glow only ever brightens what is behind it


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


# ---------------------------------------------------------------- transitions
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


def wipe_in(img, nxt, cover, smear, f):
    """The next shot smears in from the right edge over `cover` of the frame, behind a ragged soft seam."""
    edge = W * (1 - cover) + cv2.resize(np.random.default_rng(f).standard_normal((12, 1)).astype(np.float32),
                                        (1, W), interpolation=cv2.INTER_CUBIC) * 16
    xx = np.arange(W, dtype=np.float32)[None, :]
    a = np.clip((xx - edge + 24) / 48, 0, 1)
    a = a * a * (3 - 2 * a)
    near = 0.7 * np.clip(1 - np.abs(xx - edge) / 110, 0, 1)  # the outgoing picture streaks along the seam too
    img = img * (1 - near) + line_blur(img, smear * 0.5, 0) * near
    return img * (1 - a) + line_blur(nxt, smear, 0) * a


def smear(img, blur=0, echo=None, dark=1.0):
    """Horizontal smear with an optional offset echo, for the flicker frames after a glitch cut."""
    img = line_blur(img, blur, 0)
    if echo:
        off, mix = echo
        ghost = cv2.warpAffine(img, np.float32([[1, 0, off], [0, 1, 0]]), (W, W), borderMode=cv2.BORDER_REFLECT)
        img = (1 - mix) * img + mix * ghost
    return img * dark


def tone(img, g):
    """Exposure as a curve: g < 1 darkens midtones but keeps highlights, g > 1 lifts them but keeps black."""
    img = np.clip(img, 0, 1)
    if g < 0.999:
        return img ** (1 / g)
    if g > 1.001:
        return 1 - (1 - img) ** g
    return img


def glitch(img, g, f):
    """Horizontal slice offsets with a light smear; g ~ 0..1 intensity."""
    img = img.copy()
    r = np.random.default_rng(f * 7 + 3)
    for _ in range(int(12 * g) + 2):
        y = r.integers(0, W - 40)
        h, s = r.integers(6, 50), int(r.integers(-90, 90) * g)
        img[y:y + h] = np.roll(img[y:y + h], s, axis=1)
    return line_blur(img, 26 * g, 0)


# ---------------------------------------------------------------- frame assembly
SRC = None


def compose(shot, src, f):
    """The shot's flat composite (background, cut-out subject, graphics) at frame f, before the camera."""
    global SRC
    SRC = src
    n = shot["end"] - shot["start"]
    k = min(max(f - shot["start"], 0), n + 2)
    if src is not None:
        lum, mask, is_ph = src.get(min(k, n - 1))
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
    return img


def photograph(i, srcs, f):
    """Shot i at frame f through its camera: motion blur, defocus, glitch, exposure."""
    shot = SHOTS[i]
    img, st = camera.shoot(compose(shot, srcs[i], f), i, f)
    if st["glitch"] > 0.01:
        img = glitch(img, st["glitch"], f)
    flicker = CUTS[shot["start"]].get("smear_in", {}).get(f - shot["start"])
    if flicker:
        img = smear(img, **flicker)
    img = tone(img, st["gain"]) + st["lift"]
    screen(shot, f, img)
    return img


def neighbour(j, srcs, f):
    """Shot j at frame f, wrapping around the loop: before the first shot comes the last one, one loop
    later in its own timeline, and after the last shot comes the first."""
    if j < 0:
        return photograph(len(SHOTS) - 1, srcs, f + N_FRAMES)
    if j >= len(SHOTS):
        return photograph(0, srcs, f - N_FRAMES)
    return photograph(j, srcs, f)


def subject_matte(i, srcs, f):
    """Shot i's subject matte, as an alpha in frame coordinates at frame f."""
    shot = SHOTS[i]
    k = min(max(f - shot["start"], 0), shot["end"] - shot["start"] - 1)
    cam = camera.matrix(camera.state(i, f))
    return cv2.warpAffine(srcs[i].get(k)[1], cam, (W, W), flags=cv2.INTER_LINEAR, borderValue=0)


def designed(comp, a, b, f, c, j_out, srcs):
    """One of the designed transitions (transitions.py) at frame f of the cut at frame c."""
    pre, post = comp["pre"], comp.get("post", 0)
    p = (f - (c - pre) + 0.5) / (pre + post)
    dp = comp.get("shutter", 0.8) / (pre + post)  # shutter (frames), as a fraction of the transition
    kind = comp["type"]
    if kind == "portal":
        x, y, s, ang, _ = fly_pose(comp["fly"], f)
        cam = camera.matrix(camera.state(j_out % len(SHOTS), f))
        return transitions.portal(a, b, f, c, pre, FLY[comp["fly"]][0], (x, y, s, ang), cam)
    if kind == "phone_wipe":
        return transitions.phone_wipe(a, b, p, dp, f, c, pre, post, comp["phone"], comp["scale"], comp["lean"])
    if kind == "pop_in":
        return transitions.pop_in(a, b, p, dp, subject_matte((j_out + 1) % len(SHOTS), srcs, f))
    if kind == "app_close":  # the card lands on an icon of the incoming shot, found through its camera
        j_in = (j_out + 1) % len(SHOTS)
        shot = SHOTS[j_in]
        x, y, s, _ = float_pose(comp["icon"], f, max(f - shot["start"], 0), shot["end"] - shot["start"])
        cam = camera.matrix(camera.state(j_in, f))
        tx, ty = cam @ np.array([x, y, 1.0])
        icon_w = props.load(FLOAT[comp["icon"]][0])[1].shape[1] * s * math.hypot(cam[0, 0], cam[0, 1])
        return transitions.app_close(a, b, p, dp, (tx, ty), icon_w)
    return getattr(transitions, kind)(a, b, p, dp)


def render_frame(i, srcs, f):
    shot = SHOTS[i]
    c0, c1 = shot["start"], shot["end"]
    into, out_of = CUTS[c0], CUTS[c1]
    if "comp" in out_of and f >= c1 - out_of["comp"]["pre"]:
        return finish(designed(out_of["comp"], photograph(i, srcs, f), neighbour(i + 1, srcs, f), f, c1, i, srcs), f)
    if "comp" in into and f < c0 + into["comp"].get("post", 0):
        return finish(designed(into["comp"], neighbour(i - 1, srcs, f), photograph(i, srcs, f), f, c0, i - 1, srcs), f)
    img = photograph(i, srcs, f)
    # two-frame overlap across motion cuts: both shots streaking at once hides the splice
    if f == c0 and into.get("exit") and into.get("overlap", True):
        img = 0.76 * img + 0.24 * neighbour(i - 1, srcs, f)
    if f == c1 - 1 and out_of.get("exit") and out_of.get("overlap", True):
        img = 0.76 * img + 0.24 * neighbour(i + 1, srcs, f)
    wipe = out_of.get("wipe")
    if wipe and i + 1 < len(SHOTS) and f >= c1 - len(wipe["cover"]):
        j = f - (c1 - len(wipe["cover"]))
        img = wipe_in(img, photograph(i + 1, srcs, f), wipe["cover"][j], wipe["smear"][j], f)
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


def loop_audio(path, seconds, xfade=0.045, rate=44100, edge=0.0015):
    """The source's audio cut to the loop length as a temp WAV. Its first `xfade` seconds crossfade from
    the audio that follows the loop point into the real start, so on repeat the sound runs straight
    from the end into the beginning.

    The length is rounded down to whole AAC frames (1024 samples, 2.6 ms short of 262 frames at 44.1 kHz):
    a partial last frame gets zero padding that only some players trim, and FFmpeg-based tools (most
    upload pipelines) don't, which leaves a 21 ms dropout at every repeat. With whole frames there is no
    padding; players that loop on the video length see a 2.6 ms gap, softened by `edge`-long fades."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "2", "-ar", str(rate), "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    src = np.frombuffer(raw, np.float32).reshape(-1, 2)
    n, fade = int(seconds * rate) // 1024 * 1024, int(round(xfade * rate))
    out = np.zeros((n, 2), np.float32)
    out[:min(n, len(src))] = src[:n]
    tail = src[n:n + fade]
    if len(tail):
        u = np.linspace(0, 1, len(tail), dtype=np.float32)[:, None] * (np.pi / 2)
        out[:len(tail)] = out[:len(tail)] * np.sin(u) + tail * np.cos(u)  # equal-power crossfade
    e = int(edge * rate)
    ramp = (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, e, dtype=np.float32)))[:, None]
    out[:e] *= ramp
    out[-e:] *= ramp[::-1]
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(out, -1, 1) * 32767).astype("<i2").tobytes())
    return tmp.name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out.mp4"))
    ap.add_argument("--audio", default=None, help="file whose audio track is used (the reference edit)")
    ap.add_argument("--debug-frames", default=None)
    a = ap.parse_args()

    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{W}",
           "-r", str(FPS), "-i", "-"]
    audio = loop_audio(a.audio, N_FRAMES / FPS) if a.audio else None
    if audio:
        cmd += ["-i", audio, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-crf", "17", "-preset", "slow", "-pix_fmt", "yuv420p",
            "-t", f"{N_FRAMES / FPS:.3f}", "-movflags", "+faststart", a.out]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    if a.debug_frames:
        os.makedirs(a.debug_frames, exist_ok=True)
    srcs = [subject_for(s) for s in SHOTS]
    for i, shot in enumerate(SHOTS):
        kind = "none" if srcs[i] is None else type(srcs[i]).__name__
        print(f"{shot['id']} f{shot['start']}-{shot['end'] - 1} source={kind}", flush=True)
        for f in range(shot["start"], shot["end"]):
            fr = render_frame(i, srcs, f)
            enc.stdin.write(fr.tobytes())
            if a.debug_frames:
                cv2.imwrite(os.path.join(a.debug_frames, f"f{f:03d}.png"), fr)
    enc.stdin.close()
    enc.wait()
    if audio:
        os.remove(audio)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
