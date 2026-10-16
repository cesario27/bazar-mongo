import hashlib
import secrets
from datetime import datetime, timezone

import cloudinary
import cloudinary.uploader
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.base import SessionLocal
from app.modelos.detalle_movimiento import Detalle_Movimiento
from app.modelos.disco import Disco
from app.modelos.movimiento import Movimiento
from app.modelos.puja import Puja
from app.modelos.subasta import Subasta
from app.modelos.usuario import Usuario

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


# Clave para encriptar
_ENCRYPTION_KEY = "bazar_stereo_secret_key_2026"


@mi_cuenta_bp.route("/micuenta")
@login_required
def mi_cuenta():
    session = SessionLocal()
    try:
        total_compras = (
            session.query(func.count(Movimiento.id_movimiento))
            .filter_by(id_usuario=current_user.id_usuario, tipo=1)
            .scalar()
        ) or 0

        subastas_cerradas = session.query(Subasta).filter(Subasta.estado != 1).all()
        subastas_ganadas = 0
        for sub in subastas_cerradas:
            puja_ganadora = (
                session.query(Puja)
                .filter_by(id_subasta=sub.id_subasta)
                .order_by(Puja.porcentaje.desc(), Puja.fecha.desc())
                .first()
            )
            if puja_ganadora and puja_ganadora.id_usuario == current_user.id_usuario:
                subastas_ganadas += 1

        pedidos = (
            session.query(Movimiento, Detalle_Movimiento, Disco)
            .join(
                Detalle_Movimiento,
                Movimiento.id_movimiento == Detalle_Movimiento.id_movimiento,
            )
            .join(Disco, Detalle_Movimiento.id_disco == Disco.id_disco)
            .filter(
                Movimiento.id_usuario == current_user.id_usuario,
                Movimiento.tipo.in_([1, 2]),
            )
            .order_by(Movimiento.fecha.desc())
            .all()
        )

        # Desencriptar tarjeta para mostrar en el formulario
        tarjeta_mostrada = ""
        if current_user.tarjeta_numero:
            try:
                tarjeta_mostrada = _decrypt_simple(
                    current_user.tarjeta_numero, _ENCRYPTION_KEY
                )
            except:
                tarjeta_mostrada = current_user.tarjeta_numero  # Legacy sin encriptar

        return render_template(
            "mi_cuenta.html",
            total_compras=total_compras,
            subastas_ganadas=subastas_ganadas,
            pedidos=pedidos,
            tarjeta_mostrada=tarjeta_mostrada,
        )
    finally:
        session.close()


@mi_cuenta_bp.route("/micuenta/actualizar", methods=["POST"])
@login_required
def actualizar_perfil():
    session = SessionLocal()
    try:
        usuario = (
            session.query(Usuario).filter_by(id_usuario=current_user.id_usuario).first()
        )
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

        # ─── Cambio de contraseña ─── #
        if contraseña_nueva:
            # Verificar contraseña actual
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

            # Generar nuevo hash
            nuevo_salt = secrets.token_hex(16)
            usuario.salt = nuevo_salt
            usuario.contraseña = _hash_password(contraseña_nueva, nuevo_salt)
            flash("Contraseña actualizada correctamente", "success")

        # ─── Tarjeta: encriptar antes de guardar ─── #
        if tarjeta_numero:
            # Validar que sea numérica
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

        # NO guardamos CVV en la BD por seguridad

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

        session.commit()
        flash("Perfil actualizado correctamente", "success")

    except Exception as e:
        session.rollback()
        flash(f"Error al actualizar perfil: {str(e)}", "error")
    finally:
        session.close()

    return redirect(url_for("mi_cuenta.mi_cuenta"))
