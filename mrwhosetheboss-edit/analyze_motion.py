"""Optical-flow camera-motion, sharpness and brightness per frame for the reference and a render.

usage (from the folder holding ref/ref.mp4): python3 analyze_motion.py <render.mp4> <out.json>
"""
import sys, cv2, numpy as np, json
def frames(path):
    cap = cv2.VideoCapture(path); out = []
    while True:
        ok, f = cap.read()
        if not ok: break
        out.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
    return out
def analyze(path):
    F = frames(path); S = 192; k = 576 / S
    rows = []
    small = [cv2.resize(f, (S, S), interpolation=cv2.INTER_AREA) for f in F]
    yy, xx = np.mgrid[8:S-8:6, 8:S-8:6]
    pts = np.stack([xx.ravel(), yy.ravel()], 1).astype(np.float32)
    for i, f in enumerate(F):
        g144 = cv2.resize(f, (144, 144), interpolation=cv2.INTER_AREA).astype(np.float32)
        sharp = float(cv2.Laplacian(g144, cv2.CV_32F).var())
        r = dict(i=i, sharp=sharp, luma=float(f.mean()))
        if i + 1 < len(F):
            fl = cv2.calcOpticalFlowFarneback(small[i], small[i + 1], None, 0.5, 4, 21, 3, 5, 1.1, 0)
            d = fl[pts[:, 1].astype(int), pts[:, 0].astype(int)]
            M, inl = cv2.estimateAffinePartial2D(pts, pts + d, method=cv2.RANSAC, ransacReprojThreshold=2.0)
            if M is not None:
                sc = float(np.hypot(M[0, 0], M[1, 0])); rot = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
                c = np.array([S / 2, S / 2]); tc = M[:, :2] @ c + M[:, 2] - c
                r.update(tx=float(tc[0] * k), ty=float(tc[1] * k), scale=sc, rot=rot,
                         flow=float(np.median(np.hypot(d[:, 0], d[:, 1])) * k), inl=float(inl.mean()))
        rows.append(r)
    return rows
out = {name: analyze(p) for name, p in (("ref", "ref/ref.mp4"), ("ours", sys.argv[1] if len(sys.argv) > 1 else "edit/mrwhosetheboss_edit.mp4"))}
json.dump(out, open(sys.argv[2] if len(sys.argv) > 2 else "ana/motion.json", "w"))
