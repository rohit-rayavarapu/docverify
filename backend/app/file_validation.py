from io import BytesIO
from pathlib import PureWindowsPath

import pymupdf
from fastapi import HTTPException
from PIL import Image

MAX_BYTES = 5 * 1024 * 1024
FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}


def media_type_for(filename: str, content: bytes) -> str:
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "Choose a file of 5 MiB or less")
    extension = PureWindowsPath(filename).suffix.lower()
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(415, "PDF header missing")
        try:
            with pymupdf.open(stream=content, filetype="pdf") as pdf:
                if pdf.needs_pass or not pdf.page_count or not pdf.is_pdf:
                    raise ValueError()
                for page in pdf:
                    extent = max(page.rect.width, page.rect.height)
                    if extent <= 0:
                        raise ValueError()
                    scale = min(1, 128 / extent)
                    page.get_pixmap(matrix=pymupdf.Matrix(scale, scale))
        except (ValueError, RuntimeError, OverflowError):
            raise HTTPException(422, "Choose a readable, unlocked PDF") from None
        return "application/pdf"
    expected = FORMATS.get(extension)
    if expected is None:
        raise HTTPException(415, "Choose a PDF, JPG or PNG file")
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format != expected:
                raise HTTPException(415, "Image contents do not match the filename")
            if image.width * image.height > 25_000_000:
                raise HTTPException(413, "Choose an image of 25 megapixels or less")
            image.verify()
        with Image.open(BytesIO(content)) as image:
            image.load()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise HTTPException(422, "Choose a readable image") from None
    return "image/jpeg" if expected == "JPEG" else "image/png"
