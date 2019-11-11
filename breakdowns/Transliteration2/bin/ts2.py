from py4j.java_gateway import JavaGateway
from py4j.java_gateway import java_import


gateway = JavaGateway()      
java_import(gateway.jvm,'testJ')
#gateway.launch_gateway(port=25333, jarpath='', classpath='', javaopts=[], die_on_exit=False, redirect_stdout=None, redirect_stderr=None, daemonize_redirect=True, java_path='java', create_new_process_group=False, enable_auth=False)                  # connect to the JVM
gateway.jvm.run()
#other_object = java_object.run() encoder("කියන්න")
#other_object.doThis(1,'abc')
gateway.jvm.System.out.println('Hello World!') # call a static method
int_class = gateway.jvm.int

random = gateway.jvm.java.util.Random()   # create a java.util.Random instance
number1 = random.nextInt(10)              # call the Random.nextInt method
number2 = random.nextInt(10)
print(number1, number2)