"""Subject mattes for the cut-out look.

BiRefNet-portrait gives the person. For shots where he holds a device, BiRefNet-general adds the
objects that touch him, so his fingers don't float with the phone cut away. The raw mattes are then
cleaned: faint ghosts are cut, fragments not attached to him are dropped, pinholes are filled and the
contour is smoothed into a sticker edge.

CPU inference takes about a minute per image, so mattes are cached next to the stills
(footage/<id>_person.png, footage/<id>_general.png). Each inference runs in its own process with
onnxruntime's memory arena off, which keeps the peak around 8 GB.

  python3 cutout.py <still.jpg> person|general     # compute one cached matte
"""
import os
import subprocess
import sys

import cv2
import numpy as np

MODELS = {"person": "birefnet-portrait", "general": "birefnet-general"}


def model_file(kind):
    from rembg.sessions import sessions_class
    cls = next(c for c in sessions_class if c.name() == MODELS[kind])
    return cls.download_models()


def infer(kind, src, dst, size=1024):
    import onnxruntime as ort
    from PIL import Image
    so = ort.SessionOptions()
    so.enable_cpu_mem_arena = False
    so.enable_mem_pattern = False
    sess = ort.InferenceSession(model_file(kind), so, providers=["CPUExecutionProvider"])
    img = Image.open(src).convert("RGB")
    x = np.asarray(img.resize((size, size), Image.LANCZOS), np.float32)
    x = (x / max(x.max(), 1e-6) - (0.485, 0.456, 0.406)) / (0.229, 0.224, 0.225)
    out = sess.run(None, {sess.get_inputs()[0].name: x.transpose(2, 0, 1)[None].astype(np.float32)})[0]
    out = 1 / (1 + np.exp(-np.squeeze(out[:, 0])))
    out = (out - out.min()) / max(out.max() - out.min(), 1e-6)
    Image.fromarray((out * 255).astype(np.uint8)).resize(img.size, Image.LANCZOS).save(dst)


def cached(still, kind):
    """Path of the cached matte for still, computing it in a subprocess if missing or stale."""
    dst = f"{os.path.splitext(still)[0]}_{kind}.png"
    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(still):
        print(f"  matting {os.path.basename(still)} ({MODELS[kind]}) ...", flush=True)
        subprocess.run([sys.executable, os.path.abspath(__file__), still, kind], check=True)
    return dst


def _smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def clean(alpha, keep_ratio=0.05, hole_frac=0.004, smooth=1.4):
    """Hard, sticker-like matte from a soft one: no ghosts, no stray islands, no pinholes."""
    h, w = alpha.shape
    solid = _smoothstep(0.3, 0.6, alpha) > 0.5
    n, lab, stats, _ = cv2.connectedComponentsWithStats(solid.astype(np.uint8), connectivity=8)
    if n > 1:
        areas = stats[1:, cv2.CC_STAT_AREA]
        keep = np.r_[False, areas >= keep_ratio * areas.max()]
        solid = keep[lab]
    holes = (~solid).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(holes, connectivity=4)
    for j in range(1, n):
        x, y, bw, bh, area = stats[j]
        inside = x > 0 and y > 0 and x + bw < w and y + bh < h
        if inside and area < hole_frac * h * w:
            solid[lab == j] = True
    soft = cv2.GaussianBlur(solid.astype(np.float32), (0, 0), smooth)
    return _smoothstep(0.38, 0.62, soft).astype(np.float32)


def held_objects(person, general, reach=14, min_area=600):
    """Parts of the general matte that are not him but touch him: phones, consoles, watches in hand."""
    p = person > 0.5
    extra = (general > 0.5) & ~p
    near = cv2.dilate(p.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * reach + 1,) * 2)) > 0
    n, lab, stats, _ = cv2.connectedComponentsWithStats(extra.astype(np.uint8), connectivity=8)
    out = np.zeros_like(p)
    for j in range(1, n):
        comp = lab == j
        if stats[j, cv2.CC_STAT_AREA] >= min_area and (comp & near).any():
            out |= comp
    return out


def matte(still, mode="person", size=576, drop=(), erase=(), add=()):
    """Final matte at size x size. mode 'held' adds devices touching him. For anything the models get
    wrong (in size-scaled pixels): add = polygons forced in (a phone the model only half found),
    erase = polygons cut out, drop = (x, y) points whose connected part is removed after cleaning."""
    person = cv2.resize(cv2.imread(cached(still, "person"), 0), (size, size), interpolation=cv2.INTER_AREA) / 255.0
    alpha = person
    if mode == "held":
        general = cv2.resize(cv2.imread(cached(still, "general"), 0), (size, size), interpolation=cv2.INTER_AREA) / 255.0
        alpha = np.maximum(person, held_objects(person, general).astype(np.float32))
    if add:
        fill = np.zeros((size, size), np.float32)
        cv2.fillPoly(fill, [np.array(p, np.int32) for p in add], 1.0, cv2.LINE_AA)
        alpha = np.maximum(alpha, fill)
    if erase:
        cut = np.zeros((size, size), np.uint8)
        cv2.fillPoly(cut, [np.array(p, np.int32) for p in erase], 1)
        alpha = alpha * (1 - cut)
    m = clean(alpha.astype(np.float32))
    for x, y in drop:
        n, lab = cv2.connectedComponents((m > 0.5).astype(np.uint8))
        j = lab[int(y), int(x)]
        if j:
            m[lab == j] = 0
    return m


if __name__ == "__main__":
    still, kind = sys.argv[1], sys.argv[2]
    infer(kind, still, f"{os.path.splitext(still)[0]}_{kind}.png")
