''' Elementos principales de trabajo: controlador, variables, alarmas, etc.

'''

__author__="José A. Casares"
__date__="2016-02-14"
__version__="1.3"

import sys
from threading import Thread
import time
import re
from datetime import datetime
from sqlalchemy import *


class Subscriptor(object):
    pass

class Output(object):
    pass

class PLC(object):
    class Memory(object):
        class Tag(object):pass

class PLC(object):
    ''' Representación de un controlador.

    En general, se derivará como un driver.

    Attributes:
    memory (Memory{}): Áreas de memoria.
    connected (bool): Estado de la conexión.

    '''
    
    class Memory(object):
        ''' Representacióne un área de memoria.

        Args:
        plc (PLC): Controlador al que pertenece.

        Attributes:
        tag (tag{}): Diccionario de variables ordenadas por nombre.
        tagbyaddress (tag{}): Diccionario de variables ordenadas por dirección.

        '''

        class Tag(object):
            ''' Variable

            Args:
            memory (Memory): Memoria a la que pertenece (None si no esá asociada).
            key (str): Nombre.
            description (str): Descripción.
            address: Dirección (None si no esta asociada).
            
            Attributes:
            value: Valor.
            subscriptor (Subcriptor[]): Objetos suscritos a los cambios.
            
            '''
            
            def __init__(self, memory:PLC.Memory=None, key:str=None, description:str="", address=None):
                self.memory=memory
                self.key=key
                self.address=address
                self.description=description
                self.value=None
                self.subscriptor=[]

            def update(self, value):
                ''' Modifica el valor de una variable.

                En clases derivadas de Tag, debe redefinirse set, y después llamar a update.

                Args:
                value: Nuevo valor de la variable.

                '''
                if not self.value==value:
                    self.value=value
                    for subscriptor in self.subscriptor:
                        subscriptor.update(self)

            def set(self,value):
                ''' Modifica o asigna el valor de una variable.

                Puede redefinirse en clases derivadas.

                Args:
                value: Nuevo valor de la variable.

                '''
                self.update(self,value)

            def get(self):
                ''' Devuelve el valor de una variable.

                '''
                return self.value

            def subscribe(self, subscriptor: Subscriptor):
                ''' Suscribe un objeto a los cambios del valor de la variable.

                El objeto que se suscribe debe tener un método update,
                al que se llama cuando cambia el valor de la variable.

                Args:
                subscriptor: Objeto suscrito. 

                '''
                self.subscriptor.append(subscriptor)

        
        def __init__(self, plc:PLC):
            self.plc=plc
            self.tag={}
            self.tagbyaddress={}

        def create(self, tag_key, description:str="", address=None) -> Tag:
            ''' Crea una variable dentro de la memoria.

            Args:
            key (str): Nombre de la variable
            description (str): Descripción.
            address: Dirección.

            Returns (Tag):
            Variable que se ha creado.
            
            '''            
            return self.set(tag_key, self.Tag(self,tag_key,description,address))
                
        def set(self, tag_key, tag:Tag) -> Tag:
            ''' Modifica o asigna una variable a la memoria.

            Args:
            tag_key: Nombre o identificador de la variable.
            tag (Tag): Variable.

            Returns (Tag):
            La propia variable.

            '''
            self.tag[tag_key]=tag
            self.tagbyaddress[tag.address]=tag
            return tag

        def get(self, tag_key) -> Tag:
            ''' Devuelve una variable.

            Args:
            tag_key: Nombre o identificador de la variable.

            Returns (Tag):
            La variable con dicho identificador.

            '''
            return self.tag[tag_key]
               
        def len(self) -> int:
            ''' Devuelve el número de variables de la memoria.

            Returns (int):
            Número de variables.

            '''
            return len(self.tag)

        def __iter__(self):
            return iter(self.tag)


    def __init__(self):
        self.memory={}
        self.connected=False

    def create(self,memory_key) -> Memory:
        ''' Crea una memoria en el controlador.

        Args:
        memory_key (str): Nombre o identificador de la memoria.

        Returns (Memory):
        Memoria que se ha creado.
        
        ''' 
        return self.set(memory_key, self.Memory(self))

    def set(self, memory_key, memory:Memory) -> Memory:
        ''' Modifica o asigna una memoria al controlador.

        Args:
        memory_key: Nombre o identificador de la memoria.
        memory (Memory): Memoria.

        Returns (Memory):
        La propia memoria.

        '''
        self.memory[memory_key]=memory
        memory.plc=self
        return memory

    def get(self,memory_key):
        ''' Devuelve una memoria.

        Args:
        memory_key: Nombre o identificador de la memoria.

        Returns (Memory):
        La memoria con dicho identificador.

        '''
        return self.memory[memory_key]

    def len(self) -> int:
        ''' Devuelve el número de memorias del controlador.

        Returns (int):
        Número de memorias.

        '''
        return len(self.memory)

    def __iter__(self):
        return iter(self.memory)
    
    def connect(self):
        ''' Establece conexión con el controlador.

        Debe definirse en la clase derivada.
        '''
        pass

    def disconnect(self):
        ''' Termina la conexión con el controlador.

        Debe definirse en la clase derivada.
        '''
        pass


class Subscriptor(object):
    ''' Objeto que puede suscribirse a los cambios de valor de una variable.
 
    '''
    
    def update(self, tag:PLC.Memory.Tag):
        ''' Método que se llama cuando cambia el valor de una variable.

        Su acción debe definirse en las clases derivadas.

        Args:
        tag: Variable cuyo valor ha cambiado.

        '''        
        pass


class Expression(Subscriptor, PLC.Memory.Tag):
    ''' Expresión evaluable.

    La expresión se instancia pasándole el diccionario de variables,
    del cual puede formar parte. Una vez el diccionario está completo,
    se debe llamar al método analyze, que realiza las suscripciones.
    ¡La clase no comprueba referencias circulares!
    Las operaciones permitidas son: suma, resta, multiplicación, división,
    igualdad, superioridad e inferioridad. Para anidamientos se usan
    paréntesis.

    Args:
    definition (str): Definición de la expresión.
    tags: (Tag[]): Diccionario de variables que pueden
        formar parte de la expresión.

    Attributes:
    key (str): Nombre.
    value: Valor de la expresión.
    subscriptor (Subcriptor[]): Objetos suscritos a los cambios.

    Internal:
    __serialization (str[]): Expresión serializada.
    
    '''

    def __init__(self, key: str, definition:str, tags: dict, description:str=None):
        self.definition=definition
        self.tags=tags
        if description==None:
            self.description=definition
        else:
            self.description=description
        self.usedtags=[]
        self.__serialization=[]
        super().__init__(None, key, description)
    
    def analyze(self):
        ''' Analiza la definición de la expresión y realiza suscripciones.

        Debe llamarse cuando el diccionario de variables esté completo.

        '''
        elements=re.split("[ +\-*/()=<>]",self.definition)
        try:
            for element in elements:
                if len(element)>0 and element[0].isalpha():    # Si un elemento empieza por un carácter se interpreta como variable.
                    self.tags[element].subscribe(self)
                    self.usedtags.append(self.tags[element])
            self.__serialization=re.split("( |\+|\-|\*|/|\(|\<|\>|\))",self.definition)
        except:
            raise Exception("Bad expression: "+self.definition)

    def update(self, tag):
        ''' Evaluación de la expresión.

        Args:
        tag [Tag]: Variable cuyo valor ha cambiado.

        '''   
        evaluation=""
        try:
            for element in self.__serialization:
                if len(element)>0 and element[0].isalpha():
                    value=self.tags[element].get()
                    if value==None:
                        return None
                    else:
                        evaluation=evaluation+str(self.tags[element].get()) # Reemplaza cada variable por su valor
                else:
                    evaluation=evaluation+element
            self.value=eval(evaluation)
        except Exception as e:
            printexception(e,"Error evaluating expresion "+self.definition)
            

class Alarm(Expression):
    ''' Alarma.

    Args:
    key (str): Nombre o identificador de la alarma.
    definition (str): Definición de la alarma, a modo de expresión (ver Expression).
    tags: (Tag[]): Diccionario de variables que pueden
        formar parte de la expresión.
    destription (str): Texto descriptivo de la alarma. Puede contener expresiones,
        tal y como se definen en la clase Output.

    Attributes:
    alarmgroup (AlarmGroup[]): Grupos de alarma a los que pertenece.
    
    '''

    def __init__(self, key: str, definition:str, tags: dict, description:str=None):
        self.alarmgroup=[]
        super().__init__(key, definition, tags, description)

    def update(self, tag: PLC.Memory.Tag):
        ''' Método llamado automáticamente cuando cambia el valor de una de las variables.

        Args:
        tag (Tag): Variable que ha cambiado.

        '''
        oldvalue=self.value
        super().update(tag)
        if self.value and not oldvalue:
            for alarmgroup in self.alarmgroup:
                for output in alarmgroup.output:
                    output.write(self, datetime.utcnow(), True, {"alarmgroup":alarmgroup})
        elif not self.value and oldvalue:
             for alarmgroup in self.alarmgroup:
                for output in alarmgroup.output:
                    output.write(self, datetime.utcnow(), False, {"alarmgroup":alarmgroup})           


class AlarmGroup(object):
    ''' Grupo de alarmas.

    Args:
    key (str): Nombre o identificador del grupo de alarmas.

    Attributes:
    alarm (Alarm[]): Alarmas que componen el grupo.
    output (Output[]): Registros de los cambios.

    '''

    def __init__(self, key:str):
        self.key=key
        self.alarm=[]
        self.output=[]

    def addalarm(self, alarm:Alarm):
        ''' Añade una alarma al grupo.

        Args:
        alarm (Alarm): Alarma.

        '''
        self.alarm.append(alarm)
        alarm.alarmgroup.append(self)

    def addoutput(self, output:Output):
        ''' Añade un registro al grupo.

        Args:
        output (Output): Registro.

        '''
        self.output.append(output)

    def __iter__():
        return alarm.iter()

def printexception(e:Exception,text:str):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print(">==========")
    print(text)
    print(str(e))
    print(exc_type.__name__)
    print("Module: "+exc_traceback.tb_frame.f_code.co_filename)
    print("Line: "+str(exc_traceback.tb_lineno))
    print(exc_type)
    print("==========>")
