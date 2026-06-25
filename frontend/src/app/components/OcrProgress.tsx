"use client";

import type { FetchResponse, OcrJobStatus } from "@/lib/api";
import { Spinner, Badge, formatBytes } from "./ui";

export type OcrPhase = "fetch" | "queue" | "run" | "done" | "failed";

export interface OcrProgressInfo {
  phase: OcrPhase;
  fetch?: FetchResponse | null;
  jobStatus?: OcrJobStatus | null;
  error?: string | null;
}

const ORDER: OcrPhase[] = ["fetch", "queue", "run", "done"];

function phaseState(phase: OcrPhase, target: OcrPhase): "done" | "active" | "pending" | "failed" {
  if (phase === "failed") {
    return ORDER.indexOf(target) < ORDER.indexOf("run") ? "done" : target === phase ? "failed" : "pending";
  }
  const cur = ORDER.indexOf(phase);
  const tgt = ORDER.indexOf(target);
  if (tgt < cur) return "done";
  if (tgt === cur) return "active";
  return "pending";
}

export function OcrProgress({ info }: { info: OcrProgressInfo }) {
  const steps: { key: OcrPhase; label: string; detail?: string }[] = [
    {
      key: "fetch",
      label: "Fetch PDF",
      detail: info.fetch
        ? info.fetch.status === "unavailable"
          ? "No PDF available"
          : `${info.fetch.status} · ${info.fetch.source_format} · ${formatBytes(info.fetch.size_bytes)}`
        : undefined,
    },
    { key: "queue", label: "Queue OCR job", detail: info.jobStatus?.job_id ? `job ${info.jobStatus.job_id.slice(0, 8)}` : undefined },
    { key: "run", label: "Run inference", detail: info.jobStatus?.status === "running" ? "processing pages…" : undefined },
    { key: "done", label: "Done", detail: info.phase === "done" ? "results ready" : undefined },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        {steps.map((s) => {
          const st = phaseState(info.phase, s.key);
          return (
            <div key={s.key} className="flex items-start gap-3">
              <div className="mt-0.5 flex h-6 w-6 flex-none items-center justify-center">
                {st === "active" ? (
                  <Spinner className="h-5 w-5 text-indigo-500" />
                ) : st === "done" ? (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-white">
                    <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor"><path d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0L3.3 9.7a1 1 0 1 1 1.4-1.4l3.8 3.8 6.8-6.8a1 1 0 0 1 1.4 0Z" /></svg>
                  </span>
                ) : st === "failed" ? (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-rose-500 text-white text-xs">!</span>
                ) : (
                  <span className="h-5 w-5 rounded-full border-2 border-zinc-200 dark:border-zinc-700" />
                )}
              </div>
              <div className="flex flex-col">
                <span className={`text-sm font-medium ${st === "pending" ? "text-zinc-400 dark:text-zinc-600" : "text-zinc-800 dark:text-zinc-100"}`}>
                  {s.label}
                </span>
                {s.detail && <span className="text-xs text-zinc-500 dark:text-zinc-400">{s.detail}</span>}
              </div>
            </div>
          );
        })}
      </div>

      {info.phase === "run" && (
        <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-700 dark:border-indigo-900 dark:bg-indigo-950/50 dark:text-indigo-300">
          <p className="flex items-center gap-2 font-medium">
            <Spinner className="h-4 w-4" /> Running OCR — this is slow on a GPU, and even mock mode renders every page first.
          </p>
          <p className="mt-1 text-indigo-600/80 dark:text-indigo-400/80">Polling the job every second…</p>
        </div>
      )}

      {info.fetch?.status === "unavailable" && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/50 dark:text-amber-300">
          This article has no downloadable PDF. OCR needs a PDF — try another paper.
        </div>
      )}

      {info.error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-300">
          <p className="font-medium">OCR failed</p>
          <p className="mt-1 whitespace-pre-line">{info.error}</p>
        </div>
      )}
    </div>
  );
}

export function DeviceBadge({ device, mock }: { device?: string; mock?: boolean }) {
  if (!device) return null;
  const tone = mock ? "amber" : device === "cuda" ? "emerald" : "neutral";
  return <Badge tone={tone}>device: {device}</Badge>;
}
