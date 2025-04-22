# Papagayo-NG, a lip-sync tool for use with several different animation suites
# Original Copyright (C) 2005 Mike Clifton
# Contact information at http://www.lostmarble.com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import math

import json
import fnmatch
from pathlib import Path
from scipy.signal import find_peaks

# Import the recognizer factory instead of directly importing recognizer
from recognizer_factory import RecognizerFactory
import os
import logging
from Rhubarb import Rhubarb, RhubarbTimeoutException
from ai_output_process import get_best_fitting_output_from_list
from model_downloader import ensure_model_exists

from LipsyncObject import LipSyncObject

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

import PySide6.QtCore as QtCore

import utilities


logger = logging.getLogger('LipsyncDoc')

from settings_manager import SettingsManager
settings = SettingsManager.get_instance()

if settings.get_audio_output() == "old":
    import SoundPlayer as SoundPlayer
else:
    import SoundPlayerSDF as SoundPlayer
    # if sys.platform == "win32":
    #     import SoundPlayerNew as SoundPlayer
    # elif sys.platform == "darwin":
    #     import SoundPlayerOSX as SoundPlayer
    # else:
    #     import SoundPlayer as SoundPlayer

strip_symbols = '.,!?;-/()"'
strip_symbols += '\N{INVERTED QUESTION MARK}'
strip_symbols += "'"


###############################################################

class LanguageManager:
    __shared_state = {}

    def __init__(self):
        self.__dict__ = self.__shared_state
        self.language_table = {}
        self.phoneme_dictionary = {}
        self.raw_dictionary = {}
        self.current_language = ""

        self.export_conversion = {}
        self.init_languages()

    def load_dictionary(self, path):
        print("Loading dictionary: {}".format(path))
        try:
            in_file = open(path, 'r')
        except FileNotFoundError:
            logging.info("Unable to open phoneme dictionary!:{}".format(path))
            return
        new_cmu_version = False
        if in_file.readline().startswith(";;; # CMUdict"):
            new_cmu_version = True
        # process dictionary entries
        for line in in_file.readlines():
            if not new_cmu_version:
                if line[0] == '#':
                    continue  # skip comments in the dictionary
            else:
                if line.startswith(";;;"):
                    continue
            # strip out leading/trailing whitespace
            line.strip()
            line = line.rstrip('\r\n')

            # split into components
            entry = line.split()
            if len(entry) == 0:
                continue
            # check if this is a duplicate word (alternate transcriptions end with a number in parentheses) - if so, throw it out
            if entry[0].endswith(')'):
                continue
            # add this entry to the in-memory dictionary
            for i in range(len(entry)):
                if i == 0:
                    self.raw_dictionary[entry[0]] = []
                else:
                    rawentry = entry[i]
                    self.raw_dictionary[entry[0]].append(rawentry)
        in_file.close()
        in_file = None

    def load_language(self, language_config, force=False):
        if self.current_language == language_config["label"] and not force:
            return
        self.current_language = language_config["label"]

        if "dictionaries" in language_config:
            for dictionary in language_config["dictionaries"]:
                self.load_dictionary(os.path.join(utilities.get_main_dir(),
                                                  language_config["location"],
                                                  language_config["dictionaries"][dictionary]))

    def language_details(self, dirname, names):
        if "language.ini" in names:
            config = configparser.ConfigParser()
            config.read(os.path.join(dirname, "language.ini"))
            label = config.get("configuration", "label")
            ltype = config.get("configuration", "type")
            details = {"label": label, "type": ltype, "location": dirname}
            if ltype == "breakdown":
                details["breakdown_class"] = config.get("configuration", "breakdown_class")
                self.language_table[label] = details
            elif ltype == "dictionary":
                try:
                    details["case"] = config.get("configuration", "case")
                except:
                    details["case"] = "upper"
                details["dictionaries"] = {}

                if config.has_section('dictionaries'):
                    for key, value in config.items('dictionaries'):
                        details["dictionaries"][key] = value
                self.language_table[label] = details
            else:
                logging.info("unknown type ignored language not added to table")

    def init_languages(self):
        if len(self.language_table) > 0:
            return
        for path, dirs, files in os.walk(os.path.join(utilities.get_main_dir(), "rsrc", "languages")):
            if "language.ini" in files:
                self.language_details(path, files)

class LipsyncDoc:
    def __init__(self, langman: LanguageManager, parent):
        self._dirty = False
        from settings_manager import SettingsManager
        settings = SettingsManager.get_instance()
        self.settings = settings
        self.name = "Untitled"
        self.path = None
        self.fps = 24
        self.soundDuration = 72
        self.soundPath = ""
        self.sound = None
        self.voices = []
        self.current_voice = None
        self.language_manager = langman
        self.parent = parent
        self.project_node = LipSyncObject(name=self.name, object_type="project")

    @property
    def dirty(self):
        return self._dirty

    @dirty.setter
    def dirty(self, value):
        self._dirty = value

    def __del__(self):
        # Properly close down the sound object
        if self.sound is not None:
            del self.sound

    def open_json(self, path):
        self._dirty = False
        self.path = os.path.normpath(path)
        self.name = os.path.basename(path)
        self.project_node.name = self.name
        self.sound = None
        self.voices = []
        self.current_voice = None
        try:
            with Path(path).open() as f:
                json_data = json.load(f)
            self.open_from_dict(json_data)
        except Exception as e:
            logging.error(f"Error opening JSON file {path}: {str(e)}")
            raise

    def open(self, path):
        self._dirty = False
        self.path = os.path.normpath(path)
        self.name = os.path.basename(path)
        self.project_node.name = self.name
        self.sound = None
        self.voices = []
        self.current_voice = None
        in_file = open(self.path, 'r')
        in_file.readline()  # discard the header
        self.soundPath = in_file.readline().strip()
        if not os.path.isabs(self.soundPath):
            self.soundPath = os.path.normpath("{}/{}".format(os.path.dirname(self.path), self.soundPath))
        self.fps = int(in_file.readline())
        logging.info(("self.path: {}".format(self.path)))
        self.soundDuration = int(in_file.readline())
        logging.info(("self.soundDuration: {:d}".format(self.soundDuration)))
        self.project_node.sound_duration = self.soundDuration
        num_voices = int(in_file.readline())
        for i in range(num_voices):
            voice = LipSyncObject(object_type="voice", parent=self.project_node)
            voice.open(in_file)
            self.voices.append(voice)
        in_file.close()
        self.open_audio(self.soundPath)
        if len(self.voices) > 0:
            self.current_voice = self.voices[0]

    def get_audio_chunk(self, start_frame, end_frame):
        """Instead of loading the whole file we can just load a chunk of it."""
        if self.sound is None:
            return None
        if start_frame < 0:
            start_frame = 0
        if end_frame > self.sound.length:
            end_frame = self.sound.length
        if start_frame >= end_frame:
            return None
        return self.sound.get_samples(start_frame, end_frame)

    def open_audio(self, path):
        if not os.path.exists(path):
            return
        if self.sound is not None:
            del self.sound
            self.sound = None
        self.soundPath = path
        self.sound = SoundPlayer.SoundPlayer(self.soundPath, self.parent, self.fps)
        if self.sound.IsValid():
            logging.info("valid sound")
            self.soundDuration = int(self.sound.Duration() * self.fps)
            logging.info(("self.sound.Duration(): {:d}".format(int(self.sound.Duration()))))
            logging.info(("frameRate: {:d}".format(int(self.fps))))
            logging.info(("soundDuration1: {:d}".format(self.soundDuration)))
            if self.soundDuration < self.sound.Duration() * self.fps:
                self.soundDuration += 1
                logging.info(("soundDuration2: {:d}".format(self.soundDuration)))
            self.project_node.sound_duration = self.soundDuration
        else:
            self.sound = None

    def open_from_dict(self, json_data):
        self._dirty = False
        self.project_node.name = "Test_Copy"
        self.project_node.children = []
        self.sound = None
        self.voices = []
        self.current_voice = None
        self.soundPath = json_data.get("sound_path", "")
        if not os.path.isabs(self.soundPath):
            self.soundPath = os.path.normpath("{}/{}".format(os.path.dirname(self.path), self.soundPath))
        self.fps = json_data["fps"]
        self.soundDuration = json_data["sound_duration"]
        self.project_node.sound_duration = self.soundDuration
        self.parent.phonemeset.selected_set = json_data.get("phoneme_set", "preston_blair")
        num_voices = json_data["num_voices"]
        for voice in json_data["voices"]:
            temp_voice = LipSyncObject(name=voice["name"], text=voice["text"], num_children=voice["num_children"],
                                       fps=self.fps, parent=self.project_node, object_type="voice",
                                       sound_duration=self.soundDuration)
            for phrase in voice["phrases"]:
                temp_phrase = LipSyncObject(text=phrase["text"], start_frame=phrase["start_frame"],
                                            end_frame=phrase["end_frame"], tags=phrase["tags"], fps=self.fps,
                                            object_type="phrase", parent=temp_voice, sound_duration=self.soundDuration)
                for word in phrase["words"]:
                    temp_word = LipSyncObject(text=word["text"], start_frame=word["start_frame"], fps=self.fps,
                                              end_frame=word["end_frame"], tags=word["tags"], object_type="word",
                                              parent=temp_phrase, sound_duration=self.soundDuration)
                    for phoneme in word["phonemes"]:
                        temp_phoneme = LipSyncObject(text=phoneme["text"], start_frame=phoneme["frame"],
                                                     end_frame=phoneme["frame"], tags=phoneme["tags"], fps=self.fps,
                                                     object_type="phoneme", parent=temp_word,
                                                     sound_duration=self.soundDuration)
            self.voices.append(temp_voice)
        self.open_audio(self.soundPath)
        if len(self.voices) > 0:
            self.current_voice = self.voices[0]

    def copy_to_dict(self, saved_sound_path=""):
        if not saved_sound_path:
            saved_sound_path = self.soundPath
        out_dict = {"version": 2, "sound_path": saved_sound_path, "fps": self.fps,
                    "sound_duration": self.soundDuration,
                    "num_voices": len(self.project_node.children),
                    "phoneme_set": self.parent.phonemeset.selected_set}
        list_of_voices = []
        for voi_id, voice in enumerate(self.project_node.children):
            start_frame = 0
            end_frame = 1
            if len(voice.children) > 0:
                start_frame = voice.children[0].start_frame
                end_frame = voice.children[-1].end_frame
            json_data = {"name": voice.name, "start_frame": start_frame, "end_frame": end_frame,
                         "text": voice.text, "num_children": len(voice.descendants)}
            list_of_phrases = []
            list_of_used_phonemes = []
            for phr_id, phrase in enumerate(voice.children):
                dict_phrase = {"id": phr_id, "text": phrase.text, "start_frame": phrase.start_frame,
                               "end_frame": phrase.end_frame, "tags": phrase.tags}
                list_of_words = []
                for wor_id, word in enumerate(phrase.children):
                    dict_word = {"id": wor_id, "text": word.text, "start_frame": word.start_frame,
                                 "end_frame": word.end_frame, "tags": word.tags}
                    list_of_phonemes = []
                    for pho_id, phoneme in enumerate(word.children):
                        dict_phoneme = {"id": pho_id, "text": phoneme.text,
                                        "frame": phoneme.start_frame, "tags": phoneme.tags}
                        list_of_phonemes.append(dict_phoneme)
                        if phoneme.text not in list_of_used_phonemes:
                            list_of_used_phonemes.append(phoneme.text)
                    dict_word["phonemes"] = list_of_phonemes
                    list_of_words.append(dict_word)
                dict_phrase["words"] = list_of_words
                list_of_phrases.append(dict_phrase)
            json_data["phrases"] = list_of_phrases
            json_data["used_phonemes"] = list_of_used_phonemes
            list_of_voices.append(json_data)
        out_dict["voices"] = list_of_voices
        return out_dict

    def save2(self, path):
        output_dict = self.copy_to_dict()
        with Path(path).open('w') as f:
            json.dump(output_dict, f, indent=4)
        self.path = os.path.normpath(path)
        self.name = os.path.basename(path)
        self.project_node.name = self.name
        if os.path.dirname(self.path) == os.path.dirname(self.soundPath):
            saved_sound_path = os.path.basename(self.soundPath)
        else:
            saved_sound_path = self.soundPath
        self._dirty = False

    def save(self, path):
        self.path = os.path.normpath(path)
        self.name = os.path.basename(path)
        self.project_node.name = self.name
        if os.path.dirname(self.path) == os.path.dirname(self.soundPath):
            saved_sound_path = os.path.basename(self.soundPath)
        else:
            saved_sound_path = self.soundPath
        out_file = open(self.path, "w")
        out_file.write("lipsync version 1\n")
        out_file.write("{}\n".format(saved_sound_path))
        out_file.write("{:d}\n".format(self.fps))
        out_file.write("{:d}\n".format(self.soundDuration))
        out_file.write("{:d}\n".format(len(self.project_node.children)))
        for voice in self.project_node.children:
            voice.save(out_file)
        out_file.close()
        self._dirty = False

    def convert_to_phonemeset_old(self):
        # The base set is the CMU39 set, we will convert everything to that and from it to the desired one for now
        new_set = self.parent.main_window.phoneme_set.currentText()
        old_set = self.parent.phonemeset.selected_set
        if old_set != new_set:
            if old_set != "CMU_39":
                conversion_map_to_cmu = {v: k for k, v in self.parent.phonemeset.conversion.items()}
                for voice in self.project_node.children:
                    for phrase in voice.children:
                        for word in phrase.children:
                            for phoneme in word.children:
                                phoneme.text = conversion_map_to_cmu.get(phoneme.text, "rest")
            new_map = PhonemeSet()
            new_map.load(new_set)
            conversion_map_from_cmu = new_map.conversion
            for voice in self.project_node.children:
                for phrase in voice.children:
                    for word in phrase.children:
                        for phoneme in word.children:
                            phoneme.text = conversion_map_from_cmu.get(phoneme.text, "rest")
            self.dirty = True
            self.parent.phonemeset.selected_set = new_set
            self.parent.main_window.waveform_view.set_document(self, force=True, clear_scene=True)

    def convert_to_phonemeset(self):
        # The base set is the CMU39 set, we will convert everything to that and from it to the desired one for now
        new_set = self.parent.main_window.phoneme_set.currentText()
        old_set = self.parent.phonemeset.selected_set
        conversion_dict = {}
        if old_set != new_set:
            new_map = PhonemeSet()
            new_map.load(new_set)
            for conversion_name in new_map.alternate_conversions:
                if conversion_name.startswith(old_set.lower()):
                    conversion_dict = new_map.alternate_conversions[conversion_name]
            if conversion_dict:
                for voice in self.project_node.children:
                    for phrase in voice.children:
                        for word in phrase.children:
                            for phoneme in word.children:
                                phoneme.text = conversion_dict.get(phoneme.text, "rest")
                self.dirty = True
                self.parent.phonemeset.selected_set = new_set
                self.parent.main_window.waveform_view.set_document(self, force=True, clear_scene=True)

    def auto_recognize_phoneme(self, manual_invoke=False):
        if str(self.settings.get_voice_recognition()).lower() == "true" or manual_invoke:
            recognizer_type = self.settings.get_recognizer()
            distribution_mode = self.settings.get_distribution_mode()
            
            try:
                # Create the appropriate recognizer using the factory
                if recognizer_type.lower() == "onnx":
                    model_path = self.settings.get_onnx_model()
                    model_dir = ensure_model_exists(model_path, model_type="phoneme")
                    logging.info(f"Using ONNX model: {model_dir}")
                    phoneme_recognizer = RecognizerFactory.create_recognizer("onnx", phoneme_model_path=model_dir)
                else:
                    # For Allosaurus or Rhubarb
                    phoneme_recognizer = RecognizerFactory.create_recognizer(recognizer_type.lower())
                
                # Process the audio file with the selected recognizer
                if recognizer_type.lower() == "allosaurus":
                    # For Allosaurus, we get a list of phoneme dictionaries with timing
                    phoneme_results = phoneme_recognizer.predict(self.soundPath)
                    
                    # Extract phonemes and create time list
                    phonemes = [p["phoneme"] for p in phoneme_results]
                    time_list = []
                    prev_start = 0
                    for p in phoneme_results:
                        time_list.append(p["start"] - prev_start)
                        prev_start = p["start"]
                    time_list.append(self.soundDuration - prev_start)
                    
                    # Find peaks for word boundaries
                    if distribution_mode == "peaks":
                        peaks = self.get_level_peaks(time_list)
                        fitted_peaks = []
                        for peak in peaks:
                            if peak < len(time_list):
                                frame = int(round(phoneme_results[peak]["start"] * self.fps))
                                fitted_peaks.append(frame)
                        fitted_peaks.append(int(round(self.soundDuration)))
                        fitted_peaks = list(set(fitted_peaks))
                        fitted_peaks.sort()
                    else:
                        fitted_peaks = [0, int(round(self.soundDuration))]
                    
                elif recognizer_type.lower() == "rhubarb":
                    # For Rhubarb, we get a list of phoneme dictionaries with timing
                    phoneme_results = phoneme_recognizer.predict(self.soundPath)
                    
                    # Extract phonemes
                    phonemes = [p["phoneme"] for p in phoneme_results]
                    
                    # Find word boundaries based on timing
                    if distribution_mode == "peaks":
                        # Find potential word boundaries (silence or pauses)
                        fitted_peaks = [0]  # Start with frame 0
                        for i in range(1, len(phoneme_results)):
                            # If there's a gap between phonemes or a rest phoneme, consider it a word boundary
                            if (phoneme_results[i]["start"] - (phoneme_results[i-1]["start"] + phoneme_results[i-1]["duration"]) > 0.1 or
                                phoneme_results[i-1]["phoneme"] == "rest"):
                                frame = int(round(phoneme_results[i]["start"] * self.fps))
                                fitted_peaks.append(frame)
                        fitted_peaks.append(int(round(self.soundDuration)))
                        fitted_peaks = list(set(fitted_peaks))
                        fitted_peaks.sort()
                    else:
                        fitted_peaks = [0, int(round(self.soundDuration))]
                    
                else:  # ONNX
                    try:
                        # Load IPA to CMU conversion dictionary
                        ipa_convert = json.load(open("ipa_cmu.json", encoding="utf8"))
                        
                        # Predict phonemes
                        phoneme_results = phoneme_recognizer.predict(self.soundPath, "phoneme")
                        
                        # Extract just the phoneme text from the results
                        if phoneme_results and isinstance(phoneme_results, list) and len(phoneme_results) > 0:
                            # Check if we have dictionary objects with phoneme keys
                            if isinstance(phoneme_results[0], dict) and "phoneme" in phoneme_results[0]:
                                # Extract just the phoneme values
                                phonemes = [p["phoneme"] for p in phoneme_results]
                                
                                # Convert phonemes if needed
                                if any(not isinstance(p, str) or p.isupper() for p in phonemes):
                                    # Already converted to CMU format
                                    pass
                                else:
                                    # Convert from IPA to CMU format
                                    phonemes = get_best_fitting_output_from_list(phonemes, ipa_convert)
                            else:
                                # If we just have a list of phonemes, use it directly
                                phonemes = phoneme_results
                                # Convert from IPA to CMU format if needed
                                if not any(p.isupper() for p in phonemes if isinstance(p, str)):
                                    phonemes = get_best_fitting_output_from_list(phonemes, ipa_convert)
                            
                            # Filter out None values
                            phonemes = [p for p in phonemes if p is not None]
                        else:
                            logging.warning("ONNX model returned no phonemes")
                            phonemes = []
                        
                        # Find peaks for word boundaries
                        if distribution_mode == "peaks":
                            peaks = find_peaks(self.sound.soundfile, distance=2048)
                            peak_divisor = len(self.sound.soundfile) / (self.soundDuration)
                            fitted_peaks = peaks[0] / peak_divisor
                            fitted_peaks = fitted_peaks.round().astype(int)
                            fitted_peaks = list(fitted_peaks)
                            fitted_peaks.append(int(round(self.soundDuration)))
                            fitted_peaks.append(0)
                            fitted_peaks = list(set(fitted_peaks))
                            fitted_peaks.sort()
                        else:
                            fitted_peaks = [0, int(round(self.soundDuration))]
                    except Exception as e:
                        logging.error(f"Error processing ONNX model output: {str(e)}")
                        import traceback
                        logging.error(traceback.format_exc())
                        # Fall back to a simple distribution
                        phonemes = []
                        fitted_peaks = [0, int(round(self.soundDuration))]
                
                logging.info(f"Auto-Recognized Phonemes: {phonemes}")
                logging.info(f"Number of Phonemes: {len(phonemes)}")
                logging.info(f"Auto-Recognized Fitted Peaks: {fitted_peaks}")
                
                # Create words from peaks
                list_of_words = []
                for i in range(len(fitted_peaks) - 1):
                    peak_left = fitted_peaks[i]
                    peak_right = fitted_peaks[i + 1]
                    if peak_right > peak_left:  # Only add valid word ranges
                        list_of_words.append((peak_left, peak_right))
                
                logging.info(f"Auto-Recognized List of Words: {list_of_words}")
                
                # Create phrase and distribute phonemes
                phrase = LipSyncObject(object_type="phrase", parent=self.current_voice)
                phrase.text = f'Auto detection {recognizer_type}'
                phrase.start_frame = 0
                phrase.end_frame = self.soundDuration
                self.parent.phonemeset.selected_set = self.parent.phonemeset.load("CMU_39")
                
                phoneme_pointer = 0
                remaining_phonemes = len(phonemes)
                
                for i, word in enumerate(list_of_words):
                    peak_left = word[0]
                    peak_right = word[1]
                    
                    # Calculate phonemes for this word considering remaining words and phonemes
                    if i == len(list_of_words) - 1:
                        # Last word - use all remaining phonemes
                        amount_of_phonemes = remaining_phonemes
                    else:
                        # For other words, distribute remaining phonemes evenly among remaining words
                        remaining_words = len(list_of_words) - i
                        amount_of_phonemes = min(
                            peak_right - peak_left,  # Don't use more frames than available
                            max(1, remaining_phonemes // remaining_words)  # At least 1 phoneme per word
                        )
                    
                    logging.info(f"Auto-Recognized Amount of Phonemes: {amount_of_phonemes}")
                    used_phonemes = []
                    for j in range(amount_of_phonemes):
                        if phoneme_pointer < len(phonemes):
                            logging.info(f"Phoneme Pointer Position: {phoneme_pointer}")
                            used_phonemes.append(phonemes[phoneme_pointer])
                            phoneme_pointer += 1
                            remaining_phonemes -= 1
                    
                    word = LipSyncObject(object_type="word", parent=phrase)
                    word.text = "|".join(phoneme.upper() for phoneme in used_phonemes)
                    word.start_frame = peak_left
                    word.end_frame = peak_right
                    j = 0
                    for phoneme in used_phonemes:
                        pg_phoneme = LipSyncObject(object_type="phoneme", parent=word)
                        pg_phoneme.start_frame = pg_phoneme.end_frame = peak_left + j
                        pg_phoneme.text = phoneme.upper() if phoneme != "rest" else phoneme
                        j += 1
                
            except Exception as e:
                logging.error(f"Error in auto recognition: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())

    def get_level_peaks(self, v):
        """Find peaks in the audio level data for visualization"""
        peaks = [0]

        i = 1
        while i < len(v) - 1:
            pos_left = i
            pos_right = i

            while v[pos_left] == v[i] and pos_left > 0:
                pos_left -= 1

            while v[pos_right] == v[i] and pos_right < len(v) - 1:
                pos_right += 1

            # is_lower_peak = v[pos_left] > v[i] and v[i] < v[pos_right]
            is_upper_peak = v[pos_left] < v[i] and v[i] > v[pos_right]

            if is_upper_peak:
                peaks.append(i)

            i = pos_right

        peaks.append(len(v) - 1)
        return peaks

    def __str__(self):
        out_string = "LipSyncDoc:{}|Objects:{}|Sound:{}|".format(self.name, self.project_node, self.soundPath)
        return out_string

    def __repr__(self):
        return self.__str__()


class PhonemeSet:
    __shared_state = {}

    def __init__(self):
        self.__dict__ = self.__shared_state
        self.set = []
        self.conversion = {}
        self.alternatives = []
        self.alternate_conversions = {}
        phonemes_dir = utilities.get_main_dir() / "phonemes"
        for file in phonemes_dir.glob('*.json'):
            self.alternatives.append(file.stem)

        # Try to load Preston Blair as default as before, but fall back just in case
        self.selected_set = self.load("preston_blair")
        if not self.selected_set:
            self.load(self.alternatives[0])
            self.selected_set = self.alternatives[0]

    def load(self, name=''):
        if name in self.alternatives:
            phoneme_file = utilities.get_main_dir() / "phonemes" / f"{name}.json"
            with phoneme_file.open() as loaded_file:
                json_data = json.load(loaded_file)
                self.set = json_data["phoneme_set"]
                if name.lower() != "cmu_39":
                    self.conversion = json_data.get("cmu_39_phoneme_conversion")
                else:
                    for phoneme in self.set:
                        self.conversion[phoneme] = phoneme
                for key in json_data:
                    if key != "phoneme_set":
                        self.alternate_conversions[key] = json_data[key]
                return name
        else:
            logging.info(f"Can't find phonemeset! ({name})")
            return False
