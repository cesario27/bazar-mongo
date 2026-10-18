from datetime import datetime, timezone

import cloudinary
import cloudinary.uploader
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models.disco import Disco
from app.models.movimiento import Movimiento
from app.models.subasta import Subastas  # ← plural, así se llama tu clase
from app.models.usuario import Usuario

cloudinary.config(
    cloud_name="duzyxnnvg",
    api_key="852222973695323",
    api_secret="G2ndCgulGTtULPMerD8LNV1E2-s",
    secure=True,
)

vendedor_bp = Blueprint("vendedor", __name__)


def _mis_discos_ids() -> set[int]:
    return {
        d.id_disco
        for d in Disco.objects(id_usuario=current_user.id_usuario).only("id_disco")
    }


@vendedor_bp.route("/")
@login_required
def panel_vendedor():
    ahora = datetime.now()
    mis_discos_ids = _mis_discos_ids()
    ids_list = list(mis_discos_ids)

    # 1) Cerrar subastas vencidas del usuario
    if ids_list:
        for sub in Subastas.objects(
            id_disco__in=ids_list,
            estado=1,
            fecha_fin__lte=ahora,
        ):
            sub.estado = 0
            sub.save()
            disco = Disco.objects(id_disco=sub.id_disco).first()
            if disco and disco.estado == 1:
                disco.estado = 0
                disco.save()

    # 2) Discos del usuario (venta normal + en subasta)
    mis_discos = list(
        Disco.objects(
            id_usuario=current_user.id_usuario,
            estado__in=[0, 1],
        )
    )

    # 3) Estadísticas — filtradas en Mongo con $elemMatch sobre detalles
    total_ventas = 0.0
    total_movimientos = 0
    if ids_list:
        for mov in Movimiento.objects(tipo=1, detalles__id_disco__in=ids_list):
            for det in mov.detalles:
                if det.id_disco in mis_discos_ids:
                    total_ventas += float(det.precio_unitario or 0)
                    total_movimientos += 1

    subastas_activas = (
        Subastas.objects(id_disco__in=ids_list, estado=1).count() if ids_list else 0
    )

    calificacion = round(min(5.0, 3.0 + (total_movimientos * 0.05)), 1)

    # 4) Mis ventas: (mov, det, disco, comprador) — mismo shape que en SQL
    mis_ventas = []
    if ids_list:
        for mov in (
            Movimiento.objects(
                tipo__in=[1, 2],
                detalles__id_disco__in=ids_list,
            )
            .order_by("-fecha")
            .limit(50)
        ):
            for det in mov.detalles:
                if det.id_disco not in mis_discos_ids:
                    continue
                disco = Disco.objects(id_disco=det.id_disco).first()
                comprador = Usuario.objects(id_usuario=mov.id_usuario).first()
                if disco and comprador:
                    mis_ventas.append((mov, det, disco, comprador))

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


@vendedor_bp.route("/disco/nuevo", methods=["POST"])
@login_required
def crear_disco():
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
        except Exception:
            flash("Error al subir imagen, se usará imagen por defecto", "warning")

    max_d = Disco.objects.order_by("-id_disco").first()
    nuevo_id = (max_d.id_disco if max_d else 0) + 1

    Disco(
        id_disco=nuevo_id,
        estado=0,
        titulo=titulo,
        artista=artista,
        formato=formato,
        descripcion=descripcion,
        precio=float(precio),
        genero=genero,
        imagen=imagen_url,
        id_usuario=current_user.id_usuario,
    ).save()

    flash(f"¡Disco '{titulo}' publicado!", "success")
    return redirect(url_for("vendedor.panel_vendedor"))


@vendedor_bp.route("/disco/<int:id_disco>/editar", methods=["GET"])
@login_required
def editar_disco_form(id_disco):
    disco = Disco.objects(id_disco=id_disco, id_usuario=current_user.id_usuario).first()
    if not disco:
        return "<div class='alert alert-error'>Disco no encontrado</div>", 404
    return render_template(
        "partials/_editar_disco_form.html",
        disco=disco,
        mapa_generos=list(Disco.MAPA_GENEROS.items()),
    )


@vendedor_bp.route("/disco/<int:id_disco>/editar", methods=["POST"])
@login_required
def editar_disco(id_disco):
    disco = Disco.objects(id_disco=id_disco, id_usuario=current_user.id_usuario).first()
    if not disco:
        return "<div class='alert alert-error'>Disco no encontrado</div>", 404

    disco.titulo = request.form.get("titulo", "").strip()
    disco.artista = request.form.get("artista", "").strip()
    disco.descripcion = request.form.get("descripcion", "").strip()

    mapa_generos = {v: k for k, v in Disco.MAPA_GENEROS.items()}
    genero_nombre = request.form.get("genero", "")
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

    disco.save()
    flash("Disco actualizado correctamente", "success")

    mis_discos = list(
        Disco.objects(id_usuario=current_user.id_usuario, estado__in=[0, 1])
    )
    return render_template("partials/_mis_discos.html", mis_discos=mis_discos)


@vendedor_bp.route("/disco/<int:id_disco>/eliminar", methods=["GET"])
@login_required
def eliminar_disco_form(id_disco):
    disco = Disco.objects(id_disco=id_disco, id_usuario=current_user.id_usuario).first()
    if not disco:
        return "<div class='alert alert-error'>Disco no encontrado</div>", 404
    return render_template("partials/_eliminar_disco_form.html", disco=disco)


@vendedor_bp.route("/disco/<int:id_disco>/eliminar", methods=["POST"])
@login_required
def eliminar_disco(id_disco):
    disco = Disco.objects(id_disco=id_disco, id_usuario=current_user.id_usuario).first()
    if not disco:
        return "<div class='alert alert-error'>Disco no encontrado</div>", 404

    disco.delete()
    flash("Disco eliminado", "success")

    mis_discos = list(
        Disco.objects(id_usuario=current_user.id_usuario, estado__in=[0, 1])
    )
    return render_template("partials/_mis_discos.html", mis_discos=mis_discos)


@vendedor_bp.route("/subasta/crear", methods=["POST"])
@login_required
def crear_subasta():
    disco_id = int(request.form.get("disco_id"))

    disco = Disco.objects(
        id_disco=disco_id,
        id_usuario=current_user.id_usuario,
        estado=0,
    ).first()
    if not disco:
        flash("Disco no válido o ya está en subasta", "error")
        return redirect(url_for("vendedor.panel_vendedor"))

    if Subastas.objects(id_disco=disco_id, estado=1).first():
        flash("Este disco ya tiene una subasta activa", "error")
        return redirect(url_for("vendedor.panel_vendedor"))

    precio_base = float(request.form.get("precio_inicial"))
    precio_minimo = float(request.form.get("precio_deseado"))

    if precio_minimo < precio_base:
        flash("El precio mínimo no puede ser menor al precio inicial", "error")
        return redirect(url_for("vendedor.panel_vendedor"))

    # Subastas usa id (int) como PK, igual que Movimiento
    max_s = Subastas.objects.order_by("-id").first()
    nuevo_id = (max_s.id if max_s else 0) + 1

    fecha_inicio = datetime.fromisoformat(request.form.get("fecha_inicio"))
    fecha_fin = datetime.fromisoformat(request.form.get("fecha_cierre"))

    Subastas(
        id=nuevo_id,
        precio=precio_base,
        precio_minimo=precio_minimo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        estado=1,
        id_disco=disco_id,
        pujas=[],
    ).save()

    disco.estado = 1
    disco.save()

    flash("Subasta creada correctamente", "success")
    return redirect(url_for("vendedor.panel_vendedor"))


@vendedor_bp.route("/subasta/cancelar/<int:id_disco>", methods=["POST"])
@login_required
def cancelar_subasta(id_disco):
    disco = Disco.objects(
        id_disco=id_disco,
        id_usuario=current_user.id_usuario,
        estado=1,
    ).first()
    if not disco:
        flash("Disco no válido", "error")
        return redirect(url_for("vendedor.panel_vendedor"))

    subasta = Subastas.objects(id_disco=id_disco, estado=1).first()
    if subasta:
        subasta.estado = 0
        subasta.save()

    disco.estado = 0
    disco.save()

    flash("Subasta cancelada. El disco vuelve a estar en venta", "success")
    return redirect(url_for("vendedor.panel_vendedor"))
