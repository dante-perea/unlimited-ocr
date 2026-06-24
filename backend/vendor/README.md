# Vendored dependencies

## Unlimited-OCR

[Baidu Unlimited-OCR](https://github.com/baidu/Unlimited-OCR) is vendored here as
a git submodule at `Unlimited-OCR/`.

### Getting the source

If you cloned this repo **without** `--recurse-submodules`, fetch the code with:

```bash
git submodule update --init --recursive
```

(Or from the repo root: `make submodules`.)

> The git submodule contains **code only** — no model weights. Weights are
> downloaded separately from HuggingFace the first time the OCR pipeline runs
> (a later task). See the root `README.md` **HARDWARE NOTE**.

### Installing the OCR Python dependencies

The heavy ML stack (torch / transformers / accelerate) is intentionally kept out
of `backend/requirements.txt`. Install it on an OCR-capable host:

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-ocr.txt
# then follow Unlimited-OCR's own install steps:
#   pip install -r vendor/Unlimited-OCR/requirements.txt   # if present
```

### Model weights (do NOT download during foundation setup)

Weights are large and require a CUDA / bfloat16-capable GPU for real throughput.
The OCR task will document the exact `huggingface-cli download` / `from_pretrained`
step and cache them under `HF_HOME` (see `backend/.env.example`).
