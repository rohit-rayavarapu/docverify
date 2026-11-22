BEGIN;

CREATE TABLE documents (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    applicant_id bigint NOT NULL REFERENCES users(id),
    original_filename text NOT NULL CHECK (btrim(original_filename) <> ''),
    pdf_content bytea NOT NULL CHECK (octet_length(pdf_content) > 0),
    submitted_at timestamptz NOT NULL DEFAULT now(),
    review_status text NOT NULL DEFAULT 'Pending'
        CHECK (review_status IN ('Pending', 'Approved', 'Rejected'))
);

CREATE INDEX documents_applicant_submitted_idx
    ON documents (applicant_id, submitted_at DESC, id DESC);

COMMIT;