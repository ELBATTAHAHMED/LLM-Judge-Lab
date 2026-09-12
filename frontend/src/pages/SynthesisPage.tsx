import React from 'react';
import { Link } from 'react-router-dom';
import { useControlledResults } from '../api/client';
import { formatMetricCi, formatMetricValue } from '../api/finalEvidence';
import type { ControlledMetricResult, MultiJudgeConsensusSecondary } from '../api/types';
import {
  MAIN_QUESTION_BY_ID,
  MITIGATION_BY_ID,
  PRESENTATION_SECTION_BY_ID,
  RESEARCH_QUESTION_BY_ID,
  mitigationRoleLabel,
  presentationRoleLabel,
} from '../presentation/researchStructure';

const formatPercent = (value: number): string => `${(value * 100).toFixed(2)}%`;
const formatPp = (value: number): string => `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)} pp`;

const FindingRow: React.FC<{ rq: string; title: string; value: string; children: React.ReactNode; testId: string }> = ({ rq, title, value, children, testId }) => (
  <div data-testid={testId} className="min-w-0 border-t border-neutral-200 py-3 first:border-t-0 dark:border-neutral-800">
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3">
      <div className="min-w-0">
        <p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">{rq}</p>
        <h3 className="mt-0.5 text-xs font-semibold text-neutral-900 dark:text-white">{title}</h3>
      </div>
      <p className="max-w-[10rem] pt-4 text-right font-mono tabular-nums text-sm font-semibold tracking-tight text-neutral-900 dark:text-white">{value}</p>
    </div>
    <p className="mt-1.5 text-[11px] leading-relaxed text-neutral-600 dark:text-neutral-400">{children}</p>
  </div>
);

const PrincipalQuestionCard: React.FC<{ mainQuestion: 'MAIN_Q1' | 'MAIN_Q2' | 'MAIN_Q3'; children: React.ReactNode }> = ({ mainQuestion, children }) => {
  const question = MAIN_QUESTION_BY_ID[mainQuestion];
  return <section aria-label={`${question.displayLabel} ${question.displayTitle}`} className="flex h-full min-w-0 flex-col rounded-lg border border-neutral-200 bg-neutral-50 px-4 dark:border-neutral-800 dark:bg-[#0a0a0a]">
    <header className="border-b border-neutral-200 py-3 dark:border-neutral-800">
      <p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">{question.displayLabel}</p>
      <h2 className="mt-1 text-sm font-semibold text-neutral-900 dark:text-white">{question.displayTitle}</h2>
    </header>
    <div className="flex flex-1 flex-col">{children}</div>
  </section>;
};

const TradeOffRow: React.FC<{ label: string; baseline: ControlledMetricResult | undefined; intervention: ControlledMetricResult | undefined }> = ({ label, baseline, intervention }) => (
  <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-3 py-3">
    <dt className="text-[11px] text-neutral-600 dark:text-neutral-400">{label}</dt>
    <dd className="text-right font-mono text-sm font-semibold tabular-nums text-neutral-900 dark:text-white">{baseline ? formatMetricValue(baseline) : 'Unavailable'} <span className="px-0.5 text-neutral-500">→</span> {intervention ? formatMetricValue(intervention) : 'Unavailable'}</dd>
  </div>
);

const PrimaryMitigationSummary: React.FC<{ baselineAgreement: ControlledMetricResult | undefined; dualSwapAgreement: ControlledMetricResult | undefined; agreementDelta: ControlledMetricResult | undefined; baselineCoverage: ControlledMetricResult | undefined; dualSwapCoverage: ControlledMetricResult | undefined; coverageDelta: ControlledMetricResult | undefined }> = ({ baselineAgreement, dualSwapAgreement, agreementDelta, baselineCoverage, dualSwapCoverage, coverageDelta }) => (
  <div className="divide-y divide-neutral-200 dark:divide-neutral-800">
    <div className="py-3">
      <p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">RQ7 · {mitigationRoleLabel(MITIGATION_BY_ID.DUAL_SWAP)}</p>
      <h3 className="mt-0.5 text-xs font-semibold text-neutral-900 dark:text-white">{MITIGATION_BY_ID.DUAL_SWAP.displayTitle}</h3>
      <p className="mt-1 text-[11px] text-neutral-600 dark:text-neutral-400">{MITIGATION_BY_ID.DUAL_SWAP.family}</p>
    </div>
    <dl>
      <TradeOffRow label="Agreement" baseline={baselineAgreement} intervention={dualSwapAgreement} />
      <TradeOffRow label="Coverage" baseline={baselineCoverage} intervention={dualSwapCoverage} />
    </dl>
    <p className="py-3 text-[11px] leading-relaxed text-neutral-600 dark:text-neutral-400">Matched difference {agreementDelta ? formatMetricValue(agreementDelta) : 'Unavailable'} ({agreementDelta ? formatMetricCi(agreementDelta) : 'CI unavailable'}); coverage difference {coverageDelta ? formatMetricValue(coverageDelta) : 'Unavailable'}. The agreement change is small and uncertain while coverage is substantially reduced.</p>
  </div>
);

const SecondaryMitigationSummary: React.FC<{ multiJudge: MultiJudgeConsensusSecondary }> = ({ multiJudge }) => (
  <section aria-label="Additional Multi-Judge mitigation analysis" className="flex h-full min-w-0 flex-col rounded-lg border border-neutral-200 bg-neutral-50 px-4 dark:border-neutral-800 dark:bg-[#0a0a0a]">
    <header className="border-b border-neutral-200 py-3 dark:border-neutral-800">
      <p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">RQ7 · {mitigationRoleLabel(MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS)}</p>
      <h3 className="mt-1 text-xs font-semibold text-neutral-900 dark:text-white">{MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS.displayTitle}</h3>
      <p className="mt-1 text-[11px] text-neutral-600 dark:text-neutral-400">{MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS.family}; reported against its own equal-weight individual-judge comparator.</p>
    </header>
    <dl className="grid grid-cols-3 divide-x divide-neutral-200 py-3 dark:divide-neutral-800">
      <div className="min-w-0 pr-2"><dt className="text-[10px] text-neutral-600 dark:text-neutral-400">Agreement</dt><dd className="mt-1 font-mono text-xs font-semibold tabular-nums text-neutral-900 dark:text-white">{formatPercent(multiJudge.agreement)}</dd></div>
      <div className="min-w-0 px-2"><dt className="text-[10px] text-neutral-600 dark:text-neutral-400">Matched delta</dt><dd className="mt-1 font-mono text-xs font-semibold tabular-nums text-neutral-900 dark:text-white">{formatPp(multiJudge.matched_delta)}</dd></div>
      <div className="min-w-0 pl-2"><dt className="text-[10px] text-neutral-600 dark:text-neutral-400">Coverage</dt><dd className="mt-1 font-mono text-xs font-semibold tabular-nums text-neutral-900 dark:text-white">{formatPercent(multiJudge.coverage)}</dd></div>
    </dl>
  </section>
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
  const rq7BaselineAgreement = metric('RQ7', 'baseline_agreement');
  const rq7DualSwapAgreement = metric('RQ7', 'dual_swap_agreement');
  const rq7AgreementDelta = metric('RQ7', 'agreement_delta');
  const rq7BaselineCoverage = metric('RQ7', 'baseline_coverage');
  const rq7DualSwapCoverage = metric('RQ7', 'dual_swap_coverage');
  const rq7CoverageDelta = metric('RQ7', 'coverage_delta');
  const multiJudge = data?.secondary_mitigations.multi_judge_consensus;

  return <div className="mx-auto max-w-[1400px] space-y-6 py-2 font-sans">
    <header className="flex flex-col gap-3 border-b border-neutral-200 pb-4 dark:border-neutral-800 sm:flex-row sm:items-center sm:justify-between"><div><h1 className="text-2xl font-serif tracking-tight text-neutral-900 dark:text-white">Synthesis</h1><p className="mt-1 max-w-3xl text-xs leading-relaxed text-neutral-600 dark:text-neutral-400">A compact overview of the three central controlled-study findings.</p></div><Link to="/controlled-results" className="inline-flex w-fit shrink-0 items-center text-xs font-medium text-neutral-700 underline decoration-neutral-300 underline-offset-4 transition-colors hover:text-neutral-950 dark:text-neutral-300 dark:decoration-neutral-700 dark:hover:text-white">View detailed controlled evidence <span aria-hidden="true" className="ml-1">→</span></Link></header>
    {loading && <div className="border-y border-neutral-200 py-3 text-xs text-neutral-500 dark:border-neutral-800">Loading final controlled synthesis…</div>}
    {error && <div className="border-y border-neutral-200 py-3 text-xs text-neutral-500 dark:border-neutral-800">Final controlled synthesis unavailable. No alternate values are substituted: {error}</div>}
    {!loading && !error && !ready && <div className="border-y border-neutral-200 py-3 text-xs text-neutral-500 dark:border-neutral-800">Final controlled synthesis is not available: {data?.message ?? 'No controlled response.'}</div>}
    {ready && <>
      <section aria-label="Executive summary" className="border-y border-neutral-200 py-3 dark:border-neutral-800"><p className="text-sm font-medium tracking-tight text-neutral-900 dark:text-white">Human Alignment <span className="mx-2 text-neutral-400">→</span> Stability <span className="mx-2 text-neutral-400">→</span> Mitigation Trade-off</p></section>
      <section aria-labelledby="research-findings-title">
        <div className="border-b border-neutral-200 pb-2 dark:border-neutral-800"><p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">{PRESENTATION_SECTION_BY_ID.PRINCIPAL.shortPresentationLabel}</p><h2 id="research-findings-title" className="mt-1 text-sm font-semibold text-neutral-900 dark:text-white">{PRESENTATION_SECTION_BY_ID.PRINCIPAL.displayTitle}</h2></div>
        <div aria-label="Principal research questions" className="mt-3 grid grid-cols-1 gap-4 lg:auto-rows-fr lg:grid-cols-3">
          <PrincipalQuestionCard mainQuestion="MAIN_Q1"><div className="flex h-full flex-col"><FindingRow testId="finding-rq1" rq="RQ1" title={RESEARCH_QUESTION_BY_ID.RQ1.shortPresentationLabel} value={rq1 ? formatMetricValue(rq1) : 'Unavailable'}>Agreement with human preference reference labels; not an accuracy or ground-truth claim.</FindingRow><div className="mt-auto border-t border-neutral-200 py-3 dark:border-neutral-800"><p className="text-[11px] text-neutral-600 dark:text-neutral-400">Cohen’s κ</p><p className="mt-1 font-mono text-base font-semibold tabular-nums text-neutral-900 dark:text-white">{metric('RQ1', 'cohens_kappa') ? formatMetricValue(metric('RQ1', 'cohens_kappa')!) : 'Unavailable'}</p></div></div></PrincipalQuestionCard>
          <PrincipalQuestionCard mainQuestion="MAIN_Q2"><div className="divide-y divide-neutral-200 dark:divide-neutral-800"><FindingRow testId="finding-rq2" rq="RQ2" title={RESEARCH_QUESTION_BY_ID.RQ2.shortPresentationLabel} value={rq2 ? formatMetricValue(rq2) : 'Unavailable'}>Fixed-condition repeatability across strict complete-repetition cells.</FindingRow><FindingRow testId="finding-rq3" rq="RQ3" title={RESEARCH_QUESTION_BY_ID.RQ3.shortPresentationLabel} value={rq3 ? formatMetricValue(rq3) : 'Unavailable'}>Decisive flip rate after canonical answer-identity remapping under answer-order swaps.</FindingRow></div><p className="mt-auto border-t border-neutral-200 py-3 text-[11px] font-medium text-neutral-700 dark:border-neutral-800 dark:text-neutral-300">High repeatability does not imply complete robustness.</p></PrincipalQuestionCard>
          <PrincipalQuestionCard mainQuestion="MAIN_Q3"><PrimaryMitigationSummary baselineAgreement={rq7BaselineAgreement} dualSwapAgreement={rq7DualSwapAgreement} agreementDelta={rq7AgreementDelta} baselineCoverage={rq7BaselineCoverage} dualSwapCoverage={rq7DualSwapCoverage} coverageDelta={rq7CoverageDelta} /></PrincipalQuestionCard>
        </div>
      </section>
      <section aria-labelledby="supporting-analyses-title" className="border-t border-neutral-200 pt-5 dark:border-neutral-800">
        <div><p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">Supporting evidence</p><h2 id="supporting-analyses-title" className="mt-1 text-sm font-semibold text-neutral-900 dark:text-white">Supporting Analyses</h2></div>
        <div className="mt-3 grid grid-cols-1 gap-4 lg:auto-rows-fr lg:grid-cols-3">
          <section aria-label="Secondary analyses" className="flex h-full min-w-0 flex-col rounded-lg border border-neutral-200 bg-neutral-50 px-4 dark:border-neutral-800 dark:bg-[#0a0a0a]"><header className="border-b border-neutral-200 py-3 dark:border-neutral-800"><p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">{PRESENTATION_SECTION_BY_ID.SECONDARY.shortPresentationLabel}</p><h3 className="mt-1 text-xs font-semibold text-neutral-900 dark:text-white">Narrow controlled effects</h3></header><div className="divide-y divide-neutral-200 dark:divide-neutral-800"><FindingRow testId="finding-rq4" rq={`RQ4 · ${presentationRoleLabel(RESEARCH_QUESTION_BY_ID.RQ4)}`} title={RESEARCH_QUESTION_BY_ID.RQ4.shortPresentationLabel} value={rq4 ? formatMetricValue(rq4) : 'Unavailable'}>Stable controlled redundant-text variant wins among valid controlled pairs; no general verbosity inference.</FindingRow><FindingRow testId="finding-rq5" rq={`RQ5 · ${presentationRoleLabel(RESEARCH_QUESTION_BY_ID.RQ5)}`} title={RESEARCH_QUESTION_BY_ID.RQ5.shortPresentationLabel} value={rq5 ? formatMetricValue(rq5) : 'Unavailable'}>Stable controlled presentation/list-prefix variant wins among valid controlled pairs; no general presentation-bias inference.</FindingRow></div></section>
          <section aria-label="Exploratory analysis" className="flex h-full min-w-0 flex-col rounded-lg border border-neutral-200 bg-neutral-50 px-4 dark:border-neutral-800 dark:bg-[#0a0a0a]"><header className="border-b border-neutral-200 py-3 dark:border-neutral-800"><p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500 dark:text-neutral-400">{PRESENTATION_SECTION_BY_ID.EXPLORATORY.shortPresentationLabel}</p><h3 className="mt-1 text-xs font-semibold text-neutral-900 dark:text-white">Counterbalanced association</h3></header><FindingRow testId="finding-rq6" rq={`RQ6 · ${presentationRoleLabel(RESEARCH_QUESTION_BY_ID.RQ6)}`} title={RESEARCH_QUESTION_BY_ID.RQ6.shortPresentationLabel} value={rq6 ? formatMetricValue(rq6) : 'Unavailable'}>{rq6 ? `${formatMetricCi(rq6)} · N = ${rq6.denominator ?? 'unavailable'} stable decisive · coverage ${rq6Coverage ? formatMetricValue(rq6Coverage) : 'unavailable'}. Association only: no clear uniform overall same-family preference, with strong judge-level heterogeneity.` : 'Counterbalanced result unavailable.'}</FindingRow></section>
          {multiJudge && <SecondaryMitigationSummary multiJudge={multiJudge} />}
        </div>
        {multiJudge && <p className="mt-3 text-[11px] leading-relaxed text-neutral-600 dark:text-neutral-400">Each mitigation is evaluated against its own frozen comparator; the reported effects are not a direct head-to-head comparison.</p>}
      </section>
    </>}
  </div>;
};

export default SynthesisPage;
