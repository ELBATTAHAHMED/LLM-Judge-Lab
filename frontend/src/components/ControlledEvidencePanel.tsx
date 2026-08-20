import React from 'react';
import type { ControlledResultsResponse } from '../api/types';
import { RQ_TITLES, rqInterpretation } from '../api/finalEvidence';
import { EvidenceBadge } from './EvidenceBadge';
import { ControlledMetricCard } from './ControlledMetricCard';

const RQ_ORDER = ['RQ1', 'RQ2', 'RQ3', 'RQ4', 'RQ5', 'RQ6', 'RQ7'];

const AccountingItem: React.FC<{ value: string; label: string }> = ({ value, label }) => (
  <div className="min-w-0 border-l border-neutral-200 pl-3 first:border-l-0 first:pl-0 dark:border-neutral-800"><p className="font-mono text-sm font-semibold text-neutral-900 dark:text-white">{value}</p><p className="mt-0.5 text-[10px] leading-snug text-neutral-500">{label}</p></div>
);

export const ControlledEvidencePanel: React.FC<{ data: ControlledResultsResponse | null; loading: boolean; error: string | null }> = ({ data, loading, error }) => {
  if (loading) return <section className="rounded-lg border border-neutral-200 p-4 text-xs text-neutral-500 dark:border-neutral-800">Checking controlled evidence…</section>;
  if (error) return <section className="rounded-lg border border-neutral-200 p-4 text-xs text-neutral-500 dark:border-neutral-800">Controlled evidence unavailable. No legacy, pilot, or synthetic values are shown: {error}</section>;
  const empty = !data || data.status === 'NO_CONTROLLED_EVIDENCE';
  const pendingAnalysis = data?.status === 'CONTROLLED_RESULTS_PENDING_ANALYSIS';
  const metricsByRq = new Map(RQ_ORDER.map((rq) => [rq, (data?.results ?? []).filter((metric) => metric.rq === rq)]));
  const accounting = data?.accounting;

  if (empty) return <section className="rounded-lg border border-dashed border-neutral-300 p-4 dark:border-neutral-700"><div className="flex items-center gap-2"><strong className="text-sm">NO CONTROLLED EVIDENCE</strong><EvidenceBadge evidenceClass="PLANNED" /></div><p className="mt-1 text-xs text-neutral-500">No final controlled analysis is available. Executed runs: {data?.executed_runs ?? 0}; passes: {data?.executed_passes ?? 0}.</p></section>;
  if (pendingAnalysis) return <section className="rounded-lg border border-dashed border-neutral-300 p-4 dark:border-neutral-700"><strong className="text-sm">CONTROLLED ANALYSIS NOT AVAILABLE</strong><p className="mt-1 text-xs text-neutral-500">{data.message}</p></section>;

  return <section aria-label="Controlled evidence status" className="space-y-5">
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="text-base font-semibold text-neutral-900 dark:text-white">Frozen Controlled RQ1–RQ7 Evidence</h2><p className="mt-1 text-xs text-neutral-500">Final CONTROLLED evidence only. PILOT and SUPERSEDED_CONTROLLED audit history are excluded from scientific metrics.</p></div><EvidenceBadge evidenceClass="CONTROLLED" /></div>
    {accounting && <div className="grid gap-y-3 rounded-lg border border-neutral-200 bg-neutral-50 p-3 sm:grid-cols-2 sm:gap-x-3 lg:grid-cols-5 dark:border-neutral-800 dark:bg-[#0a0a0a]"><AccountingItem value={accounting.planned_units.toLocaleString()} label="units accounted" /><AccountingItem value={accounting.planned_pass_slots.toLocaleString()} label="planned pass slots" /><AccountingItem value={accounting.valid_returned_passes.toLocaleString()} label="valid returned passes" /><AccountingItem value={accounting.failed_pass_slots.toLocaleString()} label="failed slots" /><AccountingItem value={accounting.pending_units.toLocaleString()} label="pending units" /></div>}
    <div className="space-y-5">{RQ_ORDER.map((rq) => { const metrics = metricsByRq.get(rq) ?? []; return <section key={rq} aria-labelledby={`${rq}-heading`} className="border-t border-neutral-200 pt-4 first:border-t-0 first:pt-0 dark:border-neutral-800"><div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between"><div><h3 id={`${rq}-heading`} className="text-sm font-semibold text-neutral-900 dark:text-white">{rq} · {RQ_TITLES[rq]}</h3>{rqInterpretation(rq) && <p className="mt-1 text-xs leading-relaxed text-neutral-500">{rqInterpretation(rq)}</p>}</div><span className="font-mono text-[10px] text-neutral-500">{metrics.length} metric{metrics.length === 1 ? '' : 's'}</span></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{metrics.map((metric, index) => <ControlledMetricCard key={`${metric.rq}-${metric.metric_key ?? metric.metric}-${metric.judge}-${metric.condition}-${index}`} metric={metric} />)}</div></section>; })}</div>
    <details className="border-t border-neutral-200 pt-3 text-xs dark:border-neutral-800"><summary className="cursor-pointer font-medium text-neutral-700 dark:text-neutral-300">Frozen evidence provenance</summary><p className="mt-2 text-neutral-500">{Object.keys(data.analysis_runs).length}/7 canonical AnalysisRuns selected by identity. Metric values are rendered directly from the controlled-results API.</p></details>
  </section>;
};
