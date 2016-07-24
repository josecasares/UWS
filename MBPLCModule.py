"""Gestión de controlador con comunicación Modbus.

"""

__author__="José A. Casares"
__date__="2016-02-14"
__version__="1.3"

from threading import Thread
from pymodbus3.client.sync import ModbusTcpClient as ModbusClient
from TagModule import *
import time


class MBPLC(PLC):
    """PLC con comunicación Modbus.

    Args:
    address (str): Dirección IP (o nombre) del controlador.
    port (int): Puerto de conexión. Típicamente el 502.
    unit (int): Número de esclavo.
    method (str): Método de conexión (RTU/ASCII)
    retries (int): Reintentos de lectura/escritura.
    client (ModbusClient): Cliente modbus.
    pollingtime (float): Segundos entre escaneos.

    Attributes:
    coil (Memory): Memoria de bobinas.
    input (Memory): Memoria de entradas digitales.
    holding (Memory): Memoria de registros de retención.
    register  (Memory): Memoria de registros de entrada.
    client (ModbusClient): Cliente Modbus.
    thread (Thread): Hebra de escaneo.
    
    """

    class COIL:
        """Tipo de memoria COIL."""
        pass
    class INPUT:
        """Tipo de memoria INPUT."""
        pass
    class HOLDING:
        """Tipo de memoria HOLDING."""
        pass
    class REGISTER:
        """Tipo de memoria REGISTER."""
        pass


    class Memory(PLC.Memory):
        ''' Representacióne un área de memoria.

        Args:
        plc (PLC): Controlador al que pertenece.
        memorytype (type): Tipo de memoria (COIL, INPUT, HOLDING, REGISTER).

        Attributes:
        minindex (int): Dirección más baja de la memoria leída.
        maxindex (int): Dirección más alta de la memoria leída.

        '''

        class Tag(PLC.Memory.Tag):
            ''' Variable de controlador Modbus.

            Args:
            memory (Memory): Memoria a la que pertenece.
            key (str): Nombre.
            description (str): Descripción.
            address: Dirección (None si no esta asociada).
            
            Attributes:
            value: Valor.
            subscriptor (Subcriptor[]): Objetos suscritos a los cambios.
            
            '''

            def __init__(self, memory:PLC.Memory, key:str, description:str="", address=None):
                if type(address)==str:
                    address=int(address)
                super().__init__(memory,key,description,address)
                if memory.minindex is None or memory.minindex>address:
                    memory.minindex=address
                if memory.maxindex is None or memory.maxindex<address:
                    memory.maxindex=address
                
            def set(self, value):
                ''' Modifica el valor de una variable.

                Args:
                value: Nuevo valor de la variable.

                '''

                plc=self.memory.plc
                if plc.connected:
                    try:
                        if self.memory.memorytype==MBPLC.COIL:
                            if isinstance(value,str):
                                if value.upper()=="TRUE" or value=="1":
                                    value=True
                                elif value.upper()=="FALSE" or value=="0":
                                    value=False
                            rw = plc.client.write_coil(self.address,value,unit=plc.unit)
                        if self.memory.memorytype==MBPLC.HOLDING:
                            if isinstance(value,str):
                                value=int(value)
                            rw = plc.client.write_register(self.address,value,unit=plc.unit)
                        self.update(value)
                    except Exception as e:
                        self.memory.plc.connected=False
                        printexception(e,"Error writing to PLC")
                        

                
        def __init__(self, plc:PLC, memorytype:type):
            self.memorytype=memorytype
            self.minindex=None
            self.maxindex=None
            super().__init__(plc)
    

    def __init__(self, address:str, port:int=502, unit:int=1, method:str="rtu", retries:int=3, pollingtime:float=1.0):
        super().__init__()
        self.coil=self.create("coil",MBPLC.COIL)
        self.input=self.create("input",MBPLC.INPUT)
        self.holding=self.create("holding",MBPLC.HOLDING)
        self.register=self.create("register",MBPLC.REGISTER)
        self.address=address
        self.unit=unit
        self.port=port
        self.method=method
        self.retries=retries
        self.pollingtime=pollingtime
        self.client = ModbusClient(address, port, method=method, retries=retries)
        self.thread=Thread(target=self.__Polling, args=())

    def create(self,memory_key, memorytype:type):
        ''' Crea una memoria en el controlador.

        Args:
        memory_key (str): Nombre o identificador de la memoria.
        memorytype (type): Tipo de memoria (COIL, INPUT, HOLDING, REGISTER).

        Returns (Memory):
        Memoria que se ha creado.
        
        ''' 
        return self.set(memory_key, self.Memory(self, memorytype))

    def connect(self):
        ''' Conexión con el controlador

        '''
        self.thread.start()

    def disconnect(self):
        ''' Termina la conexión con el controlador.

        ''' 
        self.connected=false
        self.client.close()

    def read(self):
        ''' Lectura de un área de memoria del controlador real.

        Si falla la lectura (tras el número de reintentos)
        se actualiza el estado de conexión a desconectado.

        '''
        try:
            if not self.coil.minindex is None:
                rr = self.client.read_coils(self.coil.minindex, self.coil.maxindex-self.coil.minindex+1,unit=self.unit)
                for i in range(self.coil.minindex,self.coil.maxindex+1):
                    if i in self.coil.tagbyaddress:
                        self.coil.tagbyaddress[i].update(rr.bits[i-self.coil.minindex])
            if not self.input.minindex is None:                
                rr = self.client.read_discrete_inputs(self.input.minindex, self.input.maxindex-self.input.minindex+1,unit=self.unit)
                for i in range(self.input.minindex,self.input.maxindex+1):
                    if i in self.input.tagbyaddress:
                        self.input.tagbyaddress[i].update(rr.bits[i-self.input.minindex])
            if not self.holding.minindex is None:                    
                rr = self.client.read_holding_registers(self.holding.minindex, self.holding.maxindex-self.holding.minindex+1,unit=self.unit)
                for i in range(self.holding.minindex,self.holding.maxindex+1):
                    if i in self.holding.tagbyaddress:
                        self.holding.tagbyaddress[i].update(rr.registers[i-self.holding.minindex])
            if not self.register.minindex is None:                    
                rr = self.client.read_input_registers(self.register.minindex, self.register.maxindex-self.register.minindex+1,unit=self.unit)
                for i in range(self.register.minindex,self.register.maxindex+1):
                    if i in self.register.tagbyaddress:
                        self.register.tagbyaddress[i].update(rr.registers[i-self.register.minindex])
        except Exception as e:
            self.coil.plc.disconnect()
            printexception(e,"Error reading from PLC")

    def __Polling(plc):
        ''' Lectura de todas las áreas de escaneo.

        Establece la conexión con los controladores,
        si no se ha hecho antes, o se ha perdido.

        '''
        while True:
            if plc.connected:
                plc.read()
                time.sleep(plc.pollingtime)
            else:
                print("Connecting to MBPLC "+plc.address+":"+str(plc.port)+"("+str(plc.unit)+")")
                plc.connected=plc.client.connect()

