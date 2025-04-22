#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-

# Papagayo-NG, a lip-sync tool for use with several different animation suites
# Copyright (C) 2005 Mike Clifton
# Contact information at http://www.lostmarble.com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

import os
from pathlib import Path
from PySide6 import QtCore
import utilities


class SettingsManager:
    """
    Centralized settings manager for Papagayo-NG.
    Implements the singleton pattern to ensure only one instance exists.
    """
    _instance = None
    
    # Define settings keys as constants to avoid typos and ensure consistency
    class Keys:
        # General settings
        LAST_FPS = "LastFPS"
        MOUTH_DIR = "MouthDir"
        AUDIO_OUTPUT = "audio_output"
        QSS_FILE_PATH = "qss_file_path"
        LANGUAGE = "language"
        
        # Voice recognition settings
        class VoiceRecognition:
            PREFIX = "/VoiceRecognition"
            RECOGNIZER = f"{PREFIX}/recognizer"
            RUN_VOICE_RECOGNITION = f"{PREFIX}/run_voice_recognition"
            ALLO_LANG_ID = f"{PREFIX}/allo_lang_id"
            ALLO_EMISSION = f"{PREFIX}/allo_emission"
            ALLOSAURUS_MODEL = f"{PREFIX}/allosaurus_model"
            ONNX_MODEL = f"{PREFIX}/onnx_model"
            ONNX_EMOTION_MODEL = f"{PREFIX}/onnx_emotion_model"
            DISTRIBUTION_MODE = f"{PREFIX}/distribution_mode"
        
        # Graphics settings
        class Graphics:
            PREFIX = "/Graphics"
            
            @staticmethod
            def color_key(name):
                return f"{SettingsManager.Keys.Graphics.PREFIX}/{name}"
        
        # Behavior settings
        REST_AFTER_WORDS = "rest_after_words"
        REST_AFTER_PHONEMES = "rest_after_phonemes"
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance of SettingsManager."""
        if cls._instance is None:
            cls._instance = SettingsManager()
        return cls._instance
    
    def __init__(self):
        """Initialize the settings manager."""
        if SettingsManager._instance is not None:
            raise RuntimeError("Use SettingsManager.get_instance() instead of constructor")
        
        ini_path = Path(utilities.get_app_data_path()) / "settings.ini"
        self._settings = QtCore.QSettings(str(ini_path), QtCore.QSettings.Format.IniFormat)
        SettingsManager._instance = self
    
    def get(self, key, default_value=None):
        """
        Get a setting value.
        
        Args:
            key: The settings key to retrieve.
            default_value: The default value to return if the key doesn't exist.
            
        Returns:
            The setting value or the default value if not found.
        """
        return self._settings.value(key, default_value)
    
    def get_int(self, key, default_value=0):
        """Get a setting value as an integer."""
        value = self.get(key, default_value)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default_value
    
    def get_float(self, key, default_value=0.0):
        """Get a setting value as a float."""
        value = self.get(key, default_value)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default_value
    
    def get_bool(self, key, default_value=False):
        """Get a setting value as a boolean."""
        value = self.get(key, default_value)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)
    
    def set(self, key, value):
        """
        Set a setting value.
        
        Args:
            key: The settings key to set.
            value: The value to set.
        """
        self._settings.setValue(key, value)
    
    def get_fps(self):
        """Get the frames per second setting."""
        return self.get_int(self.Keys.LAST_FPS, 24)
    
    def set_fps(self, fps):
        """Set the frames per second setting."""
        self.set(self.Keys.LAST_FPS, fps)
    
    def get_mouth_dir(self):
        """Get the mouth directory setting."""
        return self.get(self.Keys.MOUTH_DIR, "")
    
    def set_mouth_dir(self, directory):
        """Set the mouth directory setting."""
        self.set(self.Keys.MOUTH_DIR, directory)
    
    def get_audio_output(self):
        """Get the audio output setting."""
        return self.get(self.Keys.AUDIO_OUTPUT, "new")
    
    def set_audio_output(self, output):
        """Set the audio output setting."""
        self.set(self.Keys.AUDIO_OUTPUT, output)
    
    def get_recognizer(self):
        """Get the voice recognizer setting."""
        return self.get(self.Keys.VoiceRecognition.RECOGNIZER, "Allosaurus")
    
    def set_recognizer(self, recognizer):
        """Set the voice recognizer setting."""
        self.set(self.Keys.VoiceRecognition.RECOGNIZER, recognizer)
    
    def get_run_voice_recognition(self):
        """Get whether to run voice recognition."""
        return self.get_bool(self.Keys.VoiceRecognition.RUN_VOICE_RECOGNITION, True)
    
    def set_run_voice_recognition(self, run):
        """Set whether to run voice recognition."""
        self.set(self.Keys.VoiceRecognition.RUN_VOICE_RECOGNITION, run)
    
    def get_voice_recognition(self):
        """Get the run voice recognition setting as a string."""
        return str(self.get_bool(self.Keys.VoiceRecognition.RUN_VOICE_RECOGNITION, True))
    
    def get_allo_lang_id(self):
        """Get the Allosaurus language ID setting."""
        return self.get(self.Keys.VoiceRecognition.ALLO_LANG_ID, "eng")
    
    def set_allo_lang_id(self, lang_id):
        """Set the Allosaurus language ID setting."""
        self.set(self.Keys.VoiceRecognition.ALLO_LANG_ID, lang_id)
    
    def get_allo_emission(self):
        """Get the Allosaurus emission setting."""
        return self.get_float(self.Keys.VoiceRecognition.ALLO_EMISSION, 1.0)
    
    def set_allo_emission(self, emission):
        """Set the Allosaurus emission setting."""
        self.set(self.Keys.VoiceRecognition.ALLO_EMISSION, emission)
    
    def get_allosaurus_model(self):
        """Get the Allosaurus model setting."""
        return self.get(self.Keys.VoiceRecognition.ALLOSAURUS_MODEL, "latest")
    
    def set_allosaurus_model(self, model):
        """Set the Allosaurus model setting."""
        self.set(self.Keys.VoiceRecognition.ALLOSAURUS_MODEL, model)
    
    def get_onnx_model(self):
        """Get the ONNX model setting."""
        return self.get(self.Keys.VoiceRecognition.ONNX_MODEL, "")
    
    def set_onnx_model(self, model):
        """Set the ONNX model setting."""
        self.set(self.Keys.VoiceRecognition.ONNX_MODEL, model)
    
    def get_onnx_emotion_model(self):
        """Get the ONNX emotion model setting."""
        return self.get(self.Keys.VoiceRecognition.ONNX_EMOTION_MODEL, "steveway/wav2emotion")
    
    def set_onnx_emotion_model(self, model):
        """Set the ONNX emotion model setting."""
        self.set(self.Keys.VoiceRecognition.ONNX_EMOTION_MODEL, model)
    
    def get_distribution_mode(self):
        """Get the distribution mode setting."""
        return self.get(self.Keys.VoiceRecognition.DISTRIBUTION_MODE, "peaks")
    
    def set_distribution_mode(self, mode):
        """Set the distribution mode setting."""
        self.set(self.Keys.VoiceRecognition.DISTRIBUTION_MODE, mode)
    
    def get_qss_file_path(self):
        """Get the QSS file path setting."""
        return self.get(self.Keys.QSS_FILE_PATH, "")
    
    def set_qss_file_path(self, path):
        """Set the QSS file path setting."""
        self.set(self.Keys.QSS_FILE_PATH, path)
    
    def get_language(self):
        """Get the UI language setting."""
        return self.get(self.Keys.LANGUAGE, "en_us")
    
    def set_language(self, language):
        """Set the UI language setting."""
        self.set(self.Keys.LANGUAGE, language)
    
    def get_rest_after_words(self):
        """Get whether to rest after words."""
        return self.get_bool(self.Keys.REST_AFTER_WORDS, True)
    
    def set_rest_after_words(self, rest):
        """Set whether to rest after words."""
        self.set(self.Keys.REST_AFTER_WORDS, rest)
    
    def get_rest_after_phonemes(self):
        """Get whether to rest after phonemes."""
        return self.get_bool(self.Keys.REST_AFTER_PHONEMES, True)
    
    def set_rest_after_phonemes(self, rest):
        """Set whether to rest after phonemes."""
        self.set(self.Keys.REST_AFTER_PHONEMES, rest)
    
    def get_color(self, name, default_color=None):
        """
        Get a color setting.
        
        Args:
            name: The color name.
            default_color: The default color to return if not found.
            
        Returns:
            The color value as a string.
        """
        if default_color is None and name in utilities.original_colors:
            default_color = utilities.original_colors[name].name()
        return self.get(self.Keys.Graphics.color_key(name), default_color)
    
    def set_color(self, name, color):
        """
        Set a color setting.
        
        Args:
            name: The color name.
            color: The color value to set.
        """
        self.set(self.Keys.Graphics.color_key(name), color)
    
    def reset_colors(self):
        """Reset all color settings to their default values."""
        for color_name, color_value in utilities.original_colors.items():
            self.set_color(color_name, color_value.name())
            
    def clear_settings(self):
        """Clear all settings."""
        self._settings.clear()
