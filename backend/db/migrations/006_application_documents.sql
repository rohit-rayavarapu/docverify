BEGIN;
CREATE TABLE applications (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    applicant_id bigint NOT NULL REFERENCES users(id),
    title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 120),
    UNIQUE (applicant_id, title),
    UNIQUE (id, applicant_id)
);
ALTER TABLE documents
    ADD COLUMN application_id bigint,
    ADD COLUMN document_type text NOT NULL DEFAULT 'Other',
    ADD COLUMN notes text NOT NULL DEFAULT '',
    ADD COLUMN media_type text NOT NULL DEFAULT 'application/pdf'
        CHECK (media_type IN ('application/pdf', 'image/jpeg', 'image/png')),
    ADD FOREIGN KEY (application_id, applicant_id) REFERENCES applications(id, applicant_id);
INSERT INTO applications (applicant_id, title)
SELECT DISTINCT applicant_id, 'My application' FROM documents;
UPDATE documents d SET application_id = a.id
FROM applications a WHERE a.applicant_id = d.applicant_id;
ALTER TABLE documents ALTER COLUMN application_id SET NOT NULL;
COMMIT;
