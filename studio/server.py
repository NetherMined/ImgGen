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
INPUT_DIR = r"D:\Personal\ImGen\ComfyUI_windows_portable\ComfyUI\input"
OUTPUT_DIR = r"D:\Personal\ImGen\ComfyUI_windows_portable\ComfyUI\output"
ALLOWED_UPLOADS = {"photo.png", "girl.png", "guy.png", "couple.png", "pose.png", "gen_body.png"}
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
    {"id": "01", "file": "01_photo_to_nsfw_image.json", "title": "01 · Outfit change",
     "desc": "Same pose and face, new outfit", "uploads": ["photo.png"],
     "params_help": {
         "prompt": "Describe exactly what you want. Name outfits/scenes concretely ('black lace bra') \u2014 vague verbs like 'remove' work poorly.",
         "seed": "Same seed + same settings = same image. Dice = fresh random result.",
         "steps": "More steps = finer detail but slower. 25-35 is the sweet spot; video uses fewer, larger steps.",
         "denoise": "How much to change the photo. ~0.4 keeps it close; 0.55-0.65 allows outfit/pose swaps; above 0.7 face and body start drifting.",
         "face_weight": "How strictly faces must match the input photos. Lower drifts; above 0.85 can look pasted-on.",
         "uploads": "Front-facing, well-lit photos lock best. Square-ish crops preferred."}},
    {"id": "02", "file": "02_pose_change.json", "title": "02 · Pose change",
     "desc": "New pose via pose reference", "uploads": ["photo.png", "pose.png"],
     "params_help": {
         "prompt": "Describe exactly what you want. Name outfits/scenes concretely ('black lace bra') \u2014 vague verbs like 'remove' work poorly.",
         "seed": "Same seed + same settings = same image. Dice = fresh random result.",
         "steps": "More steps = finer detail but slower. 25-35 is the sweet spot; video uses fewer, larger steps.",
         "denoise": "How much to change the photo. ~0.4 keeps it close; 0.55-0.65 allows outfit/pose swaps; above 0.7 face and body start drifting.",
         "face_weight": "How strictly faces must match the input photos. Lower drifts; above 0.85 can look pasted-on.",
         "uploads": "Front-facing, well-lit photos lock best. Square-ish crops preferred."}},
    {"id": "03", "file": "03_photo_to_video_ltxv.json", "title": "03 · Photo to video",
     "desc": "LTX-Video, 97 frames (~4s), recommended", "uploads": ["photo.png"],
     "params_help": {
         "prompt": "Describe movement only \u2014 the look comes from your input image.",
         "seed": "Same seed + same settings = same image. Dice = fresh random result.",
         "steps": "More steps = finer detail but slower. 25-35 is the sweet spot; video uses fewer, larger steps.",
         "uploads": "Front-facing, well-lit photos lock best. Square-ish crops preferred."}},
    {"id": "04", "file": "04_video_animatediff.json", "title": "04 · AnimateDiff clip",
     "desc": "Short prompt-driven motion, 16 frames", "uploads": [],
     "params_help": {
         "prompt": "Describe subject + motion. No photo is used; faces will not match anyone.",
         "seed": "Same seed + same settings = same image. Dice = fresh random result.",
         "steps": "More steps = finer detail but slower. 25-35 is the sweet spot; video uses fewer, larger steps."}},
    {"id": "05", "file": "05_couple_still_dualface.json", "title": "05 · Couple still",
     "desc": "Two photos become one couple scene", "uploads": ["girl.png", "guy.png"],
     "params_help": {
         "prompt": "Describe exactly what you want. Name outfits/scenes concretely ('black lace bra') \u2014 vague verbs like 'remove' work poorly.",
         "seed": "Same seed + same settings = same image. Dice = fresh random result.",
         "steps": "More steps = finer detail but slower. 25-35 is the sweet spot; video uses fewer, larger steps.",
         "face_weight": "How strictly faces must match the input photos. Lower drifts; above 0.85 can look pasted-on.",
         "face_weight_2": "How strictly faces must match the input photos. Lower drifts; above 0.85 can look pasted-on.",
         "uploads": "Front-facing, well-lit photos lock best. Square-ish crops preferred."}},
    {"id": "06", "file": "06_couple_still_to_video_ltxv.json", "title": "06 · Couple video",
     "desc": "Still becomes a kissing-motion clip", "uploads": ["couple.png"],
     "params_help": {
         "prompt": "Describe movement only \u2014 the look comes from your input image.",
         "seed": "Same seed + same settings = same image. Dice = fresh random result.",
         "steps": "More steps = finer detail but slower. 25-35 is the sweet spot; video uses fewer, larger steps.",
         "uploads": "Front-facing, well-lit photos lock best. Square-ish crops preferred."}},
    {"id": "07", "file": "07_prompt_to_image.json", "title": "07 · Prompt to image",
     "desc": "Pure text-to-image, no photo needed", "uploads": [],
     "params_help": {
         "prompt": "Describe the whole image \u2014 subject, pose, clothes, setting. No photo is used.",
         "seed": "Same seed + same settings = same image. Dice = fresh random result.",
         "steps": "More steps = finer detail but slower. 25-35 is the sweet spot; video uses fewer, larger steps."}},
    {"id": "09", "file": "09_pose_preset.json", "title": "09 · Pose preset",
     "desc": "Your photo, a chosen preset pose, face locked", "uploads": ["photo.png"],
     "presets": ["skel_standing", "skel_sitting", "skel_kneeling", "skel_lying_side",
                 "skel_lying_back", "skel_bending", "skel_couple_cuddle",
                 "skel_couple_kiss", "skel_couple_lying"],
     "params_help": {
         "prompt": "Describe exactly what you want. Name outfits/scenes concretely ('black lace bra') \u2014 vague verbs like 'remove' work poorly.",
         "seed": "Same seed + same settings = same image. Dice = fresh random result.",
         "steps": "More steps = finer detail but slower. 25-35 is the sweet spot; video uses fewer, larger steps.",
         "denoise": "How much to change the photo. ~0.4 keeps it close; 0.55-0.65 allows outfit/pose swaps; above 0.7 face and body start drifting.",
         "face_weight": "How strictly faces must match the input photos. Lower drifts; above 0.85 can look pasted-on.",
         "uploads": "Front-facing, well-lit photos lock best. Square-ish crops preferred."}},
    {"id": "10", "file": "10_txt2img_facelock.json", "title": "10 \u00b7 Face-lock create",
     "desc": "New body/outfit, her face locked", "uploads": ["photo.png"],
     "params_help": {
         "prompt": "Describe the full image — subject, outfit, setting. Her face comes from your photo.",
         "seed": "Same seed + same settings = same image. Dice = fresh random result.",
         "steps": "More steps = finer detail but slower. 25-35 is the sweet spot; video uses fewer, larger steps.",
         "face_weight": "How strictly faces must match the input photos. Lower drifts; above 0.85 can look pasted-on.",
         "uploads": "Front-facing, well-lit photos lock best. Square-ish crops preferred."}},
    {"id": "11", "file": "11_faceswap.json", "title": "11 \u00b7 Face swap",
     "desc": "Her real face onto any generated body", "uploads": ["gen_body.png", "photo.png"],
     "params_help": {
         "uploads": "Front-facing, well-lit photos lock best. Square-ish crops preferred."}},
    {"id": "12", "file": "12_inpaint_undress.json", "title": "12 \u00b7 Undress inpaint",
     "desc": "Repaint clothes only, face untouched", "uploads": ["photo.png"],
     "params_help": {
         "prompt": "Describe the skin/body to paint into the masked area.",
         "seed": "Same seed + same settings = same image. Dice = fresh random result.",
         "steps": "More steps = finer detail but slower. 25-35 is the sweet spot; video uses fewer, larger steps.",
         "uploads": "Front-facing, well-lit photos lock best. Square-ish crops preferred."}},
]

WORKFLOWS_DIR = r"D:\Personal\ImGen\workflows"
TEMPLATES = {}

def load_template(wfid):
    fname = next(w["file"] for w in WORKFLOWS if w["id"] == wfid)
    if fname not in TEMPLATES:
        with open(WORKFLOWS_DIR + "\\" + fname) as f:
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
           "steps": ("99", "steps", int)},
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
        wf[node]["inputs"][key] = cast(params[name])
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
        wf["52"]["inputs"]["batch_size"] = min(int(wf["52"]["inputs"]["batch_size"]), 16)
    if wfid == "12":
        try:
            src_name = "photo.png"
            try:
                node90 = wf.get("90", {}).get("inputs", {})
                if isinstance(node90, dict) and node90.get("image"):
                    src_name = os.path.basename(str(node90["image"]))
            except (TypeError, AttributeError):
                pass
            dims = read_image_dims(os.path.join(INPUT_DIR, src_name))
            if dims is not None:
                w, h = dims
                top = 0.30 * h
                band = 0.05 * h
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
                _write_gray_png(os.path.join(INPUT_DIR, "auto_mask.png"), w, h, row_vals)
                try:
                    if "92" in wf and isinstance(wf["92"].get("inputs"), dict):
                        wf["92"]["inputs"]["image"] = "auto_mask.png"
                except (TypeError, AttributeError):
                    pass
        except Exception:
            pass
    if "seed" in params and params["seed"] != "":
        for node_id in ("12", "40", "55"):
            if node_id in wf and "seed" in wf[node_id]["inputs"]:
                wf[node_id]["inputs"]["seed"] = max(0, min(int(params["seed"]), 2**31 - 1))
            if node_id in wf and "noise_seed" in wf[node_id]["inputs"]:
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
        if self.path == "/api/inputs":
            info = {}
            for name in sorted(ALLOWED_UPLOADS):
                fpath = os.path.join(INPUT_DIR, name)
                try:
                    st = os.stat(fpath)
                    info[name] = {"exists": True, "mtime": int(st.st_mtime)}
                except OSError:
                    info[name] = {"exists": False}
            return self._json({"inputs": info})
        if self.path.startswith("/inputs/"):
            raw = self.path[len("/inputs/"):].split("?")[0].split("/")[0]
            base = os.path.basename(urllib.parse.unquote(raw))
            if base not in ALLOWED_UPLOADS:
                return self._json({"error": "not found"}, 404)
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
            elif base.lower().endswith(".webp"):
                ctype = "image/webp"
            elif base.lower().endswith(".gif"):
                ctype = "image/gif"
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
        if self.path.startswith("/api/status/"):
            pid = self.path[len("/api/status/"):].split("?")[0].split("/")[0]
            try:
                with urllib.request.urlopen(COMFY + "/history/" + pid, timeout=30) as r:
                    try:
                        hist = json.loads(r.read())
                    except (ValueError, UnicodeDecodeError):
                        return self._json({"error": "ComfyUI returned invalid response."}, 502)
            except urllib.error.URLError:
                return self._json({"error": "ComfyUI not running. Start it with start_server.bat, then retry."}, 502)
            except OSError:
                return self._json({"error": "ComfyUI not running. Start it with start_server.bat, then retry."}, 502)
            if pid not in hist:
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
                except (urllib.error.URLError, OSError, ValueError, UnicodeDecodeError):
                    pass
                if queue_ok and not running and queue_pos is None:
                    return self._json({"completed": False, "outputs": [], "failed": True,
                                       "error": "This job is no longer in ComfyUI's queue (it may have restarted or been interrupted). Press Generate to retry."})
                return self._json({"completed": False, "outputs": [], "failed": False,
                                   "error": "", "running": running, "queue_pos": queue_pos})
            entry = hist[pid]
            outputs = entry.get("outputs", {}) or {}
            filenames = []
            for node_out in outputs.values():
                for key in ("images", "gifs"):
                    for item in node_out.get(key, []) or []:
                        fn = item.get("filename")
                        if fn:
                            filenames.append(fn)
            status = entry.get("status", {}) or {}
            status_str = status.get("status_str", "")
            completed_flag = status.get("completed", False)
            messages = status.get("messages", [])
            if status_str == "error":
                err_parts = []
                for m in messages:
                    s = str(m)
                    if "exception" in s.lower() or "error" in s.lower():
                        err_parts.append(s)
                error = "; ".join(err_parts) if err_parts else str(messages)
                return self._json({"completed": False, "outputs": filenames, "failed": True, "error": error})
            completed = bool(completed_flag) or status_str == "success" or bool(filenames)
            return self._json({"completed": completed, "outputs": filenames, "failed": False, "error": ""})
        if self.path == "/api/gallery":
            items = load_gallery()
            return self._json({"items": list(reversed(items))})
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path.startswith("/api/upload"):
            qs = urllib.parse.urlparse(self.path).query
            name = urllib.parse.parse_qs(qs).get("name", [""])[0]
            if name not in ALLOWED_UPLOADS:
                return self._json({"error": "bad name"}, 400)
            try:
                length = int(self.headers.get("Content-Length", 0))
            except (TypeError, ValueError):
                return self._json({"error": "bad content length"}, 400)
            if length > MAX_UPLOAD:
                return self._json({"error": "too large"}, 413)
            body = self.rfile.read(length) if length else b""
            if len(body) > MAX_UPLOAD:
                return self._json({"error": "too large"}, 413)
            with open(os.path.join(INPUT_DIR, name), "wb") as f:
                f.write(body)
            return self._json({"ok": True, "name": name})
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
        return self._json({"error": "not found"}, 404)

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
