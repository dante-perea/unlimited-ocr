"use client";

import type { Facts } from "@/lib/api";
import { Markdown } from "@/lib/markdown";
import { Badge, EmptyState } from "./ui";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">{title}</h4>
      {children}
    </section>
  );
}

export function FactsPanel({ facts }: { facts: Facts }) {
  const hasAnything =
    facts.title || facts.abstract || (facts.authors && facts.authors.length) ||
    (facts.key_findings && facts.key_findings.length) ||
    (facts.entities && facts.entities.length) || (facts.tables && facts.tables.length);

  if (!hasAnything) {
    return (
      <EmptyState
        title="No structured facts extracted"
        description="The heuristic extractor didn’t find fields in this document’s text."
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
        <Badge tone="neutral">extractor: {facts.extractor ?? "heuristic"}</Badge>
        {facts.doi && <Badge tone="indigo">doi: {facts.doi}</Badge>}
        {facts.pmcid && <Badge tone="indigo">{facts.pmcid}</Badge>}
      </div>

      {facts.title && (
        <Section title="Title">
          <p className="text-base font-semibold text-zinc-900 dark:text-zinc-50">{facts.title}</p>
        </Section>
      )}

      {facts.authors && facts.authors.length > 0 && (
        <Section title={`Authors (${facts.authors.length})`}>
          <div className="flex flex-wrap gap-1.5">
            {facts.authors.map((a, i) => (
              <span key={`${a}-${i}`} className="rounded-md border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-sm text-zinc-700 dark:border-zinc-800 dark:bg-zinc-800/60 dark:text-zinc-200">
                {a}
              </span>
            ))}
          </div>
        </Section>
      )}

      {facts.abstract && (
        <Section title="Abstract">
          <p className="text-sm leading-7 text-zinc-600 dark:text-zinc-300">{facts.abstract}</p>
        </Section>
      )}

      {facts.key_findings && facts.key_findings.length > 0 && (
        <Section title={`Key findings (${facts.key_findings.length})`}>
          <ul className="flex flex-col gap-2">
            {facts.key_findings.map((k, i) => (
              <li key={i} className="flex gap-2 text-sm leading-6 text-zinc-700 dark:text-zinc-200">
                <span className="mt-0.5 flex-none font-semibold text-indigo-500">{i + 1}.</span>
                <span>{k}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {facts.entities && facts.entities.length > 0 && (
        <Section title={`Entities (${facts.entities.length})`}>
          <div className="flex flex-wrap gap-1.5">
            {facts.entities.map((e, i) => (
              <span key={`${e}-${i}`} className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                {e}
              </span>
            ))}
          </div>
        </Section>
      )}

      {facts.tables && facts.tables.length > 0 && (
        <Section title={`Tables (${facts.tables.length})`}>
          <div className="flex flex-col gap-4">
            {facts.tables.map((t, i) => (
              <div key={i} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
                <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-zinc-400">Table {i + 1}</p>
                <Markdown source={t} />
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}
