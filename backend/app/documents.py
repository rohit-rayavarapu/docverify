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
    return store_documents([file], application, document_type, notes, applicant.id)[0]


@router.post("/batch", status_code=201, response_model=list[DocumentSummary])
def upload_batch(
    files: list[UploadFile] = File(...),
    application: str = Form("My application", min_length=1, max_length=120),
    document_type: Literal["Transcript", "Degree certificate", "Language certificate", "Other"] = Form("Other"),
    notes: str = Form("", max_length=1000),
    applicant: RegisteredUser = Depends(require_applicant),
):
    return store_documents(files, application, document_type, notes, applicant.id)


def store_documents(files, application, document_type, notes, applicant_id):
    title = application.strip()
    if not title:
        raise HTTPException(422, "Enter an application name")
    if not 1 <= len(files) <= 10:
        raise HTTPException(422, "Choose between 1 and 10 files")
    notes = notes.strip()
    saved = []
    try:
        with psycopg.connect(connect_timeout=3) as connection:
            # Serialize batches for this applicant, including overlapping batches
            # that submit the same files in different orders.
            connection.execute(
                "SELECT id FROM users WHERE id = %s FOR NO KEY UPDATE", (applicant_id,)
            )
            application_id = connection.execute(
                """
                INSERT INTO applications (applicant_id, title) VALUES (%s, %s)
                ON CONFLICT (applicant_id, title) DO UPDATE SET title = EXCLUDED.title
                RETURNING id
                """,
                (applicant_id, title),
            ).fetchone()[0]
            for file in files:
                filename = PureWindowsPath(file.filename or "").name.strip()
                content = file.file.read(MAX_BYTES + 1)
                try:
                    media_type = media_type_for(filename, content)
                except HTTPException as error:
                    raise HTTPException(error.status_code, f"{filename}: {error.detail}") from error
                row = connection.execute(
                    """
                    INSERT INTO documents (applicant_id, original_filename, pdf_content,
                                           application_id, document_type, notes, media_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (applicant_id, sha256(pdf_content))
                        WHERE NOT historical_duplicate DO NOTHING
                    RETURNING id, original_filename, submitted_at, review_status
                    """,
                    (applicant_id, filename, content, application_id, document_type, notes, media_type),
                ).fetchone()
                if row is None:
                    raise HTTPException(
                        409,
                        f"{filename}: duplicate file for this account or selection. "
                        "No files from this upload were saved. Remove the duplicate and try again.",
                    )
                saved.append(DocumentSummary(
                    id=row[0], original_filename=row[1],
                    submitted_at=row[2], review_status=row[3],
                ))
    except psycopg.OperationalError:
        raise HTTPException(503, "Database unavailable") from None

    return saved


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
