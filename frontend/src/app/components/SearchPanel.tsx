"use client";

import { useState, type FormEvent } from "react";
import type { PaperSummary, SearchResponse } from "@/lib/api";
import { Button, EmptyState, ErrorBox, Spinner } from "./ui";
import { PaperCard } from "./PaperCard";

const EXAMPLES = ["CRISPR base editing", "cancer immunotherapy", "protein folding", "brain organoids"];

export interface SearchState {
  loading: boolean;
  error: string | null;
  data: SearchResponse | null;
  query: string;
  page: number;
}

export function SearchPanel({
  state,
  onSearch,
  onPageChange,
  onSelect,
  selectedPmcid,
}: {
  state: SearchState;
  onSearch: (query: string) => void;
  onPageChange: (page: number) => void;
  onSelect: (p: PaperSummary) => void;
  selectedPmcid?: string;
}) {
  const [input, setInput] = useState(state.query ?? "");

  function submit(e: FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (q) onSearch(q);
  }

  const { loading, error, data } = state;
  const results = data?.results ?? [];
  const first = results.length ? (data!.page - 1) * data!.page_size + 1 : 0;
  const last = results.length ? first + results.length - 1 : 0;

  return (
    <div className="flex flex-col gap-5">
      <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <svg className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-400" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="9" cy="9" r="6" /><path d="m14 14 4 4" strokeLinecap="round" /></svg>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Search PubMed Central Open Access (e.g. mitochondrial dynamics)"
            aria-label="Search query"
            className="w-full rounded-lg border border-zinc-300 bg-white py-2.5 pl-10 pr-3 text-sm text-zinc-900 shadow-sm outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-200 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50 dark:focus:ring-indigo-900"
          />
        </div>
        <Button type="submit" loading={loading} className="sm:w-32">
          {loading ? "Searching" : "Search"}
        </Button>
      </form>

      {!state.query && !loading && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-zinc-400">Try:</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => {
                setInput(ex);
                onSearch(ex);
              }}
              className="rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs text-zinc-600 transition hover:border-indigo-300 hover:text-indigo-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:border-indigo-700"
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-3 px-1 py-8 text-sm text-zinc-500">
          <Spinner className="h-5 w-5 text-indigo-500" /> Searching PMC Open Access…
        </div>
      )}

      {!loading && error && <ErrorBox title="Search failed" message={error} />}

      {!loading && !error && data && (
        <>
          <div className="flex items-center justify-between px-1 text-xs text-zinc-500 dark:text-zinc-400">
            <span>
              {results.length ? (
                <>Showing <span className="font-medium text-zinc-700 dark:text-zinc-200">{first}–{last}</span> of <span className="font-medium text-zinc-700 dark:text-zinc-200">{data.total_results.toLocaleString()}</span></>
              ) : (
                "No matching papers"
              )}
            </span>
            <span>
              page <span className="font-medium text-zinc-700 dark:text-zinc-200">{data.page}</span> / {Math.max(data.total_pages, 1)}
            </span>
          </div>

          {results.length === 0 ? (
            <EmptyState
              title="No papers found"
              description={`No PMC Open Access results for “${data.query}”. Try a broader query.`}
              icon={<svg className="h-10 w-10" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M9 2a7 7 0 1 0 4.2 12.6l3.1 3.1a1 1 0 0 0 1.4-1.4l-3.1-3.1A7 7 0 0 0 9 2Zm0 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10Z" clipRule="evenodd" /></svg>}
            />
          ) : (
            <ul className="flex flex-col gap-3">
              {results.map((p) => (
                <li key={p.pmcid}>
                  <PaperCard paper={p} onSelect={onSelect} selected={p.pmcid === selectedPmcid} />
                </li>
              ))}
            </ul>
          )}

          {data.total_pages > 1 && (
            <div className="flex items-center justify-between pt-1">
              <Button variant="secondary" disabled={data.page <= 1} onClick={() => onPageChange(data.page - 1)}>
                ← Prev
              </Button>
              <span className="text-xs text-zinc-400">page {data.page} of {data.total_pages}</span>
              <Button variant="secondary" disabled={data.page >= data.total_pages} onClick={() => onPageChange(data.page + 1)}>
                Next →
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

