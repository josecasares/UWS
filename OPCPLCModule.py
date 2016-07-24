"""Gestión de controlador con comunicación OPC UA.

"""

__author__="José A. Casares"
__date__="2016-02-14"
__version__="1.3"

from threading import Thread
from TagModule import *
import time
from opcua import ua, Client


class OPCPLC(PLC):
    """PLC con comunicación OPC UA.

    Args::
    address (str): Dirección IP (o nombre) del controlador.
    port (int): Puerto de conexión.
    interval (float): Intervalo de actualización en segundos.

    Attributes:
    subscription: Grupo al que se suscriben las variables.
    handler: Manejador de las actualizaciones de los valores.
    objects: Nodo de objetos.
    tagbynodeid (Tag{}): Diccionario de variables por identificador de nodo.
    client: Cliente OPC UA.
    opctype (VariantType{}): Principales tipos de datos OPC.
    
    """
    opctype={
        1:ua.VariantType.Boolean,
        2:ua.VariantType.SByte,
        3:ua.VariantType.Byte,
        4:ua.VariantType.Int16,
        5:ua.VariantType.UInt16,
        6:ua.VariantType.Int32,
        7:ua.VariantType.UInt32,
        8:ua.VariantType.Int64,
        9:ua.VariantType.UInt64,
        10:ua.VariantType.Float,
        11:ua.VariantType.Double,
        12:ua.VariantType.String,
        13:ua.VariantType.DateTime}

    class Memory(PLC.Memory):
        ''' Representacióne un área de memoria.

        No usada en OPC.

        Args:
        plc (PLC): Controlador al que pertenece.

        Attributes:
        tag (tag{}): Diccionario de variables ordenadas por nombre.
        tagbyaddress (tag{}): Diccionario de variables ordenadas por dirección.

        '''

        class Tag(PLC.Memory.Tag):
            ''' Variable

            Args:
            memory (Memory): Memoria a la que pertenece (no usada en OPC).
            key (str): Nombre.
            description (str): Descripción.
            address: Dirección. Se pasa la ruta hasta el nodo con el carácter '\' como separación.
                Los nodos vienen precedidos del tipo en forma de entero, separados por dos puntos.
                Por ejemplo, una dirección podria ser "2:Data\2:Static\2:Scalar\2:Variable".
                Para más información de una estructura en particular, una vez conectado
                llamar al método print_tree().
            
            Attributes:
            node: Nodo OPC asociado.
            type: Tipo de dato.
            value: Valor.
            subscriptor (Subcriptor[]): Objetos suscritos a los cambios.
            
            '''

            def __init__(self, memory:PLC.Memory, key:str, description:str="", address=None):
                self.node=None
                self.type=None
                super().__init__(memory,key,description,address)

            def opcsubscribe(self):
                ''' Suscripción al nodo OPC.

                '''
                plc=self.memory.plc
                address=self.address.split("\\")
                self.node=plc.objects.get_child(address)
                self.type=int(self.node.get_data_type().Identifier)
                plc.tagbynodeid[self.node.nodeid.Identifier]=self
                plc.subscription.subscribe_data_change(self.node)
                self.node.get_value()

            def set(self,value):
                ''' Modifica o asigna el valor de una variable.

                Args:
                value: Nuevo valor de la variable.

                '''
                try:
                    if self.type==1:
                        self.node.set_value(ua.Variant(bool(value),OPCPLC.opctype[self.type])) 
                    if self.type>=2 and self.type<=9:
                        self.node.set_value(ua.Variant(int(value),OPCPLC.opctype[self.type]))
                    if self.type>=10 and self.type<=11:
                        self.node.set_value(ua.Variant(float(value),OPCPLC.opctype[self.type]))
                    if self.type==12:
                        self.node.set_value(ua.Variant(str(value),OPCPLC.opctype[self.type]))
                    if self.type==13:
                        self.node.set_value(ua.Variant(datetime.strptime(value,"%Y-%m-%d %H:%M:%S"),OPCPLC.opctype[self.type]))

                    self.__update(value)
                except Exception as e:
                    printexception(e,"Error in assignment. Tag="+self.key+", Value="+value)


    def __init__(self, address:str, port:int=502, interval:float=3):
        super().__init__()
        self.address=address
        self.port=port
        self.interval=interval
        self.handler=OPCPLC.Handler(self)
        self.subscription=None
        self.objects=None
        self.tagbynodeid={}
        self.client = Client("opc.tcp://"+self.address+":"+str(self.port)+"/")
        self.create("")

    def connect(self):
        ''' Conexión con el controlador

        '''
        try:
            self.client.connect()
            self.objects=self.client.get_objects_node()
            self.subscription=self.client.create_subscription(self.interval, self.handler)
            for key_memory in self.memory:
                memory=self.get(key_memory)
                for key_tag in memory:
                    memory.get(key_tag).opcsubscribe()
            self.connected=True
        except Exception as e:
            printexception(e,"Error connecting to OPC server")
        
    def __tree(self, root, level:int=0):
        ''' Recursión para imprimir el árbol de nodos.

        Args:
        root: nodo raíz en la recursión.
        level (int): Nivel de recursión.

        '''        
        nodes=root.get_children()
        for node in nodes:
            node2=self.client.get_node(node.nodeid)
            name=node2.get_browse_name().to_string()
            print(('   '*level)+name)
            self.tree(node, level+1)

            
    def print_tree(self):
        ''' Imprime la estructura de nodos.

        '''
        self.__tree(self.client.get_objects_node())


    class Handler(object):
        ''' Manejador de los cambios en los valores de los nodos.

        Args:
        plc (PLC): Controlador.

        '''
        
        def __init__(self,plc):
            self.plc=plc

        def datachange_notification(self, node, val, data):
            ''' Método llamado cuando cambia el valor de un nodo.

            Args:
            node: Nodo.
            val: Valor.
            data: Datos.

            '''
            self.plc.tagbynodeid[node.nodeid.Identifier].update(val)
            
