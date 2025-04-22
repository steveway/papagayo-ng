import os
from pathlib import Path
import logging

class RecognizerFactory:
    """Factory class for creating recognizer instances"""
    
    @staticmethod
    def create_recognizer(recognizer_type, **kwargs):
        """
        Create a recognizer instance based on the recognizer type
        
        Args:
            recognizer_type (str): Type of recognizer to create ("onnx", "allosaurus", or "rhubarb")
            **kwargs: Additional arguments to pass to the recognizer constructor
            
        Returns:
            BaseRecognizer: An instance of the specified recognizer
            
        Raises:
            ValueError: If the recognizer type is not supported
            ImportError: If the required dependencies are not installed
        """
        recognizer_type = recognizer_type.lower()
        
        if recognizer_type == "onnx":
            from recognizer import ComboRecognizer
            
            # Get model paths from kwargs or use defaults
            phoneme_model_path = kwargs.get("phoneme_model_path", "")
            emotion_model_path = kwargs.get("emotion_model_path", "")
            
            try:
                return ComboRecognizer(
                    phoneme_model_path=phoneme_model_path,
                    emotion_model_path=emotion_model_path
                )
            except Exception as e:
                logging.error(f"Failed to create ONNX recognizer: {str(e)}")
                # If ONNX fails, try to fall back to Allosaurus if available
                try:
                    logging.info("Falling back to Allosaurus recognizer")
                    from recognizer import AllosaurusRecognizer
                    allosaurus_recognizer = AllosaurusRecognizer()
                    if hasattr(allosaurus_recognizer, "is_available") and allosaurus_recognizer.is_available():
                        return allosaurus_recognizer
                except Exception:
                    pass
                
                # If Allosaurus also fails, try Rhubarb
                try:
                    logging.info("Falling back to Rhubarb recognizer")
                    from recognizer import RhubarbRecognizer
                    rhubarb_recognizer = RhubarbRecognizer()
                    if hasattr(rhubarb_recognizer, "is_available") and rhubarb_recognizer.is_available():
                        return rhubarb_recognizer
                except Exception:
                    pass
                
                # If all fallbacks fail, return the original ONNX recognizer (which will report as not available)
                return ComboRecognizer(
                    phoneme_model_path=phoneme_model_path,
                    emotion_model_path=emotion_model_path
                )
            
        elif recognizer_type == "allosaurus":
            from recognizer import AllosaurusRecognizer
            return AllosaurusRecognizer()
            
        elif recognizer_type == "rhubarb":
            from recognizer import RhubarbRecognizer
            return RhubarbRecognizer()
            
        else:
            raise ValueError(f"Unsupported recognizer type: {recognizer_type}")
    
    @staticmethod
    def get_available_recognizers():
        """
        Get a list of available recognizer types on the current system
        
        Returns:
            list: List of available recognizer types
        """
        available_recognizers = []
        
        # Check for ONNX
        try:
            import onnxruntime
            available_recognizers.append("onnx")
        except ImportError:
            logging.info("ONNX runtime not available")
        
        # Check for Allosaurus
        try:
            import allosaurus
            available_recognizers.append("allosaurus")
        except ImportError:
            logging.info("Allosaurus not available")
        
        # Check for Rhubarb
        try:
            import utilities
            if utilities.rhubarb_binaries_exists():
                available_recognizers.append("rhubarb")
        except Exception:
            logging.info("Rhubarb not available")
        
        return available_recognizers
