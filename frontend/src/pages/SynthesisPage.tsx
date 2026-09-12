import React from 'react';
import { Link } from 'react-router-dom';
import { useControlledResults } from '../api/client';
import { formatMetricCi, formatMetricValue } from '../api/finalEvidence';
import type { ControlledMetricResult, MultiJudgeConsensusSecondary } from '../api/types';
import { MAIN_QUESTION_BY_ID, MITIGATION_BY_ID, RESEARCH_QUESTION_BY_ID, mitigationRoleLabel, presentationRoleLabel } from '../presentation/researchStructure';

const SummaryStat: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="min-w-0 px-4 py-3 last:col-span-2 lg:last:col-span-1">
    <p className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">{label}</p>
    <div className="mt-1 font-mono text-lg font-semibold tracking-tight text-neutral-900 dark:text-white">{children}</div>
  </div>
);

const FindingRow: React.FC<{ rq: string; title: string; value: string; children: React.ReactNode; testId: string }> = ({ rq, title, value, children, testId }) => (
  <div data-testid={testId} className="min-w-0 border-t border-neutral-200 py-3 first:border-t-0 dark:border-neutral-800">
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3"><div className="min-w-0"><p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500">{rq}</p><h3 className="mt-0.5 text-xs font-semibold text-neutral-900 dark:text-white">{title}</h3></div><p className="max-w-[10rem] pt-4 text-right font-mono tabular-nums text-sm font-semibold tracking-tight text-neutral-900 dark:text-white">{value}</p></div>
    <p className="mt-1.5 text-[11px] leading-relaxed text-neutral-600 dark:text-neutral-400">{children}</p>
  </div>
);

const formatPercent = (value: number): string => `${(value * 100).toFixed(2)}%`;
const formatPp = (value: number): string => `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)} pp`;

const SynthesisSummaryMetrics: React.FC<{ testId: string; metrics: Array<{ label: string; value: string }> }> = ({ testId, metrics }) => <dl data-testid={testId} className="my-4 grid grid-cols-3 divide-x divide-neutral-200 dark:divide-neutral-800">{metrics.map((metric, index) => <div key={metric.label} className={index === 0 ? 'min-w-0 pr-2' : 'min-w-0 px-2'}><dt className="text-[10px] text-neutral-600 dark:text-neutral-400">{metric.label}</dt><dd className="mt-1 break-words font-mono tabular-nums text-xs font-semibold text-neutral-900 dark:text-white">{metric.value}</dd></div>)}</dl>;

const SynthesisMitigationCard: React.FC<{ ariaLabel: string; listId: string; role: 'PRIMARY' | 'SECONDARY'; name: string; family: string; metrics: Array<{ label: string; value: string }>; footer: React.ReactNode }> = ({ ariaLabel, listId, role, name, family, metrics, footer }) => <section aria-label={ariaLabel} className="flex h-full flex-col rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-[#0a0a0a]"><header data-testid={`${listId}-header`} className="space-y-1"><p className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">{mitigationRoleLabel(role === 'PRIMARY' ? MITIGATION_BY_ID.DUAL_SWAP : MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS)}</p><h4 className="mt-0.5 text-xs font-semibold text-neutral-900 dark:text-white">{name}</h4><p className="text-[11px] text-neutral-600 dark:text-neutral-400">{family}</p></header><SynthesisSummaryMetrics testId={`${listId}-matrix`} metrics={metrics} /><footer data-testid={`${listId}-footer`} className="mt-auto border-t border-neutral-200 pt-3 text-[11px] leading-relaxed text-neutral-600 dark:border-neutral-800 dark:text-neutral-400">{footer}</footer></section>;

const Rq7Finding: React.FC<{ baselineAgreement: ControlledMetricResult | undefined; dualSwapAgreement: ControlledMetricResult | undefined; agreementDelta: ControlledMetricResult | undefined; baselineCoverage: ControlledMetricResult | undefined; dualSwapCoverage: ControlledMetricResult | undefined; coverageDelta: ControlledMetricResult | undefined; multiJudge?: MultiJudgeConsensusSecondary }> = ({ baselineAgreement, dualSwapAgreement, agreementDelta, baselineCoverage, dualSwapCoverage, coverageDelta, multiJudge }) => (
  <div aria-label="RQ7 Mitigation Strategies">
    <div><p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500">RQ7</p><h2 className="mt-0.5 text-sm font-semibold text-neutral-900 dark:text-white">Mitigation Strategies</h2><p className="mt-1 text-[11px] text-neutral-500">Two complementary mitigation families.</p></div>
    <div className="mt-3 grid gap-4 lg:grid-cols-2"><SynthesisMitigationCard ariaLabel="DUAL_SWAP primary synthesis finding" listId="dual-swap" role={MITIGATION_BY_ID.DUAL_SWAP.role} name={MITIGATION_BY_ID.DUAL_SWAP.displayTitle} family={MITIGATION_BY_ID.DUAL_SWAP.family} metrics={[{ label: 'Agreement', value: `${baselineAgreement ? formatMetricValue(baselineAgreement) : 'Unavailable'} → ${dualSwapAgreement ? formatMetricValue(dualSwapAgreement) : 'Unavailable'}` }, { label: 'Matched delta', value: agreementDelta ? formatMetricValue(agreementDelta) : 'Unavailable' }, { label: 'Coverage', value: `${baselineCoverage ? formatMetricValue(baselineCoverage) : 'Unavailable'} → ${dualSwapCoverage ? formatMetricValue(dualSwapCoverage) : 'Unavailable'}` }]} footer={<>Small, uncertain agreement change ({agreementDelta ? formatMetricCi(agreementDelta) : 'CI unavailable'}); coverage changes by {coverageDelta ? formatMetricValue(coverageDelta) : 'unavailable'}.</>} />{multiJudge && <SynthesisMitigationCard ariaLabel="Multi-Judge Consensus secondary synthesis finding" listId="multi-judge" role={MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS.role} name={MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS.displayTitle} family={MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS.family} metrics={[{ label: 'Agreement', value: formatPercent(multiJudge.agreement) }, { label: 'Matched delta', value: formatPp(multiJudge.matched_delta) }, { label: 'Coverage', value: formatPercent(multiJudge.coverage) }]} footer={<>Delta vs equal-weight individual-judge baseline.</>} />}</div>
    {multiJudge && <p className="mt-3 max-w-4xl text-[11px] leading-relaxed text-neutral-600 dark:text-neutral-400">Each mitigation is evaluated against its own frozen comparator; the reported effects are not a direct head-to-head comparison.</p>}
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
  const rq7DualSwapAgreement = metric('RQ7', 'dual_swap_agreement');
  const rq7BaselineAgreement = metric('RQ7', 'baseline_agreement');
  const rq7AgreementDelta = metric('RQ7', 'agreement_delta');
  const rq7BaselineCoverage = metric('RQ7', 'baseline_coverage');
  const rq7DualSwapCoverage = metric('RQ7', 'dual_swap_coverage');
  const rq7CoverageDelta = metric('RQ7', 'coverage_delta');
  const multiJudge = data?.secondary_mitigations.multi_judge_consensus;

  return <div className="mx-auto max-w-[1400px] space-y-6 py-2 font-sans">
    <header className="flex flex-col gap-3 border-b border-neutral-200 pb-4 dark:border-neutral-800 sm:flex-row sm:items-center sm:justify-between"><div><h1 className="text-2xl font-serif tracking-tight text-neutral-900 dark:text-white">Final Scientific Synthesis</h1><p className="mt-1 max-w-3xl text-xs leading-relaxed text-neutral-600 dark:text-neutral-400">Human alignment → multidimensional stability → mitigation agreement–coverage trade-off. Detailed RQ1–RQ7 evidence remains available.</p></div><Link to="/controlled-results" className="inline-flex w-fit shrink-0 items-center rounded border border-neutral-200 px-3 py-2 text-xs font-medium text-neutral-700 transition-colors hover:text-neutral-950 dark:border-neutral-800 dark:text-neutral-300 dark:hover:text-white">View Controlled Experiments <span aria-hidden="true" className="ml-1">→</span></Link></header>
    {loading && <div className="border-y border-neutral-200 py-3 text-xs text-neutral-500 dark:border-neutral-800">Loading final controlled synthesis…</div>}
    {error && <div className="border-y border-neutral-200 py-3 text-xs text-neutral-500 dark:border-neutral-800">Final controlled synthesis unavailable. No alternate values are substituted: {error}</div>}
    {!loading && !error && !ready && <div className="border-y border-neutral-200 py-3 text-xs text-neutral-500 dark:border-neutral-800">Final controlled synthesis is not available: {data?.message ?? 'No controlled response.'}</div>}
    {ready && <>
      <section aria-label="Executive summary" className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-neutral-200 bg-neutral-200 lg:grid-cols-3 dark:border-neutral-800 dark:bg-neutral-800 [&>div]:bg-neutral-50 dark:[&>div]:bg-[#0a0a0a]"><SummaryStat label={MAIN_QUESTION_BY_ID.MAIN_Q1.displayTitle}>{rq1 ? formatMetricValue(rq1) : 'Unavailable'}</SummaryStat><SummaryStat label={MAIN_QUESTION_BY_ID.MAIN_Q2.displayTitle}>{rq2 ? formatMetricValue(rq2) : 'Unavailable'}</SummaryStat><SummaryStat label={MAIN_QUESTION_BY_ID.MAIN_Q3.displayTitle}>{rq7AgreementDelta ? formatMetricValue(rq7AgreementDelta) : 'Unavailable'}</SummaryStat></section>
      <p className="border-l-2 border-neutral-400 pl-3 text-xs leading-relaxed text-neutral-700 dark:text-neutral-300">{rq1 ? formatMetricValue(rq1) : 'Unavailable'} human-reference agreement and {rq2 ? formatMetricValue(rq2) : 'Unavailable'} fixed-condition repeatability measure different properties. High repeatability does not imply strong human alignment or robustness to answer-order inversion.</p>
      <section aria-labelledby="research-findings-title">
        <h2 id="research-findings-title" className="text-sm font-semibold text-neutral-900 dark:text-white">Main research questions</h2>
        <div aria-label="Paired RQ1–RQ6 findings" className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2">
          <section aria-label="Human Agreement and Stability" className="min-w-0 rounded-lg border border-neutral-200 bg-neutral-50 px-4 dark:border-neutral-800 dark:bg-[#0a0a0a]">
            <h3 className="border-b border-neutral-200 py-3 text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-600 dark:border-neutral-800 dark:text-neutral-400">{MAIN_QUESTION_BY_ID.MAIN_Q1.displayLabel} · {MAIN_QUESTION_BY_ID.MAIN_Q1.displayTitle} / {MAIN_QUESTION_BY_ID.MAIN_Q2.displayLabel} · {MAIN_QUESTION_BY_ID.MAIN_Q2.displayTitle}</h3>
            <div className="divide-y divide-neutral-200 dark:divide-neutral-800">
              <FindingRow testId="finding-rq1" rq="RQ1" title={RESEARCH_QUESTION_BY_ID.RQ1.shortPresentationLabel} value={rq1 ? formatMetricValue(rq1) : 'Unavailable'}>Agreement with human preference reference labels.</FindingRow>
              <FindingRow testId="finding-rq2" rq="RQ2" title={RESEARCH_QUESTION_BY_ID.RQ2.shortPresentationLabel} value={rq2 ? formatMetricValue(rq2) : 'Unavailable'}>Fixed-condition repeatability across strict complete-repetition cells; not accuracy or a temperature-effects estimate.</FindingRow>
              <FindingRow testId="finding-rq3" rq="RQ3" title={RESEARCH_QUESTION_BY_ID.RQ3.shortPresentationLabel} value={rq3 ? formatMetricValue(rq3) : 'Unavailable'}>Decisive flip rate after canonical answer-identity remapping under order swaps.</FindingRow>
            </div>
          </section>
          <section aria-label="Supporting analyses" className="min-w-0 rounded-lg border border-neutral-200 bg-neutral-50 px-4 dark:border-neutral-800 dark:bg-[#0a0a0a]">
            <h3 className="border-b border-neutral-200 py-3 text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-600 dark:border-neutral-800 dark:text-neutral-400">Supporting analyses</h3>
            <div className="divide-y divide-neutral-200 dark:divide-neutral-800">
              <FindingRow testId="finding-rq4" rq={`RQ4 · ${presentationRoleLabel(RESEARCH_QUESTION_BY_ID.RQ4)}`} title={RESEARCH_QUESTION_BY_ID.RQ4.shortPresentationLabel} value={rq4 ? formatMetricValue(rq4) : 'Unavailable'}>Stable controlled redundant-text variant wins among valid controlled pairs; no general verbosity inference.</FindingRow>
              <FindingRow testId="finding-rq5" rq={`RQ5 · ${presentationRoleLabel(RESEARCH_QUESTION_BY_ID.RQ5)}`} title={RESEARCH_QUESTION_BY_ID.RQ5.shortPresentationLabel} value={rq5 ? formatMetricValue(rq5) : 'Unavailable'}>Stable controlled presentation/list-prefix variant wins among valid controlled pairs; no general presentation-bias inference.</FindingRow>
              <FindingRow testId="finding-rq6" rq={`RQ6 · ${presentationRoleLabel(RESEARCH_QUESTION_BY_ID.RQ6)}`} title={RESEARCH_QUESTION_BY_ID.RQ6.shortPresentationLabel} value={rq6 ? formatMetricValue(rq6) : 'Unavailable'}>{rq6 ? `${formatMetricCi(rq6)} · N = ${rq6.denominator ?? 'unavailable'} stable decisive · coverage ${rq6Coverage ? formatMetricValue(rq6Coverage) : 'unavailable'}. Association only: no clear uniform overall same-family preference, with strong judge-level heterogeneity.` : 'Counterbalanced result unavailable.'}</FindingRow>
            </div>
          </section>
        </div>
      </section>
      <section aria-labelledby="mitigation-category-title" className="space-y-3"><h2 id="mitigation-category-title" className="border-b border-neutral-200 pb-2 text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400 dark:border-neutral-800">{MAIN_QUESTION_BY_ID.MAIN_Q3.displayLabel} · {MAIN_QUESTION_BY_ID.MAIN_Q3.displayTitle}</h2><Rq7Finding baselineAgreement={rq7BaselineAgreement} dualSwapAgreement={rq7DualSwapAgreement} agreementDelta={rq7AgreementDelta} baselineCoverage={rq7BaselineCoverage} dualSwapCoverage={rq7DualSwapCoverage} coverageDelta={rq7CoverageDelta} multiJudge={multiJudge} /></section>
    </>}
  </div>;
};

export default SynthesisPage;
