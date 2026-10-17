from flask import Blueprint, abort, redirect, render_template, url_for

from app.models.disco import Disco
from app.models.movimiento import DetalleMovimiento, Movimiento
from app.models.usuario import Usuario

detalle_disco_bp = Blueprint("detalle_disco", __name__)


@detalle_disco_bp.route("/disco/<int:id>-<slug>")
def detalle_disco(id, slug):
    # 1. Buscar el disco por su ID (que es la primary key)
    disco = Disco.objects(id_disco=id).first()

    # Si no existe o no está a la venta (estado 0), retornar 404
    if disco is None or disco.estado != 0:
        abort(404)

    # 2. Redirección 301 si el slug de la URL no coincide con el real (SEO)
    if slug != disco.slug:
        return redirect(
            url_for("detalle_disco.detalle_disco", id=id, slug=disco.slug),
            code=301,
        )

    # 3. Buscar el vendedor
    vendedor = Usuario.objects(id_usuario=disco.id_usuario).first()

    # 4. Calcular calificación del vendedor
    # Obtenemos todos los IDs de los discos que pertenecen a este vendedor
    discos_ids = [
        d.id_disco
        for d in Disco.objects(id_usuario=disco.id_usuario).only('id_disco')
    ]

    # Contamos los movimientos únicos asociados a estos discos.
    # Usamos .distinct('id_movimiento') para replicar el COUNT(Movimiento.id_movimiento) del SQL
    if discos_ids:
        movimientos_ids = Movimiento.objects(detalles__id_disco__in=discos_ids).distinct('id_movimiento')
        total_movimientos = len(movimientos_ids)
    else:
        total_movimientos = 0

    # Fórmula original de calificación
    calificacion = round(min(5.0, 3.0 + (total_movimientos * 0.05)), 1)

    # 5. Renderizar template
    return render_template(
        "disco.html",
        detalle_disco=disco,
        vendedor=vendedor,
        calificacion=calificacion,
    )
