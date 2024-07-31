import glob
import math
import os
from pathlib import Path
from queue import Queue

# import torch

os.environ['PHONEMIZER_ESPEAK_LIBRARY'] = "C:\Program Files\eSpeak NG\libespeak-ng.dll"

import onnxruntime as ort
import numpy as np
import yaml

import threading
import time
import soundfile as sf
import soxr


def resample_and_reshape_audio_data(data: np.ndarray, orig_sampling_rate, out_rate=16000):
    speech = soxr.resample(data, orig_sampling_rate, out_rate).squeeze()
    adjusted_speech = speech.reshape(1, -1)
    return adjusted_speech


def speech_file_to_array_fn_resize(path):
    speech_array, _sampling_rate = sf.read(path)
    return resample_and_reshape_audio_data(speech_array, orig_sampling_rate=_sampling_rate)


class ComboRecognizer:
    __instance = None

    @staticmethod
    def get_instance():
        if ComboRecognizer.__instance is None:
            ComboRecognizer()
        return ComboRecognizer.__instance

    def __init__(self, phoneme_model_path="", emotion_model_path="", onnx_providers=None):
        self.recognition_thread = None
        if ComboRecognizer.__instance is not None:
            raise Exception("ComboRecognizer: This class is a singleton!")
        else:
            ComboRecognizer.__instance = self
        current_torch_device = 0
        print(f"Current Torch Device = {current_torch_device}")
        self.ep_list = [
            ('CUDAExecutionProvider', {"cudnn_conv_algo_search": "HEURISTIC", "device_id": current_torch_device})]
        self.model_output = Queue()
        # self.audio_manager = audio_manager
        self.providers = self.ep_list
        self.emotion_model_path = emotion_model_path  # This is the folder containing the emotion model
        self.phoneme_model_path = phoneme_model_path  # This is the folder containing the phoneme model
        self.emotion_model_name = Path(emotion_model_path).name
        self.phoneme_model_name = Path(phoneme_model_path).name
        self.emotion_model = self._load_model(self.emotion_model_path)
        self.phoneme_model = self._load_model(self.phoneme_model_path)
        self.works = True
        self.emotion_settings = None
        self.phoneme_settings = None
        self._load_settings(self.emotion_model_path, "emotion")
        self._load_settings(self.phoneme_model_path, "phoneme")

        if glob.glob(phoneme_model_path + "/*.tokens"):
            with open(glob.glob(phoneme_model_path + "/*.tokens")[0], 'r', encoding="utf8") as f:
                self.token_dict = yaml.safe_load(f)

    def _load_model(self, model_path):
        if not model_path or model_path.endswith("/_onnx"):
            return False
        print(f"Trying to load model from {model_path}.")
        glob_result = glob.glob(model_path + "/*.onnx")
        if len(glob_result) == 0:
            raise Exception(f"No onnx model found in {model_path}.")

        onnx_file = glob_result[0]
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        return ort.InferenceSession(onnx_file, sess_options=session_options,
                                    providers=self.providers)  # , processor

    def get_gpu_info(self):
        return ort.get_device()

    def get_gpu_providers(self):
        return ort.get_available_providers()

    def change_model(self, model_path, model_type="phoneme"):
        if model_type == "phoneme":
            self.phoneme_model_path = model_path
            self.phoneme_model_name = Path(model_path).name
            self.phoneme_model = self._load_model(model_path)
        if model_type == "emotion":
            self.emotion_model_path = model_path
            self.emotion_model_name = Path(model_path).name
            self.emotion_model = self._load_model(model_path)
        # Model changed, we need to load the settings
        self._load_settings(model_path, model_type)

    def _load_settings(self, model_path, model_type="phoneme"):
        if not model_path or model_path.endswith("/_onnx"):
            return False
        settings_path = glob.glob(model_path + "/*.yaml")[0]

        with open(settings_path, 'r') as f:
            if model_type == "phoneme":
                self.phoneme_settings = yaml.safe_load(f)
                settings = self.phoneme_settings
            if model_type == "emotion":
                self.emotion_settings = yaml.safe_load(f)
                settings = self.emotion_settings

        if settings['shape'] == [1, 1024, 128]:
            self.works = False
        if "ast-emotion" in settings["full_name"]:
            self.works = False
        if "labels" in settings:
            self.emotion_labels = settings['labels']

    def processing_thread(self, delta_time=0):
        if not self.audio_manager.audio_buffer.empty():
            audio = self.audio_manager.audio_buffer.get(block=False)
            modified_audio = self.audio_manager.speech_data_to_array_fn(audio)
            start_time = time.time()
            phonemes = self.predict(modified_audio, model_type="phoneme")
            if phonemes:
                emotions = self.predict(modified_audio, model_type="emotion")
                sample_length_ms = len(audio) / self.audio_manager.selected_input_device[
                    'default_samplerate'] * 1000 / len(phonemes)
                sample_volume = self.audio_manager.rms_flat(audio)
                end_time = time.time()
                inference_time = end_time - start_time
                output_data = {"phonemes": phonemes, "emotions": emotions,
                               "audio": audio, "sample_length": sample_length_ms,
                               "volume": sample_volume, "inference_time": inference_time,
                               "number_of_phonemes": len(phonemes)}
                self.model_output.put(output_data)

    def decode_tokens(self, tokens):
        if not isinstance(tokens, list):
            tokens = [tokens]
        decoded_list = []
        for token in tokens:
            decoded_list.append(self.token_dict.get(token))
        decoded_output = []
        for token in decoded_list:
            if token not in self.phoneme_settings["special_tokens"]:
                decoded_output.append(token)
            if token == self.phoneme_settings["special_tokens"][0]:  # word separator
                pass
        return decoded_output

    def get_emotion_list(self):
        # print(f"Emotion list: {self.emotion_labels}")
        if not self.emotion_settings:
            return []
        if "wav2vec2-large-robust-12-ft-emotion-msp-dim" in self.emotion_settings["full_name"]:
            return ["anger", "disgust", "fear", "joy", "sadness", "surprise"]
        else:
            return self.emotion_labels.values()

    def predict(self, audio, model_type="phoneme"):
        if isinstance(audio, str):
            audio = speech_file_to_array_fn_resize(audio)
        input_name = None
        if model_type == "phoneme":
            input_name = self.phoneme_model.get_inputs()[0].name
        elif model_type == "emotion":
            input_name = self.emotion_model.get_inputs()[0].name
        inputs = {input_name: audio.astype(np.float32)}
        if model_type == "phoneme":
            outputs = self.phoneme_model.run(None, inputs)[0]
        else:
            outputs = self.emotion_model.run(None, inputs)[0]
        if model_type == "phoneme":
            prediction = np.argmax(outputs, axis=-1)
            return self.decode_tokens(prediction.squeeze().tolist())
        else:
            if "wav2vec2-large-robust-12-ft-emotion-msp-dim" in self.emotion_settings["full_name"]:
                scores = np.squeeze(outputs)
                use_ekman = True
                if use_ekman:
                    # Centroids of the Ekman emotions in a VAD diagram
                    ekman_emotions = {'anger': [-0.51, 0.59, 0.25], 'disgust': [-0.60, 0.35, 0.11],
                                      'fear': [-0.64, 0.60, -0.43], 'joy': [0.76, 0.48, 0.35],
                                      'sadness': [-0.63, -0.27, -0.33], 'surprise': [0.40, 0.67, -0.13]}
                    distances = []
                    scores = scores[2], scores[0], scores[1]
                    for key, value in ekman_emotions.items():
                        distance = math.dist(value, scores)
                        distances.append(distance)
                    scores = np.squeeze(distances)
                    scores = scores - np.max(scores)
                    scores = np.abs(scores)
                    probabilities = np.exp(scores) / np.sum(np.exp(scores), axis=0)
                    emotions_with_prob = [{"Emotion": label, "Score": prob} for label, prob in
                                          zip(ekman_emotions.keys(), probabilities)]
                    emotions_with_prob.sort(key=lambda x: x["Score"], reverse=True)
                else:
                    emotions_with_prob = [{"Emotion": label, "Score": prob} for label, prob in
                                          zip(self.emotion_labels.values(), scores)]
            else:
                scores = np.squeeze(outputs)
                probabilities = np.exp(scores) / np.sum(np.exp(scores), axis=0)
                emotions_with_prob = [{"Emotion": label, "Score": prob} for label, prob in
                                      zip(self.emotion_labels.values(), probabilities)]
                emotions_with_prob.sort(key=lambda x: x["Score"], reverse=True)
            return emotions_with_prob
