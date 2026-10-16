from typing import Any, ClassVar, cast

from mongoengine import (
    BooleanField,
    Document,
    FloatField,
    IntField,
    StringField,
)

from app.controladores.utils import slugify


class Disco(Document):
    id_disco = IntField(primary_key=True)
    estado = IntField()
    titulo = StringField()
    formato = BooleanField()
    descripcion = StringField()
    precio = FloatField()
    artista = StringField()
    genero = IntField()
    imagen = StringField()
    id_usuario = IntField()

    MAPA_GENEROS: ClassVar[dict[int, str]] = {
        0: "Rock",
        1: "Pop",
        2: "Pop Latino",
        3: "Pop Coreano",
        4: "Metal",
        5: "Electronica",
    }
    objects: ClassVar[Any]
    meta: ClassVar = {'collection': "discos_final"}


    @property
    def slug(self) -> str:
        titulo_str = cast(str, self.titulo)
        return slugify(titulo_str)

    @property
    def formato_nombre(self):
        formato_bool = cast(bool, self.formato)
        formatos = {False: "CD", True: "Vinilo"}
        return formatos.get(formato_bool, "Desconocido")

    @property
    def nombre_genero(self) -> str:
        genero_int = cast(int, self.genero)
        return self.MAPA_GENEROS.get(genero_int, "Otro")
