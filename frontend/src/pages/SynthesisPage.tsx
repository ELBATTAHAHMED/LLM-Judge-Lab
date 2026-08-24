import React from 'react';
import { Link } from 'react-router-dom';
import { useControlledResults } from '../api/client';
import { formatMetricCi, formatMetricValue } from '../api/finalEvidence';
import type { ControlledMetricResult, MultiJudgeConsensusSecondary } from '../api/types';

const SummaryStat: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="min-w-0 p-3">
    <p className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">{label}</p>
    <div className="mt-1 font-mono text-lg font-semibold tracking-tight text-neutral-900 dark:text-white">{children}</div>
  </div>
);

const FindingRow: React.FC<{ rq: string; title: string; value: string; children: React.ReactNode; testId: string }> = ({ rq, title, value, children, testId }) => (
  <div data-testid={testId} className="min-h-[76px] border-t border-neutral-200 py-3 dark:border-neutral-800">
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4"><div className="min-w-0"><p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500">{rq}</p><h3 className="mt-0.5 text-xs font-semibold text-neutral-900 dark:text-white">{title}</h3></div><p className="max-w-[10rem] text-right font-mono text-sm font-semibold tracking-tight text-neutral-900 dark:text-white">{value}</p></div>
    <p className="mt-1 text-[11px] leading-snug text-neutral-500">{children}</p>
  </div>
);

const formatPercent = (value: number): string => `${(value * 100).toFixed(2)}%`;
const formatPp = (value: number): string => `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)} pp`;

const SynthesisStrategyMetric: React.FC<{ label: string; value: string }> = ({ label, value }) => <div><dt className="text-[10px] text-neutral-500">{label}</dt><dd className="mt-0.5 font-mono text-xs font-semibold text-neutral-900 dark:text-white">{value}</dd></div>;

const Rq7Finding: React.FC<{ baselineAgreement: ControlledMetricResult | undefined; dualSwapAgreement: ControlledMetricResult | undefined; agreementDelta: ControlledMetricResult | undefined; dualSwapCoverage: ControlledMetricResult | undefined; dualPassStability: ControlledMetricResult | undefined; multiJudge?: MultiJudgeConsensusSecondary }> = ({ baselineAgreement, dualSwapAgreement, agreementDelta, dualSwapCoverage, dualPassStability, multiJudge }) => (
  <div aria-label="RQ7 Mitigation Strategies">
    <div><p className="font-mono text-[10px] font-medium uppercase tracking-wider text-neutral-500">RQ7</p><h2 className="mt-0.5 text-sm font-semibold text-neutral-900 dark:text-white">Mitigation Strategies</h2><p className="mt-1 text-[11px] text-neutral-500">Two complementary mitigation families.</p></div>
    <div className="mt-3 grid gap-3 sm:grid-cols-2"><article aria-label="DUAL_SWAP primary synthesis finding" className="rounded-lg border border-neutral-200 p-3 dark:border-neutral-800"><p className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">Primary</p><h4 className="mt-0.5 text-xs font-semibold text-neutral-900 dark:text-white">DUAL_SWAP</h4><p className="mt-1 text-[11px] text-neutral-500">Presentation-consistency filtering</p><dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2"><SynthesisStrategyMetric label="Agreement" value={dualSwapAgreement ? formatMetricValue(dualSwapAgreement) : 'Unavailable'} /><SynthesisStrategyMetric label="Comparator" value={baselineAgreement ? formatMetricValue(baselineAgreement) : 'Unavailable'} /><SynthesisStrategyMetric label="Matched delta" value={agreementDelta ? formatMetricValue(agreementDelta) : 'Unavailable'} /><SynthesisStrategyMetric label="Coverage" value={dualSwapCoverage ? formatMetricValue(dualSwapCoverage) : 'Unavailable'} /><SynthesisStrategyMetric label="95% CI" value={agreementDelta ? formatMetricCi(agreementDelta) : 'Unavailable'} /><SynthesisStrategyMetric label="Matched N" value={agreementDelta?.denominator === null || agreementDelta === undefined ? 'Unavailable' : agreementDelta.denominator.toLocaleString()} /></dl><p className="mt-3 text-[11px] leading-snug text-neutral-500">Dual-pass stability · {dualPassStability ? formatMetricValue(dualPassStability) : 'Unavailable'}</p></article>{multiJudge && <article aria-label="Multi-Judge Consensus secondary synthesis finding" className="rounded-lg border border-neutral-200 p-3 dark:border-neutral-800"><p className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">Secondary</p><h4 className="mt-0.5 text-xs font-semibold text-neutral-900 dark:text-white">Multi-Judge Consensus</h4><p className="mt-1 text-[11px] text-neutral-500">Cross-judge aggregation</p><dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2"><SynthesisStrategyMetric label="Agreement" value={formatPercent(multiJudge.agreement)} /><SynthesisStrategyMetric label="Comparator" value={formatPercent(multiJudge.comparator_agreement)} /><SynthesisStrategyMetric label="Matched delta" value={formatPp(multiJudge.matched_delta)} /><SynthesisStrategyMetric label="Coverage" value={formatPercent(multiJudge.coverage)} /><SynthesisStrategyMetric label="95% CI" value={`${formatPp(multiJudge.ci_95.low)} to ${formatPp(multiJudge.ci_95.high)}`} /><SynthesisStrategyMetric label="Retained / planned" value={`${multiJudge.retained_n.toLocaleString()} / ${multiJudge.planned_n.toLocaleString()}`} /></dl><p className="mt-3 text-[11px] leading-snug text-neutral-500">vs equal-weight individual-judge baseline on the same retained pairs.</p></article>}</div>
    {multiJudge && <p className="mt-3 text-[11px] leading-snug text-neutral-500">Each mitigation is evaluated against its own frozen comparator; the reported effects are not a direct head-to-head comparison.</p>}
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
  const rq7BaselineAgreement = metric('RQ7', 'baseline_agreement');
  const rq7DualSwapAgreement = metric('RQ7', 'dual_swap_agreement');
  const rq7AgreementDelta = metric('RQ7', 'agreement_delta');
  const rq7DualSwapCoverage = metric('RQ7', 'dual_swap_coverage');
  const rq7DualPassStability = metric('RQ7', 'dual_swap_dual_pass_stability');
  const multiJudge = data?.secondary_mitigations.multi_judge_consensus;

  return <div className="mx-auto max-w-[1400px] space-y-6 py-2 font-sans">
    <header className="flex flex-col gap-3 border-b border-neutral-200 pb-4 dark:border-neutral-800 sm:flex-row sm:items-end sm:justify-between"><div><h1 className="text-2xl font-serif tracking-tight text-neutral-900 dark:text-white">Final Scientific Synthesis</h1><p className="mt-1 max-w-3xl text-xs leading-relaxed text-neutral-600 dark:text-neutral-400">Executive summary of the final controlled RQ1–RQ7 evidence.</p></div><Link to="/controlled-results" className="inline-flex w-fit text-xs font-medium text-neutral-700 transition-colors hover:text-neutral-950 dark:text-neutral-300 dark:hover:text-white">View Controlled Experiments <span aria-hidden="true" className="ml-1">→</span></Link></header>
    {loading && <div className="border-y border-neutral-200 py-3 text-xs text-neutral-500 dark:border-neutral-800">Loading final controlled synthesis…</div>}
    {error && <div className="border-y border-neutral-200 py-3 text-xs text-neutral-500 dark:border-neutral-800">Final controlled synthesis unavailable. No alternate values are substituted: {error}</div>}
    {!loading && !error && !ready && <div className="border-y border-neutral-200 py-3 text-xs text-neutral-500 dark:border-neutral-800">Final controlled synthesis is not available: {data?.message ?? 'No controlled response.'}</div>}
    {ready && <>
      <section aria-label="Executive summary" className="grid divide-y divide-neutral-200 overflow-hidden rounded-lg border border-neutral-200 bg-neutral-50 sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-5 dark:divide-neutral-800 dark:border-neutral-800 dark:bg-[#0a0a0a]"><SummaryStat label="Human Alignment">{rq1 ? formatMetricValue(rq1) : 'Unavailable'}</SummaryStat><SummaryStat label="Consistency">{rq2 ? formatMetricValue(rq2) : 'Unavailable'}</SummaryStat><SummaryStat label="Position Sensitivity">{rq3 ? formatMetricValue(rq3) : 'Unavailable'}</SummaryStat><SummaryStat label="Source-Family">{rq6 ? formatMetricValue(rq6) : 'Unavailable'}</SummaryStat><SummaryStat label="Mitigation"><span className="text-sm">2 complementary strategies</span></SummaryStat></section>
      <section aria-labelledby="research-findings-title"><h2 id="research-findings-title" className="text-sm font-semibold text-neutral-900 dark:text-white">Research Findings</h2><div className="mt-3 grid grid-cols-1 gap-x-8 md:grid-cols-2"><h3 className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">Reliability</h3><h3 className="mt-4 text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500 md:mt-0">Controlled Effects</h3></div><div aria-label="Paired RQ1–RQ6 findings" className="mt-2 grid grid-cols-1 gap-x-8 md:grid-cols-2"><FindingRow testId="finding-rq1" rq="RQ1" title="Human Alignment" value={rq1 ? formatMetricValue(rq1) : 'Unavailable'}>Agreement with human preference reference labels.</FindingRow><FindingRow testId="finding-rq4" rq="RQ4" title="Redundant-Length" value={rq4 ? formatMetricValue(rq4) : 'Unavailable'}>Controlled redundant-length variant win rate.</FindingRow><FindingRow testId="finding-rq2" rq="RQ2" title="Stochastic Consistency" value={rq2 ? formatMetricValue(rq2) : 'Unavailable'}>Repeated judgments were highly consistent.</FindingRow><FindingRow testId="finding-rq5" rq="RQ5" title="Presentation Format" value={rq5 ? formatMetricValue(rq5) : 'Unavailable'}>Controlled presentation-format variant win rate.</FindingRow><FindingRow testId="finding-rq3" rq="RQ3" title="Position Sensitivity" value={rq3 ? formatMetricValue(rq3) : 'Unavailable'}>Decisive flip rate under answer-order swaps.</FindingRow><FindingRow testId="finding-rq6" rq="RQ6" title="Source-Family Preference" value={rq6 ? formatMetricValue(rq6) : 'Unavailable'}>{rq6 ? `${formatMetricCi(rq6)} · N = ${rq6.denominator ?? 'unavailable'} stable decisive · coverage ${rq6Coverage ? formatMetricValue(rq6Coverage) : 'unavailable'}. No clear uniform overall same-family preference; strong judge-level heterogeneity.` : 'Counterbalanced result unavailable.'}</FindingRow></div></section>
      <section aria-labelledby="mitigation-category-title" className="space-y-3 border-t border-neutral-200 pt-5 dark:border-neutral-800"><h2 id="mitigation-category-title" className="text-[10px] font-mono font-medium uppercase tracking-wider text-neutral-500">Mitigation</h2><Rq7Finding baselineAgreement={rq7BaselineAgreement} dualSwapAgreement={rq7DualSwapAgreement} agreementDelta={rq7AgreementDelta} dualSwapCoverage={rq7DualSwapCoverage} dualPassStability={rq7DualPassStability} multiJudge={multiJudge} /></section>
    </>}
  </div>;
};

export default SynthesisPage;
