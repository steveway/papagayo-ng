# Phonemation Backend Server

Self-contained backend for the Godot (and other) Phonemation frontends.

## Running from source

Install `requirements.txt` plus exactly one of `onnxruntime`, `onnxruntime-gpu`, `onnxruntime-directml`, or `onnxruntime-openvino` in the environment.

```powershell
# CLI mode (same as before)
$env:PHONEMATION_PHONEME_MODEL = "C:\Models\phoneme_onnx"
$env:PHONEMATION_EMOTION_MODEL = "C:\Models\emotion_onnx"
python -m phonemation_backend --autoload --port 8007

# Tkinter UI mode
python -m phonemation_backend --ui
```

Or use the provided `../start_backend.ps1` script.

Print platform, packaged runtime, ONNX Runtime providers, CPU, and memory information without starting the server:

```powershell
python -m phonemation_backend --environment
```

The CLI logs the same summary during normal startup. The Tkinter UI displays it in the Status panel, and `GET /status` exposes the complete data under `environment`, including active model providers after models are loaded.

## Packaging with Nuitka

Build each ONNX Runtime acceleration target in an isolated environment:

```powershell
.\backend_server\build_nuitka.ps1 -Runtime cpu -OneFile -UIOnly
.\backend_server\build_nuitka.ps1 -Runtime cuda -OneFile -UIOnly
.\backend_server\build_nuitka.ps1 -Runtime directml -OneFile -UIOnly
.\backend_server\build_nuitka.ps1 -Runtime openvino -OneFile -UIOnly
```

Use `-Runtime all` to build every variant. Omitting `-UIOnly` also produces `phonemation_backend_cli.exe`. Outputs are written below `artifacts/backend/<runtime>`.

The complete Godot frontend and backend MSI workflow is documented in `../packaging/README.md`.

## API highlights

- `GET /health` — `{status, version}` for compatibility checks.
- `POST /shutdown` — stops recognition **and** terminates the server process (remote shutdown from the frontend).
- `POST /models/download` / `POST /models/update` — start a **background** download; returns immediately with `{status: "started" | "in_progress" | "already_downloaded"}`.
- `GET /models/download/progress?model_id=...` — poll download progress: `{state, downloaded_bytes, total_bytes, percent, error, path}`.
- `POST /models/delete` — remove a downloaded model from disk to free space: `{status: "deleted" | "not_found"}`.
- `GET /emotions` — emotion labels for the currently loaded emotion model: `{emotions: [...], model}`.

Note: the backend deliberately has **no hotkey/input endpoints**. Hotkeys are captured locally by the frontend (BackgroundInputCapture GDExtension), because the backend may run on a different machine than the user's keyboard. The backend only does AI/audio work.

## Environment variables

- `HF_TOKEN` — override the bundled read-only HuggingFace token.
- `PHONEMIZER_ESPEAK_LIBRARY` — path to `libespeak-ng` (defaults to the standard Windows install path if present).
- `PHONEMATION_MODEL_CACHE` — override the model cache directory.

## Requirements

See `requirements.txt` (now version-pinned; requires `pydantic>=2`). Key dependencies:
- onnxruntime
- sounddevice / soundfile
- fastapi / uvicorn
- numpy / soxr
- huggingface_hub
