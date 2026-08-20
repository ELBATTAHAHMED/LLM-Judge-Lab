import React from 'react';
import { Link } from 'react-router-dom';
import { useControlledResults } from '../api/client';
import { formatMetricCi, formatMetricValue } from '../api/finalEvidence';
import type { ControlledMetricResult } from '../api/types';

const SummaryMetric: React.FC<{ label: string; metric: ControlledMetricResult | undefined }> = ({ label, metric }) => (
  <article className="rounded border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-[#121212]">
    <p className="text-xs font-medium text-neutral-700 dark:text-neutral-300">{label}</p>
    <p className="mt-2 text-xl font-mono text-neutral-900 dark:text-white">{metric ? formatMetricValue(metric) : 'Unavailable'}</p>
    <p className="mt-1 text-[11px] text-neutral-500">{metric ? formatMetricCi(metric) : 'Final controlled metric not available.'}</p>
    {metric && <p className="mt-1 text-[11px] text-neutral-500">N = {metric.denominator ?? 'not estimable'}</p>}
  </article>
);

export const SynthesisPage: React.FC = () => {
  const { data, loading, error } = useControlledResults();
  const metric = (rq: string, metricKey: string) => data?.results.find((row) => row.rq === rq && row.metric_key === metricKey);
  const ready = data?.status === 'CONTROLLED_RESULTS_AVAILABLE';

  return (
    <div className="max-w-[1400px] mx-auto space-y-6 py-4 font-sans">
      <div><h1 className="text-2xl font-serif">Final Scientific Synthesis</h1><p className="mt-1 text-xs text-neutral-500">A concise executive view of final controlled RQ1–RQ7 evidence. Detailed metrics, confidence intervals, and provenance remain on Controlled Experiments.</p></div>
      <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 text-sm dark:border-neutral-800 dark:bg-[#0a0a0a]"><p className="font-semibold">Final Evidence: Frozen</p><p className="mt-1 text-xs text-neutral-500">The complete RQ1–RQ7 evidence package is shown only on the controlled results page.</p><Link className="mt-3 inline-block text-xs font-medium text-neutral-900 underline dark:text-neutral-100" to="/controlled-results">Open Controlled Experiments</Link></div>
      {loading && <div className="rounded-lg border border-neutral-200 p-5 text-xs text-neutral-500 dark:border-neutral-800">Loading final controlled synthesis…</div>}
      {error && <div className="rounded-lg border border-neutral-200 p-5 text-xs text-neutral-500 dark:border-neutral-800">Final controlled synthesis unavailable. No legacy values are substituted: {error}</div>}
      {!loading && !error && !ready && <div className="rounded-lg border border-neutral-200 p-5 text-xs text-neutral-500 dark:border-neutral-800">Final controlled synthesis is not available: {data?.message ?? 'No controlled response.'}</div>}
      {ready && <>
        {data.accounting && <div className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4"><div className="rounded border border-neutral-200 p-3 dark:border-neutral-800"><strong>{data.accounting.planned_units.toLocaleString()}</strong><p className="mt-1 text-neutral-500">controlled units accounted</p></div><div className="rounded border border-neutral-200 p-3 dark:border-neutral-800"><strong>{data.accounting.valid_returned_passes.toLocaleString()} / {data.accounting.planned_pass_slots.toLocaleString()}</strong><p className="mt-1 text-neutral-500">valid / planned pass slots</p></div><div className="rounded border border-neutral-200 p-3 dark:border-neutral-800"><strong>{data.accounting.valid_partial_units.toLocaleString()} valid PARTIAL</strong><p className="mt-1 text-neutral-500">distinct from terminal failures</p></div><div className="rounded border border-neutral-200 p-3 dark:border-neutral-800"><strong>{Object.keys(data.analysis_runs).length}/7</strong><p className="mt-1 text-neutral-500">completed AnalysisRuns</p></div></div>}
        <section><h2 className="mb-3 text-sm font-semibold">Final controlled findings</h2><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3"><SummaryMetric label="RQ1 · Human Alignment" metric={metric('RQ1', 'exact_agreement')} /><SummaryMetric label="RQ2 · Stochastic Consistency" metric={metric('RQ2', 'consistency')} /><SummaryMetric label="RQ3 · Paired decisive flip rate" metric={metric('RQ3', 'paired_decisive_flip_rate')} /><SummaryMetric label="RQ4 · Controlled Redundant-Length Effect" metric={metric('RQ4', 'variant_win_rate')} /><SummaryMetric label="RQ5 · Controlled Presentation-Format Effect" metric={metric('RQ5', 'variant_win_rate')} /><SummaryMetric label="RQ6 · Matched Source-Family Preference" metric={metric('RQ6', 'self_family_preference')} /></div></section>
        <section className="rounded-lg border border-neutral-200 bg-neutral-50 p-5 dark:border-neutral-800 dark:bg-[#0a0a0a]"><h2 className="text-sm font-semibold">RQ7 · BASELINE SINGLE-PASS vs DUAL_SWAP Mitigation</h2><p className="mt-1 text-xs text-neutral-500">DUAL_SWAP increased agreement with human preference reference labels but reduced valid coverage.</p><div className="mt-4 grid gap-3 md:grid-cols-2"><SummaryMetric label="Baseline single-pass agreement" metric={metric('RQ7', 'baseline_agreement')} /><SummaryMetric label="DUAL_SWAP agreement" metric={metric('RQ7', 'dual_swap_agreement')} /><SummaryMetric label="Agreement delta" metric={metric('RQ7', 'agreement_delta')} /><SummaryMetric label="Coverage delta" metric={metric('RQ7', 'coverage_delta')} /></div></section>
      </>}
    </div>
  );
};

export default SynthesisPage;
