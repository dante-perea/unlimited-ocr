# NCBI Papers × Unlimited-OCR

A **local** web app to browse free-access biomedical papers and extract their
full text + structured facts with [Baidu Unlimited-OCR](https://github.com/baidu/Unlimited-OCR),
running entirely on your own hardware.

**End-to-end flow (full project):** search PubMed Central Open Access → pick a
paper → the app downloads its PDF → Unlimited-OCR runs locally → the UI shows
the extracted text and facts.

---

## Architecture

```
┌──────────────────────────────┐         ┌────────────────────────────────────┐
│  frontend/  (Next.js 16)      │  HTTP   │  backend/  (FastAPI, Python 3.12)  │
│  App Router · TS · Tailwind   │ ──────► │                                    │
│                               │  CORS   │  app/main.py    app factory + CORS │
│  src/lib/api.ts  ── typed ────┼────────►│  routers/health.py   GET /health   │
│      client (NEXT_PUBLIC_     │         │  routers/ncbi.py     /ncbi  (live)  │
│      API_BASE_URL)            │         │  routers/ocr.py      /ocr   (live)  │
│  src/app/page.tsx  placeholder│         │  utils/device.py  cuda│mps│cpu      │
└──────────────────────────────┘         │  config.py  pydantic-settings/.env │
                                          └──────────────┬─────────────────────┘
                                                         │ imports (later task)
                                                         ▼
                                          ┌────────────────────────────────────┐
                                          │ backend/vendor/Unlimited-OCR        │
                                          │   git submodule — code only,        │
                                          │   no weights (HuggingFace at runtime)│
                                          └────────────────────────────────────┘
```

```
unlimited-ocr/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app factory, CORS, router wiring, lifespan
│   │   ├── config.py          # pydantic-settings (.env) configuration
│   │   ├── routers/           # health.py + ncbi.py (search/paper/fetch) + ocr.py (run/status)
│   │   └── utils/device.py    # cuda → mps → cpu detection (+ logging)
│   ├── vendor/Unlimited-OCR/  # git submodule (code only)
│   ├── requirements.txt       # core API deps (pinned)
│   ├── requirements-ocr.txt   # heavy ML deps (torch/transformers) — install on a GPU host
│   └── .env.example
├── frontend/
│   ├── src/lib/api.ts         # typed backend client
│   ├── src/app/page.tsx       # placeholder page (pings /health)
│   └── .env.example
├── Makefile                   # dev tasks (setup / backend / frontend)
└── .gitignore
```

---

## Prerequisites

- **Python 3.12** (upstream OCR is tested on 3.12; override the Makefile with
  `PYTHON=python3.12` if `python3` is a different version)
- **Node.js 18+** and npm
- **git** (the repo uses a submodule)

Clone with submodules (or run `make submodules` afterward):

```bash
git clone --recurse-submodules <repo-url>
cd unlimited-ocr
```

---

## Quick start

```bash
make setup        # submodules + backend venv + frontend deps
make backend      # terminal 1 → http://localhost:8000  (GET /health)
make frontend     # terminal 2 → http://localhost:3000
```

`make help` lists every task.

### Backend (manual)

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optional — defaults work out of the box
uvicorn app.main:app --reload --port 8000
```

Verify:

```bash
curl http://localhost:8000/health
# {"status":"ok","app":"Unlimited-OCR Backend","version":"0.1.0","device":"cpu"}
```

Interactive API docs: <http://localhost:8000/docs>.

### Frontend (manual)

```bash
cd frontend
npm install
cp .env.example .env.local      # optional — defaults to http://localhost:8000
npm run dev                     # http://localhost:3000
```

The placeholder page pings the backend `/health` and shows the resolved
compute device. CORS for `http://localhost:3000` is enabled by default
(configure via `CORS_ORIGINS` in `backend/.env`).

---

## Configuration

| App      | File                  | Key                        | Purpose                                   |
| -------- | --------------------- | -------------------------- | ----------------------------------------- |
| backend  | `backend/.env`        | `CORS_ORIGINS`             | Comma-separated allowed origins           |
| backend  | `backend/.env`        | `DEVICE`                   | Force `cuda`/`mps`/`cpu` (blank = auto)   |
| backend  | `backend/.env`        | `DATA_DIR`, `HF_HOME`      | Download/cache locations                  |
| backend  | `backend/.env`        | `PDF_CACHE_DIR`            | Where fetched PMC PDFs are cached         |
| backend  | `backend/.env`        | `NCBI_API_KEY`             | Optional — raises E-utility limit 3→10/s  |
| backend  | `backend/.env`        | `NCBI_TOOL`, `NCBI_EMAIL`  | NCBI contact policy (tool/email params)   |
| backend  | `backend/.env`        | `OCR_MOCK`                 | `1` = canned OCR output, no GPU needed    |
| backend  | `backend/.env`        | `OCR_MODEL_NAME`           | HF model id (default `baidu/Unlimited-OCR`)|
| backend  | `backend/.env`        | `OCR_PDF_DPI`              | PDF→PNG rasterization DPI (default 300)   |
| backend  | `backend/.env`        | `OCR_MAX_PAGES`            | Hard page cap per run (0 = no cap)        |
| backend  | `backend/.env`        | `FACTS_EXTRACTOR`          | `heuristic` (built-in) or a registered one|
| frontend | `frontend/.env.local` | `NEXT_PUBLIC_API_BASE_URL` | Backend base URL (inlined at build time)  |

See `*/.env.example` for the full list.

---

## NCBI / PMC Open Access endpoints (`/ncbi`)

The backend can browse and fetch **free-access** papers from PubMed Central.
All upstream HTTP is async (`httpx`) and rate-limited to NCBI's policy
(3 requests/second without `NCBI_API_KEY`, 10/second with it).

```bash
# Search the PMC Open Access subset (auto-filtered to "open access[filter]").
curl 'http://localhost:8000/ncbi/search?query=CRISPR&page=1&page_size=20'
# -> { query, page, page_size, total_results, total_pages, results: [ { pmcid,
#      pmid, doi, title, authors, journal, year, abstract_snippet } ... ] }

# Metadata + full-text download URL(s) resolved via the PMC OA Web Service.
curl 'http://localhost:8000/ncbi/paper/PMC10000000'
# -> { pmcid, pmid, doi, title, authors, journal, year, license, citation,
#      retracted, abstract_snippet, downloads: [ { format: "pdf"|"tgz", url, updated } ] }

# Download/extract the PDF into the local cache (PDF_CACHE_DIR) and return its path.
curl -X POST 'http://localhost:8000/ncbi/fetch/PMC10000000'
# -> { pmcid, status: "cached"|"downloaded"|"extracted"|"unavailable",
#      source_format: "pdf"|"tgz"|"none", pdf_path, filename, size_bytes, message }
```

`POST /ncbi/fetch/{pmcid}` prefers a direct PDF link; if only a `.tar.gz` OA
package exists, it downloads it and extracts the embedded PDF. The cached PDF is
written to `<PDF_CACHE_DIR>/PMC<id>.pdf` — exactly the path the OCR pipeline will
consume by `pmcid` (see `OcrRunRequest.pmcid` in `backend/app/schemas/ocr.py`).
When no PDF is available it returns `status: "unavailable"` (200, not an error).

Backend tests (offline, with recorded fixtures):

```bash
cd backend && pip install -r requirements.txt -r requirements-dev.txt && pytest -q
```

---

## Unlimited-OCR (vendored)

The OCR engine is a git submodule at `backend/vendor/Unlimited-OCR`
(**code only — no model weights**). The heavy Python stack is intentionally
*not* installed by `make setup`. When you're ready to run real OCR on a capable
host:

```bash
make backend-ocr-deps     # torch, transformers, accelerate, ...
# Weights download from HuggingFace (baidu/Unlimited-OCR) on first run.
# They are large; expect a multi-GB download cached under HF_HOME.
```

See `backend/vendor/README.md` for details.

---

## OCR pipeline

The backend runs Unlimited-OCR **locally** as an inference service. The flow:

```
POST /ocr/run {pmcid|pdf_path}
        │  (enqueues an async job, returns {job_id, poll} immediately)
        ▼
  render PDF → PNG (PyMuPDF, DPI from OCR_PDF_DPI)
        ▼
  Unlimited-OCR  model.infer (1 page) / model.infer_multi (N pages)
        ▼
  normalize per-page text + concatenate → full_text
        ▼
  facts extraction (heuristic baseline) → {title, authors, findings, ...}
        ▼
GET /ocr/status/{job_id}  → {pages, full_text, facts, ...}
```

### Endpoints

| Method | Path | Purpose |
| ------ | ---- | ------- |
| `POST` | `/ocr/run` | Enqueue OCR for a `pmcid` (resolved against the PDF cache) or a cached `pdf_path`. Body: `{pmcid?, pdf_path?, dpi?}`. Returns `202` + `{job_id, poll}`. |
| `GET`  | `/ocr/status/{job_id}` | Poll a job. Returns `{status, result?, error?}`. `status` ∈ `queued`/`running`/`completed`/`failed`. A CUDA-requirement failure returns `422` with `{error_code: "gpu_required", message}`. |

The response `result` (when `completed`) is `{pages:[{page_index,text}], full_text, facts, n_pages, device, mock}`.

### Weights download

Weights are **not** in the repo. On first real run, `transformers` downloads
`baidu/Unlimited-OCR` from HuggingFace into `HF_HOME` (default `./.cache/huggingface`).
To pre-download:

```bash
cd backend && source .venv/bin/activate
export HF_HOME="$PWD/.cache/huggingface"        # where weights are cached
huggingface-cli download baidu/Unlimited-OCR      # multi-GB
```

The exact upstream-tested dependency pins are in `backend/requirements-ocr.txt`
(`torch==2.10.0`, `torchvision==0.25.0`, `transformers==4.57.1`, `pymupdf==1.27.2.2`, ...),
mirroring the README of the upstream repo (Python 3.12 + CUDA 12.9).

### MOCK / offline mode (no GPU)

To build/develop the frontend **without a GPU**, enable mock mode — the backend
returns canned OCR output (realistic markdown that exercises the whole pipeline
including facts extraction), so no torch/weights are needed:

```bash
cd backend && source .venv/bin/activate
export OCR_MOCK=1
uvicorn app.main:app --reload --port 8000
```

(Mock output is flagged with `device: "mock"`, `mock: true` in the result.)

### ⚠️ APPLE SILICON / non-CUDA reality

**Unlimited-OCR is a CUDA + bfloat16 vision-language model.** Upstream's
reference code loads it with `torch_dtype=torch.bfloat16` + `.cuda()`, and its
custom inference code is CUDA-first — it is **not expected to work on Apple
Silicon MPS or CPU**. If CUDA is unavailable, the loader tries MPS/CPU; if the
model code then fails, the backend returns a single **actionable** error
(`error_code: "gpu_required"`) instead of a cryptic traceback, explaining how to
run on CUDA or enable mock mode.

**To run REAL OCR, run the backend on an NVIDIA CUDA host:**

```bash
# on the GPU host:
cd backend && source .venv/bin/activate
pip install -r requirements-ocr.txt          # torch==2.10.0, transformers==4.57.1, ...
export HF_HOME=/path/to/writable/cache        # weights download on first run
uvicorn app.main:app --port 8000
# then point the frontend at it: NEXT_PUBLIC_API_BASE_URL=http://<gpu-host>:8000
```

### Tests

```bash
cd backend && source .venv/bin/activate
pytest -q            # runs in mock mode — no torch/weights required
```

The suite covers PDF→PNG rendering (PyMuPDF), the `/ocr/run` + `/ocr/status`
endpoint contract (mock model), pmcid→cached-PDF resolution, the GPU-requirement
failure path, the load-once singleton, and the heuristic facts extractor + its
extension point.

---

## ⚠️ HARDWARE NOTE — please read before expecting real OCR

**Unlimited-OCR is a CUDA / bfloat16 vision-language model.** Upstream's
reference code loads the model with `torch_dtype=torch.bfloat16` and calls
`.cuda()`, and its high-throughput path uses FlashAttention / SGLang — all of
which assume an **NVIDIA CUDA GPU**. It was tested on Python 3.12 + CUDA 12.9.

- **A CUDA GPU host is strongly recommended** for any real OCR throughput.
- **On Apple Silicon Macs, CUDA is unavailable.** This repo's device utility
  (`backend/app/utils/device.py`) detects and falls back to **MPS** (Apple GPU)
  or **CPU**, and the API runs fine for development on those devices — but the
  Unlimited-OCR *model* reference path is CUDA-first. Running it on MPS/CPU
  would require adapting the model loading (e.g. `.to("mps")`, `float16`/`float32`
  instead of `bfloat16`) and may be slow or not work out of the box.
- Practical setup: develop the UI/API on your Mac (CPU/MPS), and run the actual
  OCR workload on a CUDA GPU machine (set `NEXT_PUBLIC_API_BASE_URL` /
  `CORS_ORIGINS` accordingly so the frontend can reach that backend).

The device chosen at startup is logged and surfaced in `GET /health`.

---

## Status

- [x] Monorepo scaffold (backend + frontend)
- [x] FastAPI `/health`, CORS, settings, device detection
- [x] Next.js placeholder + typed API client
- [x] Unlimited-OCR vendored as a submodule
- [x] NCBI / PMC Open Access search + PDF download (`/ncbi`) — ESearch/ESummary/EFetch + PMC OA service; PDFs cached for the OCR task
- [x] OCR pipeline + structured-fact extraction (`/ocr`) + mock/offline mode
```
