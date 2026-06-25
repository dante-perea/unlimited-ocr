"use client";

import { useEffect, useRef, useState } from "react";
import { api, type OcrResult, type PaperSummary } from "@/lib/api";
import { Badge, Button, Spinner } from "./ui";
import { OcrProgress, type OcrPhase, type OcrProgressInfo } from "./OcrProgress";

const POLL_INTERVAL_MS = 1000;
const POLL_MAX_MS = 5 * 60 * 1000;

export function PaperDetail({
  paper,
  onBack,
  onComplete,
}: {
  paper: PaperSummary;
  onBack: () => void;
  onComplete: (result: OcrResult) => void;
}) {
  const [progress, setProgress] = useState<OcrProgressInfo>({ phase: "fetch" });
  const [busy, setBusy] = useState(false);
  const [started, setStarted] = useState(false);
  const mountedRef = useRef(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const setPhase = (phase: OcrPhase, extra: Partial<OcrProgressInfo> = {}) =>
    mountedRef.current && setProgress((p) => ({ ...p, phase, ...extra }));

  async function runOcr() {
    if (busy) return;
    setBusy(true);
    setStarted(true);
    const pmcid = paper.pmcid;

    try {
      // 1. Fetch the PDF (downloads to the shared cache).
      setPhase("fetch", { fetch: null });
      const fetch = await api.fetchPaper(pmcid);
      if (!mountedRef.current) return;
      setPhase("fetch", { fetch });
      if (fetch.status === "unavailable") {
        setBusy(false);
        return; // OcrProgress shows the "no PDF" notice; user can go back.
      }

      // 2. Queue the OCR job.
      setPhase("queue");
      const accepted = await api.runOcr({ pmcid });
      if (!mountedRef.current) return;
      setPhase("queue", { jobStatus: { job_id: accepted.job_id, status: "queued" } });

      // 3. Poll until terminal.
      setPhase("run");
      const deadline = Date.now() + POLL_MAX_MS;
      const poll = async () => {
        try {
          const st = await api.getOcrStatus(accepted.job_id);
          if (!mountedRef.current) return;
          setProgress((p) => ({ ...p, jobStatus: st }));
          if (st.status === "completed" && st.result) {
            setPhase("done", { jobStatus: st });
            timerRef.current = setTimeout(
              () => mountedRef.current && onComplete(st.result!),
              450,
            );
            return;
          }
          if (st.status === "failed") {
            setPhase("failed", { error: st.error || "The OCR job failed on the backend." });
            setBusy(false);
            return;
          }
          if (Date.now() > deadline) {
            setPhase("failed", { error: "OCR timed out after 5 minutes of polling." });
            setBusy(false);
            return;
          }
          timerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
        } catch (err) {
          if (!mountedRef.current) return;
          setPhase("failed", { error: err instanceof Error ? err.message : String(err) });
          setBusy(false);
        }
      };
      timerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
    } catch (err) {
      if (!mountedRef.current) return;
      setPhase("failed", { error: err instanceof Error ? err.message : String(err) });
      setBusy(false);
    }
  }

  const authors = (paper.authors ?? []).map((a) => a.name).join(", ");

  return (
    <div className="flex flex-col gap-5">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex w-fit items-center gap-1 text-sm text-zinc-500 transition hover:text-indigo-600 dark:text-zinc-400 dark:hover:text-indigo-400"
      >
        <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M12.8 4.3a1 1 0 0 1 0 1.4L8.4 10l4.4 4.3a1 1 0 0 1-1.4 1.4l-5-5a1 1 0 0 1 0-1.4l5-5a1 1 0 0 1 1.4 0Z" /></svg>
        Back to results
      </button>

      <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="indigo">{paper.pmcid}</Badge>
          {paper.year && <Badge>{paper.year}</Badge>}
          {paper.journal && <span className="text-sm italic text-zinc-500 dark:text-zinc-400">{paper.journal}</span>}
          {paper.doi && <span className="text-xs text-zinc-400">doi:{paper.doi}</span>}
        </div>
        <h2 className="mt-2 text-xl font-semibold leading-snug text-zinc-900 dark:text-zinc-50">
          {paper.title || "Untitled"}
        </h2>
        {authors && <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-300">{authors}</p>}
        {paper.abstract_snippet && (
          <p className="mt-3 text-sm leading-6 text-zinc-500 dark:text-zinc-400">{paper.abstract_snippet}</p>
        )}

        {!started && (
          <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-zinc-100 pt-4 dark:border-zinc-800">
            <Button onClick={runOcr} loading={busy}>
              {!busy && (
                <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M4 4a2 2 0 0 1 2-2h2v2H6v12h2v2H6a2 2 0 0 1-2-2V4Zm10-2a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-2v-2h2V4h-2V2h2ZM8 7h4v2H8V7Zm0 4h4v2H8v-2Z" /></svg>
              )}
              Run OCR
            </Button>
            <span className="text-xs text-zinc-400">
              Downloads the PDF, then runs Unlimited-OCR locally. OCR is slow — you’ll see live progress.
            </span>
          </div>
        )}
      </div>

      {started && (
        <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="mb-4 flex items-center gap-2">
            {busy ? <Spinner className="h-4 w-4 text-indigo-500" /> : null}
            <h3 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">OCR progress</h3>
          </div>
          <OcrProgress info={progress} />
        </div>
      )}
    </div>
  );
}

