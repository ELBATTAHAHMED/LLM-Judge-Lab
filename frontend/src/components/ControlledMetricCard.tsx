import React from 'react';
import type { ControlledMetricResult } from '../api/types';
import { isFinalControlledEvidence } from '../api/evidence';

const percentage = (value: number | null): string => value === null ? 'Not estimable' : `${value < 0 ? '' : ''}${(value * 100).toFixed(1)}%`;

/** Display-only renderer for authoritative backend metrics; it contains no formulas. */
export const ControlledMetricCard: React.FC<{ metric: ControlledMetricResult }> = ({ metric }) => {
  if (!isFinalControlledEvidence(metric)) return null;
  const unavailable = metric.status === 'NOT_ESTIMABLE' || metric.status === 'NO_DATA' || metric.value === null;
  return <article className="rounded border border-neutral-200 p-4 dark:border-neutral-800">
    <div className="flex items-start justify-between gap-3"><div><h3 className="text-sm font-semibold">{metric.metric}</h3><p className="text-xs text-neutral-500">{metric.judge ?? 'All judges'} {metric.condition ? `· ${metric.condition}` : ''}</p></div><span className="font-mono text-[10px] text-neutral-500">{unavailable ? 'Not estimable' : metric.status}</span></div>
    <p className="mt-3 text-2xl font-mono">{percentage(metric.value)}</p>
    <p className="mt-1 text-xs text-neutral-500">{metric.ci_low === null || metric.ci_high === null ? 'CI not estimable' : `95% CI: ${percentage(metric.ci_low)}–${percentage(metric.ci_high)}`} · {metric.denominator === null ? 'N unavailable' : `N = ${metric.denominator}`} (eligible {metric.eligible_n}; analyzed {metric.analyzed_n})</p>
    <p className="mt-2 text-[11px] text-neutral-500">Ties {metric.ties} · Unknown {metric.unknowns} · Failures {metric.failures} · Excluded {metric.excluded}</p>
  </article>;
};
