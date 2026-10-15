"""Armazenamento das fotos de receitas.

Como o `llm.py` faz com o provedor de IA, este módulo é o único que sabe onde
os arquivos moram. Hoje é um diretório local (um volume do Docker); trocar por
um bucket (S3, Supabase Storage) mexe aqui e em nenhum outro lugar.

Um upload é a entrada mais perigosa de uma API: são bytes arbitrários que o
servidor grava em disco e depois entrega para outros usuários. As defesas,
nesta ordem:

1. tamanho máximo, conferido lendo no máximo um byte além do limite;
2. formato identificado pelo **conteúdo**, nunca pelo `Content-Type` nem pela
   extensão — os dois são escolhidos por quem envia;
3. limite de pixels antes de decodificar, contra "bombas de descompressão"
   (um PNG de poucos KB que vira gigabytes na memória);
4. a imagem é **reprocessada**: decodificada e gravada de novo como WebP. Isso
   descarta metadados EXIF — que podem conter a localização GPS da foto — e
   qualquer conteúdo escondido junto da imagem (arquivos poliglotas);
5. o nome do arquivo é gerado aqui. O nome enviado pelo cliente é ignorado: um
   "../../app/main.py" como nome não tem para onde ir.
"""

import re
import uuid
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import get_settings

settings = get_settings()

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
# Maior lado da imagem gravada. Uma foto de celular tem 4000px; numa tela de
# receita, 1600px já sobram, e o arquivo fica uma fração do original.
MAX_DIMENSION = 1600
ACCEPTED_FORMATS = {"JPEG", "PNG", "WEBP"}

# Só nomes que este módulo gerou. Conferido antes de apagar qualquer arquivo.
_GENERATED_NAME = re.compile(r"^[0-9a-f]{32}\.webp$")

RECIPES_SUBDIR = "recipes"
PUBLIC_PREFIX = "/media"


class ImageTooLargeError(Exception):
    """O arquivo passa do tamanho máximo."""


class InvalidImageError(Exception):
    """O conteúdo não é uma imagem JPEG, PNG ou WebP válida."""


def recipes_dir() -> Path:
    return Path(settings.media_dir) / RECIPES_SUBDIR


def ensure_media_dirs() -> None:
    recipes_dir().mkdir(parents=True, exist_ok=True)


def public_url(filename: str | None) -> str | None:
    """Caminho público da imagem, relativo à URL da API."""
    if filename is None:
        return None
    return f"{PUBLIC_PREFIX}/{RECIPES_SUBDIR}/{filename}"


def save_recipe_image(stream: BinaryIO) -> str:
    """Valida, reprocessa e grava a imagem. Devolve o nome do arquivo gerado."""
    data = stream.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageTooLargeError()

    try:
        with Image.open(BytesIO(data)) as image:
            # Image.open só lê o cabeçalho: formato e dimensões estão
            # disponíveis antes de decodificar um único pixel.
            if image.format not in ACCEPTED_FORMATS:
                raise InvalidImageError(image.format)
            width, height = image.size
            if width * height > MAX_IMAGE_PIXELS:
                raise InvalidImageError("dimensões excessivas")

            # A orientação de fotos de celular vem no EXIF. Ela é aplicada aos
            # pixels antes de o EXIF ser descartado, senão a foto ficaria
            # deitada.
            processed = ImageOps.exif_transpose(image)
            processed.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
            if processed.mode not in ("RGB", "RGBA"):
                processed = processed.convert("RGBA" if "A" in processed.getbands() else "RGB")

            filename = f"{uuid.uuid4().hex}.webp"
            ensure_media_dirs()
            processed.save(recipes_dir() / filename, "WEBP", quality=82)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        # Pillow sinaliza arquivo corrompido com exceções variadas; para quem
        # chamou, todas significam a mesma coisa.
        raise InvalidImageError(str(exc)) from exc

    return filename


def delete_recipe_image(filename: str | None) -> None:
    """Apaga o arquivo, se for um nome gerado por este módulo."""
    if filename is None or not _GENERATED_NAME.match(filename):
        return
    (recipes_dir() / filename).unlink(missing_ok=True)
