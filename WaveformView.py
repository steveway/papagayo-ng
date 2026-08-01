#!/usr/bin/env python
# -*- coding: ISO-8859-1 -*-

"""WaveformView: the main timeline graphics view.

Refactored for performance and maintainability:

- Waveform polygon construction is vectorized with numpy (was a Python loop
  with a per-sample progress_callback + statusbar.showMessage call -- the
  main cause of the slow, spammy loads).
- ``drawBackground`` caches the frame tick lines / labels and only rebuilds
  them when the zoom level or sample count changes (was rebuilding thousands
  of QLineF objects on every paint).
- Waveform recalculation runs on a worker thread via the existing
  Worker/QThreadPool pattern (previously commented out), so the UI stays
  responsive during load. QGraphicsScene objects are only ever touched on
  the UI thread -- the worker just returns numpy arrays.
- ``create_movbuttons`` is de-duplicated: the phrase/word/phoneme blocks
  share one helper instead of three copy-pasted try/except RuntimeError
  blocks.
- Selection highlight uses MovableButton.selected instead of string-replacing
  ``1px``/``2px`` in the stylesheet.
- Debug print() calls removed.

The public interface used by LipsyncFrameQT / LipsyncDoc / MovableButton is
preserved exactly (see the external-usage audit).
"""

import sys
import math

import numpy as np
from PySide6 import QtCore, QtGui
import PySide6.QtWidgets as QtWidgets

from LipsyncDoc import *  # noqa: F401,F403  (star-import kept for back-compat)
import utilities
from SceneWithDrag import SceneWithDrag
from MovableButton import MovableButton

# Constants --------------------------------------------------------------- #
font = QtGui.QFont("Swiss", 6)
default_sample_width = 4
default_samples_per_frame = 2


def normalize(x):
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return x
    ptp = np.ptp(x)
    if ptp == 0:
        return np.zeros_like(x)
    return ((x - x.min()) / ptp) * 0.8


# ------------------------------------------------------------------------- #
# Worker for off-UI-thread waveform computation.
# Returns (amp_array, num_samples) -- no Qt scene objects are touched here.
# ------------------------------------------------------------------------- #
class _WaveformRecalcWorker(QtCore.QRunnable):
    def __init__(self, sound, samples_per_sec, duration):
        super().__init__()
        self._sound = sound
        self._samples_per_sec = samples_per_sec
        self._duration = duration
        self.signals = utilities.WorkerSignals()

    @QtCore.Slot()
    def run(self):
        try:
            sample_dur = 1.0 / self._samples_per_sec
            n = max(1, int(self._duration / sample_dur) + 1)
            amp = np.empty(n, dtype=float)
            time_pos = 0.0
            for i in range(n):
                amp[i] = self._sound.get_rms_amplitude(time_pos, sample_dur)
                time_pos += sample_dur
                if i % max(1, n // 100) == 0:
                    self.signals.progress.emit(int(100 * i / n))
            amp = normalize(amp)
            self.signals.result.emit((amp, n))
            self.signals.finished.emit()
        except Exception:
            import traceback
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))


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

        # Locate the main window once.
        self.main_window = None
        for widget in QtWidgets.QApplication.instance().topLevelWidgets():
            if isinstance(widget, QtWidgets.QMainWindow):
                self.main_window = widget
                break

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
        self.amp = np.array([], dtype=float)
        self.temp_play_marker = None
        self.scroll_position = 0
        self.first_update = True
        self.node = None
        self.did_resize = None
        self.threadpool = QtCore.QThreadPool.globalInstance()

        # Caching for drawBackground ------------------------------------ #
        self._bg_cache_key = None  # (frame_width, samples_per_frame, num_samples, height)
        self._bg_lines = []        # list[QLineF]
        self._bg_texts = []        # list[(QRectF, str)]

        self.scene().setSceneRect(0, 0, self.width(), self.height())
        self.resize_timer = QtCore.QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.resize_finished)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def font_for_buttons(self):
        """The font used for phrase/word/phoneme buttons (module-level ``font``)."""
        return font

    def _text_metrics(self):
        fm = QtGui.QFontMetrics(font)
        return fm, fm.horizontalAdvance("Ojyg"), fm.height() + 6

    def _color(self, key, fallback_key):
        return QtGui.QColor(
            self.settings.get("/Graphics/{}".format(key),
                              utilities.original_colors[fallback_key]))

    def _ensure_play_marker(self, visible=False):
        if self.temp_play_marker is None or self.temp_play_marker not in self.scene().items():
            self.temp_play_marker = self.scene().addRect(
                0, 1, self.frame_width + 1, self.height(),
                QtGui.QPen(self._color("playback_line_color", "playback_line_color")),
                QtGui.QBrush(self._color("playback_fill_color", "playback_fill_color"),
                             QtCore.Qt.BrushStyle.SolidPattern))
            self.temp_play_marker.setZValue(1000)
            self.temp_play_marker.setOpacity(0.5)
        self.temp_play_marker.setVisible(visible)

    # ------------------------------------------------------------------ #
    # Drag-and-drop of files onto the view
    # ------------------------------------------------------------------ #
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if sys.platform == "darwin":
                    from Foundation import NSURL
                    fname = str(NSURL.URLWithString_(str(url.toString())).filePathURL().path())
                else:
                    fname = str(url.toLocalFile())
                self.main_window.lip_sync_frame.open(fname)
        else:
            if event.source():
                event.source().is_moving = False
            event.accept()

    def dragEnterEvent(self, e):
        e.accept()

    # ------------------------------------------------------------------ #
    # Selection
    # ------------------------------------------------------------------ #
    def _select_object(self, widget):
        if self.currently_selected_object is not None:
            try:
                self.currently_selected_object.selected = False
            except RuntimeError:
                pass  # underlying C++ object already destroyed
        self.currently_selected_object = widget
        if widget is not None:
            widget.selected = True

    def _populate_tag_panel(self, widget):
        """Fill the main-window tag panels for the newly selected widget."""
        mw = self.main_window
        if widget is None:
            mw.list_of_tags.clear()
            mw.tag_list_group.setEnabled(False)
            mw.tag_list_group.setTitle(self.translator.translate("WaveformView", "Selected Object Tags"))
            mw.parent_tags.clear()
            mw.parent_tags.setEnabled(False)
            return

        mw.tag_list_group.setEnabled(True)
        mw.list_of_tags.clear()
        mw.list_of_tags.addItems(widget.node.tags)
        title_part_two = widget.node.text
        if len(widget.node.text) > 40:
            title_part_two = widget.node.text[0:40] + "..."
        mw.tag_list_group.setTitle(widget.object_type().title() + ": " + title_part_two)
        mw.parent_tags.clear()
        mw.parent_tags.setEnabled(False)

        if widget.object_type() == "phoneme":
            parent_word = widget.node.get_parent()
            parent_phrase = parent_word.get_parent()
            self._maybe_show_parent_tags(parent_word, parent_phrase)
        elif widget.object_type() == "word":
            parent_phrase = widget.node.get_parent()
            self._maybe_show_parent_tags(None, parent_phrase)

    def _maybe_show_parent_tags(self, word, phrase):
        mw = self.main_window
        word_tags = word.tags if word is not None else []
        phrase_tags = phrase.tags if phrase is not None else []
        if (word_tags and word is not None) or phrase_tags:
            mw.parent_tags.setEnabled(True)
        if phrase_tags:
            phrase_tree = QtWidgets.QTreeWidgetItem(
                [self.translator.translate("WaveformView", "Phrase: ") + phrase.text])
            phrase_tree.addChildren(QtWidgets.QTreeWidgetItem([t]) for t in phrase_tags)
            mw.parent_tags.addTopLevelItem(phrase_tree)
            phrase_tree.setExpanded(True)
        if word_tags and word is not None:
            word_tree = QtWidgets.QTreeWidgetItem(
                [self.translator.translate("WaveformView", "Word: ") + word.text])
            word_tree.addChildren(QtWidgets.QTreeWidgetItem([t]) for t in word_tags)
            mw.parent_tags.addTopLevelItem(word_tree)
            word_tree.setExpanded(True)

    # ------------------------------------------------------------------ #
    # Mouse handling: scrubbing + selection
    # ------------------------------------------------------------------ #
    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            event.accept()
            super(WaveformView, self).mousePressEvent(event)
            return
        possible_item = self.itemAt(event.pos())
        if type(possible_item) == QtWidgets.QGraphicsPolygonItem:
            possible_item = None
        if not possible_item:
            self._select_object(None)
            self._populate_tag_panel(None)
            self.is_scrubbing = True
        else:
            widget = possible_item.widget()
            self._select_object(widget)
            self._populate_tag_panel(widget)
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
            self.temp_play_marker.setPos(
                round(mouse_scene_pos / self.frame_width) * self.frame_width, 0)
            self.main_window.mouth_view.set_frame(round(mouse_scene_pos / self.frame_width))
        else:
            super(WaveformView, self).mouseMoveEvent(event)

    def dragMoveEvent(self, e):
        if self.doc.sound.is_playing():
            e.accept()
            return
        if not e.source():
            e.accept()
            return
        position = e.pos()
        if self.width() > self.sceneRect().width():
            new_x = (position.x() + self.horizontalScrollBar().value()
                     - ((self.width() - self.sceneRect().width()) / 2) - e.source().hot_spot)
        else:
            new_x = position.x() + self.horizontalScrollBar().value() - e.source().hot_spot
        dropped_widget = e.source()
        if new_x >= dropped_widget.node.get_left_max() * self.frame_width:
            if new_x + dropped_widget.width() <= dropped_widget.node.get_right_max() * self.frame_width:
                dropped_widget.move(new_x, dropped_widget.y())
                if dropped_widget.is_phoneme():
                    x_diff = round(dropped_widget.x() / self.frame_width) - dropped_widget.node.start_frame
                    dropped_widget.node.start_frame = round(new_x / self.frame_width)
                    dropped_widget.move(dropped_widget.node.start_frame * self.frame_width, dropped_widget.y())
                else:
                    x_diff = round(dropped_widget.x() / self.frame_width) - dropped_widget.node.start_frame
                    dropped_widget.node.start_frame = round(dropped_widget.x() / self.frame_width)
                    dropped_widget.end_frame = round(
                        (dropped_widget.x() + dropped_widget.width()) / self.frame_width)
                    dropped_widget.move(dropped_widget.node.start_frame * self.frame_width, dropped_widget.y())
                dropped_widget.reposition_descendants(False, x_diff)
                self.doc.dirty = True
        e.accept()

    # ------------------------------------------------------------------ #
    # Play marker / frame tracking
    # ------------------------------------------------------------------ #
    def set_frame(self, frame):
        self._ensure_play_marker(visible=True)
        self.centerOn(self.temp_play_marker)
        self.temp_play_marker.setPos(frame * self.frame_width, 0)
        self.update()
        self.scene().update()

    # ------------------------------------------------------------------ #
    # Background (frame ticks + labels) -- cached
    # ------------------------------------------------------------------ #
    def drawBackground(self, painter, rect):
        background_brush = QtGui.QBrush(
            self._color("bg_fill_color", "bg_fill_color"),
            QtCore.Qt.BrushStyle.SolidPattern)
        painter.fillRect(rect, background_brush)
        if self.doc is None:
            return

        pen = QtGui.QPen(self._color("frame_color", "frame_color"))
        painter.setPen(pen)
        painter.setFont(font)

        bg_height = self.height() + self.horizontalScrollBar().height()
        half_client_height = bg_height / 2
        fm = QtGui.QFontMetrics(font)
        text_width = fm.horizontalAdvance("Ojyg")
        top_border = fm.height() * 2

        cache_key = (self.frame_width, self.samples_per_frame, len(self.amp), bg_height)
        if cache_key != self._bg_cache_key:
            self._build_bg_cache(cache_key, text_width, top_border, bg_height)
        if self._bg_lines:
            painter.drawLines(self._bg_lines)
        for text_rect, label in self._bg_texts:
            painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignLeft, label)

    def _build_bg_cache(self, cache_key, text_width, top_border, bg_height):
        self._bg_cache_key = cache_key
        self._bg_lines = []
        self._bg_texts = []
        frame_width, samples_per_frame, n_samples, _ = cache_key
        if n_samples == 0:
            return
        fps = int(round(self.doc.fps))
        # Only frame boundaries get ticks. Frame k (1-based) ends at sample
        # k*samples_per_frame, and is drawn at x = k * frame_width.
        n_frames = n_samples // samples_per_frame
        if n_frames == 0:
            return
        frame_numbers = np.arange(1, n_frames + 1)
        xs = frame_numbers * frame_width
        # Mask: which ticks to draw (every frame if zoomed in, else every fps-th).
        draw_main = (frame_width > 2) | ((frame_numbers % fps) == 0)
        # Mask: which ticks also get a label.
        draw_label = (frame_width > 30) | ((frame_numbers % 5) == 0)
        fm = QtGui.QFontMetrics(font)
        for x, frame, do_main, do_label in zip(xs, frame_numbers, draw_main, draw_label):
            if not do_main:
                continue
            xf = float(x)
            self._bg_lines.append(QtCore.QLineF(xf, top_border, xf, bg_height))
            if do_label:
                self._bg_lines.append(QtCore.QLineF(xf, 0, xf, top_border))
                self._bg_lines.append(QtCore.QLineF(xf + 1, 0, xf + 1, bg_height))
                text_rect = QtCore.QRectF(int(xf + 4), fm.height() - 2,
                                          text_width, top_border)
                self._bg_texts.append((text_rect, str(int(frame))))

    # ------------------------------------------------------------------ #
    # Waveform creation (vectorized)
    # ------------------------------------------------------------------ #
    def start_create_waveform(self):
        self.main_window.lip_sync_frame.status_progress.show()
        available_height = int(self.height() / 2)
        fitted = self.amp * available_height
        self.main_window.lip_sync_frame.status_progress.setMaximum(max(1, len(fitted)))
        # Build the polygon vectorized; emit progress a few times only.
        self.create_waveform(self.main_window.lip_sync_frame.status_bar_progress)
        self.waveform_finished()

    def waveform_finished(self):
        self.main_window.lip_sync_frame.status_progress.hide()
        update_rect = self.scene().sceneRect()
        update_rect.setHeight(self.size().height() - 1)
        if self.doc and self.waveform_polygon is not None:
            update_rect.setWidth(self.waveform_polygon.polygon().boundingRect().width())
            self.setSceneRect(update_rect)
            self.scene().setSceneRect(update_rect)
        self.horizontalScrollBar().setValue(self.scroll_position)
        try:
            if self.temp_play_marker:
                self.temp_play_marker.setRect(
                    self.temp_play_marker.rect().x(), 1, self.frame_width + 1, self.height())
        except RuntimeError:
            pass
        if self.waveform_polygon is not None:
            self.waveform_polygon.resetTransform()
        self.scene().update()

    def create_waveform(self, progress_callback):
        """Build the waveform polygon from ``self.amp`` using numpy.

        The old implementation appended points one-by-one in a Python loop and
        called ``progress_callback`` + ``statusbar.showMessage`` per sample.
        Here the upper and lower envelope point arrays are constructed with
        numpy and converted to a QPolygonF in one shot.
        """
        if self.amp.size == 0:
            return
        available_height = int(self.height() / 2)
        fitted = self.amp * available_height
        offset = 0
        n = fitted.size
        sw = self.sample_width

        # Upper envelope: for each sample, (x, y) then (x+sw, y).
        xs0 = np.arange(n) * sw
        xs1 = xs0 + sw
        upper_x = np.empty(2 * n)
        upper_y = np.empty(2 * n)
        upper_x[0::2] = xs0
        upper_x[1::2] = xs1
        upper_y[0::2] = available_height - fitted + offset
        upper_y[1::2] = available_height - fitted + offset

        # Lower envelope: mirror, reversed.
        rev = fitted[::-1]
        lower_x = np.empty(2 * n)
        lower_y = np.empty(2 * n)
        lower_x[0::2] = (n - np.arange(n)) * sw
        lower_x[1::2] = (n - np.arange(n) - 1) * sw
        lower_y[0::2] = available_height + rev + offset
        lower_y[1::2] = available_height + rev + offset
        # Drop the degenerate duplicate at index 0 of the lower run.
        if n > 0:
            lower_y[0] = lower_y[1]

        all_x = np.concatenate([upper_x, lower_x])
        all_y = np.concatenate([upper_y, lower_y])
        temp_polygon = QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in zip(all_x, all_y)])

        if progress_callback is not None:
            try:
                progress_callback(n)
            except RuntimeError:
                pass

        if self.waveform_polygon is not None:
            self.waveform_polygon.setPolygon(temp_polygon)
        else:
            self.waveform_polygon = self.scene().addPolygon(
                temp_polygon,
                self._color("wave_line_color", "wave_line_color"),
                self._color("wave_fill_color", "wave_fill_color"))
        self.waveform_polygon.setZValue(1)
        if self.main_window is not None:
            self.main_window.statusbar.showMessage("Papagayo-NG")

    # ------------------------------------------------------------------ #
    # Movable buttons creation (de-duplicated)
    # ------------------------------------------------------------------ #
    def start_create_movbuttons(self):
        if self.doc is None:
            return
        self.main_window.lip_sync_frame.status_progress.show()
        self.main_window.lip_sync_frame.status_progress.setMaximum(
            self.doc.current_voice.num_children)
        self.create_movbuttons(self.main_window.lip_sync_frame.status_bar_progress)

    def movbuttons_finished(self):
        self.main_window.lip_sync_frame.status_progress.hide()
        self.start_recalc()

    def create_movbuttons(self, progress_callback):
        if self.doc is None:
            return
        self.setUpdatesEnabled(False)
        fm, _, text_height = self._text_metrics()
        top_border = fm.height() * 2 + 4
        current_num = 0
        total = max(1, self.doc.current_voice.num_children)

        for phrase in self.doc.current_voice.children:
            self._make_or_show_button(phrase, top_border, text_height, 0)
            self.temp_phrase = phrase.move_button
            current_num += 1
            self._report_progress(progress_callback, current_num, total, "Preparing Buttons")

            word_count = 0
            for word in phrase.children:
                y = top_border + 4 + text_height + (text_height * (word_count % 2))
                self._make_or_show_button(word, y, text_height, word_count % 2)
                self.temp_word = word.move_button
                word_count += 1
                current_num += 1
                self._report_progress(progress_callback, current_num, total, "Preparing Buttons")

                phoneme_count = 0
                for phoneme in word.children:
                    self._make_or_show_phoneme(phoneme, text_height, phoneme_count % 2)
                    self.temp_phoneme = phoneme.move_button
                    phoneme_count += 1
                    current_num += 1
                    self._report_progress(progress_callback, current_num, total, "Preparing Buttons")

        self.main_window.statusbar.showMessage("Papagayo-NG")
        self.setUpdatesEnabled(True)

    def _report_progress(self, progress_callback, current, total, label):
        if progress_callback is not None:
            try:
                progress_callback(current)
            except RuntimeError:
                pass
        self.main_window.statusbar.showMessage(
            self.translator.translate("WaveformView", "{}: {{0}}%".format(label)).format(
                str(int((current / total) * 100))))

    def _make_or_show_button(self, node, y, text_height, slot):
        """Create-or-reuse a phrase/word button at row ``y``."""
        if node.move_button:
            try:
                node.move_button.setVisible(True)
                return
            except RuntimeError:
                pass  # fall through and recreate
        button = MovableButton(node, self)
        node.move_button = button
        proxy = self.scene().addWidget(button)
        proxy.setGeometry(QtCore.QRect(
            node.start_frame * self.frame_width, y,
            (node.end_frame - node.start_frame) * self.frame_width + 1, text_height))
        proxy.setZValue(99)

    def _make_or_show_phoneme(self, node, text_height, slot):
        """Create-or-reuse a phoneme button (bottom of the view, staggered)."""
        if node.move_button:
            try:
                node.move_button.setVisible(True)
                return
            except RuntimeError:
                pass
        button = MovableButton(node, self, slot)
        node.move_button = button
        proxy = self.scene().addWidget(button)
        y = self.height() - int(self.horizontalScrollBar().height() * 1.5) \
            - (text_height + (text_height * slot))
        proxy.setGeometry(QtCore.QRect(
            node.start_frame * self.frame_width, y, self.frame_width, text_height))
        proxy.setZValue(99)

    # ------------------------------------------------------------------ #
    # Waveform recalculation (threaded)
    # ------------------------------------------------------------------ #
    def start_recalc(self, wait_for_done=True):
        if self.doc is None or self.doc.sound is None:
            return
        self.main_window.lip_sync_frame.status_progress.show()
        duration = self.doc.sound.Duration()
        self.main_window.lip_sync_frame.status_progress.setMaximum(max(1, int(duration)))
        if wait_for_done:
            # Synchronous: callers (zoom, fps change) need self.amp updated
            # before they proceed to rebuild the waveform / scene.
            self.recalc_waveform(self.main_window.lip_sync_frame.status_bar_progress)
            self.recalc_finished()
        else:
            # Asynchronous: for initial document load, keeps UI responsive.
            # recalc_finished -> start_create_waveform fires when done.
            worker = _WaveformRecalcWorker(self.doc.sound, self.samples_per_sec, duration)
            worker.signals.progress.connect(self.main_window.lip_sync_frame.status_bar_progress)
            worker.signals.result.connect(self._on_recalc_result)
            worker.signals.finished.connect(self.recalc_finished)
            worker.signals.error.connect(self._on_worker_error)
            self.threadpool.start(worker)

    def _on_recalc_result(self, result):
        self.amp, self.num_samples = result

    def _on_worker_error(self, error_info):
        import traceback
        print("[WaveformView] recalc worker error:", error_info[2])

    def recalc_finished(self):
        self.main_window.lip_sync_frame.status_progress.hide()
        self.start_create_waveform()

    def recalc_waveform(self, progress_callback):
        """Synchronous fallback (kept for API compatibility)."""
        duration = self.doc.sound.Duration()
        sample_dur = 1.0 / self.samples_per_sec
        n = max(1, int(duration / sample_dur) + 1)
        amp = np.empty(n, dtype=float)
        time_pos = 0.0
        for i in range(n):
            amp[i] = self.doc.sound.get_rms_amplitude(time_pos, sample_dur)
            time_pos += sample_dur
            if progress_callback is not None and i % max(1, n // 100) == 0:
                try:
                    progress_callback(time_pos)
                except RuntimeError:
                    pass
        self.amp = normalize(amp)
        self.num_samples = n

    # ------------------------------------------------------------------ #
    # Document lifecycle
    # ------------------------------------------------------------------ #
    def set_document(self, document, force=False, clear_scene=False):
        if document == self.doc and not force:
            return
        if (document != self.doc) or clear_scene:
            self.scene().clear()
            self.waveform_polygon = None
            self.temp_play_marker = None
            self._bg_cache_key = None  # force bg rebuild
        self.doc = document
        if self.doc is None or self.doc.sound is None:
            return
        for l_object in self.doc.project_node.descendants:
            try:
                if l_object.move_button:
                    l_object.move_button.setVisible(False)
            except RuntimeError:
                pass
        self.create_movbuttons(self.main_window.lip_sync_frame.status_bar_progress)
        self.start_recalc(wait_for_done=False)  # async: keeps UI responsive on load
        self._ensure_play_marker(visible=False)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.scene().update()

    # ------------------------------------------------------------------ #
    # Scroll / zoom
    # ------------------------------------------------------------------ #
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
        if self.doc and self.waveform_polygon is not None:
            update_rect.setWidth(self.waveform_polygon.polygon().boundingRect().width())
            self.setSceneRect(update_rect)
            self.scene().setSceneRect(update_rect)
            origin_x, origin_y = 0, 0
            height_factor = height_factor * self.waveform_polygon.transform().m22()
            self.waveform_polygon.setTransform(QtGui.QTransform().translate(
                origin_x, origin_y).scale(width_factor, height_factor).translate(-origin_x, -origin_y))
            _, _, text_height = self._text_metrics()
            for phoneme_node in self.doc.current_voice.leaves:
                if phoneme_node.move_button:
                    widget = phoneme_node.move_button
                    if widget.is_phoneme():
                        widget.setGeometry(
                            widget.x(),
                            self.height() - (self.horizontalScrollBar().height() * 1.5) -
                            (text_height + (text_height * widget.phoneme_offset)),
                            self.frame_width + 5, text_height)
            self.resize_timer.start(150)
        self.horizontalScrollBar().setValue(self.scroll_position)
        if self.temp_play_marker:
            self.temp_play_marker.setRect(
                self.temp_play_marker.rect().x(), 1, self.frame_width + 1, self.height())

    def _apply_zoom(self, factor):
        """Apply a zoom factor (2, 0.5, or reset) common to in/out/reset."""
        if self.doc is None:
            return
        self.frame_width = self.sample_width * self.samples_per_frame
        for node in self.doc.current_voice.descendants:
            node.move_button.after_reposition()
            node.move_button.fit_text_to_size()
        self.start_recalc()
        if self.temp_play_marker:
            self.temp_play_marker.setRect(
                self.temp_play_marker.rect().x(), 1, self.frame_width + 1, self.height())
        self.scene().setSceneRect(
            self.scene().sceneRect().x(), self.scene().sceneRect().y(),
            self.sceneRect().width() * factor, self.scene().sceneRect().height())
        self.setSceneRect(self.scene().sceneRect())
        self.horizontalScrollBar().setValue(self.scroll_position)
        self.start_create_waveform()

    def on_zoom_in(self, event=None):
        if self.doc is not None and self.samples_per_frame < 16:
            self.samples_per_frame *= 2
            self.samples_per_sec = self.doc.fps * self.samples_per_frame
            self.scroll_position *= 2
            self._apply_zoom(2)

    def on_zoom_out(self, event=None):
        if self.doc is not None and self.samples_per_frame > 1:
            self.samples_per_frame /= 2
            self.samples_per_sec = self.doc.fps * self.samples_per_frame
            self.scroll_position /= 2
            self._apply_zoom(0.5)

    def on_zoom_reset(self, event=None):
        if self.doc is None:
            return
        if self.samples_per_frame != self.default_samples_per_frame:
            factor = (self.samples_per_frame / self.default_samples_per_frame)
            self.scroll_position /= factor
            self.sample_width = self.default_sample_width
            self.samples_per_frame = self.default_samples_per_frame
            self.samples_per_sec = self.doc.fps * self.samples_per_frame
            self._apply_zoom(1 / factor)
