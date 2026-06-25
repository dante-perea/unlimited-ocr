"use client";

import { useCallback, useEffect, useState } from "react";
import {
  api,
  API_BASE_URL,
  type HealthResponse,
  type OcrResult,
  type PaperSummary,
} from "@/lib/api";
import { SearchPanel, type SearchState } from "./components/SearchPanel";
import { Stepper, type FlowStep } from "./components/Stepper";
import { PaperDetail } from "./components/PaperDetail";
import { ResultsView } from "./components/ResultsView";

const PAGE_SIZE = 10;

type Health =
  | { state: "loading" }
  | { state: "ok"; data: HealthResponse }
  | { state: "error"; message: string };

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export default function Home() {
  const [step, setStep] = useState<FlowStep>("search");
  const [search, setSearch] = useState<SearchState>({
    loading: false,
    error: null,
    data: null,
    query: "",
    page: 1,
  });
  const [selected, setSelected] = useState<PaperSummary | null>(null);
  const [result, setResult] = useState<OcrResult | null>(null);
  const [health, setHealth] = useState<Health>({ state: "loading" });

  useEffect(() => {
    let active = true;
    api
      .health()
      .then((data) => active && setHealth({ state: "ok", data }))
      .catch((err: unknown) =>
        active && setHealth({ state: "error", message: errorMessage(err) }),
      );
    return () => {
      active = false;
    };
  }, []);

  const runSearch = useCallback(async (query: string, page = 1) => {
    setSearch((s) => ({ ...s, loading: true, error: null, query, page }));
    try {
      const data = await api.searchPapers({ query, page, pageSize: PAGE_SIZE });
      setSearch({ loading: false, error: null, data, query, page });
    } catch (err) {
      setSearch((s) => ({ ...s, loading: false, error: errorMessage(err) }));
    }
  }, []);

  const handleSelect = useCallback((p: PaperSummary) => {
    setSelected(p);
    setResult(null);
    setStep("select");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const handleBack = useCallback(() => setStep("search"), []);

  const handleComplete = useCallback((r: OcrResult) => {
    setResult(r);
    setStep("results");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const handleStartOver = useCallback(() => {
    setSelected(null);
    setResult(null);
    setStep("search");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-8 px-4 py-10 sm:px-6">
      <header className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-medium uppercase tracking-widest text-indigo-600 dark:text-indigo-400">
            Local OCR workbench
          </p>
          <HealthBadge health={health} />
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-4xl">
          NCBI Papers × Unlimited-OCR
        </h1>
        <p className="max-w-2xl text-base leading-7 text-zinc-600 dark:text-zinc-400 sm:text-lg">
          Search PubMed Central Open Access papers, run Baidu Unlimited-OCR on
          your own hardware, and read the extracted full text and structured facts.
        </p>
      </header>

      <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <Stepper current={step} />
      </div>

      {step === "search" && (
        <section>
          <SearchPanel
            state={search}
            onSearch={(q) => runSearch(q, 1)}
            onPageChange={(p) => runSearch(search.query, p)}
            onSelect={handleSelect}
            selectedPmcid={selected?.pmcid}
          />
        </section>
      )}


      {step === "select" && selected && (
        <section>
          <PaperDetail
            paper={selected}
            onBack={handleBack}
            onComplete={handleComplete}
          />
        </section>
      )}

      {step === "results" && selected && result && (
        <section>
          <ResultsView
            result={result}
            paper={selected}
            onStartOver={handleStartOver}
          />
        </section>
      )}

      <footer className="mt-auto pt-4 text-center text-xs text-zinc-400">
        Backend at <code className="font-mono">{API_BASE_URL}</code> · OCR runs locally on your hardware.
      </footer>
    </main>
  );
}

function HealthBadge({ health }: { health: Health }) {
  if (health.state === "loading") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-zinc-100 px-2.5 py-1 text-xs text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
        <span className="h-2 w-2 animate-pulse rounded-full bg-zinc-400" /> connecting…
      </span>
    );
  }
  if (health.state === "error") {
    return (
      <span
        title={health.message}
        className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300"
      >
        <span className="h-2 w-2 rounded-full bg-amber-500" /> backend offline
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
      <span className="h-2 w-2 rounded-full bg-emerald-500" />
      online · {health.data.device}
    </span>
  );
}

