/**
 * Tiny typed client for the FastAPI backend.
 *
 * The base URL comes from NEXT_PUBLIC_API_BASE_URL (see .env.example) and
 * falls back to the local dev server. Later tasks add `ncbi` and `ocr`
 * methods alongside `health` without changing the wiring here.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  device: string;
}

// ---- OCR endpoint contracts (mirror backend/app/schemas/ocr.py) ----

export interface OcrRunAccepted {
  job_id: string;
  status: string;
  poll: string;
}

export interface OcrRunRequest {
  pmcid?: string;
  pdf_path?: string;
  dpi?: number;
}

export interface OcrPage {
  page_index: number;
  text: string;
}

export interface Facts {
  title: string | null;
  authors: string[];
  abstract: string | null;
  key_findings: string[];
  entities: string[];
  tables: string[];
  doi: string | null;
  pmcid: string | null;
  extractor: string;
}

export interface OcrResult {
  pages: OcrPage[];
  full_text: string;
  facts: Facts;
  n_pages: number;
  device: string;
  mock: boolean;
}

export interface OcrJobStatus {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  error?: string | null;
  error_code?: string | null;
  result?: OcrResult | null;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json", ...init?.headers },
      ...init,
    });
  } catch {
    throw new ApiError(
      `Could not reach the backend at ${API_BASE_URL}. Is it running?`,
    );
  }
  if (!res.ok) {
    throw new ApiError(`Request to ${path} failed (${res.status})`, res.status);
  }
  return (await res.json()) as T;
}

export const api = {
  baseUrl: API_BASE_URL,

  /** Backend liveness probe. */
  health: () => request<HealthResponse>("/health"),

  /** Enqueue an OCR job for a PMC id or cached PDF. Returns the job id to poll. */
  runOcr: (body: OcrRunRequest) =>
    request<OcrRunAccepted>("/ocr/run", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  /** Poll an OCR job's status (and result, when completed). */
  getOcrStatus: (jobId: string) =>
    request<OcrJobStatus>(`/ocr/status/${encodeURIComponent(jobId)}`),
};
