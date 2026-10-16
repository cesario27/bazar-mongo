import re
import unicodedata


def slugify(texto: str) -> str:
    # Normalizar tildes: á → a, é → e, etc.
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")

    texto = texto.lower().strip()
    texto = re.sub(r"[^\w\s-]", "", texto)  # quitar puntuación
    texto = re.sub(r"[\s_]+", "-", texto)  # espacios → guiones
    texto = re.sub(r"-+", "-", texto)  # evitar guiones repetidos
    return texto.strip("-")
