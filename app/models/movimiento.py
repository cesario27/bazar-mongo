from typing import ClassVar

from mongoengine import (
    BooleanField,
    DateTimeField,
    Document,
    EmbeddedDocument,
    EmbeddedDocumentField,
    FloatField,
    IntField,
    ListField,
)


class DetalleMovimiento(EmbeddedDocument):
    id_movimiento = IntField()
    id_disco = IntField()
    precio_unitario = FloatField()
    # id_detalle_movimiento = IntField()


class Movimiento(Document):
    id = IntField(primary_key=True)
    comision = FloatField()
    detalles = ListField(EmbeddedDocumentField(DetalleMovimiento))
    fecha = DateTimeField()
    id_usuario = IntField()
    tipo = BooleanField()
    total = FloatField()

    meta: ClassVar = {'collection': 'movimientos_final'}
