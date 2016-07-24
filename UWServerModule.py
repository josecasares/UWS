''' Conexiones con la interfaz del SCADA.

'''

__author__="José A. Casares"
__date__="2016-02-14"
__version__="1.3"

import http.server
import socketserver
from  EnsembleModule import *
import asyncio
from autobahn.asyncio.websocket import WebSocketServerProtocol, WebSocketServerFactory
import socketserver
import json
import datetime


class WSHandle(WebSocketServerProtocol, Output):
    ''' Manejador de las conexiones por websocket.

    Es necesario pasarle el Ensemble antes de lanzarlo
    para que tenga acceso a su información.
    
    '''
    ensemble=None

    def onMessage(self, payload, isBinary):
        ''' Evento de mensaje recibido.

        Acepta texto (isBinary=false) en JSON en forma de diccionario:
        Si action=subscribe, suscribe tags, la lista de variables, y
        devuelve sus valores (action=values, y tags contiene la lista
        de variables y valores). También se suscribe a grupos de alarmas,
        definidos en la lista alarmgroups.
        Si action=change, modifica el valor de la variable tag.
        La respuesta se envía en JSON.

        Args:
        payload: Contenido.
        isBinary: La información se envía en binario.
    
        '''
        if isBinary:
            print("Binary message received: {0} bytes".format(len(payload)))
        else:
            message_raw=format(payload.decode('utf8'))
            #print(message_raw)
            try:
                message=json.loads(message_raw)
                
                # Subscripción a variables
                if message["action"]=="subscribe":
                    tags=message["tags"]
                    tagvalues=self.transform_read(tags,True)
                    response={"action":"values",
                              "tags":tagvalues}
                    payload = json.dumps(response).encode('utf8')
                    self.sendMessage(payload, isBinary = False)
                    if "alarmgroups" in message:
                        alarmgroups=message["alarmgroups"]
                        alarms=[]
                        for key in alarmgroups:
                            alarmgroup=self.ensemble.alarmgroup[key]
                            for alarm in alarmgroup.alarm:
                                if alarm.value:
                                    tupl=[id(alarm),"",self.transform(alarm),"True",alarmgroup.key]
                                    alarms.append(tupl)
                            alarmgroup.addoutput(self)
                        response={"action":"alarms",
                                  "alarms":alarms}
                        payload = json.dumps(response).encode('utf8')
                        self.sendMessage(payload, isBinary = False)

                # Modificación de variables
                elif message["action"]=="change":
                    self.ensemble.tag[message["tag"]].set(message["value"])

                # Inserción en formulario (tabla)
                elif message["action"]=="set_row":
                    date=message["date"]
                    tags=message["tags"]
                    memory=self.ensemble.tag[list(tags.keys())[0]].memory
                    memory.set_row(tags,date)

                # Actualización de tendencia
                elif message["action"]=="trend":
                    trend=message["trend"]
                    datefrom=message["from"]
                    dateto=message["to"]
                    tags=message["tags"]
                    response={"action":"trend","trend":trend,"from":datefrom,"to":dateto,"tags":[]}
                    for tag_key in tags:
                        tag=self.ensemble.tag[tag_key]
                        message_tag={"label":tag_key+": "+tag.description}
                        message_tag["data"]=tag.get_data(int(datefrom),int(dateto))
                        response["tags"].append(message_tag)
                    payload = json.dumps(response).encode('utf8')
                    self.sendMessage(payload, isBinary = False)
 
            except Exception as e:
                printexception(e,"Incorrect message: "+message_raw)

    def update(self, tag: PLC.Memory.Tag):
        ''' Envía por el websocket la variable que ha cambiado.


        La respuesta se envía en JSON (action=values, y tags contiene la lista
        de variables y valores).

        Args:
        tag (Tag): Variable cuyo valor ha cambiado.

        '''
        tagvalues=self.transform_read([tag.key],False)
        response={"action":"values",
                  "tags":tagvalues}
        payload = json.dumps(response).encode('utf8')
        self.sendMessage(payload, isBinary = False)


    def transform_read(self, tags, subscribe:bool):
        ''' Conversión del valor de variables segun su tipo.

        tags (Tag[]): Lista de variables.
        subscribe (bool): Si es verdadero, se suscribe a las variables.

        '''        
        tagvalues=[]
        for key in tags:
            tag=self.ensemble.tag[key]
            value=tag.get()
            transformed_value=None
            if type(value)==bool or type(value)==int or type(value)==float:
                transformed_value=str(value)
            if type(value)==str:
                transformed_value=value
            if type(value)==datetime.datetime:
                transformed_value=value.strftime("%Y-%m-%d %H:%M:%S")
            if not transformed_value==None:
                tagvalues.append([key,transformed_value])
                if subscribe:
                    tag.subscribe(self)
        
        return tagvalues


    def write(self,expression:Expression, timestamp:datetime, state:bool, info):
        alarms=[[id(expression),str(timestamp),self.transform(expression),str(state),info["alarmgroup"].key]]
        response={"action":"alarms",
                  "alarms":alarms}
        payload = json.dumps(response).encode('utf8')
        self.sendMessage(payload, isBinary = False)


class http_handler(http.server.SimpleHTTPRequestHandler):
    ''' Servidor de ficheros.

    Attributes:
    relative_path (str): Ruta relativa de los ficheros.
    
    '''
    
    relative_path=""
    
    def do_GET(self):
        ''' Responde a una petición GET

        '''
        self.path=self.relative_path+self.path
        return http.server.SimpleHTTPRequestHandler.do_GET(self)


class UWServer(object):
    ''' Servidor SCADA web.

    Args:
    ensemble (Ensemble): Motor del SCADA.
    http_port: Puerto por el que se sirven los ficheros.
    ws_port: Puerto del websocket.
    relative_path: Ruta de los ficheros que se sirven.

    '''

    def __init__(self,ensemble:Ensemble,http_port:int=80, ws_port:int=8081, relative_path:str="/www"):
        self.ensemble=ensemble
        self.http_port=http_port
        self.ws_port=ws_port
        self.relative_path=relative_path

        if len(self.ensemble.plc)>1 and False:
            raise NameError("Free version is limited to one PLC")

        http_thread=Thread(target=self.http_server, args=())
        http_thread.start()

        self.ws_server()

    def http_server(self):
        ''' Servidor de ficheros.

        '''
        http_server = socketserver.TCPServer(("", self.http_port), http_handler)
        http_handler.relative_path=self.relative_path
        http_server.serve_forever()

    def ws_server(self):
        ''' Servidor del websocket.

        '''
        websocket = WebSocketServerFactory(u"ws://127.0.0.1:"+str(self.ws_port), debug=True)
        
        websocket.protocol = WSHandle
        websocket.protocol.ensemble=self.ensemble

        loop = asyncio.get_event_loop()
        coro = loop.create_server(websocket, '0.0.0.0', str(self.ws_port))
        ws_server = loop.run_until_complete(coro)

        try:
            loop.run_forever()
            while True:
                pass
        except KeyboardInterrupt:
            pass
        finally:
            ws_server.close()
            loop.close()


    



