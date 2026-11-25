import psycopg
from fastapi.responses import Response
from .documents import DocumentListItem, DocumentSummary
from fastapi import APIRouter, Depends, HTTPException
from typing import Literal
from .extraction import ExtractionResult, extract_review_document
from pydantic import BaseModel

from .login import current_user
from .registration import RegisteredUser


router = APIRouter(prefix="/api/reviewer", tags=["Reviewer"])


def require_reviewer(user: RegisteredUser = Depends(current_user)) -> RegisteredUser:
    if user.role != "Reviewer":
        raise HTTPException(status_code=403, detail="Reviewer access required")
    return user


@router.get("/dashboard", response_model=RegisteredUser)
def reviewer_dashboard(reviewer: RegisteredUser = Depends(require_reviewer)):
    return reviewer

@router.get(
    "/documents",
    response_model=list[DocumentListItem],
)
def list_pending_documents(reviewer: RegisteredUser = Depends(require_reviewer)):
    try:
        with psycopg.connect(connect_timeout=3) as connection:
            rows = connection.execute(
                """
                SELECT d.id, d.original_filename, d.submitted_at, d.review_status,
                       u.full_name, u.email, a.title, d.document_type, d.notes
                FROM documents AS d
                JOIN users AS u ON u.id = d.applicant_id
                JOIN applications AS a ON a.id = d.application_id
                WHERE d.review_status = 'Pending' AND d.applicant_id <> %s
                ORDER BY d.submitted_at, d.id
                """,
                (reviewer.id,),
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

@router.get(
    "/documents/{document_id}/file",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}, "image/jpeg": {}, "image/png": {}}}},
)
def open_document_file(document_id: int, reviewer: RegisteredUser = Depends(require_reviewer)):
    try:
        with psycopg.connect(connect_timeout=3) as connection:
            row = connection.execute(
                "SELECT pdf_content, media_type FROM documents WHERE id = %s AND applicant_id <> %s",
                (document_id, reviewer.id),
            ).fetchone()
    except psycopg.OperationalError:
        raise HTTPException(503, "Database unavailable") from None

    if row is None:
        raise HTTPException(404, "Document not found")

    extension = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}[row[1]]
    return Response(
        content=bytes(row[0]),
        media_type=row[1],
        headers={
            "Content-Disposition": f'inline; filename="document-{document_id}.{extension}"',
            "Cache-Control": "no-store",
        },
    )


class ReviewDecision(BaseModel):
    decision: Literal["Approved", "Rejected"]


@router.post("/documents/{document_id}/decision", response_model=DocumentSummary)
def record_decision(
    document_id: int,
    request: ReviewDecision,
    reviewer: RegisteredUser = Depends(require_reviewer),
):
    try:
        with psycopg.connect(connect_timeout=3) as connection:
            row = connection.execute(
                """
                UPDATE documents
                SET review_status = %s, reviewed_by = %s, reviewed_at = now()
                WHERE id = %s AND applicant_id <> %s AND review_status = 'Pending'
                RETURNING id, original_filename, submitted_at, review_status
                """,
                (request.decision, reviewer.id, document_id, reviewer.id),
            ).fetchone()

            if row is None:
                exists = connection.execute(
                    "SELECT 1 FROM documents WHERE id = %s AND applicant_id <> %s",
                    (document_id, reviewer.id),
                ).fetchone()
                if exists is None:
                    raise HTTPException(404, "Document not found")
                raise HTTPException(409, "Document already reviewed")
    except psycopg.OperationalError:
        raise HTTPException(503, "Database unavailable") from None

    return DocumentSummary(
        id=row[0],
        original_filename=row[1],
        submitted_at=row[2],
        review_status=row[3],
    )
@router.post("/documents/{document_id}/extraction", response_model=ExtractionResult)
def extract_document_for_review(
    document_id: int,
    reviewer: RegisteredUser = Depends(require_reviewer),
):
    return extract_review_document(document_id, reviewer.id)