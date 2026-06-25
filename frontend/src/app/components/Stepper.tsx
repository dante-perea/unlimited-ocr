"use client";

import { Badge } from "./ui";

export type FlowStep = "search" | "select" | "results";

const STEPS: { key: FlowStep; label: string; hint: string }[] = [
  { key: "search", label: "Search", hint: "PMC Open Access" },
  { key: "select", label: "Select", hint: "Fetch PDF · run OCR" },
  { key: "results", label: "Results", hint: "Text · pages · facts" },
];

export function Stepper({ current }: { current: FlowStep }) {
  const currentIndex = STEPS.findIndex((s) => s.key === current);
  return (
    <ol className="flex w-full items-center gap-2">
      {STEPS.map((step, i) => {
        const done = i < currentIndex;
        const active = i === currentIndex;
        return (
          <li key={step.key} className="flex flex-1 items-center gap-2">
            <div className="flex items-center gap-2">
              <span
                className={`flex h-7 w-7 flex-none items-center justify-center rounded-full text-xs font-semibold transition ${
                  active
                    ? "bg-indigo-600 text-white"
                    : done
                      ? "bg-emerald-500 text-white"
                      : "bg-zinc-200 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
                }`}
              >
                {done ? (
                  <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0L3.3 9.7a1 1 0 1 1 1.4-1.4l3.8 3.8 6.8-6.8a1 1 0 0 1 1.4 0Z" /></svg>
                ) : (
                  i + 1
                )}
              </span>
              <div className="hidden sm:block">
                <p className={`text-sm font-medium leading-tight ${active ? "text-zinc-900 dark:text-zinc-50" : "text-zinc-500 dark:text-zinc-400"}`}>
                  {step.label}
                </p>
                <p className="text-[11px] leading-tight text-zinc-400">{step.hint}</p>
              </div>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`mx-1 h-px flex-1 ${done ? "bg-emerald-400" : "bg-zinc-200 dark:bg-zinc-800"}`} />
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function MockBadge({ mock }: { mock?: boolean }) {
  if (!mock) return null;
  return (
    <Badge tone="amber" className="ml-2">
      <span className="h-1.5 w-1.5 rounded-full bg-amber-500" /> mock OCR
    </Badge>
  );
}
