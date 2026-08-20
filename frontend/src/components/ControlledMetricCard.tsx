import React from 'react';
import type { ControlledMetricResult } from '../api/types';
import { isFinalControlledEvidence } from '../api/evidence';
import { formatMetricCi, formatMetricValue, judgeLabel, metricLabel } from '../api/finalEvidence';

/** Display-only renderer for authoritative backend metrics; it contains no formulas. */
export const ControlledMetricCard: React.FC<{ metric: ControlledMetricResult }> = ({ metric }) => {
  if (!isFinalControlledEvidence(metric)) return null;
  const unavailable = metric.status === 'NOT_ESTIMABLE' || metric.status === 'NO_DATA' || metric.status === 'UNBALANCED_PRESENTATION' || metric.value === null;
  return <article className="rounded-lg border border-neutral-200 bg-neutral-50 p-3 dark:border-neutral-800 dark:bg-[#0a0a0a]">
    <div className="flex items-start justify-between gap-2"><div className="min-w-0"><h3 className="text-xs font-semibold text-neutral-900 dark:text-white">{metricLabel(metric)}</h3><p className="mt-0.5 truncate text-[11px] text-neutral-500">{judgeLabel(metric.judge)} {metric.condition ? `· ${metric.condition}` : ''}</p></div><span className="shrink-0 font-mono text-[10px] text-neutral-500">{unavailable ? 'NOT ESTIMABLE' : metric.status}</span></div>
    <p className="mt-2 text-xl font-mono font-semibold tracking-tight text-neutral-900 dark:text-white">{formatMetricValue(metric)}</p>
    <p className="mt-1 text-[11px] leading-snug text-neutral-500">{formatMetricCi(metric)} · {metric.denominator === null ? 'N unavailable' : `N = ${metric.denominator}`} (eligible {metric.eligible_n}; analyzed {metric.analyzed_n})</p>
    <p className="mt-1.5 text-[10px] text-neutral-500">Ties {metric.ties} · Unknown {metric.unknowns} · Failures {metric.failures} · Excluded {metric.excluded}</p>
  </article>;
};
