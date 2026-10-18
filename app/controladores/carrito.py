from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.controladores.email import enviar_correo_confirmacion
from app.models.carrito import Carrito, DetalleCarrito
from app.models.disco import Disco
from app.models.movimiento import DetalleMovimiento, Movimiento

carrito_bp = Blueprint("carrito", __name__)


# ─── Helpers ─── #


def _obtener_o_crear_carrito():
    carrito = (
        Carrito.objects(id_usuario=current_user.id_usuario)
        .order_by("-fecha_creacion")
        .first()
    )
    if not carrito:
        carrito = Carrito(
            detalles=[],
            total=0.0,
            fecha_creacion=datetime.now(),
            fecha_actualizacion=datetime.now(),
            id_usuario=current_user.id_usuario,
        )
        carrito.save()
    return carrito


def _cart_count():
    carrito = (
        Carrito.objects(id_usuario=current_user.id_usuario)
        .order_by("-fecha_creacion")
        .first()
    )
    return len(carrito.detalles) if carrito else 0


def _toast_resp(message, category="info", count=0):
    icons = {
        "success": '<svg xmlns="http://www.w3.org/2000/svg" class="stroke-success shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        "error": '<svg xmlns="http://www.w3.org/2000/svg" class="stroke-error shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        "warning": '<svg xmlns="http://www.w3.org/2000/svg" class="stroke-warning shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>',
    }
    icon = icons.get(category, "")
    html = f"""<div class="alert shadow-xl border border-white/20 bg-base-100/40 backdrop-blur-md text-base-content rounded-box px-4 py-3" role="alert">
        {icon}
        <span class="text-sm font-medium">{message}</span>
    </div>"""
    resp = make_response(html)
    resp.headers["X-Cart-Count"] = str(count)
    return resp


# ─── Agregar al carrito (HTMX y fallback clásico) ─── #


@carrito_bp.route("/carrito/agregar/<int:id_disco>", methods=["POST"])
@login_required
def agregar_al_carrito(id_disco):
    disco = Disco.objects(id_disco=id_disco, estado=0).first()
    if not disco:
        if request.headers.get("HX-Request"):
            return _toast_resp("Disco no disponible", "error", _cart_count())
        flash("Disco no disponible", "error")
        return redirect(url_for("discos.discos"))

    if disco.id_usuario == current_user.id_usuario:
        if request.headers.get("HX-Request"):
            return _toast_resp(
                "No puedes comprar tu propio disco", "error", _cart_count()
            )
        flash("No puedes comprar tu propio disco", "error")
        return redirect(
            url_for("detalle_disco.detalle_disco", id=id_disco, slug=disco.slug)
        )

    carrito = _obtener_o_crear_carrito()

    # Ya existe ese disco en el carrito
    if any(d.id_disco == id_disco for d in carrito.detalles):
        if request.headers.get("HX-Request"):
            return _toast_resp(
                "Este disco ya está en tu carrito", "warning", len(carrito.detalles)
            )
        flash("Este disco ya está en tu carrito", "warning")
        return redirect(url_for("carrito.ver_carrito"))

    # Calcular el siguiente id_detalle_carrito (único por carrito)
    max_det_id = max(
        (d.id_detalle_carrito or 0 for d in carrito.detalles), default=0
    )
    nuevo_detalle_id = max_det_id + 1

    carrito.detalles.append(
        DetalleCarrito(
            id_detalle_carrito=nuevo_detalle_id,
            id_carrito=0,  # No usado: el padre es ObjectId
            id_disco=disco.id_disco,
            precio=disco.precio,
            titulo=disco.titulo,
        )
    )
    carrito.total = float(carrito.total or 0) + float(disco.precio)
    carrito.fecha_actualizacion = datetime.now()
    carrito.save()

    if request.headers.get("HX-Request"):
        return _toast_resp(
            f"'{disco.titulo}' agregado al carrito",
            "success",
            len(carrito.detalles),
        )

    flash(f"'{disco.titulo}' agregado al carrito", "success")
    return redirect(url_for("carrito.ver_carrito"))


# ─── Ver carrito ─── #


@carrito_bp.route("/carrito")
@login_required
def ver_carrito():
    carrito = (
        Carrito.objects(id_usuario=current_user.id_usuario)
        .order_by("-fecha_creacion")
        .first()
    )

    items = []
    total = 0.0
    if carrito and carrito.detalles:
        disco_ids = [d.id_disco for d in carrito.detalles]
        discos_map = {
            d.id_disco: d for d in Disco.objects(id_disco__in=disco_ids)
        }
        for det in carrito.detalles:
            disco = discos_map.get(det.id_disco)
            if disco:  # ignorar discos borrados huérfanos
                items.append((det, disco))
        total = float(carrito.total or 0)

    return render_template("carrito.html", items=items, total=total)


# ─── Eliminar del carrito ─── #


@carrito_bp.route("/carrito/eliminar/<int:id_detalle>", methods=["POST"])
@login_required
def eliminar_del_carrito(id_detalle):
    carrito = (
        Carrito.objects(id_usuario=current_user.id_usuario)
        .order_by("-fecha_creacion")
        .first()
    )
    if not carrito:
        flash("Carrito no encontrado", "error")
        return redirect(url_for("carrito.ver_carrito"))

    detalle = next(
        (d for d in carrito.detalles if d.id_detalle_carrito == id_detalle),
        None,
    )
    if not detalle:
        flash("Item no encontrado", "error")
        return redirect(url_for("carrito.ver_carrito"))

    carrito.total = max(0, float(carrito.total or 0) - float(detalle.precio or 0))
    carrito.fecha_actualizacion = datetime.now()
    carrito.detalles = [
        d for d in carrito.detalles if d.id_detalle_carrito != id_detalle
    ]
    carrito.save()

    flash("Item eliminado del carrito", "success")
    return redirect(url_for("carrito.ver_carrito"))


# ─── Comprar carrito completo (ya adaptado a Mongo) ─── #


@carrito_bp.route("/carrito/comprar", methods=["POST"])
@login_required
def comprar_carrito():
    if not current_user.tarjeta_numero or not current_user.tarjeta_vencimiento:
        flash("Agrega un método de pago en tu perfil antes de comprar", "warning")
        return redirect(url_for("carrito.ver_carrito"))

    carrito = (
        Carrito.objects(id_usuario=current_user.id_usuario)
        .order_by("-fecha_creacion")
        .first()
    )
    if not carrito or not carrito.detalles:
        flash("Tu carrito está vacío", "error")
        return redirect(url_for("carrito.ver_carrito"))

    disco_ids = [det.id_disco for det in carrito.detalles]
    discos_map = {d.id_disco: d for d in Disco.objects(id_disco__in=disco_ids)}

    for det in carrito.detalles:
        disco = discos_map.get(det.id_disco)
        if not disco or disco.estado != 0:
            titulo = disco.titulo if disco else "Un disco"
            flash(f"'{titulo}' ya no está disponible", "error")
            return redirect(url_for("carrito.ver_carrito"))

    max_mov = Movimiento.objects.order_by("-id").first()
    nuevo_id_mov = (max_mov.id if max_mov else 0) + 1

    total = float(carrito.total or 0)
    comision = round(total * 0.06, 2)

    titulos = ", ".join(
        [discos_map[det.id_disco].titulo for det in carrito.detalles]
    )

    nuevos_detalles = []
    for det in carrito.detalles:
        disco = discos_map[det.id_disco]
        nuevos_detalles.append(
            DetalleMovimiento(
                id_movimiento=nuevo_id_mov,
                id_disco=disco.id_disco,
                precio_unitario=det.precio,
            )
        )
        disco.estado = 2
        disco.save()

    Movimiento(
        id=nuevo_id_mov,
        tipo=1,
        fecha=datetime.now(),
        total=total,
        id_usuario=current_user.id_usuario,
        comision=comision,
        detalles=nuevos_detalles,
    ).save()

    carrito.detalles = []
    carrito.total = 0.0
    carrito.fecha_actualizacion = datetime.now()
    carrito.save()

    try:
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


# ─── Comprar ahora (ya adaptado a Mongo) ─── #


@carrito_bp.route("/comprar/ahora/<int:id_disco>", methods=["POST"])
@login_required
def comprar_ahora(id_disco):
    if not current_user.tarjeta_numero or not current_user.tarjeta_vencimiento:
        flash("Agrega un método de pago en tu perfil antes de comprar", "warning")
        return redirect(url_for("discos.discos"))

    disco = Disco.objects(id_disco=id_disco, estado=0).first()
    if not disco:
        flash("Disco no disponible", "error")
        return redirect(url_for("discos.discos"))

    if disco.id_usuario == current_user.id_usuario:
        flash("No puedes comprar tu propio disco", "error")
        return redirect(
            url_for("detalle_disco.detalle_disco", id=id_disco, slug=disco.slug)
        )

    max_mov = Movimiento.objects.order_by("-id").first()
    nuevo_id_mov = (max_mov.id if max_mov else 0) + 1

    total = float(disco.precio)
    comision = round(total * 0.06, 2)

    Movimiento(
        id=nuevo_id_mov,
        tipo=1,
        fecha=datetime.now(),
        total=total,
        id_usuario=current_user.id_usuario,
        comision=comision,
        detalles=[
            DetalleMovimiento(
                id_movimiento=nuevo_id_mov,
                id_disco=disco.id_disco,
                precio_unitario=disco.precio,
            )
        ],
    ).save()

    disco.estado = 2
    disco.save()

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
