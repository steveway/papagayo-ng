#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-

import math
import re
from PySide6 import QtCore, QtGui
import PySide6.QtWidgets as QtWidgets
import utilities
from settings_manager import SettingsManager

class MovableButton(QtWidgets.QPushButton):
    def __init__(self, lipsync_object, wfv_parent, phoneme_offset=None):
        super(MovableButton, self).__init__(lipsync_object.text, None)
        self.settings = SettingsManager.get_instance()
        self.title = lipsync_object.text
        self.node = lipsync_object
        self.phoneme_offset = phoneme_offset
        self.style = None
        self.is_resizing = False
        self.is_moving = False
        self.resize_origin = 0  # 0 = left 1 = right
        self.hot_spot = 0
        self.wfv_parent = wfv_parent
        self.setToolTip(lipsync_object.text)
        self.create_and_set_style()
        self.set_tags(self.node.tags)
        self.setMinimumWidth(self.convert_to_pixels(1))
        self.fit_text_to_size()

    def text_size(self):
        font_metrics = QtGui.QFontMetrics(self.font())
        return font_metrics.horizontalAdvance(self.title)

    def text_fits_in_button(self):
        if not self.is_phoneme():
            return self.text_size() < self.convert_to_pixels(
                self.node.get_frame_size()) + self.convert_to_pixels(0.5)
        else:
            return self.text_size() < self.convert_to_pixels(
                self.node.get_frame_size()) - self.convert_to_pixels(0.5)

    def fit_text_to_size(self):
        self.title = self.node.text
        while not self.text_fits_in_button():
            if len(self.title) > 1:
                self.title = self.title[:-1]
            else:
                break
        self.setText(self.title)

    def get_handle_width(self):
        resize_handle_width = 1.5
        return int(min(self.wfv_parent.frame_width * resize_handle_width,
                       self.convert_to_pixels(self.node.get_frame_size()) / 4))

    def create_and_set_style(self):
        if not self.style:
            if self.is_phrase():

                self.style = "QPushButton {{color: #000000; background-color:{0};".format(
                    QtGui.QColor(self.settings.get("/Graphics/{}".format("phrase_fill_color"),
                                                     utilities.original_colors["phrase_fill_color"])).name())
                self.style += "border-color: {0};".format(
                    QtGui.QColor(self.settings.get("/Graphics/{}".format("phrase_line_color"),
                                                     utilities.original_colors["phrase_line_color"])).name())
                self.style += "border-style: solid solid solid solid; border-width: 1px {0}px}};".format(
                    str(self.get_handle_width()))
            elif self.is_word():
                self.style = "QPushButton {{color: #000000; background-color:{0};".format(
                    QtGui.QColor(self.settings.get("/Graphics/{}".format("word_fill_color"),
                                                     utilities.original_colors["word_fill_color"])).name())
                self.style += "border-color: {0};".format(
                    QtGui.QColor(self.settings.get("/Graphics/{}".format("word_line_color"),
                                                     utilities.original_colors["word_line_color"])).name())
                self.style += "border-style: solid solid solid solid; border-width: 1px {0}px}};".format(
                    str(self.get_handle_width()))
            elif self.is_phoneme():
                self.style = "QPushButton {{color: #000000; background-color:{0};".format(
                    QtGui.QColor(
                        self.settings.get("/Graphics/{}".format("phoneme_fill_color"),
                                            utilities.original_colors["phoneme_fill_color"])).name())
                self.style += "border:1px solid {0};}};".format(
                    QtGui.QColor(
                        self.settings.get("/Graphics/{}".format("phoneme_line_color"),
                                            utilities.original_colors["phoneme_line_color"])).name())
            self.setStyleSheet(self.style)

    def is_phoneme(self):
        return self.node.object_type == "phoneme"

    def is_word(self):
        return self.node.object_type == "word"

    def is_phrase(self):
        return self.node.object_type == "phrase"

    def object_type(self):
        return self.node.object_type

    def after_reposition(self):
        self.setGeometry(self.convert_to_pixels(self.node.start_frame), self.y(),
                         self.convert_to_pixels(self.node.get_frame_size()), self.height())
        replaced = re.sub(r'(border-width: \dpx) \d+px', r'\1 {}px'.format(str(self.get_handle_width())),
                          self.styleSheet())
        self.setStyleSheet(replaced)
        self.update()

    def convert_to_pixels(self, frame_pos):
        return frame_pos * self.wfv_parent.frame_width

    def convert_to_frames(self, pixel_pos):
        return pixel_pos / self.wfv_parent.frame_width

    def mouseMoveEvent(self, event):
        if not self.wfv_parent.doc.sound.is_playing():
            if event.buttons() == QtCore.Qt.MouseButton.LeftButton:
                if not self.is_phoneme():
                    if (self.x() + event.x() >= self.convert_to_pixels(
                            self.node.end_frame) - self.get_handle_width()):
                        self.is_resizing = True
                        self.resize_origin = 1
                    if self.x() + event.x() <= self.x() + self.get_handle_width():
                        self.is_resizing = True
                        self.resize_origin = 0
                else:
                    self.is_resizing = False
                    self.is_moving = True
            else:
                self.is_moving = True
            if self.is_resizing and not self.is_moving:
                self.wfv_parent.doc.dirty = True
                if self.resize_origin == 1:  # start resize from right side
                    if self.convert_to_frames(
                            event.x() + self.x()) >= self.node.start_frame + self.node.get_min_size():
                        if self.convert_to_frames(event.x() + self.x()) <= self.node.get_right_max():
                            self.node.end_frame = math.ceil(self.convert_to_frames(event.x() + self.x()))
                            self.wfv_parent.doc.dirty = True
                            self.resize(self.convert_to_pixels(self.node.end_frame) -
                                        self.convert_to_pixels(self.node.start_frame), self.height())
                elif self.resize_origin == 0:  # start resize from left side
                    if self.convert_to_frames(event.x() + self.x()) < self.node.end_frame:
                        if self.convert_to_frames(event.x() + self.x()) >= self.node.get_left_max():
                            self.node.start_frame = math.floor(self.convert_to_frames(event.x() + self.x()))
                            if self.node.get_frame_size() < self.node.get_min_size():
                                self.node.start_frame = self.node.end_frame - self.node.get_min_size()
                            new_length = self.convert_to_pixels(self.node.end_frame) - self.convert_to_pixels(
                                self.node.start_frame)
                            self.resize(new_length, self.height())
                            self.move(self.convert_to_pixels(self.node.start_frame), self.y())
                self.after_reposition()
            else:
                self.is_moving = True
                mime_data = QtCore.QMimeData()
                drag = QtGui.QDrag(self)
                drag.setMimeData(mime_data)
                drag.setHotSpot(event.pos() - self.rect().topLeft())
                self.hot_spot = drag.hotSpot().x()
                # PyQt5 and PySide use different function names here, likely a Qt4 vs Qt5 problem.
                try:
                    exec("dropAction = drag.exec(QtCore.Qt.MoveAction)")
                except (SyntaxError, AttributeError):
                    dropAction = drag.exec(QtCore.Qt.DropAction.MoveAction)

    def mousePressEvent(self, event):
        if not self.wfv_parent.doc.sound.is_playing():
            if event.button() == QtCore.Qt.MouseButton.RightButton and self.is_word():
                # manually enter the pronunciation for this word
                list_of_new_phonemes = []
                prev_phoneme_list = ""
                for p in self.node.children:
                    prev_phoneme_list += " " + p.text
                return_value = show_pronunciation_dialog(self, self.wfv_parent.doc.parent.phonemeset.set,
                                                         self.node.text, prev_text=prev_phoneme_list)
                if return_value == -1:
                    pass
                elif not return_value:
                    pass
                else:
                    list_of_new_phonemes = return_value
                if list_of_new_phonemes:
                    if list_of_new_phonemes != prev_phoneme_list.split():
                        for proxy in self.wfv_parent.items():
                            if isinstance(proxy, QtWidgets.QGraphicsProxyWidget):
                                for old_node in self.node.children:
                                    if proxy.widget() == old_node.move_button:
                                        self.wfv_parent.scene().removeItem(proxy)

                        self.node.children = []
                        font_metrics = QtGui.QFontMetrics(font)
                        text_width, text_height = font_metrics.horizontalAdvance("Ojyg"), font_metrics.height() + 6
                        for phoneme_count, p in enumerate(list_of_new_phonemes):
                            phoneme = LipSyncObject(object_type="phoneme", parent=self.node)
                            phoneme.text = p
                            phoneme.start_frame = phoneme.end_frame = self.node.start_frame + phoneme_count
                            temp_button = MovableButton(phoneme, self.wfv_parent, phoneme_count % 2)
                            phoneme.move_button = temp_button
                            temp_scene_widget = self.wfv_parent.scene().addWidget(temp_button)
                            temp_rect = QtCore.QRect(phoneme.start_frame * self.wfv_parent.frame_width,
                                                     int(self.wfv_parent.height() -
                                                         (self.wfv_parent.horizontalScrollBar().height() * 1.5) -
                                                         (text_height + (text_height * (phoneme_count % 2)))),
                                                     self.wfv_parent.frame_width, text_height)
                            temp_scene_widget.setGeometry(temp_rect)
                            temp_scene_widget.setZValue(99)
                        self.wfv_parent.doc.dirty = True

    def mouseDoubleClickEvent(self, event):
        if not self.wfv_parent.doc.sound.is_playing() and not self.is_phoneme():
            start = self.node.start_frame / self.wfv_parent.doc.fps
            length = (self.node.end_frame - self.node.start_frame) / self.wfv_parent.doc.fps
            self.wfv_parent.doc.sound.play_segment(start, length)
            old_cur_frame = 0
            start_time = 0
            self.wfv_parent.temp_play_marker.setVisible(True)
            self.wfv_parent.main_window.action_stop.setEnabled(True)
            self.wfv_parent.main_window.action_play.setEnabled(False)
            while self.wfv_parent.doc.sound.is_playing():
                QtCore.QCoreApplication.processEvents()
                cur_frame = int(self.wfv_parent.doc.sound.current_time() * self.wfv_parent.doc.fps)
                if old_cur_frame != cur_frame:
                    old_cur_frame = cur_frame
                    self.wfv_parent.main_window.mouth_view.set_frame(old_cur_frame)
                    self.wfv_parent.set_frame(old_cur_frame)
                    try:
                        fps = 1.0 / (time.time() - start_time)
                    except ZeroDivisionError:
                        fps = 60
                    self.wfv_parent.main_window.statusbar.showMessage(
                        "Frame: {:d} FPS: {:d}".format((cur_frame + 1), int(fps)))
                    self.wfv_parent.scroll_position = self.wfv_parent.horizontalScrollBar().value()
                    start_time = time.time()
                self.wfv_parent.update()
            self.wfv_parent.temp_play_marker.setVisible(False)
            self.wfv_parent.main_window.action_stop.setEnabled(False)
            self.wfv_parent.main_window.action_play.setEnabled(True)
            self.wfv_parent.main_window.statusbar.showMessage("Stopped")
            self.wfv_parent.main_window.waveform_view.horizontalScrollBar().setValue(
                self.wfv_parent.main_window.waveform_view.scroll_position)
            self.wfv_parent.main_window.waveform_view.update()

    def mouseReleaseEvent(self, event):
        if self.is_moving:
            self.is_moving = False
            print("end_move")
        if self.is_resizing:
            self.reposition_descendants2(True)
            self.is_resizing = False
        if self.is_phoneme():
            self.wfv_parent.main_window.mouth_view.set_phoneme_picture(self.node.text)

    def set_tags(self, new_taglist):
        self.node.tags = new_taglist
        self.setToolTip("".join("{}\n".format(entry) for entry in self.node.tags)[:-1])
        # Change the border-style or something like that depending on whether there are tags or not
        if len(self.node.tags) > 0:
            if "solid" in self.styleSheet():
                self.setStyleSheet(self.styleSheet().replace("solid solid solid solid", "dashed solid dashed solid"))
        else:
            if "dashed" in self.styleSheet():
                self.setStyleSheet(self.styleSheet().replace("dashed solid dashed solid", "solid solid solid solid"))

    def reposition_descendants(self, did_resize=False, x_diff=0):
        self.node.reposition_descendants(did_resize, x_diff)
        self.wfv_parent.doc.dirty = True

    def reposition_descendants2(self, did_resize=False, x_diff=0):
        self.node.reposition_descendants2(did_resize, x_diff)

    def reposition_to_left(self):
        self.node.reposition_to_left()
        self.after_reposition()
        self.wfv_parent.doc.dirty = True

    def __del__(self):
        try:
            self.deleteLater()
        except RuntimeError:
            pass