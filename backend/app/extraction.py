import os
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, ValidationError


class ExtractedPage(BaseModel):
    page: int = Field(ge=1)
    method: Literal["pdf_text", "ocr"]
    text: str | None


class ExtractionResult(BaseModel):
    status: Literal["extracted", "needs_review"]
    pages: list[ExtractedPage] = Field(min_length=1)


def call_extractor(content: bytes, media_type: str) -> ExtractionResult:
    base_url = os.getenv("AI_SERVICE_URL", "http://ai-service:8081").rstrip("/")
    request = Request(
        f"{base_url}/extract",
        data=content,
        headers={"Content-Type": media_type},
        method="POST",
    )

    try:
        with urlopen(request, timeout=180) as response:
            return ExtractionResult.model_validate_json(response.read())
    except HTTPError as error:
        if error.code in (413, 415, 422):
            raise HTTPException(error.code, "This document could not be extracted.") from None
        if error.code == 504:
            raise HTTPException(504, "Document extraction timed out.") from None
        raise HTTPException(502, "The extraction service returned an error.") from None
    except TimeoutError:
        raise HTTPException(504, "Document extraction timed out.") from None
    except URLError:
        raise HTTPException(503, "The extraction service is unavailable.") from None
    except ValidationError:
        raise HTTPException(502, "The extraction service returned invalid page data.") from None


def extract_review_document(document_id: int, reviewer_id: int) -> ExtractionResult:
    try:
        with psycopg.connect(connect_timeout=3) as connection:
            row = connection.execute(
                """
                SELECT d.media_type, e.status, e.pages
                FROM documents AS d
                LEFT JOIN document_extractions AS e ON e.document_id = d.id
                WHERE d.id = %s AND d.applicant_id <> %s
                """,
                (document_id, reviewer_id),
            ).fetchone()

            if row is None:
                raise HTTPException(404, "Document not found.")

            media_type, saved_status, saved_pages = row
            if saved_status is not None:
                return ExtractionResult(status=saved_status, pages=saved_pages)

            upload = connection.execute(
                """
                SELECT pdf_content FROM documents
                WHERE id = %s AND applicant_id <> %s
                """,
                (document_id, reviewer_id),
            ).fetchone()

            if upload is None:
                raise HTTPException(404, "Document not found.")

        # Release the database connection while the service processes the file.
        result = call_extractor(bytes(upload[0]), media_type)
        pages = [page.model_dump() for page in result.pages]

        with psycopg.connect(connect_timeout=3) as connection:
            connection.execute(
                """
                INSERT INTO document_extractions (document_id, status, pages)
                SELECT id, %s, %s FROM documents
                WHERE id = %s AND applicant_id <> %s
                ON CONFLICT (document_id) DO NOTHING
                """,
                (result.status, Jsonb(pages), document_id, reviewer_id),
            )

            # Concurrent requests return the same stored result.
            saved = connection.execute(
                """
                SELECT e.status, e.pages
                FROM document_extractions AS e
                JOIN documents AS d ON d.id = e.document_id
                WHERE d.id = %s AND d.applicant_id <> %s
                """,
                (document_id, reviewer_id),
            ).fetchone()

            if saved is None:
                raise HTTPException(404, "Document not found.")

        return ExtractionResult(status=saved[0], pages=saved[1])

    except psycopg.OperationalError:
        raise HTTPException(503, "The application database is unavailable.") from None