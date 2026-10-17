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

# CORRECCIÓN 1: Importar DetalleMovimiento (sin guion bajo)
from app.models.movimiento import DetalleMovimiento, Movimiento

carrito_bp = Blueprint("carrito", __name__)

# ... (Mantén _obtener_o_crear_carrito, _toast_resp, agregar_al_carrito, ver_carrito y eliminar_del_carrito IGUAL que como los tienes) ...


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

    # Verificar que todos los discos sigan disponibles (estado 0)
    for det in carrito.detalles:
        disco = discos_map.get(det.id_disco)
        if not disco or disco.estado != 0:
            titulo = disco.titulo if disco else "Un disco"
            flash(f"'{titulo}' ya no está disponible", "error")
            return redirect(url_for("carrito.ver_carrito"))

    # CORRECCIÓN 2: Ordenar por "-id" en lugar de "-id_movimiento"
    max_mov = Movimiento.objects.order_by("-id").first()
    nuevo_id_mov = (max_mov.id if max_mov else 0) + 1

    total = float(carrito.total or 0)
    comision = round(total * 0.06, 2)

    # Guardar títulos para el correo ANTES de vaciar el carrito
    titulos = ", ".join([discos_map[det.id_disco].titulo for det in carrito.detalles])

    # CORRECCIÓN 3: Construir la lista de documentos embebidos
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
        # Marcar disco como vendido
        disco.estado = 2
        disco.save()

    # CORRECCIÓN 4: Crear el movimiento padre con la lista de detalles y guardar UNA sola vez
    movimiento = Movimiento(
        id=nuevo_id_mov,  # Usar 'id' porque es la primary_key en el modelo
        tipo=1,
        fecha=datetime.now(),
        total=total,
        id_usuario=current_user.id_usuario,
        comision=comision,
        detalles=nuevos_detalles,  # <-- Aquí se asignan los embebidos
    )
    movimiento.save()

    # Vaciar el carrito
    carrito.detalles = []
    carrito.total = 0.0
    carrito.fecha_actualizacion = datetime.now()
    carrito.save()

    # Enviar correo de confirmación
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

    # CORRECCIÓN 2: Ordenar por "-id"
    max_mov = Movimiento.objects.order_by("-id").first()
    nuevo_id_mov = (max_mov.id if max_mov else 0) + 1

    total = float(disco.precio)
    comision = round(total * 0.06, 2)

    # CORRECCIÓN 3 y 4: Crear movimiento con el detalle embebido en la lista
    movimiento = Movimiento(
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
    )
    movimiento.save()

    # Marcar disco como vendido
    disco.estado = 2
    disco.save()

    # Enviar correo
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
