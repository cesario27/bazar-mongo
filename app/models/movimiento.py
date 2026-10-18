from typing import ClassVar

from mongoengine import (
    DateTimeField,
    Document,
    EmbeddedDocument,
    EmbeddedDocumentField,
    FloatField,
    IntField,
    ListField,
    ObjectIdField,
)


class DetalleMovimiento(EmbeddedDocument):
    _id = ObjectIdField()
    id_movimiento = IntField()
    id_disco = IntField()
    precio_unitario = FloatField()
    id_detalle_movimiento = IntField()


class Movimiento(Document):
    id = IntField(primary_key=True)
    comision = FloatField()
    detalles = ListField(EmbeddedDocumentField(DetalleMovimiento))
    fecha = DateTimeField()
    id_usuario = IntField()
    tipo = IntField()
    total = FloatField()

    meta: ClassVar = {"collection": "movimientos_final"}
