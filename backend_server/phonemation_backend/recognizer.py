import glob
import math
import os
from pathlib import Path
from queue import Empty, Full, Queue
import logging

# import torch

# Allow overriding the eSpeak NG library location. Falls back to the default
# Windows install path only if the env var is unset and the file exists.
if not os.environ.get("PHONEMIZER_ESPEAK_LIBRARY"):
    _default_espeak = r"C:\Program Files\eSpeak NG\libespeak-ng.dll"
    if os.path.exists(_default_espeak):
        os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = _default_espeak

import onnxruntime as ort
import numpy as np
import yaml

import threading
import time

from .audio.manager import speech_file_to_array_fn_resize

class ComboRecognizer:
    MODEL_OUTPUT_MAXSIZE = 64

    __instance = None

    @staticmethod
    def get_instance():
        if ComboRecognizer.__instance is None:
            ComboRecognizer()
        return ComboRecognizer.__instance

    def __init__(self, phoneme_model_path, emotion_model_path, audio_manager=None, onnx_providers=None):
        self.recognition_thread = None
        self._processing_stop_event = threading.Event()
        if ComboRecognizer.__instance is not None:
            raise Exception("ComboRecognizer: This class is a singleton!")
        else:
            ComboRecognizer.__instance = self
        current_torch_device = 0
        logging.info(f"Initializing ComboRecognizer with torch device: {current_torch_device}")
        self.ep_list = [
            ("TensorrtExecutionProvider", {"device_id": current_torch_device}),
            ("CUDAExecutionProvider", {"cudnn_conv_algo_search": "HEURISTIC", "device_id": current_torch_device}),
            "DmlExecutionProvider",
            "OpenVINOExecutionProvider",
        ]
        # Bounded: if no client drains outputs, drop the oldest instead of
        # growing without limit (each entry holds a raw audio array).
        self.model_output = Queue(maxsize=self.MODEL_OUTPUT_MAXSIZE)
        self.audio_manager = audio_manager
        self.audio_in_thread = None
        self.audio_out_thread = None
        self.providers = self._resolve_providers(onnx_providers)
        self.emotion_model_path = emotion_model_path
        self.phoneme_model_path = phoneme_model_path
        self.emotion_model_name = Path(emotion_model_path).name if emotion_model_path else None
        self.phoneme_model_name = Path(phoneme_model_path).name
        
        logging.info(f"Loading models - Emotion: {self.emotion_model_name}, Phoneme: {self.phoneme_model_name}")
        self.emotion_model = self._load_model(self.emotion_model_path)
        self.phoneme_model = self._load_model(self.phoneme_model_path)
        self.works = True
        self.emotion_settings = None
        self.phoneme_settings = None
        self._load_settings(self.emotion_model_path, "emotion")
        self._load_settings(self.phoneme_model_path, "phoneme")

        if self.audio_manager is not None:
            self.audio_in_thread = threading.Thread(target=self.audio_manager.start_stream,
                                                    args=(self.audio_manager.record_audio, 'input',),
                                                    daemon=True)
            self.audio_out_thread = threading.Thread(target=self.audio_manager.start_stream,
                                                     args=(self.audio_manager.playback_audio, 'output',),
                                                     daemon=True)

        token_files = glob.glob(phoneme_model_path + "/*.tokens")
        if token_files:
            try:
                with open(token_files[0], 'r', encoding="utf8") as f:
                    self.token_dict = yaml.safe_load(f)
                logging.info(f"Loaded {len(self.token_dict)} tokens from {token_files[0]}")
            except Exception as e:
                logging.error(f"Failed to load tokens file: {str(e)}")
                self.token_dict = {}
        else:
            logging.warning(f"No tokens file found in {phoneme_model_path}")
            self.token_dict = {}

    def _load_model(self, model_path):
        if not model_path or model_path.endswith("/_onnx"):
            logging.warning(f"Invalid model path: {model_path}")
            return False
            
        logging.info(f"Loading model from {model_path}")
        try:
            glob_result = glob.glob(model_path + "/*.onnx")
            if len(glob_result) == 0:
                raise FileNotFoundError(f"No onnx model found in {model_path}")

            onnx_file = glob_result[0]
            session_options = ort.SessionOptions()
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            provider_names = [provider[0] if isinstance(provider, tuple) else provider for provider in self.providers]
            if "DmlExecutionProvider" in provider_names:
                session_options.enable_mem_pattern = False
                session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

            model = ort.InferenceSession(onnx_file, sess_options=session_options, providers=self.providers)
            logging.info(f"Successfully loaded model: {Path(onnx_file).name}")
            return model
            
        except Exception as e:
            logging.error(f"Failed to load model from {model_path}: {str(e)}")
            raise

    def _resolve_providers(self, requested_providers=None):
        available_providers = ort.get_available_providers()
        if requested_providers:
            providers = []
            for provider in requested_providers:
                provider_name = provider[0] if isinstance(provider, tuple) else provider
                if provider_name in available_providers:
                    providers.append(provider)
            if "CPUExecutionProvider" in available_providers and not any(
                (provider[0] if isinstance(provider, tuple) else provider) == "CPUExecutionProvider"
                for provider in providers
            ):
                providers.append("CPUExecutionProvider")
            if providers:
                return providers

        providers = []
        for provider in self.ep_list:
            provider_name = provider[0] if isinstance(provider, tuple) else provider
            if provider_name in available_providers:
                providers.append(provider)
        if "CPUExecutionProvider" in available_providers:
            providers.append("CPUExecutionProvider")
        return providers or available_providers

    def get_gpu_info(self):
        try:
            device = ort.get_device()
            logging.debug(f"GPU device info: {device}")
            return device
        except Exception as e:
            logging.error(f"Failed to get GPU info: {str(e)}")
            return None

    def get_gpu_providers(self):
        try:
            providers = ort.get_available_providers()
            logging.debug(f"Available GPU providers: {providers}")
            return providers
        except Exception as e:
            logging.error(f"Failed to get GPU providers: {str(e)}")
            return []

    def change_model(self, model_path, model_type="phoneme"):
        logging.info(f"Changing {model_type} model to: {model_path}")
        try:
            if model_type == "phoneme":
                self.phoneme_model_path = model_path
                self.phoneme_model_name = Path(model_path).name
                self.phoneme_model = self._load_model(model_path)
            if model_type == "emotion":
                self.emotion_model_path = model_path
                self.emotion_model_name = Path(model_path).name
                self.emotion_model = self._load_model(model_path)
            self._load_settings(model_path, model_type)
            logging.info(f"Successfully changed {model_type} model")
        except Exception as e:
            logging.error(f"Failed to change {model_type} model: {str(e)}")
            raise

    def restart_recognizer(self):
        logging.info("Restarting recognizer")
        try:
            self.stop()
            self._stop_processing_thread()
            
            if self.audio_in_thread is not None and self.audio_in_thread.is_alive():
                self.audio_in_thread.join()
            if self.audio_out_thread is not None and self.audio_out_thread.is_alive():
                self.audio_out_thread.join()

            if self.audio_manager is not None:
                self.audio_in_thread = threading.Thread(target=self.audio_manager.start_stream,
                                                        args=(self.audio_manager.record_audio, 'input',),
                                                        daemon=True)
                self.audio_out_thread = threading.Thread(target=self.audio_manager.start_stream,
                                                         args=(self.audio_manager.playback_audio, 'output',),
                                                         daemon=True)
                self.audio_manager.stop_event.clear()

            self.model_output = Queue(maxsize=self.MODEL_OUTPUT_MAXSIZE)
            self._processing_stop_event.clear()
            self.start_continuous_recognition()
            logging.info("Successfully restarted recognizer")
        except Exception as e:
            logging.error(f"Failed to restart recognizer: {str(e)}")
            raise

    def _load_settings(self, model_path, model_type="phoneme"):
        if not model_path or model_path.endswith("/_onnx"):
            logging.warning(f"Invalid model path for {model_type} settings: {model_path}")
            return False
            
        try:
            settings_files = glob.glob(model_path + "/*.yaml")
            if not settings_files:
                raise FileNotFoundError(f"No settings file found for {model_type} model in {model_path}")
                
            settings_path = settings_files[0]
            with open(settings_path, 'r') as f:
                settings = yaml.safe_load(f)
                if model_type == "phoneme":
                    self.phoneme_settings = settings
                if model_type == "emotion":
                    self.emotion_settings = settings
                logging.info(f"Loaded {model_type} settings from {settings_path}")

            if settings['shape'] == [1, 1024, 128]:
                logging.warning("Model shape [1, 1024, 128] may cause issues")
                self.works = False
            if "ast-emotion" in settings["full_name"]:
                logging.warning("ast-emotion model type may cause issues")
                self.works = False
            if "labels" in settings:
                self.emotion_labels = settings['labels']
                logging.debug(f"Loaded {len(self.emotion_labels)} emotion labels")
                
        except Exception as e:
            logging.error(f"Failed to load {model_type} settings: {str(e)}")
            raise

    def start_recognition_thread(self):
        logging.info("Starting recognition thread")
        self.start_continuous_recognition()

    def start_continuous_recognition(self):
        logging.info("Starting continuous recognition")
        try:
            if self.audio_manager is not None:
                if self.audio_in_thread is not None and not self.audio_in_thread.is_alive():
                    self.audio_in_thread.start()
                if self.audio_manager.selected_output_device and self.audio_out_thread is not None and not self.audio_out_thread.is_alive():
                    self.audio_out_thread.start()
            if not self.recognition_thread or not self.recognition_thread.is_alive():
                self._processing_stop_event.clear()
                self.recognition_thread = threading.Thread(target=self._processing_loop, daemon=True)
                self.recognition_thread.start()
        except Exception as e:
            logging.error(f"Failed to start continuous recognition: {str(e)}")
            raise

    def _processing_loop(self):
        if self.audio_manager is None:
            return
        while not self._processing_stop_event.is_set() and not self.audio_manager.stop_event.is_set():
            self.processing_thread()
            time.sleep(0.1)

    def processing_thread(self, delta_time=0):
        if self.audio_manager is None:
            return
        try:
            try:
                audio = self.audio_manager.audio_buffer.get(block=False)
            except Empty:
                return
            else:
                modified_audio = self.audio_manager.speech_data_to_array_fn(audio)
                
                start_time = time.time()
                phonemes = self.predict(modified_audio, model_type="phoneme")
                
                if phonemes:
                    emotions = self.predict(modified_audio, model_type="emotion") if self.emotion_model else []
                    sample_length_ms = len(audio) / self.audio_manager.selected_input_device[
                        'default_samplerate'] * 1000 / len(phonemes)
                    sample_volume = self.audio_manager.rms_flat(audio)
                    end_time = time.time()
                    inference_time = end_time - start_time
                    
                    output_data = {
                        "phonemes": phonemes,
                        "emotions": emotions,
                        "audio": audio,
                        "sample_length": sample_length_ms,
                        "volume": sample_volume,
                        "inference_time": inference_time,
                        "number_of_phonemes": len(phonemes)
                    }
                    self._put_output(output_data)
                    logging.debug(f"Processed audio: {len(phonemes)} phonemes, {inference_time:.3f}s inference time")
                    
        except Exception as e:
            logging.error(f"Error in processing thread: {str(e)}")

    def _put_output(self, output_data):
        """Enqueue an output, dropping the oldest entry when the queue is full."""
        try:
            self.model_output.put_nowait(output_data)
        except Full:
            try:
                self.model_output.get_nowait()
            except Empty:
                pass
            try:
                self.model_output.put_nowait(output_data)
            except Full:
                logging.warning("Dropped model output; queue is full and could not be drained")

    def decode_tokens(self, tokens):
        if not isinstance(tokens, list):
            tokens = [tokens]
            
        try:
            decoded_list = []
            for token in tokens:
                decoded = self.token_dict.get(token)
                if decoded is None:
                    logging.warning(f"Unknown token: {token}")
                decoded_list.append(decoded)
                
            decoded_output = []
            for token in decoded_list:
                if token not in self.phoneme_settings.get("special_tokens", []):
                    decoded_output.append(token)
                    
            return decoded_output
            
        except Exception as e:
            logging.error(f"Error decoding tokens: {str(e)}")
            return []

    def stop(self):
        logging.info("Stopping recognizer")
        self._processing_stop_event.set()
        if self.audio_manager is not None:
            self.audio_manager.stop_event.set()

    def shutdown(self):
        """Stop recognition and join the processing thread (public API)."""
        self.stop()
        self._stop_processing_thread()

    def _stop_processing_thread(self):
        self._processing_stop_event.set()
        if self.recognition_thread and self.recognition_thread.is_alive():
            self.recognition_thread.join(timeout=2)

    def get_emotion_list(self):
        if not self.emotion_settings:
            logging.warning("No emotion settings available")
            return []
            
        if "wav2vec2-large-robust-12-ft-emotion-msp-dim" in self.emotion_settings["full_name"]:
            emotions = ["anger", "disgust", "fear", "joy", "sadness", "surprise"]
            logging.debug(f"Using wav2vec2 emotion list: {emotions}")
            return emotions
        else:
            emotions = list(self.emotion_labels.values())
            logging.debug(f"Using model emotion list: {emotions}")
            return emotions

    def predict(self, audio, model_type="phoneme"):
        try:
            if isinstance(audio, str):
                audio = speech_file_to_array_fn_resize(audio)
                
            model = self.phoneme_model if model_type == "phoneme" else self.emotion_model
            if not model:
                logging.error(f"No {model_type} model loaded")
                return None
                
            input_name = model.get_inputs()[0].name
            inputs = {input_name: audio.astype(np.float32)}
            
            if model_type == "phoneme":
                outputs = self.phoneme_model.run(None, inputs)[0]
                prediction = np.argmax(outputs, axis=-1)
                return self.decode_tokens(prediction.squeeze().tolist())
            else:
                outputs = self.emotion_model.run(None, inputs)[0]
                if "wav2vec2-large-robust-12-ft-emotion-msp-dim" in self.emotion_settings["full_name"]:
                    scores = np.squeeze(outputs)
                    use_ekman = True
                    if use_ekman:
                        ekman_emotions = {
                            'anger': [-0.51, 0.59, 0.25],
                            'disgust': [-0.60, 0.35, 0.11],
                            'fear': [-0.64, 0.60, -0.43],
                            'joy': [0.76, 0.48, 0.35],
                            'sadness': [-0.63, -0.27, -0.33],
                            'surprise': [0.40, 0.67, -0.13]
                        }
                        distances = []
                        scores = scores[2], scores[0], scores[1]
                        for key, value in ekman_emotions.items():
                            distance = math.dist(value, scores)
                            distances.append(distance)
                        scores = np.squeeze(distances)
                        scores = scores - np.max(scores)
                        scores = np.abs(scores)
                        probabilities = np.exp(scores) / np.sum(np.exp(scores), axis=0)
                        emotions_with_prob = [{"Emotion": label, "Score": float(prob)} for label, prob in
                                              zip(ekman_emotions.keys(), probabilities)]
                        emotions_with_prob.sort(key=lambda x: x["Score"], reverse=True)
                        logging.debug(f"Top emotion: {emotions_with_prob[0]['Emotion']} ({emotions_with_prob[0]['Score']:.3f})")
                    else:
                        emotions_with_prob = [{"Emotion": label, "Score": float(prob)} for label, prob in
                                              zip(self.emotion_labels.values(), scores)]
                else:
                    scores = np.squeeze(outputs)
                    probabilities = np.exp(scores) / np.sum(np.exp(scores), axis=0)
                    emotions_with_prob = [{"Emotion": label, "Score": float(prob)} for label, prob in
                                          zip(self.emotion_labels.values(), probabilities)]
                    emotions_with_prob.sort(key=lambda x: x["Score"], reverse=True)
                    logging.debug(f"Top emotion: {emotions_with_prob[0]['Emotion']} ({emotions_with_prob[0]['Score']:.3f})")
                return emotions_with_prob
                
        except Exception as e:
            logging.error(f"Error in {model_type} prediction: {str(e)}")
            return None
