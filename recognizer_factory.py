from base_recognizer import BaseRecognizer
from onnx_recognizer import OnnxRecognizer

class RecognizerFactory:
    @staticmethod
    def create_recognizer(recognizer_type, **kwargs):
        """Create a recognizer instance based on the specified type.
        
        Args:
            recognizer_type (str): Type of recognizer to create ("onnx", "allosaurus", or "rhubarb")
            **kwargs: Additional arguments to pass to the recognizer constructor
            
        Returns:
            BaseRecognizer: An instance of the specified recognizer type
        """
        if recognizer_type == "onnx":
            return OnnxRecognizer.get_instance(**kwargs)
        elif recognizer_type == "allosaurus":
            # TODO: Implement Allosaurus recognizer
            raise NotImplementedError("Allosaurus recognizer not implemented yet")
        elif recognizer_type == "rhubarb":
            # TODO: Implement Rhubarb recognizer
            raise NotImplementedError("Rhubarb recognizer not implemented yet")
        else:
            raise ValueError(f"Unknown recognizer type: {recognizer_type}")
