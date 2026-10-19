from collections import defaultdict, namedtuple
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.models.disco import Disco
from app.models.movimiento import DetalleMovimiento, Movimiento
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

from collections import defaultdict
# Asegúrate de importar defaultdict al inicio de admin.py

@admin_bp.route("/ventas")
@admin_required
def ventas():
    movimientos = list(Movimiento.objects.order_by("-fecha").limit(100))

    # Diccionario para acumular las ventas por id_usuario (vendedor)
    vendedores_agg = defaultdict(lambda: {"total_ventas": set(), "ingresos": 0.0, "discos_vendidos": 0})

    # 1. Recolectar todos los IDs de discos involucrados
    ids_discos = set()
    for mov in movimientos:
        for det in (mov.detalles or []):
            if det.id_disco:
                ids_discos.add(det.id_disco)

    # 2. Hacer una sola consulta a la BD para obtener esos discos
    discos_map = {d.id_disco: d for d in Disco.objects(id_disco__in=list(ids_discos))}

    # 3. Procesar las ventas
    for mov in movimientos:
        for det in (mov.detalles or []):
            disco = discos_map.get(det.id_disco)
            if disco and disco.id_usuario:
                v = vendedores_agg[disco.id_usuario]
                # Usamos mov.id para contar transacciones únicas
                v["total_ventas"].add(mov.id)
                v["ingresos"] += float(det.precio_unitario or 0)
                v["discos_vendidos"] += 1

    # 4. Obtener los datos de los usuarios vendedores
    usuarios_map = {
        u.id_usuario: u
        for u in Usuario.objects(id_usuario__in=list(vendedores_agg.keys()))
    }

    # 5. Construir la lista de TopVendedor y ordenarla
    top_vendedores = []
    for id_user, data in vendedores_agg.items():
        u = usuarios_map.get(id_user)
        if u:
            top_vendedores.append(
                TopVendedor(
                    id_usuario=id_user,
                    nombre=u.nombre,
                    icono_usuario=u.icono_usuario,
                    total_ventas=len(data["total_ventas"]),
                    ingresos=data["ingresos"],
                    discos_vendidos=data["discos_vendidos"]
                )
            )

    # Ordenar por ingresos de mayor a menor y tomar los primeros 10
    top_vendedores.sort(key=lambda x: x.ingresos, reverse=True)
    top_vendedores = top_vendedores[:10]

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
