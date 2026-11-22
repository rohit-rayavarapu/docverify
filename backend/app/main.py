import psycopg
from fastapi import FastAPI, HTTPException

from .admin import router as admin_router
from .login import router as login_router
from .registration import router as registration_router
from .reviewer import router as reviewer_router
from .documents import router as documents_router


app = FastAPI(title="DocVerify AI")

app.include_router(registration_router)
app.include_router(login_router)
app.include_router(reviewer_router)
app.include_router(admin_router)
app.include_router(documents_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "DocVerify AI"}


@app.get("/api/health/db")
def database_health():
    try:
        with psycopg.connect(connect_timeout=3) as connection:
            connection.execute("SELECT 1").fetchone()
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Database unavailable") from None

    return {"status": "ok", "database": "postgresql"}