from datetime import datetime

from flask import (
    Blueprint,
    current_app,  # ← NUEVO
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from flask_mail import Message
from sqlalchemy import func

from app.base import SessionLocal
from app.controladores.email import enviar_correo_confirmacion
from app.modelos.carrito import Carrito
from app.modelos.detalle_carrito import Detalle_Carrito
from app.modelos.detalle_movimiento import Detalle_Movimiento
from app.modelos.disco import Disco
from app.modelos.movimiento import Movimiento

carrito_bp = Blueprint("carrito", __name__)


def _obtener_o_crear_carrito(session, id_usuario):
    carrito = (
        session.query(Carrito)
        .filter_by(id_usuario=id_usuario)
        .order_by(Carrito.fecha_creacion.desc())
        .first()
    )
    if not carrito:
        carrito = Carrito(
            total=0,
            fecha_creacion=datetime.now(),
            id_usuario=id_usuario,
        )
        session.add(carrito)
        session.flush()
        session.refresh(carrito)
    return carrito


# ─── Helper: enviar correo de confirmación ─── #


@carrito_bp.route("/carrito/agregar/<int:id_disco>", methods=["POST"])
@login_required
def agregar_al_carrito(id_disco):
    session = SessionLocal()
    try:
        disco = session.query(Disco).filter_by(id_disco=id_disco, estado=0).first()
        if not disco:
            if request.headers.get("HX-Request"):
                return _toast_resp("Disco no disponible", "error", 0)
            flash("Disco no disponible", "error")
            return redirect(url_for("discos.discos"))

        if disco.id_usuario == current_user.id_usuario:
            if request.headers.get("HX-Request"):
                return _toast_resp("No puedes comprar tu propio disco", "error", 0)
            flash("No puedes comprar tu propio disco", "error")
            return redirect(
                url_for("detalle_disco.detalle_disco", id=id_disco, slug=disco.slug)
            )

        carrito = _obtener_o_crear_carrito(session, current_user.id_usuario)

        existente = (
            session.query(Detalle_Carrito)
            .filter_by(id_carrito=carrito.id_carrito, id_disco=id_disco)
            .first()
        )
        if existente:
            count = (
                session.query(func.count(Detalle_Carrito.id_detalle_carrito))
                .filter_by(id_carrito=carrito.id_carrito)
                .scalar()
            ) or 0
            if request.headers.get("HX-Request"):
                return _toast_resp("Este disco ya está en tu carrito", "warning", count)
            flash("Este disco ya está en tu carrito", "warning")
            return redirect(url_for("carrito.ver_carrito"))

        detalle = Detalle_Carrito(
            id_carrito=carrito.id_carrito,
            id_disco=id_disco,
            precio=disco.precio,
            titulo=disco.titulo,
        )
        session.add(detalle)

        carrito.total = float(carrito.total or 0) + float(disco.precio)
        carrito.fecha_actualizacion = datetime.now()
        session.commit()

        if request.headers.get("HX-Request"):
            count = (
                session.query(func.count(Detalle_Carrito.id_detalle_carrito))
                .filter_by(id_carrito=carrito.id_carrito)
                .scalar()
            ) or 0
            return _toast_resp(
                f"'{disco.titulo}' agregado al carrito", "success", count
            )

        flash(f"'{disco.titulo}' agregado al carrito", "success")
        return redirect(url_for("carrito.ver_carrito"))
    except Exception as e:
        session.rollback()
        if request.headers.get("HX-Request"):
            return _toast_resp(f"Error: {str(e)}", "error", 0)
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("discos.discos"))
    finally:
        session.close()


def _toast_resp(message, category="info", count=0):
    icons = {
        "success": '<svg xmlns="http://www.w3.org/2000/svg" class="stroke-success shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        "error": '<svg xmlns="http://www.w3.org/2000/svg" class="stroke-error shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        "warning": '<svg xmlns="http://www.w3.org/2000/svg" class="stroke-warning shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>',
    }
    icon = icons.get(category, "")
    html = f"""<<div class="alert shadow-xl border border-white/20 bg-base-100/40 backdrop-blur-md text-base-content rounded-box px-4 py-3" role="alert">
        {icon}
        <span class="text-sm font-medium">{message}</span>
    </div>"""
    resp = make_response(html)
    resp.headers["X-Cart-Count"] = str(count)
    return resp


@carrito_bp.route("/carrito")
@login_required
def ver_carrito():
    session = SessionLocal()
    try:
        carrito = (
            session.query(Carrito)
            .filter_by(id_usuario=current_user.id_usuario)
            .order_by(Carrito.fecha_creacion.desc())
            .first()
        )

        items = []
        total = 0
        if carrito:
            items = (
                session.query(Detalle_Carrito, Disco)
                .join(Disco, Detalle_Carrito.id_disco == Disco.id_disco)
                .filter(Detalle_Carrito.id_carrito == carrito.id_carrito)
                .all()
            )
            total = float(carrito.total or 0)

        return render_template("carrito.html", items=items, total=total)
    finally:
        session.close()


@carrito_bp.route("/carrito/eliminar/<int:id_detalle>", methods=["POST"])
@login_required
def eliminar_del_carrito(id_detalle):
    session = SessionLocal()
    try:
        detalle = (
            session.query(Detalle_Carrito)
            .filter_by(id_detalle_carrito=id_detalle)
            .first()
        )
        if not detalle:
            flash("Item no encontrado", "error")
            return redirect(url_for("carrito.ver_carrito"))

        carrito = (
            session.query(Carrito)
            .filter_by(
                id_carrito=detalle.id_carrito, id_usuario=current_user.id_usuario
            )
            .first()
        )
        if not carrito:
            flash("No autorizado", "error")
            return redirect(url_for("carrito.ver_carrito"))

        carrito.total = max(0, float(carrito.total or 0) - float(detalle.precio or 0))
        carrito.fecha_actualizacion = datetime.now()

        session.delete(detalle)
        session.commit()

        flash("Item eliminado del carrito", "success")
        return redirect(url_for("carrito.ver_carrito"))
    except Exception as e:
        session.rollback()
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("carrito.ver_carrito"))
    finally:
        session.close()


@carrito_bp.route("/carrito/comprar", methods=["POST"])
@login_required
def comprar_carrito():
    if not current_user.tarjeta_numero or not current_user.tarjeta_vencimiento:
        flash("Agrega un método de pago en tu perfil antes de comprar", "warning")
        return redirect(url_for("carrito.ver_carrito"))

    session = SessionLocal()
    try:
        carrito = (
            session.query(Carrito)
            .filter_by(id_usuario=current_user.id_usuario)
            .order_by(Carrito.fecha_creacion.desc())
            .first()
        )

        if not carrito:
            flash("Tu carrito está vacío", "error")
            return redirect(url_for("carrito.ver_carrito"))

        items = (
            session.query(Detalle_Carrito, Disco)
            .join(Disco, Detalle_Carrito.id_disco == Disco.id_disco)
            .filter(Detalle_Carrito.id_carrito == carrito.id_carrito)
            .all()
        )

        if not items:
            flash("Tu carrito está vacío", "error")
            return redirect(url_for("carrito.ver_carrito"))

        for det, disco in items:
            if disco.estado != 0:
                flash(f"'{disco.titulo}' ya no está disponible", "error")
                return redirect(url_for("carrito.ver_carrito"))

        max_id = session.query(func.max(Movimiento.id_movimiento)).scalar()
        nuevo_id_mov = (max_id or 0) + 1

        total = float(carrito.total or 0)
        comision = round(total * 0.06, 2)

        movimiento = Movimiento(
            id_movimiento=nuevo_id_mov,
            tipo=1,
            fecha=datetime.now(),
            total=total,
            id_usuario=current_user.id_usuario,
            comision=comision,
        )
        session.add(movimiento)
        session.flush()

        for det, disco in items:
            det_mov = Detalle_Movimiento(
                id_movimiento=nuevo_id_mov,
                id_disco=disco.id_disco,
                precio_unitario=det.precio,
            )
            session.add(det_mov)
            disco.estado = 2

        session.query(Detalle_Carrito).filter_by(id_carrito=carrito.id_carrito).delete()
        carrito.total = 0
        carrito.fecha_actualizacion = datetime.now()

        session.commit()

        # ─── Enviar correo de confirmación ─── #
        try:
            titulos = ", ".join([d.titulo for _, d in items])
            enviar_correo_confirmacion(
                destinatario=current_user.correo,
                nombre=current_user.nombre,
                disco=titulos,
                precio=total,
                tipo="compra",
            )
        except Exception as e:
            current_app.logger.error(f"Error enviando correo: {e}")

        flash("¡Compra realizada con éxito!", "success")
        return redirect(url_for("carrito.ver_carrito"))
    except Exception as e:
        session.rollback()
        flash(f"Error al procesar la compra: {str(e)}", "error")
        return redirect(url_for("carrito.ver_carrito"))
    finally:
        session.close()


@carrito_bp.route("/comprar/ahora/<int:id_disco>", methods=["POST"])
@login_required
def comprar_ahora(id_disco):
    if not current_user.tarjeta_numero or not current_user.tarjeta_vencimiento:
        flash("Agrega un método de pago en tu perfil antes de comprar", "warning")
        return redirect(url_for("discos.discos"))

    session = SessionLocal()
    try:
        disco = session.query(Disco).filter_by(id_disco=id_disco, estado=0).first()
        if not disco:
            flash("Disco no disponible", "error")
            return redirect(url_for("discos.discos"))

        if disco.id_usuario == current_user.id_usuario:
            flash("No puedes comprar tu propio disco", "error")
            return redirect(
                url_for("detalle_disco.detalle_disco", id=id_disco, slug=disco.slug)
            )

        max_id = session.query(func.max(Movimiento.id_movimiento)).scalar()
        nuevo_id_mov = (max_id or 0) + 1

        total = float(disco.precio)
        comision = round(total * 0.06, 2)

        movimiento = Movimiento(
            id_movimiento=nuevo_id_mov,
            tipo=1,
            fecha=datetime.now(),
            total=total,
            id_usuario=current_user.id_usuario,
            comision=comision,
        )
        session.add(movimiento)
        session.flush()

        det_mov = Detalle_Movimiento(
            id_movimiento=nuevo_id_mov,
            id_disco=disco.id_disco,
            precio_unitario=disco.precio,
        )
        session.add(det_mov)

        disco.estado = 2

        session.commit()

        # ─── Enviar correo de confirmación ─── #
        try:
            enviar_correo_confirmacion(
                destinatario=current_user.correo,
                nombre=current_user.nombre,
                disco=disco.titulo,
                precio=total,
                tipo="compra",
            )
        except Exception as e:
            current_app.logger.error(f"Error enviando correo: {e}")

        flash(f"¡Compraste '{disco.titulo}' por ${total:.2f}!", "success")
        return redirect(url_for("discos.discos"))
    except Exception as e:
        session.rollback()
        flash(f"Error al procesar la compra: {str(e)}", "error")
        return redirect(url_for("discos.discos"))
    finally:
        session.close()
