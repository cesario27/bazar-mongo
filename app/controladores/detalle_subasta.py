import math
from datetime import datetime, timezone

from flask import (
    Blueprint,
    abort,
    current_app,  # ← NUEVO
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from flask_mail import Message  # ← NUEVO
from sqlalchemy import func

from app.base import SessionLocal
from app.controladores.email import enviar_correo_confirmacion
from app.controladores.utils import slugify
from app.modelos.detalle_movimiento import Detalle_Movimiento
from app.modelos.disco import Disco
from app.modelos.movimiento import Movimiento
from app.modelos.puja import Puja
from app.modelos.subasta import Subasta
from app.modelos.usuario import Usuario

detalle_subasta_bp = Blueprint("detalle_subasta", __name__)


@detalle_subasta_bp.route("/subasta/<int:id_subasta>-<slug>")
def detalle_subasta(id_subasta, slug):
    session = SessionLocal()
    try:
        subasta = session.query(Subasta).filter_by(id_subasta=id_subasta).first()
        if not subasta:
            abort(404)

        disco = session.query(Disco).filter_by(id_disco=subasta.id_disco).first()
        if not disco:
            abort(404)

        slug_correcto = slugify(disco.titulo)
        if slug != slug_correcto:
            return redirect(
                url_for(
                    "detalle_subasta.detalle_subasta",
                    id_subasta=id_subasta,
                    slug=slug_correcto,
                ),
                code=301,
            )

        vendedor = session.query(Usuario).filter_by(id_usuario=disco.id_usuario).first()

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

        pujas = (
            session.query(Puja, Usuario)
            .join(Usuario, Puja.id_usuario == Usuario.id_usuario)
            .filter(Puja.id_subasta == id_subasta)
            .order_by(Puja.porcentaje.desc(), Puja.fecha.desc())
            .all()
        )

        puja_maxima = pujas[0][0] if pujas else None
        precio_actual = float(subasta.precio)
        if puja_maxima:
            precio_actual = float(subasta.precio) * (1 + puja_maxima.porcentaje / 100)

        # Incremento mínimo: 5% sobre la puja anterior o sobre el precio base
        min_pct = 5
        if puja_maxima:
            min_pct = max(5, puja_maxima.porcentaje + 5)

        # Verificar cierre
        ahora = datetime.now()
        if subasta.fecha_fin and subasta.estado == 1 and ahora > subasta.fecha_fin:
            subasta.estado = 0

            # ¿Se alcanzó el precio mínimo oculto?
            if precio_actual >= float(subasta.precio_minimo):
                # Venta exitosa
                disco.estado = 2

                # Calcular comisión: 16% si supera $20,000, si no 11%
                if precio_actual > 20000:
                    comision = round(precio_actual * 0.16, 2)
                else:
                    comision = round(precio_actual * 0.11, 2)

                # Crear movimiento
                max_id_mov = session.query(func.max(Movimiento.id_movimiento)).scalar()
                nuevo_id_mov = (max_id_mov or 0) + 1
                movimiento = Movimiento(
                    id_movimiento=nuevo_id_mov,
                    tipo=2,  # <-- corregido: 2 = subasta
                    fecha=ahora,
                    total=precio_actual,
                    id_usuario=puja_maxima.id_usuario
                    if puja_maxima
                    else disco.id_usuario,
                    comision=comision,
                )
                session.add(movimiento)
                session.flush()

                if puja_maxima:
                    det_mov = Detalle_Movimiento(
                        id_movimiento=nuevo_id_mov,
                        id_disco=disco.id_disco,
                        precio_unitario=float(subasta.precio),
                    )
                    session.add(det_mov)
            else:
                # No se alcanzó, volver a venta normal
                disco.estado = 0

            session.commit()

            # ─── Enviar correo al ganador (solo si hubo puja ganadora) ─── #
            if puja_maxima and precio_actual >= float(subasta.precio_minimo):
                try:
                    ganador = session.get(Usuario, puja_maxima.id_usuario)
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

        # Ganador
        es_ganador = False
        if (
            subasta.estado != 1
            and puja_maxima
            and precio_actual >= float(subasta.precio_minimo)
        ):
            es_ganador = puja_maxima.id_usuario == getattr(
                current_user, "id_usuario", None
            )

        # ¿No se vendió? (subasta cerrada sin alcanzar mínimo)
        subasta_no_vendida = subasta.estado != 1 and precio_actual < float(
            subasta.precio_minimo
        )

        precio_base = float(subasta.precio)
        ultima_puja_pct = puja_maxima.porcentaje if puja_maxima else 0

        return render_template(
            "subasta.html",
            subasta=subasta,
            disco=disco,
            vendedor=vendedor,
            pujas=pujas,
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
    finally:
        session.close()


@detalle_subasta_bp.route("/subasta/<int:id_subasta>-<slug>/pujar", methods=["POST"])
@login_required
def pujar(id_subasta, slug):
    session = SessionLocal()
    try:
        subasta = session.query(Subasta).filter_by(id_subasta=id_subasta).first()
        if not subasta or subasta.estado != 1:
            flash("La subasta no está activa", "error")
            return redirect(
                url_for(
                    "detalle_subasta.detalle_subasta", id_subasta=id_subasta, slug=slug
                )
            )

        ahora = datetime.now()
        if subasta.fecha_fin and ahora > subasta.fecha_fin:
            subasta.estado = 0
            session.commit()
            flash("La subasta ya ha finalizado", "error")
            return redirect(
                url_for(
                    "detalle_subasta.detalle_subasta", id_subasta=id_subasta, slug=slug
                )
            )

        disco = session.query(Disco).filter_by(id_disco=subasta.id_disco).first()
        if disco and disco.id_usuario == current_user.id_usuario:
            flash("No puedes pujar en tu propia subasta", "error")
            return redirect(
                url_for(
                    "detalle_subasta.detalle_subasta",
                    id_subasta=id_subasta,
                    slug=slugify(disco.titulo),
                )
            )

        porcentaje = request.form.get("porcentaje", type=int)
        if not porcentaje or porcentaje <= 0:
            flash("Debes ingresar un porcentaje válido", "error")
            return redirect(
                url_for(
                    "detalle_subasta.detalle_subasta", id_subasta=id_subasta, slug=slug
                )
            )

        # Incremento mínimo: 5% sobre la puja anterior o sobre el precio base
        puja_maxima = (
            session.query(Puja)
            .filter_by(id_subasta=id_subasta)
            .order_by(Puja.porcentaje.desc())
            .first()
        )
        min_pct = 5
        if puja_maxima:
            min_pct = max(5, puja_maxima.porcentaje + 5)

        if porcentaje < min_pct:
            flash(
                f"El incremento mínimo es del 5%. Tu puja debe ser al menos +{min_pct}%",
                "error",
            )
            return redirect(
                url_for(
                    "detalle_subasta.detalle_subasta", id_subasta=id_subasta, slug=slug
                )
            )

        max_id = session.query(func.max(Puja.id_puja)).scalar()
        nuevo_id = (max_id or 0) + 1

        nueva_puja = Puja(
            id_puja=nuevo_id,
            porcentaje=porcentaje,
            fecha=datetime.now(),
            id_subasta=id_subasta,
            id_usuario=current_user.id_usuario,
        )

        session.add(nueva_puja)
        session.commit()
        flash(f"¡Puja de {porcentaje}% registrada exitosamente!", "success")

        redirect_slug = slugify(disco.titulo) if disco else slug

    except Exception as e:
        session.rollback()
        flash(f"Error al registrar puja: {str(e)}", "error")
        redirect_slug = slug
    finally:
        session.close()

    return redirect(
        url_for(
            "detalle_subasta.detalle_subasta", id_subasta=id_subasta, slug=redirect_slug
        )
    )
