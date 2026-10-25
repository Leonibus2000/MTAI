"""Designed transitions, where the edit departs from the reference's camera-move cuts.

Each one blends the outgoing frame `a` and the incoming frame `b` (both already shot through their
own cameras) over `pre` frames before the cut and `post` frames after it, so the cut itself stays on
the music hit. `p` runs from 0 to 1 across the whole transition. Geometry that moves fast is motion
blurred by averaging the blend at several instants inside the shutter.
"""
import math

import cv2
import numpy as np

import props
from gfx import W

_YY, _XX = np.mgrid[0:W, 0:W].astype(np.float32) + 0.5


def _clip(t):
    return min(max(t, 0.0), 1.0)


def _ease_out(t):
    t = _clip(t)
    return 1 - (1 - t) ** 3


def _smooth(t):
    t = _clip(t)
    return t * t * (3 - 2 * t)


def rounded_box(cx, cy, hw, hh, r, angle=0.0):
    """Signed distance (px, negative inside) to a rounded rectangle centred at (cx, cy), half size
    (hw, hh), corner radius r, rotated by `angle` degrees (OpenCV sense: positive turns content
    counter-clockwise on screen)."""
    th = math.radians(angle)
    dx, dy = _XX - cx, _YY - cy
    u = dx * math.cos(th) - dy * math.sin(th)
    v = dx * math.sin(th) + dy * math.cos(th)
    r = max(0.0, min(r, hw, hh))
    qx, qy = np.abs(u) - (hw - r), np.abs(v) - (hh - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def _fill(d, aa=1.0):
    return np.clip(0.5 - d / aa, 0, 1)


def _keyline(d, width=3.0):
    """White die-cut line just outside a shape, matching the subject's sticker outline."""
    return _fill(d - width) - _fill(d)


def _shutter(fn, p, dp, n=3, travel=None, step=5.0, n_max=24):
    """Average fn over the shutter [p - dp/2, p + dp/2]. With `travel(q0, q1)` (px an edge moves across
    the shutter), the sample count adapts so fast geometry blurs smoothly instead of ghosting."""
    if travel is not None:
        n = int(min(max(math.ceil(travel(p - dp / 2, p + dp / 2) / step), 3), n_max))
    if n <= 1 or dp <= 0:
        return fn(p)
    return sum(fn(q) for q in np.linspace(p - dp / 2, p + dp / 2, n)) / n


# ---------------------------------------------------------------- island: Dynamic Island expand
def _island_geom(q):
    if q < 0.35:
        e = _ease_out(q / 0.35)
        hh = 15 + 11 * e
        return 35 + 80 * e, hh, 40.0, hh
    e = _ease_out((q - 0.35) / 0.65)
    ov = 16 * math.sin(math.pi * _clip((q - 0.35) / 0.65))  # overshoot past the frame edge
    return (115 + (W / 2 + ov - 115) * e, 26 + (W / 2 + ov - 26) * e, 40 + (W / 2 - 40) * e,
            26 * (1 - e) + 4 * e)


def island(a, b, p, dp):
    """The next shot plays inside a pill at the top of the screen, like an iPhone Live Activity,
    which then expands into the full frame."""
    def travel(q0, q1):
        g0, g1 = _island_geom(q0), _island_geom(q1)
        return max(abs(g1[0] - g0[0]), abs(g1[1] - g0[1]) + abs(g1[2] - g0[2]))

    def at(q, keyline=False):
        hw, hh, cy, r = _island_geom(q)
        d = rounded_box(W / 2, cy, hw, hh, r)
        m = _fill(d)
        s = max(2 * hw, 2 * hh) / W  # the shot fills the window, scaled with it
        M = np.float32([[s, 0, W / 2 - s * W / 2], [0, s, cy - s * W / 2]])
        win = cv2.warpAffine(b, M, (W, W), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        if q < 0.35:
            win = win * 0.75
        back = cv2.warpAffine(a, cv2.getRotationMatrix2D((W / 2, W / 2), 0, 1 - 0.05 * q), (W, W),
                              borderMode=cv2.BORDER_REFLECT) * (1 - 0.45 * q)
        shadow = cv2.GaussianBlur(m, (0, 0), 10)
        out = back * (1 - 0.6 * shadow)
        return out * (1 - m) + win * m
    out = _shutter(at, p, dp, travel=travel)
    hw, hh, cy, r = _island_geom(p)  # sharp white keyline at the current edge, fading while it moves fast
    k = _keyline(rounded_box(W / 2, cy, hw, hh, r)) / (1 + travel(p - dp / 2, p + dp / 2) / 40)
    return out * (1 - k) + 0.96 * k


# ---------------------------------------------------------------- strips: alternating vertical slats
def strips(a, b, p, dp, n=6, stagger=0.1, span=0.45):
    """The frame splits into vertical slats; alternate slats slide the next shot in from the top and
    the bottom, pushing the old one out, staggered left to right."""
    out = np.empty_like(a)
    sw = W // n
    for j in range(n):
        q = _clip((p - j * stagger) / span)
        e = _ease_out(q)
        xs = slice(j * sw, W if j == n - 1 else (j + 1) * sw)
        if j % 2 == 0:  # from the top: next shot stacked above the old one
            stack, start = np.vstack([b[:, xs], a[:, xs]]), W * (1 - e)
        else:           # from the bottom
            stack, start = np.vstack([a[:, xs], b[:, xs]]), W * e
        s0 = int(round(start))
        col = stack[s0:s0 + W]
        speed = W * 3 * (1 - q) ** 2 / span * dp  # px travelled during the shutter
        L = int(min(0.5 * speed, 60))
        if 0 < q < 1 and L > 2:
            col = cv2.blur(col, (1, L))
        out[:, xs] = col
    lines = np.zeros((W, W), np.float32)
    for j in range(1, n):
        lines[:, j * sw - 1:j * sw + 2] = 1.0
    o = 0.95 * math.sin(math.pi * _clip(p))
    return out * (1 - lines * o) + 0.96 * lines * o


# ---------------------------------------------------------------- crt: TV switch-off / switch-on
def _squeeze(img, sx, sy):
    w, h = max(1, int(round(W * sx))), max(1, int(round(W * sy)))
    small = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA if (sx < 1 or sy < 1) else cv2.INTER_LINEAR)
    out = np.zeros((W, W), np.float32)
    x0, y0 = (W - w) // 2, (W - h) // 2
    sx0, sy0 = max(0, -x0), max(0, -y0)
    dx0, dy0 = max(0, x0), max(0, y0)
    cw, ch = min(w - sx0, W - dx0), min(h - sy0, W - dy0)
    out[dy0:dy0 + ch, dx0:dx0 + cw] = small[sy0:sy0 + ch, sx0:sx0 + cw]
    return out


def crt(a, b, p, dp):
    """The old shot collapses into a bright line like a switched-off CRT; the next one powers on
    from a line, overshoots and settles, with scanlines while it warms up."""
    def at(q):
        if q < 0.5:
            t = q / 0.5
            src = a
            sy = np.interp(t, [0, .17, .5, .83, 1], [1, .55, .12, .012, .004])
            sx = np.interp(t, [0, .6, .83, 1], [1, 1, .55, .2])
            g = np.interp(t, [0, .17, .5, .83, 1], [1, 1.3, 2.2, 4.0, 4.0])
        else:
            t = (q - 0.5) / 0.5
            src = b
            sy = np.interp(t, [0, .17, .5, .83, 1], [.004, .012, .3, 1.04, 1.0])
            sx = np.interp(t, [0, .17, .4, 1], [.3, .7, 1, 1])
            g = np.interp(t, [0, .17, .5, .83, 1], [4, 3.0, 1.7, 1.15, 1])
        pic = _squeeze(src, sx, sy) * g
        glow = cv2.GaussianBlur(pic, (0, 0), sigmaX=18 if sy < 0.05 else 8, sigmaY=3 if sy < 0.05 else 8)
        out = pic + 1.0 * glow
        if sy < 0.98 or q >= 0.5 and t < 0.9:
            out = out * np.where(np.arange(W)[:, None] % 3 == 0, 0.72, 1.0)
        flare = math.exp(-((q - 0.5) / 0.09) ** 2)  # white flare at the centre when the picture is a line
        if flare > 0.02:
            out = out + flare * np.exp(-(((_XX - W / 2) / (60 + 200 * flare)) ** 2 + ((_YY - W / 2) / 6) ** 2))
        return out
    return _shutter(at, p, dp, n=5)


# ---------------------------------------------------------------- mosaic: pixelate through blocks
_NOISE = np.random.default_rng(7).random((2, 96, 96)).astype(np.float32)


def mosaic(a, b, p, bmax=48):
    """Both shots break into big pixel blocks; the blocks flip to the next shot in a scattered order,
    with LED-style gaps between them, then resolve back to full resolution."""
    bs = int(round(1 + (bmax - 1) * (1 - abs(2 * p - 1)) ** 1.5))
    if bs <= 1:
        return a if p < 0.5 else b
    n = math.ceil(W / bs)
    sa = cv2.resize(a, (n, n), interpolation=cv2.INTER_AREA)
    sb = cv2.resize(b, (n, n), interpolation=cv2.INTER_AREA)
    th = 0.5 + (cv2.resize(_NOISE[0], (n, n), interpolation=cv2.INTER_NEAREST) - 0.5) * 0.36
    small = np.where(p > th, sb, sa)
    if bs >= 8:
        small = np.round(small * 7) / 7
        spark = cv2.resize(_NOISE[1], (n, n), interpolation=cv2.INTER_NEAREST) > 0.93
        small = np.where(spark, np.clip(small + 0.25 * math.sin(math.pi * p), 0, 1), small)
    big = cv2.resize(small, (n * bs, n * bs), interpolation=cv2.INTER_NEAREST)[:W, :W]
    if bs >= 10:
        grid = ((np.arange(W) % bs) == 0)
        big = big * np.where(grid[:, None] | grid[None, :], 0.45, 1.0)
    return big


# ---------------------------------------------------------------- phone wipe: a real phone sweeps across
def phone_wipe(a, b, p, dp, f, c, pre, post, name, scale, lean):
    """A giant real phone slams in from the right, all but stops in the middle of the frame for the
    frames around the cut (so it reads as a product shot), then shoots out to the left. The seam runs
    along the phone's long axis, under the phone: behind it the next shot is revealed."""
    total = pre + post

    def pose(q):
        D = W / 2 + props.SIZE * scale * 0.5 + 20
        if q < 0.5:
            x = W / 2 + D * (1 - _ease_out(q / 0.5))
        else:
            x = W / 2 - D * _clip((q - 0.5) / 0.5) ** 3
        tilt = lean * abs(x - W / 2) / D  # leans into its motion, upright while it pauses
        return x, W / 2 + 10 * math.sin(math.pi * q), scale, props.upright(name) + 3 + tilt

    def seam(q):
        x, y, _, ang = pose(q)
        th = math.radians(ang - props.upright(name))  # rotation away from upright
        nx, ny = math.cos(th), -math.sin(th)          # normal to the phone's long axis, pointing right
        side = (_XX - x) * nx + (_YY - y) * ny
        m = np.clip(side / 2 + 0.5, 0, 1)
        return a * (1 - m) + b * m
    out = _shutter(seam, p, dp, n=5)

    def path(t):
        x, y, s, ang = pose((t - (c - pre) + 0.5) / total)
        return x, y, s, ang, 1.0
    props.draw_moving(out, name, path, f, size=props.SIZE * 3, max_samples=12)
    return out


# ---------------------------------------------------------------- portal: zoom into a phone's screen
def portal(a, b, f, c, pre, phone, pose, cam, dp_frames=0.8):
    """The camera dives into the screen of a phone already in the shot, where the next shot is
    playing; when the screen fills the frame, the cut lands on that shot.

    pose: (x, y, scale, angle) of the phone prop in the outgoing shot's composite at frame f.
    cam:  the outgoing shot's 2x3 camera matrix at frame f (composite -> frame)."""
    x, y, s, ang = pose
    hi = props.SIZE * 4                         # high-resolution copy of the prop for the close-up
    lum, alpha, _ = props.load(phone, hi)
    h, w = alpha.shape
    k = props.SIZE / hi
    P = cv2.getRotationMatrix2D((w / 2, h / 2), ang, s * k)
    P[0, 2] += x - w / 2
    P[1, 2] += y - h / 2
    F = np.vstack([cam, [0, 0, 1]]) @ np.vstack([P, [0, 0, 1]])   # prop pixels -> frame
    x0, y0, x1, y1, rr = props.META[phone]["screen"]
    sc = F @ np.array([(x0 + x1) / 2 * w, (y0 + y1) / 2 * h, 1.0])
    s_f = math.hypot(F[0, 0], F[0, 1])
    a_f = math.degrees(math.atan2(F[0, 1], F[0, 0]))
    sw, sh, sr = (x1 - x0) * w * s_f, (y1 - y0) * h * s_f, rr * w * s_f
    zmax = W / sw

    def geom(q):
        e = _clip(q) ** 2                        # accelerating dive
        return e, sc[0] + (W / 2 - sc[0]) * e, sc[1] + (W / 2 - sc[1]) * e, zmax ** e

    def travel(q0, q1):  # how far the screen's corners move across the shutter
        (_, x0_, y0_, z0), (_, x1_, y1_, z1) = geom(q0), geom(q1)
        return abs(x1_ - x0_) + abs(y1_ - y0_) + abs(z1 - z0) * math.hypot(sw, sh) / 2

    def at(q):
        e, tx, ty, _ = geom(q)
        Z = cv2.getRotationMatrix2D((float(sc[0]), float(sc[1])), -a_f * e, zmax ** e)
        Z[0, 2] += tx - sc[0]
        Z[1, 2] += ty - sc[1]
        out = cv2.warpAffine(a, Z, (W, W), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        ZF = np.vstack([Z, [0, 0, 1]]) @ F
        pl = cv2.warpAffine(lum, ZF[:2], (W, W), flags=cv2.INTER_LINEAR, borderValue=0)
        pa = cv2.warpAffine(alpha, ZF[:2], (W, W), flags=cv2.INTER_LINEAR, borderValue=0)
        out = out * (1 - pa) + pl * pa
        z = zmax ** e
        ang_out = a_f * (1 - e)
        Mb = cv2.getRotationMatrix2D((W / 2, W / 2), ang_out, sw * z / W)
        Mb[0, 2] += tx - W / 2
        Mb[1, 2] += ty - W / 2
        shot = cv2.warpAffine(b, Mb, (W, W), flags=cv2.INTER_LINEAR, borderValue=0)  # black bars above/below
        m = _fill(rounded_box(tx, ty, sw * z / 2, sh * z / 2, sr * z, ang_out))
        on = max(0.0, 1 - (f - (c - pre)) / 2.0)  # the screen switches on with a flash
        return out * (1 - m) + np.clip(shot + 0.6 * on, 0, 1) * m

    q = (f - (c - pre) + 0.8) / pre
    return _shutter(at, q, dp_frames / pre, travel=travel, step=6.0)
