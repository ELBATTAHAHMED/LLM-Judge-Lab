import React, { useState } from 'react';
import type { ControlledMetricResult, ControlledResultsResponse, MultiJudgeConsensusSecondary } from '../api/types';
import { formatMetricCi, formatMetricValue, metricLabel, RQ_TITLES, rqInterpretation } from '../api/finalEvidence';
import { EvidenceBadge } from './EvidenceBadge';

const RQ_ORDER = ['RQ1', 'RQ2', 'RQ3', 'RQ4', 'RQ5', 'RQ6', 'RQ7'];

const AccountingItem: React.FC<{ value: string; label: string }> = ({ value, label }) => <div className="min-w-0 border-l border-neutral-200 pl-3 first:border-l-0 first:pl-0 dark:border-neutral-800"><p className="font-mono text-sm font-semibold text-neutral-900 dark:text-white">{value}</p><p className="mt-0.5 text-[10px] text-neutral-500">{label}</p></div>;

const MetricCell: React.FC<{ metric: ControlledMetricResult }> = ({ metric }) => <article className="rounded-lg border border-neutral-200 bg-neutral-50 p-3 dark:border-neutral-800 dark:bg-[#0a0a0a]"><div className="flex items-start justify-between gap-2"><div className="min-w-0"><p className="text-xs font-semibold text-neutral-900 dark:text-white">{metricLabel(metric)}</p>{(metric.judge || metric.condition) && <p className="mt-0.5 truncate text-[10px] text-neutral-500">{metric.judge ?? 'Overall'}{metric.condition ? ` · ${metric.condition}` : ''}</p>}</div><span className="shrink-0 font-mono text-[10px] text-neutral-500">{metric.value === null ? 'NOT ESTIMABLE' : metric.status}</span></div><p className="mt-2 text-xl font-mono font-semibold tracking-tight text-neutral-900 dark:text-white">{formatMetricValue(metric)}</p><p className="mt-1 text-[10px] leading-snug text-neutral-500">{formatMetricCi(metric)} · {metric.denominator === null ? 'N unavailable' : `N = ${metric.denominator}`}</p></article>;

const CompactRows: React.FC<{ metrics: ControlledMetricResult[] }> = ({ metrics }) => <div className="overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800"><table className="w-full min-w-[460px] text-left text-xs"><thead className="bg-neutral-50 text-[10px] font-mono uppercase tracking-wider text-neutral-500 dark:bg-[#0a0a0a]"><tr><th className="px-3 py-2 font-medium">Metric</th><th className="px-3 py-2 font-medium">Value</th><th className="px-3 py-2 font-medium">CI / N</th></tr></thead><tbody className="divide-y divide-neutral-200 dark:divide-neutral-800">{metrics.map((metric, index) => <tr key={`${metric.metric_key ?? metric.metric}-${index}`}><td className="px-3 py-2 text-neutral-700 dark:text-neutral-300">{metricLabel(metric)}{metric.judge ? <span className="block text-[10px] text-neutral-500">{metric.judge}</span> : null}</td><td className="whitespace-nowrap px-3 py-2 font-mono font-semibold text-neutral-900 dark:text-white">{formatMetricValue(metric)}</td><td className="whitespace-nowrap px-3 py-2 text-[10px] text-neutral-500">{formatMetricCi(metric)} · {metric.denominator === null ? 'N unavailable' : `N = ${metric.denominator}`}</td></tr>)}</tbody></table></div>;

const formatPercent = (value: number): string => `${(value * 100).toFixed(2)}%`;
const formatPp = (value: number): string => `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)} pp`;

const MitigationMetricMatrix: React.FC<{ testId: string; metrics: Array<{ label: string; value: string }> }> = ({ testId, metrics }) => (
  <dl data-testid={testId} className="mt-3 divide-y divide-neutral-200 dark:divide-neutral-800">
    {Array.from({ length: Math.ceil(metrics.length / 2) }, (_, rowIndex) => {
      const row = metrics.slice(rowIndex * 2, rowIndex * 2 + 2);
      return <div key={row[0]?.label} className="grid grid-cols-2 py-2.5 first:pt-0 last:pb-0">
        {row.map((metric, columnIndex) => <div key={metric.label} className={columnIndex === 1 ? 'border-l border-neutral-200 pl-3 dark:border-neutral-800' : 'pr-3'}><dt className="text-[10px] text-neutral-500">{metric.label}</dt><dd className="mt-0.5 font-mono text-xs font-semibold text-neutral-900 dark:text-white">{metric.value}</dd></div>)}
      </div>;
    })}
  </dl>
);

const MitigationStrategyPanel: React.FC<{ ariaLabel: string; listId: string; role: 'PRIMARY' | 'SECONDARY'; name: string; family: string; metrics: Array<{ label: string; value: string }>; detail: React.ReactNode }> = ({ ariaLabel, listId, role, name, family, metrics, detail }) => <article aria-label={ariaLabel} className="flex h-full flex-col rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-[#0a0a0a]"><header data-testid={`${listId}-header`} className="min-h-[3.75rem] border-b border-neutral-200 pb-2 dark:border-neutral-800"><p className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">{role}</p><h3 className="mt-0.5 text-sm font-semibold text-neutral-900 dark:text-white">{name}</h3><p className="mt-1 text-[11px] text-neutral-500">{family}</p></header><MitigationMetricMatrix testId={`${listId}-matrix`} metrics={metrics} /><footer data-testid={`${listId}-footer`} className="mt-3 border-t border-neutral-200 pt-2 text-[11px] leading-snug text-neutral-500 dark:border-neutral-800">{detail}</footer></article>;

const Rq7Mitigations: React.FC<{ metrics: ControlledMetricResult[]; mitigation?: MultiJudgeConsensusSecondary }> = ({ metrics, mitigation }) => {
  const byKey = (key: string) => metrics.find((row) => row.metric_key === key);
  const baselineAgreement = byKey('baseline_agreement');
  const dualSwapAgreement = byKey('dual_swap_agreement');
  const agreementDelta = byKey('agreement_delta');
  const dualSwapCoverage = byKey('dual_swap_coverage');
  const stability = byKey('dual_swap_dual_pass_stability');
  const dualMetrics = [
    { label: 'Agreement', value: dualSwapAgreement ? formatMetricValue(dualSwapAgreement) : 'Unavailable' },
    { label: 'Comparator', value: baselineAgreement ? formatMetricValue(baselineAgreement) : 'Unavailable' },
    { label: 'Matched delta', value: agreementDelta ? formatMetricValue(agreementDelta) : 'Unavailable' },
    { label: 'Coverage', value: dualSwapCoverage ? formatMetricValue(dualSwapCoverage) : 'Unavailable' },
    { label: '95% CI', value: agreementDelta ? formatMetricCi(agreementDelta) : 'Unavailable' },
    { label: 'Matched N', value: agreementDelta?.denominator === null || agreementDelta === undefined ? 'Unavailable' : agreementDelta.denominator.toLocaleString() },
  ];
  const multiJudgeMetrics = mitigation ? [
    { label: 'Agreement', value: formatPercent(mitigation.agreement) },
    { label: 'Comparator', value: formatPercent(mitigation.comparator_agreement) },
    { label: 'Matched delta', value: formatPp(mitigation.matched_delta) },
    { label: 'Coverage', value: formatPercent(mitigation.coverage) },
    { label: '95% CI', value: `${formatPp(mitigation.ci_95.low)} to ${formatPp(mitigation.ci_95.high)}` },
    { label: 'Retained / planned', value: `${mitigation.retained_n.toLocaleString()} / ${mitigation.planned_n.toLocaleString()}` },
  ] : null;
  return <div className="mt-4 space-y-3"><h3 className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">Mitigation strategies</h3><div className="grid gap-3 sm:grid-cols-2"><MitigationStrategyPanel ariaLabel="DUAL_SWAP primary mitigation" listId="controlled-dual-swap" role="PRIMARY" name="DUAL_SWAP" family="Presentation-consistency filtering" metrics={dualMetrics} detail={<>Small matched point difference with a confidence interval crossing zero; dual-pass stability · {stability ? formatMetricValue(stability) : 'Unavailable'}; coverage is substantially reduced.</>} />{mitigation && multiJudgeMetrics && <MitigationStrategyPanel ariaLabel="Multi-Judge Consensus secondary mitigation" listId="controlled-multi-judge" role="SECONDARY" name="Multi-Judge Consensus" family="Cross-judge aggregation" metrics={multiJudgeMetrics} detail={<>Positive only against the equal-weight individual-judge comparator on the same retained consensus-covered pairs.</>} />}</div>{mitigation && <p className="border-t border-neutral-200 pt-3 text-[11px] leading-snug text-neutral-500 dark:border-neutral-800">DUAL_SWAP and Multi-Judge use different frozen units and comparators; their reported effects are separate operating-point results, not a direct head-to-head effect.</p>}</div>;
};

const Rq7Header: React.FC = () => <div className="max-w-3xl"><h2 id="selected-rq-title" className="text-lg font-semibold text-neutral-900 dark:text-white">RQ7 · {RQ_TITLES.RQ7}</h2><p className="mt-1.5 text-xs leading-relaxed text-neutral-700 dark:text-neutral-300">Two complementary approaches to improving judge reliability.</p><p className="mt-1 max-w-2xl text-[11px] leading-relaxed text-neutral-500">DUAL_SWAP filters presentation-sensitive decisions; Multi-Judge aggregates independent judge votes. Each is evaluated against its own frozen comparator.</p></div>;

const Rq6Summary: React.FC<{ metrics: ControlledMetricResult[] }> = ({ metrics }) => {
  const byKey = (key: string) => metrics.find((row) => row.metric_key === key);
  const primary = byKey('stable_same_family_preference');
  const secondary = [
    ['Stable-decisive coverage', byKey('valid_stable_decisive_coverage')],
    ['Order-sensitive disagreement', byKey('order_sensitive_disagreement')],
    ['Tie / abstention', byKey('tie_or_abstention_rate')],
  ] as const;
  const judges = [
    ['Claude 3 Haiku', byKey('judge:anthropic/claude-3-haiku:stable_same_family_preference')],
    ['GPT-4o-mini', byKey('judge:gpt-4o-mini:stable_same_family_preference')],
    ['Llama 3.3 70B', byKey('judge:meta-llama/llama-3.3-70b-instruct:stable_same_family_preference')],
  ] as const;
  return <div className="mt-4 max-w-3xl space-y-3"><div className="border-y border-neutral-200 py-3 dark:border-neutral-800"><p className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">Stable same-family preference</p><p className="mt-1 font-mono text-2xl font-semibold tracking-tight text-neutral-900 dark:text-white">{primary ? formatMetricValue(primary) : 'Unavailable'}</p><p className="mt-1 text-[11px] text-neutral-500">{primary ? `${formatMetricCi(primary)} · N = ${primary.denominator ?? 'unavailable'} stable decisive` : 'Counterbalanced result unavailable.'}</p></div><div className="grid gap-2 sm:grid-cols-2"><div className="rounded-lg border border-neutral-200 p-3 text-xs dark:border-neutral-800"><p className="font-medium text-neutral-900 dark:text-white">Per-judge stable preference</p><dl className="mt-2 space-y-1.5">{judges.map(([label, metric]) => <div key={label} className="flex justify-between gap-3"><dt className="text-neutral-500">{label}</dt><dd className="font-mono font-semibold text-neutral-900 dark:text-white">{metric ? formatMetricValue(metric) : 'Unavailable'}</dd></div>)}<div className="flex justify-between gap-3"><dt className="text-neutral-500">DeepSeek</dt><dd className="font-mono text-neutral-500">Not estimable — no eligible source data</dd></div></dl></div><div className="rounded-lg border border-neutral-200 p-3 text-xs dark:border-neutral-800"><p className="font-medium text-neutral-900 dark:text-white">Secondary metrics</p><dl className="mt-2 space-y-1.5">{secondary.map(([label, metric]) => <div key={label} className="flex justify-between gap-3"><dt className="text-neutral-500">{label}</dt><dd className="font-mono font-semibold text-neutral-900 dark:text-white">{metric ? formatMetricValue(metric) : 'Unavailable'}</dd></div>)}</dl></div></div><p className="text-[11px] leading-snug text-neutral-500">No clear uniform overall same-family preference; strong judge-level heterogeneity. Presentation order is counterbalanced, while source/content-quality confounding remains.</p></div>;
};

export const ControlledEvidencePanel: React.FC<{ data: ControlledResultsResponse | null; loading: boolean; error: string | null }> = ({ data, loading, error }) => {
  const [selectedRq, setSelectedRq] = useState('RQ1');
  if (loading) return <section className="rounded-lg border border-neutral-200 p-4 text-xs text-neutral-500 dark:border-neutral-800">Checking final RQ evidence…</section>;
  if (error) return <section className="rounded-lg border border-neutral-200 p-4 text-xs text-neutral-500 dark:border-neutral-800">Final results unavailable. No alternate evidence values are shown: {error}</section>;
  const empty = !data || data.status === 'NO_CONTROLLED_EVIDENCE';
  const pendingAnalysis = data?.status === 'CONTROLLED_RESULTS_PENDING_ANALYSIS';
  if (empty) return <section className="rounded-lg border border-dashed border-neutral-300 p-4 dark:border-neutral-700"><div className="flex items-center gap-2"><strong className="text-sm">NO CONTROLLED EVIDENCE</strong><EvidenceBadge evidenceClass="PLANNED" /></div><p className="mt-1 text-xs text-neutral-500">No final controlled analysis is available. Executed runs: {data?.executed_runs ?? 0}; passes: {data?.executed_passes ?? 0}.</p></section>;
  if (pendingAnalysis) return <section className="rounded-lg border border-dashed border-neutral-300 p-4 dark:border-neutral-700"><strong className="text-sm">CONTROLLED ANALYSIS NOT AVAILABLE</strong><p className="mt-1 text-xs text-neutral-500">{data.message}</p></section>;

  const metrics = data.results.filter((row) => row.rq === selectedRq);
  const byKey = (key: string) => metrics.find((row) => row.metric_key === key);
  const without = (keys: string[]) => metrics.filter((row) => !keys.includes(row.metric_key ?? ''));
  const primary = selectedRq === 'RQ1' ? [byKey('exact_agreement'), byKey('cohens_kappa')].filter(Boolean) as ControlledMetricResult[]
    : selectedRq === 'RQ2' ? [byKey('consistency')].filter(Boolean) as ControlledMetricResult[]
    : selectedRq === 'RQ3' ? ['paired_decisive_flip_rate', 'all_paired_disagreement_rate', 'slot_win_imbalance', 'incomplete_pairs'].map(byKey).filter(Boolean) as ControlledMetricResult[]
    : selectedRq === 'RQ4' || selectedRq === 'RQ5' ? ['variant_win_rate', 'original_win_rate', 'excluded_pair_count'].map(byKey).filter(Boolean) as ControlledMetricResult[]
    : [];
  const rq1Judges = metrics.filter((row) => row.metric_key?.startsWith('judge:'));
  const mainKeys = [...primary.map((row) => row.metric_key ?? ''), ...rq1Judges.map((row) => row.metric_key ?? '')];
  const detailMetrics = selectedRq === 'RQ7' ? metrics.filter((row) => !['baseline_agreement', 'dual_swap_agreement', 'agreement_delta', 'baseline_coverage', 'dual_swap_coverage', 'coverage_delta', 'dual_swap_dual_pass_stability'].includes(row.metric_key ?? '')) : without(mainKeys);

  return <section aria-label="Final controlled results" className="space-y-5">
    {data.accounting && <div className="grid gap-y-3 rounded-lg border border-neutral-200 bg-neutral-50 p-3 sm:grid-cols-2 sm:gap-x-3 lg:grid-cols-4 dark:border-neutral-800 dark:bg-[#0a0a0a]"><AccountingItem value={data.accounting.planned_units.toLocaleString()} label="units accounted" /><AccountingItem value={data.accounting.planned_pass_slots.toLocaleString()} label="pass slots" /><AccountingItem value={data.accounting.valid_returned_passes.toLocaleString()} label="valid returned" /><AccountingItem value={data.accounting.failed_pass_slots.toLocaleString()} label="non-valid / excluded" /><AccountingItem value={data.accounting.provider_error_pass_slots?.toLocaleString() ?? 'Unavailable'} label="provider errors" /><AccountingItem value={data.accounting.invalid_response_pass_slots?.toLocaleString() ?? 'Unavailable'} label="invalid responses" /><AccountingItem value={data.accounting.paired_excluded_valid_pass_slots?.toLocaleString() ?? 'Unavailable'} label="excluded valid paired slots" /><AccountingItem value={data.accounting.pending_units.toLocaleString()} label="pending" /></div>}
    <nav aria-label="Research question navigation" className="flex gap-1 overflow-x-auto border-b border-neutral-200 pb-2 dark:border-neutral-800">{RQ_ORDER.map((rq) => <button key={rq} type="button" onClick={() => setSelectedRq(rq)} className={`shrink-0 rounded px-3 py-1.5 text-xs font-mono transition-colors ${selectedRq === rq ? 'bg-neutral-900 text-white dark:bg-white dark:text-neutral-900' : 'text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-900'}`}>{rq}</button>)}</nav>
    <section aria-labelledby="selected-rq-title">{selectedRq === 'RQ7' ? <Rq7Header /> : <div className="flex flex-col gap-2 sm:flex-row sm:items-baseline sm:justify-between"><div><h2 id="selected-rq-title" className="text-lg font-semibold text-neutral-900 dark:text-white">{selectedRq} · {RQ_TITLES[selectedRq]}</h2>{rqInterpretation(selectedRq) && <p className="mt-1 max-w-3xl text-xs leading-relaxed text-neutral-500">{rqInterpretation(selectedRq)}</p>}</div>{selectedRq !== 'RQ6' && <span className="font-mono text-[10px] text-neutral-500">Overall controlled result</span>}</div>}
      {selectedRq === 'RQ6' ? <Rq6Summary metrics={metrics} /> : selectedRq === 'RQ7' ? <Rq7Mitigations metrics={metrics} mitigation={data.secondary_mitigations.multi_judge_consensus} /> : <><div className={`mt-4 grid gap-3 ${selectedRq === 'RQ2' ? 'max-w-sm' : 'sm:grid-cols-2 xl:grid-cols-3'}`}>{primary.map((metric) => <MetricCell key={metric.metric_key ?? metric.metric} metric={metric} />)}</div>{selectedRq === 'RQ1' && rq1Judges.length > 0 && <div className="mt-4"><h3 className="mb-2 text-xs font-semibold text-neutral-700 dark:text-neutral-300">Per-judge alignment</h3><CompactRows metrics={[...rq1Judges].sort((a, b) => (b.value ?? -Infinity) - (a.value ?? -Infinity))} /></div>}</>}
      {detailMetrics.length > 0 && <details className="mt-4 border-t border-neutral-200 pt-3 dark:border-neutral-800"><summary className="cursor-pointer text-xs font-medium text-neutral-700 dark:text-neutral-300">Additional reported metrics ({detailMetrics.length})</summary><div className="mt-3"><CompactRows metrics={detailMetrics} /></div></details>}
    </section>
  </section>;
};
