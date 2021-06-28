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
import platform
import shutil

import PySide2.QtCore as QtCore
import PySide2.QtGui as QtGui
from PySide2.QtGui import QDesktopServices
import PySide2.QtWidgets as QtWidgets

from PySide2.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

from PySide2.QtUiTools import QUiLoader as uic
from PySide2.QtCore import QFile

from utilities import *


class SettingsWindow:
    def __init__(self):
        self.loader = None
        self.ui = None
        self.ui_file = None
        self.main_window = self.load_ui_widget(os.path.join(get_main_dir(), "rsrc", "settings.ui"))
        self.settings = QtCore.QSettings("Lost Marble", "Papagayo-NG")
        self.main_window.general_2.clicked.connect(self.change_tab)
        self.main_window.graphical_2.clicked.connect(self.change_tab)
        self.main_window.misc_2.clicked.connect(self.change_tab)
        self.main_window.voice_rec.clicked.connect(self.change_tab)
        self.main_window.delete_settings.clicked.connect(self.delete_settings)
        self.main_window.ffmpeg_delete_button.clicked.connect(self.delete_ffmpeg)
        self.main_window.allo_delete_button.clicked.connect(self.delete_ai_model)
        self.main_window.accepted.connect(self.accepted)
        self.load_settings_to_gui()
        #self.main_window.setWindowIcon(QtGui.QIcon(os.path.join(get_main_dir(), "rsrc", "window_icon.bmp")))
        #self.main_window.about_ok_button.clicked.connect(self.close)

    def load_ui_widget(self, ui_filename, parent=None):
        loader = uic()
        file = QFile(ui_filename)
        file.open(QFile.ReadOnly)
        self.ui = loader.load(file, parent)
        file.close()
        return self.ui

    def change_tab(self, event=None):
        if self.main_window.graphical_2.isChecked():
            print("Graphics")
            self.main_window.settings_options.setCurrentIndex(1)
        elif self.main_window.general_2.isChecked():
            print("General")
            self.main_window.settings_options.setCurrentIndex(0)
        elif self.main_window.misc_2.isChecked():
            print("Misc")
            self.main_window.settings_options.setCurrentIndex(3)
        elif self.main_window.voice_rec.isChecked():
            print("Voice")
            self.main_window.settings_options.setCurrentIndex(2)

    def delete_settings(self, event=None):
        self.settings.clear()

    def delete_ffmpeg(self):
        ffmpeg_binary = "ffmpeg.exe"
        ffprobe_binary = "ffprobe.exe"
        if platform.system() == "Darwin":
            ffmpeg_binary = "ffmpeg"
            ffprobe_binary = "ffprobe"
        ffmpeg_path = os.path.join(get_main_dir(), ffmpeg_binary)
        ffprobe_path = os.path.join(get_main_dir(), ffprobe_binary)
        if os.path.exists(ffmpeg_path):
            os.remove(ffmpeg_path)
        if os.path.exists(ffprobe_path):
            os.remove(ffprobe_path)

    def delete_ai_model(self):
        allosaurus_model_path = os.path.join(get_main_dir(), "allosaurus_model")
        if not os.path.exists(allosaurus_model_path):
            shutil.rmtree(allosaurus_model_path)

    def load_settings_to_gui(self):
        self.main_window.fps_value.setValue(int(self.settings.value("LastFPS", 24)))
        self.main_window.lang_id_value.setText(self.settings.value("allo_lang_id", "eng"))
        self.main_window.voice_emission_value.setValue(float(self.settings.value("allo_emission", 1.0)))

    def accepted(self, event=None):
        self.settings.setValue("LastFPS", self.main_window.fps_value.value())
        self.settings.setValue("allo_lang_id", self.main_window.lang_id_value.text())
        self.settings.setValue("allo_emission", self.main_window.voice_emission_value.value())

    def close(self):
        self.main_window.close()
# end of class AboutBox
