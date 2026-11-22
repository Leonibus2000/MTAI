"""
MTAI - cloud AI providers with your own API keys, and image generation.

Chat providers
  * Anthropic (Claude) through the official `anthropic` Python SDK
  * OpenAI, Google Gemini, xAI Grok, DeepSeek, Mistral, Groq, OpenRouter and any
    other OpenAI-compatible endpoint through their /chat/completions API
    (the streaming itself is done by chat_openai in local_ai_chat.py)

Keys are stored in data/keys.json, encrypted with Windows DPAPI (only this
Windows user on this PC can decrypt them). The UI only ever gets a masked copy.

Image generation
  * OpenAI (gpt-image / dall-e), xAI (grok image models), Google (Imagen)
  * Local: AUTOMATIC1111 / Forge WebUI (port 7860, start with --api) and ComfyUI (port 8188)
"""

import base64
import ctypes
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlencode

import paths

APP_DIR = paths.APP_DIR
DATA_DIR = paths.DATA_DIR
KEYS_FILE = DATA_DIR / "keys.json"
CLOUD_CACHE = DATA_DIR / "cloud_models.json"
IMG_DIR = DATA_DIR / "images"
IMG_NAME_RE = re.compile(r"^[\w.-]{1,80}\.(png|jpe?g|webp)$", re.I)

A1111_URL = os.environ.get("MTAI_A1111", "http://127.0.0.1:7860").rstrip("/")
COMFY_URL = os.environ.get("MTAI_COMFY", "http://127.0.0.1:8188").rstrip("/")

STALE_AFTER = 6 * 3600          # model lists are refreshed in the background after this


class ProviderError(Exception):
    pass


PROVIDERS = [
    {"id": "openai", "name": "OpenAI", "label": "GPT (OpenAI)", "kind": "openai", "base": "https://api.openai.com/v1",
     "keys_url": "https://platform.openai.com/api-keys", "hint": "sk-...", "img": True,
     "desc": "GPT-5, GPT-4.1, GPT-4o, o-series. Image generation with gpt-image."},
    {"id": "anthropic", "name": "Anthropic", "label": "Claude (Anthropic)", "kind": "anthropic", "base": "https://api.anthropic.com",
     "keys_url": "https://console.anthropic.com/settings/keys", "hint": "sk-ant-...",
     "desc": "Claude Opus, Sonnet and Haiku, with visible thinking."},
    {"id": "gemini", "name": "Google Gemini", "label": "Gemini (Google)", "kind": "openai",
     "base": "https://generativelanguage.googleapis.com/v1beta/openai",
     "keys_url": "https://aistudio.google.com/apikey", "hint": "AIza...", "img": True,
     "desc": "Gemini Pro and Flash with huge context. Image generation with Imagen."},
    {"id": "xai", "name": "xAI", "label": "Grok (xAI)", "kind": "openai", "base": "https://api.x.ai/v1",
     "keys_url": "https://console.x.ai", "hint": "xai-...", "img": True,
     "desc": "Grok models. Image generation with Grok image models."},
    {"id": "deepseek", "name": "DeepSeek", "label": "DeepSeek", "kind": "openai", "base": "https://api.deepseek.com/v1",
     "keys_url": "https://platform.deepseek.com/api_keys", "hint": "sk-...",
     "desc": "DeepSeek chat and reasoner (shows its thinking). Very cheap."},
    {"id": "mistral", "name": "Mistral", "label": "Mistral", "kind": "openai", "base": "https://api.mistral.ai/v1",
     "keys_url": "https://console.mistral.ai/api-keys", "hint": "",
     "desc": "Mistral Large, Medium, Codestral, Pixtral. EU based."},
    {"id": "groq", "name": "Groq", "label": "Groq", "kind": "openai", "base": "https://api.groq.com/openai/v1",
     "keys_url": "https://console.groq.com/keys", "hint": "gsk_...",
     "desc": "Open models (Llama, Qwen, gpt-oss) at hundreds of tokens per second."},
    {"id": "openrouter", "name": "OpenRouter", "label": "OpenRouter", "kind": "openai", "base": "https://openrouter.ai/api/v1",
     "keys_url": "https://openrouter.ai/keys", "hint": "sk-or-...",
     "desc": "One key for hundreds of models from every company. Use the filter to keep the list short."},
    {"id": "custom", "name": "Custom", "label": "Custom API", "kind": "openai", "base": "",
     "keys_url": "", "hint": "", "custom": True,
     "desc": "Any other OpenAI-compatible API (Together, Fireworks, Perplexity, a server on your network...). Enter its base URL."},
]
PROV = {p["id"]: p for p in PROVIDERS}

_LOCK = threading.RLock()
CLOUD = {"models": {}, "images": {}, "errors": {}, "at": {}}   # per provider id
_REFRESHING = set()


# ------------------------------------------------------------------ helpers --

def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text("utf-8"))
    except Exception:
        return default


def _write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, path)


def _http(url, data=None, headers=None, method=None, timeout=20):
    body = None if data is None else json.dumps(data).encode()
    h = {"Content-Type": "application/json", "User-Agent": "MTAI"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw.decode("utf-8", "replace")) if raw.strip() else {}


def _http_bytes(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "MTAI"}), timeout=timeout) as r:
        return r.read()


def error_text(e, who="The server"):
    """Readable message for an HTTPError from a cloud API."""
    try:
        body = e.read().decode("utf-8", "replace")
        try:
            j = json.loads(body)
            if isinstance(j, list) and j:
                j = j[0]
            err = j.get("error", j) if isinstance(j, dict) else j
            if isinstance(err, dict):
                err = err.get("message") or err.get("msg") or str(err)
            body = str(err)
        except Exception:
            pass
    except Exception:
        body = ""
    body = (body or e.reason or "").strip()[:400]
    if e.code in (401, 403):
        return f"{who} did not accept the API key (HTTP {e.code}). {body}".strip()
    if e.code == 402:
        return f"{who}: no credit left on this account (HTTP 402). {body}".strip()
    if e.code == 429:
        return f"{who}: rate limit or quota reached (HTTP 429). {body}".strip()
    return f"{who}: HTTP {e.code}. {body}".strip()


# ------------------------------------------------------- key storage (DPAPI) --

class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data, protect):
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    buf = ctypes.create_string_buffer(data, len(data))
    inp = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = _Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(inp), None, None, None, None, 0x1, ctypes.byref(out)):   # 0x1 = no UI
        raise OSError("Windows could not " + ("encrypt" if protect else "decrypt") + " the key")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


def _seal(key):
    if os.name == "nt":
        return "dpapi:" + base64.b64encode(_dpapi(key.encode(), True)).decode()
    return "b64:" + base64.b64encode(key.encode()).decode()


def _unseal(s):
    if s.startswith("dpapi:"):
        return _dpapi(base64.b64decode(s[6:]), False).decode()
    if s.startswith("b64:"):
        return base64.b64decode(s[4:]).decode()
    return s


def _store():
    d = _read_json(KEYS_FILE, {})
    return d if isinstance(d, dict) else {}


def get_key(pid):
    e = _store().get(pid) or {}
    try:
        return _unseal(e["key"]) if e.get("key") else None
    except Exception:
        return None


def _entry(pid):
    return _store().get(pid) or {}


def base_url(pid):
    p = PROV[pid]
    return ((_entry(pid).get("base") if p.get("custom") else None) or p["base"]).rstrip("/")


def mask(key):
    if not key:
        return ""
    return key[:4] + "…" + key[-4:] if len(key) > 12 else "…" + key[-2:]


def has_sdk():
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


def status():
    """What the Cloud tab shows. Keys are masked."""
    st = _store()
    out = []
    with _LOCK:
        for p in PROVIDERS:
            e = st.get(p["id"]) or {}
            key = None
            try:
                key = _unseal(e["key"]) if e.get("key") else None
            except Exception:
                pass
            out.append({k: p.get(k) for k in ("id", "name", "label", "kind", "keys_url", "hint", "desc", "img", "custom")} | {
                "has_key": bool(key), "masked": mask(key), "base": base_url(p["id"]) if p.get("custom") else p["base"],
                "filter": e.get("filter", ""), "name_custom": e.get("name", ""),
                "count": len(CLOUD["models"].get(p["id"]) or []), "images": len(CLOUD["images"].get(p["id"]) or []),
                "error": CLOUD["errors"].get(p["id"]), "at": CLOUD["at"].get(p["id"]),
                "refreshing": p["id"] in _REFRESHING, "added": e.get("added")})
    return {"providers": out, "sdk": has_sdk(), "encrypted": os.name == "nt"}


def set_key(pid, key=None, base=None, flt=None, name=None):
    if pid not in PROV:
        raise ProviderError("Unknown provider")
    st = _store()
    e = st.get(pid) or {}
    if key is not None:
        key = key.strip()
        if not key or len(key) > 400 or any(c.isspace() for c in key):
            raise ProviderError("That does not look like an API key.")
        e["key"] = _seal(key)
        e["added"] = time.time()
    if base is not None:
        base = base.strip().rstrip("/")
        if base and not re.match(r"^https?://", base):
            raise ProviderError("The base URL must start with http:// or https://")
        e["base"] = base
    if flt is not None:
        e["filter"] = str(flt)[:300]
    if name is not None:
        e["name"] = str(name)[:40]
    if PROV[pid].get("custom") and not (e.get("base") or "").strip():
        raise ProviderError("Enter the base URL of the API, e.g. https://api.together.xyz/v1")
    st[pid] = e
    _write_json(KEYS_FILE, st)


def remove_key(pid):
    st = _store()
    st.pop(pid, None)
    _write_json(KEYS_FILE, st)
    with _LOCK:
        for k in ("models", "images", "errors", "at"):
            CLOUD[k].pop(pid, None)
        _save_cache()


# --------------------------------------------------------- model discovery --

OPENAI_SKIP = re.compile(r"embed|whisper|tts|transcri|audio|realtime|moderation|dall-e|gpt-image|image|imagen|imagine|"
                         r"veo|video|rerank|guard|ocr|search|computer-use|sora|babbage|davinci|aqa|learnlm|-live|"
                         r"native-audio|codex|-pro\b|deep-research|instruct|robotics|playai|lyria", re.I)
IMAGE_RE = re.compile(r"gpt-image|dall-e|imagen|grok-.*imag|image-gen", re.I)


def _ctx_guess(pid, mid):
    m = mid.lower()
    if pid == "gemini":
        return 1_048_576
    if pid == "openai":
        if m.startswith("gpt-4.1"):
            return 1_047_576
        if m.startswith("gpt-5"):
            return 400_000
        if re.match(r"o\d", m):
            return 200_000
    if pid == "xai":
        return 256_000 if "grok-4" in m else 131_072
    if pid == "deepseek":
        return 128_000
    return 128_000


def _caps_guess(pid, mid, extra=None):
    m, extra = mid.lower(), extra or {}
    caps = ["completion"]
    vision = thinking = False
    if pid == "openai":
        vision = bool(re.match(r"(gpt-4o|gpt-4\.1|gpt-4\.5|gpt-5|o1(?!-mini)|o3(?!-mini)|o4|chatgpt-4o)", m))
        thinking = bool(re.match(r"(o\d|gpt-5)", m)) and "chat" not in m
    elif pid == "gemini":
        vision = True
        thinking = bool(re.search(r"gemini-(2\.5|[3-9])", m))
    elif pid == "xai":
        vision = "vision" in m or "grok-4" in m
        thinking = "grok-3-mini" in m or ("grok-4" in m and "non-reasoning" not in m)
    elif pid == "deepseek":
        thinking = "reason" in m or "r1" in m
    elif pid == "mistral":
        vision = bool(re.search(r"pixtral|mistral-medium|mistral-small|mistral-large-2411", m))
        thinking = "magistral" in m
    elif pid == "groq":
        vision = bool(re.search(r"llama-4|vision", m))
        thinking = bool(re.search(r"qwen3|qwq|deepseek-r1|gpt-oss", m))
    elif pid == "openrouter":
        arch = extra.get("architecture") or {}
        vision = "image" in (arch.get("input_modalities") or [])
        thinking = "reasoning" in (extra.get("supported_parameters") or [])
    else:
        vision = bool(re.search(r"vision|vl\b|-vl-|pixtral|llava|gpt-4o|gemma-3|llama-4", m))
        thinking = bool(re.search(r"r1|reason|think|qwq|qwen3|gpt-oss|magistral", m))
    if vision:
        caps.append("vision")
    if thinking:
        caps.append("thinking")
    return caps


def _model(pid, api_id, name=None, ctx=None, caps=None, **more):
    p = PROV[pid]
    label = (_entry(pid).get("name") or p["label"]) if p.get("custom") else p["label"]
    return {"id": f"cloud|{pid}|{api_id}", "name": name or api_id, "api_id": api_id, "backend": "cloud",
            "provider": pid, "source": label, "url": base_url(pid), "size": 0, "params": None, "quant": None,
            "family": p["name"], "caps": caps or ["completion"], "ctx": ctx or _ctx_guess(pid, api_id),
            "chattable": True, "reason": None, "loaded": False, "cloud": True, **more}


def _matches(flt, *texts):
    words = [w.strip().lower() for w in re.split(r"[,\n]", flt or "") if w.strip()]
    if not words:
        return True
    t = " ".join(texts).lower()
    return any(w in t for w in words)


def _list_openai_kind(pid, key):
    base = base_url(pid)
    headers = {"Authorization": f"Bearer {key}"}
    if pid == "openrouter":
        headers.update({"HTTP-Referer": "https://localhost/mtai", "X-Title": "MTAI"})
    data = _http(base + "/models", headers=headers, timeout=15)
    items = data.get("data") if isinstance(data, dict) else data
    items = items if isinstance(items, list) else (data.get("models") or [])
    flt = _entry(pid).get("filter", "")
    chats, images = [], []
    for it in items:
        if not isinstance(it, dict):
            continue
        mid = str(it.get("id") or it.get("name") or "")
        if not mid:
            continue
        if pid == "gemini" and mid.startswith("models/"):
            mid = mid[7:]
        low = mid.lower()
        if IMAGE_RE.search(low) and pid in ("openai", "xai", "gemini"):
            images.append({"id": f"{pid}|{mid}", "provider": pid, "name": mid, "label": PROV[pid]["name"], "local": False})
            continue
        if pid == "openai" and not re.match(r"(gpt-|o\d|chatgpt-)", low):
            continue
        if pid == "gemini" and not low.startswith(("gemini", "gemma")):
            continue
        if pid == "openrouter":
            outm = ((it.get("architecture") or {}).get("output_modalities")) or ["text"]
            if "text" not in outm:
                continue
        elif OPENAI_SKIP.search(low):
            continue
        if not _matches(flt, mid, str(it.get("name") or "")):
            continue
        ctx = it.get("context_length") or it.get("context_window") or it.get("max_context_length") \
            or it.get("inputTokenLimit") or None
        name = mid
        if pid == "openrouter" and it.get("name"):
            name = mid           # keep the id: it says the company (openai/gpt-5, anthropic/claude-...)
        chats.append(_model(pid, mid, name=name, ctx=int(ctx) if str(ctx or "").isdigit() else None,
                            caps=_caps_guess(pid, mid, it), created=it.get("created") or 0))
    chats.sort(key=lambda m: (-(m.get("created") or 0), m["name"]))
    return chats, images


def _anthropic_client(key=None):
    try:
        import anthropic
    except ImportError:
        raise ProviderError("Claude needs the Anthropic SDK. Run:  py -m pip install anthropic   then restart MTAI.")
    return anthropic, anthropic.Anthropic(api_key=key or get_key("anthropic"), max_retries=2, timeout=900)


def _list_anthropic(key):
    anthropic, client = _anthropic_client(key)
    try:
        page = client.models.list(limit=100)
        items = list(page)
    except anthropic.AuthenticationError:
        raise ProviderError("Anthropic did not accept the API key.")
    except anthropic.APIConnectionError:
        raise ProviderError("Cannot reach api.anthropic.com.")
    except anthropic.APIStatusError as e:
        raise ProviderError(f"Anthropic: HTTP {e.status_code}. {e.message}")
    flt = _entry("anthropic").get("filter", "")
    out = []
    for m in items:
        caps_d = getattr(m, "capabilities", None) or {}
        if hasattr(caps_d, "model_dump"):            # the SDK gives a typed object; walk it as a dict
            caps_d = caps_d.model_dump()

        def sup(*path):
            d = caps_d
            for k in path:
                d = d.get(k) if isinstance(d, dict) else None
            return bool(d.get("supported")) if isinstance(d, dict) else False
        caps = ["completion"]
        if sup("image_input") or not caps_d:
            caps.append("vision")
        think_mode = "adaptive" if sup("thinking", "types", "adaptive") else \
            "enabled" if sup("thinking", "types", "enabled") else None
        if think_mode:
            caps.append("thinking")
        name = getattr(m, "display_name", None) or m.id
        if not _matches(flt, m.id, name):
            continue
        out.append(_model("anthropic", m.id, name=name, ctx=getattr(m, "max_input_tokens", None) or 200_000, caps=caps,
                          max_out=getattr(m, "max_tokens", None) or 32_000, think_mode=think_mode,
                          effort=sup("effort"), created=0))
    return out, []


def refresh(pid):
    """Fetch the model list of one provider (raises ProviderError on a bad key)."""
    key = get_key(pid)
    if not key:
        raise ProviderError("No API key saved.")
    with _LOCK:
        _REFRESHING.add(pid)
    try:
        if PROV[pid]["kind"] == "anthropic":
            chats, images = _list_anthropic(key)
        else:
            try:
                chats, images = _list_openai_kind(pid, key)
            except urllib.error.HTTPError as e:
                raise ProviderError(error_text(e, PROV[pid]["name"]))
            except urllib.error.URLError as e:
                raise ProviderError(f"Cannot reach {base_url(pid)}: {e.reason}")
        if not images and PROV[pid].get("img"):
            images = [{"id": f"{pid}|{n}", "provider": pid, "name": n, "label": PROV[pid]["name"], "local": False}
                      for n in {"openai": ["gpt-image-1", "dall-e-3"], "xai": ["grok-2-image"],
                                "gemini": ["imagen-4.0-generate-001"]}.get(pid, [])]
        with _LOCK:
            CLOUD["models"][pid] = chats
            CLOUD["images"][pid] = images
            CLOUD["errors"].pop(pid, None)
            CLOUD["at"][pid] = time.time()
            _save_cache()
        return len(chats)
    except ProviderError as e:
        with _LOCK:
            CLOUD["errors"][pid] = str(e)
            CLOUD["at"][pid] = time.time()
        raise
    except Exception as e:
        with _LOCK:
            CLOUD["errors"][pid] = f"{type(e).__name__}: {e}"
            CLOUD["at"][pid] = time.time()
        raise ProviderError(CLOUD["errors"][pid])
    finally:
        with _LOCK:
            _REFRESHING.discard(pid)


def _save_cache():
    _write_json(CLOUD_CACHE, {"models": CLOUD["models"], "images": CLOUD["images"], "at": CLOUD["at"]})


def load_cache():
    c = _read_json(CLOUD_CACHE, {})
    st = _store()
    with _LOCK:
        for k in ("models", "images", "at"):
            CLOUD[k] = {pid: v for pid, v in (c.get(k) or {}).items() if pid in st and pid in PROV}


def refresh_stale(background=True):
    st = _store()
    for pid in PROV:
        if pid not in st or pid in _REFRESHING:
            continue
        if time.time() - (CLOUD["at"].get(pid) or 0) < STALE_AFTER:
            continue
        if background:
            CLOUD["at"][pid] = time.time()          # one try per stale period, also when it fails
            threading.Thread(target=lambda p=pid: _quiet(refresh, p), daemon=True).start()
        else:
            _quiet(refresh, pid)


def _quiet(fn, *a):
    try:
        fn(*a)
    except Exception:
        pass


def cloud_models(privacy=False):
    st = _store()
    out = []
    with _LOCK:
        for p in PROVIDERS:
            if p["id"] not in st:
                continue
            for m in CLOUD["models"].get(p["id"]) or []:
                m = dict(m)
                if privacy:
                    m["chattable"] = False
                    m["reason"] = "Privacy mode is on: cloud models are off"
                out.append(m)
    return out


# --------------------------------------------------------------- chat glue --

def openai_request(model):
    """Endpoint, headers and tweaks for chat_openai() in local_ai_chat.py."""
    pid = model["provider"]
    key = get_key(pid)
    if not key:
        raise ProviderError(f"No API key for {PROV[pid]['name']}. Add it in Models > Cloud & API keys.")
    headers = {"Authorization": f"Bearer {key}"}
    if pid == "openrouter":
        headers.update({"HTTP-Referer": "https://localhost/mtai", "X-Title": "MTAI"})
    low = model["api_id"].lower()
    reasoning = pid == "openai" and bool(re.match(r"(o\d|gpt-5)", low)) and "chat" not in low
    return {"endpoint": base_url(pid) + "/chat/completions", "headers": headers,
            "no_sampling": reasoning,                 # these models reject temperature and top_p
            "max_key": "max_completion_tokens" if pid == "openai" else "max_tokens",
            "effort_param": pid in ("openai", "gemini", "xai", "groq", "openrouter", "custom"),
            "who": PROV[pid]["name"]}


def _parse_data_url(u):
    m = re.match(r"^data:(image/[\w.+-]+);base64,(.*)$", u, re.S)
    if m:
        return m.group(1), m.group(2)
    return "image/png", u


def _anthropic_messages(req):
    out = []
    for m in req.get("messages", []):
        role = "assistant" if m.get("role") == "assistant" else "user"
        blocks = []
        for u in m.get("images") or []:
            mt, data = _parse_data_url(u)
            blocks.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}})
        text = m.get("content") or ""
        if text.strip():
            blocks.append({"type": "text", "text": text})
        if not blocks:
            continue
        if out and out[-1]["role"] == role:
            out[-1]["content"] += blocks             # the API wants user and assistant turns to alternate
        else:
            out.append({"role": role, "content": blocks})
    if not out or out[0]["role"] != "user":
        out.insert(0, {"role": "user", "content": [{"type": "text", "text": "(conversation start)"}]})
    if out[-1]["role"] != "user":
        out.append({"role": "user", "content": [{"type": "text", "text": "Continue."}]})
    return out


def chat_anthropic(model, req, emit):
    anthropic, client = _anthropic_client()
    if not get_key("anthropic"):
        raise ProviderError("No Anthropic API key. Add it in Models > Cloud & API keys.")
    opts = req.get("options") or {}
    max_out = int(model.get("max_out") or 32_000)
    max_tokens = min(max_out, int(opts.get("num_predict") or 0) or 32_000)
    kw = {"model": model["api_id"], "max_tokens": max_tokens, "messages": _anthropic_messages(req)}
    if req.get("system"):
        kw["system"] = req["system"]
    tm, think = model.get("think_mode"), req.get("think")
    oc = {}
    if tm == "adaptive":
        if think is not False:
            kw["thinking"] = {"type": "adaptive", "display": "summarized"}
        elif model.get("effort"):
            oc["effort"] = "low"                     # Think off = quicker, shorter reasoning
    elif tm == "enabled" and think:
        kw["thinking"] = {"type": "enabled", "budget_tokens": max(1024, min(8000, max_tokens - 2048))}
    if isinstance(req.get("format"), dict):
        oc["format"] = {"type": "json_schema", "schema": req["format"]}
    if oc:
        kw["output_config"] = oc

    t0 = time.time()
    first = None
    for attempt in range(2):
        sent = False
        try:
            with client.messages.stream(**kw) as stream:
                for ev in stream:
                    if ev.type != "content_block_delta":
                        continue
                    d = ev.delta
                    if d.type == "thinking_delta" and d.thinking:
                        first = first or time.time() - t0
                        sent = True
                        emit({"type": "thinking", "text": d.thinking})
                    elif d.type == "text_delta" and d.text:
                        first = first or time.time() - t0
                        sent = True
                        emit({"type": "content", "text": d.text})
                final = stream.get_final_message()
            break
        except anthropic.BadRequestError as e:
            if attempt == 0 and not sent and ("thinking" in kw or "output_config" in kw):
                kw.pop("thinking", None)              # an older model: try once without the newer options
                kw.pop("output_config", None)
                continue
            raise ProviderError(f"Claude: {e.message}")
        except anthropic.AuthenticationError:
            raise ProviderError("Anthropic did not accept the API key (Models > Cloud & API keys).")
        except anthropic.PermissionDeniedError as e:
            raise ProviderError(f"Anthropic: no access to this model. {e.message}")
        except anthropic.RateLimitError:
            raise ProviderError("Anthropic: rate limit reached. Wait a moment and retry.")
        except anthropic.APIConnectionError:
            raise ProviderError("Cannot reach api.anthropic.com.")
        except anthropic.APIStatusError as e:
            raise ProviderError(f"Anthropic: HTTP {e.status_code}. {e.message}")
    if final.stop_reason == "refusal":
        emit({"type": "content", "text": "\n\n*Claude declined to answer this.*"})
    elif final.stop_reason == "max_tokens":
        emit({"type": "content", "text": "\n\n*(The answer hit the length limit.)*"})
    total = time.time() - t0
    n = final.usage.output_tokens or 0
    gen = total - (first or 0)
    emit({"type": "done", "stats": {"tokens": n, "tps": (n / gen) if gen > 0 else None,
                                    "prompt_tokens": final.usage.input_tokens, "total": total, "ttft": first}})


# ---------------------------------------------------------- image generation --

ASPECTS = {"square": (1, 1), "wide": (3, 2), "tall": (2, 3)}


def _probe(url, timeout=0.6):
    try:
        return _http(url, timeout=timeout)
    except Exception:
        return None


def image_backends(privacy=False):
    import imagegen
    out = [{"id": f"mtai|{m['id']}", "provider": "mtai", "name": f"{m['tier']} · {m['model']}", "label": "MTAI built-in",
            "local": True, "tier": m["tier"]} for m in imagegen.CATALOG if imagegen.installed(m["id"])]
    a1111 = _probe(A1111_URL + "/sdapi/v1/sd-models")
    if isinstance(a1111, list):
        for m in a1111:
            out.append({"id": f"a1111|{m.get('title')}", "provider": "a1111", "name": m.get("model_name") or m.get("title"),
                        "label": "Stable Diffusion WebUI", "local": True})
    comfy = _probe(COMFY_URL + "/object_info/CheckpointLoaderSimple")
    if isinstance(comfy, dict):
        try:
            names = comfy["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        except Exception:
            names = []
        for n in names if isinstance(names, list) else []:
            out.append({"id": f"comfy|{n}", "provider": "comfy", "name": n, "label": "ComfyUI", "local": True})
    st = _store()
    with _LOCK:
        for pid in ("openai", "gemini", "xai"):
            if pid in st:
                for m in CLOUD["images"].get(pid) or []:
                    out.append({**m, "blocked": privacy})
    return {"backends": out, "a1111": isinstance(a1111, list), "comfy": isinstance(comfy, dict),
            "a1111_url": A1111_URL, "comfy_url": COMFY_URL}


def _save_image(raw):
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    ext = "jpg" if raw[:3] == b"\xff\xd8\xff" else "webp" if raw[8:12] == b"WEBP" else "png"
    name = f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(5)}.{ext}"
    (IMG_DIR / name).write_bytes(raw)
    return name


def _dims(aspect, base):
    a, b = ASPECTS.get(aspect, (1, 1))
    if a == b:
        return base, base
    long_, short = int(base * 1.22) // 64 * 64, int(base * 0.82) // 64 * 64
    return (long_, short) if a > b else (short, long_)


def _openai_size(model, aspect):
    if "dall-e-3" in model:
        return {"square": "1024x1024", "wide": "1792x1024", "tall": "1024x1792"}[aspect]
    if "dall-e-2" in model:
        return "1024x1024"
    return {"square": "1024x1024", "wide": "1536x1024", "tall": "1024x1536"}[aspect]


def _cloud_image(pid, model, prompt, aspect):
    key = get_key(pid)
    if not key:
        raise ProviderError(f"No API key for {PROV[pid]['name']}.")
    body = {"model": model, "prompt": prompt, "n": 1}
    if pid == "openai":
        body["size"] = _openai_size(model, aspect)
        if "dall-e" in model:
            body["response_format"] = "b64_json"
    else:
        body["response_format"] = "b64_json"
    try:
        r = _http(base_url(pid) + "/images/generations", body, {"Authorization": f"Bearer {key}"}, timeout=300)
    except urllib.error.HTTPError as e:
        raise ProviderError(error_text(e, PROV[pid]["name"]))
    except urllib.error.URLError as e:
        raise ProviderError(f"Cannot reach {PROV[pid]['name']}: {e.reason}")
    items = r.get("data") or []
    if not items:
        raise ProviderError(f"{PROV[pid]['name']} returned no image (the prompt may have been blocked).")
    it = items[0]
    if it.get("b64_json"):
        raw = base64.b64decode(it["b64_json"])
    elif it.get("url"):
        raw = _http_bytes(it["url"])
    else:
        raise ProviderError("The answer had no image data.")
    return raw, it.get("revised_prompt")


def _a1111_image(title, prompt, negative, aspect, steps, seed):
    base = 1024 if re.search(r"xl|pony|illustrious|flux|sd3", title, re.I) else 512
    w, h = _dims(aspect, base)
    body = {"prompt": prompt, "negative_prompt": negative or "", "steps": steps or 25, "width": w, "height": h,
            "cfg_scale": 6.5, "seed": seed if seed is not None else -1, "sampler_name": "Euler a",
            "override_settings": {"sd_model_checkpoint": title}, "override_settings_restore_afterwards": False}
    try:
        r = _http(A1111_URL + "/sdapi/v1/txt2img", body, timeout=900)
    except urllib.error.HTTPError as e:
        raise ProviderError(error_text(e, "Stable Diffusion WebUI"))
    except urllib.error.URLError:
        raise ProviderError(f"Stable Diffusion WebUI is not running on {A1111_URL} (start it with --api).")
    imgs = r.get("images") or []
    if not imgs:
        raise ProviderError("The WebUI returned no image.")
    return base64.b64decode(imgs[0].split(",", 1)[-1])


def _comfy_image(ckpt, prompt, negative, aspect, steps, seed):
    base = 1024 if re.search(r"xl|pony|illustrious|sd3", ckpt, re.I) else 512
    w, h = _dims(aspect, base)
    seed = seed if seed is not None else secrets.randbelow(2 ** 31)
    wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative or "blurry, low quality", "clip": ["4", 1]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "3": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": steps or 25, "cfg": 6.5, "sampler_name": "euler",
                                                   "scheduler": "normal", "denoise": 1, "model": ["4", 0],
                                                   "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "MTAI", "images": ["8", 0]}},
    }
    try:
        r = _http(COMFY_URL + "/prompt", {"prompt": wf, "client_id": secrets.token_hex(8)}, timeout=30)
    except urllib.error.HTTPError as e:
        raise ProviderError(error_text(e, "ComfyUI"))
    except urllib.error.URLError:
        raise ProviderError(f"ComfyUI is not running on {COMFY_URL}.")
    pid = r.get("prompt_id")
    if not pid:
        raise ProviderError("ComfyUI did not accept the workflow: " + json.dumps(r.get("node_errors") or r)[:300])
    t0 = time.time()
    while time.time() - t0 < 900:
        time.sleep(0.8)
        hist = _probe(COMFY_URL + "/history/" + quote(pid), timeout=5) or {}
        entry = hist.get(pid)
        if not entry:
            continue
        st = entry.get("status") or {}
        if st.get("status_str") == "error":
            raise ProviderError("ComfyUI failed while generating (see its console).")
        for out in (entry.get("outputs") or {}).values():
            for im in out.get("images") or []:
                q = urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""), "type": im.get("type", "output")})
                return _http_bytes(COMFY_URL + "/view?" + q)
    raise ProviderError("ComfyUI took longer than 15 minutes.")


def generate_image(req, privacy=False, free_gpu=None):
    backend = str(req.get("backend") or "")
    prompt = str(req.get("prompt") or "").strip()
    if not prompt:
        raise ProviderError("Write what the image should show.")
    if "|" not in backend:
        raise ProviderError("Pick an image model first.")
    kind, model = backend.split("|", 1)
    aspect = req.get("aspect") if req.get("aspect") in ASPECTS else "square"
    steps = max(1, min(80, int(req.get("steps") or 25)))
    seed = req.get("seed")
    seed = int(seed) if str(seed or "").lstrip("-").isdigit() and int(seed) >= 0 else None
    t0 = time.time()
    revised = None
    if kind == "mtai":
        import imagegen
        IMG_DIR.mkdir(parents=True, exist_ok=True)
        name = f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(5)}.png"
        try:
            r = imagegen.generate(model, prompt, req.get("negative"), aspect, seed, IMG_DIR / name, _dims, free_gpu)
        except imagegen.GenError as e:
            raise ProviderError(str(e))
        m = imagegen.CAT[model]
        return {"url": "/img/" + name, "name": name, "model": f"{m['tier']} · {m['model']}", "backend": backend, "prompt": prompt,
                "revised": None, "aspect": aspect, "time": round(time.time() - t0, 1), "seed": r.get("seed")}
    if kind == "a1111":
        raw = _a1111_image(model, prompt, req.get("negative"), aspect, steps, seed)
    elif kind == "comfy":
        raw = _comfy_image(model, prompt, req.get("negative"), aspect, steps, seed)
    elif kind in ("openai", "gemini", "xai"):
        if privacy:
            raise ProviderError("Privacy mode is on: cloud image models are off. Local Stable Diffusion and ComfyUI still work.")
        raw, revised = _cloud_image(kind, model, prompt, aspect)
    else:
        raise ProviderError("Unknown image model.")
    name = _save_image(raw)
    return {"url": "/img/" + name, "name": name, "model": model, "backend": backend, "prompt": prompt,
            "revised": revised, "aspect": aspect, "time": round(time.time() - t0, 1)}


def list_images(limit=120):
    if not IMG_DIR.is_dir():
        return []
    files = sorted((f for f in IMG_DIR.iterdir() if IMG_NAME_RE.match(f.name)), key=lambda f: f.stat().st_mtime, reverse=True)
    return [{"url": "/img/" + f.name, "name": f.name, "t": f.stat().st_mtime} for f in files[:limit]]


def delete_image(name):
    if IMG_NAME_RE.match(name or ""):
        (IMG_DIR / name).unlink(missing_ok=True)
