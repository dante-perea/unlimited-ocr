# NCBI Papers × Unlimited-OCR

A **local** web app to browse free-access biomedical papers and extract their
full text + structured facts with [Baidu Unlimited-OCR](https://github.com/baidu/Unlimited-OCR),
running entirely on your own hardware.

**End-to-end flow:** search PubMed Central Open Access → pick a paper → the app
downloads its PDF → Unlimited-OCR runs locally → the UI shows the extracted text
and facts.

> The full flow is implemented and demoable **without a GPU**. Set `OCR_MOCK=1`
> and the OCR step returns canned, realistic output (full text + a populated
> Facts panel), so you can drive the whole UI end-to-end on any machine. See
> [Using the app](#using-the-app-end-to-end-flow).

---

## Architecture

```
┌──────────────────────────────┐         ┌────────────────────────────────────┐
│  frontend/  (Next.js 16)      │  HTTP   │  backend/  (FastAPI, Python 3.12)  │
│  App Router · TS · Tailwind   │ ──────► │                                    │
│                               │  CORS   │  app/main.py    app factory + CORS │
│  src/lib/api.ts  ── typed ────┼────────►│  routers/health.py   GET /health   │
│      client (NEXT_PUBLIC_     │         │  routers/ncbi.py   search/fetch/pdf │
│      API_BASE_URL)            │         │  routers/ocr.py    run + status     │
│  src/app/page.tsx  full flow  │         │  utils/device.py  cuda│mps│cpu      │
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
│   │   ├── routers/           # health.py + ncbi.py (search/fetch) + ocr.py (run/status)
│   │   └── utils/device.py    # cuda → mps → cpu detection (+ logging)
│   ├── vendor/Unlimited-OCR/  # git submodule (code only)
│   ├── requirements.txt       # core API deps (pinned)
│   ├── requirements-ocr.txt   # heavy ML deps (torch/transformers) — install on a GPU host
│   └── .env.example
├── frontend/
│   ├── src/lib/api.ts         # typed backend client
│   ├── src/app/page.tsx       # full flow: search → select → results (components/ + lib/markdown.tsx)
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

The page drives the full flow (search → select → results) against the backend.
A small status pill in the header shows backend reachability + the resolved
compute device. CORS for `http://localhost:3000` is enabled by default
(configure via `CORS_ORIGINS` in `backend/.env`).

> **Tip — demo without a GPU:** start the backend with `OCR_MOCK=1` so the OCR
> step returns canned, realistic output. The whole UI flow then works on any
> machine (see [Using the app](#using-the-app-end-to-end-flow)).

---

## Using the app (end-to-end flow)

The web UI is a single-page, three-step experience (with a progress indicator at
the top). It talks to the backend through the typed client in
`frontend/src/lib/api.ts`.

1. **Search** — type a free-text query (Entrez syntax) in the search box and hit
   **Search**. It calls `GET /ncbi/search` against the PMC Open Access subset and
   renders a paginated list: title, authors, journal, year, and an abstract
   snippet. Use **Prev / Next** to page through results (try the example chips on
   a first visit).

2. **Select** — click a paper to open its detail view (metadata + an abstract).
   Press **Run OCR**. The app then:
   - `POST /ncbi/fetch/{pmcid}` — downloads the article's PDF into the shared
     local cache (direct PDF, or extracted from the PMC OA `.tar.gz` package),
   - `POST /ocr/run` — enqueues an async OCR job and gets a `job_id`,
   - polls `GET /ocr/status/{job_id}` every second, showing a live
     **Fetch → Queue → Run → Done** progress indicator (OCR is slow).

3. **Results** — once the job completes you get three tabs plus actions:
   - **Full text** — the extracted document rendered as Markdown (headings,
     lists, tables, code).
   - **Pages** — a page-by-page view with prev/next navigation.
   - **Facts** — a structured panel: title, authors, abstract, key findings,
     entities, and detected tables, produced by the backend's fact extractor.
   - **Copy text** copies the full extracted text; **Download JSON** saves the
     full OCR result (`{ paper, ocr }`) as `{pmcid}-ocr.json`.

Loading, error, and empty states are handled throughout (search failures,
backend offline, "no PDF available", OCR failures, empty pages/facts).

### Running the full flow locally

```bash
# Terminal 1 — backend (mock OCR so no GPU is needed)
cd backend
source .venv/bin/activate
OCR_MOCK=1 uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev        # http://localhost:3000
```

Open <http://localhost:3000>, search for e.g. `mitochondrial dynamics`, pick a
paper, and click **Run OCR**. With `OCR_MOCK=1` the result is canned (a "mock
OCR" badge is shown); the PDF fetch + page rendering still use a real downloaded
PDF, so the page count reflects the actual document.

### Mock / offline OCR mode

Set `OCR_MOCK=1` (or `OCR_MOCK=true`) to skip loading the real
CUDA/bfloat16 model and return canned Markdown instead. The canned content is
crafted to exercise the fact extractor (title, authors, abstract, key findings,
entities, tables, DOI, PMCID), so the **Facts** panel is populated and the UI can
be demoed end-to-end without torch or model weights. Real OCR requires an
NVIDIA CUDA host — see the **HARDWARE NOTE** below.

### Backend API summary

| Method & path                  | Purpose                                                        |
| ------------------------------ | ------------------------------------------------------------- |
| `GET  /health`                 | Liveness + resolved compute device                            |
| `GET  /ncbi/search`            | Search PMC Open Access (query, page, page_size)               |
| `GET  /ncbi/paper/{pmcid}`     | Metadata + OA download links for a paper                      |
| `POST /ncbi/fetch/{pmcid}`     | Download/cache the PDF (the OCR step reads this cache)        |
| `POST /ocr/run`                | Enqueue an OCR job (`{pmcid}` or `pdf_path`); returns job id  |
| `GET  /ocr/status/{job_id}`    | Poll a job (queued → running → completed/failed + result)     |

Interactive docs are at <http://localhost:8000/docs>.

---

## Configuration

| App      | File                  | Key                        | Purpose                                   |
| -------- | --------------------- | -------------------------- | ----------------------------------------- |
| backend  | `backend/.env`        | `CORS_ORIGINS`             | Comma-separated allowed origins           |
| backend  | `backend/.env`        | `DEVICE`                   | Force `cuda`/`mps`/`cpu` (blank = auto)   |
| backend  | `backend/.env`        | `OCR_MOCK`                 | `1` = canned OCR output (no GPU needed)   |
| backend  | `backend/.env`        | `NCBI_API_KEY`             | Optional; raises the E-utilities rate limit |
| backend  | `backend/.env`        | `DATA_DIR`, `PDF_CACHE_DIR`, `HF_HOME` | Download / cache / weights locations |
| frontend | `frontend/.env.local` | `NEXT_PUBLIC_API_BASE_URL` | Backend base URL (inlined at build time)  |

See `*/.env.example` for the full list.

---

## Unlimited-OCR (vendored)

The OCR engine is a git submodule at `backend/vendor/Unlimited-OCR`
(**code only — no model weights**). The heavy Python stack is intentionally
*not* installed by `make setup`. When you're ready to run real OCR on a capable
host:

```bash
make backend-ocr-deps     # torch, transformers, accelerate, ...
# Weights download from HuggingFace (baidu/Unlimited-OCR) on first run — the
# OCR task will wire this up. They are large; expect a multi-GB download.
```

See `backend/vendor/README.md` for details.

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
- [x] NCBI / PMC Open Access search + metadata + PDF fetch (`/ncbi`)
- [x] OCR pipeline + async jobs + structured-fact extraction (`/ocr`) + `OCR_MOCK` mode
- [x] Next.js full flow UI: search → select → results (text/pages/facts) + copy/download
- [x] Unlimited-OCR vendored as a submodule
```
