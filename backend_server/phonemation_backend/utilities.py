import os
import platform
import shutil
import sys
import traceback
import appdirs
import logging
from pathlib import Path


def get_file_inside_exe(file_name):
    return os.path.join(os.path.dirname(__file__), file_name)

def get_file_near_exe(file_name):
    file_path = ""
    try:
        file_path = os.path.join(__compiled__.containing_dir, file_name)
    except NameError:
        file_path = os.path.join(os.path.dirname(sys.argv[0]), file_name)
    return file_path

def main_is_frozen():
    return (hasattr(sys, "frozen") or  # new py2exe
            hasattr(sys, "importers") or
            hasattr(sys, "_MEIPASS"))


def get_main_dir():
    """ Get absolute path to resource, works for dev and for PyInstaller """
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    if hasattr(sys, "_MEIPASS"):
        base_path = os.path.dirname(sys.executable)
    else:
        main_file = os.path.abspath(sys.argv[0])
        base_path = os.path.dirname(main_file)
    return Path(base_path)


def resource_path(relative):
    bundle_dir = os.path.abspath(os.path.dirname(__file__))
    full_path = Path(bundle_dir).joinpath(relative)
    return full_path


def get_app_data_path():
    app_name = "Phonemation"
    app_author = "Steveway"
    user_data_dir = appdirs.user_data_dir(app_name, app_author)
    # Ensure the directory (and any parents) exists.
    os.makedirs(user_data_dir, exist_ok=True)
    return Path(user_data_dir)


def which(program):
    return shutil.which(program)


def ffmpeg_binaries_exists():
    if platform.system() in ["Windows", "Darwin"]:
        ffmpeg_binary = "ffmpeg.exe"
        ffprobe_binary = "ffprobe.exe"
        if platform.system() == "Darwin":
            ffmpeg_binary = "ffmpeg"
            ffprobe_binary = "ffprobe"
        ffmpeg_path = os.path.join(get_app_data_path(), ffmpeg_binary)
        ffprobe_path = os.path.join(get_app_data_path(), ffprobe_binary)
        if not os.path.exists(ffmpeg_path) or not os.path.exists(ffprobe_path):
            return False
        else:
            return True
    return False


_INIT_LOGGING_DONE = False


def init_logging():
    """Set up logging streams and format.
    """

    global _INIT_LOGGING_DONE
    if not _INIT_LOGGING_DONE:
        root_logger = logging.root

        root_formatter = logging.Formatter(fmt='{name}.{levelname}.{lineno}: {msg}', style='{')

        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(root_formatter)

        root_logger.addHandler(stdout_handler)
        _INIT_LOGGING_DONE = True

    else:
        logging.info(f'init_logging already called; skip creation of duplicate handlers')
