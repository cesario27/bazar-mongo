from typing import Any, ClassVar

from mongoengine import (
    DateField,
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
    fecha = DateField()
    id_subasta = IntField()
    id_usuario = IntField()


class Subastas(Document):
    _id = IntField(primary_key=True)
    estado = IntField()
    fecha_inicio = DateField()
    fecha_fin = DateField()
    id_disco = IntField()
    precio = FloatField()
    precio_minimo = FloatField()
    pujas = ListField(EmbeddedDocumentField(Puja))

    objects: ClassVar[Any]
    meta: ClassVar[dict] = {"collection": "subastas_final"}
