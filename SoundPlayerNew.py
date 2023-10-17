import logging
import platform
import time

from PySide6.QtWidgets import QApplication

import utilities
import os
import numpy as np
if platform.system() == "Windows":
    os.environ['QT_MULTIMEDIA_PREFERRED_PLUGINS'] = 'windowsmediafoundation'
if utilities.get_app_data_path() not in os.environ['PATH']:
    os.environ['PATH'] += os.pathsep + utilities.get_app_data_path()

from PySide6 import QtWidgets
from PySide6.QtCore import QCoreApplication
from PySide6.QtCore import QUrl, QBuffer, QIODevice, QByteArray
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QAudioDecoder, QAudioFormat, QMediaDevices, QAudioSink
from cffi import FFI

ffi = FFI()

try:
    import thread
except ImportError:
    import _thread as thread

class SoundPlayer:
    def __init__(self, soundfile, parent):
        self.soundfile = soundfile
        self.time = 0  # current audio position in frames
        self.audio = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio.setAudioOutput(self.audio_output)
        self.decoder = QAudioDecoder()
        self.audio_format = QAudioFormat()
        self.audio_format.setSampleFormat(QAudioFormat.SampleFormat.UInt8)
        self.audio_format.setSampleRate(44100)
        self.audio_format.setChannelCount(1)
        self.decoder.setAudioFormat(self.audio_format)
        self.audio_device = QMediaDevices.audioOutputs()[0]
        self.audio_sink = QAudioSink(self.audio_device, self.audio_format)
        self.is_loaded = False
        self.volume = 100
        self.max_bits = 32768
        self.audio_sink_data = QBuffer()
        self.decoded_audio = {}
        self.only_samples = []
        self.num_channels = 1
        self.decoding_is_finished = False
        self.max_bits = 2 ** 8
        self.signed = False
        self.audio.mediaStatusChanged.connect(self.media_status_changed)
        self.audio.setSource(QUrl.fromLocalFile(soundfile))
        self.decoder.finished.connect(self.decode_finished_signal)
        self.decoder.setSource(QUrl.fromLocalFile(soundfile))  # strangely inconsistent file-handling
        self.audio.setPlaybackRate(1)
        self.audio_data = []
        self.top_level_widget = None

        for widget in QtWidgets.QApplication.topLevelWidgets():
            if "lip_sync_frame" in dir(widget):
                self.top_level_widget = widget
        self.top_level_widget.lip_sync_frame.status_progress.show()
        self.top_level_widget.lip_sync_frame.status_progress.reset()
        self.top_level_widget.lip_sync_frame.status_progress.setMinimum(0)
        self.top_level_widget.lip_sync_frame.status_progress.setMaximum(0)
        # It will hang here forever if we don't process the events.
        while not self.is_loaded:
            QCoreApplication.processEvents()
            time.sleep(0.1)
        self.decode_audio(self.top_level_widget.lip_sync_frame.status_bar_progress)
        self.top_level_widget.lip_sync_frame.status_progress.hide()
        self.np_data = np.array(self.only_samples)
        self.np_data = self.np_data - self.max_bits / 2
        self.audio_sink_data.setData(bytes(self.only_samples))
        self.audio_sink_data.open(QIODevice.ReadOnly)
        self.isvalid = True

    def get_samples(self, start_frame, end_frame):
        pass

    def audioformat_to_datatype(self, audioformat):
        self.num_channels = audioformat.channelCount()
        num_bits = audioformat.bytesPerSample() * 8
        signed = audioformat.sampleFormat()
        print("Number of Channels: {0}".format(audioformat.channelCount()))
        print("AudioFormat: {0}".format(audioformat))
        # print("num_bits: {0}, signed: {1}".format(num_bits, signed))
        # if signed == QAudioFormat.SampleFormat.Float:
        #     self.signed = False
        #     self.max_bits = 1
        #     return "float{0}_t".format(str(num_bits))
        if signed == QAudioFormat.SampleFormat.UInt8:
            print("UInt8")
            print("num_bits: {0}".format(num_bits))
            self.max_bits = 2 ** int(8)
            self.signed = False
            return "uint{0}_t".format(str(num_bits))
        elif signed == QAudioFormat.SampleFormat.Int16:
            print("Int16")
            print("num_bits: {0}".format(num_bits))
            self.max_bits = 2 ** int(16)
            self.signed = True
            return "int{0}_t".format(str(num_bits))
        elif signed == QAudioFormat.SampleFormat.Float:
            print("Float")
            print("num_bits: {0}".format(num_bits))
            self.max_bits = 1
            self.signed = False
            return "float"
    def decode_audio(self, progress_callback):
        self.decoder.start()
        while not self.decoding_is_finished:
            QCoreApplication.processEvents()
            if self.decoder.bufferAvailable():

                tempdata = self.decoder.read()
                if tempdata.isValid():
                    """Save the data from the buffer to our self.decoded_audio dict"""
                    if "data" not in dir(tempdata):
                        continue
                    else:
                        print("Decoding data")
                    # We use the Pointer Address to get a cffi Pointer to the data (hopefully)
                    cast_data = self.audioformat_to_datatype(tempdata.format())
                    # tempdata.detach()
                    if self.num_channels == 1:
                        possible_data = tempdata.constData()
                    else:
                        possible_data = tempdata.constData()
                        # possible_data = tempdata.constData()
                    # possible_data = ffi.cast("{1}[{0}]".format(tempdata.sampleCount(), cast_data),
                    #                          int(tempdata.data()))
                    # temp_bytes = QByteArray.fromRawData(possible_data, tempdata.byteCount())
                    self.only_samples.extend(possible_data)
                    #self.only_samples.append(tempdata.constData(), tempdata.byteCount())
                    self.decoded_audio[self.decoder.position()] = [possible_data, len(possible_data), tempdata.byteCount(),
                                                                   tempdata.format()]
            progress_callback(self.decoder.position())

    def decode_finished_signal(self):
        print("Decoding finished")
        self.decoding_is_finished = True
    def media_status_changed(self, status):
        logging.info("Media status changed to {}!".format(status))
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia,
                      QMediaPlayer.MediaStatus.BufferingMedia):
            self.is_loaded = True
        else:
            self.is_loaded = False

    def on_durationChanged(self, duration):
        logging.info("Duration changed to {}!".format(duration))
        self.is_loaded = True

    def get_audio_buffer(self, bufferdata):
        logging.info(bufferdata)

    def IsValid(self):
        return self.isvalid

    def Duration(self):
        return self.audio.duration() / 1000.0


    def GetRMSAmplitude(self, time_pos, sample_dur):
        # time_start = time_pos * (len(self.only_samples)/self.Duration())
        # time_end = (time_pos + sample_dur) * (len(self.only_samples)/self.Duration())
        # samples = self.only_samples[int(time_start):int(time_end)]
        time_start = time_pos * (len(self.np_data) / self.Duration())
        time_end = (time_pos + sample_dur) * (len(self.np_data) / self.Duration())
        samples = self.np_data[int(time_start):int(time_end)]

        if len(samples):
            print(np.sqrt(np.mean(samples ** 2)))
            return np.sqrt(np.mean(samples ** 2))
        else:
            return 1

    def is_playing(self):
        if self.audio.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            return True
        else:
            return False

    def set_cur_time(self, newtime):
        self.time = newtime * 1000
        self.audio.setPosition(int(self.time))

    def stop(self):
        self.audio.stop()

    def current_time(self):
        self.time = self.audio.position() / 1000.0
        return self.time

    def set_volume(self, newvolume):
        print("Volume: {}".format(newvolume))
        self.volume = newvolume
        # self.audio_output.setVolume(self.volume)
        self.audio.audioOutput().setVolume(self.volume / 100.0)

    def play(self, arg):
        self.audio.setPosition(0)
        self.audio.play()

    def is_playing(self):
        return self.audio.isPlaying()

    def play_segment(self, start, length):
        logging.info("Playing Segment")
        if not self.is_playing():  # otherwise this gets kinda echo-y
            print("Start Position: {}".format(start))
            self.audio.setPosition(int(start * 1000))
            self.audio.play()
            thread.start_new_thread(self._wait_for_segment_end, (start, length))

    def _wait_for_segment_end(self, newstart, newlength):
        start = newstart * 1000.0
        length = newlength * 1000.0
        end = start + length
        while self.audio.position() < end:
            if not self.is_playing():
                return 0
            QCoreApplication.processEvents()
            time.sleep(0.1)
        self.audio.stop()


if __name__ == "__main__":
    app = QApplication([])
    soundplayer = SoundPlayer(r"E:\PyCharmProjects\papagayo_clean\Tutorial Files\lame.wav", None)
    soundplayer.play(False)
