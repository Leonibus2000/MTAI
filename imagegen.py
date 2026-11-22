"""
MTAI built-in image models: one-click downloads from Hugging Face, ordered from
light and fast to heavy and detailed, run on this PC by MTAI's own image engine.

The engine is a venv (torch with CUDA when there is an NVIDIA GPU, plus diffusers)
in <root>/engine. It is installed with the first model download. Pictures are made
by imagegen_worker.py in a child process that keeps the last model loaded and quits
after a few idle minutes, or when a chat needs the GPU.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import netguard as NG
import paths

APP_DIR = paths.APP_DIR
DATA_DIR = paths.DATA_DIR
CONF = DATA_DIR / "imagegen.json"
WORKER = APP_DIR / "imagegen_worker.py"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
IDLE_QUIT = 300                   # seconds: the worker frees the GPU when nothing was made for this long

# light and fast first, heavy and detailed last
CATALOG = [
    {"id": "sd-turbo", "tier": "Sketch", "model": "SD-Turbo", "repo": "stabilityai/sd-turbo", "size": 2.6e9,
     "base": 512, "steps": 1, "guidance": 0.0, "speed": 5, "detail": 2, "vram": 3, "time": "about 1 s",
     "desc": "Instant drafts. Small and rough, great for trying ideas."},
    {"id": "sdxl-turbo", "tier": "Fast", "model": "SDXL-Turbo", "repo": "stabilityai/sdxl-turbo", "size": 7.0e9,
     "base": 512, "steps": 4, "guidance": 0.0, "speed": 4, "detail": 3, "vram": 6, "time": "2-4 s", "best": True,
     "desc": "Good pictures in seconds. The best start for most people."},
    {"id": "sdxl", "tier": "Detailed", "model": "Stable Diffusion XL 1.0", "repo": "stabilityai/stable-diffusion-xl-base-1.0", "size": 7.1e9,
     "base": 1024, "steps": 30, "guidance": 6.5, "speed": 2, "detail": 4, "vram": 8, "time": "20-40 s", "big": True,
     "desc": "Large 1024 px pictures with much more detail. Follows the 'Avoid' words."},
    {"id": "playground", "tier": "Artistic", "model": "Playground v2.5", "repo": "playgroundai/playground-v2.5-1024px-aesthetic", "size": 7.0e9,
     "base": 1024, "steps": 40, "guidance": 3.0, "speed": 1, "detail": 5, "vram": 8, "time": "30-60 s", "big": True,
     "desc": "The most detailed and beautiful, with rich colors and light. Slowest."},
]
CAT = {m["id"]: m for m in CATALOG}
ENGINE_SIZE = 3.2e9

_LOCK = threading.RLock()
JOBS = {}                 # id -> job dict (engine install and model downloads)
GEN = {"active": False, "step": 0, "of": 0, "status": ""}
_GPU = {"checked": False, "name": None, "vram": 0}


class Cancelled(Exception):
    pass


class GenError(Exception):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code


# ------------------------------------------------------------------ places --

def _conf():
    try:
        return json.loads(CONF.read_text("utf-8"))
    except Exception:
        return {}


def _default_root():
    local = DATA_DIR / "image-models"
    if os.name == "nt" and Path("D:/").exists():
        try:
            if shutil.disk_usage("D:/").free > shutil.disk_usage(DATA_DIR).free + 20e9:
                return Path("D:/MTAI/image-models")      # much more room than the app's drive
        except OSError:
            pass
    return local


def root():
    r = _conf().get("root")
    return Path(r) if r else _default_root()


def set_root(path):
    p = Path(path)
    if not p.is_dir():
        raise GenError("That folder does not exist.")
    if any(not j.get("finished") for j in JOBS.values()):
        raise GenError("Wait until the downloads are finished.")
    stop_worker()
    c = _conf()
    c["root"] = str(p / "MTAI image models") if p.name != "MTAI image models" else str(p)
    CONF.parent.mkdir(parents=True, exist_ok=True)
    CONF.write_text(json.dumps(c, indent=1), "utf-8")


def engine_dir():
    return root() / "engine"


def engine_python():
    return engine_dir() / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def engine_ready():
    return (engine_dir() / ".mtai_ok").is_file() and engine_python().is_file()


def model_dir(mid):
    return root() / mid


def installed(mid):
    return (model_dir(mid) / ".complete").is_file()


def gpu():
    if not _GPU["checked"]:
        _GPU["checked"] = True
        try:
            with NG.allow("read the GPU name"):
                r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=8, creationflags=NO_WINDOW)
            name, mem = r.stdout.strip().splitlines()[0].rsplit(",", 1)
            _GPU.update(name=name.strip(), vram=round(int(mem) / 1024, 1))
        except Exception:
            pass
    return _GPU


def status():
    r = root()
    try:
        free = shutil.disk_usage(r if r.exists() else r.anchor).free
    except OSError:
        free = None
    g = gpu()
    models = []
    for m in CATALOG:
        models.append({**m, "installed": installed(m["id"]), "fits": (g["vram"] or 0) >= m["vram"] - 0.5 if g["name"] else None})
    with _LOCK:
        jobs = {k: {x: v for x, v in j.items() if x != "cancel"} for k, j in JOBS.items()}
    return {"models": models, "engine": engine_ready(), "engine_size": ENGINE_SIZE, "root": str(r), "free": free,
            "gpu": g["name"], "vram": g["vram"], "jobs": jobs, "gen": dict(GEN)}


# --------------------------------------------------------------- downloads --

def _job(key, **kw):
    with _LOCK:
        j = JOBS[key] = {"id": key, "phase": "", "done": 0, "total": 0, "speed": 0, "error": None, "finished": False,
                         "cancel": False, "t": time.time(), **kw}
    return j


def _tick(j, n):
    j["done"] += n
    now = time.time()
    if now - j.get("_t0", 0) > 1:
        if j.get("_t0"):
            j["speed"] = (j["done"] - j["_b0"]) / (now - j["_t0"])
        j["_t0"], j["_b0"] = now, j["done"]


def _want(f):
    if f == "model_index.json":
        return True
    if "/" not in f or f.split("/")[0] in ("vae_1_0", "vae_decoder", "vae_encoder"):
        return False
    return f.endswith((".json", ".txt")) or f.endswith(".fp16.safetensors")


def _hf_files(repo):
    with urllib.request.urlopen(urllib.request.Request(
            f"https://huggingface.co/api/models/{repo}?blobs=true", headers={"User-Agent": "MTAI"}), timeout=30) as r:
        d = json.loads(r.read())
    return [(s["rfilename"], s.get("size") or 0) for s in d.get("siblings", []) if _want(s["rfilename"])]


def _fetch(j, url, dest, size):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and (not size or dest.stat().st_size == size):
        _tick(j, dest.stat().st_size)
        return
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.is_file() else 0
    req = urllib.request.Request(url, headers={"User-Agent": "MTAI", **({"Range": f"bytes={have}-"} if have else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        if have and r.status != 206:
            have = 0                                   # the server ignored the range: start over
        _tick(j, have)
        with open(part, "ab" if have else "wb") as o:
            while True:
                if j["cancel"]:
                    raise Cancelled()
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                o.write(chunk)
                _tick(j, len(chunk))
    os.replace(part, dest)


def _pip(j, args, label):
    cmd = [str(engine_python()), "-m", "pip", "install", "--progress-bar", "raw", "--disable-pip-version-check", *args]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                         creationflags=NO_WINDOW, encoding="utf-8", errors="replace")
    tail = []
    base = j["done"]
    for line in p.stdout:
        if j["cancel"]:
            p.kill()
            raise Cancelled()
        line = line.strip()
        tail = (tail + [line])[-12:]
        m = re.match(r"Progress (\d+) of (\d+)", line)
        if m:
            cur, tot = int(m.group(1)), int(m.group(2))
            if tot > 50e6:                                 # the big wheel (torch) drives the bar
                _tick(j, min(base + cur, j["total"] - 1) - j["done"])
            continue
        m = re.match(r"(Collecting|Downloading|Installing collected packages:)\s*(\S+)?", line)
        if m:
            what = (m.group(2) or "").rsplit("/", 1)[-1].split("-")[0].split("==")[0].split(">")[0]
            if m.group(1).startswith("Installing"):
                what, j["speed"] = "installing packages (a few minutes)", 0
            j["phase"] = f"{label}: {what}"
    if p.wait() != 0:
        raise GenError("Installing the image engine failed: " + " | ".join(tail[-4:])[:500])


def _install_engine(j):
    d = engine_dir()
    j.update(phase="Image engine: creating", total=ENGINE_SIZE, done=0)
    if not engine_python().is_file():
        py = paths.python_exe()
        if not py:
            raise GenError("The image engine needs Python 3.10 or newer from python.org. Install it, restart MTAI "
                           "and download again.")
        r = subprocess.run([str(py), "-m", "venv", str(d)], capture_output=True, text=True, creationflags=NO_WINDOW)
        if r.returncode != 0:
            raise GenError("Could not create the image engine: " + (r.stderr or r.stdout)[-300:])
    if gpu()["name"]:
        _pip(j, ["torch", "--index-url", "https://download.pytorch.org/whl/cu128"], "Image engine")
    else:
        _pip(j, ["torch"], "Image engine")
    _pip(j, ["diffusers", "transformers", "accelerate", "safetensors"], "Image engine")
    j["phase"] = "Image engine: testing"
    r = subprocess.run([str(engine_python()), "-c", "import torch, diffusers; print(torch.cuda.is_available())"],
                       capture_output=True, text=True, creationflags=NO_WINDOW, timeout=300)
    if r.returncode != 0:
        raise GenError("The image engine does not start: " + r.stderr[-300:])
    (d / ".mtai_ok").write_text(json.dumps({"cuda": r.stdout.strip() == "True", "t": time.time()}), "utf-8")


def _run_download(mid):
    m = CAT[mid]
    j = JOBS[mid]
    try:
        need = m["size"] + (0 if engine_ready() else ENGINE_SIZE)
        r = root()
        r.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(r).free < need * 1.1:
            raise GenError(f"Not enough free space in {r}: needs about {need / 1e9:.1f} GB.")
        if not engine_ready():
            _install_engine(j)
        j.update(phase="Model: listing files", done=0, total=m["size"], speed=0, _t0=0)
        files = _hf_files(m["repo"])
        j["total"] = sum(s for _, s in files) or m["size"]
        dest = model_dir(mid)
        for path, size in files:
            j["phase"] = "Model: " + path.split("/")[0]
            _fetch(j, f"https://huggingface.co/{m['repo']}/resolve/main/{path}", dest / path, size)
        (dest / ".complete").write_text(json.dumps({"repo": m["repo"], "t": time.time()}), "utf-8")
        j.update(phase="Ready", done=j["total"])
    except Cancelled:
        j["error"] = "Cancelled"
    except urllib.error.HTTPError as e:
        j["error"] = f"Download failed: HTTP {e.code}"
    except urllib.error.URLError as e:
        j["error"] = f"Download failed: {e.reason}"
    except GenError as e:
        j["error"] = str(e)
    except Exception as e:
        j["error"] = f"{type(e).__name__}: {e}"
    finally:
        j["finished"] = True


def start_download(mid):
    if mid not in CAT:
        raise GenError("Unknown model")
    with _LOCK:
        if any(not j["finished"] for j in JOBS.values()):
            raise GenError("Another download is running. Wait for it, or cancel it.")
        _job(mid, model=CAT[mid]["tier"])
    threading.Thread(target=_run_download, args=(mid,), daemon=True).start()


def cancel(mid):
    with _LOCK:
        j = JOBS.get(mid)
        if j:
            j["cancel"] = True


def delete_model(mid):
    if mid not in CAT:
        raise GenError("Unknown model")
    j = JOBS.get(mid)
    if j and not j["finished"]:
        raise GenError("Cancel the download first.")
    stop_worker()
    shutil.rmtree(model_dir(mid), ignore_errors=True)
    JOBS.pop(mid, None)


def delete_engine():
    if any(installed(m["id"]) for m in CATALOG):
        raise GenError("Delete the models first.")
    stop_worker()
    shutil.rmtree(engine_dir(), ignore_errors=True)


# ------------------------------------------------------------------ worker --

class _Worker:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.last = 0
        self.info = {}

    def start(self):
        if self.proc and self.proc.poll() is None:
            return
        log = open(engine_dir() / "worker.log", "a", encoding="utf-8")
        # MTAI_NET_GUARD: the worker blocks every outside connection itself (netguard), in both modes
        with NG.allow("start the local image engine"):
            self.proc = subprocess.Popen([str(engine_python()), "-u", str(WORKER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=log, text=True, bufsize=1, encoding="utf-8", creationflags=NO_WINDOW,
                                         cwd=str(engine_dir()), env={**os.environ, "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
                                                                     "PYTHONIOENCODING": "utf-8", "MTAI_NET_GUARD": "1"})
        GEN["status"] = "Starting the image engine"
        ev = self._read(180)
        if ev.get("type") != "ready":
            self.stop()
            raise GenError(ev.get("message") or "The image engine did not start (see worker.log in the engine folder).")
        self.info = ev
        threading.Thread(target=self._idle_watch, daemon=True).start()

    def _read(self, timeout):
        box = {}
        t = threading.Thread(target=lambda: box.update(line=self.proc.stdout.readline()), daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            self.stop()
            raise GenError("The image engine stopped answering.")
        line = box.get("line") or ""
        if not line:
            self.stop()
            raise GenError("The image engine closed (see worker.log in the engine folder).")
        try:
            return json.loads(line)
        except ValueError:
            return {"type": "log", "text": line}

    def _idle_watch(self):
        proc = self.proc
        while proc is self.proc and proc.poll() is None:
            time.sleep(15)
            if not self.lock.locked() and time.time() - self.last > IDLE_QUIT:
                self.stop()

    def stop(self):
        p, self.proc = self.proc, None
        if p and p.poll() is None:
            try:
                p.kill()
            except OSError:
                pass

    def gen(self, req):
        with self.lock:
            self.start()
            self.last = time.time()
            self.proc.stdin.write(json.dumps({"cmd": "gen", **req}) + "\n")
            self.proc.stdin.flush()
            while True:
                ev = self._read(1800)
                t = ev.get("type")
                if t == "progress":
                    GEN.update(step=ev["step"], of=ev["of"], status="Painting")
                elif t == "status":
                    GEN["status"] = ev["text"]
                elif t == "done":
                    self.last = time.time()
                    return ev
                elif t in ("error", "fatal"):
                    self.last = time.time()
                    raise GenError(ev.get("message") or "Image engine error", ev.get("code"))


W = _Worker()


def stop_worker():
    W.stop()


def busy():
    return W.lock.locked()


def generate(mid, prompt, negative, aspect, seed, out_path, dims, free_gpu=None):
    """Make one picture with a built-in model. free_gpu() unloads chat models when memory runs out."""
    if mid not in CAT or not installed(mid):
        raise GenError("That image model is not downloaded.")
    if not engine_ready():
        raise GenError("The image engine is missing. Download a model again to install it.")
    m = CAT[mid]
    w, h = dims(aspect, m["base"])
    req = {"dir": str(model_dir(mid)), "prompt": prompt, "negative": negative or "", "steps": m["steps"],
           "guidance": m["guidance"], "width": w, "height": h, "seed": seed, "out": str(out_path), "big": bool(m.get("big"))}
    GEN.update(active=True, step=0, of=m["steps"], status="Starting")
    try:
        try:
            return W.gen(req)
        except GenError as e:
            if e.code == "oom" and free_gpu and free_gpu():
                GEN["status"] = "Freed GPU memory, trying again"
                return W.gen(req)
            if e.code == "oom":
                raise GenError("Not enough GPU memory for this model. Close other GPU programs, or pick a lighter model.")
            raise
    finally:
        GEN.update(active=False, status="")
