#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test script for the new recognizer system
"""

import os
import logging
import sys
from pathlib import Path
from recognizer_factory import RecognizerFactory
from model_manager import ModelHandler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_available_recognizers():
    """Test which recognizers are available on the system"""
    available = RecognizerFactory.get_available_recognizers()
    logger.info(f"Available recognizers: {available}")
    return available

def test_onnx_recognizer(skip_large_files=True, max_file_size_mb=100):
    """
    Test the ONNX recognizer
    
    Args:
        skip_large_files: Whether to skip large files during download
        max_file_size_mb: Maximum file size in MB to download if skip_large_files is True
    """
    try:
        # Initialize the model handler
        model_handler = ModelHandler.get_instance()
        model_handler.cache_models()
        
        # Get the app data path for model storage
        import utilities
        app_data_path = utilities.get_app_data_path()
        
        # Choose a model from the available models
        model_type = "phoneme"
        model_list = model_handler.get_model_list(model_type)
        if not model_list:
            logger.error("No ONNX models available")
            return False
        
        # Use the first available model
        model_id = model_list[0]
        logger.info(f"Using model: {model_id}")
        
        # Check if the model is available locally, download if not
        if not model_handler.model_is_available_locally(model_id, app_data_path, model_type):
            logger.info(f"Model {model_id} not found locally, downloading...")
            model_handler.download_model(model_id, app_data_path, skip_large_files=skip_large_files, max_file_size_mb=max_file_size_mb)
        
        # Get the model path
        model_path = model_handler.get_model_path(model_id, app_data_path, model_type)
        logger.info(f"Model path: {model_path}")
        
        # Verify that the model is valid
        if not model_handler.verify_model(model_path):
            logger.warning(f"Model {model_id} is invalid, attempting to repair...")
            if model_handler.repair_model(model_id, app_data_path):
                logger.info(f"Model {model_id} repaired successfully")
            else:
                # If repair fails and we didn't skip large files before, try with skipping
                if not skip_large_files:
                    logger.info(f"Trying again with skip_large_files=True...")
                    if model_handler.download_model(model_id, app_data_path, force_redownload=True, skip_large_files=True, max_file_size_mb=max_file_size_mb):
                        logger.info(f"Model {model_id} downloaded successfully with large files skipped")
                    else:
                        logger.error(f"Failed to repair model {model_id}")
                        return False
                else:
                    logger.error(f"Failed to repair model {model_id}")
                    return False
        
        # Create an ONNX recognizer with the model path
        recognizer = RecognizerFactory.create_recognizer("onnx", phoneme_model_path=model_path)
        logger.info(f"ONNX recognizer created: {recognizer}")
        logger.info(f"ONNX recognizer available: {recognizer.is_available()}")
        
        return recognizer.is_available()
    except Exception as e:
        logger.error(f"Error creating ONNX recognizer: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_allosaurus_recognizer():
    """Test the Allosaurus recognizer"""
    try:
        # Create an Allosaurus recognizer
        recognizer = RecognizerFactory.create_recognizer("allosaurus")
        logger.info(f"Allosaurus recognizer created: {recognizer}")
        logger.info(f"Allosaurus recognizer available: {recognizer.is_available()}")
        return recognizer.is_available()
    except Exception as e:
        logger.error(f"Error creating Allosaurus recognizer: {str(e)}")
        return False

def test_rhubarb_recognizer():
    """Test the Rhubarb recognizer"""
    try:
        # Create a Rhubarb recognizer
        recognizer = RecognizerFactory.create_recognizer("rhubarb")
        logger.info(f"Rhubarb recognizer created: {recognizer}")
        logger.info(f"Rhubarb recognizer available: {recognizer.is_available()}")
        return recognizer.is_available()
    except Exception as e:
        logger.error(f"Error creating Rhubarb recognizer: {str(e)}")
        return False

def test_recognizer_with_audio(recognizer_type, audio_file):
    """Test a recognizer with an actual audio file"""
    try:
        # Create the recognizer
        if recognizer_type == "onnx":
            # Initialize the model handler
            model_handler = ModelHandler.get_instance()
            model_handler.cache_models()
            
            # Get the app data path for model storage
            import utilities
            app_data_path = utilities.get_app_data_path()
            
            # Choose a model from the available models
            model_type = "phoneme"
            model_list = model_handler.get_model_list(model_type)
            if not model_list:
                logger.error("No ONNX models available")
                return False
            
            # Use the first available model
            model_id = model_list[0]
            model_path = model_handler.get_model_path(model_id, app_data_path, model_type)
            
            # Create an ONNX recognizer with the model path
            recognizer = RecognizerFactory.create_recognizer("onnx", phoneme_model_path=model_path)
        else:
            recognizer = RecognizerFactory.create_recognizer(recognizer_type)
        
        if not recognizer.is_available():
            logger.error(f"Recognizer {recognizer_type} is not available")
            return False
        
        # Run recognition on the audio file
        logger.info(f"Running {recognizer_type} recognizer on {audio_file}")
        
        # Different recognizers have different predict method signatures
        if recognizer_type == "onnx":
            result = recognizer.predict(audio_file, "phoneme")
        elif recognizer_type == "allosaurus":
            # For Allosaurus, we need to use the correct parameters
            result = recognizer.predict(audio_file)
        elif recognizer_type == "rhubarb":
            # For Rhubarb, we just pass the audio file
            result = recognizer.predict(audio_file)
        
        # Check result
        if result:
            logger.info(f"Recognition result: {result[:10]}... (showing first 10 items)")
            return True
        else:
            logger.error(f"No recognition result from {recognizer_type}")
            return False
    except Exception as e:
        logger.error(f"Error testing {recognizer_type} recognizer with audio: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("Testing recognizer system...")
    
    # Test available recognizers
    available_recognizers = test_available_recognizers()
    
    # Test each available recognizer
    onnx_available = False
    allosaurus_available = False
    rhubarb_available = False
    
    if "onnx" in available_recognizers:
        onnx_available = test_onnx_recognizer()
    
    if "allosaurus" in available_recognizers:
        allosaurus_available = test_allosaurus_recognizer()
    
    if "rhubarb" in available_recognizers:
        rhubarb_available = test_rhubarb_recognizer()
    
    # Test with audio file if provided
    audio_file = "Tutorial Files/lame.wav"
    if os.path.exists(audio_file):
        logger.info(f"Found audio file: {audio_file}")
        
        # Test each available recognizer with the audio file
        if allosaurus_available:
            test_recognizer_with_audio("allosaurus", audio_file)
        
        if rhubarb_available:
            test_recognizer_with_audio("rhubarb", audio_file)
        
        # Don't test ONNX if it's not available
        if onnx_available:
            test_recognizer_with_audio("onnx", audio_file)
    else:
        logger.warning(f"Audio file not found: {audio_file}")
    
    logger.info("Testing complete!")
