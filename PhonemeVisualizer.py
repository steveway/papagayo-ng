# -*- coding: ISO-8859-1 -*-

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
import sys

from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtWidgets import QMainWindow, QApplication, QGraphicsView, QGraphicsScene

import utilities
from LipsyncDoc import PhonemeSet
from math import sqrt


def sort_mouth_list_order(elem):
    try:
        return int(elem.split("-")[0])
    except ValueError:
        return hash(elem)


class PronunciationDialog(QMainWindow):
    def __init__(self):
        super(PronunciationDialog, self).__init__()
        self.translator = utilities.ApplicationTranslator()
        self.setWindowTitle(self.translator.translate("PronunciationDialog", "Phoneme Visualizer"))
        self.word_label = QtWidgets.QLabel(self.translator.translate("PronunciationDialog", "Break down the word:"))
        self.word_label.setAlignment(QtCore.Qt.AlignCenter)
        self.box = QtWidgets.QVBoxLayout()
        self.phoneme_grid = QtWidgets.QGridLayout()
        self.main_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.main_widget)
        self.current_mouth = None
        self.mouths = {}
        self.current_phoneme = "rest"
        self.mouth_view = QGraphicsView()
        self.mouth_view.setScene(QGraphicsScene())
        self.mouth_view.setMinimumSize(200, 200)
        self.mouth_view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.mouth_view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.load_mouths()
        self.phoneme_set = PhonemeSet()
        self.phoneme_set.load("preston_blair")
        self.mouth_choice = QtWidgets.QComboBox()
        self.phoneme_choice = QtWidgets.QComboBox()
        mouth_list = list(self.mouths.keys())
        mouth_list.sort(key=sort_mouth_list_order)
        for mouth in mouth_list:
            self.mouth_choice.addItem(mouth)
        #self.mouth_choice.setCurrentIndex(self.main_window.mouth_choice.currentIndex())
        self.mouth_choice.current_mouth = self.mouth_choice.currentText()

        self.gave_ok = False
        self.stop_decode = False
        self.curr_x = 0
        self.curr_y = 0
        self.max_x = round(sqrt(len(self.phoneme_set.set)))  # This way the grid should always be as square as possible
        print(self.max_x)

        self.box.addWidget(self.mouth_view)
        self.box.addWidget(self.mouth_choice)
        self.box.addWidget(self.phoneme_choice)
        self.box.addLayout(self.phoneme_grid)

        phoneme_ids = {}
        self.phoneme_buttons = {}
        for phoneme_set in self.phoneme_set.alternatives:
            self.phoneme_choice.addItem(phoneme_set)
        self.phoneme_choice.setCurrentText(self.phoneme_set.selected_set)
        self.phoneme_choice.currentIndexChanged.connect(self.change_phoneme_buttons)
        self.change_phoneme_buttons()
        # for phoneme in self.phoneme_set.set:
        #     print(phoneme)
        #     if phoneme != "rest":
        #         self.phoneme_buttons[phoneme] = QtWidgets.QPushButton(phoneme)
        #         self.phoneme_buttons[phoneme].clicked.connect(self.on_phoneme_click)
        #         self.phoneme_buttons[phoneme].enterEvent = self.hover_phoneme
        #         self.phoneme_grid.addWidget(self.phoneme_buttons[phoneme], self.curr_y, self.curr_x)
        #         print(self.curr_y, self.curr_x)
        #         self.curr_x += 1
        #         if self.curr_x >= self.max_x:
        #             self.curr_x = 0
        #             self.curr_y += 1
        # print(self.phoneme_buttons)
        self.mouth_choice.currentIndexChanged.connect(self.on_mouth_choice)
        self.set_phoneme_picture(self.current_phoneme)
        self.main_widget.setLayout(self.box)
        self.setWindowIcon(QtGui.QIcon(os.path.join(utilities.get_main_dir(), "rsrc", "window_icon.bmp")))
        self.show()

    def change_phoneme_buttons(self):
        self.phoneme_set.load(self.phoneme_choice.currentText())
        for button in self.phoneme_buttons.values():
            self.phoneme_grid.removeWidget(button)
            button.deleteLater()
        self.phoneme_buttons = {}
        self.curr_x = 0
        self.curr_y = 0
        self.max_x = round(sqrt(len(self.phoneme_set.set)))  # This way the grid should always be as square as possible
        for phoneme in self.phoneme_set.set:
            print(phoneme)
            if phoneme != "rest":
                self.phoneme_buttons[phoneme] = QtWidgets.QPushButton(phoneme)
                self.phoneme_buttons[phoneme].clicked.connect(self.hover_phoneme)
                # self.phoneme_buttons[phoneme].enterEvent = self.hover_phoneme
                self.phoneme_buttons[phoneme].setAutoExclusive(True)
                self.phoneme_buttons[phoneme].setCheckable(True)
                self.phoneme_grid.addWidget(self.phoneme_buttons[phoneme], self.curr_y, self.curr_x)
                print(self.curr_y, self.curr_x)
                self.curr_x += 1
                if self.curr_x >= self.max_x:
                    self.curr_x = 0
                    self.curr_y += 1

    def hover_phoneme(self, event=None):
        for phoneme in self.phoneme_buttons:
            if self.phoneme_buttons[phoneme].underMouse():
                self.set_phoneme_picture(phoneme)

    def add_phoneme(self, phoneme):
        text = "{} {}".format(self.phoneme_ctrl.text().strip(), phoneme)
        self.phoneme_ctrl.setText(text.strip())

    def on_phoneme_click(self, event=None):
        phoneme = self.sender().text()
        text = "{} {}".format(self.phoneme_ctrl.text().strip(), phoneme)
        self.phoneme_ctrl.setText(text.strip())

    def on_mouth_choice(self, event=None):
        self.current_mouth = self.mouth_choice.currentText()
        #self.mouth_view.draw_me()

    def on_accept(self):
        self.gave_ok = True
        self.accept()
        # self.close()

    def on_reject(self):
        self.gave_ok = False
        self.reject()
        # self.close()

    def on_abort(self):
        self.gave_ok = False
        self.stop_decode = True
        self.reject()

    def process_mouth_dir(self, dir_name, names, supported_imagetypes):
        has_images = False
        for files in names:
            files = files.lower()
            if files.split(".")[-1] in supported_imagetypes:
                has_images = True
        if not has_images:
            return
        self.add_mouth(os.path.normpath(dir_name), names)

    def load_mouths(self):
        supported_imagetypes = QtGui.QImageReader.supportedImageFormats()
        for directory, dir_names, file_names in os.walk(os.path.join(utilities.get_main_dir(), "rsrc", "mouths")):
            self.process_mouth_dir(directory, file_names, supported_imagetypes)

    def add_mouth(self, dir_name, names):
        bitmaps = {}
        for files in names:
            if ".svn" in files:
                continue
            path = os.path.normpath(os.path.join(dir_name, files))
            bitmaps[files.split('.')[0]] = QtGui.QPixmap(path)
        self.mouths[os.path.basename(dir_name)] = bitmaps
        if self.current_mouth is None:
            self.current_mouth = os.path.basename(dir_name)

    def set_phoneme_picture(self, phoneme):
        if not self.current_mouth:
            self.current_mouth = list(self.mouths)[0]
        if self.current_mouth in self.mouths.keys():
            if phoneme in self.mouths[self.current_mouth].keys():
                bitmap = self.mouths[self.current_mouth][phoneme]
            else:
                bitmap = self.mouths[self.current_mouth]["rest"]
        else:
            bitmap = self.mouths[list(self.mouths)[0]]["rest"]
        self.mouth_view.scene().clear()
        bitmap = bitmap.scaled(self.mouth_view.scene().width() or 200, self.mouth_view.scene().height() or 200,
                               QtCore.Qt.KeepAspectRatio)
        self.mouth_view.scene().addPixmap(bitmap)
        if phoneme not in self.mouths[self.current_mouth].keys():
            self.mouth_view.scene().addText(self.translator.translate("MouthView", "Missing Mouth: {0}").format(phoneme), QtGui.QFont("Swiss", 14))
        self.mouth_view.fitInView(self.mouth_view.x(), self.mouth_view.y(), self.mouth_view.width(), self.mouth_view.height())


# end of class PronunciationDialog


def show_pronunciation_dialog(parent_window, phoneme_set, word_to_decode, prev_text=""):
    dlg = PronunciationDialog(parent_window, phoneme_set)
    dlg.word_label.setText("{} {}".format(dlg.word_label.text(), word_to_decode))
    dlg.phoneme_ctrl.setText(prev_text)
    dlg.exec_()
    if dlg.stop_decode:
        dlg.destroy()
        return -1
    if dlg.gave_ok:
        phonemes_as_list = []
        for p in dlg.phoneme_ctrl.text().split():
            if len(p) == 0:
                continue
            phonemes_as_list.append(p)
        dlg.destroy()
        return phonemes_as_list


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = PronunciationDialog()
    sys.exit(app.exec_())
