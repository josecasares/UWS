"""Gestión de controlador a través de base de datos

"""

__author__="José A. Casares"
__date__="2016-04-30"
__version__="1.0"

from threading import Thread
from TagModule import *
from datetime import datetime
from sqlalchemy import *
import time

class DBPLC(PLC):
    """PLC con comunicación via base de datos.

    Args:
    connection (str): Cadena de conexión.
    pollingtime (float): Segundos entre escaneos.

    Attributes:
    engine (Engine): Conector con base de datos.
    thread (Thread): Hebra de escaneo.
    
    """


    class Memory(PLC.Memory):
        ''' Representación de un área de memoria (tabla).

        Args:
        plc (PLC): Controlador al que pertenece.

        Attributes:
        Table (Table): Tabla.

        '''

        class Tag(PLC.Memory.Tag):
            ''' Variable (columna) de controlador DBPLC.

            Args:
            memory (Memory): Memoria a la que pertenece.
            key (str): Nombre.
            description (str): Descripción.
            address: Dirección. No se usa, se conserva por compatibilidad.
            
            Attributes:
            value: Valor.
            subscriptor (Subcriptor[]): Objetos suscritos a los cambios.
            
            '''

            def __init__(self, memory:PLC.Memory, key:str, description:str="", address=None):
                super().__init__(memory,key,description)
                
            def set(self, value, date:datetime=None):
                ''' Modifica el valor de una variable. En este contexto inserta un dato en la tabla.
                Importante: si la memoria contiene más de una variable, las demás columnas se quedan en nulo.

                Args:
                value: Nuevo valor de la variable.
                datetime: Fecha y hora del valor (por defecto, la actual).

                '''
                if date==None:
                    date=func.now()
                plc=self.memory.plc
                if plc.connected:
                    try:
                        d=dict([("date",date),(self.key,value)])
                        i=self.memory.table.insert().values(**d)
                        i.compile().params
                        plc.engine.execute(i)
                        self.update(value)
                    except Exception as e:
                        self.memory.plc.connected=False
                        printexception(e,"Error writing to PLC")

            def get(self):
                ''' Devuelve el valor de una variable. En este contexto, valor más reciente.

                '''
                plc=self.memory.plc
                if plc.connected:
                    try:
                        s = select([self.column]).order_by(desc(text("date"))).limit(1)
                        self.value=plc.engine.execute(s).fetchone()[0]
                        return self.value
                    except Exception as e:
                        printexception(e,"Error reading from PLC")

            def get_data(self, datefrom:datetime, dateto:datetime):
                ''' Devuelve los registros de esa variable entre dos momentos.

                Args:
                datefrom (datetime): Fecha y hora de inicio.
                dateto (datetime): Fecha y hora de fin.

                Returns ([[time(UNIX),[float]]):
                Lista con pares tiempo (formato UNIX) y valor.
            
                '''
                plc=self.memory.plc
                _from=datetime.fromtimestamp(datefrom/1000).strftime('%Y-%m-%d %H:%M:%S')
                _to=datetime.fromtimestamp(dateto/1000).strftime('%Y-%m-%d %H:%M:%S')
                if plc.connected:
                    try:
                        s = select([literal_column("date"),
                            self.column]).where(literal_column("date")>_from).where(literal_column("date")<_to).order_by(asc(text("date")))               
                        values=plc.engine.execute(s).fetchall()
                        results=[]
                        for value in values:
                            results.append([int(time.mktime(value[0].timetuple()))*1000,value[1]])
                        results2=[[datefrom,results[0][1]]]+results+[[dateto,results[-1][1]]] # Añade un primer y último elemento
                        print(results2)
                        return results2
                    except Exception as e:
                        printexception(e,"Error reading from PLC")
                        

        def __init__(self, plc:PLC):
            self.table=Table()
            super().__init__(plc)

        def set_row(self, dictionary:dict, date:datetime=None):
            ''' Inserta un regitro en la tabla.

            Args:
            dictionary ({str,float}): Valor de variables. Si no están todas, se inserta un nulo.
            date (datetime): Fecha y hora. Por defecto, la actual.

            '''
            
            if date==None:
                date=func.now()
            plc=self.plc
            if plc.connected:
                try:
                    d=dict({"date":date},**dictionary)
                    i=self.table.insert().values(**d)
                    i.compile().params  
                    plc.engine.execute(i)
                    for tag_key in self:
                        if tag_key in dictionary.values():
                            tag=self.tag[tag_key]
                            value=dictionary[tag_key]
                            tag.update(value)
                except Exception as e:
                    printexception(e,"Error writing to PLC")

        def get_row(self):
            ''' Devuelve el registro más reciente de la tabla.

            Returns ({datetime,float...}):
            Diccionario con momento de registro y valores. 
                
            '''
            
            plc=self.plc
            if plc.connected:
                try:
                    s = select([self.table]).order_by(desc(text("date"))).limit(1)
                    self.values=plc.engine.execute(s).fetchone()
                    return self.values 
                except Exception as e:
                    printexception(e,"Error reading from PLC")


    def __init__(self, connection:str, pollingtime:float=0.0):
        super().__init__()
        self.connection=connection
        self.pollingtime=pollingtime
        self.engine=create_engine(connection)
        self.thread=Thread(target=self.__Polling, args=())

    def connect(self):
        ''' Conexión con el controlador.

        '''
        self.thread.start()

    def disconnect(self):
        ''' Termina la conexión con el controlador.

        ''' 
        self.connected=false

    def read(self):
        ''' Lectura de todas las variables del controlador (datos más recientes de las tablas.

        '''
        try:
            for memory_key in self.memory:
                memory=self.memory[memory_key]
                for tag_key in memory:
                    tag=memory.tag[tag_key]
                    tag.get()

        except Exception as e:
            self.disconnect()
            printexception(e,"Error reading from PLC")

    def __Polling(plc):
        ''' Lectura inicial y periódica de los valores más recientes.
        Establece la conexión con la base de datos.
        Si no existen la tablas, las crea de acuerdo a definición de variables y memoria.

        '''
        while True:
            if plc.connected:
                plc.read()
                if plc.pollingtime>0.0:
                    time.sleep(plc.pollingtime)
            else:
                print("Connecting to DBPLC.")
                plc.engine.connect()
                plc.connected=True
                for key_memory in plc.memory:
                    memory=plc.memory[key_memory]
                    metadata = MetaData()
                    columns=[key_memory, metadata, Column("date",DateTime,primary_key=True)]
                    for key_tag in plc.memory[key_memory]:
                        tag=memory.tag[key_tag]
                        tag.column=Column(key_tag,Float)
                        columns.append(tag.column)
                    memory.table=Table(*columns)
                    memory.table.create(plc.engine,checkfirst=True)
                        
                

