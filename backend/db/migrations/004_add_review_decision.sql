BEGIN;

ALTER TABLE documents
    ADD COLUMN reviewed_by bigint REFERENCES users(id),
    ADD COLUMN reviewed_at timestamptz;

COMMIT;