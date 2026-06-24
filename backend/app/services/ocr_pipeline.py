"""OCR pipeline: render PDF → run Unlimited-OCR → normalize per-page text.

This orchestrates the steps that turn a source PDF into
:class:`~app.schemas.ocr.OcrResult`:

1. :func:`app.services.pdf.pdf_to_images` — rasterize each page to PNG (PyMuPDF).
2. ``model.infer`` / ``model.infer_multi`` — run Unlimited-OCR over the page
   images, using a document-parsing prompt (per the upstream README).
3. Normalize the (loosely specified) model output to a per-page list[str].

The README documents ``model.infer(...)`` for a single image and
``model.infer_multi(...)`` for multi-page/PDF, both with ``save_results=True``
writing markdown to ``output_path``. The **return value** of these methods is not
documented in the upstream README, so :func:`_to_page_texts` normalizes whatever
the model returns (a str, a list[str], an object with ``.text``, etc.) and, as a
fallback, reads the saved ``*.md`` files from ``output_path``. This makes the
pipeline robust to either contract.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

from app.config import Settings
from app.schemas.ocr import OcrPage, OcrResult
from app.services.facts import extract_facts
from app.services.model_types import ModelBundle
from app.services.pdf import pdf_to_images

logger = logging.getLogger(__name__)

# Document-parsing prompts, verbatim from the upstream README:
#   single image : "<image>document parsing."
#   multi page   : "<image>Multi page parsing."
SINGLE_IMAGE_PROMPT = "<image>document parsing."
MULTI_PAGE_PROMPT = "<image>Multi page parsing."

# Inference hyperparameters from the upstream README (shared by both paths).
_INFER_KWARGS = dict(max_length=32768, no_repeat_ngram_size=35, save_results=True)
# Multi-page (base) uses image_size=1024 and ngram_window=1024 per the README.
_MULTI_KWARGS = dict(image_size=1024, ngram_window=1024)


def run_ocr(
    pdf_path: str | os.PathLike[str],
    model_bundle: ModelBundle,
    *,
    settings: Settings,
    pmcid: str | None = None,
) -> OcrResult:
    """Run the full OCR pipeline on a PDF and return the normalized result.

    ``model_bundle`` is a ``(model, tokenizer, device)`` triple from
    :func:`app.services.ocr_model.get_model`. Importing this function never
    imports torch/transformers — they stay lazy inside the loader.
    """
    model, tokenizer, device = model_bundle
    is_mock = bool(getattr(model, "is_mock", False)) or device == "mock"

    dpi = settings.ocr_pdf_dpi
    image_paths = pdf_to_images(pdf_path, dpi=dpi)

    # Honor the page cap.
    if settings.ocr_max_pages and len(image_paths) > settings.ocr_max_pages:
        logger.warning(
            "PDF has %d pages; capping to %d (OCR_MAX_PAGES).",
            len(image_paths),
            settings.ocr_max_pages,
        )
        image_paths = image_paths[: settings.ocr_max_pages]

    with tempfile.TemporaryDirectory(prefix="ocr_out_") as output_path:
        page_texts = _infer_pages(
            model, tokenizer, image_paths, output_path=output_path, is_mock=is_mock
        )

    pages = [OcrPage(page_index=i, text=t) for i, t in enumerate(page_texts)]
    full_text = "\n\n".join(t for t in page_texts if t and t.strip())

    facts = extract_facts(full_text, pmcid=pmcid, extractor=settings.facts_extractor)

    return OcrResult(
        pages=pages,
        full_text=full_text,
        facts=facts,
        n_pages=len(pages),
        device=device,
        mock=is_mock,
    )


def _infer_pages(
    model: Any,
    tokenizer: Any,
    image_paths: list[str],
    *,
    output_path: str,
    is_mock: bool,
) -> list[str]:
    """Run the model and normalize output to a per-page list[str].

    Single page → ``model.infer``; multiple pages → ``model.infer_multi``.
    """
    if not image_paths:
        return []

    if len(image_paths) == 1:
        result = model.infer(
            tokenizer,
            prompt=SINGLE_IMAGE_PROMPT,
            image_file=image_paths[0],
            output_path=output_path,
            # Single-image "gundam" config per the README (base_size/image_size/crop_mode).
            base_size=1024,
            image_size=640,
            crop_mode=True,
            ngram_window=128,
            **_INFER_KWARGS,
        )
        return _to_page_texts(result, image_paths, output_path, expected=1)

    result = model.infer_multi(
        tokenizer,
        prompt=MULTI_PAGE_PROMPT,
        image_files=image_paths,
        output_path=output_path,
        **_INFER_KWARGS,
        **_MULTI_KWARGS,
    )
    return _to_page_texts(result, image_paths, output_path, expected=len(image_paths))
def _to_page_texts(
    result: Any,
    image_paths: list[str],
    output_path: str,
    *,
    expected: int,
) -> list[str]:
    """Normalize the (loosely documented) model return value into list[str].

    Handles: a plain str, a list/tuple of str, an object with ``.text`` /
    ``.outputs[0].text`` (HF generation-style objects), or ``None`` (fall back to
    saved markdown files). Always returns exactly ``expected`` entries.
    """
    texts: list[str] = []

    if isinstance(result, str):
        texts = [result]
    elif isinstance(result, (list, tuple)):
        texts = [str(x) if not isinstance(x, str) else x for x in result]
        texts = [t for t in texts if t is not None]
    elif result is not None:
        single = getattr(result, "text", None)
        if isinstance(single, str):
            texts = [single]
        elif getattr(result, "outputs", None):
            out = []
            for o in result.outputs:
                t = getattr(o, "text", None)
                if isinstance(t, str):
                    out.append(t)
            texts = out

    # Pad/trim to the expected page count; fill blanks from saved markdown files.
    if len(texts) < expected:
        texts.extend([""] * (expected - len(texts)))
        saved = _read_saved_markdown(output_path)
        for i, md in enumerate(saved[:expected]):
            if i < len(texts) and not texts[i].strip():
                texts[i] = md
    texts = texts[:expected]

    # Final fallback: if a page still has no text, try the saved file for it.
    if any(not t.strip() for t in texts):
        saved = _read_saved_markdown(output_path)
        for i in range(len(texts)):
            if not texts[i].strip() and i < len(saved):
                texts[i] = saved[i]

    return texts


def _read_saved_markdown(output_path: str) -> list[str]:
    """Read ``*.md`` files written by the model (save_results=True), sorted."""
    from pathlib import Path

    directory = Path(output_path)
    if not directory.is_dir():
        return []
    contents: list[str] = []
    for md in sorted(directory.glob("*.md")):
        try:
            contents.append(md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            contents.append("")
    return contents
