FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY extract.py service.py ./

ENV XDG_CACHE_HOME=/tmp
USER nobody

CMD ["python", "-m", "uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8081"]