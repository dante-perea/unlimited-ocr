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

  // TODO(ncbi-task): api.searchPapers(...), api.getPaper(...), ...
  // TODO(ocr-task):  api.runOcr(...), api.getOcrJob(...), ...
};
