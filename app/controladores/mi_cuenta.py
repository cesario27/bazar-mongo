import hashlib
import secrets
from datetime import datetime, timezone

import cloudinary
import cloudinary.uploader
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models.disco import Disco

# Ajusta las rutas de importación si tus modelos están en otra carpeta
from app.models.movimiento import DetalleMovimiento, Movimiento
from app.models.subasta import Puja
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
        id_usuario=current_user.id_usuario,
        tipo=1
    ).count()

    # 2. Subastas ganadas
    # Optimización: Solo revisamos subastas cerradas donde el usuario haya pujado
    subastas_ganadas = 0
    subastas_cerradas = Subasta.objects(estado__ne=1).only('id_subasta')

    for sub in subastas_cerradas:
        # Obtener la puja más alta para esta subasta
        puja_ganadora = Puja.objects(id_subasta=sub.id_subasta).order_by('-porcentaje', '-fecha').first()
        if puja_ganadora and puja_ganadora.id_usuario == current_user.id_usuario:
            subastas_ganadas += 1

    # 3. Historial de pedidos (Simulación de JOIN eficiente)
    # Paso A: Obtener los movimientos del usuario
    movimientos = Movimiento.objects(
        id_usuario=current_user.id_usuario,
        tipo__in=[1, 2]
    ).order_by('-fecha').all()

    mov_ids = [m.id_movimiento for m in movimientos]
    pedidos_data = []

    if mov_ids:
        # Paso B: Obtener todos los detalles de esos movimientos de una sola vez
        detalles = DetalleMovimiento.objects(id_movimiento__in=mov_ids).all()

        # Paso C: Obtener todos los discos relacionados de una sola vez
        disco_ids = list(set([d.id_disco for d in detalles]))
        discos_map = {
            d.id_disco: d
            for d in Disco.objects(id_disco__in=disco_ids).only('id_disco', 'titulo', 'imagen', 'precio', 'artista')
        }

        # Paso D: Unir los datos en memoria (como haría un JOIN en SQL)
        for mov in movimientos:
            mov_detalles = [d for d in detalles if d.id_movimiento == mov.id_movimiento]
            for det in mov_detalles:
                pedidos_data.append({
                    'movimiento': mov,
                    'detalle': det,
                    'disco': discos_map.get(det.id_disco)
                })

    # 4. Desencriptar tarjeta para mostrar en el formulario
    tarjeta_mostrada = ""
    if current_user.tarjeta_numero:
        try:
            tarjeta_mostrada = _decrypt_simple(current_user.tarjeta_numero, _ENCRYPTION_KEY)
        except Exception:
            tarjeta_mostrada = current_user.tarjeta_numero  # Legacy sin encriptar

    return render_template(
        "mi_cuenta.html",
        total_compras=total_compras,
        subastas_ganadas=subastas_ganadas,
        pedidos=pedidos_data,  # Pasamos la lista de diccionarios unidos
        tarjeta_mostrada=tarjeta_mostrada,
    )


@mi_cuenta_bp.route("/micuenta/actualizar", methods=["POST"])
@login_required
def actualizar_perfil():
    # 1. Buscar usuario
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

    # 2. Actualizar campos básicos
    if nombre:
        usuario.nombre = nombre
    if direccion:
        usuario.direccion = direccion

    # 3. Cambio de contraseña
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

    # 4. Tarjeta: encriptar antes de guardar
    if tarjeta_numero:
        if not tarjeta_numero.isdigit() or len(tarjeta_numero) < 13:
            flash("Número de tarjeta inválido", "error")
            return redirect(url_for("mi_cuenta.mi_cuenta"))
        usuario.tarjeta_numero = _encrypt_simple(tarjeta_numero, _ENCRYPTION_KEY)
    else:
        usuario.tarjeta_numero = None  # Limpiar si se envía vacío

    if tarjeta_vencimiento:
        usuario.tarjeta_vencimiento = tarjeta_vencimiento
    else:
        usuario.tarjeta_vencimiento = None

    # 5. Subida de imagen a Cloudinary
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

    # 6. Guardar todos los cambios en MongoDB
    try:
        usuario.save()
        flash("Perfil actualizado correctamente", "success")
    except Exception as e:
        flash(f"Error al actualizar perfil: {str(e)}", "error")

    return redirect(url_for("mi_cuenta.mi_cuenta"))
