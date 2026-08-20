import React from 'react';
import type { ControlledResultsResponse } from '../api/types';
import { RQ_TITLES, rqInterpretation } from '../api/finalEvidence';
import { EvidenceBadge } from './EvidenceBadge';
import { ControlledMetricCard } from './ControlledMetricCard';

const RQ_ORDER = ['RQ1', 'RQ2', 'RQ3', 'RQ4', 'RQ5', 'RQ6', 'RQ7'];

export const ControlledEvidencePanel: React.FC<{ data: ControlledResultsResponse | null; loading: boolean; error: string | null }> = ({ data, loading, error }) => {
  if (loading) return <section className="rounded-lg border border-neutral-200 p-5 text-xs text-neutral-500 dark:border-neutral-800">Checking controlled evidence…</section>;
  if (error) return <section className="rounded-lg border border-neutral-200 p-5 text-xs text-neutral-500 dark:border-neutral-800">Controlled evidence unavailable. No legacy, pilot, or synthetic values are shown: {error}</section>;
  const empty = !data || data.status === 'NO_CONTROLLED_EVIDENCE';
  const pendingAnalysis = data?.status === 'CONTROLLED_RESULTS_PENDING_ANALYSIS';
  const metricsByRq = new Map(RQ_ORDER.map((rq) => [rq, (data?.results ?? []).filter((metric) => metric.rq === rq)]));
  const accounting = data?.accounting;

  return <section className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 dark:border-neutral-800 dark:bg-[#0a0a0a]" aria-label="Controlled evidence status">
    <div className="flex items-center justify-between gap-3"><div><h2 className="text-base font-semibold">Frozen Controlled RQ1–RQ7 Evidence</h2><p className="mt-1 text-xs text-neutral-500">Final CONTROLLED evidence only. PILOT and SUPERSEDED_CONTROLLED audit history are excluded from scientific metrics.</p></div><EvidenceBadge evidenceClass={empty ? 'PLANNED' : 'CONTROLLED'} /></div>
    {empty ? <div className="mt-4 rounded border border-dashed border-neutral-300 p-4 text-sm dark:border-neutral-700"><strong>NO CONTROLLED EVIDENCE</strong><p className="mt-1 text-xs text-neutral-500">No final controlled analysis is available. Executed runs: {data?.executed_runs ?? 0}; passes: {data?.executed_passes ?? 0}.</p></div> : pendingAnalysis ? <div className="mt-4 rounded border border-dashed border-neutral-300 p-4 text-sm dark:border-neutral-700"><strong>CONTROLLED ANALYSIS NOT AVAILABLE</strong><p className="mt-1 text-xs text-neutral-500">{data.message}</p></div> : <>
      {accounting && <div className="mt-4 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4"><div className="rounded border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-[#121212]"><strong>{accounting.planned_units.toLocaleString()}</strong><p className="mt-1 text-neutral-500">planned / accounted units</p></div><div className="rounded border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-[#121212]"><strong>{accounting.succeeded_units.toLocaleString()} SUCCEEDED</strong><p className="mt-1 text-neutral-500">{accounting.valid_partial_units.toLocaleString()} valid PARTIAL · {accounting.failed_units.toLocaleString()} terminal FAILED</p></div><div className="rounded border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-[#121212]"><strong>{accounting.valid_returned_passes.toLocaleString()} valid passes</strong><p className="mt-1 text-neutral-500">{accounting.failed_pass_slots.toLocaleString()} failed slots / {accounting.planned_pass_slots.toLocaleString()} planned</p></div><div className="rounded border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-[#121212]"><strong>{Object.keys(data.analysis_runs).length}/7 AnalysisRuns</strong><p className="mt-1 text-neutral-500">{accounting.pending_units} pending provider-eligible units</p></div></div>}
      <div className="mt-5 space-y-5">{RQ_ORDER.map((rq) => <section key={rq} aria-labelledby={`${rq}-heading`}><div className="mb-3"><h3 id={`${rq}-heading`} className="text-sm font-semibold">{rq} · {RQ_TITLES[rq]}</h3>{rqInterpretation(rq) && <p className="mt-1 text-xs text-neutral-500">{rqInterpretation(rq)}</p>}</div><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{metricsByRq.get(rq)?.map((metric, index) => <ControlledMetricCard key={`${metric.rq}-${metric.metric_key ?? metric.metric}-${metric.judge}-${metric.condition}-${index}`} metric={metric} />)}</div></section>)}</div>
    </>}
  </section>;
};
