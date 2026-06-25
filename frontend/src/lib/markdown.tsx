/**
 * Tiny, dependency-free Markdown -> React renderer.
 *
 * The OCR pipeline emits (loosely specified) markdown: headings, paragraphs,
 * lists, blockquotes, GFM pipe tables and fenced code blocks. This renderer
 * covers that subset with long-form reading typography in mind. It renders real
 * React nodes (no dangerouslySetInnerHTML) so all text is escaped by default.
 */

import type { ElementType, ReactNode } from "react";

const HEADING_RE = /^(#{1,6})\s+(.*)$/;
const HR_RE = /^(-{3,}|\*{3,}|_{3,})\s*$/;
const UL_RE = /^([-*+])\s+(.*)$/;
const OL_RE = /^(\d+)\.\s+(.*)$/;
const QUOTE_RE = /^>\s?(.*)$/;
const FENCE_RE = /^```(.*)$/;
const TABLE_SEP_RE = /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?$/;

export function Markdown({ source }: { source: string }) {
  return <div className="prose-md">{renderBlocks(source)}</div>;
}

function renderBlocks(source: string): ReactNode[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const out: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i++;
      continue;
    }

    // Fenced code block.
    const fence = line.match(FENCE_RE);
    if (fence) {
      const lang = fence[1].trim();
      const code: string[] = [];
      i++;
      while (i < lines.length && !FENCE_RE.test(lines[i])) {
        code.push(lines[i]);
        i++;
      }
      i++;
      out.push(
        <pre key={key++} className="overflow-x-auto rounded-lg bg-zinc-900 p-4 text-sm text-zinc-100 dark:bg-black">
          <code data-lang={lang || undefined} className="whitespace-pre font-mono">{code.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    // Heading.
    const h = line.match(HEADING_RE);
    if (h) {
      const level = h[1].length;
      const sizes = ["text-3xl", "text-2xl", "text-xl", "text-lg", "text-base", "text-sm"];
      const Tag = `h${level}` as ElementType;
      out.push(
        <Tag key={key++} className={`mt-6 mb-2 font-semibold tracking-tight text-zinc-900 dark:text-zinc-50 ${sizes[level - 1]}`}>
          {parseInline(h[2].trim())}
        </Tag>,
      );
      i++;
      continue;
    }

    if (HR_RE.test(line)) {
      out.push(<hr key={key++} className="my-6 border-zinc-200 dark:border-zinc-800" />);
      i++;
      continue;
    }

    // Table (header | separator | rows).
    if (line.includes("|") && i + 1 < lines.length && TABLE_SEP_RE.test(lines[i + 1])) {
      const header = splitRow(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
        rows.push(splitRow(lines[i]));
        i++;
      }
      out.push(
        <div key={key++} className="my-4 overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                {header.map((c, ci) => (
                  <th key={ci} className="border border-zinc-300 bg-zinc-100 px-3 py-1.5 text-left font-semibold dark:border-zinc-700 dark:bg-zinc-800">
                    {parseInline(c)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri}>
                  {r.map((c, ci) => (
                    <td key={ci} className="border border-zinc-200 px-3 py-1.5 align-top dark:border-zinc-800">
                      {parseInline(c)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    // Blockquote.
    if (QUOTE_RE.test(line)) {
      const quote: string[] = [];
      while (i < lines.length && QUOTE_RE.test(lines[i])) {
        quote.push(lines[i].replace(QUOTE_RE, "$1"));
        i++;
      }
      out.push(
        <blockquote key={key++} className="my-4 border-l-4 border-indigo-300 pl-4 italic text-zinc-600 dark:border-indigo-700 dark:text-zinc-400">
          {parseInline(quote.join(" "))}
        </blockquote>,
      );
      continue;
    }

    // Unordered list.
    if (UL_RE.test(line)) {
      const items: string[] = [];
      while (i < lines.length && UL_RE.test(lines[i])) {
        items.push(lines[i].replace(UL_RE, "$2"));
        i++;
      }
      out.push(
        <ul key={key++} className="my-3 list-disc space-y-1 pl-6">
          {items.map((it, ii) => <li key={ii}>{parseInline(it)}</li>)}
        </ul>,
      );
      continue;
    }

    // Ordered list.
    if (OL_RE.test(line)) {
      const items: string[] = [];
      while (i < lines.length && OL_RE.test(lines[i])) {
        items.push(lines[i].replace(OL_RE, "$2"));
        i++;
      }
      out.push(
        <ol key={key++} className="my-3 list-decimal space-y-1 pl-6">
          {items.map((it, ii) => <li key={ii}>{parseInline(it)}</li>)}
        </ol>,
      );
      continue;
    }

    // Paragraph.
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !HEADING_RE.test(lines[i]) &&
      !HR_RE.test(lines[i]) &&
      !FENCE_RE.test(lines[i]) &&
      !UL_RE.test(lines[i]) &&
      !OL_RE.test(lines[i]) &&
      !QUOTE_RE.test(lines[i]) &&
      !(lines[i].includes("|") && i + 1 < lines.length && TABLE_SEP_RE.test(lines[i + 1]))
    ) {
      para.push(lines[i].trim());
      i++;
    }
    out.push(<p key={key++} className="my-3 leading-7">{parseInline(para.join(" "))}</p>);
  }

  return out;
}

function splitRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((c) => c.trim());
}

// --- Inline parsing -------------------------------------------------------- //
// Finds the earliest inline marker and recurses, so nested emphasis works.
// (parseInline is hoisted as a function declaration, so renderBlocks can call it.)

const INLINE_RE =
  /(`[^`]+`)|(\[[^\]]+\]\([^)]+\))|(\*\*[^*]+\*\*)|(__[^_]+__)|(\*[^*]+\*)|(_[^_]+_)|(~[^~]+~)/;

export function parseInline(text: string): ReactNode[] {
  if (!text) return [];
  const nodes: ReactNode[] = [];
  let rest = text;
  let key = 0;

  while (rest.length) {
    const m = INLINE_RE.exec(rest);
    if (!m) {
      nodes.push(rest);
      break;
    }
    const start = m.index;
    if (start > 0) nodes.push(rest.slice(0, start));
    const token = m[0];

    if (token.startsWith("`")) {
      nodes.push(
        <code key={key++} className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[0.85em] text-pink-600 dark:bg-zinc-800 dark:text-pink-400">
          {token.slice(1, -1)}
        </code>,
      );
    } else if (token.startsWith("[")) {
      const lm = token.match(/\[([^\]]+)\]\(([^)]+)\)/)!;
      nodes.push(
        <a
          key={key++}
          href={lm[2]}
          target="_blank"
          rel="noreferrer noopener"
          className="font-medium text-indigo-600 underline decoration-indigo-300 hover:text-indigo-500 dark:text-indigo-400 dark:decoration-indigo-700"
        >
          {lm[1]}
        </a>,
      );
    } else if (token.startsWith("**") || token.startsWith("__")) {
      nodes.push(<strong key={key++} className="font-semibold">{parseInline(token.slice(2, -2))}</strong>);
    } else if (token.startsWith("*") || token.startsWith("_")) {
      nodes.push(<em key={key++}>{parseInline(token.slice(1, -1))}</em>);
    } else if (token.startsWith("~")) {
      nodes.push(<del key={key++}>{token.slice(1, -1)}</del>);
    }
    rest = rest.slice(start + token.length);
  }
  return nodes;
}

