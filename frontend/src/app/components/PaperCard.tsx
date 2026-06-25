"use client";

import type { PaperSummary } from "@/lib/api";
import { Badge } from "./ui";

export function PaperCard({
  paper,
  onSelect,
  selected = false,
}: {
  paper: PaperSummary;
  onSelect: (p: PaperSummary) => void;
  selected?: boolean;
}) {
  const authorList = (paper.authors ?? [])
    .slice(0, 4)
    .map((a) => a.name)
    .join(", ");
  const moreAuthors = (paper.authors?.length ?? 0) > 4;
  return (
    <button
      type="button"
      onClick={() => onSelect(paper)}
      className={`group w-full rounded-xl border p-4 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
        selected
          ? "border-indigo-400 bg-indigo-50 dark:border-indigo-600 dark:bg-indigo-950/40"
          : "border-zinc-200 bg-white hover:border-indigo-300 hover:shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-indigo-700"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-semibold leading-snug text-zinc-900 group-hover:text-indigo-700 dark:text-zinc-50 dark:group-hover:text-indigo-300">
          {paper.title || "Untitled"}
        </h3>
        <svg className={`mt-1 h-4 w-4 flex-none text-zinc-300 transition group-hover:translate-x-0.5 group-hover:text-indigo-500 ${selected ? "text-indigo-500" : ""}`} viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M7.2 4.3a1 1 0 0 1 1.4 0l5 5a1 1 0 0 1 0 1.4l-5 5a1 1 0 0 1-1.4-1.4L11.6 10 7.2 5.7a1 1 0 0 1 0-1.4Z" clipRule="evenodd" /></svg>
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-zinc-500 dark:text-zinc-400">
        <Badge tone="indigo">{paper.pmcid}</Badge>
        {paper.year && <span>{paper.year}</span>}
        {paper.journal && (
          <>
            <span className="text-zinc-300 dark:text-zinc-600">·</span>
            <span className="italic">{paper.journal}</span>
          </>
        )}
      </div>
      {authorList && (
        <p className="mt-1.5 text-sm text-zinc-600 dark:text-zinc-300">
          {authorList}
          {moreAuthors && <span className="text-zinc-400"> et al.</span>}
        </p>
      )}
      {paper.abstract_snippet && (
        <p className="mt-2 line-clamp-2 text-sm leading-6 text-zinc-500 dark:text-zinc-400">
          {paper.abstract_snippet}
        </p>
      )}
    </button>
  );
}
