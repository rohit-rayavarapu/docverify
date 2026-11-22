import sqlite3

import pytest
from fastapi import HTTPException

from app import reviewer
from app.registration import RegisteredUser


@pytest.fixture
def database(monkeypatch):
    db = sqlite3.connect(":memory:")
    db.create_function("now", 0, lambda: "2026-01-02")
    db.executescript("""
        CREATE TABLE users(id, full_name, email);
        CREATE TABLE applications(id, title);
        CREATE TABLE documents(id, applicant_id, original_filename, submitted_at,
            review_status, application_id, document_type, notes, pdf_content,
            media_type, reviewed_by, reviewed_at);
        INSERT INTO users VALUES (1,'Alex','alex@example.com'),(2,'Sam','sam@example.com');
        INSERT INTO applications VALUES (10,'Example');
        INSERT INTO documents VALUES
            (1,1,'alex.pdf','2026-01-01T00:00:00','Pending',10,'Other','',X'01','application/pdf',NULL,NULL),
            (2,2,'sam.pdf','2026-01-01T00:00:00','Pending',10,'Other','',X'02','application/pdf',NULL,NULL);
    """)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return db.__exit__(*args)

        def execute(self, sql, params):
            return db.execute(sql.replace("%s", "?"), params)

    monkeypatch.setattr(reviewer.psycopg, "connect", lambda **kwargs: Connection())
    yield db
    db.close()


@pytest.mark.parametrize("decision", ["Approved", "Rejected"])
def test_reviewer_must_be_independent(database, decision):
    alex = RegisteredUser(id=1, email="alex@example.com", role="Reviewer")
    assert [doc.id for doc in reviewer.list_pending_documents(alex)] == [2]
    with pytest.raises(HTTPException) as own_file:
        reviewer.open_document_file(1, alex)
    assert own_file.value.status_code == 404
    request = reviewer.ReviewDecision(decision=decision)
    with pytest.raises(HTTPException) as own_decision:
        reviewer.record_decision(1, request, alex)
    assert own_decision.value.status_code == 404
    assert database.execute("SELECT review_status, reviewed_by FROM documents WHERE id=1").fetchone() == ("Pending", None)
    assert reviewer.open_document_file(2, alex).body == bytes([2])
    assert reviewer.record_decision(2, request, alex).review_status == decision
    with pytest.raises(HTTPException) as repeat:
        reviewer.record_decision(2, request, alex)
    assert repeat.value.status_code == 409
