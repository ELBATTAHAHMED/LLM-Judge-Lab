import React from 'react';
import { Link } from 'react-router-dom';
import { useControlledResults } from '../api/client';
import { formatMetricValue } from '../api/finalEvidence';
import type { ControlledMetricResult } from '../api/types';
import { EvidenceBadge } from '../components/EvidenceBadge';

const SummaryMetric: React.FC<{ label: string; metric: ControlledMetricResult | undefined; detail: string }> = ({ label, metric, detail }) => (
  <article className="rounded-lg border border-neutral-200 bg-neutral-50 p-3 dark:border-neutral-800 dark:bg-[#0a0a0a]">
    <p className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">{label}</p>
    <p className="mt-1 text-xl font-mono font-semibold tracking-tight text-neutral-900 dark:text-white">{metric ? formatMetricValue(metric) : 'Unavailable'}</p>
    <p className="mt-1 text-[11px] leading-snug text-neutral-500">{metric ? detail : 'Final controlled metric not available.'}</p>
  </article>
);

const Finding: React.FC<{ rq: string; children: React.ReactNode }> = ({ rq, children }) => (
  <li className="flex gap-2 text-xs leading-relaxed text-neutral-600 dark:text-neutral-400"><span className="shrink-0 font-mono text-[10px] font-semibold text-neutral-900 dark:text-neutral-200">{rq}</span><span>{children}</span></li>
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
  const rq7Agreement = metric('RQ7', 'agreement_delta');
  const rq7Coverage = metric('RQ7', 'coverage_delta');

  return <div className="mx-auto max-w-[1400px] space-y-5 py-2 font-sans">
    <header className="flex flex-col gap-3 border-b border-neutral-200 pb-4 dark:border-neutral-800 sm:flex-row sm:items-start sm:justify-between"><div><h1 className="text-2xl font-serif tracking-tight text-neutral-900 dark:text-white">Final Scientific Synthesis</h1><p className="mt-1 max-w-3xl text-xs leading-relaxed text-neutral-600 dark:text-neutral-400">Concise executive interpretation of the final controlled RQ1–RQ7 evidence.</p></div><Link to="/controlled-results" className="inline-flex w-fit items-center gap-2 rounded border border-neutral-200 px-2.5 py-1.5 text-[11px] font-medium text-neutral-700 transition-colors hover:bg-neutral-50 dark:border-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-900"><EvidenceBadge evidenceClass="CONTROLLED" /><span>Final Evidence: Frozen</span></Link></header>
    {loading && <div className="rounded-lg border border-neutral-200 p-4 text-xs text-neutral-500 dark:border-neutral-800">Loading final controlled synthesis…</div>}
    {error && <div className="rounded-lg border border-neutral-200 p-4 text-xs text-neutral-500 dark:border-neutral-800">Final controlled synthesis unavailable. No legacy values are substituted: {error}</div>}
    {!loading && !error && !ready && <div className="rounded-lg border border-neutral-200 p-4 text-xs text-neutral-500 dark:border-neutral-800">Final controlled synthesis is not available: {data?.message ?? 'No controlled response.'}</div>}
    {ready && <>
      <section aria-label="Headline findings" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><SummaryMetric label="RQ1 · Human Alignment" metric={rq1} detail="Agreement with human preference reference labels" /><SummaryMetric label="RQ2 · Consistency" metric={rq2} detail="Within-unit repeated-evaluation consistency" /><SummaryMetric label="RQ3 · Position Sensitivity" metric={rq3} detail="Paired decisive flip rate under answer-order swap" /><SummaryMetric label="RQ7 · Mitigation Trade-off" metric={rq7Agreement} detail={`Coverage change: ${rq7Coverage ? formatMetricValue(rq7Coverage) : 'unavailable'}`} /></section>
      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]"><div className="rounded-lg border border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-800 dark:bg-[#0a0a0a]"><h2 className="text-sm font-semibold text-neutral-900 dark:text-white">Research Findings</h2><ul className="mt-3 space-y-2.5"><Finding rq="RQ1">{rq1 ? `${formatMetricValue(rq1)} agreement with human preference reference labels; this is not an accuracy claim.` : 'No final metric available.'}</Finding><Finding rq="RQ2">{rq2 ? `${formatMetricValue(rq2)} consistency across the frozen repeated-evaluation protocol.` : 'No final metric available.'}</Finding><Finding rq="RQ3">{rq3 ? `${formatMetricValue(rq3)} paired decisive flips under controlled answer-order swaps.` : 'No final metric available.'}</Finding><Finding rq="RQ4–RQ5">{rq4 && rq5 ? `Controlled redundant-length variant win: ${formatMetricValue(rq4)}; controlled presentation-format variant win: ${formatMetricValue(rq5)}.` : 'Controlled variant metrics are unavailable.'}</Finding><Finding rq="RQ7">DUAL_SWAP increased agreement with human preference reference labels while reducing valid coverage.</Finding></ul></div><aside className="space-y-3"><div className="rounded-lg border border-dashed border-neutral-300 p-3 dark:border-neutral-700"><p className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">RQ6 limitation</p><p className="mt-1 font-mono text-sm font-semibold text-neutral-900 dark:text-white">NOT ESTIMABLE</p><p className="mt-1 text-[11px] leading-snug text-neutral-500">UNBALANCED_PRESENTATION — no numeric matched source-family preference effect is reported.</p></div><div className="rounded-lg border border-neutral-200 p-3 dark:border-neutral-800"><p className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">RQ7 trade-off</p><div className="mt-2 grid grid-cols-2 gap-2 text-xs"><div><p className="font-mono font-semibold text-neutral-900 dark:text-white">{rq7Agreement ? formatMetricValue(rq7Agreement) : 'Unavailable'}</p><p className="mt-0.5 text-[10px] text-neutral-500">Agreement</p></div><div><p className="font-mono font-semibold text-neutral-900 dark:text-white">{rq7Coverage ? formatMetricValue(rq7Coverage) : 'Unavailable'}</p><p className="mt-0.5 text-[10px] text-neutral-500">Coverage</p></div></div></div></aside></section>
    </>}
  </div>;
};

export default SynthesisPage;
