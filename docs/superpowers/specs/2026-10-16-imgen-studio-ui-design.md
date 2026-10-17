# ImGen Studio UI — Design Spec (2026-10-16)

## Goal
A user-friendly local web page that exposes the 6 tested ComfyUI workflows
(01–06) as selectable cards with tweakable key settings, photo uploads, live
progress, and a results gallery. Single local user, RTX 4060 8GB machine.

## Non-goals
- No user accounts, no database, no internet access from the app.
- No new npm/pip dependencies (Python stdlib + plain HTML/JS only).
- Tested workflow JSONs in `workflows/` stay untouched as fallback.

## Architecture
Two pieces, both local:
1. **Static page** (`studio.html`): 3-column layout per approved mockup
   (`ui-mockup.html`). Left = workflow cards, middle = settings form,
   right = progress/result, bottom = gallery. Plain JS `fetch()` only.
2. **Backend** (`server.py`, stdlib `http.server` only): endpoints
   - `GET /api/workflows` — list of 6 workflows + their parameter schema.
   - `POST /api/generate` — accept {workflow, params, inputRefs}, fill the
     in-memory template, POST to ComfyUI `:8188/prompt`, return prompt_id.
   - `GET /api/status/<prompt_id>` — proxy ComfyUI history/progress.
   - `POST /api/upload` — save photo to ComfyUI `input/` (fixed names:
     photo.png, girl.png, guy.png, couple.png, pose.png).
   - `GET /outputs/<file>` — serve finished files from ComfyUI `output/`.

## Per-workflow parameters (key settings only)
- Common: prompt text, seed (+dice randomize), steps.
- 01/02: denoise slider, face-lock weight slider.
- 02: pose upload slot. 05: girl+guy upload slots, face-lock weight.
- 03/06: motion prompt, length fixed at 97 (8GB VRAM ceiling).
- 04: batch size capped at 16 (VRAM ceiling).

## Data flow
Generate → fill template → ComfyUI queue → poll every 2s → progress bar
(step counts from ComfyUI progress messages) → on completion show result,
append gallery entry stamped with {workflow, params, seed, output file}.
Gallery click reloads those settings into the form.

## Error handling
- ComfyUI unreachable: banner with exact start command, retry button.
- Missing required photo: highlight the slot, block queueing.
- Job failure: show ComfyUI error text, keep settings filled for retry.

## Testing
Queue each of the 6 workflows through the UI, byte-compare outputs against
direct-API runs. Then exercise: missing photo, server down, double-submit
while a job runs (second click disabled until completion).

## Files
- `D:\Personal\ImGen\studio\server.py` (new)
- `D:\Personal\ImGen\studio\studio.html` (new, evolved from `ui-mockup.html`)
- `D:\Personal\ImGen\workflows\README.md` (append usage section)
- No changes to ComfyUI core, custom nodes, models, or tested JSONs.
