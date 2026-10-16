from math import ceil

from flask import Blueprint, render_template, request
from flask_login import current_user

from app.models.disco import Disco
from app.models.subasta import Subastas

subasta_bp = Blueprint("subastas", __name__)
PER_PAGE = 12


@subasta_bp.route("/subastas")
def subastas():
    # 1. Capturar filtros de la request
    formatos_select = [f for f in request.args.getlist("formato") if f]
    generos_select = request.args.getlist("generos")

    # 2. Buscar primero las subastas activas (estado=1)
    subastas_activas_qs = Subastas.objects(estado=1)
    discos_ids_en_subasta = [s.id_disco for s in subastas_activas_qs.only('id_disco')]

    # Si no hay subastas activas, devolvemos el contexto vacío
    if not discos_ids_en_subasta:
        context = {
            "subastas": [],
            "lista_generos": list(Disco.MAPA_GENEROS.values()),
            "formatos_select": formatos_select,
            "generos_select": generos_select,
            "page": 1,
            "total_pages": 0,
            "total_discos": 0,
            "per_page": PER_PAGE,
        }
        if request.headers.get("HX-Request"):
            return render_template("partials/_subastas_grid.html", **context)
        return render_template("subastas.html", **context)

    # 3. Buscar los discos que corresponden a estas subastas
    # Usamos id_disco__in porque ese es el nombre exacto del campo en el modelo
    discos_qs = Disco.objects(id_disco__in=discos_ids_en_subasta)

    # 4. Aplicar filtros sobre los discos encontrados
    if current_user.is_authenticated:
        discos_qs = discos_qs.filter(id_usuario__ne=current_user.id_usuario)

    # Filtro formato
    if formatos_select:
        filtros = []
        if "cd" in formatos_select:
            filtros.append(False)
        if "vinilo" in formatos_select:
            filtros.append(True)
        if filtros:
            discos_qs = discos_qs.filter(formato__in=filtros)

    # Filtro género
    if generos_select:
        mapa_inverso = {v: k for k, v in Disco.MAPA_GENEROS.items()}
        generos_ids = [
            mapa_inverso.get(g)
            for g in generos_select
            if mapa_inverso.get(g) is not None
        ]
        if generos_ids:
            discos_qs = discos_qs.filter(genero__in=generos_ids)

    # 5. Obtener los IDs de los discos que sobrevivieron a los filtros
    # CORRECCIÓN: Usar 'id_disco' en .only() en lugar de 'id'
    discos_ids_filtrados = [d.id_disco for d in discos_qs.only('id_disco')]

    # 6. Volver a filtrar las subastas para que solo incluyan los discos válidos
    subastas_qs = Subastas.objects(estado=1, id_disco__in=discos_ids_filtrados)

    # 7. Paginación
    page = max(request.args.get("page", 1, type=int), 1)
    total_subastas = subastas_qs.count()
    total_pages = ceil(total_subastas / PER_PAGE) if total_subastas > 0 else 1
    page = min(page, total_pages)
    skip = (page - 1) * PER_PAGE

    subastas_result = list(subastas_qs.skip(skip).limit(PER_PAGE))

    # 8. Mapeo manual: Adjuntar el objeto Disco a cada objeto Subasta
    discos_ids_pagina = [s.id_disco for s in subastas_result]

    # CORRECCIÓN: Usar 'id_disco__in' y 'd.id_disco' para el diccionario
    discos_map = {
        d.id_disco: d
        for d in Disco.objects(id_disco__in=discos_ids_pagina)
    }

    for subasta in subastas_result:
        subasta.disco = discos_map.get(subasta.id_disco)

    # 9. Construir contexto
    context = {
        "subastas": subastas_result,
        "lista_generos": list(Disco.MAPA_GENEROS.values()),
        "formatos_select": formatos_select,
        "generos_select": generos_select,
        "page": page,
        "total_pages": total_pages,
        "total_discos": total_subastas,
        "per_page": PER_PAGE,
    }

    # 10. Retornar respuesta
    if request.headers.get("HX-Request"):
        return render_template("partials/_subastas_grid.html", **context)

    return render_template("subastas.html", **context)
