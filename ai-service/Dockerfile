FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY extract.py .

ENV XDG_CACHE_HOME=/tmp
USER nobody

ENTRYPOINT ["python", "/app/extract.py"]