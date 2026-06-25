# Unlimited-OCR monorepo — developer tasks.
# Requires Python 3.12 and Node 18+. If `python3` is not 3.12, override:
#     make backend-setup PYTHON=python3.12

PYTHON ?= python3
BACKEND_DIR := backend
FRONTEND_DIR := frontend
VENV_BIN := $(BACKEND_DIR)/.venv/bin
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 3000

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.PHONY: setup
setup: submodules backend-setup frontend-setup ## Full setup: submodules + backend venv + frontend deps

.PHONY: submodules
submodules: ## Fetch git submodules (Unlimited-OCR source — code only, no weights)
	git submodule update --init --recursive

.PHONY: backend-setup
backend-setup: ## Create the backend venv and install core deps
	$(PYTHON) -m venv $(BACKEND_DIR)/.venv
	$(VENV_BIN)/python -m pip install --upgrade pip
	$(VENV_BIN)/pip install -r $(BACKEND_DIR)/requirements.txt
	@echo "Backend ready. Optionally: cp backend/.env.example backend/.env"

.PHONY: backend-ocr-deps
backend-ocr-deps: ## Install heavy OCR deps (torch/transformers) — CUDA host recommended
	$(VENV_BIN)/pip install -r $(BACKEND_DIR)/requirements-ocr.txt

.PHONY: test
test: ## Run backend tests (mock mode; no torch/weights required)
	cd $(BACKEND_DIR) && .venv/bin/pip install -r requirements-dev.txt -q || true
	cd $(BACKEND_DIR) && OCR_MOCK=1 .venv/bin/pytest -q

.PHONY: backend
backend: ## Run the FastAPI backend (uvicorn with reload)
	cd $(BACKEND_DIR) && .venv/bin/uvicorn app.main:app --reload --port $(BACKEND_PORT)

.PHONY: frontend-setup
frontend-setup: ## Install frontend dependencies
	cd $(FRONTEND_DIR) && npm install

.PHONY: frontend
frontend: ## Run the Next.js dev server
	cd $(FRONTEND_DIR) && npm run dev -- --port $(FRONTEND_PORT)

.PHONY: frontend-build
frontend-build: ## Production build of the frontend
	cd $(FRONTEND_DIR) && npm run build

.PHONY: dev
dev: ## How to run both apps together
	@echo "Open two terminals:  make backend   |   make frontend"
