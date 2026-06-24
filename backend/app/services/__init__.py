"""Backend service modules (OCR pipeline, jobs, facts, PDF, NCBI cache).

These modules intentionally import heavy dependencies (``torch`` /
``transformers``) lazily, *inside* functions, so the FastAPI service can start
and the non-OCR endpoints keep working on hosts where the ML stack is not
installed — mirroring the pattern in ``app.utils.device``.
"""
