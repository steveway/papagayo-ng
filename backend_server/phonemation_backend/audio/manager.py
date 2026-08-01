"""
Audio device management module for Phonemation.

Handles audio device detection, selection, streaming, and voice activity detection.
"""

import threading
from queue import Queue
import logging

import numpy as np
from collections import deque
import sounddevice as sd
import soundfile as sf
import time

import soxr
from .vad import EnergyVAD
from .pysilero_vad import SileroVoiceActivityDetector


def resample_and_reshape_audio_data(data: np.ndarray, orig_sampling_rate, out_rate=16000):
    speech = soxr.resample(data, orig_sampling_rate, out_rate).squeeze()
    adjusted_speech = speech.reshape(1, -1)
    return adjusted_speech


def speech_file_to_array_fn_resize(path):
    speech_array, _sampling_rate = sf.read(path)
    return resample_and_reshape_audio_data(speech_array, orig_sampling_rate=_sampling_rate)


def get_default_device(device_type):
    if device_type == 'input':
        return sd.default.device['input']
    elif device_type == 'output':
        return sd.default.device['output']


def get_default_hostapi():
    return sd.default.hostapi


def get_device_name_from_id(device_id):
    return sd.query_devices(device_id)['name']


def get_hostapi_name_from_id(hostapi_id):
    return sd.query_hostapis(hostapi_id)['name']


class AudioDeviceManager:
    __instance = None

    @staticmethod
    def get_instance():
        if AudioDeviceManager.__instance is None:
            AudioDeviceManager()
        return AudioDeviceManager.__instance

    def __init__(self, vad_system='volume', volume_level_threshold=0.05):
        if AudioDeviceManager.__instance is not None:
            raise Exception("AudioDeviceManager: This class is a singleton!")
        else:
            AudioDeviceManager.__instance = self
        self.audio_buffer = Queue()
        self.vad = None
        self.use_vad = False
        self.use_volume_level = False
        self.vad_system = vad_system
        self.volume_level_threshold = volume_level_threshold
        self.change_vad_system(self.vad_system, self.volume_level_threshold)
        self.temp_output_audio = []
        self.pre_buffer_size = 1
        self.post_buffer_size = 3
        self.prev_buffer = deque(maxlen=self.pre_buffer_size)
        self.output_audio = Queue()
        self.devices = sd.query_devices()
        self.selected_input_device = None
        self.selected_output_device = None
        self.selected_hostapi = None
        self.stop_event = threading.Event()
        self.block_size = 32000
        self.current_volume_level = 0

        self.record_extra = self.post_buffer_size

    def get_default_device(self, device_type):
        """Get the default device for the specified type"""
        try:
            if device_type == 'input':
                default_device = sd.default.device[0]
            elif device_type == 'output':
                default_device = sd.default.device[1]
            else:
                return None

            if self.selected_hostapi is None and default_device is not None:
                device_info = sd.query_devices(default_device)
                self.selected_hostapi = device_info['hostapi']

            available_devices = self.get_available_audio_devices(device_type)
            
            if default_device is not None:
                default_device_info = sd.query_devices(default_device)
                for device in available_devices:
                    if (device['name'] == default_device_info['name'] and 
                        device['hostapi'] == self.selected_hostapi):
                        return device['index']
            
            if available_devices:
                return available_devices[0]['index']
            
            return None
            
        except Exception as e:
            print(f"Error getting default {device_type} device: {e}")
            return None

    def get_available_hostapis(self):
        return [hostapi['name'] for hostapi in sd.query_hostapis()]

    def change_vad_system(self, vad_system=None, vol_threshold=None):
        if vol_threshold is not None:
            self.volume_level_threshold = vol_threshold
        if vad_system is not None:
            self.vad_system = vad_system
            if self.vad_system == 'energy':
                self.vad = EnergyVAD()
                self.use_vad = True
                self.use_volume_level = False
            elif self.vad_system == 'silero':
                self.vad = SileroVoiceActivityDetector()
                self.use_vad = True
                self.use_volume_level = False
            elif self.vad_system == 'volume':
                self.vad = None
                self.use_vad = False
                self.use_volume_level = True

    def select_hostapi(self, hostapi_name):
        logging.debug(f"Available hostapis: {self.get_available_hostapis()}")
        logging.info(f"Selecting hostapi: {hostapi_name}")
        for index, hostapi in enumerate(sd.query_hostapis()):
            if hostapi['name'] == hostapi_name:
                self.selected_hostapi = index
                return True
        logging.warning(f"Hostapi '{hostapi_name}' not found")
        return False

    def get_available_audio_devices(self, device_type='input'):
        """Get list of available audio devices filtered by type and current hostapi"""
        available_devices = []
        try:
            for device in self.devices:
                if device_type == 'input':
                    if (device['max_input_channels'] > 0 and 
                        (self.selected_hostapi is None or device['hostapi'] == self.selected_hostapi)):
                        available_devices.append(device)
                elif device_type == 'output':
                    if (device['max_output_channels'] > 0 and 
                        (self.selected_hostapi is None or device['hostapi'] == self.selected_hostapi)):
                        available_devices.append(device)
        except Exception as e:
            logging.error(f"Error getting available {device_type} devices: {e}")
        
        return available_devices

    def select_audio_device(self, device_index, device_type='input'):
        """Select an audio device by index"""
        try:
            logging.info(f"Selecting {device_type} device with index: {device_index}")
            device_info = sd.query_devices(device_index)
            
            if device_info['hostapi'] != self.selected_hostapi:
                logging.warning(f"Device {device_index} belongs to different hostapi")
                return False
                
            if device_type == 'input' and device_info['max_input_channels'] > 0:
                self.selected_input_device = device_info
                logging.info(f"Selected input device: {device_info['name']}")
                return True
            elif device_type == 'output' and device_info['max_output_channels'] > 0:
                self.selected_output_device = device_info
                logging.info(f"Selected output device: {device_info['name']}")
                return True
                
            logging.warning(f"Device {device_index} is not suitable as {device_type} device")
            return False
            
        except Exception as e:
            logging.error(f"Error selecting {device_type} device: {e}")
            return False

    def get_device_id_from_name(self, device_name, device_type='input'):
        logging.debug(f"Looking up device ID for {device_type} device: {device_name}")
        for device in self.devices:
            if device['name'] == device_name and device['hostapi'] == self.selected_hostapi:
                if device_type == 'input' and device['max_input_channels'] > 0:
                    logging.debug(f"Found input device: {device}")
                    return device['index']
                elif device_type == 'output' and device['max_output_channels'] > 0:
                    logging.debug(f"Found output device: {device}")
                    return device['index']
        
        logging.warning(f"{device_type} device '{device_name}' not found")
        return None

    def playback_audio(self, outdata, frames, time, status):
        if status:
            logging.warning(f"Playback status: {status}")
            
        if not self.output_audio.empty():
            out_audio = self.output_audio.get()
            outdata[:] = out_audio

    def resample_and_playback(self, audio_data, delta_time=0):
        try:
            if self.selected_output_device:
                target_rate = int(self.selected_output_device['default_samplerate'])
                resampled = soxr.resample(audio_data, 
                                          int(self.selected_input_device['default_samplerate']), 
                                          target_rate)
                self.output_audio.put(resampled.reshape(-1, 1))
        except Exception as e:
            logging.error(f"Error in resample_and_playback: {e}")

    def record_audio(self, indata, frames, time, status):
        if status:
            logging.warning(f"Recording status: {status}")
        
        if self.use_volume_level:
            audio_data = indata.copy()
            volume_norm = self.rms_flat(audio_data)
            self.current_volume_level = volume_norm
            
            if volume_norm > self.volume_level_threshold:
                if not self.temp_output_audio and self.record_extra == self.post_buffer_size:
                    if self.prev_buffer:
                        self.temp_output_audio = list(self.prev_buffer)[-self.pre_buffer_size:]
                        self.prev_buffer.clear()
                self.temp_output_audio.append(indata.copy())
            else:
                if self.record_extra > 0 and self.temp_output_audio:
                    self.temp_output_audio.append(indata.copy())
                    self.record_extra -= 1
                elif self.temp_output_audio and self.record_extra <= 0:
                    connected_audio = np.concatenate(self.temp_output_audio)
                    self.audio_buffer.put(connected_audio)
                    self.temp_output_audio = []
                    self.record_extra = self.post_buffer_size
                else:
                    self.prev_buffer.append(indata.copy())
        elif self.use_vad:
            if hasattr(self.vad, 'is_speech') and callable(self.vad.is_speech):
                speech_detected = self.vad.is_speech(indata)
                if speech_detected and not self.temp_output_audio:
                    if self.prev_buffer:
                        self.temp_output_audio = list(self.prev_buffer)[-self.pre_buffer_size:]
                        self.prev_buffer.clear()
                    self.temp_output_audio.append(indata.copy())
                elif speech_detected:
                    self.temp_output_audio.append(indata.copy())
                    self.record_extra = self.post_buffer_size
                elif not speech_detected and self.temp_output_audio:
                    if self.record_extra > 0:
                        self.temp_output_audio.append(indata.copy())
                        self.record_extra -= 1
                    else:
                        connected_audio = np.concatenate(self.temp_output_audio)
                        self.audio_buffer.put(connected_audio)
                        self.temp_output_audio = []
                        self.record_extra = self.post_buffer_size
                else:
                    self.prev_buffer.append(indata.copy())
            else:
                self.audio_buffer.put(indata.copy())
        else:
            self.audio_buffer.put(indata.copy())

    def speech_data_to_array_fn(self, data):
        return resample_and_reshape_audio_data(data,
                                               orig_sampling_rate=self.selected_input_device[
                                                   'default_samplerate'])

    def rms_flat(self, a):
        rms = np.sqrt(np.mean(a ** 2))
        return rms

    def start_stream(self, callback, device_type='input', duration=0.01):
        selected_device = self.selected_input_device if device_type == 'input' else self.selected_output_device
        if not selected_device:
            logging.error("No device selected for streaming")
            self.stop_event.set()
            return False

        self.block_size = int(selected_device['default_samplerate']) // 10
        try:
            if device_type == 'input':
                with sd.InputStream(device=selected_device['index'],
                                    channels=1, callback=callback,
                                    samplerate=int(selected_device['default_samplerate']),
                                    blocksize=self.block_size) as stream:
                    while True:
                        time.sleep(duration)
                        if self.stop_event.is_set():
                            logging.info(f"Stopping {device_type} stream")
                            break
            elif device_type == 'output':
                with sd.OutputStream(device=selected_device['index'],
                                     channels=1, callback=callback,
                                     samplerate=int(selected_device['default_samplerate']),
                                     blocksize=self.block_size) as stream:
                    while True:
                        time.sleep(duration)
                        if self.stop_event.is_set():
                            logging.info(f"Stopping {device_type} stream")
                            break
            else:
                with sd.Stream(device=(self.selected_input_device['index'],
                                       self.selected_output_device['index']),
                               callback=callback, samplerate=int(selected_device['default_samplerate']),
                               blocksize=self.block_size) as stream:
                    while True:
                        time.sleep(duration)
                        if self.stop_event.is_set():
                            logging.info(f"Stopping {device_type} stream")
                            break
        except sd.PortAudioError as e:
            logging.error(f"PortAudio error while streaming: {str(e)}")
            self.stop_event.set()
            return False
        logging.info("Stream stopped successfully")
        return True
