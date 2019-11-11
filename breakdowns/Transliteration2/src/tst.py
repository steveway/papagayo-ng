import os.path,subprocess
from subprocess import STDOUT,PIPE

def compile_java(java_file):
    subprocess.check_call(['javac', java_file])

def execute_java(java_file, stdin):
    java_class,ext = os.path.splitext(java_file)
    cmd = ['java', java_class]
    proc = subprocess.Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    stdout,stderr = proc.communicate(stdin)
    print ('This was "' + stdout + '"')

#compile_java('Encode.java')
#execute_java('Encode.java', 'Jon')

fo = open("output_en.txt", "r")
phonesStr = fo.read()

temp_phonemes = phonesStr.split("-")
temp_phonemes1 = temp_phonemes[:len(temp_phonemes)-1]
print(temp_phonemes1)


