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
    'A', #
    'A_', #
    'AE', #
    'I', #
    'U',
    'E',
    'E_',
    'O',
    'O_',

    'K',
    'C', 
    'P',
    'W',
    'rest'
      # not really a phoneme - this is used in-between phrases when the mouth is at rest
]

# Phoneme conversion dictionary: CMU on the left to Preston Blair on the right
phoneme_conversion = {
    'a': 'A',  # odd     AA D
    'a:': 'A_',
    'ae': 'AE',
    'ae:': 'AE',  # at   AE T
    'i': 'I',
    'i:': 'I_',
    'u': 'U',  # hut  HH AH T
    'u:': 'U',
    'ri': 'i',
    'ru': 'i',  # ought AO T
    'ilu': 'i',
    'ilu:': 'i',
    'e': 'E',  # cow   K AW
    'e:': 'E_',
    'ai': 'I',   #check this
    'o': 'O',  # hide HH AY D
    'o:': 'O_',
    'ou': 'U',

    'k': 'K',
    'g': 'K',
    'j': 'k',
    'µ': 'k',
    'c':'C',
    't':'K',
    'd':'K',
    't^':'K',
    'd^':'K', #check this
    'n':'K',
    'p':'P',
    'b':'P',
    'm':'P',
    'mb':'P',
    'y':'K',
    'r':'K',
    'l':'K',
    'w':'W',
    's^':'SHA',
    's':'K',
    'h':'K',
    'f':'F',

    'ii':'I_',
    'ai':'AE',
    'uu':'U',
    'nd^':'K', #check this
    'uu':'U_',
    'd^':'K', #check this
    'c^':'C',
    'jn': 'K', #not right
    'ng':'K',
    '@':'K'






   

}
