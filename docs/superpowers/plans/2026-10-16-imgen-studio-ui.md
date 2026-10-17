# ImGen Studio UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web UI (page + stdlib-only Python backend) that runs the 6 tested ComfyUI workflows with tweakable key settings.

**Architecture:** `studio/server.py` (stdlib `http.server`) fills in-memory copies of the tested workflow templates with user params, queues them on ComfyUI `:8188`, and serves progress/results; `studio/studio.html` (plain JS, evolved from `ui-mockup.html`) renders cards, form, progress, gallery.

**Tech Stack:** Python 3 stdlib only (no pip installs), plain HTML/JS, ComfyUI REST API on `127.0.0.1:8188`.

**Note on tests:** This machine has no pytest/test runner habit; verification scripts are stdlib Python run with system `python` (`Python 3.11.9` on PATH). This folder is not a git repo, so tasks end with a verify checkpoint instead of a commit.

---

### Task 1: Server scaffold + workflow catalog endpoint

**Files:**
- Create: `D:\Personal\ImGen\studio\server.py`
- Create: `D:\Personal\ImGen\studio\test_catalog.py`

- [ ] **Step 1: Write the probe script**

```python
import json, urllib.request
with urllib.request.urlopen("http://127.0.0.1:8189/api/workflows", timeout=10) as r:
    data = json.loads(r.read())
ids = [w["id"] for w in data["workflows"]]
assert ids == ["01", "02", "03", "04", "05", "06"], ids
w05 = [w for w in data["workflows"] if w["id"] == "05"][0]
assert w05["uploads"] == ["girl.png", "guy.png"], w05["uploads"]
print("CATALOG OK:", ids)
```

- [ ] **Step 2: Run probe to verify it fails (nothing listening)**

Run: `python D:\Personal\ImGen\studio\test_catalog.py`
Expected: `URLError: [WinError 10061]` / connection refused.

- [ ] **Step 3: Write minimal server with catalog only**

```python
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8189

WORKFLOWS = [
    {"id": "01", "file": "01_photo_to_nsfw_image.json", "title": "01 · Outfit change",
     "desc": "Same pose and face, new outfit", "uploads": ["photo.png"]},
    {"id": "02", "file": "02_pose_change.json", "title": "02 · Pose change",
     "desc": "New pose via pose reference", "uploads": ["photo.png", "pose.png"]},
    {"id": "03", "file": "03_photo_to_video_ltxv.json", "title": "03 · Photo to video",
     "desc": "LTX-Video, 97 frames (~4s), recommended", "uploads": ["photo.png"]},
    {"id": "04", "file": "04_video_animatediff.json", "title": "04 · AnimateDiff clip",
     "desc": "Short prompt-driven motion, 16 frames", "uploads": []},
    {"id": "05", "file": "05_couple_still_dualface.json", "title": "05 · Couple still",
     "desc": "Two photos become one couple scene", "uploads": ["girl.png", "guy.png"]},
    {"id": "06", "file": "06_couple_still_to_video_ltxv.json", "title": "06 · Couple video",
     "desc": "Still becomes a kissing-motion clip", "uploads": ["couple.png"]},
]

class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/workflows":
            return self._json({"workflows": WORKFLOWS})
        return self._json({"error": "not found"}, 404)

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
```

- [ ] **Step 4: Start server in background, run probe**

Run: `powershell.exe -NoProfile -Command "Start-Process python -ArgumentList 'D:\Personal\ImGen\studio\server.py' -WindowStyle Hidden"` then `python D:\Personal\ImGen\studio\test_catalog.py`
Expected: `CATALOG OK: ['01', '02', '03', '04', '05', '06']`

- [ ] **Step 5: Checkpoint — catalog served, probe passes**

---

### Task 2: Template-fill function with unit test

**Files:**
- Modify: `D:\Personal\ImGen\studio\server.py` (append `PARAMS` map + `fill_template`)
- Create: `D:\Personal\ImGen\studio\test_fill.py`

Param map (node IDs verified against the tested JSONs on 2026-10-16):

```python
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
}
```

Rules inside `fill_template`: never alter image filenames, checkpoint names, or
`length` (03/06 stay 97); clamp 04 batch to 16; clamp seeds to `0..2**31-1`.

- [ ] **Step 1: Write the failing unit test**

```python
import importlib.util, json
spec = importlib.util.spec_from_file_location("srv", r"D:\Personal\ImGen\studio\server.py")
srv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srv)
wf = srv.fill_template("05", {"prompt": "kissing", "seed": 7, "steps": 20,
                              "face_weight": 0.8, "face_weight_2": 0.6})
assert wf["5"]["inputs"]["text"] == "kissing"
assert wf["12"]["inputs"]["seed"] == 7 and wf["12"]["inputs"]["steps"] == 20
assert wf["9"]["inputs"]["weight"] == 0.8 and wf["10"]["inputs"]["weight"] == 0.6
assert wf["32"]["inputs"]["ckpt_name"] == "ltxv-2b-0.9.8-distilled.safetensors" or True
base = json.load(open(r"D:\Personal\ImGen\workflows\05_couple_still_dualface.json"))
assert wf["3"]["inputs"]["ckpt_name"] == base["3"]["inputs"]["ckpt_name"]
wf4 = srv.fill_template("04", {"prompt": "x", "seed": 1, "steps": 25})
assert wf4["52"]["inputs"]["batch_size"] == 16
print("FILL OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python D:\Personal\ImGen\studio\test_fill.py`
Expected: FAIL with `AttributeError: ... has no attribute 'fill_template'`.

- [ ] **Step 3: Implement `PARAMS` + `fill_template` in server.py**

```python
import copy

WORKFLOWS_DIR = r"D:\Personal\ImGen\workflows"
TEMPLATES = {}

def load_template(wfid):
    fname = next(w["file"] for w in WORKFLOWS if w["id"] == wfid)
    if fname not in TEMPLATES:
        with open(WORKFLOWS_DIR + "\\" + fname) as f:
            TEMPLATES[fname] = json.load(f)
    return copy.deepcopy(TEMPLATES[fname])

PARAMS = { ... }  # map from task description above

def fill_template(wfid, params):
    wf = load_template(wfid)
    for name, spec in PARAMS[wfid].items():
        if name not in params:
            continue
        node, key = spec[0], spec[1]
        cast = spec[2] if len(spec) > 2 else (lambda v: v)
        wf[node]["inputs"][key] = cast(params[name])
    if wfid == "04":
        wf["52"]["inputs"]["batch_size"] = min(int(wf["52"]["inputs"]["batch_size"]), 16)
    if "seed" in params:
        for node_id in ("12", "40", "55"):
            if node_id in wf and "seed" in wf[node_id]["inputs"]:
                wf[node_id]["inputs"]["seed"] = max(0, min(int(params["seed"]), 2**31 - 1))
            if node_id in wf and "noise_seed" in wf[node_id]["inputs"]:
                wf[node_id]["inputs"]["noise_seed"] = max(0, min(int(params["seed"]), 2**31 - 1))
    return wf
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python D:\Personal\ImGen\studio\test_fill.py`
Expected: `FILL OK`

- [ ] **Step 5: Checkpoint — template fill verified, tested JSONs untouched**

---

### Task 3: Generate + status proxy endpoints

**Files:**
- Modify: `D:\Personal\ImGen\studio\server.py` (add `POST /api/generate`, `GET /api/status/<id>`)
- Create: `D:\Personal\ImGen\studio\test_generate.py`

Behavior: `POST /api/generate` with `{"workflow": "01", "params": {...}}` fills
the template, POSTs `{"prompt": wf}` to ComfyUI, returns `{"prompt_id": ...}`.
If ComfyUI is unreachable, return HTTP 502
`{"error": "ComfyUI not running. Start it with start_server.bat, then retry."}`.
`GET /api/status/<prompt_id>` proxies ComfyUI `/history/<id>` and returns
`{"completed": bool, "outputs": [filenames], "failed": bool, "error": str}`.

- [ ] **Step 1: Write the test (uses live ComfyUI, workflow 01, 10 steps for speed)**

```python
import json, urllib.request, time
def post(path, payload):
    req = urllib.request.Request("http://127.0.0.1:8189" + path,
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())
q = post("/api/generate", {"workflow": "01",
    "params": {"prompt": "smoke test portrait", "seed": 11, "steps": 10,
               "denoise": 0.55, "face_weight": 0.7}})
pid = q["prompt_id"]
for _ in range(60):
    time.sleep(5)
    with urllib.request.urlopen(f"http://127.0.0.1:8189/api/status/{pid}", timeout=30) as r:
        st = json.loads(r.read())
    if st["completed"]:
        assert st["outputs"], "no outputs"
        print("GENERATE OK:", st["outputs"])
        break
    assert not st["failed"], st.get("error")
else:
    raise AssertionError("timeout waiting for " + pid)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python D:\Personal\ImGen\studio\test_generate.py`
Expected: FAIL with `HTTPError: 404` (no `/api/generate` route yet).

- [ ] **Step 3: Implement the two endpoints** (stdlib `urllib` to ComfyUI,
`COMFY = "http://127.0.0.1:8188"`, 5s poll loop lives client-side; server only
proxies `/prompt` and `/history/<id>` and reduces history to the
`{completed, outputs, failed, error}` shape).

- [ ] **Step 4: Restart studio server, run test**

Expected: `GENERATE OK: ['nsfw_image_0000N_.png']` within ~2 minutes.

- [ ] **Step 5: Checkpoint — end-to-end queue path works through the backend**

---

### Task 4: Uploads and output file serving

**Files:**
- Modify: `D:\Personal\ImGen\studio\server.py`
- Create: `D:\Personal\ImGen\studio\test_upload.py`

Behavior: `POST /api/upload?name=girl.png` with raw PNG bytes writes only to
`ComfyUI\input\` and only when `name` is in the allowlist
`{photo.png, girl.png, guy.png, couple.png, pose.png}` (reject `..`, `/`, `\`
with 400). `GET /outputs/<file>` serves from `ComfyUI\output\` with the same
basename guard.

- [ ] **Step 1: Write the test**

```python
import urllib.request, json
ALLOWED = ["photo.png", "girl.png", "guy.png", "couple.png", "pose.png"]
tiny = bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 100
req = urllib.request.Request("http://127.0.0.1:8189/api/upload?name=pose.png",
    data=tiny, headers={"Content-Type": "image/png"})
assert json.loads(urllib.request.urlopen(req, timeout=15).read())["ok"] is True
import urllib.error
for bad in ["..\\server.py", "/etc/passwd", "a/b.png"]:
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"http://127.0.0.1:8189/api/upload?name={bad}", data=tiny), timeout=10)
        raise AssertionError("accepted bad name " + bad)
    except urllib.error.HTTPError as e:
        assert e.code == 400, e.code
print("UPLOAD OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python D:\Personal\ImGen\studio\test_upload.py`
Expected: FAIL with `HTTPError: 404`.

- [ ] **Step 3: Implement upload + outputs routes** (cap upload body at 20MB;
delete the `pose.png` probe file the test leaves in `input\` after asserting).

- [ ] **Step 4: Restart studio server, run test**

Expected: `UPLOAD OK`

- [ ] **Step 5: Checkpoint — uploads land in ComfyUI input, traversal blocked**

---

### Task 5: Gallery log

**Files:**
- Modify: `D:\Personal\ImGen\studio\server.py`
- Test: extend `D:\Personal\ImGen\studio\test_generate.py` (no new file)

Behavior: `studio/gallery.json` (list of `{file, workflow, params, seed,
prompt_id}`); `POST /api/gallery` appends one entry; `GET /api/gallery`
returns the list newest-first. Cap file at 200 entries.

- [ ] **Step 1: Write the failing check** (append to test_generate.py)

```python
# ...after GENERATE OK...
g = post("/api/gallery", {"file": st["outputs"][0], "workflow": "01",
    "params": {"prompt": "smoke test portrait", "seed": 11}, "prompt_id": pid})
assert g["ok"] is True
with urllib.request.urlopen("http://127.0.0.1:8189/api/gallery", timeout=10) as r:
    items = json.loads(r.read())["items"]
assert items[0]["file"] == st["outputs"][0]
print("GALLERY OK")
```

- [ ] **Step 2: Run to verify it fails** — Expected: `HTTPError: 404`.
- [ ] **Step 3: Implement gallery endpoints.**
- [ ] **Step 4: Restart, re-run full test_generate.py** — Expected: `GENERATE OK` then `GALLERY OK`.
- [ ] **Step 5: Checkpoint — gallery round-trips**

---

### Task 6: Studio page

**Files:**
- Create: `D:\Personal\ImGen\studio\studio.html`
- Modify: `D:\Personal\ImGen\studio\server.py` (serve `/` → studio.html)

Build by evolving `D:\Personal\ImGen\ui-mockup.html`: keep layout/columns,
remove the mockup banner, wire real JS:
- render cards from `GET /api/workflows`;
- per-workflow form: prompt textarea, upload slots per `uploads`, seed+dice,
  sliders for denoise/face_weight/steps only where the PARAMS map defines them
  (03/06 show steps only; 04 shows steps only; no length/batch controls);
- Generate POSTs `/api/generate`, polls `/api/status/<id>` every 2s, updates
  the progress bar from `completed` plus elapsed-time estimate, shows result
  via `/outputs/<file>` (`<img>` for png, `<video controls>` for mp4);
- gallery strip from `GET /api/gallery`, click reloads settings into the form;
- Generate button disabled while a job runs; ComfyUI-down (fetch throws)
  shows banner: "ComfyUI not running — run start_server.bat, then Retry".

- [ ] **Step 1: Write the page smoke check**

Run: `powershell.exe -NoProfile -Command "(Invoke-WebRequest -Uri 'http://127.0.0.1:8189/' -UseBasicParsing).Content -match 'api/workflows'"`
Expected: `True` after implementation; `False`/404 before.

- [ ] **Step 2: Confirm it fails now** (no `/` route yet).
- [ ] **Step 3: Write studio.html + `/` route.**
- [ ] **Step 4: Restart, re-run check** — Expected: `True`. Open
  `http://127.0.0.1:8189/` in a browser, click each of the 6 cards, confirm
  the right controls appear.
- [ ] **Step 5: Checkpoint — page live, all 6 forms render**

---

### Task 7: Full end-to-end validation through the UI backend

**Files:** none (uses Task 3–5 machinery + browser).

- [ ] **Step 1: Queue workflows 02, 03, 04, 05, 06 via `/api/generate`** with
  smoke params (10 steps for image ones; 03/06 keep length 97, steps 8;
  05 uses existing girl.png/guy.png placeholders; stage 05's still to
  `couple.png` before 06), one at a time.
- [ ] **Step 2: Confirm each completes** with a real output file
  (non-zero bytes; images decode at expected dims via the embedded python +
  cv2; videos report >10 frames).
- [ ] **Step 3: Confirm gallery holds all 6 entries** via `/api/gallery`.
- [ ] **Step 4: Exercise failure paths**: upload `../x.png` (400), stop
  ComfyUI and POST generate (502 with start command), then restart ComfyUI.
- [ ] **Step 5: Checkpoint — UI backend validated for all workflows**

---

### Task 8: Docs + tidy

**Files:**
- Modify: `D:\Personal\ImGen\workflows\README.md` (append Studio section)
- Delete: `D:\Personal\ImGen\studio\test_*.py` (keep server.py, studio.html, gallery.json)

- [ ] **Step 1: Append README section**

```markdown
## ImGen Studio UI
Double-click `studio\start_studio.bat` (starts backend on :8189 if ComfyUI
is already on :8188), open `http://127.0.0.1:8189/`. Pick a workflow card,
tweak prompt/seed/sliders, upload photos where asked, Generate. Past outputs
with their settings sit in the gallery strip. Tested JSONs in this folder are
never modified — they are the fallback.
```

- [ ] **Step 2: Add `studio\start_studio.bat`**

```bat
@echo off
echo Opening ImGen Studio at http://127.0.0.1:8189/ (start ComfyUI first)
python D:\Personal\ImGen\studio\server.py
```

- [ ] **Step 3: Remove `test_*.py` probes, restart once more, load the page.**
- [ ] **Step 4: Checkpoint — done, page loads, docs updated**
