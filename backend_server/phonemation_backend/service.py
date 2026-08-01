import logging
import threading
from dataclasses import dataclass, field
from queue import Empty
from typing import Any, Dict, List, Optional

from .audio.manager import AudioDeviceManager, get_default_device, get_default_hostapi, get_hostapi_name_from_id
from .environment import get_environment_info
from .phoneme_mapping import PhonemeMapper
from .recognizer import ComboRecognizer


@dataclass
class BackendConfig:
    phoneme_model_path: Optional[str] = None
    emotion_model_path: Optional[str] = None
    host_api: Optional[str] = None
    input_device: Optional[str] = None
    output_device: Optional[str] = None
    enable_output: bool = False
    vad_system: str = "volume"
    volume_level_threshold: float = 0.05
    onnx_providers: Optional[List[Any]] = None
    audio_source: str = "local"
    viseme_set: str = "preston_blair"


@dataclass
class BackendStatus:
    running: bool = False
    initialized: bool = False
    input_device: Optional[str] = None
    output_device: Optional[str] = None
    current_volume: float = 0.0
    last_error: Optional[str] = None
    available_providers: List[str] = field(default_factory=list)


class PhonemationBackend:
    def __init__(self, config: BackendConfig):
        self.config = config
        self.audio_manager: Optional[AudioDeviceManager] = None
        self.recognizer: Optional[ComboRecognizer] = None
        self.status = BackendStatus()
        self._lock = threading.RLock()
        self.phoneme_mapper = PhonemeMapper(target_set=config.viseme_set)

    def initialize(self) -> None:
        with self._lock:
            if self.status.initialized:
                return

            ComboRecognizer._ComboRecognizer__instance = None
            AudioDeviceManager._AudioDeviceManager__instance = None

        if self.config.audio_source != "remote":
            self.audio_manager = AudioDeviceManager(
                vad_system=self.config.vad_system,
                volume_level_threshold=self.config.volume_level_threshold,
            )
            self._configure_audio_devices()

        if self.config.phoneme_model_path:
            self.recognizer = ComboRecognizer(
                self.config.phoneme_model_path,
                self.config.emotion_model_path,
                self.audio_manager if self.config.audio_source != "remote" else None,
                onnx_providers=self.config.onnx_providers,
            )
            providers = self.recognizer.get_gpu_providers()
        else:
            providers = []

        with self._lock:
            self.status.available_providers = providers
            self.status.initialized = True
            self.status.last_error = None

    def start(self) -> None:
        self.initialize()
        with self._lock:
            if self.status.running:
                return
            if self.recognizer and self.config.audio_source != "remote":
                self.recognizer.start_continuous_recognition()
            self.status.running = True
            self.status.last_error = None

    def stop(self) -> None:
        with self._lock:
            if self.recognizer:
                self.recognizer.shutdown()
            self.status.running = False

    def restart(self) -> None:
        with self._lock:
            if not self.recognizer:
                self.start()
                return
            self.recognizer.restart_recognizer()
            self.status.running = True

    def get_status(self) -> Dict[str, Any]:
        if self.audio_manager:
            try:
                self.status.current_volume = float(self.audio_manager.current_volume_level)
                if self.audio_manager.selected_input_device:
                    self.status.input_device = self.audio_manager.selected_input_device.get("name")
                if self.audio_manager.selected_output_device:
                    self.status.output_device = self.audio_manager.selected_output_device.get("name")
            except Exception:
                pass
        return {
            "running": self.status.running,
            "initialized": self.status.initialized,
            "phoneme_model_running": self.status.running and self.recognizer is not None,
            "input_device": self.status.input_device or "default",
            "output_device": self.status.output_device or "default",
            "current_volume": self.status.current_volume,
            "last_error": self.status.last_error or "",
            "available_providers": self.status.available_providers,
            "environment": get_environment_info(self.recognizer),
        }

    def get_emotions(self) -> List[str]:
        """Return the emotion labels supported by the currently loaded emotion model."""
        with self._lock:
            if not self.recognizer:
                return []
            try:
                return list(self.recognizer.get_emotion_list())
            except Exception as exc:
                logging.error("Failed to get emotion list: %s", exc)
                return []

    def get_next_output(self, block: bool = False, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        if not self.recognizer:
            return None
        try:
            output = self.recognizer.model_output.get(block=block, timeout=timeout)
        except Empty:
            return None
        return self._serialize_output(output)

    def drain_outputs(self, limit: int = 10) -> List[Dict[str, Any]]:
        outputs = []
        for _ in range(limit):
            output = self.get_next_output(block=False)
            if output is None:
                break
            outputs.append(output)
        return outputs

    def _configure_audio_devices(self) -> None:
        if not self.audio_manager:
            raise RuntimeError("Audio manager is not initialized")

        host_api = self.config.host_api
        if not host_api:
            host_api = get_hostapi_name_from_id(get_default_hostapi())

        if not self.audio_manager.select_hostapi(host_api):
            default_hostapi = get_hostapi_name_from_id(get_default_hostapi())
            logging.warning("Could not select host API %s, falling back to %s", host_api, default_hostapi)
            self.audio_manager.select_hostapi(default_hostapi)

        input_device_id = self._resolve_device_id(self.config.input_device, "input")
        if input_device_id is None:
            input_device_id = get_default_device("input")
        if input_device_id is not None:
            self.audio_manager.select_audio_device(input_device_id, "input")

        if self.config.enable_output:
            output_device_id = self._resolve_device_id(self.config.output_device, "output")
            if output_device_id is None:
                output_device_id = get_default_device("output")
            if output_device_id is not None:
                self.audio_manager.select_audio_device(output_device_id, "output")

    def _resolve_device_id(self, device_name: Optional[str], device_type: str) -> Optional[int]:
        if not device_name or device_name.lower() == "default":
            return None
        return self.audio_manager.get_device_id_from_name(device_name, device_type)

    def process_audio(self, audio_base64: str, sample_rate: int, channels: int = 1) -> Optional[Dict[str, Any]]:
        import base64
        import time
        import numpy as np
        from .audio.manager import resample_and_reshape_audio_data

        if not self.recognizer:
            return None

        try:
            audio_bytes = base64.b64decode(audio_base64)
            audio = np.frombuffer(audio_bytes, dtype=np.float32)

            if channels > 1:
                audio = audio.reshape(-1, channels).mean(axis=1)

            volume = float(np.sqrt(np.mean(audio ** 2)))
            modified_audio = resample_and_reshape_audio_data(audio, orig_sampling_rate=sample_rate)

            start_time = time.time()
            phonemes = self.recognizer.predict(modified_audio, model_type="phoneme")
            if not phonemes:
                return {
                    "phonemes": [],
                    "emotions": [],
                    "sample_length": 0.0,
                    "volume": volume,
                    "inference_time": 0.0,
                    "number_of_phonemes": 0,
                }

            emotions = self.recognizer.predict(modified_audio, model_type="emotion") if self.recognizer.emotion_model else []
            inference_time = time.time() - start_time

            sample_length_ms = len(audio) / sample_rate * 1000 / len(phonemes) if phonemes else 0

            phonemes_cmu = self.phoneme_mapper.convert_phonemes(phonemes)
            visemes = self.phoneme_mapper.convert_visemes(phonemes)

            return {
                "phonemes": phonemes,
                "phonemes_cmu": phonemes_cmu,
                "visemes": visemes,
                "emotions": emotions or [],
                "sample_length": sample_length_ms,
                "volume": volume,
                "inference_time": inference_time,
                "number_of_phonemes": len(phonemes),
            }
        except Exception as exc:
            logging.error("Error in process_audio: %s", exc)
            return None

    def _serialize_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        audio = output.get("audio")
        phonemes = output.get("phonemes", []) or []
        phonemes_cmu = self.phoneme_mapper.convert_phonemes(phonemes)
        visemes = self.phoneme_mapper.convert_visemes(phonemes)
        return {
            "phonemes": phonemes,
            "phonemes_cmu": phonemes_cmu,
            "visemes": visemes,
            "emotions": output.get("emotions", []),
            "sample_length": output.get("sample_length"),
            "volume": float(output.get("volume", 0.0)),
            "inference_time": float(output.get("inference_time", 0.0)),
            "number_of_phonemes": output.get("number_of_phonemes", 0),
            "audio_sample_count": int(len(audio)) if audio is not None else 0,
        }
