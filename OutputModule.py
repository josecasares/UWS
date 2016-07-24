'''Salidas (ficheros, bases de datos, mensajes...)

'''

__author__="José A. Casares"
__date__="2016-02-14"
__version__="1.3"

from datetime import datetime
from sqlalchemy import *
from TagModule import *
from email.mime.text import MIMEText
import smtplib

class Output(object):
    ''' Registro de cambios de una expresión.

    '''

    def write(self, expression:Expression, timestamp:datetime, value, info):
        ''' Acción cuando cambia el valor de la expresión.

        Es llamado de forma automática. Debe definirse en la clase derivada.

        Args:
        expression (Expression): Expresión cuyo valor se registra.
        timestamp (datatime): Fecha y hora en que se ha producido el cambio.
        value: Valor de la expresión.
        info ({}): Información adicional, como grupo de alarmas.

        '''
        
        pass

    def transform(self, expression:Expression):
        ''' Efectúa sustituciones en el texto (descripción) de la expresión.

        {n.key} es reemplazado por el nombre de la variable en la posición n.
        {n.description} es reemplazado por el nombre de la variable en la posición n.
        {n.value} es reemplazado por el valor de la variable en la posición n.

        Args:
        expression (Expression): Expresión cuya descripción se debe transformar.

        '''
        output=expression.description
        for i in range(0,len(expression.usedtags)):
            output=output.replace("{"+str(i)+".key}",str(expression.usedtags[i].key))
            output=output.replace("{"+str(i)+".description}",str(expression.usedtags[i].description))
            output=output.replace("{"+str(i)+".value}",str(expression.usedtags[i].value))
        return output


class LogOutput(Output):
    ''' Registro a depurador de Python

    '''

    def write(self,expression:Expression, timestamp:datetime, value, info):
        ''' Acción cuando cambia el valor de la expresión.

        Es llamado de forma automática. Debe definirse en la clase derivada.

        Args:
        expression (Expression): Expresión cuyo valor se registra.
        timestamp (datatime): Fecha y hora en que se ha producido el cambio.
        value: Valor de la expresión.
        info ({}): Información adicional, como grupo de alarmas.

        '''
        if "alarmgroup" in info:
            value=("ON" if value else "OFF")
        print(str(timestamp)+" "+value+" "+self.transform(expression))
        

class SimpleFileOutput(Output):
    ''' Registro a fichero.

    Args:
    filename (str): Nombre del fichero.

    '''

    def __init__(self, filename:str):
        self.filename=filename
        super().__init__()

    def write(self, expression:Expression, timestamp:datetime, value, info):
        ''' Acción cuando cambia el valor de la expresión.

        Es llamado de forma automática. Debe definirse en la clase derivada.

        Args:
        expression (Expression): Expresión cuyo valor se registra.
        timestamp (datatime): Fecha y hora en que se ha producido el cambio.
        value: Valor de la expresión.
        info ({}): Información adicional, como grupo de alarmas.

        '''
        if "alarmgroup" in info:
            value=("ON" if value else "OFF")
        with open(self.filename, "a") as file:
            file.write(str(timestamp)+" "+value+" "+self.transform(expression)+"\n")

class DataBaseOutput(Output):
    ''' Registro a base de datos.

    Args:
    connection (str): Cadena de conexión.
    table (str): Nombre de la tabla.
    timestampcolumn (str): Nombre de la columna con la fecha y hora.
    descriptioncolumn (str): Nombre de la columna con la descripción.
    valuecolumn (str): Nombre de la columna con el valor de la expresión.

    '''

    def __init__(self, connection:str, table:str="alarms", timestampcolumn:str="timestamp",
                 descriptioncolumn:str="description", valuecolumn:str="value"):
        self.connection=connection
        self.table=table
        self.timestampcolumn=timestampcolumn
        self.descriptioncolumn=descriptioncolumn
        self.valuecolumn=valuecolumn
        self.engine=create_engine(connection)
        self.engine.connect()

    def write(self,expression:Expression, timestamp:datetime, value, info):
        ''' Acción cuando cambia el valor de la expresión.

        Es llamado de forma automática. Debe definirse en la clase derivada.

        Args:
        expression (Expression): Expresión cuyo valor se registra.
        timestamp (datatime): Fecha y hora en que se ha producido el cambio.
        value: Valor de la expresión.
        info ({}): Información adicional, como grupo de alarmas.

        '''
        if "alarmgroup" in info:
            value=("1" if value else "0")
        self.engine.execute("INSERT INTO "+self.table+"("+self.timestampcolumn+","+self.descriptioncolumn+","
            +self.valuecolumn+") VALUES ('"+str(timestamp)+"','"+self.transform(expression)+"','"+value+"')")

class MailOutput(Output):
    ''' Envío a correo.

    Args:
    sender (str): Correo para identificación.
    password (str): Contraseña.
    mailto ([str]): Correos destinatarios.
    server (str): SMTP server.
    port (int): Puerto.
    SSL (bool): Conexión segura.

    '''

    def __init__(self, sender:str, password: str, mailto: list, server:str, port:int=465, SSL:bool=True):
        self.server=server
        self.port=port
        self.sender=sender
        self.password=password
        self.mailto=mailto
        self.SSL=SSL

    def write(self,expression:Expression, timestamp:datetime, value, info):
        ''' Acción cuando cambia el valor de la expresión.

        Es llamado de forma automática. Debe definirse en la clase derivada.

        Args:
        expression (Expression): Expresión cuyo valor se envía.
        timestamp (datatime): Fecha y hora en que se ha producido el cambio.
        value: Valor de la expresión.
        info ({}): Información adicional, como grupo de alarmas.

        '''
        if "alarmgroup" in info:
            value=("1" if value else "0")

        text=self.transform(expression)
        msg = MIMEText("Date: "+str(timestamp)+"\r\n"+
            "Concept: "+text+"\r\n"+
            "Value: "+value)
        msg['Subject'] = text
        msg['From'] = self.sender
        msg['To'] = ", ".join(self.mailto)
        try:
            if self.SSL:
                SMTPserver=smtplib.SMTP_SSL(self.server, self.port)
                SMTPserver.login(self.sender, self.password)
            else:
                SMTPserver=smtplib.SMTP(self.server, self.port)
            SMTPserver.sendmail(self.sender, self.mailto, msg.as_string())
            SMTPserver.quit()
        except Exception as e:
            printexception(e,"Error sending mail")
