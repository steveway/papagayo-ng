import sounddevice as sd
import soundfile as sf
import numpy as np


class SoundPlayer:
    def __init__(self, soundfile_path, parent=None, fps=24):
        self.soundfile_path = soundfile_path
        self.soundfile, self.samplerate = sf.read(soundfile_path, dtype='float32')
        self.soundinfo = sf.info(soundfile_path)
        self.channels = self.soundinfo.channels
        self.volume = 1.0
        self.current_frame = 0
        self.play_only_segment = False
        self.fps = fps

        self.stream = sd.OutputStream(samplerate=self.samplerate, channels=self.soundinfo.channels,
                                      callback=self.callback, blocksize=int(self.samplerate / self.fps))
        self.stream.start()
        self.playing = False

    def change_fps(self, new_fps):
        self.fps = new_fps
        self.stream.close()
        self.stream = sd.OutputStream(samplerate=self.samplerate, channels=self.soundinfo.channels,
                                      callback=self.callback, blocksize=int(self.samplerate / self.fps))
        self.stream.start()

    def callback(self, outdata, frames, time, status):
        if self.playing:
            start = self.current_frame
            end = start + frames
            if end > len(self.soundfile):
                end = len(self.soundfile)
                self.playing = False
            data = self.soundfile[start:end] * self.volume
            if self.channels == 1:
                data = np.expand_dims(data, axis=1)
            outdata[:len(data)] = data
            if len(data) < frames:
                outdata[len(data):] = 0
            self.current_frame = end
            if self.play_only_segment:
                self.playing = False
        else:
            outdata.fill(0)

    def play_segment(self, start, length):  # times are in ms
        start_frame = int(start * self.samplerate)
        end_frame = start_frame + int(length * self.samplerate)
        self.current_frame = start_frame
        self.play_only_segment = True
        self.playing = True

    def play(self, arg):
        self.current_frame = 0
        self.play_only_segment = False
        self.playing = True

    def stop(self):
        self.playing = False

    def set_volume(self, volume):
        self.volume = volume / 100.0

    def is_playing(self):
        return self.playing

    def IsValid(self):
        return True

    def current_time(self):
        return self.current_frame / self.samplerate

    def set_cur_time(self, newtime):
        self.current_frame = int(newtime * self.samplerate)

    def Duration(self):
        return self.soundinfo.duration

    def get_rms_amplitude(self, time_pos, sample_dur):
        time_start = time_pos * (len(self.soundfile) / self.Duration())
        time_end = (time_pos + sample_dur) * (len(self.soundfile) / self.Duration())
        samples = self.soundfile[int(time_start):int(time_end)]

        if len(samples):
            rms_amplitude = np.sqrt(np.mean(samples ** 2))
            print(rms_amplitude)
            return rms_amplitude
        else:
            return 1
