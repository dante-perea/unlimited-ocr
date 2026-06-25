# Backend image for the Unlimited-OCR FastAPI service.
#
# Deploys in MOCK/offline mode by default (OCR_MOCK=1 via fly.toml): the NCBI
# search + PDF download endpoints are fully real, and OCR returns canned output
# so the whole flow is demoable without a CUDA GPU or the multi-GB ML stack.
# To run REAL OCR on a GPU machine, add requirements-ocr.txt and unset OCR_MOCK.
FROM python:3.12-slim

WORKDIR /app

# Core dependencies only (fastapi, uvicorn, httpx, pymupdf, pydantic).
# PyMuPDF ships self-contained manylinux wheels — no extra system libs needed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code. vendor/ and tests/ are excluded via .dockerignore.
COPY app/ ./app/

# Writable data directory for the PMC PDF cache.
RUN mkdir -p /app/data/pdfs

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
