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
#
# This file contains a mapping between the CMU phoneme set to the phoneme set
# you use for animating. By default, the animation phoneme set is the Preston
# Blair phoneme set, as found in the book:
# "Cartoon Animation", by Preston Blair, page 186.
#
# The phonemeset is defined in the two tables below. The first table contains
# the basic list of phonemes to use in your animation. The second table 
# contains a mapping from the CMU phonemes to the phonemes in the first table.
#
# This is a simple and stupid 1-to-1 mapping from CMU to CMU

phoneme_set = [
    'AA0',
    'AA1',
    'AA2',
    'AE0',
    'AE1',
    'AE2',
    'AH0',
    'AH1',
    'AH2',
    'AO0',
    'AO1',
    'AO2',
    'AW0',
    'AW1',
    'AW2',
    'AY0',
    'AY1',
    'AY2',
    'B',
    'CH',
    'D',
    'DH',
    'EH0',
    'EH1',
    'EH2',
    'ER0',
    'ER1',
    'ER2',
    'EY0',
    'EY1',
    'EY2',
    'F',
    'G',
    'HH',
    'IH0',
    'IH1',
    'IH2',
    'IY0',
    'IY1',
    'IY2',
    'JH',
    'K',
    'L',
    'M',
    'N',
    'NG',
    'OW0',
    'OW1',
    'OW2',
    'OY0',
    'OY1',
    'OY2',
    'P',
    'R',
    'S',
    'SH',
    'T',
    'TH',
    'UH0',
    'UH1',
    'UH2',
    'UW0',
    'UW1',
    'UW2',
    'V',
    'W',
    'Y',
    'Z',
    'ZH',
    # The following phonemes are not part of the CMU phoneme set, but are meant to fix bugs in the CMU dictionary
    'E21',
    'rest'  # not really a phoneme - this is used in-between phrases when the mouth is at rest
]

# Phoneme conversion dictionary: CMU on the left to Preston Blair on the right
phoneme_conversion = {
    'AA0': 'AA0',
    'AA1': 'AA1',
    'AA2': 'AA2',
    'AE0': 'AE0',
    'AE1': 'AE1',
    'AE2': 'AE2',
    'AH0': 'AH0',
    'AH1': 'AH1',
    'AH2': 'AH2',
    'AO0': 'AO0',
    'AO1': 'AO1',
    'AO2': 'AO2',
    'AW0': 'AW0',
    'AW1': 'AW1',
    'AW2': 'AW2',
    'AY0': 'AY0',
    'AY1': 'AY1',
    'AY2': 'AY2',
    'B': 'B',
    'CH': 'CH',
    'D': 'D',
    'DH': 'DH',
    'EH0': 'EH0',
    'EH1': 'EH1',
    'EH2': 'EH2',
    'ER0': 'ER0',
    'ER1': 'ER1',
    'ER2': 'ER2',
    'EY0': 'EY0',
    'EY1': 'EY1',
    'EY2': 'EY2',
    'F': 'F',
    'G': 'G',
    'HH': 'HH',
    'IH0': 'IH0',
    'IH1': 'IH1',
    'IH2': 'IH2',
    'IY0': 'IY0',
    'IY1': 'IY1',
    'IY2': 'IY2',
    'JH': 'JH',
    'K': 'K',
    'L': 'L',
    'M': 'M',
    'N': 'N',
    'NG': 'NG',
    'OW0': 'OW0',
    'OW1': 'OW1',
    'OW2': 'OW2',
    'OY0': 'OY0',
    'OY1': 'OY1',
    'OY2': 'OY2',
    'P': 'P',
    'R': 'R',
    'S': 'S',
    'SH': 'SH',
    'T': 'T',
    'TH': 'TH',
    'UH0': 'UH0',
    'UH1': 'UH1',
    'UH2': 'UH2',
    'UW0': 'UW0',
    'UW1': 'UW1',
    'UW2': 'UW2',
    'V': 'V',
    'W': 'W',
    'Y': 'Y',
    'Z': 'Z',
    'ZH': 'ZH',
    # The following phonemes are not part of the CMU phoneme set, but are meant to fix bugs in the CMU dictionary
    'E21': 'E21'
}
