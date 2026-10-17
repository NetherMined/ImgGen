import copy
import json
import os
import re
import urllib.parse
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8189
COMFY = "http://127.0.0.1:8188"
INPUT_DIR = os.environ.get("COMFY_INPUT", r"D:\Personal\ImGen\ComfyUI_windows_portable\ComfyUI\input")
OUTPUT_DIR = os.environ.get("COMFY_OUTPUT", r"D:\Personal\ImGen\ComfyUI_windows_portable\ComfyUI\output")
ALLOWED_UPLOADS = {"photo.png", "girl.png", "guy.png", "couple.png", "pose.png", "gen_body.png", "cleanup.png"}
MAX_UPLOAD = 20 * 1024 * 1024
REQUIRED_INPUTS = {
    "01": ["photo.png"],
    "02": ["photo.png", "pose.png"],
    "03": ["photo.png"],
    "04": [],
    "05": ["girl.png", "guy.png"],
    "06": ["couple.png"],
    "07": [],
    "09": ["photo.png"],
    "10": ["photo.png"],
    "11": ["gen_body.png", "photo.png"],
    "12": ["photo.png"],
    "13": ["photo.png"],
    "14": ["cleanup.png"],
}
GALLERY_MAX_BODY = 64 * 1024
GALLERY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gallery.json")
STUDIO_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "studio.html")

def load_gallery():
    try:
        with open(GALLERY_FILE) as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except (OSError, ValueError):
        return []

def save_gallery(items):
    with open(GALLERY_FILE, "w") as f:
        json.dump(items, f)

WORKFLOWS = [
    {"id": "01", "file": "01_photo_to_nsfw_image.json", "title": "Outfit change",
     "desc": "Same pose and face, new outfit", "uploads": ["photo.png"],
     "params_help": {
         "prompt": "Describe the new outfit concretely.",
         "seed": "Same seed + settings = same image.",
         "steps": "20-30 is the sweet spot.",
         "denoise": "~0.4 keeps close; 0.55-0.65 for outfit swaps.",
         "face_weight": "Lower drifts; above 0.85 can look pasted-on.",
         "uploads": "Front-facing, well-lit photos lock best."}},
    {"id": "02", "file": "02_pose_change.json", "title": "Pose change",
     "desc": "New pose via pose reference", "uploads": ["photo.png", "pose.png"],
     "params_help": {
         "prompt": "Describe the new pose and outfit.",
         "seed": "Same seed + settings = same image.",
         "steps": "20-30 is the sweet spot.",
         "denoise": "0.55-0.65 for pose swaps.",
         "face_weight": "Lower drifts; above 0.85 can look pasted-on.",
         "uploads": "Front-facing, well-lit photos lock best."}},
    {"id": "03", "file": "03_photo_to_video_ltxv.json", "title": "Photo to video",
     "desc": "LTX-Video, 97 frames (~4s)", "uploads": ["photo.png"],
     "params_help": {
         "prompt": "Describe movement only.",
         "seed": "Same seed + settings = same result.",
         "steps": "Fewer steps for video.",
         "uploads": "Front-facing, well-lit photos lock best."}},
    {"id": "04", "file": "04_video_animatediff.json", "title": "AnimateDiff clip",
     "desc": "Short prompt-driven motion, 16 frames", "uploads": [],
     "params_help": {
         "prompt": "Describe subject + motion.",
         "seed": "Same seed + settings = same result.",
         "steps": "25 typical."}},
    {"id": "05", "file": "05_couple_still_dualface.json", "title": "Couple still",
     "desc": "Two photos become one couple scene", "uploads": ["girl.png", "guy.png"],
     "params_help": {
         "prompt": "Describe the couple scene.",
         "seed": "Same seed + settings = same image.",
         "steps": "20-30 is the sweet spot.",
         "face_weight": "How strictly faces must match.",
         "face_weight_2": "Second face weight.",
         "uploads": "Front-facing, well-lit photos lock best."}},
    {"id": "06", "file": "06_couple_still_to_video_ltxv.json", "title": "Couple video",
     "desc": "Still becomes a kissing-motion clip", "uploads": ["couple.png"],
     "params_help": {
         "prompt": "Describe movement only.",
         "seed": "Same seed + settings = same result.",
         "steps": "Fewer steps for video.",
         "uploads": "Front-facing, well-lit photos lock best."}},
    {"id": "07", "file": "07_prompt_to_image.json", "title": "Prompt to image",
     "desc": "Pure text-to-image, no photo needed", "uploads": [],
     "params_help": {
         "prompt": "Describe the whole image.",
         "seed": "Same seed + settings = same image.",
         "steps": "20-30 is the sweet spot."}},
    {"id": "09", "file": "09_pose_preset.json", "title": "Pose preset",
     "desc": "Your photo, a chosen preset pose, face locked", "uploads": ["photo.png"],
     "presets": ["skel_standing", "skel_sitting", "skel_kneeling", "skel_lying_side",
                 "skel_lying_back", "skel_bending", "skel_couple_cuddle",
                 "skel_couple_kiss", "skel_couple_lying"],
     "params_help": {
         "prompt": "Describe the outfit and scene.",
         "seed": "Same seed + settings = same image.",
         "steps": "20-30 is the sweet spot.",
         "denoise": "0.55-0.65 typical.",
         "face_weight": "Lower drifts; above 0.85 can look pasted-on.",
         "uploads": "Front-facing, well-lit photos lock best."}},
    {"id": "10", "file": "10_txt2img_facelock.json", "title": "Face-lock create",
     "desc": "New body/outfit, her face locked", "uploads": ["photo.png"],
     "params_help": {
         "prompt": "Describe the full image.",
         "seed": "Same seed + settings = same image.",
         "steps": "20-30 is the sweet spot.",
         "face_weight": "How strictly faces must match.",
         "uploads": "Front-facing, well-lit photos lock best."}},
    {"id": "11", "file": "11_faceswap.json", "title": "Face swap",
     "desc": "Her real face onto any generated body", "uploads": ["gen_body.png", "photo.png"],
     "params_help": {
         "uploads": "Front-facing, well-lit photos lock best."}},
    {"id": "12", "file": "12_inpaint_undress.json", "title": "Undress inpaint",
     "desc": "Repaint clothes only, face untouched", "uploads": ["photo.png"],
     "params_help": {
         "prompt": "Describe the skin/body to paint into the masked area.",
         "seed": "Same seed + settings = same image.",
         "steps": "20-30 is the sweet spot.",
         "denoise": "1.0 for full inpaint; lower for subtle.",
         "cfg": "5.0 typical; higher forces the prompt more.",
         "uploads": "Front-facing, well-lit photos lock best."}},
    {"id": "13", "file": "13_inpaint_proper.json", "title": "Inpaint proper",
     "desc": "Dedicated inpaint UNET for cleaner strap/clothing removal", "uploads": ["photo.png"],
     "params_help": {
         "prompt": "Describe the skin/body to paint. Better on straps and edges.",
         "seed": "Same seed + settings = same image.",
         "steps": "20-30 is the sweet spot.",
         "denoise": "1.0 for full; lower for cleanup.",
         "cfg": "5.0 typical.",
         "uploads": "Front-facing, well-lit photos lock best."}},
    {"id": "14", "file": "14_cleanup_pass.json", "title": "Cleanup pass",
     "desc": "Second pass to clean residual straps/seams", "uploads": ["cleanup.png"],
     "params_help": {
         "prompt": "Describe the clean skin/body for residual areas.",
         "seed": "Same seed + settings = same image.",
         "steps": "20-30 typical.",
         "denoise": "0.4-0.6 for residual cleanup.",
         "cfg": "5.0 typical.",
         "uploads": "Use a previous result as cleanup.png."}},
]

WORKFLOWS_DIR = os.environ.get("IMGEN_WORKFLOWS", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workflows"))
TEMPLATES = {}

def load_template(wfid):
    fname = next(w["file"] for w in WORKFLOWS if w["id"] == wfid)
    if fname not in TEMPLATES:
        path = os.path.join(WORKFLOWS_DIR, fname)
        with open(path) as f:
            TEMPLATES[fname] = json.load(f)
    return copy.deepcopy(TEMPLATES[fname])

PARAMS = {
    "01": {"prompt": ("6", "text"), "seed": ("12", "seed", int),
           "steps": ("12", "steps", int), "denoise": ("12", "denoise", float),
           "face_weight": ("11", "weight", float)},
    "02": {"prompt": ("6", "text"), "seed": ("12", "seed", int),
           "steps": ("12", "steps", int), "denoise": ("12", "denoise", float),
           "face_weight": ("11", "weight", float)},
    "03": {"prompt": ("34", "text"), "seed": ("40", "noise_seed", int),
           "steps": ("38", "steps", int)},
    "04": {"prompt": ("53", "text"), "seed": ("55", "seed", int),
           "steps": ("55", "steps", int)},
    "05": {"prompt": ("5", "text"), "seed": ("12", "seed", int),
           "steps": ("12", "steps", int), "face_weight": ("9", "weight", float),
           "face_weight_2": ("10", "weight", float)},
    "06": {"prompt": ("34", "text"), "seed": ("40", "noise_seed", int),
           "steps": ("38", "steps", int)},
    "07": {"prompt": ("62", "text"), "seed": ("64", "seed", int),
           "steps": ("64", "steps", int)},
    "09": {"prompt": ("6", "text"), "seed": ("12", "seed", int),
           "steps": ("12", "steps", int), "denoise": ("12", "denoise", float),
           "face_weight": ("11", "weight", float)},
    "10": {"prompt": ("62", "text"), "seed": ("69", "seed", int),
           "steps": ("69", "steps", int), "face_weight": ("68", "weight", float)},
    "12": {"prompt": ("95", "text"), "seed": ("99", "seed", int),
           "steps": ("99", "steps", int), "denoise": ("99", "denoise", float),
           "cfg": ("99", "cfg", float)},
    "13": {"prompt": ("95", "text"), "seed": ("99", "seed", int),
           "steps": ("99", "steps", int), "denoise": ("99", "denoise", float),
           "cfg": ("99", "cfg", float)},
    "14": {"prompt": ("95", "text"), "seed": ("99", "seed", int),
           "steps": ("99", "steps", int), "denoise": ("99", "denoise", float),
           "cfg": ("99", "cfg", float)},
}

ASPECT_LADDER = ((832, 1216), (768, 1344), (640, 1536), (1024, 1024),
                 (1216, 832), (1344, 768), (1536, 640))

def read_image_dims(path):
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if len(head) < 8:
                return None
            if head[0:8] == b"\x89PNG\r\n\x1a\n":
                if len(head) < 24:
                    return None
                if head[12:16] != b"IHDR":
                    return None
                w = int.from_bytes(head[16:20], "big")
                h = int.from_bytes(head[20:24], "big")
                if w <= 0 or h <= 0:
                    return None
                return (w, h)
            if head[0:2] != b"\xff\xd8":
                return None
            f.seek(2)
            data = f.read()
    except (OSError, ValueError):
        return None
    try:
        i = 0
        n = len(data)
        while i + 1 < n:
            if data[i] != 0xFF:
                i += 1
                continue
            while i < n and data[i] == 0xFF:
                i += 1
            if i >= n:
                break
            marker = data[i]
            i += 1
            if marker == 0xD8 or marker == 0xD9 or (0xD0 <= marker <= 0xD7) or marker == 0x01:
                continue
            if i + 1 >= n:
                break
            seg_len = (data[i] << 8) + data[i + 1]
            if seg_len < 2:
                break
            if marker in (0xC0, 0xC1, 0xC2):
                if i + 7 >= n:
                    break
                h = (data[i + 3] << 8) + data[i + 4]
                w = (data[i + 5] << 8) + data[i + 6]
                if w <= 0 or h <= 0:
                    return None
                return (w, h)
            i += seg_len - 2
    except (IndexError, ValueError):
        return None
    return None

def _write_gray_png(path, w, h, row_vals):
    import struct
    import zlib
    raw = bytearray()
    for v in row_vals:
        raw.append(0)
        raw.extend(bytes((v,)) * w)
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw)))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)

def fill_template(wfid, params):
    wf = load_template(wfid)
    if wfid in ("01", "02", "09"):
        try:
            dims = read_image_dims(os.path.join(INPUT_DIR, "photo.png"))
        except Exception:
            dims = None
        if dims is not None:
            w, h = dims
            src_ar = w / h
            tw, th = min(ASPECT_LADDER,
                         key=lambda c: abs(src_ar - c[0] / c[1]))
            try:
                if "4" in wf and isinstance(wf["4"].get("inputs"), dict):
                    wf["4"]["inputs"]["width"] = tw
                    wf["4"]["inputs"]["height"] = th
            except (TypeError, AttributeError):
                pass
    for name, spec in PARAMS.get(wfid, {}).items():
        if name not in params:
            continue
        if params[name] == "":
            continue
        node, key = spec[0], spec[1]
        cast = spec[2] if len(spec) > 2 else (lambda v: v)
        try:
            wf[node]["inputs"][key] = cast(params[name])
        except (KeyError, TypeError):
            pass
    if wfid == "09":
        pose = params.get("pose", "")
        if pose not in ("", None):
            pose = str(pose)
            if not re.fullmatch(r"[a-z_]+", pose):
                raise ValueError("bad pose: " + pose)
            if not os.path.isfile(os.path.join(INPUT_DIR, "poses", pose + ".png")):
                raise ValueError("unknown pose: " + pose)
            try:
                wf["20"]["inputs"]["image"] = "poses/" + pose + ".png"
            except (TypeError, AttributeError, KeyError):
                pass
    if wfid == "04":
        try:
            wf["52"]["inputs"]["batch_size"] = min(int(wf["52"]["inputs"]["batch_size"]), 16)
        except (KeyError, TypeError):
            pass
    if wfid in ("12", "13", "14"):
        try:
            src_name = "cleanup.png" if wfid == "14" else "photo.png"
            try:
                if isinstance(wf.get("90"), dict) and isinstance(wf["90"].get("inputs"), dict):
                    wf["90"]["inputs"]["image"] = src_name
            except (TypeError, AttributeError):
                pass
            dims = read_image_dims(os.path.join(INPUT_DIR, src_name))
            if dims is not None:
                w, h = dims
                top = 0.12 * h
                band = 0.15 * h
                row_vals = []
                for y in range(h):
                    yc = y + 0.5
                    if band > 0 and abs(yc - top) < band / 2:
                        v = int(round(255 * ((yc - (top - band / 2)) / band)))
                    elif yc >= top:
                        v = 255
                    else:
                        v = 0
                    row_vals.append(max(0, min(255, v)))
                mask_name = "auto_mask.png"
                _write_gray_png(os.path.join(INPUT_DIR, mask_name), w, h, row_vals)
                try:
                    if "92" in wf and isinstance(wf["92"].get("inputs"), dict):
                        wf["92"]["inputs"]["image"] = mask_name
                except (TypeError, AttributeError):
                    pass
        except Exception:
            pass
    if "seed" in params and params["seed"] != "":
        for node_id in ("12", "40", "55", "99"):
            if node_id in wf and "seed" in wf[node_id].get("inputs", {}):
                wf[node_id]["inputs"]["seed"] = max(0, min(int(params["seed"]), 2**31 - 1))
            if node_id in wf and "noise_seed" in wf[node_id].get("inputs", {}):
                wf[node_id]["inputs"]["noise_seed"] = max(0, min(int(params["seed"]), 2**31 - 1))
    return wf

class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            try:
                with open(STUDIO_HTML, "rb") as f:
                    data = f.read()
            except OSError:
                return self._json({"error": "not found"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/api/workflows":
            return self._json({"workflows": WORKFLOWS})
        if self.path == "/api/health":
            comfy = False
            try:
                with urllib.request.urlopen(COMFY + "/system_stats", timeout=2.5) as r:
                    r.read(64)
                comfy = True
            except (urllib.error.URLError, OSError):
                comfy = False
            return self._json({"studio": True, "comfy": comfy})
        if self.path == "/api/poses":
            poses_dir = os.path.join(INPUT_DIR, "poses")
            try:
                names = sorted(
                    os.path.splitext(f)[0] for f in os.listdir(poses_dir)
                    if f.lower().endswith(".png")
                    and os.path.isfile(os.path.join(poses_dir, f)))
            except OSError:
                names = []
            return self._json({"poses": names})
        if self.path == "/api/inputs":
            result = {}
            for name in ALLOWED_UPLOADS:
                fpath = os.path.join(INPUT_DIR, name)
                exists = os.path.isfile(fpath)
                mtime = os.path.getmtime(fpath) if exists else 0
                result[name] = {"exists": exists, "mtime": mtime}
            return self._json({"inputs": result})
        if self.path.startswith("/inputs/"):
            raw = self.path[len("/inputs/"):].split("?")[0].split("/")[0]
            raw = urllib.parse.unquote(raw)
            base = os.path.basename(raw)
            if base not in ALLOWED_UPLOADS:
                return self._json({"error": "forbidden"}, 403)
            fpath = os.path.join(INPUT_DIR, base)
            if not os.path.isfile(fpath):
                return self._json({"error": "not found"}, 404)
            try:
                with open(fpath, "rb") as f:
                    data = f.read()
            except OSError:
                return self._json({"error": "not found"}, 404)
            ctype = "image/png" if base.lower().endswith(".png") else "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path.startswith("/outputs/"):
            raw = self.path[len("/outputs/"):].split("?")[0].split("/")[0]
            raw = urllib.parse.unquote(raw)
            base = os.path.basename(raw)
            fpath = os.path.join(OUTPUT_DIR, base)
            if not base or not os.path.isfile(fpath):
                return self._json({"error": "not found"}, 404)
            try:
                with open(fpath, "rb") as f:
                    data = f.read()
            except OSError:
                return self._json({"error": "not found"}, 404)
            if base.lower().endswith(".png"):
                ctype = "image/png"
            elif base.lower().endswith((".jpg", ".jpeg")):
                ctype = "image/jpeg"
            elif base.lower().endswith(".mp4"):
                ctype = "video/mp4"
            else:
                ctype = "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/api/gallery":
            items = load_gallery()
            return self._json({"items": list(reversed(items))})
        if self.path.startswith("/api/status/"):
            pid = self.path[len("/api/status/"):].split("?")[0]
            try:
                with urllib.request.urlopen(COMFY + "/history/" + urllib.parse.quote(pid), timeout=10) as r:
                    hist = json.loads(r.read())
            except (urllib.error.URLError, OSError, ValueError):
                return self._json({"completed": False, "failed": True,
                                   "error": "ComfyUI not reachable (it may have restarted) - press Generate to retry."}, 502)
            entry = hist.get(pid)
            if not entry:
                running = False
                queue_pos = None
                queue_ok = False
                try:
                    with urllib.request.urlopen(COMFY + "/queue", timeout=10) as r:
                        q = json.loads(r.read())
                    queue_ok = True
                    for ent in (q.get("queue_running") or []):
                        if len(ent) > 1 and str(ent[1]) == pid:
                            running = True
                            break
                    if not running:
                        for i, ent in enumerate(q.get("queue_pending") or []):
                            if len(ent) > 1 and str(ent[1]) == pid:
                                queue_pos = i + 1
                                break
                except (urllib.error.URLError, OSError, ValueError):
                    pass
                if queue_ok and not running and queue_pos is None:
                    return self._json({"completed": False, "failed": True,
                                       "error": "This job is no longer in ComfyUI's queue (it may have been interrupted). Press Generate to retry."})
                return self._json({"completed": False, "failed": False, "outputs": [],
                                   "error": "", "running": running, "queue_pos": queue_pos})
            outputs = []
            for node in (entry.get("outputs") or {}).values():
                for img in node.get("images") or []:
                    if img.get("filename"):
                        outputs.append(img["filename"])
                for vid in node.get("videos") or []:
                    if vid.get("filename"):
                        outputs.append(vid["filename"])
            status = entry.get("status") or {}
            completed = bool(status.get("completed"))
            failed = bool(status.get("status_str") == "error")
            error = ""
            if failed:
                msgs = status.get("messages") or []
                last = msgs[-1] if msgs else None
                if isinstance(last, (list, tuple)) and len(last) >= 2 and isinstance(last[1], dict):
                    error = str(last[1].get("exception_message") or last[1].get("message") or last[0])
                elif last is not None:
                    error = str(last)
            return self._json({"completed": completed, "failed": failed, "outputs": outputs, "error": error})
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path.startswith("/api/upload"):
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            name = params.get("name", [""])[0]
            if name not in ALLOWED_UPLOADS:
                return self._json({"error": "name not allowed"}, 400)
            try:
                length = int(self.headers.get("Content-Length", 0))
            except (TypeError, ValueError):
                return self._json({"error": "bad content length"}, 400)
            if length > MAX_UPLOAD:
                return self._json({"error": "too large"}, 413)
            raw = self.rfile.read(length) if length else b""
            if len(raw) > MAX_UPLOAD:
                return self._json({"error": "too large"}, 413)
            is_png = raw[:8] == bytes([137, 80, 78, 71, 13, 10, 26, 10])
            is_jpg = raw[:2] == bytes([255, 216])
            is_webp = raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"
            if not (is_png or is_jpg or is_webp):
                return self._json({"error": "upload must be a PNG, JPEG or WebP image"}, 400)
            try:
                os.makedirs(INPUT_DIR, exist_ok=True)
                with open(os.path.join(INPUT_DIR, name), "wb") as f:
                    f.write(raw)
            except OSError:
                return self._json({"error": "write failed"}, 500)
            return self._json({"ok": True})
        if self.path == "/api/generate":
            try:
                length = int(self.headers.get("Content-Length", 0))
            except (TypeError, ValueError):
                return self._json({"error": "bad content length"}, 400)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode() or "{}")
            except Exception:
                return self._json({"error": "invalid json"}, 400)
            wfid = body.get("workflow")
            params = body.get("params", {})
            if (wfid == "09" and isinstance(params, dict) and "pose" not in params
                    and "pose" in body):
                params["pose"] = body["pose"]
            if not any(w["id"] == wfid for w in WORKFLOWS):
                return self._json({"error": "unknown workflow: " + str(wfid)}, 400)
            if wfid in REQUIRED_INPUTS:
                missing = [n for n in REQUIRED_INPUTS[wfid]
                           if not os.path.isfile(os.path.join(INPUT_DIR, n))]
                if missing:
                    return self._json({"error": "missing inputs: " + ", ".join(missing),
                                       "missing": missing}, 400)
            try:
                wf = fill_template(wfid, params)
            except Exception as e:
                return self._json({"error": str(e)}, 400)
            # free stale models first so this run gets the full VRAM budget
            try:
                freq = urllib.request.Request(COMFY + "/free",
                                              data=b'{"unload_models": true, "free_memory": true}',
                                              headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(freq, timeout=15) as fr:
                    fr.read(64)
            except (urllib.error.URLError, OSError):
                pass
            payload = json.dumps({"prompt": wf}).encode()
            req = urllib.request.Request(COMFY + "/prompt", data=payload,
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    try:
                        resp = json.loads(r.read())
                    except (ValueError, UnicodeDecodeError):
                        return self._json({"error": "ComfyUI returned invalid response."}, 502)
            except urllib.error.URLError:
                return self._json({"error": "ComfyUI not running. Start it with start_server.bat, then retry."}, 502)
            except OSError:
                return self._json({"error": "ComfyUI not running. Start it with start_server.bat, then retry."}, 502)
            return self._json({"prompt_id": resp.get("prompt_id")})
        if self.path == "/api/gallery":
            try:
                length = int(self.headers.get("Content-Length", 0))
            except (TypeError, ValueError):
                return self._json({"error": "bad content length"}, 400)
            if length > GALLERY_MAX_BODY:
                return self._json({"error": "too large"}, 413)
            raw = self.rfile.read(length) if length else b"{}"
            if len(raw) > GALLERY_MAX_BODY:
                return self._json({"error": "too large"}, 413)
            try:
                body = json.loads(raw.decode() or "{}")
            except Exception:
                return self._json({"error": "invalid json"}, 400)
            if not body.get("file") or not body.get("workflow"):
                return self._json({"error": "file and workflow are required"}, 400)
            items = load_gallery()
            items.append({"file": body.get("file"), "workflow": body.get("workflow"),
                          "params": body.get("params", {}), "prompt_id": body.get("prompt_id")})
            items = items[-200:]
            save_gallery(items)
            return self._json({"ok": True})
        if self.path == "/api/gallery/delete":
            try:
                length = int(self.headers.get("Content-Length", 0))
            except (TypeError, ValueError):
                return self._json({"error": "bad content length"}, 400)
            if length > GALLERY_MAX_BODY:
                return self._json({"error": "too large"}, 413)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode() or "{}")
            except Exception:
                return self._json({"error": "invalid json"}, 400)
            fname = str(body.get("file") or "")
            name = os.path.basename(fname)
            if not name or name != fname:
                return self._json({"error": "bad file name"}, 400)
            items = load_gallery()
            kept = [it for it in items if it.get("file") != name]
            removed = len(items) - len(kept)
            if not removed:
                return self._json({"error": "not in gallery", "removed": 0}, 404)
            save_gallery(kept)
            deleted_file = False
            try:
                fpath = os.path.join(OUTPUT_DIR, name)
                if os.path.isfile(fpath):
                    os.remove(fpath)
                    deleted_file = True
            except OSError:
                pass
            return self._json({"ok": True, "removed": removed, "deleted_file": deleted_file})
        return self._json({"error": "not found"}, 404)

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
