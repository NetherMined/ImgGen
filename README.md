# ImGen

Local image/video generation studio built on top of ComfyUI (Windows, RTX 4060 8GB).
Aimed at personal, photo-faithful generation workflows.

> ⚠️ **18+ / NSFW project.** The workflows in this repo generate adult imagery.
> Use only with images of yourself or consenting adults.

## Layout

| Path | What it is |
|---|---|
| `studio/` | **ImGen Studio** — local web UI (port `8189`) that drives ComfyUI (`8188`): workflow cards, prompt/seed/slider controls, photo uploads, live progress, gallery of past runs |
| `workflows/` | ComfyUI workflow JSONs (tested end-to-end) — see [`workflows/README.md`](workflows/README.md) for per-workflow parameter notes |
| `docs/` | Design spec + implementation plan for the studio |
| `ui-mockup.html` | Static mockup of the studio UI |

The ComfyUI portable install itself is **not** in this repo — the models are ~48 GB and
its input/output folders contain personal media. Both are intentionally gitignored.

## Requirements

- Windows + NVIDIA GPU (developed on an RTX 4060 8GB)
- ComfyUI portable with custom nodes: ReActor, IPAdapter Plus, ControlNet (Union),
  LTX-Video, AnimateDiff — plus the model inventory listed in `workflows/README.md`
- System Python 3.11 for the studio backend

## Quick start

1. Start ComfyUI: `ComfyUI_windows_portable\run_nvidia_gpu.bat` → `http://127.0.0.1:8188`
2. Start Studio: `studio\start_studio.bat` → `http://127.0.0.1:8189`
3. Pick a workflow card, tweak prompt/seed, upload photos where asked, **Generate**.

## Workflows

`01` outfit change · `02` pose change · `03` photo→video (LTX-Video) · `04` AnimateDiff clip ·
`05` couple still (dual face lock) · `06` couple still→video · `07` prompt→image ·
`08` skeleton extract · `09` pose preset · `10` txt2img face-lock · `11` ReActor face swap ·
`12` inpaint undress · `13` inpaint (proper) · `14` cleanup pass — details in `workflows/README.md`.

## Notes

- First run of a workflow is slower (models load into VRAM); the Studio frees ComfyUI's cached models before every run so the new workflow gets the full VRAM budget.
- 8GB VRAM: keep LTX-Video at ≤97 frames and AnimateDiff at ≤16 frames.
- The ReActor NSFW-filter patch in `custom_nodes\ComfyUI-ReActor\nodes.py` must be
  re-applied after any ReActor update.
