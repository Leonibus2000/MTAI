"""Camera motion, modelled on optical-flow measurements of the reference edit.

Each shot has a continuous camera path: an arrival move that carries on from the previous cut and
decelerates, a steady push-in with rotation drift, handheld jitter that bursts after cuts and music
accents, and an exit move that accelerates into the next cut. A frame is the average of the shot
sampled at many instants inside the shutter interval, so motion blur follows the real path: radial
for zooms, arcs for spins, streaks for whips.
"""
import math

import cv2
import numpy as np

from gfx import W
from timeline import CUTS, N_FRAMES, ONSETS, SHOTS

SHUTTER = 0.8      # fraction of a frame the virtual shutter is open
STEP_PX = 2.0      # one sub-frame sample per this many pixels of travel
MAX_SAMPLES = 28

# Handheld jitter: one random target per frame joined by a Catmull-Rom spline (continuous, so it blurs).
_JIT = np.random.default_rng(21).standard_normal((N_FRAMES + 32, 3)).astype(np.float32)


def _jitter(t):
    i = int(math.floor(t))
    u = t - i
    p0, p1, p2, p3 = (_JIT[min(max(j + 8, 0), len(_JIT) - 1)] for j in (i - 1, i, i + 1, i + 2))
    return 0.5 * (2 * p1 + (p2 - p0) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                  + (3 * p1 - p0 - 3 * p2 + p3) * u ** 3)


def _decay(t, events, tau):
    return sum(a * math.exp(-(t - e) / tau) for e, a in events if 0 <= t - e < 6 * tau)


CUT_SHAKE = [(c, spec.get("shake", 0)) for c, spec in CUTS.items()]
BEATS = [(o, 1.0) for o in ONSETS]


def state(i, t):
    """Camera state of shot i at (fractional, global) frame time t; t may run past either end of the shot."""
    shot = SHOTS[i]
    cam = shot["cam"]
    c0, c1 = shot["start"], shot["end"]
    n = c1 - c0
    k = t - c0
    st = dict(logz=cam.get("zoom0", 0.0) + cam.get("push", 0.0) * k, rot=cam.get("rot0", 0.0) + cam.get("spin", 0.0) * k,
              tx=cam.get("pan", (0, 0))[0] * k, ty=cam.get("pan", (0, 0))[1] * k,
              focus=shot.get("focus", (W / 2, W / 2)), sigma=0.0, gain=1.0, lift=0.0, glitch=0.0,
              crash=0.0, crash_focus=(W / 2, W / 2))
    ex = cam.get("exposure", 1.0)
    st["gain"] = ex[0] + (ex[1] - ex[0]) * min(max(k / max(n - 1, 1), 0), 1) if isinstance(ex, tuple) else ex

    # Moves are centred on the splice (half a frame before the first new frame): v = 1 there and 0 once
    # settled; u = 0 when an exit starts and 1 at the splice. Both run past 1 on the overlap frames.
    for kind, p in CUTS[c0].get("arrive", []):
        if kind == "push":
            st["logz"] += p["amount"] * (1 - math.exp(-max(k, -2.0) / p.get("T", 4)))
            continue
        if kind == "pull":
            st["logz"] += p["amount"] * math.exp(-max(k, -2.0) / p.get("T", 4))
            continue
        v = max(0.0, 1 - (k + 0.5) / p["frames"])
        e = v * v
        if kind == "whip":
            a = math.radians(p["angle"])
            st["tx"] -= p["dist"] * e * math.cos(a)
            st["ty"] -= p["dist"] * e * math.sin(a)
        elif kind == "spin":
            st["rot"] += p["deg"] * e
        elif kind == "defocus":
            st["sigma"] += p["sigma"] * e
            st["gain"] *= 1 - p.get("dark", 0.35) * min(e, 1)

    for kind, p in CUTS.get(c1, {}).get("exit", []):
        u = (t - (c1 - 0.5 - p["frames"])) / p["frames"]
        if u <= 0:
            continue
        e = u * u
        if kind == "zoom":
            st["logz"] += p["amount"] * e
        elif kind == "pull":
            st["logz"] -= p["amount"] * e
        elif kind == "crash":  # extra zoom about its own point, stacked on the shot's camera
            st["crash"] += p["amount"] * e
            st["crash_focus"] = p["focus"]
        elif kind == "whip":
            a = math.radians(p["angle"])
            st["tx"] += p["dist"] * e * math.cos(a)
            st["ty"] += p["dist"] * e * math.sin(a)
        elif kind == "spin":
            st["rot"] += p["deg"] * e
        elif kind == "defocus":
            st["sigma"] += p["sigma"] * e
        elif kind == "dip":
            st["gain"] *= 1 - p["amount"] * min(u, 1)
        elif kind == "bright":
            st["gain"] *= 1 + p["amount"] * e
        elif kind == "glitch":
            st["glitch"] = max(st["glitch"], min(u, 1.2))

    for kk, frames, amount, focus in cam.get("zoom_to", []):  # push into a point of the shot and stay
        if k > kk:
            q = min((k - kk) / frames, 1.0)
            st["crash"] += amount * q * q
            st["crash_focus"] = focus

    for kk, frames, dx, dy in cam.get("jolt", []):  # out and back: heavy streaks both ways, then sharp
        if kk < k < kk + frames:
            b = math.sin(math.pi * (k - kk) / frames)
            st["tx"] += dx * b
            st["ty"] += dy * b

    amp = cam.get("shake", 1.5) + _decay(t, CUT_SHAKE, 3.0) + cam.get("beat", 6.5) * _decay(t, BEATS, 2.5)
    j = _jitter(t)
    st["tx"] += amp * j[0]
    st["ty"] += amp * j[1]
    st["rot"] += 0.12 * amp * j[2]
    st["logz"] += 0.02 * _decay(t, BEATS, 2.0)

    for c, spec in CUTS.items():  # white flash centred on the cut
        if spec.get("flash") and abs(t - c + 0.5) < 3:
            st["lift"] += spec["flash"] * math.exp(-abs(t - c + 0.5) / 0.9)
    return st


def matrix(st):
    M = cv2.getRotationMatrix2D(tuple(map(float, st["focus"])), st["rot"], math.exp(st["logz"]))
    M[0, 2] += st["tx"]
    M[1, 2] += st["ty"]
    if st["crash"]:  # the crash target is a point in the shot; follow it through the camera move
        px, py = M @ np.array([*st["crash_focus"], 1.0])
        C = cv2.getRotationMatrix2D((float(px), float(py)), 0, math.exp(st["crash"]))
        M = C @ np.vstack([M, [0, 0, 1]])
    return M


_CORNERS = np.array([[0, 0, 1], [W, 0, 1], [0, W, 1], [W, W, 1], [W / 2, W / 2, 1]], np.float32).T


def shoot(img, i, f):
    """Photograph shot i's composite at frame f through its moving camera, with motion blur."""
    t0, t1 = f - SHUTTER / 2, f + SHUTTER / 2
    travel = np.abs(matrix(state(i, t1)) @ _CORNERS - matrix(state(i, t0)) @ _CORNERS).max()
    mid = state(i, f)
    travel = max(travel, np.abs(matrix(mid) @ _CORNERS - matrix(state(i, t0)) @ _CORNERS).max() * 2)
    n = int(min(max(math.ceil(travel / STEP_PX), 1), MAX_SAMPLES))
    times = [f] if n == 1 else np.linspace(t0, t1, n)
    acc = np.zeros_like(img)
    for t in times:
        acc += cv2.warpAffine(img, matrix(state(i, t)), (W, W), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REFLECT)
    out = acc / len(times)
    if mid["sigma"] > 0.3:
        out = cv2.GaussianBlur(out, (0, 0), mid["sigma"])
    return out, mid
