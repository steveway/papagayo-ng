import logging

class RecognizerFactory:
    """Factory class for creating recognizer instances.

    The ONNX wav2vec2 models are now loaded and run by the
    phonemation_backend server (managed as a subprocess by
    BackendRecognizer).  Allosaurus and Rhubarb fallbacks have been
    removed in favour of a single clean ONNX backend.
    """

    @staticmethod
    def create_recognizer(recognizer_type, **kwargs):
        """
        Create a recognizer instance based on the recognizer type.

        Args:
            recognizer_type (str): Type of recognizer to create ("onnx" or "backend")
            **kwargs: Additional arguments to pass to the recognizer constructor

        Returns:
            BackendRecognizer: An instance of the backend-based recognizer

        Raises:
            ValueError: If the recognizer type is not supported
        """
        recognizer_type = recognizer_type.lower()

        if recognizer_type in ("onnx", "backend"):
            from backend_recognizer import BackendRecognizer

            phoneme_model_path = kwargs.get("phoneme_model_path", "")
            emotion_model_path = kwargs.get("emotion_model_path", "")

            try:
                return BackendRecognizer(
                    phoneme_model_path=phoneme_model_path,
                    emotion_model_path=emotion_model_path,
                )
            except Exception as e:
                logging.error(f"Failed to create backend recognizer: {str(e)}")
                raise

        else:
            raise ValueError(
                f"Unsupported recognizer type: {recognizer_type}. "
                f"Only 'onnx' (backend subprocess) is supported."
            )

    @staticmethod
    def get_available_recognizers():
        """
        Get a list of available recognizer types on the current system.

        Returns:
            list: List of available recognizer types
        """
        available_recognizers = []

        # The backend needs onnxruntime and the server dependencies.
        try:
            import onnxruntime
            available_recognizers.append("onnx")
        except ImportError:
            logging.info("ONNX runtime not available")

        return available_recognizers
