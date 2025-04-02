"""
Utility module for handling file paths in different execution contexts (development, packed exe, etc.)
"""

import os
import sys
from pathlib import Path
from appdirs import user_data_dir, user_config_dir

# Application metadata
APP_NAME = "PapagayoNG"
APP_AUTHOR = "Morevna Project"

def get_file_inside_exe(file_name: str) -> str:
    """
    Get path to a file that is packed inside the exe.
    Used for files that are part of the application (like .ui files).
    
    Args:
        file_name: Name of the file to locate
        
    Returns:
        str: Absolute path to the file
    """
    return os.path.join(os.path.dirname(__file__), file_name)

def get_file_near_exe(file_name: str) -> str:
    """
    Get path to a file that should be located next to the exe.
    Used for files that are installed alongside the application.
    
    Args:
        file_name: Name of the file to locate
        
    Returns:
        str: Absolute path to the file
    """
    try:
        # When running as compiled exe
        file_path = os.path.join(__compiled__.containing_dir, file_name)
    except NameError:
        # When running from source
        file_path = os.path.join(os.path.dirname(sys.argv[0]), file_name)
    return file_path

def get_user_data_path(file_name: str = "") -> str:
    """
    Get path in user's AppData directory for storing application data.
    Creates the directory if it doesn't exist.
    
    Args:
        file_name: Optional name of file within the data directory
        
    Returns:
        str: Absolute path to the data directory or file
    """
    data_dir = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / file_name) if file_name else str(data_dir)

def get_user_config_path(file_name: str = "") -> str:
    """
    Get path in user's AppData directory for storing configuration.
    Creates the directory if it doesn't exist.
    
    Args:
        file_name: Optional name of file within the config directory
        
    Returns:
        str: Absolute path to the config directory or file
    """
    config_dir = Path(user_config_dir(APP_NAME, APP_AUTHOR))
    config_dir.mkdir(parents=True, exist_ok=True)
    return str(config_dir / file_name) if file_name else str(config_dir)

def get_resource_path(resource_type: str, file_name: str) -> str:
    """
    Get path to a resource file (ui, prompts, etc.).
    Checks both the exe directory and development paths.
    
    Args:
        resource_type: Type of resource (e.g., 'ui', 'prompts')
        file_name: Name of the resource file
        
    Returns:
        str: Absolute path to the resource file
    """
    # First try inside exe/package
    resource_path = get_file_inside_exe(os.path.join(resource_type, file_name))
    if os.path.exists(resource_path):
        return resource_path
        
    # Then try next to exe
    resource_path = get_file_near_exe(os.path.join(resource_type, file_name))
    if os.path.exists(resource_path):
        return resource_path
        
    raise FileNotFoundError(f"Could not find resource {file_name} in {resource_type} directory")
