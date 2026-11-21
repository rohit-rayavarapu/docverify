from fastapi import FastAPI

app = FastAPI(title="DocVerify AI")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "DocVerify AI"}