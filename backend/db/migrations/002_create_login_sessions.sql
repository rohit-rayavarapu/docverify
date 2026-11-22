BEGIN;

CREATE TABLE login_sessions (
    token_hash text PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL
);

COMMIT;