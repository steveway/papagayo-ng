"""
Voice Activity Detection (VAD) implementations.

This module contains the EnergyVAD class for detecting speech based on audio energy levels.
"""

import numpy as np


class EnergyVAD:
    """Energy-based Voice Activity Detection.
    
    Detects speech by analyzing the energy level of audio frames.
    """
    
    def __init__(self, energy_threshold=0.05, window_size=5):
        """Initialize EnergyVAD.
        
        Args:
            energy_threshold: Audio energy threshold for speech detection
            window_size: Number of frames for smoothing
        """
        self.energy_threshold = energy_threshold
        self.window_size = window_size
        self.energies = []
        
    def is_speech(self, audio_frame):
        """Determine if the audio frame contains speech.
        
        Args:
            audio_frame: Numpy array containing audio data
            
        Returns:
            bool: True if speech is detected, False otherwise
        """
        # Calculate energy (RMS)
        energy = np.sqrt(np.mean(audio_frame ** 2))
        
        # Add to sliding window
        self.energies.append(energy)
        if len(self.energies) > self.window_size:
            self.energies.pop(0)
        
        # Calculate average energy over window
        avg_energy = np.mean(self.energies)
        
        # Detect speech based on threshold
        return avg_energy > self.energy_threshold
