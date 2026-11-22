import psycopg
from fastapi.responses import Response
from .documents import DocumentSummary
from fastapi import APIRouter, Depends, HTTPException

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
    response_model=list[DocumentSummary],
    dependencies=[Depends(require_reviewer)],
)
def list_pending_documents():
    try:
        with psycopg.connect(connect_timeout=3) as connection:
            rows = connection.execute(
                """
                SELECT id, original_filename, submitted_at, review_status
                FROM documents
                WHERE review_status = 'Pending'
                ORDER BY submitted_at, id
                """
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

@router.get(
    "/documents/{document_id}/file",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    dependencies=[Depends(require_reviewer)],
)
def open_document_pdf(document_id: int):
    try:
        with psycopg.connect(connect_timeout=3) as connection:
            row = connection.execute(
                "SELECT pdf_content FROM documents WHERE id = %s",
                (document_id,),
            ).fetchone()
    except psycopg.OperationalError:
        raise HTTPException(503, "Database unavailable") from None

    if row is None:
        raise HTTPException(404, "Document not found")

    return Response(
        content=bytes(row[0]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="document-{document_id}.pdf"',
            "Cache-Control": "no-store",
        },
    )