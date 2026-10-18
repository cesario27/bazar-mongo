import math
from datetime import datetime, timezone

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.controladores.email import enviar_correo_confirmacion
from app.controladores.utils import slugify
from app.models.disco import Disco
from app.models.movimiento import DetalleMovimiento, Movimiento
from app.models.subasta import Puja, Subastas
from app.models.usuario import Usuario

detalle_subasta_bp = Blueprint("detalle_subasta", __name__)


@detalle_subasta_bp.route("/subasta/<int:id_subasta>-<slug>")
def detalle_subasta(id_subasta, slug):
    subasta = Subastas.objects(id=id_subasta).first()
    if not subasta:
        abort(404)

    disco = Disco.objects(id_disco=subasta.id_disco).first()
    if not disco:
        abort(404)

    slug_correcto = slugify(disco.titulo)
    if slug != slug_correcto:
        return redirect(
            url_for(
                "detalle_subasta.detalle_subasta",
                id_subasta=subasta.id,
                slug=slug_correcto,
            ),
            code=301,
        )

    vendedor = Usuario.objects(id_usuario=disco.id_usuario).first()

    discos_ids = [
        d.id_disco for d in Disco.objects(id_usuario=disco.id_usuario).only("id_disco")
    ]

    if discos_ids:
        movimientos_ids = Movimiento.objects(
            detalles__id_disco__in=discos_ids
        ).distinct("id") # Corregido a "id"
        total_movimientos = len(movimientos_ids)
    else:
        total_movimientos = 0

    calificacion = round(min(5.0, 3.0 + (total_movimientos * 0.05)), 1)

    # ─── CORRECCIÓN DE FECHAS Y TUPLAS ───
    # 1. Convertir fechas de string a datetime si es necesario
    for p in subasta.pujas:
        if isinstance(p.fecha, str):
            try:
                p.fecha = datetime.strptime(p.fecha, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                p.fecha = datetime.strptime(p.fecha, "%Y-%m-%d %H:%M:%S")

    # 2. Ordenar pujas
    pujas_ordenadas = sorted(
        subasta.pujas, key=lambda p: (p.porcentaje, p.fecha), reverse=True
    )

    puja_maxima = pujas_ordenadas[0] if pujas_ordenadas else None
    precio_actual = float(subasta.precio)

    if puja_maxima:
        precio_actual = float(subasta.precio) * (1 + puja_maxima.porcentaje / 100)

    min_pct = 5
    if puja_maxima:
        min_pct = max(5, puja_maxima.porcentaje + 5)

    ahora = datetime.now()
    if subasta.fecha_fin and subasta.estado == 1 and ahora > subasta.fecha_fin:
        subasta.estado = 0

        if precio_actual >= float(subasta.precio_minimo):
            disco.estado = 2

            if precio_actual > 20000:
                comision = round(precio_actual * 0.16, 2)
            else:
                comision = round(precio_actual * 0.11, 2)

            # ─── CORRECCIÓN MOVIMIENTO Y DETALLE ───
            max_id_mov = Movimiento.objects.order_by("-id").first()
            nuevo_id_mov = (max_id_mov.id if max_id_mov else 0) + 1

            movimiento = Movimiento(
                id=nuevo_id_mov,
                tipo=2,
                fecha=ahora,
                total=precio_actual,
                id_usuario=puja_maxima.id_usuario if puja_maxima else disco.id_usuario,
                comision=comision,
                detalles=[]
            )

            if puja_maxima:
                # Se agrega a la lista de documentos embebidos
                movimiento.detalles.append(
                    DetalleMovimiento(
                        id_movimiento=nuevo_id_mov,
                        id_disco=disco.id_disco,
                        precio_unitario=float(subasta.precio),
                    )
                )
            movimiento.save()
        else:
            disco.estado = 0

        subasta.save()
        disco.save()

        if puja_maxima and precio_actual >= float(subasta.precio_minimo):
            try:
                ganador = Usuario.objects(id_usuario=puja_maxima.id_usuario).first()
                if ganador and ganador.correo:
                    enviar_correo_confirmacion(
                        destinatario=ganador.correo,
                        nombre=ganador.nombre,
                        disco=disco.titulo,
                        precio=precio_actual,
                        tipo="subasta",
                    )
            except Exception as e:
                current_app.logger.error(f"Error enviando correo subasta: {e}")

    es_ganador = False
    if (
        subasta.estado != 1
        and puja_maxima
        and precio_actual >= float(subasta.precio_minimo)
    ):
        es_ganador = puja_maxima.id_usuario == getattr(current_user, "id_usuario", None)

    subasta_no_vendida = subasta.estado != 1 and precio_actual < float(
        subasta.precio_minimo
    )

    precio_base = float(subasta.precio)
    ultima_puja_pct = puja_maxima.porcentaje if puja_maxima else 0

    # ─── CONSTRUIR TUPLAS (PUJA, USUARIO) PARA EL TEMPLATE ───
    usuarios_ids = [p.id_usuario for p in pujas_ordenadas]
    usuarios_map = {
        u.id_usuario: u for u in Usuario.objects(id_usuario__in=usuarios_ids)
    }

    pujas_con_usuario = [
        (p, usuarios_map.get(p.id_usuario)) for p in pujas_ordenadas
    ]

    return render_template(
        "subasta.html",
        subasta=subasta,
        disco=disco,
        vendedor=vendedor,
        pujas=pujas_con_usuario,
        puja_maxima=puja_maxima,
        precio_actual=round(precio_actual, 2),
        es_ganador=es_ganador,
        slug=slug_correcto,
        calificacion=calificacion,
        min_pct=min_pct,
        subasta_no_vendida=subasta_no_vendida,
        precio_base=precio_base,
        ultima_puja_pct=ultima_puja_pct,
    )


@detalle_subasta_bp.route("/subasta/<int:id_subasta>-<slug>/pujar", methods=["POST"])
@login_required
def pujar(id_subasta, slug):
    subasta = Subastas.objects(id=id_subasta).first()
    if not subasta or subasta.estado != 1:
        flash("La subasta no está activa", "error")
        return redirect(
            url_for("detalle_subasta.detalle_subasta", id_subasta=id_subasta, slug=slug)
        )

    ahora = datetime.now()
    if subasta.fecha_fin and ahora > subasta.fecha_fin:
        subasta.estado = 0
        subasta.save()
        flash("La subasta ya ha finalizado", "error")
        return redirect(
            url_for("detalle_subasta.detalle_subasta", id_subasta=id_subasta, slug=slug)
        )

    disco = Disco.objects(id_disco=subasta.id_disco).first()
    if disco and disco.id_usuario == current_user.id_usuario:
        flash("No puedes pujar en tu propia subasta", "error")
        return redirect(
            url_for(
                "detalle_subasta.detalle_subasta",
                id_subasta=subasta.id,
                slug=slugify(disco.titulo),
            )
        )

    porcentaje = request.form.get("porcentaje", type=int)
    if not porcentaje or porcentaje <= 0:
        flash("Debes ingresar un porcentaje válido", "error")
        return redirect(
            url_for("detalle_subasta.detalle_subasta", id_subasta=id_subasta, slug=slug)
        )

    for p in subasta.pujas:
        if isinstance(p.fecha, str):
            try:
                p.fecha = datetime.strptime(p.fecha, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                p.fecha = datetime.strptime(p.fecha, "%Y-%m-%d %H:%M:%S")

    pujas_ordenadas = sorted(subasta.pujas, key=lambda p: p.porcentaje, reverse=True)
    puja_maxima = pujas_ordenadas[0] if pujas_ordenadas else None

    min_pct = 5
    if puja_maxima:
        min_pct = max(5, puja_maxima.porcentaje + 5)

    if porcentaje < min_pct:
        flash(
            f"El incremento mínimo es del 5%. Tu puja debe ser al menos +{min_pct}%",
            "error",
        )
        return redirect(
            url_for("detalle_subasta.detalle_subasta", id_subasta=id_subasta, slug=slug)
        )

    max_id = max([p.id_puja for p in subasta.pujas], default=0)
    nuevo_id = max_id + 1

    nueva_puja = Puja(
        id_puja=nuevo_id,
        porcentaje=porcentaje,
        fecha=datetime.now(),
        id_subasta=subasta.id,
        id_usuario=current_user.id_usuario,
    )

    subasta.pujas.append(nueva_puja)
    subasta.save()

    flash(f"¡Puja de {porcentaje}% registrada exitosamente!", "success")

    redirect_slug = slugify(disco.titulo) if disco else slug

    return redirect(
        url_for(
            "detalle_subasta.detalle_subasta", id_subasta=id_subasta, slug=redirect_slug
        )
    )
