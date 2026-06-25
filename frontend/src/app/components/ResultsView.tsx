"use client";

import { useState } from "react";
import type { OcrResult, PaperSummary } from "@/lib/api";
import { Markdown } from "@/lib/markdown";
import { Badge, Button, copyToClipboard } from "./ui";
import { FactsPanel } from "./FactsPanel";
import { MockBadge } from "./Stepper";

type Tab = "text" | "pages" | "facts";

const TABS: { key: Tab; label: string }[] = [
  { key: "text", label: "Full text" },
  { key: "pages", label: "Pages" },
  { key: "facts", label: "Facts" },
];

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function ResultsView({
  result,
  paper,
  onStartOver,
}: {
  result: OcrResult;
  paper: PaperSummary;
  onStartOver: () => void;
}) {
  const [tab, setTab] = useState<Tab>("text");
  const [pageIdx, setPageIdx] = useState(0);
  const [copied, setCopied] = useState(false);

  const pages = result.pages ?? [];
  const safePageIdx = Math.min(pageIdx, Math.max(pages.length - 1, 0));

  async function handleCopy() {
    const ok = await copyToClipboard(result.full_text);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    }
  }

  function handleDownload() {
    downloadJson(`${paper.pmcid}-ocr.json`, {
      paper: {
        pmcid: paper.pmcid,
        title: paper.title,
        authors: paper.authors,
        journal: paper.journal,
        year: paper.year,
        doi: paper.doi,
      },
      ocr: result,
    });
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="indigo">{paper.pmcid}</Badge>
            <Badge>{result.n_pages} pages</Badge>
            <Badge tone={result.mock ? "amber" : "neutral"}>device: {result.device}</Badge>
            <MockBadge mock={result.mock} />
          </div>
          <h2 className="mt-2 truncate text-lg font-semibold text-zinc-900 dark:text-zinc-50">
            {paper.title || "Untitled"}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={handleCopy}>
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M8 2a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6.4a2 2 0 0 0-.6-1.4l-2.4-2.4A2 2 0 0 0 11.6 2H8Z" /><path d="M4 6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-1H8a4 4 0 0 1-4-4V6Z" /></svg>
            {copied ? "Copied!" : "Copy text"}
          </Button>
          <Button variant="secondary" onClick={handleDownload}>
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M10 2a1 1 0 0 1 1 1v7.6l2.3-2.3a1 1 0 1 1 1.4 1.4l-4 4a1 1 0 0 1-1.4 0l-4-4a1 1 0 1 1 1.4-1.4L9 10.6V3a1 1 0 0 1 1-1Z" /><path d="M3 15a1 1 0 0 1 1 1v1h12v-1a1 1 0 1 1 2 0v2a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1Z" /></svg>
            Download JSON
          </Button>
          <Button variant="ghost" onClick={onStartOver}>New search</Button>
        </div>
      </div>

      <div className="flex gap-1 border-b border-zinc-200 dark:border-zinc-800">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`relative px-4 py-2 text-sm font-medium transition ${
              tab === t.key
                ? "text-indigo-600 dark:text-indigo-400"
                : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
            }`}
          >
            {t.label}
            {tab === t.key && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-indigo-600 dark:bg-indigo-400" />}
          </button>
        ))}
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900 sm:p-7">
        {tab === "text" && (
          result.full_text.trim() ? (
            <article className="max-w-none">
              <Markdown source={result.full_text} />
            </article>
          ) : (
            <p className="py-8 text-center text-sm text-zinc-400">No text was extracted.</p>
          )
        )}

        {tab === "pages" && (
          pages.length > 0 ? (
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <Button
                  variant="secondary"
                  disabled={safePageIdx <= 0}
                  onClick={() => setPageIdx((i) => Math.max(0, i - 1))}
                >
                  ← Prev page
                </Button>
                <span className="text-sm text-zinc-500 dark:text-zinc-400">
                  page <span className="font-medium text-zinc-700 dark:text-zinc-200">{safePageIdx + 1}</span> / {pages.length}
                </span>
                <Button
                  variant="secondary"
                  disabled={safePageIdx >= pages.length - 1}
                  onClick={() => setPageIdx((i) => Math.min(pages.length - 1, i + 1))}
                >
                  Next page →
                </Button>
              </div>
              <div className="rounded-lg border border-zinc-100 bg-zinc-50/60 p-5 dark:border-zinc-800 dark:bg-zinc-950/40">
                {pages[safePageIdx]?.text.trim() ? (
                  <Markdown source={pages[safePageIdx].text} />
                ) : (
                  <p className="py-6 text-center text-sm text-zinc-400">This page had no extractable text.</p>
                )}
              </div>
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-zinc-400">No pages.</p>
          )
        )}

        {tab === "facts" && <FactsPanel facts={result.facts} />}
      </div>
    </div>
  );
}

