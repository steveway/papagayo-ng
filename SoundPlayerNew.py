import audioop
import logging
import platform
import time
import utilities
import os

if platform.system() == "Windows":
    os.environ['QT_MULTIMEDIA_PREFERRED_PLUGINS'] = 'windowsmediafoundation'
if utilities.get_app_data_path() not in os.environ['PATH']:
    os.environ['PATH'] += os.pathsep + utilities.get_app_data_path()
import audioread
import soundfile
import struct

from PySide2.QtCore import QCoreApplication
from PySide2.QtCore import QUrl
from PySide2.QtMultimedia import QMediaPlayer
from cffi import FFI

ffi = FFI()

try:
    import thread
except ImportError:
    import _thread as thread
AudioSegment = None


class SoundPlayer:
    def __init__(self, sound_file_path):
        self.sound_file_chunk = None
        self.sound_file_path = sound_file_path
        """Instead of loading the whole file at once we load it in chunks to save memory."""
        """This uses the soundfile library to read the file in chunks."""
        self.sound_file = soundfile.SoundFile(self.sound_file_path)
        self.sound_file_length = self.sound_file.duration
        self.sound_file_channels = self.sound_file.channels
        self.sound_file_sample_rate = self.sound_file.samplerate
        self.sound_file_sample_width = self.sound_file.subtype
        self.sound_file_sample_width_bytes = self.sound_file_sample_width / 8
        self.player = QMediaPlayer()
        self.player.setVolume(100)
        self.player.setMedia(QUrl.fromLocalFile(self.sound_file_path))
        while not self.is_loaded():
            QCoreApplication.processEvents()
            time.sleep(0.1)

    def load_sound_file_chunk(self, start_time, end_time):
        """Loads a chunk of the sound file."""
        self.sound_file.seek(start_time)
        self.sound_file_chunk = self.sound_file.read(end_time - start_time)
        """Returns the chunk of the sound file."""
        return self.sound_file_chunk

    def calculate_rms_of_chunk(self, chunk):
        """Calculates the rms of a chunk of the sound file."""
        """Returns the rms of the chunk."""
        return audioop.rms(chunk, self.sound_file_sample_width)

    def play_sound_file_part(self, start_time, end_time):
        """Plays a part of the sound file."""
        self.player.setPosition(start_time * 1000)
        self.player.play()
        """Waits until the end of the part is reached using a thread."""
        thread.start_new_thread(self.wait_until_end_of_part, (end_time,))

    def wait_until_end_of_part(self, end_time):
        """Waits until the end of the part is reached."""
        while self.player.position() < end_time * 1000:
            if not self.is_playing():
                break
            time.sleep(0.01)
            QCoreApplication.processEvents()

    def is_playing(self):
        """Returns true if the sound file is playing."""
        return self.player.state() == QMediaPlayer.PlayingState

    def play_sound_file(self):
        """Plays the sound file."""
        self.player.play()

    def stop_sound_file(self):
        """Stops the sound file."""
        self.player.stop()

    def is_loaded(self):
        """Returns true if the sound file is loaded."""
        return self.player.mediaStatus() == QMediaPlayer.LoadedMediaStatus

    def set_volume(self, volume):
        """Sets the volume of the sound file."""
        self.player.setVolume(volume)


class SoundPlayer:
    def __init__(self, soundfile, parent):
        self.soundfile = soundfile
        self.isplaying = False
        self.time = 0  # current audio position in frames
        self.audio = QMediaPlayer()
        self.is_loaded = False
        self.volume = 100
        self.isplaying = False
        self.max_bits = 32768
        # File Loading is Asynchronous, so we need to be creative here, doesn't need to be duration but it works
        self.audio.durationChanged.connect(self.on_durationChanged)
        # self.decoder.finished.connect(self.decode_finished_signal)
        self.audio.setMedia(QUrl.fromLocalFile(soundfile))
        # self.decoder.setSourceFilename(soundfile)  # strangely inconsistent file-handling
        # It will hang here forever if we don't process the events.
        self.audio_file = audioread.audio_open(self.soundfile)
        self.audio_data = []
        for buf in self.audio_file:
            self.audio_data.extend(struct.unpack("<{}H".format(int(len(list(buf)) / 2)), buf))
        while not self.is_loaded:
            QCoreApplication.processEvents()
            time.sleep(0.1)
        self.isvalid = True
        self.pydubfile = None
        if AudioSegment:
            if utilities.which("ffmpeg") is not None:
                AudioSegment.converter = utilities.which("ffmpeg")
            elif utilities.which("avconv") is not None:
                AudioSegment.converter = utilities.which("avconv")
            else:
                if platform.system() == "Windows":
                    AudioSegment.converter = os.path.join(utilities.get_app_data_path(), "ffmpeg.exe")
                    # AudioSegment.converter = os.path.dirname(os.path.realpath(__file__)) + "\\ffmpeg.exe"
                else:
                    # TODO: Check if we have ffmpeg or avconv installed
                    AudioSegment.converter = "ffmpeg"

        self.isvalid = True

        # self.audio.play()

    def get_samples(self, start_frame, end_frame):
        pass

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
        if AudioSegment:
            return self.pydubfile[time_pos * 1000.0:(time_pos + sample_dur) * 1000.0].rms
        else:
            if time_pos > 0:
                sample_pos = int(self.audio_file.samplerate * time_pos)
            else:
                sample_pos = 0
            sample_end = int(sample_pos + sample_dur * self.audio_file.samplerate)
            return audioop.rms(struct.pack("<{}H".format(len(self.audio_data[sample_pos:sample_end])),
                                           *self.audio_data[sample_pos:sample_end]), 2)

    def is_playing(self):
        if self.audio.state() == QMediaPlayer.PlayingState:
            return True
        else:
            return False

    def set_cur_time(self, newtime):
        self.time = newtime * 1000.0
        self.audio.setPosition(self.time)

    def stop(self):
        self.isplaying = False
        self.audio.stop()

    def current_time(self):
        self.time = self.audio.position() / 1000.0
        return self.time

    def set_volume(self, newvolume):
        self.volume = newvolume
        self.audio.setVolume(self.volume)

    def play(self, arg):
        self.isplaying = True  # TODO: We should be able to replace isplaying with queries to self.audio.state()
        self.audio.play()

    def play_segment(self, start, length):
        logging.info("Playing Segment")
        if not self.isplaying:  # otherwise this gets kinda echo-y
            self.isplaying = True
            self.audio.setPosition(start * 1000.0)
            self.audio.play()
            thread.start_new_thread(self._wait_for_segment_end, (start, length))

    def _wait_for_segment_end(self, newstart, newlength):
        start = newstart * 1000.0
        length = newlength * 1000.0
        end = start + length
        while self.audio.position() < end:
            if not self.isplaying:
                return 0
            QCoreApplication.processEvents()
            time.sleep(0.001)
        self.audio.stop()
        self.isplaying = False
