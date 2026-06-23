"""API routers.

Each feature area lives in its own module and exposes an ``APIRouter`` named
``router``. ``app.main`` mounts them. New feature routers (``ncbi``, ``ocr``)
can be added here and wired in ``app.main`` without restructuring anything.
"""
