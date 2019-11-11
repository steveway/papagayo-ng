class Transliterator:
    line = ""
    enter = ['\r', '\n']
    scheme = {}
    char_repeats = ["^", ":"]
    char_omits = ["m", "w"]
    char_specials = ["෿", ".", ",", "'", "’", "‘", "‛", "\"", "“", "-", "–", "_", ";", 
		  ":", "+", "(", ")", "{", "}", "'", "‒", "—", "­", "´", "‚", "﻿", "෾", "",
		  "[", "]", "?", "<", ">", "=", "*", "&", "^", "%", "$", "#", "@", "!", "~", "|", "\\", "/"]
    char_numbers = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
    char_letters = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n",
		  "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
		  "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]

       
    def encode_scheme(self):
        f= open("breakdowns/sinhala_breakdown_rules/Scheme_Enc.txt",'r',encoding='utf-8')
        while(True):
            line = f.readline()
            #print(line)
            if(line == ""):
                break
            key, val = line.split()
            self.scheme[key] = Node(val[0:val.index('*')],val[val.index('*')+1:])
        
        return self.scheme

    def encoder(self,word):
        self.encode_scheme()
        f2 = open("Out.txt", "w",encoding='utf-16')

        str1 = ""
        str2 = ""
        str3 = ""

        str1 = word
        f2.write(str1 + '\t')
        for i in range(len(str1)):
            f2.write('\n' + str1[i])
            f2.write('\t' + str1[i])

            if(str1[i] in self.scheme):
                f2.write('\n' + 'containskey')
                localNode = Node(self.scheme[str1[i]].word,self.scheme[str1[i]].cat)
                f2.write('\n' + localNode.word + " " + localNode.cat)
                
                if(localNode.cat == "m"):
                    if(localNode.word == "x"):
                        str3 = str3
                    else:
                        str3 = str3[0:len(str3)-2]

                if(localNode.word == ""):
                    str3 = str3 + localNode.word
                else:
                    str3 = str3 + localNode.word + "-"

                if(localNode.cat == "c"):
                    if(localNode.word != "x"):
                        str3 = str3 + "@-"

            else:
                f2.write('\n' + "elseeee")
                if(str1[1] in self.char_specials):
                    str3 = str3 + " "
                elif(str1[i] in self.char_numbers):
                    str3 = str3 + str1[i]
                else:
                    if(i>3):
                        last_char = str3[len(str3)-2:len(str3)-1]
                        if(last_char in self.char_repeats): #If the proceeding phone has two chars
                            str3 = str3 + str3[len(str3)-3:len(str3)]
                        elif(last_char in self.char_omits):  #Do not repeat the proceeding phone for these phones
                            str3 = str3[0:len(str3)]
                        else:  #If the proceeding phone has only one char
                            str3 = str3 + str3[len(str3)-2:len(str3)]

        str2 = str2 + str3 + " "

        str3 = ""
        
        f2.close()

        return str2


        

class Node:
    def __init__(self,word,cat):
        self.word = word
        self.cat = cat
    def show(self):
        print("self.word")
        print(self.word)
        print("self.cat")
        print(self.cat)

y = Transliterator()
print(y.encoder("කනවා"))
