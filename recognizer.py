import glob
import platform
import traceback
import subprocess
import tempfile
import math
import os
from pathlib import Path
from queue import Queue
import logging
import json
from ai_output_process import get_best_fitting_output_from_list

os.environ['PHONEMIZER_ESPEAK_LIBRARY'] = r"C:\Program Files\eSpeak NG\libespeak-ng.dll"

import onnxruntime as ort
import numpy as np
import yaml
from allosaurus.app import read_recognizer
import path_utils
import time
import soundfile as sf
import soxr
from abc import ABC, abstractmethod


def resample_and_reshape_audio_data(data: np.ndarray, orig_sampling_rate, out_rate=16000):
    speech = soxr.resample(data, orig_sampling_rate, out_rate).squeeze()
    adjusted_speech = speech.reshape(1, -1)
    return adjusted_speech


def speech_file_to_array_fn_resize(path):
    speech_array, _sampling_rate = sf.read(path)
    return resample_and_reshape_audio_data(speech_array, orig_sampling_rate=_sampling_rate)


class BaseRecognizer(ABC):
    """Abstract base class for all recognizers"""
    
    @abstractmethod
    def predict(self, audio, **kwargs):
        """
        Predict phonemes from audio data
        
        Args:
            audio: Audio data or path to audio file
            **kwargs: Additional arguments specific to the recognizer
            
        Returns:
            List of phonemes or phoneme dictionaries
        """
        pass
    
    @abstractmethod
    def is_available(self):
        """Check if this recognizer is available on the current system"""
        pass


class ComboRecognizer(BaseRecognizer):
    """
    A recognizer that combines ONNX, Allosaurus, and Rhubarb
    Falls back to Allosaurus or Rhubarb if ONNX is not available
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """
        Create a new instance of the class, or return the existing one
        """
        if cls._instance is None:
            cls._instance = super(ComboRecognizer, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, phoneme_model_path="", emotion_model_path="", onnx_providers=None):
        """
        Initialize the recognizer with the given model path
        :param phoneme_model_path: Path to the phoneme model
        :param emotion_model_path: Path to the emotion model
        :param onnx_providers: List of ONNX providers to use
        """
        if getattr(self, "_initialized", False):
            # Already initialized, just update the model path if provided
            if phoneme_model_path and phoneme_model_path != self.phoneme_model_path:
                self.phoneme_model_path = phoneme_model_path
                self._initialize_models()
            if emotion_model_path and emotion_model_path != self.emotion_model_path:
                self.emotion_model_path = emotion_model_path
                self._initialize_models()
            if onnx_providers and onnx_providers != self.providers:
                self.providers = onnx_providers
                self._initialize_models()
            return
            
        super().__init__()
        self.recognition_thread = None
        self.ep_list = [
            ('CUDAExecutionProvider', {"cudnn_conv_algo_search": "HEURISTIC", "device_id": 0})]
        self.model_output = Queue()
        self.providers = self.ep_list if onnx_providers is None else onnx_providers
        
        # Initialize models
        self.phoneme_model_path = phoneme_model_path
        self.emotion_model_path = emotion_model_path
        self.phoneme_model = None
        self.emotion_model = None
        self.phoneme_settings = {}
        self.emotion_settings = {}
        
        # Initialize recognizers
        self.onnx_recognizer = None
        self.allosaurus_recognizer = None
        self.rhubarb_recognizer = None
        self.current_recognizer = None
        
        # Try to initialize the ONNX model
        self._initialize_models()
        
        # Initialize fallback recognizers
        self._initialize_fallbacks()

        self._initialized = True
    
    def _initialize_models(self):
        """Initialize the ONNX models"""
        try:
            if self.phoneme_model_path:
                self._load_model(self.phoneme_model_path, "phoneme")
            if self.emotion_model_path:
                self._load_model(self.emotion_model_path, "emotion")
            
            # Set works flag based on model availability
            self.works = bool(self.phoneme_model or self.emotion_model)
            
            # Load settings if models are available
            if self.phoneme_model and self.phoneme_model_path:
                self._load_settings(self.phoneme_model_path, "phoneme")
            if self.emotion_model and self.emotion_model_path:
                self._load_settings(self.emotion_model_path, "emotion")
                
        except Exception as e:
            logging.error(f"Error initializing models: {str(e)}")
            logging.error(traceback.format_exc())
            self.works = False
    
    def _initialize_fallbacks(self):
        """Initialize fallback recognizers"""
        try:
            # Create Allosaurus recognizer as fallback
            self.allosaurus_recognizer = AllosaurusRecognizer()
            
            # Create Rhubarb recognizer as fallback
            self.rhubarb_recognizer = RhubarbRecognizer()
            
            # Set the current recognizer based on availability
            if self.works:
                self.current_recognizer = "onnx"
                logging.info("Using ONNX recognizer")
            elif self.allosaurus_recognizer.is_available():
                self.current_recognizer = "allosaurus"
                logging.info("Falling back to Allosaurus recognizer")
            elif self.rhubarb_recognizer.is_available():
                self.current_recognizer = "rhubarb"
                logging.info("Falling back to Rhubarb recognizer")
            else:
                self.current_recognizer = None
                logging.error("No recognizer available")
        except Exception as e:
            logging.error(f"Error initializing fallbacks: {str(e)}")
            logging.error(traceback.format_exc())
            self.current_recognizer = None
    
    def _load_model(self, model_path, model_type="phoneme"):
        """Load the ONNX model from the given path"""
        try:
            logging.info(f"Trying to load model from {model_path}.")
            
            # Convert string path to Path object if needed
            if isinstance(model_path, str):
                model_path = Path(model_path)
                
            if not model_path.exists():
                logging.error(f"Model path {model_path} does not exist")
                return None
            
            # Check if model_path is a directory or a file
            if model_path.is_dir():
                # Find the ONNX file in the directory
                onnx_files = list(model_path.glob("*.onnx"))
                if not onnx_files:
                    logging.error(f"No ONNX files found in {model_path}")
                    return None
                model_file = onnx_files[0]
                logging.info(f"Found ONNX model file: {model_file}")
            else:
                # Assume model_path is the ONNX file
                model_file = model_path
            
            # Load the model
            try:
                session_options = ort.SessionOptions()
                session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                session_options.enable_cpu_mem_arena = False
                session_options.enable_mem_pattern = False
                session_options.enable_mem_reuse = False
                
                # Try to load with CUDA first, fall back to CPU if needed
                try:
                    model = ort.InferenceSession(str(model_file), sess_options=session_options, providers=self.providers)
                    logging.info(f"Successfully loaded {model_type} model with providers: {self.providers}")
                except Exception as e:
                    logging.warning(f"Failed to load model with CUDA: {str(e)}, falling back to CPU")
                    model = ort.InferenceSession(str(model_file), sess_options=session_options, providers=['CPUExecutionProvider'])
                    logging.info(f"Successfully loaded {model_type} model with CPU provider")
                
                # Set the appropriate model attribute
                if model_type == "phoneme":
                    self.phoneme_model = model
                else:
                    self.emotion_model = model
                
                return model
            except Exception as e:
                logging.error(f"Failed to load ONNX model: {str(e)}")
                logging.error(traceback.format_exc())
                return None
        except Exception as e:
            logging.error(f"Error loading model: {str(e)}")
            logging.error(traceback.format_exc())
            return None

    def get_gpu_info(self):
        return ort.get_device()

    def get_gpu_providers(self):
        return ort.get_available_providers()

    def change_model(self, model_path, model_type="phoneme"):
        model_path = Path(model_path)
        if model_type == "phoneme":
            self.phoneme_model_path = model_path
            self.phoneme_model_name = model_path.name
            self.phoneme_model = self._load_model(model_path, "phoneme")
            if self.phoneme_model:
                self._load_settings(model_path, "phoneme")
        if model_type == "emotion":
            self.emotion_model_path = model_path
            self.emotion_model_name = model_path.name
            self.emotion_model = self._load_model(model_path, "emotion")
            if self.emotion_model:
                self._load_settings(model_path, "emotion")
        return bool(self.phoneme_model or self.emotion_model)

    def _load_settings(self, model_path, model_type="phoneme"):
        """Load settings for the model from a YAML file"""
        try:
            # Convert string path to Path object if needed
            if isinstance(model_path, str):
                model_path = Path(model_path)
                
            # Find the YAML file in the model directory
            if model_path.is_dir():
                yaml_files = list(model_path.glob("*.yaml"))
                if not yaml_files:
                    logging.warning(f"No YAML settings file found for {model_type} model in {model_path}")
                    return None
                yaml_file = yaml_files[0]
            else:
                # Assume model_path is a file, use the same directory
                yaml_files = list(model_path.parent.glob("*.yaml"))
                if not yaml_files:
                    logging.warning(f"No YAML settings file found for {model_type} model in {model_path.parent}")
                    return None
                yaml_file = yaml_files[0]
            
            logging.info(f"Using settings file: {yaml_file}")
            
            # Load the settings from the YAML file
            with open(yaml_file, 'r') as f:
                settings = yaml.safe_load(f)
            
            # Store the settings in the appropriate attribute
            if model_type == "phoneme":
                self.phoneme_settings = settings
                
                # Initialize token_dict
                self.token_dict = {}
                
                # Try to load token dictionary from settings
                if "token_dict" in settings:
                    token_dict_path = model_path / settings["token_dict"] if model_path.is_dir() else model_path.parent / settings["token_dict"]
                    if token_dict_path.exists():
                        with open(token_dict_path, 'r') as f:
                            self.token_dict = yaml.safe_load(f)
                    else:
                        logging.warning(f"Token dictionary file not found: {token_dict_path}")
                
                # If token_dict is still empty, try to find token files
                if not self.token_dict:
                    # Try to find any token file in the directory
                    token_files = list(model_path.glob("*.tokens")) if model_path.is_dir() else list(model_path.parent.glob("*.tokens"))
                    if token_files:
                        try:
                            with open(token_files[0], 'r') as f:
                                # Try to load as YAML first
                                try:
                                    self.token_dict = yaml.safe_load(f)
                                except yaml.YAMLError:
                                    # If YAML loading fails, try to read as plain text
                                    f.seek(0)
                                    token_list = f.read().splitlines()
                                    self.token_dict = {i: token for i, token in enumerate(token_list)}
                        except Exception as e:
                            logging.error(f"Error loading token file: {str(e)}")
                
                # If still no token_dict, check if there's a token_list in settings
                if not self.token_dict and "token_list" in settings:
                    token_list_path = model_path / settings["token_list"] if model_path.is_dir() else model_path.parent / settings["token_list"]
                    if token_list_path.exists():
                        with open(token_list_path, 'r') as f:
                            token_list = f.read().splitlines()
                            self.token_dict = {i: token for i, token in enumerate(token_list)}
                    else:
                        logging.warning(f"Token list file not found: {token_list_path}")
                
                # If still no token_dict, use a default mapping if available in settings
                if not self.token_dict and "tokens" in settings:
                    self.token_dict = settings["tokens"]
                
                # Log warning if token_dict is still empty
                if not self.token_dict:
                    logging.warning(f"No token dictionary found for {model_type} model")
            else:
                self.emotion_settings = settings
                
                # Initialize emotion_labels
                self.emotion_labels = {}
                
                # Try to load emotion labels from settings
                if "label_dict" in settings:
                    label_dict_path = model_path / settings["label_dict"] if model_path.is_dir() else model_path.parent / settings["label_dict"]
                    if label_dict_path.exists():
                        with open(label_dict_path, 'r') as f:
                            self.emotion_labels = yaml.safe_load(f)
                    else:
                        logging.warning(f"Label dictionary file not found: {label_dict_path}")
                
                # If still no emotion_labels, check if there's a label_list in settings
                if not self.emotion_labels and "label_list" in settings:
                    label_list_path = model_path / settings["label_list"] if model_path.is_dir() else model_path.parent / settings["label_list"]
                    if label_list_path.exists():
                        with open(label_list_path, 'r') as f:
                            label_list = f.read().splitlines()
                            self.emotion_labels = {i: label for i, label in enumerate(label_list)}
                    else:
                        logging.warning(f"Label list file not found: {label_list_path}")
                
                # If still no emotion_labels, use labels from settings if available
                if not self.emotion_labels and "labels" in settings:
                    self.emotion_labels = settings["labels"]
                
                # Log warning if emotion_labels is still empty
                if not self.emotion_labels:
                    logging.warning(f"No emotion labels found for {model_type} model")
            
            return settings
        except Exception as e:
            logging.error(f"Error loading settings: {str(e)}")
            logging.error(traceback.format_exc())
            return None
    
    def processing_thread(self, delta_time=0):
        """Background processing thread for asynchronous recognition"""
        while True:
            if not self.model_output.empty():
                audio_file = self.model_output.get()
                if audio_file == "STOP":
                    break
                try:
                    result = self.predict(audio_file)
                    logging.info(f"Processed {audio_file} with result: {result}")
                except Exception as e:
                    logging.error(f"Error processing {audio_file}: {str(e)}")
            time.sleep(delta_time)

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
        if not self.emotion_settings:
            return []
        if "wav2vec2-large-robust-12-ft-emotion-msp-dim" in self.emotion_settings.get("full_name", ""):
            return ["anger", "disgust", "fear", "joy", "sadness", "surprise"]
        else:
            return list(self.emotion_labels.values())

    def predict(self, audio, model_type="phoneme"):
        """
        Predict phonemes or emotions from audio
        
        Args:
            audio: Audio data or path to audio file
            model_type: Type of prediction to make ("phoneme" or "emotion")
            
        Returns:
            List of phonemes or emotions with probabilities
        """
        if isinstance(audio, str):
            audio = speech_file_to_array_fn_resize(audio)
        
        # Get the appropriate model and input name
        if model_type == "phoneme":
            if not self.phoneme_model:
                raise RuntimeError("No phoneme model loaded")
            model = self.phoneme_model
        else:  # emotion
            if not self.emotion_model:
                raise RuntimeError("No emotion model loaded")
            model = self.emotion_model
        
        input_name = model.get_inputs()[0].name
        inputs = {input_name: audio.astype(np.float32)}
        outputs = model.run(None, inputs)[0]
        
        # Process outputs based on model type
        if model_type == "phoneme":
            prediction = np.argmax(outputs, axis=-1)
            phonemes = self.decode_tokens(prediction.squeeze().tolist())
            
            # Convert IPA phonemes to CMU phonemes using the mapping
            
            # Load the IPA to CMU mapping
            ipa_cmu_path = path_utils.get_file_inside_exe("ipa_cmu.json")
            with open(ipa_cmu_path, 'r', encoding='utf-8') as f:
                ipa_cmu_dict = json.load(f)
            
            # Convert phonemes using the mapping
            cmu_phonemes = get_best_fitting_output_from_list(phonemes, ipa_cmu_dict)
            
            # Create timing information
            result = []
            if phonemes:
                # Calculate time per phoneme
                time_per_phoneme = len(audio) / len(phonemes)
                
                # Create result with timing information
                for i, phoneme in enumerate(cmu_phonemes):
                    result.append({
                        "start": i * time_per_phoneme,
                        "duration": time_per_phoneme,
                        "phoneme": phoneme
                    })
            
            return result
        else:  # emotion
            if "wav2vec2-large-robust-12-ft-emotion-msp-dim" in self.emotion_settings.get("full_name", ""):
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
    
    def is_available(self):
        """Check if ONNX models are available"""
        return self.works


class AllosaurusRecognizer(BaseRecognizer):
    """Allosaurus recognizer for phoneme recognition"""
    __instance = None
    
    def __init__(self):
        """Initialize the Allosaurus recognizer"""
        super().__init__()
        self.lang_id = "eng"
        self.emission = 1.0
        self.recognizer = None
        
        try:
            self.recognizer = read_recognizer()
            self.available = True
        except Exception as e:
            logging.error(f"Failed to initialize Allosaurus: {str(e)}")
            self.available = False
    
    def is_available(self):
        """Check if Allosaurus is available"""
        return self.available
    
    def set_language(self, lang_id):
        """Set the language for Allosaurus"""
        self.lang_id = lang_id
    
    def set_emission(self, emission):
        """Set the emission value for Allosaurus"""
        self.emission = emission
    
    def predict(self, audio_file, language="eng"):
        """
        Predict phonemes from audio file using Allosaurus
        :param audio_file: Path to audio file
        :param language: Language code
        :return: List of phonemes with timing information
        """
        try:
            # Check if Allosaurus is available
            if not self.is_available():
                logging.error("Allosaurus is not available")
                return []
            
            # Get the audio duration
            audio_duration = self.get_audio_duration(audio_file)
            if audio_duration is None:
                logging.error(f"Failed to get audio duration: {audio_file}")
                return []
            
            # Run Allosaurus
            try:
                # Try to use the full Allosaurus API with timing information
                logging.info(f"Running Allosaurus on {audio_file}")
                try:
                    # First try with timestamp parameter if available
                    phonemes = self.recognizer.recognize(audio_file, timestamp=True)
                    print(phonemes)
                    
                    # Check if we got proper timing information
                    if isinstance(phonemes, str):
                        # Parse the string output format (timestamp duration phoneme)
                        lines = phonemes.strip().split('\n')
                        result = []
                        for line in lines:
                            parts = line.strip().split()
                            if len(parts) >= 3:
                                try:
                                    start = float(parts[0])
                                    duration = float(parts[1])
                                    phone = parts[2]
                                    
                                    # Convert IPA phoneme to CMU
                                    
                                    # Load the IPA to CMU mapping
                                    ipa_cmu_path = path_utils.get_file_inside_exe("ipa_cmu.json")
                                    with open(ipa_cmu_path, 'r', encoding='utf-8') as f:
                                        ipa_cmu_dict = json.load(f)
                                    
                                    # Convert the phoneme
                                    cmu_phoneme = get_best_fitting_output_from_list([phone], ipa_cmu_dict)[0]
                                    
                                    result.append({
                                        "start": start,
                                        "duration": duration,
                                        "phoneme": cmu_phoneme
                                    })
                                except (ValueError, IndexError) as e:
                                    logging.warning(f"Could not parse line: {line}, error: {str(e)}")
                        
                        if result:
                            return result
                    elif isinstance(phonemes, list) and len(phonemes) > 0 and isinstance(phonemes[0], dict) and "start" in phonemes[0]:
                        # Convert IPA phonemes to CMU phonemes
                        
                        # Load the IPA to CMU mapping
                        ipa_cmu_path = path_utils.get_file_inside_exe("ipa_cmu.json")
                        with open(ipa_cmu_path, 'r', encoding='utf-8') as f:
                            ipa_cmu_dict = json.load(f)
                        
                        # Extract just the phoneme values
                        ipa_phonemes = [p["phone"] for p in phonemes]
                        
                        # Convert phonemes using the mapping
                        cmu_phonemes = get_best_fitting_output_from_list(ipa_phonemes, ipa_cmu_dict)
                        
                        # Create new result with converted phonemes
                        result = []
                        for i, p in enumerate(phonemes):
                            result.append({
                                "start": p["start"],
                                "duration": p["duration"],
                                "phoneme": cmu_phonemes[i]
                            })
                        
                        return result
                except (AttributeError, TypeError) as e:
                    logging.warning(f"Timestamp parameter not supported: {str(e)}")
                
                # Fall back to basic recognition
                logging.warning("Falling back to basic Allosaurus recognition")
                try:
                    # Try with the specified parameters
                    phoneme_str = self.recognizer.recognize(audio_file, self.lang_id, self.emission)
                except TypeError:
                    # If that fails, try with just the audio file
                    phoneme_str = self.recognizer.recognize(audio_file)
                
                phonemes = phoneme_str.strip().split()
                
                # Convert IPA phonemes to CMU phonemes
                
                # Load the IPA to CMU mapping
                ipa_cmu_path = path_utils.get_file_inside_exe("ipa_cmu.json")
                with open(ipa_cmu_path, 'r', encoding='utf-8') as f:
                    ipa_cmu_dict = json.load(f)
                
                # Convert phonemes using the mapping
                cmu_phonemes = get_best_fitting_output_from_list(phonemes, ipa_cmu_dict)
                
                # Create timing information
                result = []
                if phonemes:
                    # Calculate time per phoneme
                    time_per_phoneme = audio_duration / len(phonemes)
                    
                    # Create result with timing information
                    for i, phoneme in enumerate(cmu_phonemes):
                        result.append({
                            "start": i * time_per_phoneme,
                            "duration": time_per_phoneme,
                            "phoneme": phoneme
                        })
                
                return result
            except Exception as e:
                logging.error(f"Error running Allosaurus: {str(e)}")
                logging.error(traceback.format_exc())
                return []
        except Exception as e:
            logging.error(f"Error predicting phonemes with Allosaurus: {str(e)}")
            logging.error(traceback.format_exc())
            return []

    def get_audio_duration(self, audio_file):
        try:
            audio_data, sample_rate = sf.read(audio_file)
            return len(audio_data) / float(sample_rate)
        except Exception as e:
            logging.error(f"Error reading audio file duration: {str(e)}")
            return None


class RhubarbRecognizer(BaseRecognizer):
    """Rhubarb recognizer for phoneme recognition"""
    __instance = None
    
    def __init__(self):
        """Initialize the Rhubarb recognizer"""
        super().__init__()
        self.rhubarb_path = self._find_rhubarb_binary()
        self.available = self.rhubarb_path is not None
    
    def is_available(self):
        """Check if Rhubarb is available"""
        return self.available
    
    def _find_rhubarb_binary(self):
        """Find the Rhubarb binary in the system"""
        
        system = platform.system()
        if system == "Windows":
            # Look for rhubarb.exe in the current directory and subdirectories
            for root, dirs, files in os.walk("."):
                if "rhubarb.exe" in files:
                    return os.path.abspath(os.path.join(root, "rhubarb.exe"))
        elif system == "Darwin" or system == "Linux":
            # Look for rhubarb in the current directory and subdirectories
            for root, dirs, files in os.walk("."):
                if "rhubarb" in files:
                    return os.path.abspath(os.path.join(root, "rhubarb"))
        
        # If not found, check if it's in the PATH
        rhubarb_in_path = shutil.which("rhubarb")
        if rhubarb_in_path:
            return rhubarb_in_path
        
        return None
    
    def predict(self, audio_file, model_type=None):
        """
        Predict phonemes using Rhubarb
        :param audio_file: Path to the audio file
        :param model_type: Not used for Rhubarb, included for interface consistency
        :return: List of phonemes
        """
        if not self.is_available():
            return []
        
        try:
            
            # Create a temporary file for the JSON output
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
                temp_json_path = temp_file.name
            
            # Run Rhubarb
            cmd = [
                self.rhubarb_path,
                "-o", temp_json_path,
                "--exportFormat", "json",
                "--extendedShapes", "GHX",
                audio_file
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logging.error(f"Rhubarb error: {stderr}")
                return []
            
            # Read the JSON output
            with open(temp_json_path, "r") as f:
                rhubarb_data = json.load(f)
            
            # Convert Rhubarb output to phoneme dictionaries
            phoneme_dicts = []
            for mouth_cue in rhubarb_data.get("mouthCues", []):
                phoneme_dicts.append({
                    "start": mouth_cue["start"],
                    "duration": mouth_cue["end"] - mouth_cue["start"],
                    "phoneme": mouth_cue["value"]
                })
            
            # Clean up the temporary file
            if os.path.exists(temp_json_path):
                os.unlink(temp_json_path)
            
            return phoneme_dicts
        except Exception as e:
            logging.error(f"Rhubarb prediction error: {str(e)}")
            logging.error(traceback.format_exc())
            return []


# Import needed for RecognizerFactory to work
import sys
