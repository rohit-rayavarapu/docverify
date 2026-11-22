BEGIN;

CREATE TABLE users (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text NOT NULL CHECK (email = btrim(email) AND email <> ''),
    password_hash text NOT NULL,
    role text NOT NULL DEFAULT 'Applicant'
        CHECK (role IN ('Applicant', 'Reviewer', 'Admin')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX users_email_unique ON users (lower(email));

COMMIT;