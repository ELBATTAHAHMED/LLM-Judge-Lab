import React from 'react';
import { Link } from 'react-router-dom';
import { useControlledResults } from '../api/client';
import { formatMetricCi, formatMetricValue } from '../api/finalEvidence';
import type { ControlledMetricResult } from '../api/types';

const SummaryStat: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="min-w-0 p-3">
    <p className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">{label}</p>
    <div className="mt-1 font-mono text-lg font-semibold tracking-tight text-neutral-900 dark:text-white">{children}</div>
  </div>
);

const FindingRow: React.FC<{ rq: string; title: string; value: string; children: React.ReactNode }> = ({ rq, title, value, children }) => (
  <div className="py-3">
    <div className="flex items-baseline justify-between gap-4"><div className="min-w-0"><p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500">{rq}</p><h3 className="mt-0.5 text-xs font-semibold text-neutral-900 dark:text-white">{title}</h3></div><p className="shrink-0 font-mono text-sm font-semibold tracking-tight text-neutral-900 dark:text-white">{value}</p></div>
    <p className="mt-1 text-[11px] leading-snug text-neutral-500">{children}</p>
  </div>
);

const Rq7Finding: React.FC<{ agreement: ControlledMetricResult | undefined; coverage: ControlledMetricResult | undefined }> = ({ agreement, coverage }) => (
  <div className="py-3">
    <div><p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500">RQ7</p><h3 className="mt-0.5 text-xs font-semibold text-neutral-900 dark:text-white">DUAL_SWAP Mitigation</h3></div>
    <div className="mt-2 grid grid-cols-2 gap-4"><div><p className="text-[10px] text-neutral-500">Agreement</p><p className="mt-0.5 font-mono text-sm font-semibold text-neutral-900 dark:text-white">{agreement ? formatMetricValue(agreement) : 'Unavailable'}</p></div><div><p className="text-[10px] text-neutral-500">Coverage</p><p className="mt-0.5 font-mono text-sm font-semibold text-neutral-900 dark:text-white">{coverage ? formatMetricValue(coverage) : 'Unavailable'}</p></div></div>
    <p className="mt-2 text-[11px] leading-snug text-neutral-500">Higher agreement among retained decisions, lower valid coverage.</p>
  </div>
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

  return <div className="mx-auto max-w-[1400px] space-y-6 py-2 font-sans">
    <header className="flex flex-col gap-3 border-b border-neutral-200 pb-4 dark:border-neutral-800 sm:flex-row sm:items-end sm:justify-between"><div><h1 className="text-2xl font-serif tracking-tight text-neutral-900 dark:text-white">Final Scientific Synthesis</h1><p className="mt-1 max-w-3xl text-xs leading-relaxed text-neutral-600 dark:text-neutral-400">Executive summary of the final controlled RQ1–RQ7 evidence.</p></div><Link to="/controlled-results" className="inline-flex w-fit text-xs font-medium text-neutral-700 transition-colors hover:text-neutral-950 dark:text-neutral-300 dark:hover:text-white">View Controlled Experiments <span aria-hidden="true" className="ml-1">→</span></Link></header>
    {loading && <div className="border-y border-neutral-200 py-3 text-xs text-neutral-500 dark:border-neutral-800">Loading final controlled synthesis…</div>}
    {error && <div className="border-y border-neutral-200 py-3 text-xs text-neutral-500 dark:border-neutral-800">Final controlled synthesis unavailable. No alternate values are substituted: {error}</div>}
    {!loading && !error && !ready && <div className="border-y border-neutral-200 py-3 text-xs text-neutral-500 dark:border-neutral-800">Final controlled synthesis is not available: {data?.message ?? 'No controlled response.'}</div>}
    {ready && <>
      <section aria-label="Executive summary" className="grid divide-y divide-neutral-200 overflow-hidden rounded-lg border border-neutral-200 bg-neutral-50 sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-5 dark:divide-neutral-800 dark:border-neutral-800 dark:bg-[#0a0a0a]"><SummaryStat label="Human Alignment">{rq1 ? formatMetricValue(rq1) : 'Unavailable'}</SummaryStat><SummaryStat label="Consistency">{rq2 ? formatMetricValue(rq2) : 'Unavailable'}</SummaryStat><SummaryStat label="Position Sensitivity">{rq3 ? formatMetricValue(rq3) : 'Unavailable'}</SummaryStat><SummaryStat label="Source-Family">{rq6 ? formatMetricValue(rq6) : 'Unavailable'}</SummaryStat><SummaryStat label="Mitigation"><span className="text-sm">{rq7Agreement ? formatMetricValue(rq7Agreement) : 'Unavailable'} / {rq7Coverage ? formatMetricValue(rq7Coverage) : 'Unavailable'}</span></SummaryStat></section>
      <section aria-labelledby="research-findings-title"><h2 id="research-findings-title" className="text-sm font-semibold text-neutral-900 dark:text-white">Research Findings</h2><div className="mt-3 grid gap-x-8 gap-y-6 lg:grid-cols-2"><section aria-labelledby="reliability-title"><h3 id="reliability-title" className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">Reliability</h3><div className="mt-2 divide-y divide-neutral-200 border-y border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800"><FindingRow rq="RQ1" title="Human Alignment" value={rq1 ? formatMetricValue(rq1) : 'Unavailable'}>Agreement with human preference reference labels.</FindingRow><FindingRow rq="RQ2" title="Stochastic Consistency" value={rq2 ? formatMetricValue(rq2) : 'Unavailable'}>Repeated judgments were highly consistent.</FindingRow><FindingRow rq="RQ3" title="Position Sensitivity" value={rq3 ? formatMetricValue(rq3) : 'Unavailable'}>Decisive flip rate under answer-order swaps.</FindingRow></div></section><section aria-labelledby="effects-title"><h3 id="effects-title" className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">Controlled Effects &amp; Mitigation</h3><div className="mt-2 divide-y divide-neutral-200 border-y border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800"><FindingRow rq="RQ4" title="Redundant-Length" value={rq4 ? formatMetricValue(rq4) : 'Unavailable'}>Controlled redundant-length variant win rate.</FindingRow><FindingRow rq="RQ5" title="Presentation Format" value={rq5 ? formatMetricValue(rq5) : 'Unavailable'}>Controlled presentation-format variant win rate.</FindingRow><FindingRow rq="RQ6" title="Source-Family Preference" value={rq6 ? formatMetricValue(rq6) : 'Unavailable'}>{rq6 ? `${formatMetricCi(rq6)} · N = ${rq6.denominator ?? 'unavailable'} stable decisive · coverage ${rq6Coverage ? formatMetricValue(rq6Coverage) : 'unavailable'}. No clear uniform overall same-family preference; strong judge-level heterogeneity.` : 'Counterbalanced result unavailable.'}</FindingRow><Rq7Finding agreement={rq7Agreement} coverage={rq7Coverage} /></div></section></div></section>
    </>}
  </div>;
};

export default SynthesisPage;
