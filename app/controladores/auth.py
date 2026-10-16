import hashlib
import secrets

from flask import Blueprint, flash, redirect, request, url_for
from flask_login import login_required, login_user, logout_user

from app.base import SessionLocal
from app.modelos.usuario import Usuario

auth_bp = Blueprint("auth", __name__)


def _hash_password(password: str, salt: str) -> str:
    """Hash SHA-256 con salt"""
    return hashlib.sha256((password + salt).encode()).hexdigest()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return redirect(url_for("main.inicio"))

    correo = request.form.get("correo", "").strip()
    contraseña = request.form.get("contraseña", "")

    session = SessionLocal()
    try:
        usuario = session.query(Usuario).filter_by(correo=correo).first()

        if not usuario:
            flash("Este correo no está registrado", "error")
            return redirect(url_for("main.inicio"))

        # Verificar con hash si tiene salt, si no comparar plano (migración)
        if usuario.salt:
            hash_ingresado = _hash_password(contraseña, usuario.salt)
            match = hash_ingresado == usuario.contraseña
        else:
            # Legacy: contraseña sin hash (solo durante migración)
            match = usuario.contraseña == contraseña

        if not match:
            flash("Contraseña incorrecta", "error")
            return redirect(url_for("main.inicio"))

        # Migrar a hash si aún no tiene salt
        if not usuario.salt:
            usuario.salt = secrets.token_hex(16)
            usuario.contraseña = _hash_password(usuario.contraseña, usuario.salt)
            session.commit()

        login_user(usuario)
        flash(f"¡Bienvenido, {usuario.nombre}!", "success")
        return redirect(
            request.args.get("next")
            or request.form.get("next")
            or url_for("main.inicio")
        )
    finally:
        session.close()


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return redirect(url_for("main.inicio"))

    nombre = request.form.get("nombre", "").strip()
    correo = request.form.get("correo", "").strip()
    contraseña = request.form.get("contraseña", "")

    if not nombre or not correo or not contraseña:
        flash("Todos los campos son obligatorios", "error")
        return redirect(url_for("main.inicio"))

    session = SessionLocal()
    try:
        existe = session.query(Usuario).filter_by(correo=correo).first()

        if existe:
            flash("Este correo ya está registrado. Inicia sesión.", "warning")
            return redirect(url_for("main.inicio"))

        # Generar salt y hash
        salt = secrets.token_hex(16)
        password_hash = _hash_password(contraseña, salt)

        nuevo = Usuario(
            nombre=nombre,
            correo=correo,
            contraseña=password_hash,
            salt=salt,
            tipo_usuario=1,
            direccion="",
        )
        session.add(nuevo)
        session.commit()

        login_user(nuevo)
        flash("¡Cuenta creada exitosamente!", "success")
        return redirect(url_for("main.inicio"))

    except Exception as e:
        session.rollback()
        flash(f"Error al registrar: {str(e)}", "error")
        return redirect(url_for("main.inicio"))
    finally:
        session.close()


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada", "info")
    return redirect(url_for("main.inicio"))
