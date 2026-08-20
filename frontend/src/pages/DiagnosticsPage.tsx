import React, { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useBiasStats, useConsistencyStats, useSelfPreferenceStats } from '../api/client';
import { useJudge } from '../context/JudgeContext';
import { VerbosityBiasChart } from '../components/VerbosityBiasChart';
import { PositionBiasChart } from '../components/PositionBiasChart';
import { FormatBiasChart } from '../components/FormatBiasChart';
import { SelfPreferenceCard } from '../components/SelfPreferenceCard';
import { DomainReliabilityChart } from '../components/DomainReliabilityChart';
import { InterJudgeComparisonCard } from '../components/InterJudgeComparisonCard';
import { DiagnosticScientificCallouts } from '../components/DiagnosticScientificCallouts';
import { RefreshCw, Download } from 'lucide-react';
import { EvidenceBadge } from '../components/EvidenceBadge';

export const DiagnosticsPage: React.FC = () => {
  const { judgeModel } = useJudge();
  const { data: biasData, loading: biasLoading, error: biasError, refetch: refetchBias } = useBiasStats(judgeModel);
  const { data: consistencyData, loading: consistencyLoading, error: consistencyError, refetch: refetchConsistency } = useConsistencyStats(judgeModel);
  const { data: selfPrefData, loading: selfPrefLoading, error: selfPrefError, refetch: refetchSelfPref } = useSelfPreferenceStats(judgeModel);
  const location = useLocation();

  useEffect(() => {
    if (location.hash) {
      const elementId = location.hash.replace('#', '');
      const timer = setTimeout(() => {
        const elem = document.getElementById(elementId);
        if (elem) {
          elem.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [location.hash]);

  const handleRefresh = () => {
    refetchBias();
    refetchConsistency();
    refetchSelfPref();
  };

  const handleExportTelemetryCSV = () => {
    if (!biasData && !consistencyData && !selfPrefData) return;

    const rows: string[][] = [
      ['Category', 'Metric', 'Value', 'Details'],
      ['Judge Model', 'Model Name', `"${judgeModel}"`, ''],
      ['Logical Consistency', 'Overall Score', consistencyData?.overall_consistency_score != null ? `${(consistencyData.overall_consistency_score * 100).toFixed(1)}%` : 'N/A', 'Ordering invariance rate'],
      ['Logical Consistency', 'Position Consistency', consistencyData?.position_consistency_rate != null ? `${(consistencyData.position_consistency_rate * 100).toFixed(1)}%` : 'N/A', 'Verdict invariance under A/B swap'],
      ['Logical Consistency', 'Domain Specialization', consistencyData?.cross_category_consistency_rate != null ? `${(consistencyData.cross_category_consistency_rate * 100).toFixed(1)}%` : 'N/A', 'Category win rate variance'],
      ['Logical Consistency', 'Position Flips', `${consistencyData?.inconsistencies_count ?? 'N/A'}`, 'Flagged pairwise verdict reversals'],
      ['Slot-Win Imbalance', 'Position A Wins', `${biasData?.position_data?.position_a ?? 'N/A'}`, 'Legacy slot A total selections'],
      ['Slot-Win Imbalance', 'Position B Wins', `${biasData?.position_data?.position_b ?? 'N/A'}`, 'Legacy slot B total selections'],
      ['Slot-Win Imbalance', 'Ties', `${biasData?.position_data?.tie ?? 'N/A'}`, 'Legacy tie decisions'],
      ['Formatting Association', 'Markdown Chosen', `${biasData?.format_bias?.markdown_chosen ?? 'N/A'}`, 'Historical markdown-heavy selections'],
      ['Formatting Association', 'Plain Text Chosen', `${biasData?.format_bias?.plain_text_chosen ?? 'N/A'}`, 'Plain text selections'],
      ['Formatting Association', 'Chi-Square Stat', `${biasData?.format_bias?.chi2_stat ?? 'N/A'}`, 'Chi2 goodness of fit'],
      ['Formatting Association', 'p-value', `${biasData?.format_bias?.p_value ?? 'N/A'}`, 'Raw p-value'],
      ['Formatting Association', 'p-value (BH Adjusted)', `${biasData?.format_bias?.p_value_adjusted ?? 'N/A'}`, 'Benjamini-Hochberg adjusted p-value'],
      ['Self Preference', 'Judge Family', `"${selfPrefData?.judge_family ?? ''}"`, 'Model provider family'],
      ['Self Preference', 'Self Win Rate', selfPrefData?.self_win_rate != null ? `${(selfPrefData.self_win_rate * 100).toFixed(1)}%` : 'N/A', 'Same family win rate'],
      ['Self Preference', 'Baseline Win Rate', selfPrefData?.baseline_win_rate != null ? `${(selfPrefData.baseline_win_rate * 100).toFixed(1)}%` : 'N/A', 'Other family win rate'],
      ['Self Preference', 'Self Preference Ratio', selfPrefData?.self_preference_ratio != null ? selfPrefData.self_preference_ratio.toFixed(3) : 'N/A', 'Ratio over baseline'],
      ['Self Preference', 'Detected', `${selfPrefData?.self_preference_detected ?? false}`, 'Statistical significance flag'],
    ];

    if (biasData?.domain_kappa) {
      biasData.domain_kappa.forEach((dk) => {
        rows.push(['Domain Reliability', `Kappa (${dk.domain})`, dk.kappa != null ? dk.kappa.toFixed(3) : 'N/A', 'Domain stratified Cohen Kappa']);
      });
    }

    const csvContent = 'data:text/csv;charset=utf-8,' + rows.map((r) => r.join(',')).join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `judgelab_telemetry_${judgeModel.replace('/', '_')}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const isLoading = biasLoading || consistencyLoading || selfPrefLoading;

  return (
    <div className="max-w-[1400px] mx-auto space-y-8 py-2 font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-200 dark:border-neutral-800 pb-4">
        <div>
          <h1 className="text-2xl font-serif text-neutral-900 dark:text-white tracking-tight">
            Legacy / Exploratory Diagnostics
          </h1>
          <p className="text-xs text-neutral-600 dark:text-neutral-400 mt-1">
            <span className="mr-2 inline-block"><EvidenceBadge evidenceClass="LEGACY_EXPLORATORY" /></span>Model-specific historical telemetry from retained database decisions. It is not final controlled RQ1–RQ7 evidence; each metric shows N/A when no eligible observations exist.
          </p>
        </div>

        <div className="flex items-center space-x-2 self-start sm:self-auto font-mono">
          <button
            onClick={handleExportTelemetryCSV}
            disabled={isLoading || (!biasData && !consistencyData && !selfPrefData)}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-950 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white transition-colors cursor-pointer text-xs disabled:opacity-40"
          >
            <Download className="w-3 h-3 text-neutral-500 dark:text-neutral-400" />
            <span>Export Telemetry CSV</span>
          </button>

          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-950 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white transition-colors cursor-pointer text-xs"
          >
            <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Logical Consistency Telemetry */}
      <div id="consistency-summary" className="scroll-mt-6 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-mono uppercase tracking-wider text-neutral-500 dark:text-neutral-500">
            Logical Consistency — {judgeModel}
          </h3>
          {consistencyData?.inter_judge_reliability?.inter_judge_kappa != null && (
            <span className="hidden sm:block text-[11px] font-mono text-neutral-500 dark:text-neutral-500">
              &kappa; vs {consistencyData.inter_judge_reliability.model_b}:{' '}
              <span className="text-neutral-700 dark:text-neutral-300 font-medium">
                {consistencyData.inter_judge_reliability.inter_judge_kappa.toFixed(3)}
              </span>{' '}
              (N={consistencyData.inter_judge_reliability.overlapping_trials})
            </span>
          )}
        </div>

        {consistencyError ? (
          <div className="p-4 rounded-lg bg-neutral-100 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400 text-xs font-mono">
            Failed to load consistency statistics: {consistencyError}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Overall Consistency */}
            <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800">
              <p className="text-[10px] font-mono uppercase tracking-wider text-neutral-500 dark:text-neutral-500 mb-2">
                Overall Consistency
              </p>
              {consistencyLoading ? (
                <div className="h-7 w-20 bg-neutral-200 dark:bg-neutral-800 animate-pulse rounded mb-1" />
              ) : (
                <p className="text-2xl font-mono font-bold text-neutral-900 dark:text-white tracking-tight">
                  {consistencyData?.overall_consistency_score != null ? `${(consistencyData.overall_consistency_score * 100).toFixed(1)}%` : 'N/A'}
                </p>
              )}
              <p className="text-[11px] text-neutral-500 dark:text-neutral-500 mt-1 leading-snug">
                Ordering invariance across repeated evaluations
              </p>
            </div>

            {/* Position Consistency */}
            <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800">
              <p className="text-[10px] font-mono uppercase tracking-wider text-neutral-500 dark:text-neutral-500 mb-2">
                Position Consistency
              </p>
              {consistencyLoading ? (
                <div className="h-7 w-20 bg-neutral-200 dark:bg-neutral-800 animate-pulse rounded mb-1" />
              ) : (
                <p className="text-2xl font-mono font-bold text-neutral-900 dark:text-white tracking-tight">
                  {consistencyData?.position_consistency_rate != null ? `${(consistencyData.position_consistency_rate * 100).toFixed(1)}%` : 'N/A'}
                </p>
              )}
              <p className="text-[11px] text-neutral-500 dark:text-neutral-500 mt-1 leading-snug">
                Verdict invariance under A/B order swap
              </p>
            </div>

            {/* Domain Specialization */}
            <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800">
              <p className="text-[10px] font-mono uppercase tracking-wider text-neutral-500 dark:text-neutral-500 mb-2">
                Domain Specialization
              </p>
              {consistencyLoading ? (
                <div className="h-7 w-20 bg-neutral-200 dark:bg-neutral-800 animate-pulse rounded mb-1" />
              ) : (
                <p className="text-2xl font-mono font-bold text-neutral-900 dark:text-white tracking-tight">
                  {consistencyData?.cross_category_consistency_rate != null ? `${(consistencyData.cross_category_consistency_rate * 100).toFixed(1)}%` : 'N/A'}
                </p>
              )}
              <p className="text-[11px] text-neutral-500 dark:text-neutral-500 mt-1 leading-snug">
                Category-specific win rate variance
              </p>
            </div>

            {/* Position Flips — semantic muted red on value only */}
            <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800">
              <p className="text-[10px] font-mono uppercase tracking-wider text-neutral-500 dark:text-neutral-500 mb-2">
                Position Flips
              </p>
              {consistencyLoading ? (
                <div className="h-7 w-20 bg-neutral-200 dark:bg-neutral-800 animate-pulse rounded mb-1" />
              ) : (
                <p className={`text-2xl font-mono font-bold tracking-tight ${
                  (consistencyData?.inconsistencies_count ?? 0) > 0
                    ? 'text-red-600/90 dark:text-red-400/90'
                    : 'text-neutral-900 dark:text-white'
                }`}>
                  {consistencyData?.inconsistencies_count ?? 'N/A'}
                </p>
              )}
              <p className="text-[11px] text-neutral-500 dark:text-neutral-500 mt-1 leading-snug">
                Flagged pairwise verdict reversals
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Primary Bias Charts Grid — Position & Format */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-stretch">
        <div id="position-bias" className="scroll-mt-6">
          <PositionBiasChart
            data={biasData ? biasData.position_data : null}
            loading={biasLoading}
            error={biasError}
          />
        </div>

        <FormatBiasChart
          data={biasData ? biasData.format_bias : null}
          loading={biasLoading}
          error={biasError}
        />
      </div>

      {/* Full-Width Verbosity Bias Scatter Chart */}
      <div id="verbosity-bias" className="scroll-mt-6">
        <VerbosityBiasChart
          data={biasData ? biasData.verbosity_data : []}
          loading={biasLoading}
          error={biasError}
        />
      </div>

      {/* Primary Research Row — Self-Preference Bias (RQ6) + Inter-Judge Agreement */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-stretch">
        <div id="self-preference-bias" className="scroll-mt-6 h-full">
          <SelfPreferenceCard
            data={selfPrefData}
            loading={selfPrefLoading}
            error={selfPrefError}
          />
        </div>

        <div id="inter-judge-comparison" className="scroll-mt-6 h-full">
          <InterJudgeComparisonCard />
        </div>
      </div>

      {/* Domain-Stratified Reliability Bar Chart */}
      <div id="reliability-metrics" className="scroll-mt-6 space-y-8">
        <DomainReliabilityChart
          data={biasData ? biasData.domain_kappa : []}
          loading={biasLoading}
          error={biasError}
        />

        {/* Academic Synthesis Callouts */}
        <DiagnosticScientificCallouts />
      </div>
    </div>
  );
};


