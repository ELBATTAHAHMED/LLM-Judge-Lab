import React from 'react';
import { Link } from 'react-router-dom';
import { useControlledResults } from '../api/client';
import { formatMetricCi, formatMetricValue } from '../api/finalEvidence';
import type { ControlledMetricResult } from '../api/types';

const SummaryMetric: React.FC<{ label: string; metric: ControlledMetricResult | undefined; detail: string }> = ({ label, metric, detail }) => (
  <article className="flex h-full flex-col rounded-lg border border-neutral-200 bg-neutral-50 p-3 dark:border-neutral-800 dark:bg-[#0a0a0a]">
    <p className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">{label}</p>
    <p className="mt-1 text-xl font-mono font-semibold tracking-tight text-neutral-900 dark:text-white">{metric ? formatMetricValue(metric) : 'Unavailable'}</p>
    <p className="mt-1 text-[11px] leading-snug text-neutral-500">{metric ? detail : 'Final controlled metric not available.'}</p>
  </article>
);

const Finding: React.FC<{ rq: string; title: string; children: React.ReactNode }> = ({ rq, title, children }) => (
  <li className="rounded-lg border border-neutral-200 bg-neutral-50 p-3 dark:border-neutral-800 dark:bg-[#0a0a0a]"><p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500">{rq}</p><h3 className="mt-1 text-xs font-semibold text-neutral-900 dark:text-white">{title}</h3><p className="mt-1 text-[11px] leading-snug text-neutral-500">{children}</p></li>
);

const Rq7Tradeoff: React.FC<{ agreement: ControlledMetricResult | undefined; coverage: ControlledMetricResult | undefined }> = ({ agreement, coverage }) => (
  <article className="flex h-full flex-col rounded-lg border border-neutral-200 bg-neutral-50 p-3 dark:border-neutral-800 dark:bg-[#0a0a0a]">
    <p className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">RQ7 · Mitigation</p>
    <div className="mt-2 grid grid-cols-2 gap-3">
      <div><p className="text-[10px] text-neutral-500">Agreement</p><p className="mt-0.5 font-mono text-lg font-semibold tracking-tight text-neutral-900 dark:text-white">{agreement ? formatMetricValue(agreement) : 'Unavailable'}</p></div>
      <div><p className="text-[10px] text-neutral-500">Coverage</p><p className="mt-0.5 font-mono text-lg font-semibold tracking-tight text-neutral-900 dark:text-white">{coverage ? formatMetricValue(coverage) : 'Unavailable'}</p></div>
    </div>
    <p className="mt-1 text-[11px] leading-snug text-neutral-500">Higher agreement among retained decisions, lower valid coverage.</p>
  </article>
);

export const SynthesisPage: React.FC = () => {
  const { data, loading, error } = useControlledResults();
  const metric = (rq: string, metricKey: string) => data?.results.find((row) => row.rq === rq && row.metric_key === metricKey);
  const ready = data?.status === 'CONTROLLED_RESULTS_AVAILABLE';
  const rq1 = metric('RQ1', 'exact_agreement');
  const rq2 = metric('RQ2', 'consistency');
  const rq3 = metric('RQ3', 'paired_decisive_flip_rate');
  const rq4 = metric('RQ4', 'variant_win_rate');
  const rq5 = metric('RQ5', 'variant_win_rate');
  const rq6 = metric('RQ6', 'stable_same_family_preference');
  const rq6Coverage = metric('RQ6', 'valid_stable_decisive_coverage');
  const rq7Agreement = metric('RQ7', 'agreement_delta');
  const rq7Coverage = metric('RQ7', 'coverage_delta');

  return <div className="mx-auto max-w-[1400px] space-y-5 py-2 font-sans">
    <header className="border-b border-neutral-200 pb-4 dark:border-neutral-800"><h1 className="text-2xl font-serif tracking-tight text-neutral-900 dark:text-white">Final Scientific Synthesis</h1><p className="mt-1 max-w-3xl text-xs leading-relaxed text-neutral-600 dark:text-neutral-400">Executive summary of the final controlled RQ1–RQ7 evidence.</p></header>
    {loading && <div className="rounded-lg border border-neutral-200 p-4 text-xs text-neutral-500 dark:border-neutral-800">Loading final controlled synthesis…</div>}
    {error && <div className="rounded-lg border border-neutral-200 p-4 text-xs text-neutral-500 dark:border-neutral-800">Final controlled synthesis unavailable. No alternate values are substituted: {error}</div>}
    {!loading && !error && !ready && <div className="rounded-lg border border-neutral-200 p-4 text-xs text-neutral-500 dark:border-neutral-800">Final controlled synthesis is not available: {data?.message ?? 'No controlled response.'}</div>}
    {ready && <>
      <section aria-label="Headline findings" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><SummaryMetric label="RQ1 · Human Alignment" metric={rq1} detail="Agreement with human preference reference labels" /><SummaryMetric label="RQ2 · Consistency" metric={rq2} detail="Within-unit repeated-evaluation consistency" /><SummaryMetric label="RQ3 · Position Sensitivity" metric={rq3} detail="Paired decisive flip rate under answer-order swap" /><SummaryMetric label="RQ4 · Redundant-Length Effect" metric={rq4} detail="Controlled redundant-length variant win rate" /><SummaryMetric label="RQ5 · Presentation-Format Effect" metric={rq5} detail="Controlled presentation-format variant win rate" /><SummaryMetric label="RQ6 · Source-Family Preference" metric={rq6} detail={rq6 ? `Stable same-family preference · ${formatMetricCi(rq6)} · N = ${rq6.denominator ?? 'unavailable'} stable decisive` : 'Stable same-family preference'} /><Rq7Tradeoff agreement={rq7Agreement} coverage={rq7Coverage} /></section>
      <section aria-labelledby="key-findings-title"><h2 id="key-findings-title" className="text-sm font-semibold text-neutral-900 dark:text-white">Key Findings</h2><ul className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Finding rq="RQ1" title="Human Alignment">{rq1 ? `${formatMetricValue(rq1)} agreement with human preference reference labels.` : 'No final metric available.'}</Finding><Finding rq="RQ2" title="Consistency">{rq2 ? `${formatMetricValue(rq2)} repeated-evaluation consistency.` : 'No final metric available.'}</Finding><Finding rq="RQ3" title="Position Sensitivity">{rq3 ? `${formatMetricValue(rq3)} decisive flip rate under answer-order swaps.` : 'No final metric available.'}</Finding><Finding rq="RQ4" title="Redundant-Length">{rq4 ? `${formatMetricValue(rq4)} controlled variant win rate.` : 'Final metric unavailable.'}</Finding><Finding rq="RQ5" title="Presentation Format">{rq5 ? `${formatMetricValue(rq5)} controlled format-variant win rate.` : 'Final metric unavailable.'}</Finding><Finding rq="RQ6" title="Source-Family Preference">{rq6 ? `${formatMetricValue(rq6)} overall stable same-family preference; no clear uniform overall preference, with strong judge-level heterogeneity; coverage ${rq6Coverage ? formatMetricValue(rq6Coverage) : 'unavailable'}.` : 'Counterbalanced RQ6 metric unavailable.'}</Finding><Finding rq="RQ7" title="Mitigation">{rq7Agreement && rq7Coverage ? `Agreement ${formatMetricValue(rq7Agreement)}, coverage ${formatMetricValue(rq7Coverage)}.` : 'Final mitigation metrics unavailable.'}</Finding></ul></section>
      <Link to="/controlled-results" className="inline-flex w-fit rounded border border-neutral-200 px-2.5 py-1.5 text-[11px] font-medium text-neutral-700 transition-colors hover:bg-neutral-50 dark:border-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-900">View full controlled evidence</Link>
    </>}
  </div>;
};

export default SynthesisPage;
