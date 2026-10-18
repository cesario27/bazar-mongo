from collections import defaultdict, namedtuple
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.models.disco import Disco
from app.models.movimiento import Movimiento
from app.models.usuario import Usuario

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# namedtuples para que el template pueda usar tanto v.mes como { for mes, ... in }
VentaMes = namedtuple("VentaMes", ["mes", "anio", "total", "comision", "cantidad"])
TopVendedor = namedtuple(
    "TopVendedor",
    [
        "id_usuario",
        "nombre",
        "icono_usuario",
        "total_ventas",
        "ingresos",
        "discos_vendidos",
    ],
)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if getattr(current_user, "tipo_usuario", None) != 2:
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


# ─── Dashboard ─── #


@admin_bp.route("/")
@admin_required
def dashboard():
    total_usuarios = Usuario.objects.count()
    total_ventas = Movimiento.objects.count()

    # Un solo pase: totales globales + agrupación por mes
    ingresos_totales = 0.0
    comisiones_totales = 0.0
    ventas_agg = defaultdict(lambda: {"total": 0.0, "comision": 0.0, "cantidad": 0})

    for mov in Movimiento.objects.only("fecha", "total", "comision"):
        ingresos_totales += float(mov.total or 0)
        comisiones_totales += float(mov.comision or 0)
        if not mov.fecha:
            continue
        key = (mov.fecha.year, mov.fecha.month)
        ventas_agg[key]["total"] += float(mov.total or 0)
        ventas_agg[key]["comision"] += float(mov.comision or 0)
        ventas_agg[key]["cantidad"] += 1

    ventas_mes = [
        VentaMes(
            mes=m,
            anio=y,
            total=v["total"],
            comision=v["comision"],
            cantidad=v["cantidad"],
        )
        for (y, m), v in sorted(ventas_agg.items())
    ][:12]

    return render_template(
        "admin/dashboard.html",
        total_usuarios=total_usuarios,
        total_ventas=total_ventas,
        ingresos_totales=ingresos_totales,
        comisiones_totales=comisiones_totales,
        ventas_mes=ventas_mes,
    )


# ─── Usuarios ─── #


@admin_bp.route("/usuarios")
@admin_required
def usuarios():
    lista = list(Usuario.objects.order_by("-fecha_registro"))
    return render_template("admin/usuarios.html", usuarios=lista)


@admin_bp.route("/usuario/<int:id>/eliminar", methods=["POST"])
@admin_required
def eliminar_usuario(id):
    if current_user.id_usuario == id:
        flash("No puedes eliminar tu propia cuenta", "error")
        return redirect(url_for("admin.usuarios"))

    usuario = Usuario.objects(id_usuario=id).first()
    if not usuario:
        flash("Usuario no encontrado", "error")
        return redirect(url_for("admin.usuarios"))

    nombre = usuario.nombre
    try:
        usuario.delete()
        flash(f"Usuario {nombre} eliminado correctamente", "success")
    except Exception as e:
        flash(f"Error al eliminar usuario: {str(e)}", "error")

    return redirect(url_for("admin.usuarios"))


# ─── Ventas ─── #


@admin_bp.route("/ventas")
@admin_required
def ventas():
    movimientos = list(Movimiento.objects.order_by("-fecha").limit(100))

    pipeline = [
        {"$unwind": "$detalles"},
        {
            "$lookup": {
                "from": Disco._get_collection_name(),
                "localField": "detalles.id_disco",
                "foreignField": "id_disco",
                "as": "disco_info",
            }
        },
        {"$unwind": "$disco_info"},
        {
            "$group": {
                "_id": "$disco_info.id_usuario",
                "total_ventas_ids": {"$addToSet": "$id"},
                "ingresos": {"$sum": "$detalles.precio_unitario"},
                "discos_vendidos": {"$sum": 1},
            }
        },
        {"$sort": {"ingresos": -1}},
        {"$limit": 10},
    ]
    raw_top = list(Movimiento.objects.aggregate(*pipeline))

    usuarios_map = {
        u.id_usuario: u
        for u in Usuario.objects(id_usuario__in=[r["_id"] for r in raw_top])
    }

    top_vendedores = []
    for r in raw_top:
        u = usuarios_map.get(r["_id"])
        if not u:
            continue
        top_vendedores.append(
            TopVendedor(
                id_usuario=r["_id"],
                nombre=u.nombre,
                icono_usuario=u.icono_usuario,
                total_ventas=len(r["total_ventas_ids"]),
                ingresos=r["ingresos"],
                discos_vendidos=r["discos_vendidos"],
            )
        )

    return render_template(
        "admin/ventas.html",
        movimientos=movimientos,
        top_vendedores=top_vendedores,
    )


# ─── Discos ─── #


@admin_bp.route("/discos")
@admin_required
def discos():
    discos_list = list(Disco.objects.order_by("-id_disco"))
    usuarios_map = {
        u.id_usuario: u
        for u in Usuario.objects(
            id_usuario__in=[d.id_usuario for d in discos_list if d.id_usuario]
        )
    }
    lista = [(d, usuarios_map.get(d.id_usuario)) for d in discos_list]
    return render_template("admin/discos.html", discos=lista)


@admin_bp.route("/disco/<int:id>/eliminar", methods=["POST"])
@admin_required
def eliminar_disco(id):
    disco = Disco.objects(id_disco=id).first()
    if not disco:
        flash("Disco no encontrado", "error")
        return redirect(url_for("admin.discos"))

    titulo = disco.titulo
    try:
        disco.delete()
        flash(f"Disco '{titulo}' eliminado correctamente", "success")
    except Exception as e:
        flash(f"Error al eliminar disco: {str(e)}", "error")

    return redirect(url_for("admin.discos"))
