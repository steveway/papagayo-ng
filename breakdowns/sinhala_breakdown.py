import os.path,subprocess
from subprocess import STDOUT,PIPE
from breakdowns.sinhala_breakdown_rules.Schwa_Analysis import shewa_analyse
from breakdowns.sinhala_breakdown_rules.Transliterator import Transliterator

#!/usr/local/bin/python
# -*- coding: cp1252 -*-

# this language module is written to be part of
# Papagayo-NG, a lip-sync tool for use with several different animation suites
# Original Copyright (C) 2005 Mike Clifton
#
# this module Copyright (C) 2005 Myles Strous
# Contact information at http://www-personal.monash.edu.au/~myless/catnap/index.html
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

"""functions to take a Sinhala word and return a list of phonemes
"""


def breakdownWord(input_word, recursive=False):
    word = input_word
    y = Transliterator()
    mid_word = y.encoder(word)
    phonesStr = shewa_analyse(mid_word)
    
    temp_phonemes = phonesStr.strip('-').split("-")
    temp_phonemes_new = temp_phonemes[:len(temp_phonemes)-1]


    return temp_phonemes_new



if __name__ == '__main__':
    # test the function
    test_words = ['Holas', 'amigos', 'si', 'espa�ol', 'padr�', 'Selecciones', 'de', 'la', 'semana', 'Los', 'mejores',
                  'sitios', 'los', 'derechos', 'humanos', 'en', 'am�rica', 'latina', 'y', 'f�rger', 'p�', 'h�nsyn']
    for eachword in test_words:
        print(eachword, breakdownWord(unicode(eachword, input_encoding)), " ".join(
            breakdownWord(unicode(eachword, input_encoding))))
    
