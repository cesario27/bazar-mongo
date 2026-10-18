from typing import Any

import cloudinary
from flask.app import Flask
from flask_login import LoginManager, current_user
from flask_mail import Mail

from app.base import conexion_mongo
from app.controladores.admin import admin_bp
from app.controladores.auth import auth_bp
from app.controladores.carrito import carrito_bp
from app.controladores.detalle_subasta import detalle_subasta_bp
from app.controladores.disco import detalle_disco_bp
from app.controladores.discos import discos_bp
from app.controladores.mi_cuenta import mi_cuenta_bp
from app.controladores.rutas import main_bp
from app.controladores.subastas import subasta_bp
from app.controladores.utils import slugify
from app.controladores.vendedor import vendedor_bp

login_manager = LoginManager()
mail = Mail()
login_manager: Any = LoginManager()


def create_app():
    conexion_mongo()
    app = Flask(__name__)
    app.secret_key = "cesar:v12"

    # Claudinary config
    cloudinary.config(
        cloud_name="duzyxnnvg",
        api_key="852222973695323",
        api_secret="G2ndCgulGTtULPMerD8LNV1E2-s",
        secure=True,
    )

    # Flask Mail
    app.config["MAIL_SERVER"] = "smtp.gmail.com"
    app.config["MAIL_PORT"] = 587
    app.config["MAIL_USE_TLS"] = True
    app.config["MAIL_USE_SSL"] = False
    app.config["MAIL_USERNAME"] = "ruizcesar12756@gmail.com"
    app.config["MAIL_PASSWORD"] = "nnvt gtqu fwqu vcrt"
    app.config["MAIL_DEFAULT_SENDER"] = ("Bazar Stereo", "ruizcesar12756@gmail.com")
    mail.init_app(app)

    # Flask Login
    login_manager.init_app(app)
    login_manager.login_view = "main.inicio"
    login_manager.login_message_category = "warning"

    app.jinja_env.filters["slugify"] = slugify

    @app.context_processor
    def inject_cart_count():
        if not current_user.is_authenticated:
            return {"cart_count": 0}

        from app.models.carrito import Carrito

        carrito = (
            Carrito.objects(id_usuario=current_user.id_usuario)
            .order_by("-fecha_creacion")
            .first()
        )

        if not carrito:
            return {"cart_count": 0}

        return {"cart_count": len(carrito.detalles)}

    app.register_blueprint(auth_bp)
    app.register_blueprint(discos_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(subasta_bp)
    app.register_blueprint(detalle_disco_bp)
    app.register_blueprint(vendedor_bp, url_prefix="/vendedor")
    app.register_blueprint(detalle_subasta_bp)
    app.register_blueprint(mi_cuenta_bp)
    app.register_blueprint(carrito_bp)
    app.register_blueprint(admin_bp)

    return app


@login_manager.user_loader
def load_user(user_id):
    from app.models.usuario import Usuario

    try:
        return Usuario.objects(id_usuario=int(user_id)).first()
    except (ValueError, TypeError):
        return None
