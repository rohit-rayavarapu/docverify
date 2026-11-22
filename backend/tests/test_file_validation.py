from io import BytesIO

import pymupdf
import pytest
from fastapi import HTTPException
from PIL import Image

from app.file_validation import MAX_BYTES, media_type_for


@pytest.mark.parametrize(("fmt", "suffix"), [("JPEG", "jpg"), ("PNG", "png")])
def test_readable_images(fmt, suffix):
    data = BytesIO()
    Image.new("RGB", (32, 16)).save(data, fmt)
    assert media_type_for("scan." + suffix, data.getvalue()) == "image/" + fmt.lower()


def test_readable_pdf():
    with pymupdf.open() as pdf:
        pdf.new_page()
        assert media_type_for("scan.pdf", pdf.tobytes()) == "application/pdf"


@pytest.mark.parametrize(("name", "content", "status"), [
    ("broken.pdf", b"%PDF-invalid", 422),
    ("broken.png", b"bad", 422),
    ("notes.txt", b"text", 415),
    ("fake.pdf", b"bad", 415),
    ("large.pdf", b"a" * (MAX_BYTES + 1), 413),
])
def test_invalid_uploads(name, content, status):
    with pytest.raises(HTTPException) as error:
        media_type_for(name, content)
    assert error.value.status_code == status
