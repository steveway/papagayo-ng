"""
Silero Voice Activity Detection (VAD) wrapper for Phonemation.

Provides a Python interface to the Silero VAD model for high-quality speech detection.
"""

import numpy as np
import logging

# Optional imports to avoid breaking if torch is not installed
try:
    import torch
    torch_available = True
except ImportError:
    torch_available = False
    logging.warning("PyTorch not available - Silero VAD will not function")


class SileroVoiceActivityDetector:
    """Wrapper for the Silero Voice Activity Detection model.
    
    Detects speech in audio frames using the Silero VAD pre-trained model.
    """
    
    def __init__(self, threshold=0.5, sampling_rate=16000):
        """Initialize the Silero VAD detector.
        
        Args:
            threshold: Confidence threshold for speech detection (0.0-1.0)
            sampling_rate: Audio sampling rate, must match input audio
        """
        self.threshold = threshold
        self.sampling_rate = sampling_rate
        self.model = None
        
        if not torch_available:
            logging.error("Cannot initialize Silero VAD: PyTorch not available")
            return
            
        try:
            self._load_model()
        except Exception as e:
            logging.error(f"Failed to load Silero VAD model: {e}")
    
    def _load_model(self):
        """Load the Silero VAD model."""
        if not torch_available:
            return
            
        try:
            from torch.hub import load as torch_hub_load
            
            self.model = torch_hub_load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False
            )
            
            # Get the VAD model
            (self.get_speech_ts, 
             self.get_speech_probs) = self.model
             
            logging.info("Silero VAD model loaded successfully")
        except Exception as e:
            logging.error(f"Error loading Silero VAD: {e}")
            self.model = None
    
    def is_speech(self, audio_frame):
        """Determine if the audio frame contains speech.
        
        Args:
            audio_frame: Numpy array containing audio data
            
        Returns:
            bool: True if speech is detected, False otherwise
        """
        if not torch_available or self.model is None:
            # Fallback to simple energy detection
            energy = np.sqrt(np.mean(audio_frame ** 2))
            return energy > 0.05
        
        try:
            # Convert numpy to torch tensor
            audio_tensor = torch.from_numpy(audio_frame.reshape(-1)).float()
            
            # Get speech probabilities
            with torch.no_grad():
                speech_probs = self.get_speech_probs(
                    audio_tensor, 
                    self.sampling_rate
                )
                
            # Check if speech probability exceeds threshold
            if speech_probs[-1] > self.threshold:
                return True
                
            return False
        except Exception as e:
            logging.error(f"Error in Silero VAD inference: {e}")
            # Fallback to simple energy detection
            energy = np.sqrt(np.mean(audio_frame ** 2))
            return energy > 0.05
