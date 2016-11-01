import audioop
import os
import platform
import traceback
import wave
from utilities import *
from tempfile import NamedTemporaryFile
import pyaudio
import io
from utilities import which

try:
    from pydub import AudioSegment, playback
    from pydub.utils import make_chunks
except ImportError:
    AudioSegment = None
    playback = None

try:
    import thread
except ImportError:
    import _thread as thread


class SoundPlayer:
    def __init__(self, soundfile, parent):
        self.soundfile = soundfile
        self.isplaying = False
        self.volume = 75
        self.mindb = 60
        self.maxdb = 24
        self.stepdb = (self.mindb-self.maxdb)/100.0
        self.time = 0  # current audio position in frames
        self.audio = pyaudio.PyAudio()
        self.tempsound = None
        if AudioSegment:
            if which("ffmpeg") is not None:
                AudioSegment.converter = which("ffmpeg")
            elif which("avconv") is not None:
                AudioSegment.converter = which("avconv")
            else:
                if platform.system() == "Windows":
                    AudioSegment.converter = os.path.join(get_main_dir(), "ffmpeg.exe")
                    #AudioSegment.converter = os.path.dirname(os.path.realpath(__file__)) + "\\ffmpeg.exe"
                else:
                    # TODO: Check if we have ffmpeg or avconv installed
                    AudioSegment.converter = "ffmpeg"

        try:
            if AudioSegment:
                print(self.soundfile)
                self.tempsound = AudioSegment.from_file(self.soundfile, format=os.path.splitext(self.soundfile)[1][1:])
                f = NamedTemporaryFile("w+b", suffix=".wav", delete=False)
                if self.volume <= 0:
                    self.volume = 0
                if self.volume > 100:
                    self.volume = 100
                self.maxdb = self.tempsound.max_dBFS*-100.0
                print("NewVolume: " + str(self.mindb-(self.stepdb*self.volume)))
                self.tempsound.apply_gain(-1*(self.mindb-(self.stepdb*self.volume))).export(f.name, "wav")
                f.close()
                self.wave_reference = wave.open(f.name, "rb")
            else:
                self.wave_reference = wave.open(self.soundfile)

            self.isvalid = True

        except:
            traceback.print_exc()
            self.wave_reference = None
            self.isvalid = False

    def IsValid(self):
        return self.isvalid

    def Duration(self):
        return float(self.wave_reference.getnframes()) / float(self.wave_reference.getframerate())

    def GetRMSAmplitude(self, time, sampleDur):
        startframe = int(round(time * self.wave_reference.getframerate()))
        samplelen = int(round(sampleDur * self.wave_reference.getframerate()))
        self.wave_reference.setpos(startframe)
        frame = self.wave_reference.readframes(samplelen)
        width = self.wave_reference.getsampwidth()
        return audioop.rms(frame, width)

    def ChangeVolume(self, newvolume):
        if AudioSegment:
            self.volume = newvolume
            f = NamedTemporaryFile("w+b", suffix=".wav", delete=False)
            if self.volume <= 0:
                self.volume = 0
            if self.volume > 100:
                self.volume = 100
            print("NewVolume: " + str(self.mindb - (self.stepdb * self.volume)))
            self.tempsound.apply_gain(-1 * (self.mindb - (self.stepdb * self.volume))).export(f.name, "wav")
            f.close()
            self.wave_reference = wave.open(f.name, "rb")
        else:
            pass

    def IsPlaying(self):
        return self.isplaying

    def SetCurTime(self, time):
        self.time = time

    def Stop(self):
        self.isplaying = False

    def CurrentTime(self):
        return self.time

    def _play(self, start, length):
        self.isplaying = True
        startframe = int(round(start * self.wave_reference.getframerate()))
        samplelen = int(round(length * self.wave_reference.getframerate()))
        remaining = samplelen
        chunk = 1024
        try:
            self.wave_reference.setpos(startframe)
        except wave.Error:
            self.isplaying = False
            return
        stream = self.audio.open(format=
                                 self.audio.get_format_from_width(self.wave_reference.getsampwidth()),
                                 channels=self.wave_reference.getnchannels(),
                                 rate=self.wave_reference.getframerate(),
                                 output=True)
        # read data

        if remaining >= 1024:
            data = self.wave_reference.readframes(chunk)
            remaining -= chunk
        else:
            data = self.wave_reference.readframes(remaining)
            remaining = 0

        # play stream
        while data != '' and self.isplaying:
            stream.write(data)
            self.time = float(self.wave_reference.tell()) / float(self.wave_reference.getframerate())
            if remaining >= 1024:
                data = self.wave_reference.readframes(chunk)
                remaining -= chunk
            else:
                data = self.wave_reference.readframes(remaining)
                remaining = 0

        stream.close()
        self.isplaying = False

    def Play(self, arg):
        print("Duration: " + str(self.Duration()))
        thread.start_new_thread(self._play, (0, self.Duration()))

    def PlaySegment(self, start, length, arg):
        # Both are measured in seconds using floats
        print("Start: " + str(start) + " Length: " + str(length))
        thread.start_new_thread(self._play, (start, length))
