import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from extract import extract_document


app = FastAPI(title="DocVerify Extraction Service")

MAX_FILE_BYTES = 5 * 1024 * 1024

FILE_SUFFIXES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract")
async def extract_upload(request: Request):
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    suffix = FILE_SUFFIXES.get(media_type)

    if suffix is None:
        raise HTTPException(415, "Supported file types are PDF, JPEG, and PNG.")

    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / f"document{suffix}"
        size = 0

        with source.open("wb") as output:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    raise HTTPException(413, "The document exceeds the 5 MiB limit.")
                output.write(chunk)

        if size == 0:
            raise HTTPException(422, "The document is empty.")

        try:
            result = await run_in_threadpool(extract_document, source)
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "Document extraction timed out.") from None
        except (ValueError, subprocess.CalledProcessError):
            raise HTTPException(422, "The document could not be read.") from None

    return {"status": result["status"], "pages": result["pages"]}