from datetime import datetime
from pathlib import PureWindowsPath

import psycopg
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from .login import current_user
from .registration import RegisteredUser


router = APIRouter(prefix="/api/documents", tags=["Documents"])
MAX_PDF_BYTES = 5 * 1024 * 1024


class DocumentSummary(BaseModel):
    id: int
    original_filename: str
    submitted_at: datetime
    review_status: str


def require_applicant(user: RegisteredUser = Depends(current_user)) -> RegisteredUser:
    if user.role != "Applicant":
        raise HTTPException(status_code=403, detail="Applicant access required")
    return user


@router.post("", status_code=201, response_model=DocumentSummary)
def upload_document(
    file: UploadFile = File(...),
    applicant: RegisteredUser = Depends(require_applicant),
):
    filename = PureWindowsPath(file.filename or "").name.strip()
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Choose a PDF file")

    content = file.file.read(MAX_PDF_BYTES + 1)
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds the 5 MiB limit")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="PDF header missing")

    try:
        with psycopg.connect(connect_timeout=3) as connection:
            row = connection.execute(
                """
                INSERT INTO documents (applicant_id, original_filename, pdf_content)
                VALUES (%s, %s, %s)
                RETURNING id, original_filename, submitted_at, review_status
                """,
                (applicant.id, filename, content),
            ).fetchone()
    except psycopg.OperationalError:
        raise HTTPException(503, "Database unavailable") from None

    return DocumentSummary(
        id=row[0],
        original_filename=row[1],
        submitted_at=row[2],
        review_status=row[3],
    )


@router.get("", response_model=list[DocumentSummary])
def list_my_documents(applicant: RegisteredUser = Depends(require_applicant)):
    try:
        with psycopg.connect(connect_timeout=3) as connection:
            rows = connection.execute(
                """
                SELECT id, original_filename, submitted_at, review_status
                FROM documents
                WHERE applicant_id = %s
                ORDER BY submitted_at DESC, id DESC
                """,
                (applicant.id,),
            ).fetchall()
    except psycopg.OperationalError:
        raise HTTPException(503, "Database unavailable") from None

    return [
        DocumentSummary(
            id=row[0],
            original_filename=row[1],
            submitted_at=row[2],
            review_status=row[3],
        )
        for row in rows
    ]