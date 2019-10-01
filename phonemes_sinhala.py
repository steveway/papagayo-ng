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
# Preston Blair phoneme set:
# AI O E U etc L WQ MBP FV
# etc=CDGKNRSThYZ

phoneme_set = [
    'AI',
    'O',
    'E',
    'U',
    'etc',  # this covers Preston Blair's CDGKNRSThYZ mouth shape
    'L',
    'WQ',
    'MBP',
    'FV',
    'rest'  # not really a phoneme - this is used in-between phrases when the mouth is at rest
]

# Phoneme conversion dictionary: CMU on the left to Preston Blair on the right
phoneme_conversion = {
    'a': 'AI',  # odd     AA D
    'a:': 'AI',
    'ae': 'AI',
    'ae:': 'AI',  # at   AE T
    'i': 'AI',
    'i:': 'AI',
    'u': 'AI',  # hut  HH AH T
    'u:': 'AI',
    'ri': 'AI',
    'ru': 'O',  # ought AO T
    'ilu': 'O',
    'ilu:': 'O',
    'e': 'O',  # cow   K AW
    'e:': 'O',
    'ai': 'O',
    'o': 'AI',  # hide HH AY D
    'o:': 'AI',
    'ou': 'AI',


    'k': 'MBP',  # be    B IY
    'g': 'etc',  # cheese   CH IY Z
    'n': 'etc',  # dee   D IY
    'g*': 'etc',  # thee DH IY
    'c': 'E',  # Ed    EH D
    'j': 'E',
    'jn': 'E',
    'jnn': 'E',  # hurt  HH ER T
    'j': 'E',
    't': 'E',
    'd': 'E',  # ate   EY T
    'n': 'E',
    't': 'E',
    'd': 'FV',  # fee    F IY
    'p': 'etc',  # green G R IY N
    'b': 'etc',  # he   HH IY
    'm': 'AI',  # it   IH T
    'bh': 'AI',
    'j': 'AI',
    'r': 'E',  # eat   IY T
    'l': 'E',
    'w': 'E',
    's': 'etc',  # gee  JH IY
    'h': 'etc',  # key   K IY
    'f': 'L',  # lee L IY
    'M': 'MBP',  # me    M IY
    
    'ZH': 'etc',  # seizure  S IY ZH ER
    # The following phonemes are not part of the CMU phoneme set, but are meant to fix bugs in the CMU dictionary
    'E21': 'E'  # E21 is used in ENGINEER
}
