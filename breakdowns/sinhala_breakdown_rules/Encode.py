from Schwa_Analysis import shewa_analyse
from Transliterator import Transliterator

word = "කනවා"
y = Transliterator()
mid_word = y.encoder(word)
print(shewa_analyse(mid_word))