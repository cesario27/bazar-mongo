from flask import current_app, render_template
from flask_mail import Message


def enviar_correo_confirmacion(destinatario, nombre, disco, precio, tipo="compra"):
    """
    Envía correo de confirmación de compra o subasta ganada usando template HTML.

    Args:
        destinatario: Email del usuario
        nombre: Nombre del usuario
        disco: Título del disco (string)
        precio: Precio final (float)
        tipo: "compra" o "subasta"
    """
    try:
        mail = current_app.extensions.get("mail")
        if not mail:
            current_app.logger.warning("Mail extension no encontrada")
            return False

        asunto = (
            "¡Tu compra en Bazar Stereo!"
            if tipo == "compra"
            else "¡Ganaste una subasta en Bazar Stereo!"
        )

        # Renderizar template HTML
        html_body = render_template(
            "confirmacion/confirmacion.html",
            nombre=nombre,
            disco=disco,
            precio=precio,
            tipo=tipo,
        )

        msg = Message(
            subject=asunto,
            recipients=[destinatario],
        )

        # Cuerpo en texto plano (fallback para clientes que no soportan HTML)
        msg.body = f"""Hola {nombre},

{"Tu compra" if tipo == "compra" else "La subasta que ganaste"} ha sido confirmada.

Disco: {disco}
Precio final: ${precio:.2f} MXN

Gracias por confiar en Bazar Stereo.
Equipo Bazar Stereo
"""

        # Cuerpo HTML (el bonito)
        msg.html = html_body

        mail.send(msg)
        current_app.logger.info(f"✅ Correo enviado a {destinatario}: {asunto}")
        return True

    except Exception as e:
        current_app.logger.error(f"❌ Error enviando correo: {e}")
        return False
