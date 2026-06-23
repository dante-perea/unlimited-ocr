"use client";

import { useEffect, useState } from "react";
import { api, API_BASE_URL, type HealthResponse } from "@/lib/api";

type Status =
  | { state: "loading" }
  | { state: "ok"; data: HealthResponse }
  | { state: "error"; message: string };

const STEPS = [
  "Search PubMed Central Open Access papers",
  "Select a paper — the app downloads its PDF",
  "Run Unlimited-OCR locally to extract text + facts",
  "Browse the full text and structured results",
];

export default function Home() {
  const [status, setStatus] = useState<Status>({ state: "loading" });

  useEffect(() => {
    let active = true;
    api
      .health()
      .then((data) => active && setStatus({ state: "ok", data }))
      .catch(
        (err: unknown) =>
          active &&
          setStatus({
            state: "error",
            message: err instanceof Error ? err.message : String(err),
          }),
      );
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-10 px-6 py-16">
      <header className="flex flex-col gap-3">
        <p className="text-sm font-medium uppercase tracking-widest text-indigo-600 dark:text-indigo-400">
          Local OCR workbench
        </p>
        <h1 className="text-4xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          NCBI Papers × Unlimited-OCR
        </h1>
        <p className="max-w-xl text-lg leading-8 text-zinc-600 dark:text-zinc-400">
          Browse free-access papers and run Baidu Unlimited-OCR on your own
          hardware to extract full text and structured facts.
        </p>
      </header>

      <section className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          Backend status
        </h2>
        <BackendStatus status={status} />
      </section>

      <section>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          How it will work
        </h2>
        <ol className="flex flex-col gap-3">
          {STEPS.map((step, i) => (
            <li key={step} className="flex items-start gap-3">
              <span className="mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full bg-indigo-600 text-xs font-semibold text-white">
                {i + 1}
              </span>
              <span className="text-zinc-700 dark:text-zinc-300">{step}</span>
            </li>
          ))}
        </ol>
      </section>

      <footer className="mt-auto text-sm text-zinc-400">
        Foundation scaffold — NCBI search and OCR are wired in by later tasks.
      </footer>
    </main>
  );
}

function BackendStatus({ status }: { status: Status }) {
  if (status.state === "loading") {
    return (
      <p className="text-zinc-500">
        Pinging <code className="font-mono">{API_BASE_URL}/health</code>…
      </p>
    );
  }

  if (status.state === "error") {
    return (
      <div className="flex flex-col gap-1">
        <p className="flex items-center gap-2 font-medium text-amber-600 dark:text-amber-400">
          <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
          Backend unreachable
        </p>
        <p className="text-sm text-zinc-500">{status.message}</p>
        <p className="text-sm text-zinc-500">
          Start it with <code className="font-mono">make backend</code>.
        </p>
      </div>
    );
  }

  return (
    <dl className="grid grid-cols-2 gap-y-2 text-sm sm:grid-cols-4">
      <div className="col-span-2 flex items-center gap-2 sm:col-span-4">
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
        <span className="font-medium text-emerald-600 dark:text-emerald-400">
          {status.data.status}
        </span>
      </div>
      <dt className="text-zinc-400">App</dt>
      <dd className="text-zinc-700 dark:text-zinc-300">{status.data.app}</dd>
      <dt className="text-zinc-400">Version</dt>
      <dd className="text-zinc-700 dark:text-zinc-300">{status.data.version}</dd>
      <dt className="text-zinc-400">Device</dt>
      <dd className="font-mono text-zinc-700 dark:text-zinc-300">
        {status.data.device}
      </dd>
    </dl>
  );
}
