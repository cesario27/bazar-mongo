from typing import Any, ClassVar

from mongoengine import (
    DateField,
    Document,
    EmbeddedDocument,
    EmbeddedDocumentField,
    FloatField,
    IntField,
    ListField,
    StringField,
)
from mongoengine.base.metaclasses import ObjectIdField


class DetalleCarrito(EmbeddedDocument):
    _id = IntField()
    precio = FloatField()
    id_disco = IntField()
    id_carrito = IntField()
    id_detalle_carrito = IntField()
    titulo = StringField()


class Carrito(Document):
    _id = ObjectIdField(primary_key=True)
    detalles = ListField(EmbeddedDocumentField(DetalleCarrito))
    total = FloatField()
    fecha_creacion = DateField()
    fecha_actualizacion = DateField()
    id_usuario = IntField()

    objects: ClassVar[Any]
    meta: ClassVar = {"collection": "carritos_final"}
