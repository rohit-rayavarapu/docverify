from datetime import datetime
from typing import Literal
from pathlib import PureWindowsPath

import psycopg
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .file_validation import MAX_BYTES, media_type_for
from .login import current_user
from .registration import RegisteredUser


router = APIRouter(prefix="/api/documents", tags=["Documents"])



class DocumentSummary(BaseModel):
    id: int
    original_filename: str
    submitted_at: datetime
    review_status: str


class DocumentListItem(DocumentSummary):
    applicant_name: str | None
    applicant_email: str
    application_title: str
    document_type: str
    notes: str


def require_applicant(user: RegisteredUser = Depends(current_user)) -> RegisteredUser:
    if user.role != "Applicant":
        raise HTTPException(status_code=403, detail="Applicant access required")
    return user


@router.post("", status_code=201, response_model=DocumentSummary)
def upload_document(
    file: UploadFile = File(...),
    application: str = Form("My application", min_length=1, max_length=120),
    document_type: Literal["Transcript", "Degree certificate", "Language certificate", "Other"] = Form("Other"),
    notes: str = Form("", max_length=1000),
    applicant: RegisteredUser = Depends(require_applicant),
):
    filename = PureWindowsPath(file.filename or "").name.strip()
    title = application.strip()
    if not title:
        raise HTTPException(422, "Enter an application name")
    content = file.file.read(MAX_BYTES + 1)
    media_type = media_type_for(filename, content)

    try:
        with psycopg.connect(connect_timeout=3) as connection:
            application_id = connection.execute(
                """
                INSERT INTO applications (applicant_id, title) VALUES (%s, %s)
                ON CONFLICT (applicant_id, title) DO UPDATE SET title = EXCLUDED.title
                RETURNING id
                """,
                (applicant.id, title),
            ).fetchone()[0]
            row = connection.execute(
                """
                INSERT INTO documents (applicant_id, original_filename, pdf_content,
                                       application_id, document_type, notes, media_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, original_filename, submitted_at, review_status
                """,
                (applicant.id, filename, content, application_id, document_type, notes.strip(), media_type),
            ).fetchone()
    except psycopg.OperationalError:
        raise HTTPException(503, "Database unavailable") from None

    return DocumentSummary(
        id=row[0],
        original_filename=row[1],
        submitted_at=row[2],
        review_status=row[3],
    )


@router.get("", response_model=list[DocumentListItem])
def list_my_documents(applicant: RegisteredUser = Depends(require_applicant)):
    try:
        with psycopg.connect(connect_timeout=3) as connection:
            rows = connection.execute(
                """
                SELECT d.id, d.original_filename, d.submitted_at, d.review_status,
                       u.full_name, u.email, a.title, d.document_type, d.notes
                FROM documents AS d
                JOIN users AS u ON u.id = d.applicant_id
                JOIN applications AS a ON a.id = d.application_id
                WHERE d.applicant_id = %s
                ORDER BY d.submitted_at DESC, d.id DESC
                """,
                (applicant.id,),
            ).fetchall()
    except psycopg.OperationalError:
        raise HTTPException(503, "Database unavailable") from None

    return [
        DocumentListItem(
            id=row[0],
            original_filename=row[1],
            submitted_at=row[2],
            review_status=row[3],
            applicant_name=row[4],
            applicant_email=row[5],
            application_title=row[6],
            document_type=row[7],
            notes=row[8],
        )
        for row in rows
    ]
