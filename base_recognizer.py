from queue import Queue

class BaseRecognizer:
    def __init__(self):
        self.works = True
        self.recognition_thread = None
        self.model_output = Queue()

    def predict(self, audio):
        raise NotImplementedError("Subclasses must implement predict method")

    def processing_thread(self, delta_time=0):
        if not self.audio_manager.audio_buffer.empty():
            audio = self.audio_manager.audio_buffer.get(block=False)
            modified_audio = self.audio_manager.speech_data_to_array_fn(audio)
            phonemes = self.predict(modified_audio)
            if phonemes:
                sample_length_ms = len(audio) / self.audio_manager.selected_input_device['default_samplerate'] * 1000 / len(phonemes)
                sample_volume = self.audio_manager.rms_flat(audio)
                output_data = {
                    "phonemes": phonemes,
                    "audio": audio,
                    "sample_length": sample_length_ms,
                    "volume": sample_volume,
                    "number_of_phonemes": len(phonemes)
                }
                self.model_output.put(output_data)
