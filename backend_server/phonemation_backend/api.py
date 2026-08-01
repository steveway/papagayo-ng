import asyncio
import logging
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

from .environment import get_environment_info

if TYPE_CHECKING:
    from .service import PhonemationBackend

# 0.5.0: /hotkeys endpoints removed again; hotkeys are captured by the frontend
# (BackgroundInputCapture GDExtension) since the backend may run remotely.
API_VERSION = "0.5.0"


class BackendStartRequest(BaseModel):
    phoneme_model_path: str = Field(..., description="Path to the phoneme ONNX model directory")
    emotion_model_path: Optional[str] = Field(None, description="Optional path to the emotion ONNX model directory. Omit to skip emotion inference.")
    host_api: Optional[str] = Field(None, description="Optional PortAudio host API name")
    input_device: Optional[str] = Field(None, description="Optional audio input device name")
    output_device: Optional[str] = Field(None, description="Optional audio output device name")
    enable_output: bool = Field(False, description="Whether to start audio playback output")
    vad_system: str = Field("volume", description="Audio segmentation mode: volume, energy, or silero")
    volume_level_threshold: float = Field(0.05, description="Volume threshold for speech capture")
    audio_source: str = Field("local", description="Audio source: 'local' uses system audio devices, 'remote' accepts audio from client")
    viseme_set: str = Field("preston_blair", description="Phoneme target set used for visemes. One of: cmu_39, preston_blair, fleming_dobbs, rhubarb")


class ProcessAudioRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64-encoded float32 PCM audio data")
    sample_rate: int = Field(44100, description="Sample rate of the provided audio")
    channels: int = Field(1, description="Number of audio channels (1=mono, 2=stereo)")
    chunk_id: int = Field(0, description="Client-side chunk identifier echoed back for sync pairing")


class ModelDownloadRequest(BaseModel):
    model_id: str = Field(..., description="HuggingFace model ID to download (e.g. steveway/wav2vec2-xls-r-300m-timit-phoneme_onnx)")
    force: bool = Field(False, description="Re-download even if the model already exists locally")


def _default_model_cache_path() -> Path:
    try:
        from .utilities import get_app_data_path

        return get_app_data_path() / "transformers_cache"
    except Exception:
        return Path(os.environ.get("HF_HOME", Path.cwd() / "ai_cache"))


def _model_dir_for(model_id: str, model_type: str) -> Path:
    """Return the expected local directory path for a downloaded model."""
    cache_root = Path(os.environ.get("PHONEMATION_MODEL_CACHE", _default_model_cache_path()))
    model_name = model_id.split("/")[-1]
    return cache_root / model_type / model_name


def _model_is_downloaded(model_id: str, model_type: str) -> bool:
    """Check if a model is fully downloaded locally by looking for .onnx files."""
    model_dir = _model_dir_for(model_id, model_type)
    if not model_dir.exists():
        return False
    return any(f.suffix == ".onnx" for f in model_dir.rglob("*"))


def _resolve_model_type(model_id: str) -> str:
    """Return 'phoneme' or 'emotion' for a steveway/* model id, or raise HTTPException."""
    if not model_id.startswith("steveway/"):
        raise HTTPException(status_code=400, detail="Only steveway/* models are supported")
    # Local-first: derive the type from the on-disk cache layout so model
    # management (delete, re-download) keeps working without HF connectivity.
    for model_type in ("phoneme", "emotion"):
        if _model_dir_for(model_id, model_type).exists():
            return model_type
    try:
        from .model_manager import ModelHandler

        mh = ModelHandler.get_instance()
        mh.cache_models()
        for item in mh.phoneme_collection.items:
            if item.item_id == model_id:
                return "phoneme"
        for item in mh.emotion_collection.items:
            if item.item_id == model_id:
                return "emotion"
    except HTTPException:
        raise
    except Exception as exc:
        logging.error("Failed to determine model type for %s: %s", model_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail=f"Model {model_id} not found in phoneme or emotion collections")


# Cache HF collection listings so /models does not hit the network on every call.
_HF_MODELS_CACHE_TTL = 300.0
_hf_models_cache: Dict[str, tuple] = {}  # model_type -> (timestamp, list[str])
_hf_models_cache_lock = threading.Lock()


def _list_hf_available_models(model_type: str) -> list[str]:
    """Query HuggingFace collections for available models of a given type (cached)."""
    now = time.monotonic()
    with _hf_models_cache_lock:
        cached = _hf_models_cache.get(model_type)
        if cached and now - cached[0] < _HF_MODELS_CACHE_TTL:
            return cached[1]
    try:
        from .model_manager import ModelHandler

        mh = ModelHandler.get_instance()
        mh.cache_models()
        if model_type == "phoneme":
            model_ids = [model.item_id for model in mh.phoneme_collection.items]
        else:
            model_ids = [model.item_id for model in mh.emotion_collection.items]
        with _hf_models_cache_lock:
            _hf_models_cache[model_type] = (now, model_ids)
        return model_ids
    except Exception as exc:
        logging.warning("Could not query HuggingFace for %s models: %s", model_type, exc)
        return []


def _list_cached_models(model_type: str) -> list[dict]:
    """List available models with their download status and local paths."""
    models = []
    seen_ids = set()

    available_ids = _list_hf_available_models(model_type)

    for model_id in available_ids:
        model_name = model_id.split("/")[-1].removesuffix("_onnx")
        seen_ids.add(model_id)
        downloaded = _model_is_downloaded(model_id, model_type)
        model_dir = _model_dir_for(model_id, model_type)
        models.append(
            {
                "id": model_id,
                "name": model_name,
                "path": str(model_dir),
                "downloaded": downloaded,
            }
        )

    cache_root = Path(os.environ.get("PHONEMATION_MODEL_CACHE", _default_model_cache_path()))
    model_root = cache_root / model_type
    if model_root.exists():
        for path in sorted(model_root.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_dir():
                continue
            model_id = f"steveway/{path.name}"
            if model_id in seen_ids:
                continue
            model_name = path.name.removesuffix("_onnx")
            downloaded = any(f.suffix == ".onnx" for f in path.rglob("*"))
            models.append(
                {
                    "id": model_id,
                    "name": model_name,
                    "path": str(path),
                    "downloaded": downloaded,
                }
            )

    return models


# Registry of in-flight / finished downloads, keyed by model id.
_download_registry: Dict[str, "object"] = {}
_download_registry_lock = threading.Lock()


def _run_download(model_id: str, model_type: str, force: bool, progress) -> None:
    """Background worker that downloads a model while reporting progress."""
    from .model_manager import ModelHandler, make_progress_tqdm

    try:
        if force:
            model_dir = _model_dir_for(model_id, model_type)
            if model_dir.exists():
                shutil.rmtree(model_dir)

        cache_root = Path(os.environ.get("PHONEMATION_MODEL_CACHE", _default_model_cache_path()))
        download_path = cache_root / model_type
        download_path.mkdir(parents=True, exist_ok=True)

        mh = ModelHandler.get_instance()
        result = mh.download_model(model_id, str(download_path), tqdm_class=make_progress_tqdm(progress))
        progress.set_completed(Path(result))
        logging.info("Model download completed: %s", model_id)
    except Exception as exc:
        logging.error("Model download failed for %s: %s", model_id, exc)
        progress.set_error(str(exc))


def create_backend_app(backend: Optional["PhonemationBackend"] = None) -> FastAPI:
    app = FastAPI(
        title="Phonemation Backend API",
        description="Frontend-independent audio AI processing API for Phonemation clients such as Godot.",
        version=API_VERSION,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.backend = backend
    # uvicorn.Server handle, set by the launcher so /shutdown can stop the process.
    app.state.server = None

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": API_VERSION}

    @app.get("/status")
    async def status():
        current_backend = app.state.backend
        if not current_backend:
            return {"running": False, "initialized": False, "environment": get_environment_info()}
        return current_backend.get_status()

    @app.get("/emotions")
    async def emotions():
        current_backend = app.state.backend
        if not current_backend:
            return {"emotions": [], "model": None}
        model = None
        if getattr(current_backend, "recognizer", None):
            model = current_backend.recognizer.emotion_model_name
        return {"emotions": current_backend.get_emotions(), "model": model}

    @app.get("/models")
    async def models():
        # _list_cached_models may hit the HuggingFace API (on cache miss); run it
        # off the event loop so output polling is never blocked by network I/O.
        loop = asyncio.get_running_loop()
        phoneme_models = await loop.run_in_executor(None, _list_cached_models, "phoneme")
        emotion_models = await loop.run_in_executor(None, _list_cached_models, "emotion")
        return {
            "cache_path": str(Path(os.environ.get("PHONEMATION_MODEL_CACHE", _default_model_cache_path()))),
            "phoneme": phoneme_models,
            "emotion": emotion_models,
        }

    def _begin_download(model_id: str, force: bool) -> dict:
        """Start (or report) a background download. Shared by /download and /update."""
        from .model_manager import DownloadProgress

        model_type = _resolve_model_type(model_id)

        if not force and _model_is_downloaded(model_id, model_type):
            return {
                "status": "already_downloaded",
                "model_id": model_id,
                "model_type": model_type,
                "path": str(_model_dir_for(model_id, model_type)),
            }

        with _download_registry_lock:
            existing = _download_registry.get(model_id)
            if existing is not None and existing.snapshot()["state"] in ("starting", "downloading"):
                return {
                    "status": "in_progress",
                    "model_id": model_id,
                    "model_type": model_type,
                }
            progress = DownloadProgress(model_id)
            _download_registry[model_id] = progress

        thread = threading.Thread(
            target=_run_download,
            args=(model_id, model_type, force, progress),
            daemon=True,
        )
        thread.start()
        return {"status": "started", "model_id": model_id, "model_type": model_type}

    @app.post("/models/download")
    async def download_model(request: ModelDownloadRequest):
        return _begin_download(request.model_id, request.force)

    @app.post("/models/update")
    async def update_model(request: ModelDownloadRequest):
        return _begin_download(request.model_id, force=True)

    @app.get("/models/download/progress")
    async def download_progress(model_id: str):
        with _download_registry_lock:
            progress = _download_registry.get(model_id)
        if progress is None:
            return {"model_id": model_id, "state": "idle"}
        snapshot = progress.snapshot()
        snapshot["model_id"] = model_id
        if snapshot["state"] in ("completed", "error"):
            try:
                model_type = _resolve_model_type(model_id)
            except HTTPException:
                model_type = None
            if model_type is not None:
                snapshot["path"] = snapshot.get("path") or str(_model_dir_for(model_id, model_type))
        return snapshot

    @app.post("/models/delete")
    async def delete_model(request: ModelDownloadRequest):
        model_id = request.model_id
        model_type = _resolve_model_type(model_id)

        with _download_registry_lock:
            existing = _download_registry.get(model_id)
            if existing is not None and existing.snapshot()["state"] in ("starting", "downloading"):
                raise HTTPException(status_code=409, detail="Cannot delete a model while it is downloading")

        model_dir = _model_dir_for(model_id, model_type)
        if not model_dir.exists():
            return {"status": "not_found", "model_id": model_id, "model_type": model_type}

        try:
            shutil.rmtree(model_dir)
        except Exception as exc:
            logging.error("Failed to delete model %s: %s", model_id, exc)
            raise HTTPException(status_code=500, detail=f"Delete failed: {exc}") from exc

        with _download_registry_lock:
            _download_registry.pop(model_id, None)

        logging.info("Deleted model %s at %s", model_id, model_dir)
        return {"status": "deleted", "model_id": model_id, "model_type": model_type}

    @app.post("/start")
    async def start(request: BackendStartRequest):
        try:
            current_backend = app.state.backend
            if current_backend:
                current_backend.stop()
            from .service import BackendConfig, PhonemationBackend

            request_data = request.model_dump() if hasattr(request, "model_dump") else request.dict()
            current_backend = PhonemationBackend(BackendConfig(**request_data))
            app.state.backend = current_backend
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, current_backend.start)
            return current_backend.get_status()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/stop")
    async def stop():
        current_backend = app.state.backend
        if not current_backend:
            return {"running": False, "initialized": False}
        current_backend.stop()
        return current_backend.get_status()

    @app.post("/restart")
    async def restart():
        current_backend = app.state.backend
        if not current_backend:
            raise HTTPException(status_code=400, detail="Backend has not been started yet")
        try:
            current_backend.restart()
            return current_backend.get_status()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/shutdown")
    async def shutdown():
        """Stop recognition and terminate the server process (remote shutdown)."""
        current_backend = app.state.backend
        if current_backend:
            try:
                current_backend.stop()
            except Exception as exc:
                logging.warning("Error stopping backend during shutdown: %s", exc)

        server = getattr(app.state, "server", None)
        if server is not None:
            logging.info("Remote shutdown requested; stopping server.")
            server.should_exit = True
            return {"status": "shutting_down"}

        logging.warning("Shutdown requested but no server handle was registered.")
        return {
            "status": "stopped_recognition_only",
            "detail": "Recognition stopped, but the server process could not be terminated (no server handle).",
        }

    class VisemeSetRequest(BaseModel):
        viseme_set: str = Field(..., description="Phoneme target set name")

    @app.post("/viseme_set")
    async def set_viseme_set(request: VisemeSetRequest):
        current_backend = app.state.backend
        if not current_backend:
            raise HTTPException(status_code=400, detail="Backend not initialized")
        from .phoneme_mapping import PhonemeMapper
        current_backend.config.viseme_set = request.viseme_set
        current_backend.phoneme_mapper = PhonemeMapper(target_set=request.viseme_set)
        return {"viseme_set": request.viseme_set}

    @app.get("/outputs")
    async def outputs(limit: int = 10):
        current_backend = app.state.backend
        if not current_backend:
            return {"outputs": []}
        return {"outputs": current_backend.drain_outputs(max(1, min(limit, 100)))}

    @app.get("/outputs/next")
    async def next_output(timeout: float = 0.0):
        current_backend = app.state.backend
        if not current_backend:
            return {"output": None}
        output = current_backend.get_next_output(block=timeout > 0, timeout=timeout or None)
        return {"output": output}

    @app.post("/process_audio")
    async def process_audio(request: ProcessAudioRequest):
        current_backend = app.state.backend
        if not current_backend:
            raise HTTPException(status_code=400, detail="Backend not initialized")
        if not current_backend.status.initialized:
            raise HTTPException(status_code=400, detail="Backend not initialized. Call /start first.")
        try:
            result = current_backend.process_audio(request.audio_base64, request.sample_rate, request.channels)
            if result is None:
                raise HTTPException(status_code=500, detail="Audio processing failed")
            result["chunk_id"] = request.chunk_id
            return result
        except HTTPException:
            raise
        except Exception as exc:
            logging.error("Audio processing failed: %s", exc)
            raise HTTPException(status_code=500, detail=f"Audio processing failed: {exc}") from exc

    return app
