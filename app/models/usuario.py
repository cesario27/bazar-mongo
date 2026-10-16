from typing import Any, ClassVar

from mongoengine import Document
from mongoengine.fields import BooleanField, DateField, IntField, StringField


class Usuario(Document):
    id_usuario = IntField()
    nombre = StringField()
    correo = StringField()
    contraseña = StringField()
    tipo_usuario = BooleanField()
    direccion = StringField()
    fecha_registro = DateField()
    icono_usuario = StringField()
    tarjeta_numero = IntField()
    tarjeta_vencimiento = DateField()
    salt = StringField()

    objects: ClassVar[Any]
