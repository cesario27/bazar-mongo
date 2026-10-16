from flask import Blueprint, abort, redirect, render_template, url_for
from sqlalchemy import func

from app.base import SessionLocal
from app.modelos.detalle_movimiento import Detalle_Movimiento
from app.modelos.disco import Disco
from app.modelos.movimiento import Movimiento
from app.modelos.usuario import Usuario

detalle_disco_bp = Blueprint("detalle_disco", __name__)


@detalle_disco_bp.route("/disco/<int:id>-<slug>")
def detalle_disco(id, slug):
    session = SessionLocal()
    try:
        disco = session.get(Disco, id)

        if disco is None or disco.estado != 0:
            abort(404)

        if slug != disco.slug:
            return redirect(
                url_for("detalle_disco.detalle_disco", id=id, slug=disco.slug),
                code=301,
            )

        vendedor = session.get(Usuario, disco.id_usuario)

        # Calificación del vendedor
        total_movimientos = (
            session.query(func.count(Movimiento.id_movimiento))
            .join(
                Detalle_Movimiento,
                Movimiento.id_movimiento == Detalle_Movimiento.id_movimiento,
            )
            .join(Disco, Detalle_Movimiento.id_disco == Disco.id_disco)
            .filter(Disco.id_usuario == disco.id_usuario)
            .scalar()
        ) or 0
        calificacion = round(min(5.0, 3.0 + (total_movimientos * 0.05)), 1)

        return render_template(
            "disco.html",
            detalle_disco=disco,
            vendedor=vendedor,
            calificacion=calificacion,
        )
    finally:
        session.close()
