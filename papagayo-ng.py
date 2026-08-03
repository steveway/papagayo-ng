
import argparse
import ctypes
import tempfile
from pathlib import Path

from PySide6 import QtWidgets, QtCore

import utilities
import logging
import os
import platform
import sys
import traceback
import papagayongrcc
import logging
from utilities import init_logging

logger = logging.getLogger('papagayo')

try:
    import pyi_splash
except ImportError:
    pyi_splash = None

log_file = utilities.get_app_data_path() / "runtime.log"
logging.basicConfig(filename=str(log_file), encoding='utf-8', level=logging.INFO,
                    format="%(asctime)s:%(funcName)s:%(lineno)d:%(message)s")


class ParentClass:
    def __init__(self):
        self.phonemeset = LipsyncFrameQT.LipsyncDoc.PhonemeSet()


def parse_cli():
    ARG_KEY_LOG_LEVEL = "log_level"

    translator = utilities.ApplicationTranslator()
    parser = argparse.ArgumentParser(description="Papagayo-NG LipSync Tool")
    parser.add_argument("-i", dest="input_file_path",
                        help=translator.translate("CLI",
                                                  "The input file, either a supported Papagayo-NG Project or a sound file."),
                        metavar="FILE")
    parser.add_argument("--cli", dest="use_cli", action="store_true", help="Set this to use CLI commands.")
    parser.add_argument("-o", dest="output_file",
                        help=translator.translate("CLI",
                                                  "The output file, should be one of these filetypes or a directory: {}").format(
                            LipsyncFrameQT.lipsync_extension_list + LipsyncFrameQT.export_file_types))
    parser.add_argument("--output-type", dest="output_type",
                        help=translator.translate("CLI", "Possible options: {}").format(
                            "".join(" {},".format(o_type.upper()) for o_type in
                                    LipsyncFrameQT.lipsync_extension_list + LipsyncFrameQT.exporter_list)[:-1]))
    parser.add_argument("--language", dest="language",
                        help=translator.translate("CLI", "Choose the language for Alelo Export."))
    parser.add_argument("--mouth-images", dest="mouth_image_dir",
                        help=translator.translate("CLI", "The Directory containing the mouth Images."))
    parser.add_argument("--use-onnx", dest="onnx", action="store_true",
                        help=translator.translate("CLI", "Set this to run ONNX (wav2vec2 backend) on your input files."))
    parser.add_argument("--fps", dest="fps", help=translator.translate("CLI", "Set FPS for Input."), metavar="INT")
    parser.add_argument("--log-level", "-l", dest=ARG_KEY_LOG_LEVEL, choices=logging._nameToLevel.keys(), help="Set logging level.", default=logging._levelToName[logging.WARNING])
    parser.add_argument("--build-smoke-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # update root logger log level
    try:
        log_level_name = getattr(args, ARG_KEY_LOG_LEVEL, None)
        logging.root.setLevel(logging._nameToLevel[log_level_name])
    except:
        logger.warning(f"unable to set log level to {log_level_name}; leave at {logging._nameToLevel[logging.root.getEffectiveLevel()]}")

    list_of_input_files = []
    langman = LipsyncFrameQT.LipsyncDoc.LanguageManager()
    langman.init_languages()
    
    # Use the settings manager instead of direct QSettings
    from settings_manager import SettingsManager
    settings = SettingsManager.get_instance()
    
    if not args.use_cli:
        settings.set_audio_output("new")
    else:
        settings.set_audio_output("old")
        if args.onnx:
            settings.set_recognizer("ONNX")
            settings.set_run_voice_recognition(True)
        if not args.onnx:
            settings.set_run_voice_recognition(False)
        if args.fps:
            settings.set_fps(args.fps)
        if args.mouth_image_dir:
            settings.set_mouth_dir(args.mouth_image_dir)
            
    ini_path = Path(LipsyncFrameQT.utilities.get_app_data_path()) / "settings.ini"
    config = LipsyncFrameQT.QtCore.QSettings(str(ini_path), LipsyncFrameQT.QtCore.QSettings.Format.IniFormat)
    
    if args.input_file_path:
        parent = ParentClass()
        if os.path.isdir(args.input_file_path):
            for (dirpath, dirnames, filenames) in os.walk(args.input_file_path):
                list_of_input_files.extend(os.path.join(dirpath, filename) if filename.endswith(
                    LipsyncFrameQT.lipsync_extension_list + LipsyncFrameQT.audio_extension_list) else "" for
                                           filename in
                                           filenames)
                break
        else:
            if args.input_file_path.endswith(
                    LipsyncFrameQT.lipsync_extension_list + LipsyncFrameQT.audio_extension_list):
                list_of_input_files.append(args.input_file_path)
        list_of_input_files = filter(None, list_of_input_files)
        logging.info("Input Files:")
        list_of_doc_objects = []
        for i in list_of_input_files:
            logging.info(i)
            new_doc = LipsyncFrameQT.open_file_no_gui(i, parent)
            list_of_doc_objects.append(new_doc)

        for i in list_of_doc_objects:
            if args.output_type.upper() == "MOHO":
                for voice in i.project_node.children:
                    if args.output_file:
                        if os.path.isdir(args.output_file):
                            voice_file_path = os.path.join(args.output_file, "{}.dat".format(voice.name))
                            voice.export(voice_file_path)
                        else:
                            voice.export(args.output_file)
            elif args.output_type.upper() == "ALELO":
                for voice in i.project_node.children:
                    if args.output_file:
                        if os.path.isdir(args.output_file):
                            voice_file_path = os.path.join(args.output_file, "{}.txt".format(voice.name))
                            voice.export_alelo(voice_file_path, args.language, langman)
                        else:
                            voice.export_alelo(args.output_file, args.language, langman)
            elif args.output_type.upper() == "JSON":
                for voice in i.project_node.children:
                    if args.output_file:
                        if os.path.isdir(args.output_file):
                            voice_file_path = os.path.join(args.output_file, "{}.json".format(voice.name))
                            voice.export_json(voice_file_path, i.soundPath)
                        else:
                            voice.export_json(args.output_file, i.soundPath)
            elif args.output_type.upper() == "IMAGES":
                for voice in i.project_node.children:
                    if args.output_file:
                        if os.path.isdir(args.output_file):
                            voice.export_images(args.output_file, "")
            elif args.output_type.upper() == "PGO":
                if args.output_file:
                    i.save(args.output_file)
            elif args.output_type.upper() == "PG2":
                if args.output_file:
                    i.save2(args.output_file)

    return args


def main():
    global LipsyncFrameQT
    import LipsyncFrameQT

    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    init_logging()

    if pyi_splash:
        pyi_splash.close()
    # Use this code to signal the splash screen removal.
    if "NUITKA_ONEFILE_PARENT" in os.environ:
        splash_file = Path(tempfile.gettempdir()) / f"onefile_{os.environ['NUITKA_ONEFILE_PARENT']}_splash_feedback.tmp"
        if splash_file.exists():
            splash_file.unlink()
    application = QtWidgets.QApplication(sys.argv)
    args = parse_cli()
    if args.use_cli:
        return 0
    if platform.system() == "Windows":
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        process_array = (ctypes.c_uint8 * 1)()
        num_processes = kernel32.GetConsoleProcessList(process_array, 1)
        if num_processes < 3:
            ctypes.WinDLL('user32').ShowWindow(kernel32.GetConsoleWindow(), 0)
    papagayo_window = LipsyncFrameQT.LipsyncFrame()
    papagayo_window.main_window.show()
    if args.build_smoke_test:
        QtCore.QTimer.singleShot(1000, application.quit)
    return papagayo_window.app.exec()


def report_startup_error():
    crash_file = utilities.get_app_data_path() / "startup-crash.log"
    with crash_file.open("a", encoding="utf-8") as stream:
        traceback.print_exc(file=stream)
    logging.exception("Papagayo-NG failed during startup")
    if platform.system() == "Windows" and not os.environ.get("PAPAGAYO_BUILD_SMOKE_TEST"):
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Papagayo-NG could not start.\n\nDiagnostic details were written to:\n{crash_file}",
            "Papagayo-NG startup error",
            0x10,
        )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        report_startup_error()
        sys.exit(1)
