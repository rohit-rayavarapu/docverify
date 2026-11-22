BEGIN;

-- Keep all historical submissions and review decisions. Only extra copies
-- that already existed at migration time are excluded from the unique index.
ALTER TABLE documents
    ADD COLUMN historical_duplicate boolean NOT NULL DEFAULT false;

WITH copies AS (
    SELECT id, row_number() OVER (
        PARTITION BY applicant_id, sha256(pdf_content)
        ORDER BY id
    ) AS copy_number
    FROM documents
)
UPDATE documents d
SET historical_duplicate = true
FROM copies
WHERE copies.id = d.id AND copies.copy_number > 1;

CREATE UNIQUE INDEX documents_applicant_content_unique
    ON documents (applicant_id, sha256(pdf_content))
    WHERE NOT historical_duplicate;

COMMIT;
