from PySide6 import QtCore
from anytree import NodeMixin
import anytree
from pathlib import Path
import path_utils
import utilities
from PronunciationDialogQT import show_pronunciation_dialog
from settings_manager import SettingsManager

class LipSyncObject(NodeMixin):
    '''
    This should be a general class for all LipSync Objects
    '''

    def __init__(self, parent=None, children=None, object_type="voice", text="", start_frame=0, end_frame=0, name="",
                 tags=None, num_children=0, sound_duration=0, fps=24):
        self.parent = parent
        self.config = SettingsManager.get_instance()
        if children:
            self.children = children
        self.object_type = object_type
        self.name = name
        self.text = text
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.tags = tags if tags else []
        self.num_children = num_children
        self.move_button = None
        if self.parent:
            self.sound_duration = self.root.sound_duration
        else:
            self.sound_duration = sound_duration
        self.fps = fps
        self.last_returned_frame = "rest"

    def get_min_size(self):
        # An object should be at least be able to contain all it's phonemes since only 1 phoneme per frame is allowed.
        if self.object_type == "phoneme":
            num_of_phonemes = 1
        else:
            num_of_phonemes = 0
            for descendant in self.descendants:
                if descendant.object_type == "phoneme":
                    num_of_phonemes += 1
        return num_of_phonemes

    def get_left_sibling(self):
        return anytree.util.leftsibling(self)

    def get_right_sibling(self):
        return anytree.util.rightsibling(self)

    def get_parent(self):
        if self.object_type != "phrase":
            return self.parent
        else:
            return None

    def get_frame_size(self):
        if self.object_type == "phoneme":
            return 1
        else:
            return self.end_frame - self.start_frame

    def has_shrink_room(self):
        if self.object_type == "phoneme":
            return False
        else:
            if self.get_min_size() >= self.get_frame_size():
                return False
            else:
                return True

    def has_left_sibling(self):
        try:
            left_sibling = bool(self.get_left_sibling())
        except AttributeError:
            left_sibling = False
        return left_sibling

    def has_right_sibling(self):
        try:
            right_sibling = bool(self.get_right_sibling())
        except AttributeError:
            right_sibling = False
        return right_sibling

    def get_left_max(self):
        if self.has_left_sibling():
            temp = self.get_left_sibling()
            if not temp.object_type == "phoneme":
                left_most_pos = temp.end_frame
            else:
                left_most_pos = temp.end_frame + 1
        else:
            left_most_pos = self.parent.start_frame
        return left_most_pos

    def get_right_max(self):
        if self.has_right_sibling():
            right_most_pos = self.get_right_sibling().start_frame
        else:
            if self.parent.object_type == "voice":
                right_most_pos = self.root.sound_duration
            elif self.parent.object_type == "project":
                right_most_pos = self.root.sound_duration
            else:
                try:
                    right_most_pos = self.parent.end_frame
                except AttributeError:
                    right_most_pos = self.root.sound_duration
        return right_most_pos

    def get_phoneme_at_frame(self, frame):
        for descendant in self.descendants:
            if descendant.object_type == "phoneme":
                if descendant.start_frame == frame:
                    self.last_returned_frame = descendant.text
                    return descendant.text

        if str(self.config.get_rest_after_words()).lower() == "true":
            if not self.frame_is_in_word(frame):
                return "rest"
            else:
                if str(self.config.get_rest_after_phonemes()).lower() == "true":
                    return "rest"
                else:
                    return self.last_returned_frame
        else:
            if str(self.config.get_rest_after_phonemes()).lower() == "true":
                return "rest"
            else:
                return self.last_returned_frame

    def frame_is_in_word(self, frame):
        is_in_word = False
        for descendant in self.descendants:
            if descendant.object_type == "word":
                if descendant.start_frame <= frame <= descendant.end_frame:
                    is_in_word = True
                    return is_in_word
        return is_in_word

    def reposition_to_left(self):
        if self.has_left_sibling():
            if self.object_type == "phoneme":
                self.start_frame = self.get_left_sibling().start_frame + 1
            else:
                self.start_frame = self.get_left_sibling().end_frame
                self.end_frame = self.start_frame + self.get_min_size()
                for child in self.children:
                    child.reposition_to_left()
        else:
            if self.object_type == "phoneme":
                self.start_frame = self.parent.start_frame
            else:
                self.start_frame = self.parent.name.node.start_frame
                self.end_frame = self.start_frame + self.get_min_size()
                for child in self.children:
                    child.reposition_to_left()

    def reposition_descendants(self, did_resize=False, x_diff=0):
        if did_resize:
            for child in self.children:
                child.reposition_to_left()
        else:
            for child in self.descendants:
                child.start_frame += x_diff
                child.end_frame += x_diff
                child.move_button.after_reposition()

    def reposition_descendants2(self, did_resize=False, x_diff=0):
        if did_resize:
            if self.object_type == "word":
                for position, child in enumerate(self.children):
                    child.start_frame = round(self.start_frame +
                                              ((self.get_frame_size() / self.get_min_size()) * position))
                    child.move_button.after_reposition()
                # self.wfv_parent.doc.dirty = True
            elif self.object_type == "phrase":
                extra_space = self.get_frame_size() - self.get_min_size()
                for child in self.children:
                    if child.has_left_sibling():
                        child.start_frame = child.get_left_sibling().end_frame
                        child.end_frame = child.start_frame + child.get_min_size()
                    else:
                        child.start_frame = self.start_frame
                        child.end_frame = child.start_frame + child.get_min_size()
                last_position = -1
                moved_child = False
                while extra_space > 0:
                    if last_position == len(self.children) - 1:
                        last_position = -1
                    if not moved_child:
                        last_position = -1
                    moved_child = False
                    for position, child in enumerate(self.children):
                        if child.has_left_sibling():
                            if child.start_frame < child.get_left_sibling().end_frame:
                                child.start_frame += 1
                                child.end_frame += 1
                            else:
                                if extra_space and not moved_child and (position > last_position):
                                    child.end_frame += 1
                                    extra_space -= 1
                                    moved_child = True
                                    last_position = position
                        else:
                            if extra_space and not moved_child and (position > last_position):
                                child.end_frame += 1
                                extra_space -= 1
                                moved_child = True
                                last_position = position
                    if not moved_child and extra_space == 0:
                        break
                for child in self.children:
                    child.move_button.after_reposition()
                    child.reposition_descendants2(True, 0)
                # self.wfv_parent.doc.dirty = True
        else:
            for child in self.descendants:
                child.start_frame += x_diff
                child.end_frame += x_diff
                child.move_button.after_reposition()
            # self.wfv_parent.doc.dirty = True

    def open(self, in_file):
        self.name = in_file.readline().strip()
        temp_text = in_file.readline().strip()
        self.text = temp_text.replace('|', '\n')
        num_phrases = int(in_file.readline())
        for p in range(num_phrases):
            self.num_children += 1
            phrase = LipSyncObject(object_type="phrase", parent=self)
            phrase.text = in_file.readline().strip()
            phrase.start_frame = int(in_file.readline())
            phrase.end_frame = int(in_file.readline())
            num_words = int(in_file.readline())
            for w in range(num_words):
                self.num_children += 1
                word = LipSyncObject(object_type="word", parent=phrase)
                word_line = in_file.readline().split()
                word.text = word_line[0]
                word.start_frame = int(word_line[1])
                word.end_frame = int(word_line[2])
                num_phonemes = int(word_line[3])
                for p2 in range(num_phonemes):
                    self.num_children += 1
                    phoneme = LipSyncObject(object_type="phoneme", parent=word)
                    phoneme_line = in_file.readline().split()
                    phoneme.start_frame = phoneme.end_frame = int(phoneme_line[0])
                    phoneme.text = phoneme_line[1]

    def save(self, out_file):
        out_file.write("    {}\n".format(self.name))
        temp_text = self.text.replace('\n', '|')
        out_file.write("    {}\n".format(temp_text))
        out_file.write("    {:d}\n".format(len(self.children)))
        for phrase in self.children:
            out_file.write("        {}\n".format(phrase.text))
            out_file.write("        {:d}\n".format(phrase.start_frame))
            out_file.write("        {:d}\n".format(phrase.end_frame))
            out_file.write("        {:d}\n".format(len(phrase.children)))
            for word in phrase.children:
                out_file.write(
                    "            {} {:d} {:d} {:d}\n".format(word.text, word.start_frame, word.end_frame, len(word.children)))
                for phoneme in word.children:
                    out_file.write("                {:d} {}\n".format(phoneme.start_frame, phoneme.text))

    def run_breakdown(self, frame_duration, parent_window, language, languagemanager, phonemeset):
        if self.object_type == "voice":
            # First we delete all children
            self.children = []
            # make sure there is a space after all punctuation marks
            repeat_loop = True
            while repeat_loop:
                repeat_loop = False
                for i in range(len(self.text) - 1):
                    if (self.text[i] in ".,!?;-/()") and (not self.text[i + 1].isspace()):
                        self.text = "{} {}".format(self.text[:i + 1], self.text[i + 1:])
                        repeat_loop = True
                        break
            # break text into phrases
            # self.phrases = []
            for line in self.text.splitlines():
                if len(line) == 0:
                    continue
                phrase = LipSyncObject(object_type="phrase", parent=self)
                phrase.text = line
                # self.children.append(phrase)
            # now break down the phrases
            for phrase in self.children:
                return_value = phrase.run_breakdown(frame_duration, parent_window, language, languagemanager,
                                                    phonemeset)
                if return_value == -1:
                    return -1
            # for first-guess frame alignment, count how many phonemes we have
            phoneme_count = 0
            for phrase in self.children:
                for word in phrase.children:
                    if len(word.children) == 0:  # deal with unknown words
                        phoneme_count += 4
                    for phoneme in word.children:
                        phoneme_count += 1
            # now divide up the total time by phonemes
            if frame_duration > 0 and phoneme_count > 0:
                frames_per_phoneme = int(float(frame_duration) / float(phoneme_count))
                if frames_per_phoneme < 1:
                    frames_per_phoneme = 1
            else:
                frames_per_phoneme = 1
            # finally, assign frames based on phoneme durations
            cur_frame = 0
            for phrase in self.children:
                for word in phrase.children:
                    for phoneme in word.children:
                        phoneme.start_frame = phoneme.end_frame = cur_frame
                        cur_frame += frames_per_phoneme
                    if len(word.children) == 0:  # deal with unknown words
                        word.start_frame = cur_frame
                        word.end_frame = cur_frame + 3
                        cur_frame += 4
                    else:
                        word.start_frame = word.children[0].start_frame
                        word.end_frame = word.children[-1].end_frame + frames_per_phoneme - 1
                phrase.start_frame = phrase.children[0].start_frame
                phrase.end_frame = phrase.children[-1].end_frame
        elif self.object_type == "phrase":
            # self.words = []
            for w in self.text.split():
                if len(w) == 0:
                    continue
                word = LipSyncObject(object_type="word", parent=self)
                word.text = w
                # self.words.append(word)
            for word in self.children:
                result = word.run_breakdown(frame_duration, parent_window, language, languagemanager, phonemeset)
                if result == -1:
                    return -1
        elif self.object_type == "word":
            # self.phonemes = []
            try:
                text = self.text.strip(strip_symbols)
                details = languagemanager.language_table[language]
                pronunciation_raw = None
                if details["type"] == "breakdown":
                    breakdown = importlib.import_module(details["breakdown_class"])
                    pronunciation_raw = breakdown.breakdown_word(text)
                elif details["type"] == "dictionary":
                    if languagemanager.current_language != language:
                        languagemanager.load_language(details)
                        languagemanager.current_language = language
                    if details["case"] == "upper":
                        pronunciation_raw = languagemanager.raw_dictionary[text.upper()]
                    elif details["case"] == "lower":
                        pronunciation_raw = languagemanager.raw_dictionary[text.lower()]
                    else:
                        pronunciation_raw = languagemanager.raw_dictionary[text]
                else:
                    logging.info(("Unknown type:", details["type"]))

                pronunciation = []
                for i in range(len(pronunciation_raw)):
                    try:
                        pronunciation_phoneme = pronunciation_raw[i].rstrip("0123456789")
                        pronunciation.append(phonemeset.conversion[pronunciation_phoneme])
                    except KeyError:
                        logging.info(("Unknown phoneme:", pronunciation_raw[i], "in word:", text))

                for p in pronunciation:
                    if len(p) == 0:
                        continue
                    phoneme = LipSyncObject(object_type="phoneme", parent=self)
                    phoneme.text = p
                    # self.phonemes.append(phoneme)
            except KeyError:
                # this word was not found in the phoneme dictionary
                # TODO: This now depends on QT, make it neutral!
                return_value = show_pronunciation_dialog(parent_window, phonemeset.set, self.text)
                if return_value == -1:
                    return -1
                elif not return_value:
                    pass
                else:
                    conversion_map_to_cmu = {v: k for k, v in parent_window.doc.parent.phonemeset.conversion.items()}
                    phonemes_as_list = []
                    for p in return_value:
                        phoneme = LipSyncObject(object_type="phoneme", parent=self)
                        phoneme.text = p
                        phoneme_as_cmu = conversion_map_to_cmu.get(p, "rest")
                        phonemes_as_list.append(phoneme_as_cmu)
                    languagemanager.raw_dictionary[self.text.upper()] = phonemes_as_list

    ###

    def export(self, path, use_rest_frame_settings=False):

        out_file = open(path, 'w')
        out_file.write("MohoSwitch1\n")
        phoneme = ""
        if len(self.children) > 0:
            start_frame = self.children[0].start_frame
            end_frame = self.children[-1].end_frame
            if start_frame != 0:
                phoneme = "rest"
                out_file.write("{:d} {}\n".format(1, phoneme))
        else:
            start_frame = 0
            end_frame = 1
        last_phoneme = self.leaves[0]
        for phoneme in self.leaves:
            if last_phoneme.text != phoneme.text:
                if phoneme.text == "rest":
                    # export an extra "rest" phoneme at the end of a pause between words or phrases
                    out_file.write("{:d} {}\n".format(phoneme.start_frame, phoneme.text))
            if use_rest_frame_settings:
                if str(self.config.get_rest_after_words()).lower() == "true":
                    if last_phoneme.parent != phoneme.parent:
                        if (last_phoneme.start_frame + 1) < phoneme.start_frame:
                            out_file.write("{:d} {}\n".format((last_phoneme.start_frame + 2), "rest"))
            last_phoneme = phoneme
            out_file.write("{:d} {}\n".format(phoneme.start_frame + 1, phoneme.text))
        out_file.write("{:d} {}\n".format(end_frame + 2, "rest"))
        out_file.close()

    def export_images(self, path, currentmouth, use_rest_frame_settings=False):
        if not self.config.get_mouth_dir():
            logging.info("Use normal procedure.\n")
            phonemedict = {}
            mouth_full_dir = Path(path_utils.get_resource_path("rsrc", "mouths")) / currentmouth
            for files in mouth_full_dir.iterdir():
                phonemedict[files.stem] = files.suffix
            for phoneme in self.leaves:
                try:
                    shutil.copy(mouth_full_dir / (phoneme.text + phonemedict[phoneme.text]),
                                path + str(phoneme.start_frame).rjust(6, '0') +
                                phoneme.text + phonemedict[phoneme.text])
                except KeyError:
                    logging.info("Phoneme \'{0}\' does not exist in chosen directory.".format(phoneme.text))

        else:
            logging.info("Use this dir: {}\n".format(self.config.get_mouth_dir()))
            phonemedict = {}
            for files in Path(self.config.get_mouth_dir()).iterdir():
                phonemedict[files.stem] = files.suffix
            for phoneme in self.leaves:
                try:
                    shutil.copy(
                        "{}/{}{}".format(self.config.get_mouth_dir(), phoneme.text, phonemedict[phoneme.text]),
                        "{}{}{}{}".format(path, str(phoneme.start_frame).rjust(6, "0"), phoneme.text,
                                          phonemedict[phoneme.text]))
                except KeyError:
                    logging.info("Phoneme \'{0}\' does not exist in chosen directory.".format(phoneme.text))

    def export_alelo(self, path, language, languagemanager, use_rest_frame_settings=False):
        out_file = open(path, 'w')
        for phrase in self.children:
            for word in phrase.children:
                text = word.text.strip(strip_symbols)
                details = languagemanager.language_table[language]
                if languagemanager.current_language != language:
                    languagemanager.LoadLanguage(details)
                    languagemanager.current_language = language
                if details["case"] == "upper":
                    pronunciation = languagemanager.raw_dictionary[text.upper()]
                elif details["case"] == "lower":
                    pronunciation = languagemanager.raw_dictionary[text.lower()]
                else:
                    pronunciation = languagemanager.raw_dictionary[text]
                first = True
                position = -1
                last_phoneme = None
                for phoneme in word.children:
                    if first:
                        first = False
                    else:
                        try:
                            out_file.write("{:d} {:d} {}\n".format(last_phoneme.start_frame, phoneme.start_frame - 1,
                                                                   languagemanager.export_conversion[
                                                                       last_phoneme_text]))
                        except KeyError:
                            pass
                    if phoneme.text.lower() == "sil":
                        position += 1
                        out_file.write("{:d} {:d} sil\n".format(phoneme.start_frame, phoneme.start_frame))
                        continue
                    position += 1
                    last_phoneme_text = pronunciation[position]
                    last_phoneme = phoneme
                try:
                    out_file.write("{:d} {:d} {}\n".format(last_phoneme.start_frame, word.end_frame,
                                                           languagemanager.export_conversion[last_phoneme_text]))
                except KeyError:
                    pass
        out_file.close()

    def export_json(self, path, sound_path="", use_rest_frame_settings=False):
        if len(self.children) > 0:
            start_frame = self.children[0].start_frame
            end_frame = self.children[-1].end_frame
        else:  # No phrases means no data, so do nothing
            return
        json_data = {"name": self.name, "start_frame": start_frame, "end_frame": end_frame,
                     "text": self.text, "num_children": self.num_children, "fps": self.fps, "sound_path": sound_path}
        list_of_phrases = []
        list_of_used_phonemes = []
        for phr_id, phrase in enumerate(self.children):
            dict_phrase = {"id": phr_id, "text": phrase.text, "start_frame": phrase.start_frame,
                           "end_frame": phrase.end_frame, "tags": phrase.tags}
            list_of_words = []
            for wor_id, word in enumerate(phrase.children):
                dict_word = {"id": wor_id, "text": word.text, "start_frame": word.start_frame,
                             "end_frame": word.end_frame, "tags": word.tags + phrase.tags}
                list_of_phonemes = []
                for pho_id, phoneme in enumerate(word.children):
                    dict_phoneme = {"id": pho_id, "text": phoneme.text, "frame": phoneme.start_frame,
                                    "tags": phoneme.tags + word.tags + phrase.tags}
                    list_of_phonemes.append(dict_phoneme)
                    if phoneme.text not in list_of_used_phonemes:
                        list_of_used_phonemes.append(phoneme.text)
                dict_word["phonemes"] = list_of_phonemes
                list_of_words.append(dict_word)
            dict_phrase["words"] = list_of_words
            list_of_phrases.append(dict_phrase)
        json_data["phrases"] = list_of_phrases
        json_data["used_phonemes"] = list_of_used_phonemes
        file_path = open(path, "w")
        json.dump(json_data, file_path, indent=True)
        file_path.close()

    ###

    def __str__(self):
        if self.is_root:
            out_string = "LipSync{}:{}|{}|start_frame:{}|end_frame:{}|Children:{}".format(
                self.object_type.capitalize(),
                self.name, self.text,
                self.start_frame,
                self.end_frame, self.children)
        else:
            out_string = "LipSync{}:{}|{}|start_frame:{}|end_frame:{}|Parent:{}|Children:{}".format(
                self.object_type.capitalize(),
                self.name, self.text,
                self.start_frame,
                self.end_frame, self.parent.name or self.parent.text, self.children)
        return out_string

    def __repr__(self):
        return self.__str__()
