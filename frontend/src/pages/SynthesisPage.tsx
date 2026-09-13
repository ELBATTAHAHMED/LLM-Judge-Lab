import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { useControlledResults } from '../api/client';
import { formatMetricCi, formatMetricValue } from '../api/finalEvidence';
import { MAIN_QUESTION_BY_ID, MITIGATION_BY_ID, PRESENTATION_SECTION_BY_ID, RESEARCH_QUESTION_BY_ID, mitigationRoleLabel, presentationRoleLabel, type MainQuestionId, type InternalRqId } from '../presentation/researchStructure';

const muted = 'text-xs leading-relaxed text-neutral-600 dark:text-neutral-400';
const number = 'font-mono font-semibold tracking-tight tabular-nums text-neutral-900 dark:text-white';

const Question: React.FC<{ id: MainQuestionId; children: React.ReactNode }> = ({ id, children }) => {
  const question = MAIN_QUESTION_BY_ID[id];
  return <section aria-label={`${question.displayLabel} ${question.displayTitle}`} className={`min-w-0 rounded-lg border border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-[#0a0a0a] ${id === 'MAIN_Q2' ? 'lg:col-span-2' : id === 'MAIN_Q3' ? 'lg:col-span-3' : ''}`}>
    <header className="flex items-baseline justify-between gap-3 border-b border-neutral-200 px-4 py-3 dark:border-neutral-800">
      <div><p className="text-[10px] font-medium text-neutral-600 dark:text-neutral-400">{question.displayLabel}</p>
      <h2 className="mt-1 text-sm font-semibold text-neutral-900 dark:text-white">{question.displayTitle}</h2></div>
      <p className="shrink-0 font-mono text-[10px] text-neutral-500 dark:text-neutral-400">{question.internalRqIds.join(' / ')}</p>
    </header>
    <div className={`min-w-0 p-4 ${id === 'MAIN_Q3' ? 'grid items-start gap-x-6 gap-y-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]' : ''}`}>{children}</div>
  </section>;
};

const Finding: React.FC<{ rq: InternalRqId; value: React.ReactNode; children: React.ReactNode; supporting?: boolean }> = ({ rq, value, children, supporting }) => <article data-testid={`finding-${rq.toLowerCase()}`} className="min-w-0">
  <p className="text-[10px] text-neutral-500 dark:text-neutral-400">{rq}{supporting ? ` · ${presentationRoleLabel(RESEARCH_QUESTION_BY_ID[rq])}` : ''}</p>
  <h3 className="mt-1 text-xs font-semibold text-neutral-900 dark:text-white">{RESEARCH_QUESTION_BY_ID[rq].shortPresentationLabel}</h3>
  <p className={`mt-3 ${supporting ? 'text-lg' : 'text-xl'} ${number}`}>{value}</p>
  <p className={`mt-2 ${muted}`}>{children}</p>
</article>;

export const SynthesisPage: React.FC = () => {
  const { data, loading, error } = useControlledResults();
  const metric = (rq: string, key: string) => data?.results.find(row => row.rq === rq && row.metric_key === key);
  const value = (rq: string, key: string) => { const result = metric(rq, key); return result ? formatMetricValue(result) : 'Unavailable'; };
  const fraction = (rq: string, key: string) => { const result = metric(rq, key); return result?.numerator != null && result.denominator != null ? `${result.numerator} / ${result.denominator}` : 'Unavailable'; };
  const ready = data?.status === 'CONTROLLED_RESULTS_AVAILABLE';
  const rq6 = metric('RQ6', 'stable_same_family_preference');
  const rq6Coverage = metric('RQ6', 'valid_stable_decisive_coverage');
  const agreementDelta = metric('RQ7', 'agreement_delta');
  const multiJudge = data?.secondary_mitigations.multi_judge_consensus;
  const percent = (n: number) => `${(n * 100).toFixed(2)}%`;
  const pp = (n: number) => `${n >= 0 ? '+' : ''}${(n * 100).toFixed(2)} pp`;

  return <div className="mx-auto max-w-[1400px] space-y-5 py-2 font-sans">
    <header className="flex flex-col gap-3 border-b border-neutral-200 pb-4 dark:border-neutral-800 sm:flex-row sm:items-center sm:justify-between">
      <div><h1 className="text-2xl font-serif tracking-tight text-neutral-900 dark:text-white">Synthesis</h1><p className={`mt-1 ${muted}`}>A compact overview of the three central controlled-study findings.</p></div>
      <Link to="/controlled-results" className="inline-flex w-fit shrink-0 items-center gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 text-xs font-medium text-neutral-700 transition-colors hover:border-neutral-300 hover:bg-white hover:text-neutral-950 dark:border-neutral-800 dark:bg-[#0a0a0a] dark:text-neutral-300 dark:hover:bg-neutral-900/40 dark:hover:text-white">View detailed controlled evidence <ArrowRight aria-hidden="true" className="size-3" /></Link>
    </header>
    {loading && <p role="status" className={`border-y border-neutral-200 py-4 dark:border-neutral-800 ${muted}`}>Loading final controlled synthesis…</p>}
    {error && <p role="alert" className={muted}>Final controlled synthesis unavailable. No alternate values are substituted: {error}</p>}
    {!loading && !error && !ready && <p className={muted}>Final controlled synthesis is not available: {data?.message ?? 'No controlled response.'}</p>}
    {ready && <>
      <section aria-label="Principal research questions">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xs font-semibold text-neutral-800 dark:text-neutral-200">{PRESENTATION_SECTION_BY_ID.PRINCIPAL.displayTitle}</h2>
          <p className="text-[11px] text-neutral-500 dark:text-neutral-400">Human Alignment → Stability → Mitigation Trade-off</p>
        </div>
        <div className="grid items-start gap-4 lg:grid-cols-3">
        <Question id="MAIN_Q1">
          <div className="space-y-3">
            <Finding rq="RQ1" value={value('RQ1', 'exact_agreement')}>Agreement with human preference reference labels; not an accuracy or ground-truth claim.</Finding>
            <dl className="flex items-baseline justify-between gap-3 border-t border-neutral-200 pt-3 dark:border-neutral-800"><dt className="text-xs text-neutral-600 dark:text-neutral-400">Cohen’s κ</dt><dd className={`text-sm ${number}`}>{value('RQ1', 'cohens_kappa')}</dd></dl>
          </div>
        </Question>
        <Question id="MAIN_Q2">
          <div className="grid gap-5 sm:grid-cols-2">
            <Finding rq="RQ2" value={value('RQ2', 'consistency')}>Fixed-condition repeatability across strict complete-repetition cells.</Finding>
            <Finding rq="RQ3" value={value('RQ3', 'paired_decisive_flip_rate')}>Decisive flip rate after canonical answer-identity remapping under answer-order swaps.</Finding>
          </div>
          <p className="mt-4 border-t border-neutral-200 pt-3 text-xs font-medium text-neutral-700 dark:border-neutral-800 dark:text-neutral-300">High repeatability does not imply complete robustness.</p>
        </Question>
        <Question id="MAIN_Q3">
          <div>
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1"><h3 className="text-sm font-semibold text-neutral-900 dark:text-white">{MITIGATION_BY_ID.DUAL_SWAP.displayTitle}</h3><p className="text-[10px] text-neutral-500 dark:text-neutral-400">RQ7 · PRIMARY · {mitigationRoleLabel(MITIGATION_BY_ID.DUAL_SWAP)}</p></div>
          <p className={`mt-1 ${muted}`}>{MITIGATION_BY_ID.DUAL_SWAP.family}</p>
          </div>
          <div className="overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
            <table className="w-full text-left text-xs">
              <caption className="sr-only">DUAL_SWAP agreement and coverage trade-off</caption>
              <thead className="bg-neutral-50 text-[10px] text-neutral-500 dark:bg-neutral-900/60 dark:text-neutral-400"><tr><th scope="col" className="px-3 py-2 font-medium">Measure</th><th scope="col" className="px-3 py-2 text-right font-medium">Baseline</th><th scope="col" className="px-3 py-2 text-right font-medium">DUAL_SWAP</th></tr></thead>
              <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800">{['agreement', 'coverage'].map(key => <tr key={key}><th scope="row" className="px-3 py-3 font-medium text-neutral-700 dark:text-neutral-300">{key === 'agreement' ? 'Agreement' : 'Coverage'}</th><td className={`px-3 py-3 text-right ${number}`}>{value('RQ7', `baseline_${key}`)}</td><td className={`px-3 py-3 text-right ${number}`}>{value('RQ7', `dual_swap_${key}`)}</td></tr>)}</tbody>
            </table>
          </div>
          <p className={`border-t border-neutral-200 pt-3 dark:border-neutral-800 md:col-span-2 ${muted}`}>Matched difference {value('RQ7', 'agreement_delta')} ({agreementDelta ? formatMetricCi(agreementDelta) : 'CI unavailable'}); coverage difference {value('RQ7', 'coverage_delta')}. The agreement change is small and uncertain while coverage is substantially reduced.</p>
        </Question>
        </div>
      </section>
      <section aria-labelledby="supporting-title" className="border-t border-neutral-200 pt-4 dark:border-neutral-800">
        <h2 id="supporting-title" className="text-sm font-semibold text-neutral-900 dark:text-white">Supporting Evidence</h2>
        <div className="mt-3 grid items-start gap-3 lg:grid-cols-[1.15fr_1fr_1fr]">
          <section aria-label="Secondary analyses" className="min-w-0 rounded-lg border border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-[#0a0a0a]">
            <header className="border-b border-neutral-200 px-4 py-3 dark:border-neutral-800"><p className="text-[10px] text-neutral-500 dark:text-neutral-400">{PRESENTATION_SECTION_BY_ID.SECONDARY.displayTitle}</p><h3 className="mt-1 text-xs font-semibold text-neutral-900 dark:text-white">Narrow controlled effects</h3></header>
            <div className="divide-y divide-neutral-200 px-4 dark:divide-neutral-800"><div className="py-2.5"><Finding supporting rq="RQ4" value={<><span className="block text-xs font-medium text-neutral-600 dark:text-neutral-400">{fraction('RQ4', 'variant_win_rate')}</span><span className="mt-0.5 block">{value('RQ4', 'variant_win_rate')}</span></>}>Stable controlled redundant-text variant wins among valid controlled pairs; no general verbosity inference.</Finding></div><div className="py-2.5"><Finding supporting rq="RQ5" value={<><span className="block text-xs font-medium text-neutral-600 dark:text-neutral-400">{fraction('RQ5', 'variant_win_rate')}</span><span className="mt-0.5 block">{value('RQ5', 'variant_win_rate')}</span></>}>Stable controlled presentation/list-prefix variant wins among valid controlled pairs; no general presentation-bias inference.</Finding></div></div>
          </section>
          <section aria-label="Exploratory analysis" className="min-w-0 rounded-lg border border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-[#0a0a0a]">
            <header className="border-b border-neutral-200 px-4 py-3 dark:border-neutral-800"><p className="text-[10px] text-neutral-500 dark:text-neutral-400">{PRESENTATION_SECTION_BY_ID.EXPLORATORY.displayTitle}</p><h3 className="mt-1 text-xs font-semibold text-neutral-900 dark:text-white">Counterbalanced association</h3></header>
            <div className="px-4 py-2.5"><article data-testid="finding-rq6" className="min-w-0"><p className="text-[10px] text-neutral-500 dark:text-neutral-400">RQ6 · {presentationRoleLabel(RESEARCH_QUESTION_BY_ID.RQ6)}</p><h3 className="mt-1 text-xs font-semibold text-neutral-900 dark:text-white">Same-family preference</h3><p className={`mt-3 text-lg ${number}`}>{value('RQ6', 'stable_same_family_preference')}</p>{rq6 ? <><dl className="mt-3 grid grid-cols-3 gap-2 border-t border-neutral-200 pt-3 dark:border-neutral-800"><div><dt className="text-[10px] text-neutral-500 dark:text-neutral-400">95% CI</dt><dd className={`mt-1 text-xs ${number}`}>{formatMetricCi(rq6).replace('95% CI: ', '')}</dd></div><div><dt className="text-[10px] text-neutral-500 dark:text-neutral-400">Stable decisive N</dt><dd className={`mt-1 text-xs ${number}`}>{rq6.denominator ?? 'Unavailable'}</dd></div><div><dt className="text-[10px] text-neutral-500 dark:text-neutral-400">Coverage</dt><dd className={`mt-1 text-xs ${number}`}>{rq6Coverage ? formatMetricValue(rq6Coverage) : 'Unavailable'}</dd></div></dl><p className={`mt-3 ${muted}`}>Association only: no clear uniform overall same-family preference, with strong judge-level heterogeneity.</p></> : <p className={`mt-2 ${muted}`}>Counterbalanced result unavailable.</p>}</article></div>
          </section>
          {multiJudge && <section aria-label="Additional Multi-Judge mitigation analysis" className="min-w-0 rounded-lg border border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-[#0a0a0a]">
            <header className="border-b border-neutral-200 px-4 py-3 dark:border-neutral-800"><p className="text-[10px] text-neutral-500 dark:text-neutral-400">RQ7 · {mitigationRoleLabel(MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS)}</p><h3 className="mt-1 text-xs font-semibold text-neutral-900 dark:text-white">{MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS.displayTitle}</h3></header>
            <div className="px-4 py-2.5"><p className={muted}>{MITIGATION_BY_ID.MULTI_JUDGE_CONSENSUS.family}; reported against its own equal-weight individual-judge comparator.</p>
            <dl className="mt-3 divide-y divide-neutral-200 dark:divide-neutral-800">{[['Agreement', percent(multiJudge.agreement)], ['Matched delta', pp(multiJudge.matched_delta)], ['Coverage', percent(multiJudge.coverage)]].map(([label, result]) => <div key={label} className="flex items-baseline justify-between gap-3 py-2.5"><dt className="text-xs text-neutral-600 dark:text-neutral-400">{label}</dt><dd className={`text-sm ${number}`}>{result}</dd></div>)}</dl></div>
          </section>}
        </div>
        {multiJudge && <p className={`mt-3 border-t border-neutral-200 pt-3 dark:border-neutral-800 ${muted}`}>Each mitigation is evaluated against its own frozen comparator; the reported effects are not a direct head-to-head comparison.</p>}
      </section>
    </>}
  </div>;
};

export default SynthesisPage;
