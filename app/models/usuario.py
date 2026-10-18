from tokenize import String
from typing import Any, ClassVar

from flask_login import UserMixin
from mongoengine import DateTimeField, Document, IntField, StringField


class Usuario(UserMixin, Document):
    id_usuario = IntField(primary_key=True)
    nombre = StringField()
    correo = StringField()
    contraseña = StringField()
    tipo_usuario = IntField()
    direccion = StringField()
    fecha_registro = DateTimeField()
    icono_usuario = StringField()
    tarjeta_numero = StringField()
    tarjeta_vencimiento = DateTimeField()
    salt = StringField()

    objects: ClassVar[Any]
    meta: ClassVar[dict] = {"collection": "usuarios_final"}

    def get_id(self):
        return str(self.id_usuario)
