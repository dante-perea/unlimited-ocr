"""Compute-device detection.

Picks the best available PyTorch device: ``cuda`` if a CUDA GPU is present,
otherwise ``mps`` on Apple Silicon, otherwise ``cpu``. The chosen device is
logged so it is visible in the server logs at startup.

``torch`` is an optional/heavy dependency (installed only on an OCR-capable
host — see the README HARDWARE NOTE). When it is not installed we degrade
gracefully to ``cpu`` so the rest of the service still runs.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

VALID_DEVICES = ("cuda", "mps", "cpu")


def detect_device(preferred: str | None = None) -> str:
    """Return the compute device to use and log the choice.

    Args:
        preferred: An explicit device override ("cuda" | "mps" | "cpu"). When
            provided and valid it is honored as-is; an unknown value is ignored
            with a warning and auto-detection proceeds.

    Returns:
        One of ``"cuda"``, ``"mps"`` or ``"cpu"``.
    """
    if preferred:
        normalized = preferred.strip().lower()
        if normalized in VALID_DEVICES:
            logger.info("Using configured compute device: %s", normalized)
            return normalized
        logger.warning(
            "Ignoring unknown DEVICE override %r (expected one of %s); auto-detecting.",
            preferred,
            ", ".join(VALID_DEVICES),
        )

    try:
        import torch
    except ImportError:
        logger.warning(
            "torch is not installed; defaulting compute device to 'cpu'. "
            "Install the OCR dependencies on a CUDA host for real throughput."
        )
        return "cpu"

    if torch.cuda.is_available():
        device = "cuda"
    elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"

    logger.info("Auto-detected compute device: %s", device)
    return device
