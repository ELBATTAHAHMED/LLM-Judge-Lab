import React from 'react';
import type { ControlledResultsResponse } from '../api/types';
import { EvidenceBadge } from './EvidenceBadge';
import { ControlledMetricCard } from './ControlledMetricCard';

export const ControlledEvidencePanel: React.FC<{ data: ControlledResultsResponse | null; loading: boolean; error: string | null }> = ({ data, loading, error }) => {
  if (loading) return <section className="rounded-lg border border-neutral-200 p-5 text-xs text-neutral-500 dark:border-neutral-800">Checking controlled evidence…</section>;
  if (error) return <section className="rounded-lg border border-neutral-200 p-5 text-xs text-neutral-500 dark:border-neutral-800">Controlled evidence status unavailable: {error}</section>;
  const empty = !data || data.status === 'NO_CONTROLLED_EVIDENCE';
  return <section className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 dark:border-neutral-800 dark:bg-[#0a0a0a]" aria-label="Controlled evidence status">
    <div className="flex items-center justify-between gap-3"><div><h2 className="text-base font-semibold">Controlled RQ1–RQ7 Evidence</h2><p className="mt-1 text-xs text-neutral-500">Frozen-protocol results only; legacy and sandbox data are never substituted.</p></div><EvidenceBadge evidenceClass={empty ? 'PLANNED' : 'CONTROLLED'} /></div>
    {empty ? <div className="mt-4 rounded border border-dashed border-neutral-300 p-4 text-sm dark:border-neutral-700"><strong>NO CONTROLLED EVIDENCE YET</strong><p className="mt-1 text-xs text-neutral-500">Controlled experiment is planned but has not yet been executed. Executed runs: {data?.executed_runs ?? 0}; passes: {data?.executed_passes ?? 0}.</p></div> : <div className="mt-4 grid gap-3 md:grid-cols-2">{data.results.map((metric) => <ControlledMetricCard key={`${metric.rq}-${metric.metric}-${metric.judge}-${metric.condition}`} metric={metric} />)}</div>}
  </section>;
};
