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
from app.modelos.subasta import Subasta
from app.modelos.usuario import Usuario

cloudinary.config(
    cloud_name="duzyxnnvg",
    api_key="852222973695323",
    api_secret="G2ndCgulGTtULPMerD8LNV1E2-s",
    secure=True,
)

vendedor_bp = Blueprint("vendedor", __name__)


@vendedor_bp.route("/")
@login_required
def panel_vendedor():
    """Muestra el panel del vendedor con estadísticas reales"""
    session = SessionLocal()
    try:
        # ─── Cerrar subastas vencidas del usuario ───
        from datetime import datetime

        ahora = datetime.now()
        vencidas = (
            session.query(Subasta)
            .join(Disco, Subasta.id_disco == Disco.id_disco)
            .filter(
                Disco.id_usuario == current_user.id_usuario,
                Subasta.estado == 1,
                Subasta.fecha_fin <= ahora,
            )
            .all()
        )
        for sub in vencidas:
            sub.estado = 0
            disco = session.get(Disco, sub.id_disco)
            if disco and disco.estado == 1:
                disco.estado = 0
        if vencidas:
            session.commit()

        # ─── Discos del usuario (venta normal + en subasta) ───
        mis_discos = (
            session.query(Disco)
            .filter_by(id_usuario=current_user.id_usuario)
            .filter(Disco.estado.in_([0, 1]))
            .all()
        )

        # ─── ESTADÍSTICAS ─── #
        ventas_result = (
            session.query(
                func.coalesce(func.sum(Detalle_Movimiento.precio_unitario), 0)
            )
            .join(
                Movimiento, Detalle_Movimiento.id_movimiento == Movimiento.id_movimiento
            )
            .join(Disco, Detalle_Movimiento.id_disco == Disco.id_disco)
            .filter(
                Disco.id_usuario == current_user.id_usuario,
                Movimiento.tipo == 1,
            )
            .scalar()
        )
        total_ventas = float(ventas_result) if ventas_result else 0

        subastas_activas = (
            session.query(Subasta)
            .join(Disco, Subasta.id_disco == Disco.id_disco)
            .filter(
                Disco.id_usuario == current_user.id_usuario,
                Subasta.estado == 1,
            )
            .count()
        )

        total_movimientos = (
            session.query(func.count(Movimiento.id_movimiento))
            .join(
                Detalle_Movimiento,
                Movimiento.id_movimiento == Detalle_Movimiento.id_movimiento,
            )
            .join(Disco, Detalle_Movimiento.id_disco == Disco.id_disco)
            .filter(Disco.id_usuario == current_user.id_usuario)
            .scalar()
        ) or 0

        calificacion = min(5.0, 3.0 + (total_movimientos * 0.05))
        calificacion = round(calificacion, 1)

        # ─── MIS VENTAS: quién compró mis discos ───
        mis_ventas = (
            session.query(
                Movimiento,
                Detalle_Movimiento,
                Disco,
                Usuario,
            )
            .join(
                Detalle_Movimiento,
                Movimiento.id_movimiento == Detalle_Movimiento.id_movimiento,
            )
            .join(Disco, Detalle_Movimiento.id_disco == Disco.id_disco)
            .join(Usuario, Movimiento.id_usuario == Usuario.id_usuario)
            .filter(
                Disco.id_usuario == current_user.id_usuario,
                Movimiento.tipo.in_([1, 2]),  # Compras + subastas ganadas
            )
            .order_by(Movimiento.fecha.desc())
            .limit(50)
            .all()
        )

        return render_template(
            "vendedor.html",
            mis_discos=mis_discos,
            mapa_generos=list(Disco.MAPA_GENEROS.items()),
            stats={
                "ventas": total_ventas,
                "subastas_activas": subastas_activas,
                "calificacion": calificacion,
                "total_movimientos": total_movimientos,
            },
            mis_ventas=mis_ventas,
        )
    finally:
        session.close()


@vendedor_bp.route("/disco/nuevo", methods=["POST"])
@login_required
def crear_disco():
    session = SessionLocal()
    try:
        titulo = request.form.get("titulo", "").strip()
        artista = request.form.get("artista", "").strip()
        genero_nombre = request.form.get("genero", "")
        formato_str = request.form.get("formato", "")
        precio = request.form.get("precio", "0")
        descripcion = request.form.get("descripcion", "").strip()
        imagen_file = request.files.get("imagen")

        if not titulo or not artista or not precio:
            flash("Título, artista y precio son obligatorios", "error")
            return redirect(url_for("vendedor.panel_vendedor"))

        mapa_generos = {v: k for k, v in Disco.MAPA_GENEROS.items()}
        genero = mapa_generos.get(genero_nombre, 0)
        formato = 1 if formato_str.lower() == "vinilo" else 0

        imagen_url = "https://placehold.co/400x400?text=Sin+Imagen"

        if imagen_file and imagen_file.filename:
            try:
                resultado = cloudinary.uploader.upload(
                    imagen_file,
                    upload_preset="bazar_stereo",
                    folder="bazar_stereo/discos",
                    public_id=f"disco_{current_user.id_usuario}_{int(datetime.now(timezone.utc).timestamp())}",
                )
                imagen_url = resultado["secure_url"]
            except Exception as e:
                flash("Error al subir imagen, se usará imagen por defecto", "warning")

        nuevo = Disco(
            estado=0,
            titulo=titulo,
            artista=artista,
            formato=formato,
            descripcion=descripcion,
            precio=float(precio),
            genero=genero,
            imagen=imagen_url,
            id_usuario=current_user.id_usuario,
        )

        session.add(nuevo)
        session.commit()

        flash(f"¡Disco '{titulo}' publicado!", "success")
        return redirect(url_for("vendedor.panel_vendedor"))

    except Exception as e:
        session.rollback()
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("vendedor.panel_vendedor"))
    finally:
        session.close()


@vendedor_bp.route("/disco/<int:id_disco>/editar", methods=["GET"])
@login_required
def editar_disco_form(id_disco):
    session = SessionLocal()
    try:
        disco = (
            session.query(Disco)
            .filter_by(id_disco=id_disco, id_usuario=current_user.id_usuario)
            .first()
        )
        if not disco:
            return "<div class='alert alert-error'>Disco no encontrado</div>", 404

        return render_template(
            "partials/_editar_disco_form.html",
            disco=disco,
            mapa_generos=list(Disco.MAPA_GENEROS.items()),
        )
    finally:
        session.close()


@vendedor_bp.route("/disco/<int:id_disco>/editar", methods=["POST"])
@login_required
def editar_disco(id_disco):
    session = SessionLocal()
    try:
        disco = (
            session.query(Disco)
            .filter_by(id_disco=id_disco, id_usuario=current_user.id_usuario)
            .first()
        )
        if not disco:
            return "<div class='alert alert-error'>Disco no encontrado</div>", 404

        disco.titulo = request.form.get("titulo", "").strip()
        disco.artista = request.form.get("artista", "").strip()
        disco.descripcion = request.form.get("descripcion", "").strip()

        genero_nombre = request.form.get("genero", "")
        mapa_generos = {v: k for k, v in Disco.MAPA_GENEROS.items()}
        if genero_nombre in mapa_generos:
            disco.genero = mapa_generos[genero_nombre]

        formato_str = request.form.get("formato", "")
        if formato_str:
            disco.formato = 1 if formato_str.lower() == "vinilo" else 0

        precio = request.form.get("precio")
        if precio:
            disco.precio = float(precio)

        imagen_file = request.files.get("imagen")
        if imagen_file and imagen_file.filename:
            try:
                resultado = cloudinary.uploader.upload(
                    imagen_file,
                    upload_preset="bazar_stereo",
                    folder="bazar_stereo/discos",
                    public_id=f"disco_{current_user.id_usuario}_{id_disco}_{int(datetime.now(timezone.utc).timestamp())}",
                )
                disco.imagen = resultado["secure_url"]
            except Exception:
                pass

        session.commit()
        flash("Disco actualizado correctamente", "success")

        mis_discos = (
            session.query(Disco)
            .filter_by(id_usuario=current_user.id_usuario)
            .filter(Disco.estado.in_([0, 1]))
            .all()
        )
        return render_template("partials/_mis_discos.html", mis_discos=mis_discos)

    except Exception as e:
        session.rollback()
        flash(f"Error al actualizar: {str(e)}", "error")
        return redirect(url_for("vendedor.panel_vendedor"))
    finally:
        session.close()


@vendedor_bp.route("/disco/<int:id_disco>/eliminar", methods=["GET"])
@login_required
def eliminar_disco_form(id_disco):
    session = SessionLocal()
    try:
        disco = (
            session.query(Disco)
            .filter_by(id_disco=id_disco, id_usuario=current_user.id_usuario)
            .first()
        )
        if not disco:
            return "<div class='alert alert-error'>Disco no encontrado</div>", 404

        return render_template("partials/_eliminar_disco_form.html", disco=disco)
    finally:
        session.close()


@vendedor_bp.route("/disco/<int:id_disco>/eliminar", methods=["POST"])
@login_required
def eliminar_disco(id_disco):
    session = SessionLocal()
    try:
        disco = (
            session.query(Disco)
            .filter_by(id_disco=id_disco, id_usuario=current_user.id_usuario)
            .first()
        )
        if not disco:
            return "<div class='alert alert-error'>Disco no encontrado</div>", 404

        session.delete(disco)
        session.commit()
        flash("Disco eliminado", "success")

        mis_discos = (
            session.query(Disco)
            .filter_by(id_usuario=current_user.id_usuario)
            .filter(Disco.estado.in_([0, 1]))
            .all()
        )
        return render_template("partials/_mis_discos.html", mis_discos=mis_discos)

    except Exception as e:
        session.rollback()
        flash(f"Error al eliminar: {str(e)}", "error")
        return redirect(url_for("vendedor.panel_vendedor"))
    finally:
        session.close()


@vendedor_bp.route("/subasta/crear", methods=["POST"])
@login_required
def crear_subasta():
    """Crea una subasta para un disco del usuario"""
    session = SessionLocal()
    try:
        disco_id = int(request.form.get("disco_id"))

        disco = (
            session.query(Disco)
            .filter_by(id_disco=disco_id, id_usuario=current_user.id_usuario, estado=0)
            .first()
        )
        if not disco:
            flash("Disco no válido o ya está en subasta", "error")
            return redirect(url_for("vendedor.panel_vendedor"))

        existente = (
            session.query(Subasta).filter_by(id_disco=disco_id, estado=1).first()
        )
        if existente:
            flash("Este disco ya tiene una subasta activa", "error")
            return redirect(url_for("vendedor.panel_vendedor"))

        precio_base = float(request.form.get("precio_inicial"))
        precio_minimo = float(request.form.get("precio_deseado"))

        if precio_minimo < precio_base:
            flash("El precio mínimo no puede ser menor al precio inicial", "error")
            return redirect(url_for("vendedor.panel_vendedor"))

        max_id = session.query(func.max(Subasta.id_subasta)).scalar()
        nuevo_id = (max_id or 0) + 1

        fecha_inicio = datetime.fromisoformat(request.form.get("fecha_inicio"))
        fecha_fin = datetime.fromisoformat(request.form.get("fecha_cierre"))

        nueva_subasta = Subasta(
            id_subasta=nuevo_id,
            precio=precio_base,
            precio_minimo=precio_minimo,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            estado=1,
            id_disco=disco_id,
        )

        disco.estado = 1

        session.add(nueva_subasta)
        session.commit()
        flash("Subasta creada correctamente", "success")
    except Exception as e:
        session.rollback()
        flash(f"Error al crear subasta: {str(e)}", "error")
    finally:
        session.close()

    return redirect(url_for("vendedor.panel_vendedor"))


@vendedor_bp.route("/subasta/cancelar/<int:id_disco>", methods=["POST"])
@login_required
def cancelar_subasta(id_disco):
    """Cancela una subasta y devuelve el disco a venta normal"""
    session = SessionLocal()
    try:
        disco = (
            session.query(Disco)
            .filter_by(id_disco=id_disco, id_usuario=current_user.id_usuario, estado=1)
            .first()
        )
        if not disco:
            flash("Disco no válido", "error")
            return redirect(url_for("vendedor.panel_vendedor"))

        subasta = session.query(Subasta).filter_by(id_disco=id_disco, estado=1).first()
        if subasta:
            subasta.estado = 0

        disco.estado = 0
        session.commit()
        flash("Subasta cancelada. El disco vuelve a estar en venta", "success")
    except Exception as e:
        session.rollback()
        flash(f"Error: {str(e)}", "error")
    finally:
        session.close()

    return redirect(url_for("vendedor.panel_vendedor"))
