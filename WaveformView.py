#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-

import os
import re
import time
import sys
import numpy as np
from PySide6 import QtCore, QtGui
import PySide6.QtWidgets as QtWidgets

from LipsyncDoc import *
import utilities
from SceneWithDrag import SceneWithDrag
from MovableButton import MovableButton

# Constants
font = QtGui.QFont("Swiss", 6)
default_sample_width = 4
default_samples_per_frame = 2

def normalize(x):
    x = np.asarray(x)
    return ((x - x.min()) / (np.ptp(x))) * 0.8

class WaveformView(QtWidgets.QGraphicsView):
    def __init__(self, parent=None):
        super(WaveformView, self).__init__(parent)
        self.setScene(SceneWithDrag(self))
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.ViewportUpdateMode.NoViewportUpdate)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.translator = utilities.ApplicationTranslator()
        from settings_manager import SettingsManager
        self.settings = SettingsManager.get_instance()
        # Other initialization
        self.main_window = None
        for widget in QtWidgets.QApplication.instance().topLevelWidgets():
            if isinstance(widget, QtWidgets.QMainWindow):
                self.main_window = widget
        self.doc = None
        self.currently_selected_object = None
        self.is_scrubbing = False
        self.cur_frame = 0
        self.old_frame = 0
        self.default_sample_width = default_sample_width
        self.default_samples_per_frame = default_samples_per_frame
        self.sample_width = self.default_sample_width
        self.samples_per_frame = self.default_samples_per_frame
        self.samples_per_sec = int(str(self.settings.get_fps())) * self.samples_per_frame
        self.frame_width = self.sample_width * self.samples_per_frame
        self.phrase_bottom = 16
        self.word_bottom = 32
        self.phoneme_top = 128
        self.waveform_polygon = None
        self.wv_height = 1
        self.temp_phrase = None
        self.temp_word = None
        self.temp_phoneme = None
        self.temp_button = None
        self.draw_play_marker = False
        self.num_samples = 0
        self.list_of_lines = []
        self.amp = []
        self.temp_play_marker = None
        self.scroll_position = 0
        self.first_update = True
        self.node = None
        self.did_resize = None
        self.threadpool = QtCore.QThreadPool.globalInstance()
        self.scene().setSceneRect(0, 0, self.width(), self.height())
        self.resize_timer = QtCore.QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.resize_finished)

    def dropEvent(self, event):
        print("DragLeave")  # Strangely no dragLeaveEvent fires but a dropEvent instead...
        if event.mimeData().hasUrls():
            # event.accept()
            for url in event.mimeData().urls():
                if sys.platform == "darwin":
                    from Foundation import NSURL
                    fname = str(NSURL.URLWithString_(str(url.toString())).filePathURL().path())
                    self.main_window.lip_sync_frame.open(fname)
                else:
                    fname = str(url.toLocalFile())
                    self.main_window.lip_sync_frame.open(fname)
            return True
        else:
            if event.source():
                event.source().is_moving = False
            event.accept()

    def dragEnterEvent(self, e):
        print("DragEnter!")
        e.accept()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            possible_item = self.itemAt(event.pos())
            if type(possible_item) == QtWidgets.QGraphicsPolygonItem:
                possible_item = None
            if not possible_item:
                if self.currently_selected_object:
                    try:
                        new_style = self.currently_selected_object.styleSheet()
                        if "2px" in new_style:
                            new_style = new_style.replace("2px", "1px")
                        else:
                            pass
                        self.currently_selected_object.setStyleSheet(new_style)
                    except RuntimeError:
                        pass  # The real object was deleted, instead of carefully tracking we simply do this
                self.currently_selected_object = None
                self.main_window.list_of_tags.clear()
                self.main_window.tag_list_group.setEnabled(False)
                self.main_window.tag_list_group.setTitle(self.translator.translate("WaveformView", "Selected Object Tags"))
                self.main_window.parent_tags.clear()
                self.main_window.parent_tags.setEnabled(False)
                self.is_scrubbing = True
            else:
                self.main_window.tag_list_group.setEnabled(True)
                if self.currently_selected_object:
                    try:
                        new_style = self.currently_selected_object.styleSheet()
                        if "2px" in new_style:
                            new_style = new_style.replace("2px", "1px")
                        else:
                            pass
                        self.currently_selected_object.setStyleSheet(new_style)
                    except RuntimeError:
                        pass  # The real object was deleted, instead of carefully tracking we simply do this
                self.currently_selected_object = possible_item.widget()
                new_style = self.currently_selected_object.styleSheet()
                if "1px" in new_style:
                    new_style = new_style.replace("1px", "2px")
                else:
                    pass
                self.currently_selected_object.setStyleSheet(new_style)
                self.main_window.list_of_tags.clear()
                self.main_window.list_of_tags.addItems(self.currently_selected_object.node.tags)
                title_part_two = self.currently_selected_object.node.text
                if len(self.currently_selected_object.node.text) > 40:
                    title_part_two = self.currently_selected_object.node.text[0:40] + "..."
                new_title = self.currently_selected_object.object_type().title() + ": " + title_part_two
                self.main_window.tag_list_group.setTitle(new_title)
                self.main_window.parent_tags.clear()
                self.main_window.parent_tags.setEnabled(False)
                if self.currently_selected_object.object_type() == "phoneme":
                    parent_word = self.currently_selected_object.node.get_parent()
                    parent_phrase = parent_word.get_parent()
                    word_tags = parent_word.tags
                    phrase_tags = parent_phrase.tags
                    if word_tags or phrase_tags:
                        self.main_window.parent_tags.setEnabled(True)
                    if phrase_tags:
                        list_of_phrase_tags = []
                        for tag in phrase_tags:
                            new_tag = QtWidgets.QTreeWidgetItem([tag])
                            list_of_phrase_tags.append(new_tag)
                        phrase_tree = QtWidgets.QTreeWidgetItem([self.translator.translate("WaveformView", "Phrase: ") + parent_phrase.text])
                        phrase_tree.addChildren(list_of_phrase_tags)
                        self.main_window.parent_tags.addTopLevelItem(phrase_tree)
                        phrase_tree.setExpanded(True)
                    if word_tags:
                        list_of_word_tags = []
                        for tag in word_tags:
                            new_tag = QtWidgets.QTreeWidgetItem([tag])
                            list_of_word_tags.append(new_tag)
                        word_tree = QtWidgets.QTreeWidgetItem([self.translator.translate("WaveformView", "Word: ") + parent_word.text])
                        word_tree.addChildren(list_of_word_tags)
                        self.main_window.parent_tags.addTopLevelItem(word_tree)
                        word_tree.setExpanded(True)
                elif self.currently_selected_object.object_type() == "word":
                    parent_phrase = self.currently_selected_object.node.get_parent()
                    parent_tags = parent_phrase.tags
                    list_of_tags = []
                    if parent_tags:
                        self.main_window.parent_tags.setEnabled(True)
                        for tag in parent_tags:
                            new_tag = QtWidgets.QTreeWidgetItem([tag])
                            list_of_tags.append(new_tag)
                        phrase_tree = QtWidgets.QTreeWidgetItem([self.translator.translate("WaveformView", "Phrase: ") + parent_phrase.text])
                        phrase_tree.addChildren(list_of_tags)
                        self.main_window.parent_tags.addTopLevelItem(phrase_tree)
                        phrase_tree.setExpanded(True)
                else:
                    self.main_window.parent_tags.setEnabled(False)
        event.accept()
        super(WaveformView, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_scrubbing:
            self.is_scrubbing = False
            self.doc.sound.stop()
            self.temp_play_marker.setVisible(False)
            self.main_window.mouth_view.set_frame(0)
        super(WaveformView, self).mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_scrubbing:
            mouse_scene_pos = self.mapToScene(event.pos()).x()
            if not self.doc.sound.is_playing():
                start = round(mouse_scene_pos / self.frame_width) / self.doc.fps
                length = self.frame_width / self.doc.fps
                self.doc.sound.play_segment(start, length)
            self.draw_play_marker = True
            self.temp_play_marker.setVisible(True)
            self.temp_play_marker.setPos(round(mouse_scene_pos / self.frame_width) * self.frame_width, 0)
            self.main_window.mouth_view.set_frame(round(mouse_scene_pos / self.frame_width))
        else:
            super(WaveformView, self).mouseMoveEvent(event)

    def dragMoveEvent(self, e):
        if not self.doc.sound.is_playing():
            if e.source():
                position = e.pos()
                if self.width() > self.sceneRect().width():
                    new_x = e.pos().x() + self.horizontalScrollBar().value() - \
                            ((self.width() - self.sceneRect().width()) / 2) - e.source().hot_spot
                else:
                    new_x = e.pos().x() + self.horizontalScrollBar().value() - e.source().hot_spot
                dropped_widget = e.source()
                if new_x >= dropped_widget.node.get_left_max() * self.frame_width:
                    if new_x + dropped_widget.width() <= dropped_widget.node.get_right_max() * self.frame_width:
                        x_diff = 0
                        dropped_widget.move(new_x, dropped_widget.y())
                        # after moving save the position and align to the grid based on that. Hacky but works!
                        if dropped_widget.is_phoneme():
                            x_diff = round(
                                dropped_widget.x() / self.frame_width) - dropped_widget.node.start_frame
                            dropped_widget.node.start_frame = round(new_x / self.frame_width)
                            dropped_widget.move(dropped_widget.node.start_frame * self.frame_width,
                                                dropped_widget.y())
                        else:
                            x_diff = round(
                                dropped_widget.x() / self.frame_width) - dropped_widget.node.start_frame
                            dropped_widget.node.start_frame = round(dropped_widget.x() / self.frame_width)
                            dropped_widget.end_frame = round(
                                (dropped_widget.x() + dropped_widget.width()) / self.frame_width)
                            dropped_widget.move(dropped_widget.node.start_frame * self.frame_width,
                                                dropped_widget.y())
                            # Move the children!
                        dropped_widget.reposition_descendants(False, x_diff)
                        self.doc.dirty = True
        e.accept()

    def set_frame(self, frame):
        if self.temp_play_marker not in self.scene().items():
            self.temp_play_marker = self.scene().addRect(0, 1, self.frame_width + 1, self.height(),
                                                         QtGui.QPen(QtGui.QColor(
                                                             self.settings.get(
                                                                 "/Graphics/{}".format("playback_line_color"),
                                                                 utilities.original_colors[
                                                                     "playback_line_color"]))),
                                                         QtGui.QBrush(QtGui.QColor(
                                                             self.settings.get(
                                                                 "/Graphics/{}".format("playback_fill_color"),
                                                                 utilities.original_colors[
                                                                     "playback_fill_color"])), QtCore.Qt.BrushStyle.SolidPattern))
            self.temp_play_marker.setZValue(1000)
            self.temp_play_marker.setOpacity(0.5)
            self.temp_play_marker.setVisible(True)
        self.centerOn(self.temp_play_marker)
        self.temp_play_marker.setPos(frame * self.frame_width, 0)
        self.update()
        self.scene().update()

    def drawBackground(self, painter, rect):
        background_brush = QtGui.QBrush(
            QtGui.QColor(self.settings.get("/Graphics/{}".format("bg_fill_color"),
                                             utilities.original_colors["bg_fill_color"])),
            QtCore.Qt.BrushStyle.SolidPattern)
        painter.fillRect(rect, background_brush)
        if self.doc is not None:
            pen = QtGui.QPen(
                QtGui.QColor(self.settings.get("/Graphics/{}".format("frame_color"),
                                             utilities.original_colors["frame_color"])))
            # pen.setWidth(5)
            painter.setPen(pen)
            painter.setFont(font)

            first_sample = 0
            last_sample = len(self.amp)
            bg_height = self.height() + self.horizontalScrollBar().height()
            half_client_height = bg_height / 2
            font_metrics = QtGui.QFontMetrics(font)
            text_width, top_border = font_metrics.horizontalAdvance("Ojyg"), font_metrics.height() * 2
            x = first_sample * self.sample_width
            frame = first_sample / self.samples_per_frame
            fps = int(round(self.doc.fps))
            sample = first_sample
            self.list_of_lines = []
            list_of_textmarkers = []
            for i in range(int(first_sample), int(last_sample)):
                if (i + 1) % self.samples_per_frame == 0:
                    frame_x = (frame + 1) * self.frame_width
                    if (self.frame_width > 2) or ((frame + 1) % fps == 0):
                        self.list_of_lines.append(QtCore.QLineF(frame_x, top_border, frame_x, bg_height))
                    # draw frame label
                    if (self.frame_width > 30) or ((int(frame) + 1) % 5 == 0):
                        self.list_of_lines.append(QtCore.QLineF(frame_x, 0, frame_x, top_border))
                        self.list_of_lines.append(QtCore.QLineF(frame_x + 1, 0, frame_x + 1, bg_height))
                        temp_rect = QtCore.QRectF(int(frame_x + 4), font_metrics.height() - 2, text_width, top_border)
                        # Positioning is a bit different in QT here
                        list_of_textmarkers.append((temp_rect, str(int(frame + 1))))
                x += self.sample_width
                sample += 1
                if sample % self.samples_per_frame == 0:
                    frame += 1
            painter.drawLines(self.list_of_lines)
            for text_marker in list_of_textmarkers:
                painter.drawText(text_marker[0], QtCore.Qt.AlignmentFlag.AlignLeft, text_marker[1])

    def start_create_waveform(self):
        # worker = utilities.Worker(self.create_waveform)
        # worker.signals.finished.connect(self.waveform_finished)
        # worker.signals.progress.connect(self.main_window.lip_sync_frame.status_bar_progress)

        self.main_window.lip_sync_frame.status_progress.show()
        available_height = int(self.height() / 2)
        fitted_samples = self.amp * available_height
        self.main_window.lip_sync_frame.status_progress.setMaximum(len(fitted_samples))
        self.create_waveform(self.main_window.lip_sync_frame.status_bar_progress)
        self.waveform_finished()
        # self.threadpool.start(worker)
        # self.threadpool.waitForDone()

    def waveform_finished(self):
        self.main_window.lip_sync_frame.status_progress.hide()
        update_rect = self.scene().sceneRect()
        update_rect.setHeight(self.size().height() - 1)
        if self.doc:
            update_rect.setWidth(self.waveform_polygon.polygon().boundingRect().width())
            self.setSceneRect(update_rect)
            self.scene().setSceneRect(update_rect)
            # We need to at least update the Y Position of the Phonemes
            font_metrics = QtGui.QFontMetrics(font)
            text_width, top_border = font_metrics.horizontalAdvance("Ojyg"), font_metrics.height() * 2
            text_width, text_height = font_metrics.horizontalAdvance("Ojyg"), font_metrics.height() + 6
            top_border += 4
        self.horizontalScrollBar().setValue(self.scroll_position)
        try:
            if self.temp_play_marker:
                self.temp_play_marker.setRect(self.temp_play_marker.rect().x(), 1, self.frame_width + 1, self.height())
        except RuntimeError:
            pass  # When changing a file we get a RuntimeError from QT because it deletes the temp_play_marker
        self.waveform_polygon.resetTransform()  # Change the transform back when resize is finished.
        self.scene().update()

    def create_waveform(self, progress_callback):
        available_height = int(self.height() / 2)
        fitted_samples = self.amp * available_height
        offset = 0  # available_height / 2
        temp_polygon = QtGui.QPolygonF()
        for x, y in enumerate(fitted_samples):
            progress_callback((x / 2))
            self.main_window.statusbar.showMessage(
                self.translator.translate("WaveformView", "Preparing Waveform: {0}%").format(str(int(((x / 2) / len(fitted_samples)) * 100))))
            temp_polygon.append(QtCore.QPointF(x * self.sample_width, available_height - y + offset))
            if x < len(fitted_samples):
                temp_polygon.append(QtCore.QPointF((x + 1) * self.sample_width, available_height - y + offset))
        for x, y in enumerate(fitted_samples[::-1]):
            progress_callback((len(fitted_samples) / 2) + (x / 2))
            self.main_window.statusbar.showMessage(
                self.translator.translate("WaveformView", "Preparing Waveform: {0}%").format(str(int(((x / 2) / len(fitted_samples)) * 100) + 50)))
            temp_polygon.append(QtCore.QPointF((len(fitted_samples) - x) * self.sample_width,
                                               available_height + y + offset))
            if x > 0:
                temp_polygon.append(QtCore.QPointF((len(fitted_samples) - x - 1) * self.sample_width,
                                                   available_height + y + offset))
        if self.waveform_polygon:
            self.waveform_polygon.setPolygon(temp_polygon)
        else:
            self.waveform_polygon = self.scene().addPolygon(temp_polygon, QtGui.QColor(
                self.settings.get("/Graphics/{}".format("wave_line_color"),
                                    utilities.original_colors["wave_line_color"])),
                                                            QtGui.QColor(
                                                                self.settings.get(
                                                                    "/Graphics/{}".format("wave_fill_color"),
                                                                    utilities.original_colors["wave_fill_color"])))
        self.waveform_polygon.setZValue(1)
        self.main_window.statusbar.showMessage("Papagayo-NG")

    def start_create_movbuttons(self):
        if self.doc is not None:
            # worker = Worker(self.create_movbuttons)
            # worker.signals.finished.connect(self.movbuttons_finished)
            # worker.signals.progress.connect(self.main_window.lip_sync_frame.status_bar_progress)

            self.main_window.lip_sync_frame.status_progress.show()
            self.main_window.lip_sync_frame.status_progress.setMaximum(self.doc.current_voice.num_children)
            # self.threadpool.start(worker)
            # self.threadpool.waitForDone()
            self.create_movbuttons(self.main_window.lip_sync_frame.status_bar_progress)

    def movbuttons_finished(self):
        self.main_window.lip_sync_frame.status_progress.hide()
        self.start_recalc()

    def create_movbuttons(self, progress_callback):
        if self.doc is not None:
            self.setUpdatesEnabled(False)
            font_metrics = QtGui.QFontMetrics(font)
            text_width, top_border = font_metrics.horizontalAdvance("Ojyg"), font_metrics.height() * 2
            text_width, text_height = font_metrics.horizontalAdvance("Ojyg"), font_metrics.height() + 6
            top_border += 4
            current_num = 0

            for phrase in self.doc.current_voice.children:
                if not phrase.move_button:
                    self.temp_button = MovableButton(phrase, self)
                    phrase.move_button = self.temp_button
                    # self.temp_button.node = Node(self.temp_button, parent=self.main_node)
                    temp_scene_widget = self.scene().addWidget(self.temp_button)
                    temp_rect = QtCore.QRect(phrase.start_frame * self.frame_width, top_border,
                                             (phrase.end_frame - phrase.start_frame) * self.frame_width + 1,
                                             text_height)
                    temp_scene_widget.setGeometry(temp_rect)
                    temp_scene_widget.setZValue(99)
                    self.temp_phrase = self.temp_button
                else:
                    try:
                        phrase.move_button.setVisible(True)
                    except RuntimeError:
                        self.temp_button = MovableButton(phrase, self)
                        phrase.move_button = self.temp_button
                        # self.temp_button.node = Node(self.temp_button, parent=self.main_node)
                        temp_scene_widget = self.scene().addWidget(self.temp_button)
                        temp_rect = QtCore.QRect(phrase.start_frame * self.frame_width, top_border,
                                                 (phrase.end_frame - phrase.start_frame) * self.frame_width + 1,
                                                 text_height)
                        temp_scene_widget.setGeometry(temp_rect)
                        temp_scene_widget.setZValue(99)
                        self.temp_phrase = self.temp_button
                word_count = 0
                current_num += 1
                progress_callback(current_num)
                if self.doc.current_voice.num_children:
                    self.main_window.statusbar.showMessage(self.translator.translate("WaveformView", "Preparing Buttons: {0}%").format(
                        str(int((current_num / self.doc.current_voice.num_children) * 100))))
                for word in phrase.children:
                    if not word.move_button:
                        self.temp_button = MovableButton(word, self)
                        word.move_button = self.temp_button
                        # self.temp_button.node = Node(self.temp_button, parent=self.temp_phrase.node)
                        temp_scene_widget = self.scene().addWidget(self.temp_button)
                        temp_rect = QtCore.QRect(word.start_frame * self.frame_width, top_border + 4 + text_height +
                                                 (text_height * (word_count % 2)), (word.end_frame - word.start_frame) *
                                                 self.frame_width + 1, text_height)
                        temp_scene_widget.setGeometry(temp_rect)
                        temp_scene_widget.setZValue(99)
                        self.temp_word = self.temp_button
                    else:
                        try:
                            word.move_button.setVisible(True)
                        except RuntimeError:
                            self.temp_button = MovableButton(word, self)
                            word.move_button = self.temp_button
                            # self.temp_button.node = Node(self.temp_button, parent=self.temp_phrase.node)
                            temp_scene_widget = self.scene().addWidget(self.temp_button)
                            temp_rect = QtCore.QRect(word.start_frame * self.frame_width, top_border + 4 + text_height +
                                                     (text_height * (word_count % 2)),
                                                     (word.end_frame - word.start_frame) *
                                                     self.frame_width + 1, text_height)
                            temp_scene_widget.setGeometry(temp_rect)
                            temp_scene_widget.setZValue(99)
                            self.temp_word = self.temp_button
                    word_count += 1
                    phoneme_count = 0
                    current_num += 1
                    progress_callback(current_num)
                    if self.doc.current_voice.num_children:
                        self.main_window.statusbar.showMessage(self.translator.translate("WaveformView", "Preparing Buttons: {0}%").format(
                            str(int((current_num / self.doc.current_voice.num_children) * 100))))
                    for phoneme in word.children:
                        if not phoneme.move_button:
                            self.temp_button = MovableButton(phoneme, self, phoneme_count % 2)
                            phoneme.move_button = self.temp_button
                            # self.temp_button.node = Node(self.temp_button, parent=self.temp_word.node)
                            temp_scene_widget = self.scene().addWidget(self.temp_button)
                            temp_rect = QtCore.QRect(phoneme.start_frame * self.frame_width, self.height() -
                                                     int(self.horizontalScrollBar().height() * 1.5) -
                                                     (text_height + (text_height * (phoneme_count % 2))),
                                                     self.frame_width, text_height)
                            temp_scene_widget.setGeometry(temp_rect)
                            temp_scene_widget.setZValue(99)
                            self.temp_phoneme = self.temp_button
                        else:
                            try:
                                phoneme.move_button.setVisible(True)
                            except RuntimeError:
                                self.temp_button = MovableButton(phoneme, self, phoneme_count % 2)
                                phoneme.move_button = self.temp_button
                                # self.temp_button.node = Node(self.temp_button, parent=self.temp_word.node)
                                temp_scene_widget = self.scene().addWidget(self.temp_button)
                                temp_rect = QtCore.QRect(phoneme.start_frame * self.frame_width, self.height() -
                                                         int(self.horizontalScrollBar().height() * 1.5) -
                                                         (text_height + (text_height * (phoneme_count % 2))),
                                                         self.frame_width, text_height)
                                temp_scene_widget.setGeometry(temp_rect)
                                temp_scene_widget.setZValue(99)
                                self.temp_phoneme = self.temp_button
                        phoneme_count += 1
                        current_num += 1
                        progress_callback(current_num)
                        if self.doc.current_voice.num_children:
                            self.main_window.statusbar.showMessage(
                                self.translator.translate("WaveformView", "Preparing Buttons: {0}%").format(
                                    str(int((current_num / self.doc.current_voice.num_children) * 100))))
            self.main_window.statusbar.showMessage("Papagayo-NG")
            self.setUpdatesEnabled(True)

    def start_recalc(self, wait_for_done=True):
        # worker = utilities.Worker(self.recalc_waveform)
        # worker.signals.finished.connect(self.recalc_finished)
        # worker.signals.progress.connect(self.main_window.lip_sync_frame.status_bar_progress)

        self.main_window.lip_sync_frame.status_progress.show()
        self.main_window.lip_sync_frame.status_progress.setMaximum(self.doc.sound.Duration())
        # self.threadpool.start(worker)
        # if wait_for_done:
        #     self.threadpool.waitForDone()
        self.recalc_waveform(self.main_window.lip_sync_frame.status_bar_progress)
        self.recalc_finished()

    def recalc_finished(self):
        self.main_window.lip_sync_frame.status_progress.hide()
        self.start_create_waveform()

    def recalc_waveform(self, progress_callback):
        duration = self.doc.sound.Duration()
        time_pos = 0.0
        sample_dur = 1.0 / self.samples_per_sec
        max_amp = 0.0
        self.amp = []
        while time_pos < duration:
            progress_callback(time_pos)
            self.num_samples += 1
            amp = self.doc.sound.get_rms_amplitude(time_pos, sample_dur)
            self.amp.append(amp)
            max_amp = max(max_amp, amp)
            time_pos += sample_dur
        self.amp = normalize(self.amp)

    def set_document(self, document, force=False, clear_scene=False):
        if document != self.doc or force:
            if document != self.doc or clear_scene:
                self.scene().clear()
                self.waveform_polygon = None
            self.doc = document
            if (self.doc is not None) and (self.doc.sound is not None):
                for l_object in self.doc.project_node.descendants:
                    try:
                        if l_object.move_button:
                            l_object.move_button.setVisible(False)
                    except RuntimeError:
                        pass
                self.create_movbuttons(self.main_window.lip_sync_frame.status_bar_progress)
                self.start_recalc()
                if self.temp_play_marker not in self.scene().items():
                    self.temp_play_marker = self.scene().addRect(0, 1, self.frame_width + 1, self.height(),
                                                                 QtGui.QPen(QtGui.QColor(
                                                                     self.settings.get(
                                                                         "/Graphics/{}".format("playback_line_color"),
                                                                         utilities.original_colors[
                                                                             "playback_line_color"]))),
                                                                 QtGui.QBrush(QtGui.QColor(
                                                                     self.settings.get(
                                                                         "/Graphics/{}".format("playback_fill_color"),
                                                                         utilities.original_colors[
                                                                             "playback_fill_color"])),
                                                                     QtCore.Qt.BrushStyle.SolidPattern))
                    self.temp_play_marker.setZValue(1000)
                    self.temp_play_marker.setOpacity(0.5)
                    self.temp_play_marker.setVisible(False)
                self.setViewportUpdateMode(QtWidgets.QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
                self.scene().update()

    def on_slider_change(self, value):
        self.scroll_position = value

    def wheelEvent(self, event):
        self.scroll_position = self.horizontalScrollBar().value() + (event.angleDelta().y() / 1.2)
        self.horizontalScrollBar().setValue(self.scroll_position)

    def resize_finished(self):
        self.start_create_waveform()

    def resizeEvent(self, event):
        update_rect = self.scene().sceneRect()
        width_factor = 1  # Only the height needs to change.
        try:
            height_factor = event.size().height() / event.oldSize().height()
        except ZeroDivisionError:
            height_factor = 1
        update_rect.setHeight(event.size().height())
        if self.doc:
            update_rect.setWidth(self.waveform_polygon.polygon().boundingRect().width())
            self.setSceneRect(update_rect)
            self.scene().setSceneRect(update_rect)
            origin_x, origin_y = 0, 0
            height_factor = height_factor * self.waveform_polygon.transform().m22()  # We need to add the factors
            self.waveform_polygon.setTransform(QtGui.QTransform().translate(
                origin_x, origin_y).scale(width_factor, height_factor).translate(-origin_x, -origin_y))
            # We need to at least update the Y Position of the Phonemes
            font_metrics = QtGui.QFontMetrics(font)
            text_width, top_border = font_metrics.horizontalAdvance("Ojyg"), font_metrics.height() * 2
            text_width, text_height = font_metrics.horizontalAdvance("Ojyg"), font_metrics.height() + 6
            top_border += 4
            for phoneme_node in self.doc.current_voice.leaves:  # this should be all phonemes
                if phoneme_node.move_button:
                    widget = phoneme_node.move_button
                    if widget.is_phoneme():  # shouldn't be needed, just to be sure
                        widget.setGeometry(widget.x(), self.height() - (self.horizontalScrollBar().height() * 1.5) -
                                           (text_height + (text_height * widget.phoneme_offset)), self.frame_width + 5,
                                           text_height)
            self.resize_timer.start(150)
        self.horizontalScrollBar().setValue(self.scroll_position)
        if self.temp_play_marker:
            self.temp_play_marker.setRect(self.temp_play_marker.rect().x(), 1, self.frame_width + 1, self.height())

    def on_zoom_in(self, event=None):
        if (self.doc is not None) and (self.samples_per_frame < 16):
            self.samples_per_frame *= 2
            self.samples_per_sec = self.doc.fps * self.samples_per_frame
            self.frame_width = self.sample_width * self.samples_per_frame
            for node in self.doc.current_voice.descendants:
                node.move_button.after_reposition()
                node.move_button.fit_text_to_size()
            self.start_recalc()
            if self.temp_play_marker:
                self.temp_play_marker.setRect(self.temp_play_marker.rect().x(), 1, self.frame_width + 1, self.height())
            self.scene().setSceneRect(self.scene().sceneRect().x(), self.scene().sceneRect().y(),
                                      self.sceneRect().width() * 2, self.scene().sceneRect().height())
            self.setSceneRect(self.scene().sceneRect())
            self.scroll_position *= 2
            self.horizontalScrollBar().setValue(self.scroll_position)
            self.start_create_waveform()

    def on_zoom_out(self, event=None):
        if (self.doc is not None) and (self.samples_per_frame > 1):
            self.samples_per_frame /= 2
            self.samples_per_sec = self.doc.fps * self.samples_per_frame
            self.frame_width = self.sample_width * self.samples_per_frame
            for node in self.doc.current_voice.descendants:
                node.move_button.after_reposition()
                node.move_button.fit_text_to_size()
            self.start_recalc()
            if self.temp_play_marker:
                self.temp_play_marker.setRect(self.temp_play_marker.rect().x(), 1, self.frame_width + 1, self.height())
            self.scene().setSceneRect(self.scene().sceneRect().x(), self.scene().sceneRect().y(),
                                      self.scene().sceneRect().width() / 2, self.scene().sceneRect().height())
            self.setSceneRect(self.scene().sceneRect())
            self.scroll_position /= 2
            self.horizontalScrollBar().setValue(self.scroll_position)
            self.start_create_waveform()

    def on_zoom_reset(self, event=None):
        if self.doc is not None:
            if self.samples_per_frame != self.default_samples_per_frame:
                self.scroll_position /= (self.samples_per_frame / self.default_samples_per_frame)
                factor = (self.samples_per_frame / self.default_samples_per_frame)
                self.sample_width = self.default_sample_width
                self.samples_per_frame = self.default_samples_per_frame
                self.samples_per_sec = self.doc.fps * self.samples_per_frame
                self.frame_width = self.sample_width * self.samples_per_frame
                for node in self.doc.current_voice.descendants:
                    node.move_button.after_reposition()
                    node.move_button.fit_text_to_size()
                self.start_recalc()
                if self.temp_play_marker:
                    self.temp_play_marker.setRect(self.temp_play_marker.rect().x(), 1, self.frame_width + 1,
                                                  self.height())
                self.scene().setSceneRect(self.scene().sceneRect().x(), self.scene().sceneRect().y(),
                                          self.scene().sceneRect().width() / factor, self.scene().sceneRect().height())
                self.setSceneRect(self.scene().sceneRect())
                self.horizontalScrollBar().setValue(self.scroll_position)
                self.start_create_waveform()