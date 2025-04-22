import os
import logging
import json
import tempfile
import soundfile as sf
from pathlib import Path

import PySide6.QtCore as QtCore
import utilities
from ai_output_process import get_best_fitting_output_from_list
from recognizer_factory import RecognizerFactory
import subprocess

import string
import time
import pydub
from pydub.generators import WhiteNoise
from PySide6 import QtWidgets

if utilities.get_app_data_path() not in os.environ['PATH']:
    os.environ['PATH'] += os.pathsep + utilities.get_app_data_path()

if utilities.main_is_frozen():
    subprocess.STARTUPINFO().dwFlags |= subprocess.STARTF_USESHOWWINDOW


class AutoRecognize:
    def __init__(self, sound_path):
        ini_path = os.path.join(utilities.get_app_data_path(), "settings.ini")
        self.settings = QtCore.QSettings(ini_path, QtCore.QSettings.Format.IniFormat)
        self.settings.setFallbacksEnabled(False)  # File only, not registry or or.
        
        # Get the selected recognizer type from settings
        self.recognizer_type = self.settings.value("/VoiceRecognition/recognizer", "Allosaurus").lower()
        
        # Paths and temporary files
        self.temp_wave_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        
        # Performance metrics
        self.duration_for_one_second = 1
        
        # GUI references
        try:
            app = QtWidgets.QApplication.instance()
            self.main_window = None
            self.threadpool = QtCore.QThreadPool.globalInstance()
            for widget in app.topLevelWidgets():
                if isinstance(widget, QtWidgets.QMainWindow):
                    self.main_window = widget
        except AttributeError:
            self.main_window = None
            
        # Audio properties
        self.sound_length = 0
        self.analysis_finished = False
        
        # Initialize and test the recognizer
        self.test_decode_time()
        self.convert_to_wav(sound_path)

    def test_decode_time(self):
        """Test the recognition speed to estimate progress"""
        # Create a 5-second test sample
        five_second_sample = WhiteNoise().to_audio_segment(duration=5000)
        five_second_sample = five_second_sample.set_sample_width(2)
        five_second_sample = five_second_sample.set_frame_rate(16000)
        five_second_sample = five_second_sample.set_channels(1)
        five_second_sample_temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        out_ = five_second_sample.export(five_second_sample_temp_file, format="wav", bitrate="256k")
        out_.close()
        
        # Create the appropriate recognizer based on settings
        try:
            # Create a recognizer based on the selected type
            recognizer = RecognizerFactory.create_recognizer(self.recognizer_type)
            
            # Time the recognition process
            start_time = time.process_time()
            
            if self.recognizer_type == "allosaurus":
                # For Allosaurus, we need to pass specific parameters
                lang_id = self.settings.value("/VoiceRecognition/allo_lang_id", "eng")
                emission = float(str(self.settings.value("/VoiceRecognition/allo_emission", 1.0)))
                recognizer.predict(five_second_sample_temp_file, lang_id=lang_id, emit=emission)
            else:
                # For other recognizers, just call predict
                recognizer.predict(five_second_sample_temp_file)
                
            self.duration_for_one_second = (time.process_time() - start_time) / 5
            
        except Exception as e:
            logging.error(f"Error testing recognizer: {str(e)}")
            self.duration_for_one_second = 1  # Default fallback
            
        finally:
            # Clean up
            os.remove(five_second_sample_temp_file)

    def convert_to_wav(self, sound_path):
        """Convert the input audio to a WAV file with consistent format"""
        try:
            pydubfile = pydub.AudioSegment.from_file(sound_path, format=os.path.splitext(sound_path)[1][1:])
            pydubfile = pydubfile.set_sample_width(2)
            pydubfile = pydubfile.set_frame_rate(16000)
            pydubfile = pydubfile.set_channels(1)
            half_second_silence = pydub.AudioSegment.silent(500)
            self.sound_length = pydubfile.duration_seconds
            pydubfile += half_second_silence
            out_ = pydubfile.export(self.temp_wave_file, format="wav", bitrate="256k")
            out_.close()
        except Exception as e:
            logging.error(f"Error converting audio: {str(e)}")
            raise

    def update_progress(self, progress_callback):
        """Update the progress bar during recognition"""
        expected_time_to_finish = self.sound_length * self.duration_for_one_second
        start_time = time.process_time()
        finish_time = start_time + expected_time_to_finish
        progress_multiplier = 100.0 / expected_time_to_finish
        
        while time.process_time() < finish_time:
            if self.analysis_finished:
                break
            QtCore.QCoreApplication.processEvents()
            current_progress = (time.process_time() - start_time) * progress_multiplier
            progress_callback(current_progress)
            
        if self.main_window and hasattr(self.main_window, 'lip_sync_frame') and hasattr(self.main_window.lip_sync_frame, 'status_progress'):
            self.main_window.lip_sync_frame.status_progress.hide()

    def recognize(self, audio_file, language="eng", progress_callback=None):
        """
        Run speech recognition on an audio file
        :param audio_file: Path to the audio file
        :param language: Language code (for Allosaurus)
        :param progress_callback: Callback function for progress updates
        :return: Tuple of (phonemes, peaks)
        """
        try:
            # If using ONNX, verify and repair the model if needed
            if self.recognizer_type == "onnx":
                from model_manager import ModelHandler
                import utilities
                
                # Initialize the model handler
                model_handler = ModelHandler.get_instance()
                model_handler.cache_models()
                
                # Get the app data path for model storage
                app_data_path = utilities.get_app_data_path()
                
                # Choose a model from the available models
                model_type = "phoneme"
                model_list = model_handler.get_model_list(model_type)
                if model_list:
                    # Use the first available model
                    model_id = model_list[0]
                    
                    # Check if the model is available locally, download if not
                    if not model_handler.model_is_available_locally(model_id, app_data_path, model_type):
                        logging.info(f"Model {model_id} not found locally, downloading...")
                        # Skip large files to avoid long downloads
                        model_handler.download_model(model_id, app_data_path, skip_large_files=True, max_file_size_mb=100)
                    
                    # Get the model path
                    model_path = model_handler.get_model_path(model_id, app_data_path, model_type)
                    
                    # Verify that the model is valid
                    if not model_handler.verify_model(model_path):
                        logging.warning(f"Model {model_id} is invalid, attempting to repair...")
                        # Skip large files during repair to avoid long downloads
                        if model_handler.download_model(model_id, app_data_path, force_redownload=True, skip_large_files=True, max_file_size_mb=100):
                            logging.info(f"Model {model_id} repaired successfully")
                        else:
                            logging.error(f"Failed to repair model {model_id}")
            
            # Create the recognizer
            recognizer = RecognizerFactory.create_recognizer(self.recognizer_type)
            
            # Check if the recognizer is available
            if not recognizer.is_available():
                error_message = f"The selected recognizer '{self.recognizer_type}' is not available on this system."
                logging.error(error_message)
                
                # Try to find an available recognizer as fallback
                available_recognizers = RecognizerFactory.get_available_recognizers()
                if available_recognizers:
                    fallback_type = available_recognizers[0]
                    logging.info(f"Falling back to '{fallback_type}' recognizer")
                    recognizer = RecognizerFactory.create_recognizer(fallback_type)
                    self.recognizer_type = fallback_type
                else:
                    raise RuntimeError(error_message)
            
            # Set language for Allosaurus
            if self.recognizer_type == "allosaurus" and hasattr(recognizer, "set_language"):
                recognizer.set_language(language)
            
            # Run recognition
            logging.info(f"Running {self.recognizer_type} recognizer on {audio_file}")
            if progress_callback:
                recognizer.set_progress_callback(progress_callback)
            
            # Get phonemes
            phonemes = recognizer.predict(audio_file, "phoneme")
            
            # Check if we got valid phonemes
            if not phonemes or len(phonemes) == 0:
                logging.warning(f"No phonemes returned from {self.recognizer_type} recognizer")
                return [], []
            
            # Process phonemes if they're in dictionary format
            if isinstance(phonemes, list) and len(phonemes) > 0 and isinstance(phonemes[0], dict) and "phoneme" in phonemes[0]:
                # For ONNX and Allosaurus, we have dictionaries with timing information
                processed_phonemes = []
                for p in phonemes:
                    # Extract just the phoneme text
                    processed_phonemes.append(p["phoneme"])
                phonemes = processed_phonemes
            
            # Convert phonemes to CMU format if needed
            if self.recognizer_type.lower() in ["onnx", "allosaurus"]:
                try:
                    # Load IPA to CMU conversion dictionary
                    ipa_convert = json.load(open("ipa_cmu.json", encoding="utf8"))
                    
                    # Check if conversion is needed (if phonemes are not already in uppercase CMU format)
                    if not any(not isinstance(p, str) or p.isupper() for p in phonemes):
                        phonemes = get_best_fitting_output_from_list(phonemes, ipa_convert)
                        logging.info(f"Converted phonemes to CMU format: {phonemes[:5]}...")
                except Exception as e:
                    logging.error(f"Error converting phonemes to CMU format: {str(e)}")
            
            # Get peaks for word boundaries
            if hasattr(recognizer, "get_peaks"):
                peaks = recognizer.get_peaks(audio_file)
            else:
                # Default peaks at start and end
                audio_data, sample_rate = sf.read(audio_file)
                duration = len(audio_data) / sample_rate
                peaks = [0, duration]
            
            return phonemes, peaks
        
        except Exception as e:
            logging.error(f"Error in auto recognition: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return [], []

    def recognize_allosaurus(self):
        """Legacy method for backward compatibility"""
        return self.recognize(self.temp_wave_file)

    def get_level_peaks(self, v):
        """Find peaks in the audio level data for visualization"""
        peaks = [0]

        i = 1
        while i < len(v) - 1:
            pos_left = i
            pos_right = i

            while v[pos_left] == v[i] and pos_left > 0:
                pos_left -= 1

            while v[pos_right] == v[i] and pos_right < len(v) - 1:
                pos_right += 1

            # is_lower_peak = v[pos_left] > v[i] and v[i] < v[pos_right]
            is_upper_peak = v[pos_left] < v[i] and v[i] > v[pos_right]

            if is_upper_peak:
                peaks.append(i)

            i = pos_right

        peaks.append(len(v) - 1)
        return peaks

    def __del__(self):
        """Clean up temporary files"""
        try:
            if hasattr(self, 'temp_wave_file') and os.path.exists(self.temp_wave_file):
                os.remove(self.temp_wave_file)
        except Exception as e:
            logging.error(f"Error cleaning up: {str(e)}")
