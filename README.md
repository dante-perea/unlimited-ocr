# NCBI Papers × Unlimited-OCR

A **local** web app to browse free-access biomedical papers and extract their
full text + structured facts with [Baidu Unlimited-OCR](https://github.com/baidu/Unlimited-OCR),
running entirely on your own hardware.

**End-to-end flow (full project):** search PubMed Central Open Access → pick a
paper → the app downloads its PDF → Unlimited-OCR runs locally → the UI shows
the extracted text and facts.

> **This repository is the foundation scaffold.** The backend exposes `/health`
> today; NCBI search and the OCR pipeline are mounted as empty seams (`/ncbi`,
> `/ocr`) that later tasks fill in.

---

## Architecture

```
┌──────────────────────────────┐         ┌────────────────────────────────────┐
│  frontend/  (Next.js 16)      │  HTTP   │  backend/  (FastAPI, Python 3.12)  │
│  App Router · TS · Tailwind   │ ──────► │                                    │
│                               │  CORS   │  app/main.py    app factory + CORS │
│  src/lib/api.ts  ── typed ────┼────────►│  routers/health.py   GET /health   │
│      client (NEXT_PUBLIC_     │         │  routers/ncbi.py     /ncbi  (seam)  │
│      API_BASE_URL)            │         │  routers/ocr.py      /ocr   (seam)  │
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
│   │   ├── routers/           # health.py (live) + ncbi.py / ocr.py (empty seams)
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
| backend  | `backend/.env`        | `DATA_DIR`, `HF_HOME`      | Download/cache locations (later tasks)    |
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
- [x] Next.js placeholder + typed API client
- [x] Unlimited-OCR vendored as a submodule
- [ ] NCBI / PMC Open Access search + PDF download (`/ncbi`) — later task
- [ ] OCR pipeline + structured-fact extraction (`/ocr`) — later task
```
