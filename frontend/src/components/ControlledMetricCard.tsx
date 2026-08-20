import React from 'react';
import type { ControlledMetricResult } from '../api/types';
import { isFinalControlledEvidence } from '../api/evidence';
import { formatMetricCi, formatMetricValue, judgeLabel, metricLabel } from '../api/finalEvidence';

/** Display-only renderer for authoritative backend metrics; it contains no formulas. */
export const ControlledMetricCard: React.FC<{ metric: ControlledMetricResult }> = ({ metric }) => {
  if (!isFinalControlledEvidence(metric)) return null;
  const unavailable = metric.status === 'NOT_ESTIMABLE' || metric.status === 'NO_DATA' || metric.status === 'UNBALANCED_PRESENTATION' || metric.value === null;
  return <article className="rounded border border-neutral-200 p-4 dark:border-neutral-800">
    <div className="flex items-start justify-between gap-3"><div><h3 className="text-sm font-semibold">{metricLabel(metric)}</h3><p className="text-xs text-neutral-500">{judgeLabel(metric.judge)} {metric.condition ? `· ${metric.condition}` : ''}</p></div><span className="font-mono text-[10px] text-neutral-500">{unavailable ? 'NOT ESTIMABLE' : metric.status}</span></div>
    <p className="mt-3 text-2xl font-mono">{formatMetricValue(metric)}</p>
    <p className="mt-1 text-xs text-neutral-500">{formatMetricCi(metric)} · {metric.denominator === null ? 'N unavailable' : `N = ${metric.denominator}`} (eligible {metric.eligible_n}; analyzed {metric.analyzed_n})</p>
    <p className="mt-2 text-[11px] text-neutral-500">Ties {metric.ties} · Unknown {metric.unknowns} · Failures {metric.failures} · Excluded {metric.excluded}</p>
  </article>;
};
