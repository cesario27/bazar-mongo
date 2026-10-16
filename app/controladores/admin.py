from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import extract, func

from app.base import SessionLocal
from app.modelos.detalle_movimiento import Detalle_Movimiento
from app.modelos.disco import Disco
from app.modelos.movimiento import Movimiento
from app.modelos.usuario import Usuario

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if getattr(current_user, "tipo_usuario", None) != 2:
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


@admin_bp.route("/")
@admin_required
def dashboard():
    session = SessionLocal()
    try:
        total_usuarios = session.query(func.count(Usuario.id_usuario)).scalar()
        total_ventas = session.query(func.count(Movimiento.id_movimiento)).scalar()
        ingresos_totales = session.query(func.sum(Movimiento.total)).scalar() or 0
        comisiones_totales = session.query(func.sum(Movimiento.comision)).scalar() or 0

        ventas_mes = (
            session.query(
                extract("month", Movimiento.fecha).label("mes"),
                extract("year", Movimiento.fecha).label("anio"),
                func.sum(Movimiento.total).label("total"),
                func.sum(Movimiento.comision).label("comision"),
                func.count(Movimiento.id_movimiento).label("cantidad"),
            )
            .group_by("mes", "anio")
            .order_by("anio", "mes")
            .limit(12)
            .all()
        )

        return render_template(
            "admin/dashboard.html",
            total_usuarios=total_usuarios,
            total_ventas=total_ventas,
            ingresos_totales=ingresos_totales,
            comisiones_totales=comisiones_totales,
            ventas_mes=ventas_mes,
        )
    finally:
        session.close()


@admin_bp.route("/usuarios")
@admin_required
def usuarios():
    session = SessionLocal()
    try:
        lista = session.query(Usuario).order_by(Usuario.fecha_registro.desc()).all()
        return render_template("admin/usuarios.html", usuarios=lista)
    finally:
        session.close()


@admin_bp.route("/usuario/<int:id>/eliminar", methods=["POST"])
@admin_required
def eliminar_usuario(id):
    if current_user.id_usuario == id:
        flash("No puedes eliminar tu propia cuenta", "error")
        return redirect(url_for("admin.usuarios"))

    session = SessionLocal()
    try:
        usuario = session.get(Usuario, id)
        if usuario:
            session.delete(usuario)
            session.commit()
            flash(f"Usuario {usuario.nombre} eliminado correctamente", "success")
        else:
            flash("Usuario no encontrado", "error")
    except Exception as e:
        session.rollback()
        flash(f"Error al eliminar usuario: {str(e)}", "error")
    finally:
        session.close()

    return redirect(url_for("admin.usuarios"))


@admin_bp.route("/ventas")
@admin_required
def ventas():
    session = SessionLocal()
    try:
        movimientos = (
            session.query(Movimiento).order_by(Movimiento.fecha.desc()).limit(100).all()
        )

        # ─── CORREGIDO: usar precio_unitario en lugar de total_producto/cantidad ───
        top_vendedores = (
            session.query(
                Usuario.id_usuario,
                Usuario.nombre,
                Usuario.icono_usuario,
                func.count(func.distinct(Movimiento.id_movimiento)).label(
                    "total_ventas"
                ),
                func.sum(Detalle_Movimiento.precio_unitario).label("ingresos"),
                func.count(Detalle_Movimiento.id_detalle_movimiento).label(
                    "discos_vendidos"
                ),
            )
            .select_from(Detalle_Movimiento)
            .join(Disco, Detalle_Movimiento.id_disco == Disco.id_disco)
            .join(Usuario, Disco.id_usuario == Usuario.id_usuario)
            .join(
                Movimiento, Detalle_Movimiento.id_movimiento == Movimiento.id_movimiento
            )
            .group_by(Usuario.id_usuario, Usuario.nombre, Usuario.icono_usuario)
            .order_by(func.sum(Detalle_Movimiento.precio_unitario).desc())
            .limit(10)
            .all()
        )

        return render_template(
            "admin/ventas.html",
            movimientos=movimientos,
            top_vendedores=top_vendedores,
        )
    finally:
        session.close()


@admin_bp.route("/discos")
@admin_required
def discos():
    session = SessionLocal()
    try:
        lista = (
            session.query(Disco, Usuario)
            .join(Usuario, Disco.id_usuario == Usuario.id_usuario)
            .order_by(Disco.id_disco.desc())
            .all()
        )
        return render_template("admin/discos.html", discos=lista)
    finally:
        session.close()


@admin_bp.route("/disco/<int:id>/eliminar", methods=["POST"])
@admin_required
def eliminar_disco(id):
    session = SessionLocal()
    try:
        disco = session.get(Disco, id)
        if disco:
            session.delete(disco)
            session.commit()
            flash(f"Disco '{disco.titulo}' eliminado correctamente", "success")
        else:
            flash("Disco no encontrado", "error")
    except Exception as e:
        session.rollback()
        flash(f"Error al eliminar disco: {str(e)}", "error")
    finally:
        session.close()

    return redirect(url_for("admin.discos"))
