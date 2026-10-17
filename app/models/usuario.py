from typing import Any, ClassVar

from flask_login import UserMixin
from mongoengine import Document
from mongoengine.fields import BooleanField, DateField, IntField, StringField


class Usuario(UserMixin, Document):
    id_usuario = IntField(primary_key=True)
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
    meta: ClassVar[dict] = {'collection': 'usuarios_final'}

    def get_id(self):
        return str(self.id_usuario)
