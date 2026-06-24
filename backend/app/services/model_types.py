"""Shared type aliases for the OCR services.

Kept tiny and dependency-free so modules can type the ``(model, tokenizer,
device)`` triple returned by :func:`app.services.ocr_model.get_model` without
forcing any heavy imports.
"""

from __future__ import annotations

from typing import Any

# (model, tokenizer, device). tokenizer is None in mock mode; device is one of
# "cuda" / "mps" / "cpu" / "mock".
ModelBundle = tuple[Any, Any, str]
