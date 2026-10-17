# Local NSFW Generation — ComfyUI Setup (RTX 4060 8GB)

## Start the server
Run `start_server.bat` inside `ComfyUI_windows_portable/`
(or `run_nvidia_gpu.bat` for defaults).
Then open `http://127.0.0.1:8188`.

## Use the workflows
Put your photo in `ComfyUI_windows_portable/ComfyUI/input/` named
`photo.png` (or click the LoadImage node and pick any file).

Drag a workflow JSON from this folder into the ComfyUI browser window,
then press **Queue**. Outputs land in `ComfyUI_windows_portable/ComfyUI/output/`.
All the user-facing workflows were tested end-to-end on this machine
(helper 08 and the experiments 13/14 are noted below).

### 01_photo_to_nsfw_image.json — outfit change, same pose/face ✓ tested
img2img (denoise 0.55) + IPAdapter PLUS FACE lock.
- Edit node 6 for the outfit/scene you want.
- `denoise`: lower (0.4) = closer to the photo, higher (0.7) = more change.
- IPAdapter weight: lower (0.5) = likeness drifts, higher (0.85) = strict face.

### 02_pose_change.json — new pose via pose reference ✓ tested
Same as 01 plus ControlNet OpenPose (Union model). Put a pose reference
image in `ComfyUI/input/` named `pose.png`. ControlNet strength 0.85,
denoise 0.6.

### 03_photo_to_video_ltxv.json — photo to NSFW video (recommended) ✓ tested
LTX-Video 2B distilled: 97 frames at 768x512, ~4 sec at 24fps.
Takes ~3-6 min on the 4060. Edit node 34 for the motion you want.

### 04_video_animatediff.json — short prompt-driven motion clip ✓ tested
AnimateDiff SDXL motion module, 16 frames. Not photo-faithful —
use 03 when the face must match the photo.

### 05_couple_still_dualface.json — two photos → one couple still ✓ tested
txt2img with dual IPAdapter PLUS FACE lock (0.75 each): put the
woman's photo in `ComfyUI/input/` named `girl.png` and the man's as
`guy.png`. Edit node 5 for the scene/position you want
(e.g. "kissing", "cuddling"). Output: `couple_still_*.png`.
Note: LTX-Video can't invent a pose from two photos — the pose must
be created here first, then animated in 06.

### 06_couple_still_to_video_ltxv.json — couple still → kissing video ✓ tested
Copy your favourite still to `ComfyUI/input/` named `couple.png`,
then queue. 97 frames at 768x512, ~4 sec at 24fps. Edit node 34
for the motion (kissing, caressing, etc.).

### 07_prompt_to_image.json — pure prompt image (no photo)
Text-to-image on RealVisXL: no photo is used and faces won't match
anyone. Edit node 62 for the full image description (subject, pose,
clothes, setting), node 64 for seed/steps. Output: `prompt_image_*.png`.

### 08_extract_skeleton.json — photo to pose-skeleton PNG (helper)
Runs OpenPose (node 71) on a photo and saves the rendered skeleton with
prefix `skel_standing`. Put the source photo in `ComfyUI/input/` named
`pose_src_standing.png` (or edit node 70), queue, then copy the result from
`ComfyUI/output/` into `ComfyUI/input/poses/` to use it as a pose preset in
the Studio (workflow 09). Not exposed as a Studio card.

### 09_pose_preset.json — photo + preset pose, face locked
Same img2img + IPAdapter PLUS FACE lock as 01 (denoise 0.6), but the
pose comes from a preset skeleton picked from the Studio dropdown
(node 20 `LoadImage`, default `poses/skel_standing.png`). Put your
photo in `ComfyUI/input/` named `photo.png`, edit node 6 for the
outfit/scene. Output: `preset_pose_*.png`.
Preset skeletons live in `ComfyUI\input\poses` — 6 single
(`skel_standing`, `skel_sitting`, `skel_kneeling`, `skel_lying_side`,
`skel_lying_back`, `skel_bending`) + 3 couple (`skel_couple_cuddle`,
`skel_couple_kiss`, `skel_couple_lying`).

### 10_txt2img_facelock.json — new body w/ locked face
Pure txt2img on RealVisXL + IPAdapter PLUS FACE lock (0.85, node 68):
your photo supplies the face (node 66 `LoadImage`, `photo.png`, squared
to 512 via node 67), the prompt (node 62) describes everything else.
Edit node 62 for subject/outfit/setting, node 69 for seed/steps.
Output: `facelock_txt2img_*.png` — Vogel-style bodies from 07, but with
her face. Feed a favourite into 11 for an exact-face swap.

### 11_faceswap.json — exact-face swap via ReActor
ReActor `ReActorFaceSwap` (node 82, `inswapper_128.onnx`): pastes her
real face from `photo.png` (node 81) onto any generated body
`gen_body.png` (node 80, e.g. a 07/10 output copied to
`ComfyUI/input/`). No prompt/seed — Studio sends images only, so the
form shows uploads + Generate. Output: `faceswap_*.png`.
Requires ReActor + inswapper, both installed. NOTE: the NSFW-filter
patch in `custom_nodes\ComfyUI-ReActor\nodes.py` must be re-applied
after any ReActor update, or swaps get blocked.

### 12_inpaint_undress.json — masked repaint, face untouched
Inpaint on RealVisXL: only the masked torso region is repainted (node 97
`VAEEncodeForInpaint`, grow 48), everything else — incl. the face —
is pixel-identical. Edit node 95 for the skin/body to paint into the
mask, node 99 for seed/steps. Studio auto-generates a feathered mask
(black above ~5% height, solid white below ~20%, soft ramp between —
starts just under the collarbone) sized to your source photo and sends
it as `auto_mask.png` (node 92); node 93 rescales it and node 89
converts to mask, so no manual mask file is needed. Output:
`undress_*.png`.

### 13_inpaint_proper.json — inpaint with the official SDXL inpaint model
Alternative to 12 built on `sd_xl_inpaint_0.1_fp16.safetensors` +
`InpaintModelConditioning` (node 97). Studio loads your uploaded `photo.png`
(node 90) and the same Studio-generated `auto_mask.png` as 12; edit node 95
for content, node 99 for seed/steps. Output `inpaint_pro_*.png`. NOTE: the
official inpaint model is content-filtered (no nudity) — for undress use 12
on uncensored RealVisXL; 13 is kept for SFW repaints and strap/edge cleanup
experiments. Heavy on 8GB VRAM (holds the inpaint UNET *and* a RealVis
checkpoint at once) — expect several minutes per run.

### 14_cleanup_pass.json — second pass for residual straps/seams
Cleans up a previous result: the Studio's "Use as cleanup" button (on a
result or gallery item) stages that image as `cleanup.png` (node 90) and
switches to this card — it also generates the feathered `auto_mask.png`
sized to the image. Prompts live in nodes 95/96, seed/steps/denoise in
node 99 (denoise 0.4-0.6 for residual cleanup). Output: `cleanup_*.png`.
Uses the same content-filtered SDXL inpaint UNET as 13 — check the result
on your images; a censored inpaint can only fix what it allows.

## Prompt tips
- Keep identity words in the prompt ("same woman, same face").
- RealVisXL understands: `lingerie, nightdress, silk robe, bedroom,
  soft lighting, detailed skin texture, photorealistic, 8k uhd`.
- Negative: `cartoon, anime, painting, blurry, deformed, extra limbs,
  watermark, text`.

## Notes
- First run of a workflow is slower (model loads into VRAM, ~30-60s).
- SDXL image workflows (01/02/05/09/10/12) decode with `VAEDecodeTiled`
  (512px tiles): a full-frame decode under VRAM pressure spills into
  shared memory and can take many minutes, tiled stays fast on 8GB.
- 8GB VRAM: don't raise LTXV length above 97 or AnimateDiff batch
  above 16 without expecting offload slowdowns.
- Optional: an NSFW LoRA in `models/loras/` + LoraLoaderModelOnly
  (strength 0.6-0.8) for stronger undress results.
- Backup copy of all models (hash-verified): `C:\ComfyUI_models\`.

## ⚠️ D: drive health warning
During setup the D: drive (WD Blue SN580 2TB) intermittently returned
I/O errors (`IN_PAGE_ERROR` / "a device which does not exist") and one
model file was found silently corrupted (wrong SHA256 at correct size).
SMART reports healthy — this fits the known Windows 11 24H2 + WD SN580
HMB incompatibility, or early flash failure. Recommended:
1. Back up anything important on D: now.
2. Install WD Dashboard and update the SN580 firmware.
3. Install all Windows updates, then reboot.
4. Run `chkdsk D: /f`.
If generation ever returns blocky noise again, re-hash the models:
any mismatch means re-copy that file from `C:\ComfyUI_models\`.

## Model inventory (all SHA256-verified on 2026-10-16)
| File | Folder | Size |
|---|---|---|
| RealVisXL_V5.0_fp16.safetensors | checkpoints | 6.5GB |
| ltxv-2b-0.9.8-distilled.safetensors | checkpoints | 5.9GB |
| ltxv-2b-0.9.8-distilled-fp8.safetensors | diffusion_models | 4.2GB |
| t5xxl_fp16.safetensors | text_encoders | 9.1GB |
| diffusion_pytorch_model.safetensors (LTX VAE) | vae | 1.6GB |
| sdxl_vae.safetensors | vae | 319MB |
| diffusion_pytorch_model.safetensors (ControlNet Union) | controlnet | 2.3GB |
| ip-adapter-plus-face_sdxl_vit-h.safetensors | ipadapter | 808MB |
| CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors | clip_vision | 2.4GB |
| mm_sdxl_v10_beta.ckpt | animatediff_models | 906MB |

## ImGen Studio UI
Double-click `studio\start_studio.bat` (starts backend on :8189 if ComfyUI is already on :8188), open `http://127.0.0.1:8189/`. Pick a workflow card, tweak prompt/seed/sliders, upload photos where asked, Generate. Past outputs with their settings sit in the gallery strip. Tested JSONs in this folder are never modified — they are the fallback.
