import hashlib
import secrets
from datetime import datetime, timezone

import cloudinary
import cloudinary.uploader
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models.disco import Disco
from app.models.movimiento import Movimiento
from app.models.subasta import Subastas
from app.models.usuario import Usuario

cloudinary.config(
    cloud_name="duzyxnnvg",
    api_key="852222973695323",
    api_secret="G2ndCgulGTtULPMerD8LNV1E2-s",
    secure=True,
)

mi_cuenta_bp = Blueprint("mi_cuenta", __name__)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((password + salt).encode()).hexdigest()


def _encrypt_simple(text: str, key: str) -> str:
    if not text:
        return ""
    encrypted = []
    for i, char in enumerate(text):
        encrypted.append(chr(ord(char) ^ ord(key[i % len(key)])))
    return "".join(encrypted)


def _decrypt_simple(encrypted: str, key: str) -> str:
    if not encrypted:
        return ""
    return _encrypt_simple(encrypted, key)


_ENCRYPTION_KEY = "bazar_stereo_secret_key_2026"


@mi_cuenta_bp.route("/micuenta")
@login_required
def mi_cuenta():
    # 1. Total de compras
    total_compras = Movimiento.objects(
        id_usuario=current_user.id_usuario, tipo=1
    ).count()

    # 2. Subastas ganadas
    subastas_ganadas = 0
    subastas_cerradas = Subastas.objects(estado__ne=1).all()

    for sub in subastas_cerradas:
        if not sub.pujas:
            continue

        pujas_ordenadas = sorted(
            sub.pujas,
            key=lambda p: (p.porcentaje, p.fecha if p.fecha else datetime.min),
            reverse=True
        )

        puja_ganadora = pujas_ordenadas[0]

        if puja_ganadora.id_usuario == current_user.id_usuario:
            subastas_ganadas += 1

    # 3. Historial de pedidos (CORREGIDO: Los detalles ya vienen en el movimiento)
    movimientos = (
        Movimiento.objects(id_usuario=current_user.id_usuario, tipo__in=[1, 2])
        .order_by("-id")
        .all()
    )

    pedidos_data = []

    if movimientos:
        # Paso A: Extraer todos los detalles de todos los movimientos en una sola lista
        todos_los_detalles = []
        for mov in movimientos:
            for det in mov.detalles:  # ← Los detalles ya están aquí, no necesitas consultar
                todos_los_detalles.append((mov, det))

        # Paso B: Obtener todos los discos relacionados de una sola vez
        disco_ids = list(set([det.id_disco for _, det in todos_los_detalles]))
        discos_map = {
            d.id_disco: d
            for d in Disco.objects(id_disco__in=disco_ids).only(
                "id_disco", "titulo", "imagen", "precio", "artista"
            )
        }

        # Paso C: Construir la lista de pedidos
        for mov, det in todos_los_detalles:
            pedidos_data.append(
                {
                    "movimiento": mov,
                    "detalle": det,
                    "disco": discos_map.get(det.id_disco),
                }
            )

    # 4. Desencriptar tarjeta para mostrar en el formulario
    tarjeta_mostrada = ""
    if current_user.tarjeta_numero:
        try:
            tarjeta_mostrada = _decrypt_simple(
                current_user.tarjeta_numero, _ENCRYPTION_KEY
            )
        except Exception:
            tarjeta_mostrada = current_user.tarjeta_numero

    return render_template(
        "mi_cuenta.html",
        total_compras=total_compras,
        subastas_ganadas=subastas_ganadas,
        pedidos=pedidos_data,
        tarjeta_mostrada=tarjeta_mostrada,
    )


@mi_cuenta_bp.route("/micuenta/actualizar", methods=["POST"])
@login_required
def actualizar_perfil():
    usuario = Usuario.objects(id_usuario=current_user.id_usuario).first()
    if not usuario:
        flash("Usuario no encontrado", "error")
        return redirect(url_for("mi_cuenta.mi_cuenta"))

    nombre = request.form.get("nombre", "").strip()
    direccion = request.form.get("direccion", "").strip()
    tarjeta_numero = request.form.get("tarjeta_numero", "").strip().replace(" ", "")
    tarjeta_vencimiento = request.form.get("tarjeta_vencimiento", "").strip()
    contraseña_actual = request.form.get("contraseña_actual", "")
    contraseña_nueva = request.form.get("contraseña_nueva", "")
    contraseña_confirmar = request.form.get("contraseña_confirmar", "")

    if nombre:
        usuario.nombre = nombre
    if direccion:
        usuario.direccion = direccion

    if contraseña_nueva:
        if usuario.salt:
            hash_actual = _hash_password(contraseña_actual, usuario.salt)
            match = hash_actual == usuario.contraseña
        else:
            match = usuario.contraseña == contraseña_actual

        if not match:
            flash("Contraseña actual incorrecta", "error")
            return redirect(url_for("mi_cuenta.mi_cuenta"))

        if contraseña_nueva != contraseña_confirmar:
            flash("Las contraseñas nuevas no coinciden", "error")
            return redirect(url_for("mi_cuenta.mi_cuenta"))

        if len(contraseña_nueva) < 6:
            flash("La contraseña debe tener al menos 6 caracteres", "error")
            return redirect(url_for("mi_cuenta.mi_cuenta"))

        nuevo_salt = secrets.token_hex(16)
        usuario.salt = nuevo_salt
        usuario.contraseña = _hash_password(contraseña_nueva, nuevo_salt)
        flash("Contraseña actualizada correctamente", "success")

    if tarjeta_numero:
        if not tarjeta_numero.isdigit() or len(tarjeta_numero) < 13:
            flash("Número de tarjeta inválido", "error")
            return redirect(url_for("mi_cuenta.mi_cuenta"))
        usuario.tarjeta_numero = _encrypt_simple(tarjeta_numero, _ENCRYPTION_KEY)
    else:
        usuario.tarjeta_numero = None

    if tarjeta_vencimiento:
        usuario.tarjeta_vencimiento = tarjeta_vencimiento
    else:
        usuario.tarjeta_vencimiento = None

    imagen_file = request.files.get("icono_usuario")
    if imagen_file and imagen_file.filename:
        try:
            resultado = cloudinary.uploader.upload(
                imagen_file,
                folder="bazar_stereo/usuarios",
                public_id=f"usuario_{current_user.id_usuario}_{int(datetime.now(timezone.utc).timestamp())}",
                overwrite=True,
            )
            usuario.icono_usuario = resultado["secure_url"]
        except Exception as e:
            flash(f"Error al subir imagen: {str(e)}", "error")

    try:
        usuario.save()
        flash("Perfil actualizado correctamente", "success")
    except Exception as e:
        flash(f"Error al actualizar perfil: {str(e)}", "error")

    return redirect(url_for("mi_cuenta.mi_cuenta"))
