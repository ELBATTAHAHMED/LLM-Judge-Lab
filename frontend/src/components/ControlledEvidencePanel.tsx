import React, { useState } from 'react';
import type { ControlledMetricResult, ControlledResultsResponse, MultiJudgeConsensusSecondary } from '../api/types';
import { formatMetricCi, formatMetricValue, metricLabel, rqInterpretation } from '../api/finalEvidence';
import { MAIN_QUESTION_BY_ID, MITIGATION_BY_ID, PRESENTATION_SECTION_BY_ID, RESEARCH_QUESTION_BY_ID, mitigationRoleLabel, presentationRoleLabel, type InternalRqId } from '../presentation/researchStructure';
import { EvidenceBadge } from './EvidenceBadge';

const AccountingItem: React.FC<{ value: string; label: string }> = ({ value, label }) => <div className="min-w-0"><p className="font-mono tabular-nums text-sm font-semibold text-neutral-900 dark:text-white">{value}</p><p className="mt-0.5 text-[10px] text-neutral-600 dark:text-neutral-400">{label}</p></div>;

const MetricCell: React.FC<{ metric: ControlledMetricResult; label?: string }> = ({ metric, label }) => <article className="min-w-0 rounded-lg border border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-800 dark:bg-[#0a0a0a]"><div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><p className="text-xs font-semibold text-neutral-900 dark:text-white">{label ?? metricLabel(metric)}</p>{(metric.judge || metric.condition) && <p className="mt-0.5 break-words text-[10px] text-neutral-600 dark:text-neutral-400">{metric.judge ?? 'Overall'}{metric.condition ? ` · ${metric.condition}` : ''}</p>}</div><span className="shrink-0 font-mono text-[10px] text-neutral-600 dark:text-neutral-400">{metric.value === null ? 'NOT ESTIMABLE' : metric.status}</span></div><p className="mt-3 text-xl font-mono tabular-nums font-semibold tracking-tight text-neutral-900 dark:text-white">{formatMetricValue(metric)}</p><p className="mt-1 text-[10px] leading-snug text-neutral-500">{formatMetricCi(metric)} · {metric.denominator === null ? 'N unavailable' : `N = ${metric.denominator}`}</p></article>;

const CompactRows: React.FC<{ metrics: ControlledMetricResult[] }> = ({ metrics }) => <div className="overflow-x-auto rounded-lg border border-neutral-200 focus-visible:outline-2 focus-visible:outline-offset-2 dark:border-neutral-800" tabIndex={0} role="region" aria-label="Reported metrics table"><table className="w-full min-w-[460px] text-left text-xs"><thead className="bg-neutral-50 text-[10px] text-neutral-600 dark:bg-[#0a0a0a] dark:text-neutral-400"><tr><th scope="col" className="px-4 py-2.5 font-medium">Metric</th><th scope="col" className="px-4 py-2.5 font-medium">Value</th><th scope="col" className="px-4 py-2.5 font-medium">CI / N</th></tr></thead><tbody className="divide-y divide-neutral-200 dark:divide-neutral-800">{metrics.map((metric, index) => <tr key={`${metric.metric_key ?? metric.metric}-${index}`} className="align-top hover:bg-neutral-50 dark:hover:bg-neutral-900/40"><td className="px-4 py-2.5 text-neutral-700 dark:text-neutral-300">{metricLabel(metric)}{metric.judge ? <span className="block text-[10px] text-neutral-600 dark:text-neutral-400">{metric.judge}</span> : null}</td><td className="whitespace-nowrap px-4 py-2.5 font-mono font-semibold text-neutral-900 dark:text-white">{formatMetricValue(metric)}</td><td className="whitespace-nowrap px-4 py-2.5 text-[10px] text-neutral-600 dark:text-neutral-400">{formatMetricCi(metric)} · {metric.denominator === null ? 'N unavailable' : `N = ${metric.denominator}`}</td></tr>)}</tbody></table></div>;

const formatPercent = (value: number): string => `${(value * 100).toFixed(2)}%`;
const formatPp = (value: number): string => `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)} pp`;

const MitigationMetricMatrix: React.FC<{ testId: string; metrics: Array<{ label: string; value: string }> }> = ({ testId, metrics }) => (
  <dl data-testid={testId} className="grid grid-cols-2 gap-x-5 gap-y-4 sm:grid-cols-3">
    {metrics.map((metric) => <div key={metric.label} className="min-w-0">
      <dt className="text-[11px] text-neutral-600 dark:text-neutral-400">{metric.label}</dt>
      <dd className={`mt-1 break-words font-mono tabular-nums font-semibold tracking-tight text-neutral-900 dark:text-white ${metric.label === 'Agreement' ? 'text-lg' : 'text-xs'}`}>{metric.value}</dd>
    </div>)}
  </dl>
);

const MitigationStrategyPanel: React.FC<{ ariaLabel: string; listId: string; role: 'PRIMARY' | 'SECONDARY'; name: string; family: string; metrics: Array<{ label: string; value: string }>; detail: React.ReactNode; emphasis: 'PRIMARY' | 'SECONDARY' }> = ({ ariaLabel, listId, role, name, family, metrics, detail, emphasis }) => (
  <article aria-label={ariaLabel} className={`min-w-0 rounded-lg border border-neutral-200 dark:border-neutral-800 ${emphasis === 'PRIMARY' ? 'bg-white dark:bg-[#0a0a0a]' : 'bg-neutral-50 dark:bg-neutral-900/30'}`}>
    <div className="grid lg:grid-cols-[14rem_minmax(0,1fr)]">
      <header data-testid={`${listId}-header`} className="border-b border-neutral-200 p-4 dark:border-neutral-800 lg:border-b-0 lg:border-r">
        <p className="text-[10px] font-medium tracking-wide text-neutral-600 dark:text-neutral-400">{mitigationRoleLabel(role === 'PRIMARY' ? MITIGATION_BY_ID.DUAL_SWAP : MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS)}</p>
        <h3 className="mt-2 text-sm font-semibold text-neutral-900 dark:text-white">{name}</h3>
        <p className="mt-1 text-[11px] leading-relaxed text-neutral-600 dark:text-neutral-400">{family}</p>
      </header>
      <div className="p-4"><MitigationMetricMatrix testId={`${listId}-matrix`} metrics={metrics} /></div>
    </div>
    <footer data-testid={`${listId}-footer`} className="border-t border-neutral-200 px-4 py-3 text-[11px] leading-relaxed text-neutral-600 dark:border-neutral-800 dark:text-neutral-400">{detail}</footer>
  </article>
);

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
  return <div className="mt-4 space-y-5">
    <section aria-label="Primary mitigation analysis">
      <div className="mb-2"><p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">{MAIN_QUESTION_BY_ID.MAIN_Q3.displayLabel}</p><h3 className="mt-1 text-xs font-semibold text-neutral-900 dark:text-white">Primary mitigation analysis</h3></div>
      <MitigationStrategyPanel ariaLabel="DUAL_SWAP primary mitigation" listId="controlled-dual-swap" role={MITIGATION_BY_ID.DUAL_SWAP.role} name={MITIGATION_BY_ID.DUAL_SWAP.displayTitle} family={MITIGATION_BY_ID.DUAL_SWAP.family} metrics={dualMetrics} detail={<>Small matched point difference with a confidence interval crossing zero; dual-pass stability · {stability ? formatMetricValue(stability) : 'Unavailable'}; coverage is substantially reduced.</>} emphasis="PRIMARY" />
    </section>
    {mitigation && multiJudgeMetrics && <section aria-label="Additional mitigation analysis" className="border-t border-neutral-200 pt-4 dark:border-neutral-800"><div className="mb-2"><p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">{PRESENTATION_SECTION_BY_ID.ADDITIONAL_MITIGATION.shortPresentationLabel}</p><h3 className="mt-1 text-xs font-semibold text-neutral-900 dark:text-white">{PRESENTATION_SECTION_BY_ID.ADDITIONAL_MITIGATION.displayTitle}</h3><p className="mt-1 text-[11px] leading-relaxed text-neutral-600 dark:text-neutral-400">Secondary/exploratory evidence against its own comparator; it is not a competing operating point for DUAL_SWAP.</p></div><MitigationStrategyPanel ariaLabel="Multi-Judge Consensus secondary mitigation" listId="controlled-multi-judge" role={MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS.role} name={MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS.displayTitle} family={MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS.family} metrics={multiJudgeMetrics} detail={<>Positive only against the equal-weight individual-judge comparator on the same retained consensus-covered pairs.</>} emphasis="SECONDARY" /></section>}
    {mitigation && <p className="text-[11px] leading-relaxed text-neutral-600 dark:text-neutral-400">DUAL_SWAP and Multi-Judge use different frozen units and comparators; their reported effects are separate operating-point results, not a direct head-to-head effect.</p>}
  </div>;
};

const Rq7Header: React.FC = () => <div className="max-w-3xl"><p className="font-mono text-[10px] uppercase tracking-wider text-neutral-500">{MAIN_QUESTION_BY_ID.MAIN_Q3.displayLabel} · {MAIN_QUESTION_BY_ID.MAIN_Q3.displayTitle}</p><h2 id="selected-rq-title" className="text-lg font-semibold text-neutral-900 dark:text-white">RQ7 · {RESEARCH_QUESTION_BY_ID.RQ7.displayTitle}</h2><p className="mt-1.5 text-xs leading-relaxed text-neutral-700 dark:text-neutral-300">DUAL_SWAP is the main agreement–coverage analysis. Multi-Judge is secondary/exploratory mitigation evidence against its own comparator.</p></div>;

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
  return (
    <div className="mt-4 space-y-3">
      <div className="grid gap-4 lg:grid-cols-2">
        <section aria-label="Overall source-family result" className="min-w-0 rounded-lg border border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-[#0a0a0a]">
          <div className="p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="text-xs font-semibold text-neutral-900 dark:text-white">Stable same-family preference</h3>
              {primary && <span className="text-[10px] font-mono text-neutral-600 dark:text-neutral-400">{primary.value === null ? 'NOT ESTIMABLE' : primary.status}</span>}
            </div>
            {primary ? <>
              {(primary.judge || primary.condition) && <p className="mt-0.5 break-words text-[10px] text-neutral-600 dark:text-neutral-400">{primary.judge ?? 'Overall'}{primary.condition ? ` · ${primary.condition}` : ''}</p>}
              <p className="mt-3 font-mono text-xl font-semibold tabular-nums tracking-tight text-neutral-900 dark:text-white">{formatMetricValue(primary)}</p>
              <p className="mt-1 text-[11px] text-neutral-600 dark:text-neutral-400">{formatMetricCi(primary)} · {primary.denominator === null ? 'N unavailable' : `N = ${primary.denominator}`}</p>
            </> : <p className="mt-3 text-xs text-neutral-500">Counterbalanced result unavailable.</p>}
          </div>
          <div className="border-t border-neutral-200 px-4 py-3 dark:border-neutral-800">
            <h3 className="text-xs font-medium text-neutral-900 dark:text-white">Secondary metrics</h3>
            <dl className="mt-2 space-y-2">
              {secondary.map(([label, metric]) => <div key={label} className="flex items-baseline justify-between gap-4 text-xs">
                <dt className="text-neutral-600 dark:text-neutral-400">{label}</dt>
                <dd className="shrink-0 font-mono font-semibold tabular-nums text-neutral-900 dark:text-white">{metric ? formatMetricValue(metric) : 'Unavailable'}</dd>
              </div>)}
            </dl>
          </div>
        </section>
        <section aria-label="Per-judge stable preference" className="min-w-0 rounded-lg border border-neutral-200 dark:border-neutral-800">
          <h3 className="border-b border-neutral-200 px-4 py-3 text-xs font-semibold text-neutral-900 dark:border-neutral-800 dark:text-white">Per-judge stable preference</h3>
          <dl className="divide-y divide-neutral-200 px-4 dark:divide-neutral-800">
            {judges.map(([label, metric]) => <div key={label} className="flex items-baseline justify-between gap-4 py-3 text-xs">
              <dt className="text-neutral-600 dark:text-neutral-400">{label}</dt>
              <dd className="shrink-0 font-mono text-sm font-semibold tabular-nums text-neutral-900 dark:text-white">{metric ? formatMetricValue(metric) : 'Unavailable'}</dd>
            </div>)}
            <div className="flex items-baseline justify-between gap-4 py-3 text-xs">
              <dt className="text-neutral-600 dark:text-neutral-400">DeepSeek</dt>
              <dd className="max-w-[12rem] text-right text-[11px] leading-relaxed text-neutral-600 dark:text-neutral-400">Not estimable — no eligible source data</dd>
            </div>
          </dl>
        </section>
      </div>
      <p className="text-[11px] leading-relaxed text-neutral-600 dark:text-neutral-400">No clear uniform overall same-family preference; strong judge-level heterogeneity. Presentation order is counterbalanced, while source/content-quality confounding remains.</p>
    </div>
  );
};

const NavigationButton: React.FC<{ rq: InternalRqId; selectedRq: InternalRqId; onSelect: (rq: InternalRqId) => void; detail?: string }> = ({ rq, selectedRq, onSelect, detail }) => (
  <button type="button" onClick={() => onSelect(rq)} aria-label={rq} aria-pressed={selectedRq === rq} aria-controls="controlled-rq-content" title={RESEARCH_QUESTION_BY_ID[rq].displayTitle} className={`flex w-full flex-col rounded-md border px-3 py-2 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 ${selectedRq === rq ? 'border-neutral-900 bg-neutral-900 text-white dark:border-neutral-700 dark:bg-neutral-800 dark:text-white' : 'border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300 hover:bg-white dark:border-neutral-800 dark:bg-[#111] dark:text-neutral-300 dark:hover:bg-neutral-900/40'}`}>
    <span className="font-mono text-xs font-semibold">{rq}</span>
    <span className={`mt-0.5 text-[10px] leading-snug ${selectedRq === rq ? 'text-neutral-200 dark:text-neutral-300' : 'text-neutral-500 dark:text-neutral-400'}`}>{detail ?? RESEARCH_QUESTION_BY_ID[rq].shortPresentationLabel}</span>
  </button>
);

const NavigationGroup: React.FC<{ label: string; title: string; children: React.ReactNode; ariaLabel: string; subdued?: boolean }> = ({ label, title, children, ariaLabel, subdued = false }) => (
  <section aria-label={ariaLabel} className={`min-w-0 rounded-lg border p-3 ${subdued ? 'border-neutral-200 bg-white dark:border-neutral-800 dark:bg-[#0a0a0a]' : 'border-neutral-300 bg-white dark:border-neutral-700 dark:bg-[#111]'}`}>
    <header className="border-b border-neutral-200 pb-2 dark:border-neutral-800">
      <p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">{label}</p>
      <h3 className="mt-1 text-xs font-semibold text-neutral-900 dark:text-white">{title}</h3>
    </header>
    <div className="mt-3 space-y-2">{children}</div>
  </section>
);

const ResearchQuestionNavigation: React.FC<{ selectedRq: InternalRqId; onSelect: (rq: InternalRqId) => void }> = ({ selectedRq, onSelect }) => (
  <nav aria-label="Research question navigation" className="space-y-5 rounded-lg border border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-800 dark:bg-[#0a0a0a]">
    <section aria-labelledby="principal-navigation-title">
      <div className="border-b border-neutral-200 pb-2 dark:border-neutral-800">
        <p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">{PRESENTATION_SECTION_BY_ID.PRINCIPAL.shortPresentationLabel}</p>
        <h2 id="principal-navigation-title" className="mt-1 text-xs font-semibold text-neutral-900 dark:text-white">{PRESENTATION_SECTION_BY_ID.PRINCIPAL.displayTitle}</h2>
      </div>
      <div className="mt-3 grid grid-cols-1 items-start gap-3 md:grid-cols-3">
        <NavigationGroup ariaLabel={`${MAIN_QUESTION_BY_ID.MAIN_Q1.displayLabel} ${MAIN_QUESTION_BY_ID.MAIN_Q1.displayTitle}`} label={MAIN_QUESTION_BY_ID.MAIN_Q1.displayLabel} title={MAIN_QUESTION_BY_ID.MAIN_Q1.displayTitle}>
          <NavigationButton rq="RQ1" selectedRq={selectedRq} onSelect={onSelect} />
        </NavigationGroup>
        <NavigationGroup ariaLabel={`${MAIN_QUESTION_BY_ID.MAIN_Q2.displayLabel} ${MAIN_QUESTION_BY_ID.MAIN_Q2.displayTitle}`} label={MAIN_QUESTION_BY_ID.MAIN_Q2.displayLabel} title={MAIN_QUESTION_BY_ID.MAIN_Q2.displayTitle}>
          <NavigationButton rq="RQ2" selectedRq={selectedRq} onSelect={onSelect} />
          <NavigationButton rq="RQ3" selectedRq={selectedRq} onSelect={onSelect} />
        </NavigationGroup>
        <NavigationGroup ariaLabel={`${MAIN_QUESTION_BY_ID.MAIN_Q3.displayLabel} ${MAIN_QUESTION_BY_ID.MAIN_Q3.displayTitle}`} label={MAIN_QUESTION_BY_ID.MAIN_Q3.displayLabel} title={MAIN_QUESTION_BY_ID.MAIN_Q3.displayTitle}>
          <NavigationButton rq="RQ7" selectedRq={selectedRq} onSelect={onSelect} detail={`Primary · ${MITIGATION_BY_ID.DUAL_SWAP.displayTitle}`} />
        </NavigationGroup>
      </div>
    </section>
    <section aria-labelledby="supporting-navigation-title" className="border-t border-neutral-200 pt-4 dark:border-neutral-800">
      <div>
        <p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">Supporting controlled analyses</p>
        <h2 id="supporting-navigation-title" className="mt-1 text-xs font-semibold text-neutral-900 dark:text-white">Secondary, exploratory, and additional mitigation evidence</h2>
      </div>
      <div className="mt-3 grid grid-cols-1 items-start gap-3 md:grid-cols-3">
        <NavigationGroup ariaLabel="Secondary analyses" label={PRESENTATION_SECTION_BY_ID.SECONDARY.shortPresentationLabel} title={PRESENTATION_SECTION_BY_ID.SECONDARY.displayTitle} subdued>
          <NavigationButton rq="RQ4" selectedRq={selectedRq} onSelect={onSelect} />
          <NavigationButton rq="RQ5" selectedRq={selectedRq} onSelect={onSelect} />
        </NavigationGroup>
        <NavigationGroup ariaLabel="Exploratory analysis" label={PRESENTATION_SECTION_BY_ID.EXPLORATORY.shortPresentationLabel} title={PRESENTATION_SECTION_BY_ID.EXPLORATORY.displayTitle} subdued>
          <NavigationButton rq="RQ6" selectedRq={selectedRq} onSelect={onSelect} />
        </NavigationGroup>
        <NavigationGroup ariaLabel="Additional mitigation navigation" label={PRESENTATION_SECTION_BY_ID.ADDITIONAL_MITIGATION.shortPresentationLabel} title={PRESENTATION_SECTION_BY_ID.ADDITIONAL_MITIGATION.displayTitle} subdued>
          <button type="button" onClick={() => onSelect('RQ7')} aria-pressed={selectedRq === 'RQ7'} aria-controls="controlled-rq-content" className={`flex w-full flex-col rounded-md border px-3 py-2 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 ${selectedRq === 'RQ7' ? 'border-neutral-900 bg-neutral-900 text-white dark:border-neutral-700 dark:bg-neutral-800 dark:text-white' : 'border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300 hover:bg-white dark:border-neutral-800 dark:bg-[#111] dark:text-neutral-300 dark:hover:bg-neutral-900/40'}`}>
            <span className="font-mono text-xs font-semibold">RQ7</span>
            <span className={`mt-0.5 text-[10px] leading-snug ${selectedRq === 'RQ7' ? 'text-neutral-200 dark:text-neutral-300' : 'text-neutral-500 dark:text-neutral-400'}`}>{MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS.displayTitle} · Secondary</span>
          </button>
        </NavigationGroup>
      </div>
    </section>
  </nav>
);

export const ControlledEvidencePanel: React.FC<{ data: ControlledResultsResponse | null; loading: boolean; error: string | null }> = ({ data, loading, error }) => {
  const [selectedRq, setSelectedRq] = useState<InternalRqId>('RQ1');
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
  const rq2AliasKeys = selectedRq === 'RQ2'
    ? metrics.filter((row) => row.metric_key === 'strict_complete_repetition_consistency' || row.metric_key?.endsWith(':strict_complete_repetition_consistency')).map((row) => row.metric_key ?? '')
    : [];
  const mainKeys = [...primary.map((row) => row.metric_key ?? ''), ...rq1Judges.map((row) => row.metric_key ?? ''), ...rq2AliasKeys];
  const detailMetrics = selectedRq === 'RQ7' ? metrics.filter((row) => !['baseline_agreement', 'dual_swap_agreement', 'agreement_delta', 'baseline_coverage', 'dual_swap_coverage', 'coverage_delta', 'dual_swap_dual_pass_stability'].includes(row.metric_key ?? '')) : without(mainKeys);

  return <section aria-label="Final controlled results" className="space-y-5">
    {data.accounting && <section aria-label="Execution summary" className="rounded-lg border border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-800 dark:bg-[#0a0a0a]">
      <h2 className="text-xs font-semibold text-neutral-900 dark:text-white">Execution summary</h2>
      <p className="mt-1 text-[11px] leading-relaxed text-neutral-600 dark:text-neutral-400">Database-wide accounting · includes historical and superseded lineages, not just the final analysis population.</p>
      <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 lg:grid-cols-4">
        <AccountingItem value={data.accounting.planned_units.toLocaleString()} label="all persisted controlled units" />
        <AccountingItem value={data.accounting.planned_pass_slots.toLocaleString()} label="pass slots" />
        <AccountingItem value={data.accounting.valid_returned_passes.toLocaleString()} label="valid returned" />
        <AccountingItem value={data.accounting.failed_pass_slots.toLocaleString()} label="non-valid / excluded" />
      </div>
      <details className="mt-3 border-t border-neutral-200 pt-2 text-xs dark:border-neutral-800">
        <summary className="cursor-pointer py-1 focus-visible:outline-2 focus-visible:outline-offset-2 text-neutral-600 dark:text-neutral-400">Accounting details · {data.accounting.pending_units.toLocaleString()} pending</summary>
        <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 lg:grid-cols-4">
          <AccountingItem value={data.accounting.provider_error_pass_slots?.toLocaleString() ?? 'Unavailable'} label="provider errors" />
          <AccountingItem value={data.accounting.invalid_response_pass_slots?.toLocaleString() ?? 'Unavailable'} label="invalid responses" />
          <AccountingItem value={data.accounting.paired_excluded_valid_pass_slots?.toLocaleString() ?? 'Unavailable'} label="excluded valid paired slots" />
          <AccountingItem value={data.accounting.pending_units.toLocaleString()} label="pending" />
        </div>
        <p className="mt-3 text-neutral-500">Final RQ estimates below use pinned authoritative AnalysisRuns.</p>
      </details>
    </section>}
    <ResearchQuestionNavigation selectedRq={selectedRq} onSelect={setSelectedRq} />
    <section id="controlled-rq-content" aria-labelledby="selected-rq-title" className="min-w-0">{selectedRq === 'RQ7' ? <Rq7Header /> : <div className="flex flex-col gap-2 sm:flex-row sm:items-baseline sm:justify-between"><div><p className="font-mono text-[10px] uppercase tracking-wider text-neutral-500">{presentationRoleLabel(RESEARCH_QUESTION_BY_ID[selectedRq])}{RESEARCH_QUESTION_BY_ID[selectedRq].parentMainQuestion ? ` · ${MAIN_QUESTION_BY_ID[RESEARCH_QUESTION_BY_ID[selectedRq].parentMainQuestion].displayLabel}: ${MAIN_QUESTION_BY_ID[RESEARCH_QUESTION_BY_ID[selectedRq].parentMainQuestion].displayTitle}` : ''}</p><h2 id="selected-rq-title" className="text-lg font-semibold text-neutral-900 dark:text-white">{selectedRq} · {RESEARCH_QUESTION_BY_ID[selectedRq].displayTitle}</h2>{rqInterpretation(selectedRq) && <p className="mt-1 max-w-3xl text-xs leading-relaxed text-neutral-600 dark:text-neutral-400">{rqInterpretation(selectedRq)}</p>}</div>{selectedRq !== 'RQ6' && <span className="font-mono text-[10px] text-neutral-600 dark:text-neutral-400">Overall controlled result</span>}</div>}
      {selectedRq === 'RQ6' ? <Rq6Summary metrics={metrics} /> : selectedRq === 'RQ7' ? <Rq7Mitigations metrics={metrics} mitigation={data.secondary_mitigations.multi_judge_consensus} /> : <><div className={`mt-4 grid gap-3 ${selectedRq === 'RQ2' ? 'max-w-sm' : primary.length === 4 ? 'sm:grid-cols-2 xl:grid-cols-4' : primary.length === 2 ? 'sm:grid-cols-2' : 'sm:grid-cols-2 xl:grid-cols-3'}`}>{primary.map((metric) => <MetricCell key={metric.metric_key ?? metric.metric} metric={metric} />)}</div>{selectedRq === 'RQ1' && rq1Judges.length > 0 && <div className="mt-4"><h3 className="mb-2 text-xs font-semibold text-neutral-700 dark:text-neutral-300">Per-judge alignment</h3><CompactRows metrics={[...rq1Judges].sort((a, b) => (b.value ?? -Infinity) - (a.value ?? -Infinity))} /></div>}</>}
      {detailMetrics.length > 0 && <details className="mt-4 border-t border-neutral-200 pt-3 dark:border-neutral-800"><summary className="cursor-pointer py-1 text-xs font-medium focus-visible:outline-2 focus-visible:outline-offset-2 text-neutral-700 dark:text-neutral-300">Additional reported metrics ({detailMetrics.length})</summary><div className="mt-3"><CompactRows metrics={detailMetrics} /></div></details>}
    </section>
  </section>;
};
