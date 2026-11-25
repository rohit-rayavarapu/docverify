BEGIN;

CREATE TABLE document_extractions (
    document_id bigint PRIMARY KEY
        REFERENCES documents(id) ON DELETE CASCADE,

    status text NOT NULL
        CHECK (status IN ('extracted', 'needs_review')),

    pages jsonb NOT NULL
        CHECK (jsonb_typeof(pages) = 'array'),

    extracted_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;