"""Collect Mrwhosetheboss footage for each shot slot.

  python3 fetch_footage.py scout <video-url> [--every 1.5]
      Downloads a 360p copy and writes scout/<id>.jpg, a timestamped contact sheet
      for picking moments.
  python3 fetch_footage.py stills
      For every slot in sources.json with a thumbnail and crop, downloads the official
      video thumbnail and writes footage/<slot>.jpg (square crop). Fallback when video
      downloads are refused; clips in footage/<slot>.mp4 take priority in render.py.
  python3 fetch_footage.py fetch
      For every slot in sources.json that has a url and start time, downloads only
      that section (yt-dlp --download-sections) and writes footage/<slot>.mp4, trimmed
      to the slot's length. render.py picks those up automatically.

Every download is logged with URL and timestamps to footage/SOURCES.log.
Needs network access to youtube.com and googlevideo.com.
"""
import json
import os
import subprocess
import sys

from timeline import FPS, SHOTS

HERE = os.path.dirname(os.path.abspath(__file__))
FOOT = os.path.join(HERE, "footage")


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def scout(url, every=1.5):
    d = os.path.join(HERE, "scout")
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, "%(id)s.%(ext)s")
    run(["yt-dlp", "-f", "bv*[height<=360]+ba/b[height<=360]", "-o", tmp, "--print", "after_move:filepath", url])
    vid = sorted((os.path.join(d, f) for f in os.listdir(d) if not f.endswith(".jpg")), key=os.path.getmtime)[-1]
    sheet = os.path.splitext(vid)[0] + ".jpg"
    run(["ffmpeg", "-v", "error", "-y", "-i", vid, "-vf",
         f"fps=1/{every},scale=240:-2,drawtext=text='%{{pts\\:hms}}':x=4:y=4:fontsize=16:fontcolor=yellow:box=1,tile=8x12",
         "-frames:v", "1", sheet])
    print("contact sheet:", sheet)


def fetch():
    src = json.load(open(os.path.join(HERE, "sources.json")))
    os.makedirs(FOOT, exist_ok=True)
    log = open(os.path.join(FOOT, "SOURCES.log"), "a")
    for shot in SHOTS:
        s = src.get(shot["id"], {})
        if not shot["framing"] or not s.get("url") or s.get("start") is None:
            continue
        dur = (shot["end"] - shot["start"]) / FPS + 0.2
        t0 = float(s["start"])
        raw = os.path.join(FOOT, f"{shot['id']}_raw.%(ext)s")
        run(["yt-dlp", "-f", "bv*[height<=1080]+ba/b", "--download-sections", f"*{t0:.2f}-{t0 + dur + 1:.2f}",
             "--force-keyframes-at-cuts", "-o", raw, s["url"]])
        got = [f for f in os.listdir(FOOT) if f.startswith(f"{shot['id']}_raw.")][0]
        run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(FOOT, got), "-t", f"{dur:.3f}", "-an",
             "-vf", f"fps={FPS}", "-c:v", "libx264", "-crf", "14", os.path.join(FOOT, f"{shot['id']}.mp4")])
        os.remove(os.path.join(FOOT, got))
        log.write(f"{shot['id']}\t{s['url']}\t{t0:.2f}-{t0 + dur:.2f}s\t{shot['need']}\n")
        log.flush()


def stills():
    import cv2
    import urllib.request
    src = json.load(open(os.path.join(HERE, "sources.json")))
    os.makedirs(FOOT, exist_ok=True)
    log = open(os.path.join(FOOT, "SOURCES.log"), "a")
    for sid, s in src.items():
        if not s.get("thumbnail") or not s.get("crop"):
            continue
        raw = os.path.join(FOOT, f"{sid}_thumb.jpg")
        urllib.request.urlretrieve(s["thumbnail"], raw)
        img = cv2.imread(raw)
        img = cv2.resize(img, (1280, 720), interpolation=cv2.INTER_CUBIC)
        x0, y0, size = s["crop"]
        cv2.imwrite(os.path.join(FOOT, f"{sid}.jpg"), img[y0:y0 + size, x0:x0 + size], [cv2.IMWRITE_JPEG_QUALITY, 95])
        os.remove(raw)
        log.write(f"{sid}\t{s['thumbnail']}\tthumbnail of {s['url']} ({s.get('title', '')})\tcrop x={x0} y={y0} size={size} @1280x720\n")
        print(sid, "<-", s["thumbnail"])


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "scout":
        every = float(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 1.5
        scout(sys.argv[2], every)
    elif len(sys.argv) >= 2 and sys.argv[1] == "stills":
        stills()
    elif len(sys.argv) >= 2 and sys.argv[1] == "fetch":
        fetch()
    else:
        print(__doc__)
