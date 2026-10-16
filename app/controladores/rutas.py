from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


# <-- Rutas -->
@main_bp.route("/")
def inicio():
    return render_template("index.html")
