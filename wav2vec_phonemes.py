# Use a pipeline as a high-level helper
import os

from espnet2.text.phoneme_tokenizer import PhonemeTokenizer
import utilities

if utilities.get_app_data_path() not in os.environ['PATH']:
    os.environ['PATH'] += os.pathsep + utilities.get_app_data_path()
from transformers import pipeline

pipe = pipeline("automatic-speech-recognition", model="jbtruong/whisper-small-phonemes-test-1e-4_50k_steps", tokenizer=PhonemeTokenizer)
output = pipe("./Tutorial Files/lame.wav", chunk_length_s=10, stride_length_s=(4, 2))
print(output)
