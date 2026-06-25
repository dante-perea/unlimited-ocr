/**
 * Typed client for the FastAPI backend.
 *
 * The base URL comes from NEXT_PUBLIC_API_BASE_URL (see .env.example) and
 * falls back to the local dev server. Covers the full flow:
 *
 *   - NCBI:  search / paper detail / fetch PDF
 *   - OCR:   run (async) / poll status
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  device: string;
}

// --------------------------------------------------------------------------- //
// NCBI / PMC Open Access
// --------------------------------------------------------------------------- //

export interface Author {
  name: string;
  initials?: string;
}

export interface PaperSummary {
  pmcid: string;
  pmid?: string;
  doi?: string;
  title?: string;
  authors?: Author[];
  journal?: string;
  year?: string;
  abstract_snippet?: string;
}

export interface SearchResponse {
  query: string;
  page: number;
  page_size: number;
  total_results: number;
  total_pages: number;
  results: PaperSummary[];
}

export interface DownloadLink {
  format: "pdf" | "tgz";
  url: string;
  updated?: string;
}

export interface PaperDetail {
  pmcid: string;
  pmid?: string;
  doi?: string;
  title?: string;
  authors?: Author[];
  journal?: string;
  year?: string;
  license?: string;
  citation?: string;
  retracted?: boolean;
  abstract_snippet?: string;
  downloads?: DownloadLink[];
}

export type FetchStatus = "cached" | "downloaded" | "extracted" | "unavailable";
export type FetchSourceFormat = "pdf" | "tgz" | "none";

export interface FetchResponse {
  pmcid: string;
  status: FetchStatus;
  source_format: FetchSourceFormat;
  pdf_path?: string | null;
  filename?: string | null;
  size_bytes?: number | null;
  message?: string;
}

// --------------------------------------------------------------------------- //
// OCR pipeline
// --------------------------------------------------------------------------- //

export interface OcrRunRequest {
  pmcid?: string;
  pdf_path?: string;
  dpi?: number;
}

export interface OcrRunAccepted {
  job_id: string;
  status: string;
  poll: string;
}

export interface OcrPage {
  page_index: number;
  text: string;
}

export interface Facts {
  title?: string | null;
  authors?: string[];
  abstract?: string | null;
  key_findings?: string[];
  entities?: string[];
  tables?: string[];
  doi?: string | null;
  pmcid?: string | null;
  extractor?: string;
}

export interface OcrResult {
  pages: OcrPage[];
  full_text: string;
  facts: Facts;
  n_pages: number;
  device: string;
  mock?: boolean;
}

export type OcrJobState = "queued" | "running" | "completed" | "failed";

export interface OcrJobStatus {
  job_id: string;
  status: OcrJobState;
  error?: string | null;
  error_code?: string | null;
  result?: OcrResult | null;
}

// --------------------------------------------------------------------------- //
// Client
// --------------------------------------------------------------------------- //

export class ApiError extends Error {
  detail: unknown;
  constructor(message: string, readonly status?: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.detail = detail;
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
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = undefined;
    }
    const msg =
      (detail && typeof detail === "object" && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : undefined) ?? `Request to ${path} failed (${res.status})`;
    throw new ApiError(msg, res.status, detail);
  }
  return (await res.json()) as T;
}

function withQuery(params: Record<string, string | number | boolean | undefined>) {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") usp.set(k, String(v));
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  baseUrl: API_BASE_URL,

  /** Backend liveness probe. */
  health: () => request<HealthResponse>("/health"),

  // -- NCBI ----------------------------------------------------------------
  searchPapers: (opts: {
    query: string;
    page?: number;
    pageSize?: number;
  }) =>
    request<SearchResponse>(
      `/ncbi/search${withQuery({
        query: opts.query,
        page: opts.page,
        page_size: opts.pageSize,
      })}`,
    ),

  getPaper: (pmcid: string) => request<PaperDetail>(`/ncbi/paper/${pmcid}`),

  fetchPaper: (pmcid: string, opts?: { force?: boolean }) =>
    request<FetchResponse>(
      `/ncbi/fetch/${pmcid}${withQuery({ force: opts?.force })}`,
      { method: "POST" },
    ),

  // -- OCR -----------------------------------------------------------------
  runOcr: (body: OcrRunRequest) =>
    request<OcrRunAccepted>("/ocr/run", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getOcrStatus: (jobId: string) =>
    request<OcrJobStatus>(`/ocr/status/${jobId}`),
};

