"""
MTAI image worker. Runs inside MTAI's own image engine (a venv with torch + diffusers),
started by imagegen.py. Talks JSON lines: requests on stdin, events on stdout.
Keeps the last model loaded so the next picture is quick.
"""
import json
import os
import sys
import time

out = sys.stdout

if os.environ.get("MTAI_NET_GUARD") == "1":
    # This worker never needs the internet (models load from disk with HF_HUB_OFFLINE), so the
    # network guard blocks every outside connection in both modes. netguard.py sits next to this file.
    import netguard
    netguard.install(always=True, component_name="Image engine")


def send(obj):
    out.write(json.dumps(obj) + "\n")
    out.flush()


try:
    import torch
    from diffusers import AutoPipelineForText2Image
except Exception as e:                       # broken engine: say so and quit
    send({"type": "fatal", "message": f"The image engine is broken ({type(e).__name__}: {e}). Delete it and download again."})
    sys.exit(1)

DEV = "cuda" if torch.cuda.is_available() else "cpu"
VRAM = torch.cuda.get_device_properties(0).total_memory / 2 ** 30 if DEV == "cuda" else 0
send({"type": "ready", "device": DEV, "vram": round(VRAM, 1), "gpu": torch.cuda.get_device_name(0) if DEV == "cuda" else None})

pipe, current = None, None


def load(req):
    global pipe, current
    if current == req["dir"] and pipe is not None:
        return
    pipe, current = None, None
    if DEV == "cuda":
        torch.cuda.empty_cache()
    send({"type": "status", "text": "Loading the model"})
    t0 = time.time()
    p = AutoPipelineForText2Image.from_pretrained(req["dir"], torch_dtype=torch.float16 if DEV == "cuda" else torch.float32,
                                                  variant="fp16", use_safetensors=True)
    if DEV == "cuda":
        if req.get("big") and VRAM < 11:
            p.enable_model_cpu_offload()      # SDXL-size models on 8 GB cards: parts move to the GPU in turn
        else:
            p.to("cuda")
    try:
        p.vae.enable_tiling()                 # big pictures decode in tiles: less memory
    except Exception:
        pass
    p.set_progress_bar_config(disable=True)
    pipe, current = p, req["dir"]
    send({"type": "status", "text": f"Model loaded in {time.time() - t0:.0f} s"})


def generate(req):
    load(req)
    n = int(req["steps"])
    seed = int(req.get("seed") if req.get("seed") is not None else torch.seed() % 2 ** 31)
    gen = torch.Generator("cpu").manual_seed(seed)

    def on_step(_pipe, i, _t, kw):
        send({"type": "progress", "step": i + 1, "of": n})
        return kw
    kw = dict(prompt=req["prompt"], num_inference_steps=n, guidance_scale=float(req["guidance"]),
              width=int(req["width"]), height=int(req["height"]), generator=gen, callback_on_step_end=on_step)
    if float(req["guidance"]) > 1 and req.get("negative"):
        kw["negative_prompt"] = req["negative"]
    send({"type": "progress", "step": 0, "of": n})
    image = pipe(**kw).images[0]
    image.save(req["out"])
    send({"type": "done", "out": req["out"], "seed": seed})


for line in sys.stdin:
    try:
        req = json.loads(line)
    except ValueError:
        continue
    try:
        if req.get("cmd") == "gen":
            generate(req)
        elif req.get("cmd") == "unload":
            pipe, current = None, None
            if DEV == "cuda":
                torch.cuda.empty_cache()
            send({"type": "done"})
    except torch.cuda.OutOfMemoryError:
        pipe, current = None, None
        torch.cuda.empty_cache()
        send({"type": "error", "code": "oom", "message": "Not enough GPU memory for this model."})
    except Exception as e:
        send({"type": "error", "message": f"{type(e).__name__}: {str(e)[:400]}"})
