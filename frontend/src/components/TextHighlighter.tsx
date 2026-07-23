import React from 'react';

interface Props {
  text: string;
}

// Length / Verbosity target terms
const LENGTH_TERMS = [
  "more detailed",
  "provides specific details",
  "comprehensive",
  "less informative",
  "provides more",
  "more thorough",
  "greater depth",
  "more complete",
  "well structured",
  "more information",
  "detailed explanation",
  "additional details",
  "elaborates",
  "far more",
];

// Hedging target terms
const HEDGING_TERMS = [
  "slightly",
  "however",
  "nuanced",
  "hard to choose",
  "marginal",
  "subtle",
  "somewhat",
  "arguably",
  "minor",
  "similar",
  "tie",
  "comparable",
];

/**
 * Normalizes text to eliminate duplicate bracket artifacts like '[Answer A] Answer A'.
 */
function sanitizeRawText(rawText: string): string {
  if (!rawText) return '';
  return rawText
    .replace(/\[\s*(Answer\s+[AB]|Position\s+[AB])\s*\]\s*\1/gi, '$1')
    .replace(/\[\s*(Answer\s+[AB]|Position\s+[AB])\s*\]\s*Answer\s+[AB]/gi, '$1')
    .replace(/\[\s*(Answer\s+[AB]|Position\s+[AB])\s*\]/gi, '$1')
    .replace(/\b(Answer\s+[AB]|Position\s+[AB])\s+\1\b/gi, '$1');
}

/**
 * Scans and tokenizes text, converting Answer labels to single JSX badges
 * and bi-gram terms into colored highlights.
 */
function highlightKeywordsInText(segment: string, keyPrefix: string): React.ReactNode[] {
  if (!segment) return [];

  const answerPattern = '\\b(?:Answer\\s+[AB]|Position\\s+[AB])\\b';
  const lengthPattern = '\\b(?:' + LENGTH_TERMS.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')\\b';
  const hedgingPattern = '\\b(?:' + HEDGING_TERMS.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')\\b';

  const combinedRegex = new RegExp(`(${answerPattern}|${lengthPattern}|${hedgingPattern})`, 'gi');

  const nodes: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = combinedRegex.exec(segment)) !== null) {
    const matchText = match[0];
    const matchIndex = match.index;

    // Append preceding plain text
    if (matchIndex > lastIndex) {
      nodes.push(segment.substring(lastIndex, matchIndex));
    }

    const lowerMatch = matchText.toLowerCase();

    if (/\b(?:answer\s+[ab]|position\s+[ab])\b/i.test(matchText)) {
      nodes.push(
        <span
          key={`${keyPrefix}-lbl-${matchIndex}`}
          className="font-mono text-[11px] font-semibold text-neutral-900 dark:text-neutral-100 border-b border-neutral-400/50 dark:border-neutral-500/40 mx-0.5 align-baseline"
        >
          {matchText}
        </span>
      );
    } else if (LENGTH_TERMS.some((term) => lowerMatch === term.toLowerCase())) {
      nodes.push(
        <em
          key={`${keyPrefix}-len-${matchIndex}`}
          className="not-italic font-sans text-[11px] text-emerald-700 dark:text-emerald-400/90 border-b border-emerald-500/50 dark:border-emerald-500/40 mx-0.5 align-baseline"
        >
          {matchText}
        </em>
      );
    } else if (HEDGING_TERMS.some((term) => lowerMatch === term.toLowerCase())) {
      nodes.push(
        <em
          key={`${keyPrefix}-hdg-${matchIndex}`}
          className="not-italic font-sans text-[11px] text-rose-600 dark:text-rose-400/80 border-b border-rose-500/50 dark:border-rose-500/40 mx-0.5 align-baseline"
        >
          {matchText}
        </em>
      );
    } else {
      nodes.push(matchText);
    }

    lastIndex = combinedRegex.lastIndex;
  }

  // Append remaining text
  if (lastIndex < segment.length) {
    nodes.push(segment.substring(lastIndex));
  }

  return nodes;
}

/**
 * Parses markdown bold (**text**) inside a line and delegates keyword highlighting.
 */
function parseLineMarkdown(line: string, lineIdx: number): React.ReactNode {
  const boldRegex = /(\*\*.*?\*\*)/g;
  const segments = line.split(boldRegex);

  return (
    <>
      {segments.map((segment, segIdx) => {
        if (!segment) return null;
        const key = `l${lineIdx}-s${segIdx}`;

        if (segment.startsWith('**') && segment.endsWith('**')) {
          const innerText = segment.slice(2, -2);
          return (
            <strong key={key} className="font-bold text-neutral-950 dark:text-white">
              {highlightKeywordsInText(innerText, key)}
            </strong>
          );
        }

        return <React.Fragment key={key}>{highlightKeywordsInText(segment, key)}</React.Fragment>;
      })}
    </>
  );
}

export const TextHighlighter: React.FC<Props> = ({ text }) => {
  if (!text) return <span className="text-neutral-500">No reasoning text available.</span>;

  const sanitized = sanitizeRawText(text);
  const lines = sanitized.split('\n');

  return (
    <div className="space-y-2 text-xs font-mono leading-relaxed text-neutral-800 dark:text-neutral-300">
      {lines.map((line, lineIdx) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={`line-${lineIdx}`} className="h-1.5" />;

        // Handle bullet points (- or *)
        const isBullet = /^[*-]\s+/.test(trimmed);
        const contentLine = isBullet ? trimmed.replace(/^[*-]\s+/, '') : line;

        if (isBullet) {
          return (
            <div
              key={`line-${lineIdx}`}
              className="flex items-start space-x-2 pl-3 py-0.5 my-1 border-l-2 border-neutral-300 dark:border-neutral-700 bg-neutral-100/50 dark:bg-neutral-900/40 rounded-r"
            >
              <span className="text-neutral-400 font-bold select-none">&bull;</span>
              <div className="flex-1">{parseLineMarkdown(contentLine, lineIdx)}</div>
            </div>
          );
        }

        return <div key={`line-${lineIdx}`}>{parseLineMarkdown(line, lineIdx)}</div>;
      })}
    </div>
  );
};
