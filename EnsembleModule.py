''' Motor del SCADA

Gestiona controladores, variables, comunicaciones.

'''

__author__="José A. Casares"
__date__="2016-02-14"
__version__="1.3"

from TagModule import *
from MBPLCModule import *
from OPCPLCModule import *
from DBPLCModule import *
from OutputModule import *
import csv
import time

class Ensemble(object):
    ''' Motor del SCADA

    Attributes:
    plc (PLC{}): Diccionario de controladores.
    tag (Tag{}): Diccionario de variables.
    alarmgroup (Alarmgroup{}): Diccionario de grupos de alarmas

    '''
    
    def __init__(self):
        self.plc={}
        self.tag={}
        self.alarmgroup={}

    def __setitem__(self, plc_key, plc:PLC):
        ''' Agrega un controlador al Ensemble.

        Args:
        plc_key: Identificador del controlador.
        plc (PLC): Controlador.

        Returns (PLC):
        El propio controlador.

        '''
        return self.setplc(plc_key, plc)

    def __getitem__(self,plc_key) -> PLC:
        ''' Devuelve un controlador del Ensemble.

        Args:
        plc_key: Identificador del controlador.

        Returns (PLC):
        El propio controlador.

        '''
        return self.getplc(plc_key)

    def __iter__(self):
        return iter(self.plc)

    def setplc(self, plc_key, plc:PLC) -> PLC:
        ''' Agrega un controlador al Ensemble.

        Args:
        plc_key: Identificador del controlador.
        plc (PLC): Controlador.

        Returns (PLC):
        El propio controlador.

        '''
        self.plc[plc_key]=plc
        return plc

    def getplc(self,plc_key) -> PLC:
        ''' Devuelve un controlador del Ensemble.

        Args:
        plc_key: Identificador del controlador.

        Returns (PLC):
        El propio controlador.

        '''
        return self.plc[plc_key]   

    def settag(self, tag_key:str, tag: PLC.Memory.Tag) -> PLC.Memory.Tag:
        ''' Agrega o sustituye una variable.

        Args:
        tag_key: Nombre simbólico.
        tag (Tag): Variable.

        Returns (Tag):
        La propia variable.

        '''
        self.tag[tag_key]=tag
        return tag
    
    def gettag(self, tag_key) -> PLC.Memory.Tag:
        ''' Devuelve una variable

        Args:
        tag_key: Nombre simbólico

        Returns (Tag):
        Variable
        
        '''
        return self.tag[tag_key]

    def setalarmgroup(self, alarmgroup_key:str, alarmgroup: AlarmGroup) -> AlarmGroup:
        ''' Agrega un grupo de alarmas.

        Args:
        alarmgroup_key: Identificador del grupo de alarmas.
        alarmgroup (AlarmGroup): Grupo de alarmas.

        Returns (AlamrGroup):
        El propio grupo de alarmas.
        
        '''
        self.alarmgroup[alarmgroup_key]=alarmgroup
        return alarmgroup

    def getalarmgroup(alarmgroup_key:str) -> AlarmGroup:
        ''' Devuelve un grupo de alarmas.

        Args:
        alarmgroup_key: Identificador del grupo de alarmas.

        Returns (AlarmGroup):
        Grupo de alarmas.
        
        '''
        return self.alarmgroup[alarmgroup_key]


    def deploy(self):
        '''  Despliegue rápido del motor.

        Analiza las expresiones e inicia las comunicaciones.
        
        '''
        self.analyze_alarms()
        
        for plc_key,plc in self.plc.items():
            plc.connect()


    def import_tags(self, filename:str, prefix:str="", delimiter:str=";", quotechar:str='"', encoding:str="utf8"):
        '''Importa las variables de un fichero csv.

        La primera línea del fichero contiene el encabezado.
        Las siguientes deben incluir los datos de las variables con formato:
        [nombre];[plc];[memoria];[posición]

        Args:
        filename (str): Ruta del fichero con las variables.
        prefix (str): Prefijo que se añade a las variables.
        delimiter (str): Separador, normalmente coma o punto y coma.
        quotechar (str): Carácter para las comillas.
        encoding (str): Codificación del fichero.
        
        '''

        with open(filename, newline="", encoding=encoding) as file:
            next(file) # Saltamos la cabecera
            stream=csv.reader(file,delimiter=delimiter, quotechar=quotechar)
            for row in stream:
                tag_key=row[0]
                plc_key=row[1]
                memory_key=row[2]
                address=row[3]
                description=row[4]

                try:
                    tag=self.plc[plc_key].memory[memory_key].create(prefix+tag_key,description,address)
                    self.tag[tag_key]=tag
                except Exception as e:
                    printexception(e,"Error importing tag "+prefix+tag_key+" to memory "+memory_key+" of PLC "+plc_key)

    def import_alarms(self, filename:str, alarmgroup:str="default", delimiter:str=";", quotechar:str='"', encoding:str="utf8"):
        '''Importa las alarmas de un fichero csv.

        La primera línea del fichero contiene el encabezado.
        Las siguientes deben incluir los datos de las alarmas con formato:
        [definition];[description]

        Args:
        filename (str): Ruta del fichero con las alarmas.
        alarmgroup (str): Nombre del grupo al que se agregan las alarmas. Se crea si no exite.
        delimiter (str): Carácter delimitador de los elementos en una fila.
        quotechar (str): Caracter que hace de comillas.
        encoding (str): Codificación de caracteres.
        
        '''

        if not str in self.alarmgroup:
            self.alarmgroup[alarmgroup]=AlarmGroup(alarmgroup)
        with open(filename, newline="", encoding=encoding) as file:
            next(file) # Saltamos la cabecera
            stream=csv.reader(file,delimiter=delimiter, quotechar=quotechar)
            for row in stream:
                alarm_key=row[0]
                definition=row[1]
                description=row[2]
                alarm=Alarm(alarm_key,definition,self.tag,description)
                self.tag[alarm.key]=alarm
                self.alarmgroup[alarmgroup].addalarm(alarm)

    def analyze_alarms(self):
        ''' Analiza todas las expresiones en el Ensemble.

        '''    
        for alarmgroup_key,alarmgroup in self.alarmgroup.items():
            for alarm in alarmgroup.alarm:
                alarm.analyze()
