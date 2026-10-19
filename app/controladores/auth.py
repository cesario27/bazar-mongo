import hashlib
import secrets

from flask import Blueprint, flash, redirect, request, url_for
from flask_login import login_required, login_user, logout_user

from app.models.usuario import Usuario

auth_bp = Blueprint("auth", __name__)


def _hash_password(password: str, salt: str) -> str:
    """Hash SHA-256 con salt"""
    return hashlib.sha256((password + salt).encode()).hexdigest()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return redirect(url_for("main.inicio"))

    correo = request.form.get("correo", "").strip().lower()
    contraseña = request.form.get("contraseña", "")

    usuario = Usuario.objects(correo__iexact=correo).first()

    # Debug
    # print(f"Buscando correo: '{correo}'")
    # print(f"Usuarios en BD: {[(u.correo, u.nombre) for u in Usuario.objects.all()]}")
    # usuario = Usuario.objects(correo__iexact=correo).first()
    # print(f"Usuario encontrado: {usuario}")

    if not usuario:
        flash("Este correo no está registrado", "error")
        return redirect(url_for("main.inicio"))

    if usuario.salt:
        hash_ingresado = _hash_password(contraseña, usuario.salt)
        match = hash_ingresado == usuario.contraseña
    else:
        match = usuario.contraseña == contraseña

    if not match:
        flash("Contraseña incorrecta", "error")
        return redirect(url_for("main.inicio"))

    if not usuario.salt:
        usuario.salt = secrets.token_hex(16)
        usuario.contraseña = _hash_password(contraseña, usuario.salt)
        usuario.save()

    login_user(usuario)
    flash(f"¡Bienvenido, {usuario.nombre}!", "success")

    return redirect(
        request.args.get("next")
        or request.form.get("next")
        or url_for("main.inicio")
    )


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

    existe = Usuario.objects(correo=correo).first()

    if existe:
        flash("Este correo ya está registrado. Inicia sesión.", "warning")
        return redirect(url_for("main.inicio"))

    try:
        salt = secrets.token_hex(16)
        password_hash = _hash_password(contraseña, salt)

        ultimo = Usuario.objects.order_by("-id_usuario").first()
        nuevo_id = (ultimo.id_usuario + 1) if ultimo else 1

        nuevo = Usuario(
            id_usuario=nuevo_id,
            nombre=nombre,
            correo=correo,
            contraseña=password_hash,
            salt=salt,
            tipo_usuario=1,
            direccion="",
        )
        nuevo.save()

        login_user(nuevo)
        flash("¡Cuenta creada exitosamente!", "success")
        return redirect(url_for("main.inicio"))

    except Exception as e:
        flash(f"Error al registrar: {str(e)}", "error")
        return redirect(url_for("main.inicio"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada", "info")
    return redirect(url_for("main.inicio"))
