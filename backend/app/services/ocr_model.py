"""Unlimited-OCR model loader (lazy singleton).

Loads ``baidu/Unlimited-OCR`` via transformers ``AutoModel``/``AutoTokenizer``
with ``trust_remote_code=True`` and ``torch.bfloat16`` (per the upstream README),
on the device chosen by :func:`app.utils.device.detect_device`
(``cuda`` > ``mps`` > ``cpu``).

The model is heavy (multi-GB) and CUDA-first. It is therefore:

* loaded **once** (module-level singleton), the first time it is needed;
* loaded **lazily** — ``torch`` / ``transformers`` are imported inside the loader
  so importing this module never requires them; and
* replaceable by a :class:`MockOcrModel` when ``settings.ocr_mock`` is set, so the
  frontend can be developed without a GPU.

On non-CUDA hosts the upstream model code frequently fails (it was built/tested
on NVIDIA CUDA + bfloat16). When that happens we raise a single, clearly-worded
:class:`GpuRequirementError` explaining the requirement instead of a cryptic
traceback.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.config import Settings
from app.utils.device import detect_device

logger = logging.getLogger(__name__)

# Module-level singleton tuple: (model, tokenizer, device). ``device`` is one of
# "cuda" / "mps" / "cpu" for the real model, or "mock" in mock mode.
_model_singleton: tuple[Any, Any, str] | None = None

MODEL_NAME = "baidu/Unlimited-OCR"


class GpuRequirementError(RuntimeError):
    """Raised when the model cannot run on the current (non-CUDA) host.

    The message is actionable: it states what happened, what is required, and how
    to proceed (run on CUDA, or enable mock mode).
    """

    error_code = "gpu_required"


def _gpu_required_message(device: str, cause: Exception | str) -> str:
    reason = (
        str(cause).strip().splitlines()[-1]
        if str(cause).strip()
        else "the model's custom code requires an NVIDIA CUDA GPU"
    )
    return (
        f"Unlimited-OCR could not run on this host (detected device: {device!r}). "
        f"{reason}. The upstream model is a CUDA + bfloat16 vision-language model "
        "tested on NVIDIA GPUs (Python 3.12 + CUDA 12.9); its custom inference code "
        "is CUDA-first and is not expected to work on Apple Silicon MPS/CPU.\n\n"
        "To run REAL OCR, run this backend on an NVIDIA CUDA host:\n"
        "  1. pip install -r requirements-ocr.txt   (torch==2.10.0, transformers==4.57.1, ...)\n"
        "  2. export HF_HOME=<a writable cache dir>  # weights download on first run\n"
        "  3. start the backend there and point the frontend at it (NEXT_PUBLIC_API_BASE_URL).\n\n"
        "To keep building the FRONTEND without a GPU, enable mock/offline mode:\n"
        "  export OCR_MOCK=1   # canned OCR output; no torch/weights required."
    )


def _gpu_required_error(device: str, cause: Exception | str) -> GpuRequirementError:
    return GpuRequirementError(_gpu_required_message(device, cause))


def _looks_like_cuda_error(exc: BaseException) -> bool:
    """Heuristic: did a RuntimeError come from missing CUDA / unsupported device?"""
    text = str(exc).lower()
    needles = (
        "cuda",
        "device-side assert",
        "not implemented for",  # e.g. op not implemented for 'Half'/'BFloat16'
        "placeholder storage has not been allocated",
        "expected all tensors to be on the same device",
        "mps",  # MPS-specific fallbacks
    )
    return any(n in text for n in needles)


def get_model(settings: Settings) -> tuple[Any, Any, str]:
    """Return the ``(model, tokenizer, device)`` singleton, loading it if needed.

    When ``settings.ocr_mock`` is true, a :class:`MockOcrModel` is returned with
    ``device == "mock"`` and no tokenizer — no torch/transformers/weights needed.
    """
    global _model_singleton
    if _model_singleton is not None:
        return _model_singleton

    if settings.ocr_mock:
        logger.warning("OCR_MOCK=1 — returning canned OCR output (no model loaded).")
        _model_singleton = (MockOcrModel(), None, "mock")
        return _model_singleton

    device = detect_device(settings.device)
    model, tokenizer = _load_real_model(settings.ocr_model_name, device)
    _model_singleton = (model, tokenizer, device)
    return _model_singleton


def reset_model() -> None:
    """Clear the cached singleton (used by tests to force a fresh load)."""
    global _model_singleton
    _model_singleton = None


def _load_real_model(model_name: str, device: str) -> tuple[Any, Any]:
    """Load the real Unlimited-OCR model + tokenizer (imports torch lazily)."""
    try:
        import torch  # noqa: F401  (imported for the dtype below)
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:  # pragma: no cover - depends on host
        raise GpuRequirementError(
            "The OCR ML stack (torch/transformers) is not installed. "
            "Install requirements-ocr.txt on a CUDA host, or set OCR_MOCK=1."
        ) from exc

    logger.info("Loading Unlimited-OCR model %r on device %r ...", model_name, device)
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        model = AutoModel.from_pretrained(
            model_name,
            trust_remote_code=True,
            use_safetensors=True,
            torch_dtype=torch.bfloat16,
        )
        model = model.eval()
        # README calls `.cuda()`; `.to(device)` is equivalent for cuda and the
        # only way to attempt mps/cpu. On non-CUDA hosts this (or the first infer)
        # is where CUDA-only code typically fails.
        model = model.to(device)
    except RuntimeError as exc:
        if device != "cuda" and _looks_like_cuda_error(exc):
            raise _gpu_required_error(device, exc) from exc
        raise
    except Exception as exc:
        # The remote modeling code occasionally raises non-RuntimeError CUDA issues.
        if device != "cuda" and _looks_like_cuda_error(exc):
            raise _gpu_required_error(device, exc) from exc
        raise

    logger.info("Unlimited-OCR loaded on %r.", device)
    return model, tokenizer


# --------------------------------------------------------------------------- #
# Mock model (OCR_MOCK=1)
# --------------------------------------------------------------------------- #
# Canned "paper" content used in mock mode. Concatenated, it exercises the
# heuristic facts extractor (title / authors / abstract / findings / entities /
# table / DOI / PMCID) so the frontend can show a realistic result without a GPU.
_CANNED_PAGE_0 = """# Mitochondrial Dynamics Regulate Longevity in Caenorhabditis elegans

Alice B. Researcher, Bob Q. Scientist, Carol Lee
Department of Biology, Example University, Cambridge, MA

## Abstract

Mitochondrial dynamics balance fission and fusion to maintain cellular energy homeostasis. We show that reducing mitochondrial fission extends lifespan in the nematode C. elegans. Our results demonstrate a 35% increase in mean lifespan for fission-deficient mutants.

| Genotype | Mean lifespan (days) | n |
|---|---|---|
| wild-type (N2) | 18.2 | 120 |
| drp-1(ad817) | 24.6 | 118 |
| fis1(tm1867) | 23.9 | 110 |
"""

_CANNED_PAGE_1 = """## Results

We find that loss of the dynamin-related protein DRP-1 (human ortholog DNM1L) significantly increases lifespan. The transcription factor DAF-16 is required for this longevity, indicating that mitochondrial fission limits lifespan through insulin/IGF-1 signaling.

In conclusion, our findings indicate that mitochondrial fission is a druggable target for healthy ageing.

DOI: 10.1000/jexbio.2026.123456
PMCID: PMC1234567
"""

_CANNED_PAGES: list[str] = [_CANNED_PAGE_0, _CANNED_PAGE_1]


class MockOcrModel:
    """Stand-in model that returns canned markdown, used when ``OCR_MOCK=1``.

    Mirrors the subset of the real API the pipeline relies on: ``infer`` (single
    image -> str) and ``infer_multi`` (list of images -> list[str]).
    """

    is_mock = True

    def _page_text(self, image_ref: str | None, fallback_index: int) -> str:
        # Prefer a numeric hint in the filename (e.g. page_0003.png) so repeated
        # mock runs are deterministic and varied per page.
        if image_ref:
            digits = "".join(ch for ch in os.path.basename(str(image_ref)) if ch.isdigit())
            if digits:
                return _CANNED_PAGES[int(digits) % len(_CANNED_PAGES)]
        return _CANNED_PAGES[fallback_index % len(_CANNED_PAGES)]

    def infer(self, tokenizer, *, prompt, image_file, output_path, **kwargs):  # type: ignore[no-untyped-def]
        # Signature mirrors the real model.infer; we only use image_file.
        return self._page_text(image_file, 0)

    def infer_multi(self, tokenizer, *, prompt, image_files, output_path, **kwargs):  # type: ignore[no-untyped-def]
        return [self._page_text(img, i) for i, img in enumerate(image_files)]

