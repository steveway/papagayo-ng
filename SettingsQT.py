#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-
# generated by wxGlade 0.3.5.1 on Thu Apr 21 12:10:56 2005

# Papagayo-NG, a lip-sync tool for use with several different animation suites
# Original Copyright (C) 2005 Mike Clifton
# Contact information at http://www.lostmarble.com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import os
import platform
import shutil
from functools import partial

import PySide6.QtWidgets as QtWidgets
from PySide6 import QtCore, QtGui
from PySide6.QtCore import QFile, QThread, QObject, Signal
from PySide6.QtUiTools import QUiLoader as uic
import model_manager

import utilities


class MySignal(QObject):
    sig = Signal(str)


class OnnxDownloadThread(QThread):
    def __init__(self, parent, model_name, model_path):
        QThread.__init__(self, parent)
        self.parent = parent
        try:
            self.model_manager = model_manager.ModelHandler()
        except:
            self.model_manager = model_manager.ModelHandler.get_instance()
        self.model_name = model_name
        self.model_path = model_path
        self.signal = MySignal()

    def change_name_and_path(self, model_name, model_path):
        self.model_name = model_name
        self.model_path = model_path

    def __del__(self):
        self.wait()

    def run(self):
        self.model_manager.download_model(self.model_name, self.model_path)
        self.signal.sig.emit("Download complete")


class SettingsWindow:
    def __init__(self, progress_callback, status_bar_progress):
        self.loader = None
        self.progress_callback = progress_callback
        self.status_bar_progress = status_bar_progress
        self.translator = utilities.ApplicationTranslator()
        #self.app = QtCore.QCoreApplication.instance()
        #self.translator = QtCore.QTranslator()
        #self.translator.load("en_text", utilities.get_main_dir())
        self.ui = None
        self.ui_file = None
        try:
            self.model_manager = model_manager.ModelHandler()
        except:
            self.model_manager = model_manager.ModelHandler.get_instance()
        self.download_thread = OnnxDownloadThread(None, None, None)
        self.download_thread.signal.sig.connect(self.onnx_complete)
        self.main_window = self.load_ui_widget(os.path.join(utilities.get_main_dir(), "rsrc", "settings.ui"))
        ini_path = os.path.join(utilities.get_app_data_path(), "settings.ini")
        self.settings = QtCore.QSettings(ini_path, QtCore.QSettings.IniFormat)
        self.settings.setFallbacksEnabled(False)  # File only, not registry or or.
        self.main_window.general_2.clicked.connect(self.change_tab)
        self.main_window.graphical_2.clicked.connect(self.change_tab)
        self.main_window.misc_2.clicked.connect(self.change_tab)
        self.main_window.voice_rec.clicked.connect(self.change_tab)
        self.main_window.delete_settings.clicked.connect(self.delete_settings)
        self.main_window.reset_colors.clicked.connect(self.on_reset_colors)
        self.main_window.ffmpeg_delete_button.clicked.connect(self.delete_ffmpeg)
        self.main_window.allo_delete_button.clicked.connect(self.delete_ai_model)
        self.main_window.rhubarb_delete_button.clicked.connect(self.delete_rhubarb)
        self.main_window.download_onnx_model.clicked.connect(self.download_onnx_model)
        self.main_window.accepted.connect(self.accepted)
        for color_button in self.main_window.graphical.findChildren(QtWidgets.QPushButton):
            if "Color" in color_button.text():
                self.main_window.connect(color_button, QtCore.SIGNAL("clicked()"),
                                         partial(self.open_color_dialog, color_button))
        self.load_settings_to_gui()
        self.main_window.open_app_data_path.clicked.connect(self.open_app_data)
        self.main_window.set_qss_path_button.clicked.connect(self.select_qss_path)
        self.main_window.settings_options.setCurrentIndex(0)
        # self.main_window.setWindowIcon(QtGui.QIcon(os.path.join(get_main_dir(), "rsrc", "window_icon.bmp")))
        # self.main_window.about_ok_button.clicked.connect(self.close)

    def load_ui_widget(self, ui_filename, parent=None):
        loader = uic()
        file = QFile(ui_filename)
        file.open(QFile.ReadOnly)
        self.ui = loader.load(file, parent)
        file.close()
        return self.ui

    def download_onnx_model(self):
        model_name = self.main_window.available_onnx_models.currentText()
        model_path = os.path.join(utilities.get_app_data_path(), "onnx_models")
        self.status_bar_progress.show()
        self.status_bar_progress.setMaximum(0)
        self.status_bar_progress.setMinimum(0)
        self.status_bar_progress.setValue(0)
        self.download_thread.change_name_and_path(model_name, model_path)
        self.download_thread.start()

    def onnx_complete(self, data):
        print(f"Download finished with message: {data}")
        self.status_bar_progress.hide()

    def change_tab(self, event=None):
        if self.main_window.graphical_2.isChecked():
            self.main_window.settings_options.setCurrentIndex(1)
        elif self.main_window.general_2.isChecked():
            self.main_window.settings_options.setCurrentIndex(0)
        elif self.main_window.misc_2.isChecked():
            self.main_window.settings_options.setCurrentIndex(3)
        elif self.main_window.voice_rec.isChecked():
            self.main_window.settings_options.setCurrentIndex(2)

    def delete_settings(self, event=None):
        self.settings.clear()

    def select_qss_path(self):
        qss_file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self.main_window,
                                                                 "Open QSS StyleSheet",
                                                                 self.settings.value("/Graphics/qss_path",
                                                                                     utilities.get_app_data_path()),
                                                                 "QSS files (*.qss)")
        self.main_window.qss_path.setText(qss_file_name)

    def open_color_dialog(self, event=None):
        old_color = event.palette().button().color()
        new_color = QtWidgets.QColorDialog().getColor(old_color)
        new_text_color = "#ffffff" if new_color.lightnessF() < 0.5 else "#000000"
        style = "background-color: {};\n color: {};\n border: transparent;".format(new_color.name(), new_text_color)
        event.setStyleSheet(style)

    def open_app_data(self):
        qt_url = QtCore.QUrl(r"file:///" + utilities.get_app_data_path(), QtCore.QUrl.TolerantMode)
        QtGui.QDesktopServices.openUrl(qt_url)

    def delete_ffmpeg(self):
        ffmpeg_binary = "ffmpeg.exe"
        ffprobe_binary = "ffprobe.exe"
        if platform.system() == "Darwin":
            ffmpeg_binary = "ffmpeg"
            ffprobe_binary = "ffprobe"
        ffmpeg_path_old = os.path.join(utilities.get_main_dir(), ffmpeg_binary)
        ffprobe_path_old = os.path.join(utilities.get_main_dir(), ffprobe_binary)
        if os.path.exists(ffmpeg_path_old):
            os.remove(ffmpeg_path_old)
        if os.path.exists(ffprobe_path_old):
            os.remove(ffprobe_path_old)
        ffmpeg_path_new = os.path.join(utilities.get_app_data_path(), ffmpeg_binary)
        ffprobe_path_new = os.path.join(utilities.get_app_data_path(), ffprobe_binary)
        if os.path.exists(ffmpeg_path_new):
            os.remove(ffmpeg_path_new)
        if os.path.exists(ffprobe_path_new):
            os.remove(ffprobe_path_new)

    def delete_rhubarb(self):
        rhubarb_path = os.path.join(utilities.get_app_data_path(), "rhubarb")
        if os.path.exists(rhubarb_path):
            shutil.rmtree(rhubarb_path)

    def delete_ai_model(self):
        allosaurus_model_path_old = os.path.join(utilities.get_main_dir(), "allosaurus_model")
        allosaurus_model_path_new = os.path.join(utilities.get_app_data_path(), "allosaurus_model")
        if os.path.exists(allosaurus_model_path_old):
            shutil.rmtree(allosaurus_model_path_old)
        if os.path.exists(allosaurus_model_path_new):
            shutil.rmtree(allosaurus_model_path_new)

    def load_settings_to_gui(self):
        self.main_window.fps_value.setValue(int(self.settings.value("LastFPS", 24)))
        self.main_window.lang_id_value.setText(self.settings.value("/VoiceRecognition/allo_lang_id", "eng"))
        self.main_window.voice_emission_value.setValue(
            float(self.settings.value("/VoiceRecognition/allo_emission", 1.0)))
        if str(self.settings.value("/VoiceRecognition/run_voice_recognition", "true")).lower() == "true":
            self.main_window.run_voice_recognition.setChecked(True)
        else:
            self.main_window.run_voice_recognition.setChecked(False)
        self.main_window.app_data_path.setText(utilities.get_app_data_path())
        self.main_window.model_name.setText(self.settings.value("/VoiceRecognition/allosaurus_model", "latest"))
        self.main_window.app_data_path.home(True)
        list_of_recognizers = ["Allosaurus", "Rhubarb"]
        self.main_window.selected_recognizer.addItems(list_of_recognizers)
        language_list = []
        for f in os.listdir(os.path.join(utilities.get_main_dir(), "rsrc", "i18n")):
            language_list.append(os.path.basename(f).split(".")[0])
        self.main_window.ui_language.addItems(language_list)
        lang_index = self.main_window.ui_language.findText(self.settings.value("language", "en_us"))
        self.main_window.ui_language.setCurrentIndex(lang_index)
        if str(self.settings.value("rest_after_words", "true")).lower() == "true":
            self.main_window.rest_after_words.setChecked(True)
        else:
            self.main_window.rest_after_words.setChecked(False)
        if str(self.settings.value("rest_after_phonemes", "true")).lower() == "true":
            self.main_window.rest_after_phonemes.setChecked(True)
        else:
            self.main_window.rest_after_phonemes.setChecked(False)
        recog_index = self.main_window.selected_recognizer.findText(
            self.settings.value("/VoiceRecognition/recognizer", "Allosaurus"))
        self.main_window.selected_recognizer.setCurrentIndex(recog_index)
        for color_button in self.main_window.graphical.findChildren(QtWidgets.QPushButton):
            if "Color" in color_button.text():
                new_color = QtGui.QColor(
                    self.settings.value("/Graphics/{}".format(color_button.objectName()),
                                        utilities.original_colors[color_button.objectName()]))
                new_text_color = "#ffffff" if new_color.lightnessF() < 0.5 else "#000000"
                style = "background-color: {};\n color: {};\n border: transparent;".format(new_color.name(),
                                                                                           new_text_color)
                color_button.setStyleSheet(style)
        onnx_model_list = self.model_manager.get_model_list("phoneme")
        self.main_window.available_onnx_models.addItems(onnx_model_list)
        self.main_window.available_onnx_models.setCurrentText(self.settings.value("/VoiceRecognition/onnx_model"))
        self.main_window.qss_path.setText(self.settings.value("qss_file_path", ""))

    def on_reset_colors(self):
        for color_name, color_value in utilities.original_colors.items():
            self.settings.setValue("/Graphics/{}".format(color_name), color_value.name())
        for color_button in self.main_window.graphical.findChildren(QtWidgets.QPushButton):
            if "Color" in color_button.text():
                new_color = QtGui.QColor(self.settings.value(color_button.objectName(),
                                                             utilities.original_colors[color_button.objectName()]))
                new_text_color = "#ffffff" if new_color.lightnessF() < 0.5 else "#000000"
                style = "background-color: {};\n color: {};\n border: transparent;".format(new_color.name(),
                                                                                           new_text_color)
                color_button.setStyleSheet(style)

    def accepted(self, event=None):
        self.settings.setValue("LastFPS", self.main_window.fps_value.value())
        self.settings.setValue("/VoiceRecognition/allo_lang_id", self.main_window.lang_id_value.text())
        self.settings.setValue("/VoiceRecognition/allo_emission", self.main_window.voice_emission_value.value())
        self.settings.setValue("/VoiceRecognition/run_voice_recognition",
                               bool(self.main_window.run_voice_recognition.isChecked()))
        self.settings.setValue("qss_file_path", str(self.main_window.qss_path.text()))
        self.settings.setValue("/VoiceRecognition/recognizer", self.main_window.selected_recognizer.currentText())
        self.settings.setValue("rest_after_words", bool(self.main_window.rest_after_words.isChecked()))
        self.settings.setValue("rest_after_phonemes", bool(self.main_window.rest_after_phonemes.isChecked()))
        self.settings.setValue("language", self.main_window.ui_language.currentText())
        self.settings.setValue("/VoiceRecognition/allosaurus_model", self.main_window.model_name.text())
        self.settings.setValue("/VoiceRecognition/onnx_model", self.main_window.available_onnx_models.currentText())
        for color_button in self.main_window.graphical.findChildren(QtWidgets.QPushButton):
            if "Color" in color_button.text():
                self.settings.setValue("/Graphics/{}".format(color_button.objectName()),
                                       color_button.palette().button().color().name())

    def close(self):
        self.main_window.close()
# end of class AboutBox
