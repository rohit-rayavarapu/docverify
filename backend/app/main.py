from .registration import router as registration_router


import psycopg
from fastapi import FastAPI, HTTPException

app = FastAPI(title="DocVerify AI")
app.include_router(registration_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "DocVerify AI"}


@app.get("/api/health/db")
def database_health():
    try:
        with psycopg.connect(connect_timeout=3) as connection:
            connection.execute("SELECT 1").fetchone()
    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from None

    return {"status": "ok", "database": "postgresql"}