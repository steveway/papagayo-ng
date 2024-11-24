import os
import shutil
from pathlib import Path

def ensure_model_exists(model_path, model_type="phoneme", local_dir=None):
    """
    Ensures the model directory exists and has the correct structure.
    
    Args:
        model_path (str): Path to model directory or model identifier
        model_type (str): Type of model ("phoneme" or "emotion")
        local_dir (str): Local directory to store models. If None, uses default app data path.
    
    Returns:
        str: Path to the model directory
    """
    if local_dir is None:
        from utilities import get_app_data_path
        local_dir = os.path.join(get_app_data_path(), "onnx_models")
    
    # If model_path is just a name, construct full path
    if not os.path.isabs(model_path):
        model_dir = os.path.join(local_dir, model_type, Path(model_path).name)
    else:
        model_dir = model_path
    
    os.makedirs(model_dir, exist_ok=True)
    
    # Check if model exists
    if any(f.endswith('.onnx') for f in os.listdir(model_dir) if os.path.isfile(os.path.join(model_dir, f))):
        print(f"Model found in {model_dir}")
        return model_dir
    else:
        print(f"No ONNX model found in {model_dir}. Please add your model files to this directory:")
        print(f"Required files:")
        print(f" - model.onnx: The ONNX model file")
        print(f" - tokens.yaml: Token configuration file")
        print(f" - config.yaml: Model configuration file")
        raise FileNotFoundError(f"No ONNX model found in {model_dir}")
