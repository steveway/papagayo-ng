"""Backend-based phoneme recognizer for papagayo-ng.

Manages the phonemation_backend server as a subprocess and communicates
with it over HTTP (REST API).  The backend loads the ONNX wav2vec2 models,
runs inference, and returns phonemes already converted to CMU format via
its PhonemeMapper.

This replaces the previous in-process ComboRecognizer / OnnxRecognizer /
AllosaurusRecognizer / RhubarbRecognizer stack with a single clean
integration point.
"""

import atexit
import base64
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
import requests
import soundfile as sf

import utilities

logger = logging.getLogger(__name__)

# Default port for the backend subprocess.  Chosen to avoid common conflicts.
_DEFAULT_PORT = 8765
_HEALTH_TIMEOUT = 30  # seconds to wait for the backend to become healthy
_HTTP_TIMEOUT = 120  # seconds for individual HTTP requests


def _find_free_port(preferred: int = _DEFAULT_PORT) -> int:
    """Return *preferred* if it is free, otherwise let the OS pick a port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


class BackendRecognizer:
    """Phoneme recognizer that delegates to the phonemation_backend subprocess."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, phoneme_model_path: str = "", emotion_model_path: str = "", port: int = 0):
        if getattr(self, "_initialized", False):
            # Re-use the running backend; just reload models if paths changed.
            if phoneme_model_path and phoneme_model_path != self._loaded_phoneme_path:
                self._start_backend_with_models(phoneme_model_path, emotion_model_path)
            return

        self._initialized = True
        self._process: Optional[subprocess.Popen] = None
        self._port: int = 0
        self._base_url: str = ""
        self._loaded_phoneme_path: str = ""
        self._loaded_emotion_path: str = ""
        self._available: bool = False
        self._progress_callback = None

        if phoneme_model_path:
            self._start_backend_with_models(phoneme_model_path, emotion_model_path)

        atexit.register(self.shutdown)

    # ------------------------------------------------------------------ #
    #  Subprocess management
    # ------------------------------------------------------------------ #

    def _backend_server_dir(self) -> Path:
        """Return the directory containing the ``phonemation_backend`` package."""
        return Path(__file__).resolve().parent / "backend_server"

    def _python_executable(self) -> str:
        """Return the Python executable to use for the backend subprocess."""
        # Use the same interpreter that papagayo-ng is running with.
        return sys.executable

    def _start_subprocess(self, port: int) -> bool:
        """Launch the backend server subprocess on *port*."""
        backend_dir = str(self._backend_server_dir())
        cmd = [
            self._python_executable(),
            "-m",
            "phonemation_backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]

        logger.info("Starting backend subprocess: %s (cwd=%s)", " ".join(cmd), backend_dir)
        try:
            self._process = subprocess.Popen(
                cmd,
                cwd=backend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
            )
            # Start a thread to drain stdout so the pipe doesn't fill and block.
            import threading
            def _drain():
                if self._process and self._process.stdout:
                    for line in self._process.stdout:
                        logger.info("[backend] %s", line.decode("utf-8", errors="replace").rstrip())
            t = threading.Thread(target=_drain, daemon=True)
            t.start()
        except Exception as exc:
            logger.error("Failed to start backend subprocess: %s", exc)
            self._available = False
            return False

        self._port = port
        self._base_url = f"http://127.0.0.1:{port}"
        return self._wait_for_health()

    def _wait_for_health(self) -> bool:
        """Poll the /health endpoint until the backend responds or timeout."""
        deadline = time.time() + _HEALTH_TIMEOUT
        while time.time() < deadline:
            if self._process and self._process.poll() is not None:
                logger.error("Backend subprocess exited early with code %s", self._process.returncode)
                self._available = False
                return False
            try:
                resp = requests.get(f"{self._base_url}/health", timeout=2)
                if resp.status_code == 200:
                    logger.info("Backend is healthy on port %d", self._port)
                    self._available = True
                    return True
            except requests.RequestException:
                pass
            time.sleep(0.5)

        logger.error("Backend did not become healthy within %d seconds", _HEALTH_TIMEOUT)
        self._available = False
        return False

    def _start_backend_with_models(self, phoneme_model_path: str, emotion_model_path: str = "") -> bool:
        """Ensure the backend subprocess is running and has the requested models loaded."""
        # Start subprocess if not yet running.
        if not self._available or not self._base_url:
            port = _find_free_port(_DEFAULT_PORT)
            if not self._start_subprocess(port):
                return False

        # Tell the backend to load the models (audio_source=remote => no audio devices).
        payload = {
            "phoneme_model_path": phoneme_model_path,
            "audio_source": "remote",
            "viseme_set": "cmu_39",
        }
        if emotion_model_path:
            payload["emotion_model_path"] = emotion_model_path

        try:
            resp = requests.post(f"{self._base_url}/start", json=payload, timeout=_HTTP_TIMEOUT)
            if resp.status_code != 200:
                logger.error("Backend /start failed: %s %s", resp.status_code, resp.text)
                self._available = False
                return False
            self._loaded_phoneme_path = phoneme_model_path
            self._loaded_emotion_path = emotion_model_path
            logger.info("Backend loaded models (phoneme=%s, emotion=%s)", phoneme_model_path, emotion_model_path or "none")
            return True
        except requests.RequestException as exc:
            logger.error("Failed to call backend /start: %s", exc)
            self._available = False
            return False

    # ------------------------------------------------------------------ #
    #  Model management (delegated to the backend's REST API)
    # ------------------------------------------------------------------ #

    def _ensure_backend_running(self) -> bool:
        """Make sure the backend subprocess is up and healthy."""
        if self._available and self._base_url:
            return True
        port = _find_free_port(_DEFAULT_PORT)
        return self._start_subprocess(port)

    def list_models(self, model_type: str = "phoneme") -> List[dict]:
        """Return the list of available models from the backend.

        Each entry is a dict with keys: id, name, path, downloaded.
        """
        if not self._ensure_backend_running():
            return []
        try:
            resp = requests.get(f"{self._base_url}/models", timeout=30)
            if resp.status_code == 200:
                return resp.json().get(model_type, [])
        except requests.RequestException as exc:
            logger.error("Failed to list models: %s", exc)
        return []

    def get_model_list(self, model_type: str = "phoneme") -> List[str]:
        """Return just the model IDs (compatible with old ModelHandler interface)."""
        return [m["id"] for m in self.list_models(model_type)]

    def is_model_downloaded(self, model_id: str, model_type: str = "phoneme") -> bool:
        """Check whether *model_id* is already downloaded locally."""
        for m in self.list_models(model_type):
            if m["id"] == model_id:
                return m["downloaded"]
        return False

    def get_model_path(self, model_id: str, model_type: str = "phoneme") -> Optional[str]:
        """Return the local filesystem path for a downloaded model, or None."""
        for m in self.list_models(model_type):
            if m["id"] == model_id:
                return m["path"] if m["downloaded"] else None
        return None

    def download_model(self, model_id: str, force: bool = False,
                       progress_callback=None) -> Optional[str]:
        """Download *model_id* via the backend and return its local path.

        *progress_callback* (if given) is called with a float 0..100.
        Blocks until the download completes or fails.
        """
        if not self._ensure_backend_running():
            return None

        # If already downloaded and not forcing, return the path directly.
        if not force:
            path = self.get_model_path(model_id)
            if path:
                logger.info("Model %s already downloaded at %s", model_id, path)
                return path

        try:
            resp = requests.post(
                f"{self._base_url}/models/download",
                json={"model_id": model_id, "force": force},
                timeout=30,
            )
            data = resp.json()
            status = data.get("status")
            if status == "already_downloaded":
                return data.get("path")
            if status not in ("started", "in_progress"):
                logger.error("Download not started: %s", data)
                return None
        except requests.RequestException as exc:
            logger.error("Failed to start download: %s", exc)
            return None

        # Poll progress until done.
        import time as _time
        while True:
            _time.sleep(1.0)
            try:
                resp = requests.get(
                    f"{self._base_url}/models/download/progress",
                    params={"model_id": model_id},
                    timeout=10,
                )
                data = resp.json()
                state = data.get("state", "idle")
                percent = data.get("percent", 0.0)
                if progress_callback:
                    progress_callback(percent)
                logger.info("Download %s: %.1f%%", state, percent)
                if state == "completed":
                    return data.get("path")
                if state == "error":
                    logger.error("Download error: %s", data.get("error"))
                    return None
            except requests.RequestException as exc:
                logger.warning("Progress poll failed: %s", exc)

    def ensure_model(self, model_id: str, model_type: str = "phoneme",
                     progress_callback=None) -> Optional[str]:
        """Ensure *model_id* is downloaded and return its local path.

        This replaces the old ``ensure_model_exists`` function.
        """
        if not model_id:
            return None
        return self.download_model(model_id, force=False,
                                   progress_callback=progress_callback)

    def delete_model(self, model_id: str) -> bool:
        """Delete a downloaded model from the backend's cache."""
        if not self._ensure_backend_running():
            return False
        try:
            resp = requests.post(
                f"{self._base_url}/models/delete",
                json={"model_id": model_id},
                timeout=10,
            )
            return resp.status_code == 200 and resp.json().get("status") == "deleted"
        except requests.RequestException:
            return False

    # ------------------------------------------------------------------ #
    #  Public API (compatible with the old recognizer interface)
    # ------------------------------------------------------------------ #

    def is_available(self) -> bool:
        return self._available

    def set_progress_callback(self, callback):
        self._progress_callback = callback

    def predict(self, audio_file: str, model_type: str = "phoneme") -> List[dict]:
        """Recognize phonemes in *audio_file*.

        Returns a list of dicts with ``start``, ``duration`` and ``phoneme``
        keys.  Phonemes are already in CMU-39 format (the backend performs
        the IPA→CMU conversion via its PhonemeMapper).
        """
        if not self._available:
            logger.error("Backend is not available; cannot predict")
            return []

        try:
            audio_data, sample_rate = sf.read(audio_file)
        except Exception as exc:
            logger.error("Failed to read audio file %s: %s", audio_file, exc)
            return []

        # Ensure float32 and flatten multi-channel to mono.
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        if audio_data.ndim > 1:
            channels = audio_data.shape[1]
            audio_data = audio_data.mean(axis=1)
        else:
            channels = 1
        audio_data = audio_data.squeeze()

        audio_bytes = audio_data.tobytes()
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

        payload = {
            "audio_base64": audio_b64,
            "sample_rate": sample_rate,
            "channels": channels,
            "chunk_id": 0,
        }

        try:
            resp = requests.post(f"{self._base_url}/process_audio", json=payload, timeout=_HTTP_TIMEOUT)
        except requests.RequestException as exc:
            logger.error("Failed to call /process_audio: %s", exc)
            return []

        if resp.status_code != 200:
            logger.error("/process_audio returned %s: %s", resp.status_code, resp.text)
            return []

        result = resp.json()
        phonemes_cmu = result.get("phonemes_cmu", [])
        if not phonemes_cmu:
            logger.warning("Backend returned no CMU phonemes")
            return []

        sample_length_ms = result.get("sample_length", 0.0)
        sample_length_sec = sample_length_ms / 1000.0 if sample_length_ms else 0.0

        output = []
        for i, phoneme in enumerate(phonemes_cmu):
            if phoneme is None:
                continue
            output.append({
                "start": i * sample_length_sec,
                "duration": sample_length_sec,
                "phoneme": phoneme,
            })

        logger.info("Backend recognized %d phonemes from %s", len(output), audio_file)
        return output

    def change_model(self, model_path: str, model_type: str = "phoneme") -> bool:
        """Load a different model into the running backend."""
        if model_type == "phoneme":
            return self._start_backend_with_models(model_path, self._loaded_emotion_path)
        elif model_type == "emotion":
            return self._start_backend_with_models(self._loaded_phoneme_path, model_path)
        return False

    def get_gpu_info(self):
        return "backend-subprocess"

    def get_gpu_providers(self):
        if not self._available:
            return []
        try:
            resp = requests.get(f"{self._base_url}/status", timeout=5)
            if resp.status_code == 200:
                return resp.json().get("available_providers", [])
        except requests.RequestException:
            pass
        return []

    def shutdown(self):
        """Stop the backend subprocess."""
        if self._base_url:
            try:
                requests.post(f"{self._base_url}/shutdown", timeout=5)
            except requests.RequestException:
                pass

        if self._process:
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

        self._available = False
        self._base_url = ""
