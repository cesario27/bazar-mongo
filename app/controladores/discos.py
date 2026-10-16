from math import ceil

from flask import Blueprint, render_template, request
from flask_login import current_user

from app.models.disco import Disco

discos_bp = Blueprint("discos", __name__)
PER_PAGE = 12

@discos_bp.route("/discos")
def discos():
    # 1. Filtros de la request
    formatos_select = [f for f in request.args.getlist("formato") if f]
    generos_select = request.args.getlist("generos")

    # 2. Iniciar el QuerySet con el filtro base
    qs = Disco.objects(estado=0)

    # 3. Filtro de usuario autenticado
    if current_user.is_authenticated:
        qs = qs.filter(id_usuario__ne=current_user.id_usuario)

    # 4. Filtro formato
    if formatos_select:
        filtros = []
        if "cd" in formatos_select:
            filtros.append(False)
        if "vinilo" in formatos_select:
            filtros.append(True)
        if filtros:
            qs = qs.filter(formato__in=filtros)

    # 5. Filtro género
    if generos_select:
        mapa_inverso = {v: k for k, v in Disco.MAPA_GENEROS.items()}
        generos_ids = [
            mapa_inverso.get(g)
            for g in generos_select
            if mapa_inverso.get(g) is not None
        ]
        if generos_ids:
            qs = qs.filter(genero__in=generos_ids)

    # 6. Paginación
    page = request.args.get("page", 1, type=int)
    page = max(page,1)

    # Contar total de documentos que coinciden con los filtros
    total_discos = qs.count()

    total_pages = ceil(total_discos / PER_PAGE) if total_discos > 0 else 1
    page = min(page, total_pages)

    # Aplicar paginación al QuerySet
    skip = (page - 1) * PER_PAGE
    discos_result = qs.skip(skip).limit(PER_PAGE)

    # 7. Contexto para el template
    context = {
        "discos": discos_result,  # El QuerySet es iterable directamente en Jinja2
        "lista_generos": list(Disco.MAPA_GENEROS.values()),
        "formatos_select": formatos_select,
        "generos_select": generos_select,
        "page": page,
        "total_pages": total_pages,
        "total_discos": total_discos,
        "per_page": PER_PAGE,
    }

    # 8. Respuesta (HTMX o normal)
    if request.headers.get("HX-Request"):
        return render_template("partials/_discos_grid.html", **context)

    return render_template("discos.html", **context)
