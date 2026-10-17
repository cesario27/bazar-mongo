from typing import Any, ClassVar

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


class Puja(EmbeddedDocument):
    _id = ObjectIdField()
    id_puja = IntField()
    porcentaje = FloatField()
    fecha = DateTimeField()
    id_subasta = IntField()
    id_usuario = IntField()


class Subastas(Document):
    id = IntField(primary_key=True)
    estado = IntField()
    fecha_inicio = DateTimeField()
    fecha_fin = DateTimeField()
    id_disco = IntField()
    precio = FloatField()
    precio_minimo = FloatField()
    pujas = ListField(EmbeddedDocumentField(Puja))

    objects: ClassVar[Any]
    meta: ClassVar[dict] = {"collection": "subastas_final"}
