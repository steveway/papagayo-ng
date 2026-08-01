#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-

"""MovableButton: a draggable/resizable QPushButton representing a lipsync object.

Refactored for clarity and performance:
- Style is data-driven (colors + border widths held as attributes, stylesheet
  rebuilt from a template) instead of fragile string-replacement of CSS.
- Selection highlight and tag-dashed-border are first-class states, not
  regex hacks on the stylesheet string.
- The Qt4/PyQt5 ``exec()`` compatibility hack for QDrag is gone (PySide6 only).
- Text truncation computes available width once instead of per-character.
- The public interface used by WaveformView / LipsyncFrameQT / LipsyncObject
  is preserved exactly (see the external-usage audit).
"""

import math
import time
from PySide6 import QtCore, QtGui
import PySide6.QtWidgets as QtWidgets
from PronunciationDialogQT import show_pronunciation_dialog
from LipsyncObject import LipSyncObject
import utilities
from settings_manager import SettingsManager


# Border-style tokens used when (re)building the stylesheet.
_SOLID = "solid solid solid solid"
_DASHED = "dashed solid dashed solid"


def _setting_color(settings, key, fallback_key):
    """Read a color setting, falling back to the original default color."""
    return QtGui.QColor(
        settings.get("/Graphics/{}".format(key),
                     utilities.original_colors[fallback_key]))


class MovableButton(QtWidgets.QPushButton):
    def __init__(self, lipsync_object, wfv_parent, phoneme_offset=None):
        super(MovableButton, self).__init__(lipsync_object.text, None)
        self.settings = SettingsManager.get_instance()
        self.title = lipsync_object.text
        self.node = lipsync_object
        self.phoneme_offset = phoneme_offset if phoneme_offset is not None else 0
        self.is_resizing = False
        self.is_moving = False
        self.resize_origin = 0  # 0 = left, 1 = right
        self.hot_spot = 0
        self.wfv_parent = wfv_parent
        self.setToolTip(lipsync_object.text)

        # Style state -----------------------------------------------------
        # Colors are resolved once from settings; the stylesheet is rebuilt
        # whenever selection / tag / handle-width state changes.
        self._fill_color = None
        self._line_color = None
        self._selected = False
        self._has_tags = bool(lipsync_object.tags)
        self._resolve_colors()
        self.node.tags = list(lipsync_object.tags)
        self._rebuild_stylesheet()

        self.setMinimumWidth(self.convert_to_pixels(1))
        self.fit_text_to_size()

    # ------------------------------------------------------------------ #
    # Style
    # ------------------------------------------------------------------ #
    def _resolve_colors(self):
        if self.is_phrase():
            self._fill_color = _setting_color(self.settings, "phrase_fill_color", "phrase_fill_color")
            self._line_color = _setting_color(self.settings, "phrase_line_color", "phrase_line_color")
        elif self.is_word():
            self._fill_color = _setting_color(self.settings, "word_fill_color", "word_fill_color")
            self._line_color = _setting_color(self.settings, "word_line_color", "word_line_color")
        elif self.is_phoneme():
            self._fill_color = _setting_color(self.settings, "phoneme_fill_color", "phoneme_fill_color")
            self._line_color = _setting_color(self.settings, "phoneme_line_color", "phoneme_line_color")

    def _rebuild_stylesheet(self):
        """Build the stylesheet from current state (colors, selection, tags)."""
        fill = self._fill_color.name() if self._fill_color else "#cccccc"
        line = self._line_color.name() if self._line_color else "#000000"
        border_width = 2 if self._selected else 1
        border_style = _DASHED if self._has_tags else _SOLID

        if self.is_phoneme():
            # Phonemes use a uniform 1px border (selection thickens it).
            bw = border_width
            self.setStyleSheet(
                "QPushButton {color: #000000; background-color:%s;"
                "border:%dpx solid %s;}" % (fill, bw, line))
        else:
            # Phrase/word: left/right handles are wider; top/bottom are 1px.
            handle = self.get_handle_width()
            self.setStyleSheet(
                "QPushButton {color: #000000; background-color:%s;"
                "border-color: %s;"
                "border-style: %s;"
                "border-width: %dpx %dpx %dpx %dpx;}" % (
                    fill, line, border_style,
                    border_width, handle, border_width, handle))

    @property
    def selected(self):
        return self._selected

    @selected.setter
    def selected(self, value):
        value = bool(value)
        if value != self._selected:
            self._selected = value
            self._rebuild_stylesheet()

    # ------------------------------------------------------------------ #
    # Type helpers
    # ------------------------------------------------------------------ #
    def is_phoneme(self):
        return self.node.object_type == "phoneme"

    def is_word(self):
        return self.node.object_type == "word"

    def is_phrase(self):
        return self.node.object_type == "phrase"

    def object_type(self):
        return self.node.object_type

    # ------------------------------------------------------------------ #
    # Geometry helpers
    # ------------------------------------------------------------------ #
    def convert_to_pixels(self, frame_pos):
        return frame_pos * self.wfv_parent.frame_width

    def convert_to_frames(self, pixel_pos):
        return pixel_pos / self.wfv_parent.frame_width

    def get_handle_width(self):
        resize_handle_width = 1.5
        return int(min(self.wfv_parent.frame_width * resize_handle_width,
                       self.convert_to_pixels(self.node.get_frame_size()) / 4))

    # ------------------------------------------------------------------ #
    # Text fitting
    # ------------------------------------------------------------------ #
    def text_size(self):
        return QtGui.QFontMetrics(self.font()).horizontalAdvance(self.title)

    def _available_width(self):
        """Pixel width available for text inside this button."""
        pad = self.convert_to_pixels(0.5)
        if self.is_phoneme():
            return self.convert_to_pixels(self.node.get_frame_size()) - pad
        return self.convert_to_pixels(self.node.get_frame_size()) + pad

    def text_fits_in_button(self):
        return self.text_size() < self._available_width()

    def fit_text_to_size(self):
        """Truncate the displayed title so it fits, using a single metrics pass.

        Previously this looped char-by-char re-asking ``text_fits_in_button``
        (which itself re-derived the available width each call). We now compute
        the available width once and binary-search the truncation length.
        """
        full = self.node.text
        fm = QtGui.QFontMetrics(self.font())
        avail = self._available_width()
        if fm.horizontalAdvance(full) <= avail:
            self.title = full
            self.setText(full)
            return
        # Binary search the longest prefix (with an ellipsis) that fits.
        lo, hi = 1, len(full)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if fm.horizontalAdvance(full[:mid]) <= avail:
                lo = mid
            else:
                hi = mid - 1
        self.title = full[:lo]
        self.setText(self.title)

    # ------------------------------------------------------------------ #
    # Repositioning
    # ------------------------------------------------------------------ #
    def after_reposition(self):
        self.setGeometry(self.convert_to_pixels(self.node.start_frame), self.y(),
                         self.convert_to_pixels(self.node.get_frame_size()), self.height())
        # Handle width depends on the (possibly changed) frame size.
        self._rebuild_stylesheet()
        self.update()

    def reposition_descendants(self, did_resize=False, x_diff=0):
        self.node.reposition_descendants(did_resize, x_diff)
        self.wfv_parent.doc.dirty = True

    def reposition_descendants2(self, did_resize=False, x_diff=0):
        self.node.reposition_descendants2(did_resize, x_diff)

    def reposition_to_left(self):
        self.node.reposition_to_left()
        self.after_reposition()
        self.wfv_parent.doc.dirty = True

    # ------------------------------------------------------------------ #
    # Tags
    # ------------------------------------------------------------------ #
    def set_tags(self, new_taglist):
        self.node.tags = new_taglist
        self.setToolTip("".join("{}\n".format(entry) for entry in self.node.tags)[:-1])
        self._has_tags = len(self.node.tags) > 0
        self._rebuild_stylesheet()

    # ------------------------------------------------------------------ #
    # Mouse / drag handling
    # ------------------------------------------------------------------ #
    def mousePressEvent(self, event):
        if self.wfv_parent.doc.sound.is_playing():
            return
        if event.button() == QtCore.Qt.MouseButton.RightButton and self.is_word():
            # Manually enter the pronunciation for this word.
            self._edit_pronunciation()
            return

    def _edit_pronunciation(self):
        prev_phoneme_list = ""
        for p in self.node.children:
            prev_phoneme_list += " " + p.text
        return_value = show_pronunciation_dialog(
            self, self.wfv_parent.doc.parent.phonemeset.set,
            self.node.text, prev_text=prev_phoneme_list)
        if not return_value or return_value == -1:
            return
        list_of_new_phonemes = return_value
        if list_of_new_phonemes == prev_phoneme_list.split():
            return
        # Remove old phoneme proxies from the scene.
        for proxy in self.wfv_parent.items():
            if isinstance(proxy, QtWidgets.QGraphicsProxyWidget):
                for old_node in self.node.children:
                    if proxy.widget() == old_node.move_button:
                        self.wfv_parent.scene().removeItem(proxy)
        self.node.children = []
        fm = QtGui.QFontMetrics(self.wfv_parent.font_for_buttons())
        text_height = fm.height() + 6
        for phoneme_count, p in enumerate(list_of_new_phonemes):
            phoneme = LipSyncObject(object_type="phoneme", parent=self.node)
            phoneme.text = p
            phoneme.start_frame = phoneme.end_frame = self.node.start_frame + phoneme_count
            temp_button = MovableButton(phoneme, self.wfv_parent, phoneme_count % 2)
            phoneme.move_button = temp_button
            temp_scene_widget = self.wfv_parent.scene().addWidget(temp_button)
            temp_rect = QtCore.QRect(
                phoneme.start_frame * self.wfv_parent.frame_width,
                int(self.wfv_parent.height() -
                    (self.wfv_parent.horizontalScrollBar().height() * 1.5) -
                    (text_height + (text_height * (phoneme_count % 2)))),
                self.wfv_parent.frame_width, text_height)
            temp_scene_widget.setGeometry(temp_rect)
            temp_scene_widget.setZValue(99)
        self.wfv_parent.doc.dirty = True

    def mouseMoveEvent(self, event):
        if self.wfv_parent.doc.sound.is_playing():
            return
        if event.buttons() != QtCore.Qt.MouseButton.LeftButton:
            return

        # Decide between resize and move based on cursor position.
        if not self.is_phoneme():
            global_x = self.x() + event.x()
            if global_x >= self.convert_to_pixels(self.node.end_frame) - self.get_handle_width():
                self.is_resizing = True
                self.resize_origin = 1
            elif global_x <= self.x() + self.get_handle_width():
                self.is_resizing = True
                self.resize_origin = 0
            else:
                self.is_resizing = False
        else:
            self.is_resizing = False

        if self.is_resizing:
            self._do_resize(event)
        else:
            self._do_drag(event)

    def _do_resize(self, event):
        self.wfv_parent.doc.dirty = True
        cursor_frame = self.convert_to_frames(event.x() + self.x())
        if self.resize_origin == 1:  # right edge
            if cursor_frame >= self.node.start_frame + self.node.get_min_size():
                if cursor_frame <= self.node.get_right_max():
                    self.node.end_frame = math.ceil(cursor_frame)
                    self.resize(self.convert_to_pixels(self.node.end_frame) -
                                self.convert_to_pixels(self.node.start_frame), self.height())
        else:  # left edge
            if cursor_frame < self.node.end_frame and cursor_frame >= self.node.get_left_max():
                self.node.start_frame = math.floor(cursor_frame)
                if self.node.get_frame_size() < self.node.get_min_size():
                    self.node.start_frame = self.node.end_frame - self.node.get_min_size()
                new_length = self.convert_to_pixels(self.node.end_frame) - \
                             self.convert_to_pixels(self.node.start_frame)
                self.resize(new_length, self.height())
                self.move(self.convert_to_pixels(self.node.start_frame), self.y())
        self.after_reposition()

    def _do_drag(self, event):
        self.is_moving = True
        mime_data = QtCore.QMimeData()
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime_data)
        drag.setHotSpot(event.pos() - self.rect().topLeft())
        self.hot_spot = drag.hotSpot().x()
        drag.exec(QtCore.Qt.DropAction.MoveAction)

    def mouseDoubleClickEvent(self, event):
        if self.wfv_parent.doc.sound.is_playing() or self.is_phoneme():
            return
        start = self.node.start_frame / self.wfv_parent.doc.fps
        length = (self.node.end_frame - self.node.start_frame) / self.wfv_parent.doc.fps
        self.wfv_parent.doc.sound.play_segment(start, length)
        old_cur_frame = 0
        start_time = 0
        self.wfv_parent.temp_play_marker.setVisible(True)
        mw = self.wfv_parent.main_window
        mw.action_stop.setEnabled(True)
        mw.action_play.setEnabled(False)
        while self.wfv_parent.doc.sound.is_playing():
            QtCore.QCoreApplication.processEvents()
            cur_frame = int(self.wfv_parent.doc.sound.current_time() * self.wfv_parent.doc.fps)
            if old_cur_frame != cur_frame:
                old_cur_frame = cur_frame
                mw.mouth_view.set_frame(old_cur_frame)
                self.wfv_parent.set_frame(old_cur_frame)
                try:
                    fps = 1.0 / (time.time() - start_time)
                except ZeroDivisionError:
                    fps = 60
                mw.statusbar.showMessage("Frame: {:d} FPS: {:d}".format((cur_frame + 1), int(fps)))
                self.wfv_parent.scroll_position = self.wfv_parent.horizontalScrollBar().value()
                start_time = time.time()
            self.wfv_parent.update()
        self.wfv_parent.temp_play_marker.setVisible(False)
        mw.action_stop.setEnabled(False)
        mw.action_play.setEnabled(True)
        mw.statusbar.showMessage("Stopped")
        mw.waveform_view.horizontalScrollBar().setValue(mw.waveform_view.scroll_position)
        mw.waveform_view.update()

    def mouseReleaseEvent(self, event):
        if self.is_moving:
            self.is_moving = False
        if self.is_resizing:
            self.reposition_descendants2(True)
            self.is_resizing = False
        if self.is_phoneme():
            self.wfv_parent.main_window.mouth_view.set_phoneme_picture(self.node.text)

    def __del__(self):
        try:
            self.deleteLater()
        except RuntimeError:
            pass
