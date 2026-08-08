import React from 'react';
import type { SelfPreferenceResponse } from '../api/types';
import { TrendingUp, Minus, Loader2, Info, FlaskConical } from 'lucide-react';

interface Props {
  data: SelfPreferenceResponse | null;
  loading: boolean;
  error: string | null;
}

export const SelfPreferenceCard: React.FC<Props> = ({ data, loading, error }) => {
  if (loading) {
    return (
      <div className="p-5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 h-full flex flex-col justify-center items-center font-sans">
        <Loader2 className="w-4 h-4 animate-spin text-neutral-400 mb-2" />
        <p className="text-xs text-neutral-500 font-mono">Computing bias telemetry...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 h-full flex flex-col justify-center items-center font-sans text-center">
        <p className="text-xs text-neutral-500 font-mono">
          {error || 'Self-preference telemetry unavailable'}
        </p>
      </div>
    );
  }

  const isBiased = data.self_preference_detected;
  const hasData =
    data.total_self_matchups > 0 &&
    data.self_win_rate !== null &&
    data.baseline_win_rate !== null;

  const selfPct =
    hasData && data.self_win_rate !== null ? (data.self_win_rate * 100).toFixed(1) : null;
  const baselinePct =
    hasData && data.baseline_win_rate !== null
      ? (data.baseline_win_rate * 100).toFixed(1)
      : null;
  const diffPct =
    hasData && data.self_win_rate !== null && data.baseline_win_rate !== null
      ? ((data.self_win_rate - data.baseline_win_rate) * 100).toFixed(1)
      : null;
  const ratioStr =
    hasData && data.self_preference_ratio !== null
      ? data.self_preference_ratio.toFixed(2)
      : null;

  const diffVal =
    hasData && data.self_win_rate !== null && data.baseline_win_rate !== null
      ? (data.self_win_rate - data.baseline_win_rate) * 100
      : null;

  // Scientific interpretation helpers
  const pValueStr =
    data.p_value !== null
      ? data.p_value < 0.001
        ? '< 0.001'
        : data.p_value.toFixed(4)
      : null;

  const getInterpretationText = () => {
    if (!hasData) return null;
    const formattedP = pValueStr ? (pValueStr.startsWith('<') ? `p ${pValueStr}` : `p = ${pValueStr}`) : null;

    if (isBiased) {
      return (
        <>
          Statistically robust positive self-preference bias detected for the{' '}
          <strong className="text-neutral-900 dark:text-neutral-200">
            {data.judge_family.toUpperCase()}
          </strong>{' '}
          family ({formattedP}). Binomial test on {data.total_self_matchups.toLocaleString()} asymmetric pairs confirms a{' '}
          <strong className="text-neutral-900 dark:text-neutral-200">+{diffPct}%</strong> win-rate advantage over rival baseline ({baselinePct}%).
        </>
      );
    }

    if (diffVal !== null && diffVal <= -10) {
      return (
        <>
          No positive self-preference detected. The model exhibits significant{' '}
          <strong className="text-neutral-900 dark:text-neutral-200">
            Self-Disfavor Bias ({diffPct}%)
          </strong>
          , penalizing answers from its own{' '}
          <strong className="text-neutral-900 dark:text-neutral-200">
            {data.judge_family.toUpperCase()}
          </strong>{' '}
          family compared to rivals ({baselinePct}% baseline).
        </>
      );
    }

    return (
      <>
        No statistically robust self-preference bias detected for the{' '}
        <strong className="text-neutral-900 dark:text-neutral-200">
          {data.judge_family.toUpperCase()}
        </strong>{' '}
        family ({formattedP}). The observed {diffPct && parseFloat(diffPct) >= 0 ? `+${diffPct}%` : `${diffPct}%`}{' '}
        delta is consistent with random variation.
      </>
    );
  };

  return (
    <div className="p-5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 flex flex-col space-y-4 font-sans h-full">
      {/* ── Header ── */}
      <div className="border-b border-neutral-200 dark:border-neutral-800 pb-2.5">
        <div className="flex items-center justify-between">
          <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 text-xs tracking-tight">
            Self-Preference Bias (RQ6)
          </h4>
          <span
            className={`text-[10px] font-mono border px-2 py-0.5 rounded ${
              !hasData
                ? 'bg-neutral-100 dark:bg-neutral-900 border-neutral-300 dark:border-neutral-700 text-neutral-500 dark:text-neutral-400'
                : isBiased
                ? 'bg-neutral-100 dark:bg-neutral-900 border-neutral-400 dark:border-neutral-600 text-neutral-700 dark:text-neutral-300'
                : 'bg-neutral-100 dark:bg-neutral-900 border-neutral-300 dark:border-neutral-700 text-neutral-500 dark:text-neutral-400'
            }`}
          >
            {!hasData
              ? 'Insufficient Data'
              : isBiased
              ? `Detected · ${ratioStr}×`
              : `Not Detected · ${ratioStr}×`}
          </span>
        </div>
        <p className="text-[11px] text-neutral-500 dark:text-neutral-500 mt-0.5">
          Does the judge favor its own model family ({data.judge_family.toUpperCase()})?
        </p>
      </div>

      {!hasData ? (
        /* ── Academic Empty State ── */
        <div className="flex-1 flex flex-col justify-center items-center text-center p-6 rounded bg-neutral-100/50 dark:bg-neutral-900/40 border border-dashed border-neutral-200 dark:border-neutral-800 space-y-2">
          <Info className="w-4 h-4 text-neutral-400 shrink-0" />
          <p className="text-xs text-neutral-600 dark:text-neutral-400 font-mono leading-relaxed max-w-[280px]">
            Insufficient data: No rival-family pairings found for this judge model in the
            current dataset.
          </p>
        </div>
      ) : (
        <>
          {/* ── Metric Mini-Cards Grid ── */}
          <div className="grid grid-cols-3 gap-2.5 font-mono text-center">
            {/* Asymmetric Pairs */}
            <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 space-y-1">
              <p className="text-[9px] text-neutral-500 uppercase tracking-wider leading-tight">
                Asymmetric Pairs
              </p>
              <p className="text-lg font-bold text-neutral-900 dark:text-white">
                {data.total_self_matchups.toLocaleString()}
              </p>
              <p className="text-[9px] text-neutral-500 leading-tight">self-family trials</p>
            </div>

            {/* Baseline Pairs */}
            <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 space-y-1">
              <p className="text-[9px] text-neutral-500 uppercase tracking-wider leading-tight">
                Baseline Neutral
              </p>
              <p className="text-lg font-bold text-neutral-900 dark:text-white">
                {data.total_other_matchups.toLocaleString()}
              </p>
              <p className="text-[9px] text-neutral-500 leading-tight">rival-family trials</p>
            </div>

            {/* Odds Ratio / Multiplier */}
            <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 space-y-1">
              <p className="text-[9px] text-neutral-500 uppercase tracking-wider leading-tight">
                Odds Multiplier
              </p>
              <p className="text-lg font-bold text-neutral-900 dark:text-white">
                {ratioStr}
                <span className="text-xs font-normal text-neutral-500 ml-0.5">×</span>
              </p>
              <span
                className={`inline-block px-1.5 py-0.5 rounded border text-[9px] font-mono leading-tight ${
                  isBiased
                    ? 'border-neutral-400 dark:border-neutral-600 bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300'
                    : 'border-neutral-200 dark:border-neutral-700 bg-neutral-100 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400'
                }`}
              >
                {isBiased ? 'Significant' : 'Neutral'}
              </span>
            </div>
          </div>

          {/* ── Progress Bars ── */}
          <div className="space-y-3.5">
            {/* Own Family Win Rate */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] font-mono uppercase tracking-wider text-neutral-500">
                  Own Family Win Rate
                </span>
                <span className="text-xs font-bold text-neutral-900 dark:text-white font-mono tabular-nums bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 rounded px-1.5 py-0.5">
                  {selfPct}%
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-neutral-200 dark:bg-neutral-800 overflow-hidden relative">
                {/* Track fill */}
                <div
                  className="h-full rounded-full bg-slate-500 dark:bg-slate-400 transition-all duration-500"
                  style={{
                    width: `${Math.min(100, Math.max(0, (data.self_win_rate ?? 0) * 100))}%`,
                  }}
                />
              </div>
            </div>

            {/* Rival Families Baseline */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] font-mono uppercase tracking-wider text-neutral-500">
                  Rival Families (Baseline)
                </span>
                <span className="text-xs font-bold text-neutral-900 dark:text-white font-mono tabular-nums bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 rounded px-1.5 py-0.5">
                  {baselinePct}%
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-neutral-200 dark:bg-neutral-800 overflow-hidden relative">
                <div
                  className="h-full rounded-full bg-neutral-400 dark:bg-neutral-600 transition-all duration-500"
                  style={{
                    width: `${Math.min(100, Math.max(0, (data.baseline_win_rate ?? 0) * 100))}%`,
                  }}
                />
              </div>
            </div>

            {/* Δ Delta label */}
            <div className="flex items-center justify-between text-[10px] font-mono text-neutral-500 pt-0.5">
              <span className="flex items-center gap-1">
                {isBiased ? (
                  <TrendingUp className="w-3 h-3 text-neutral-500 shrink-0" />
                ) : (
                  <Minus className="w-3 h-3 text-neutral-400 shrink-0" />
                )}
                <span>Win-rate delta (own − baseline)</span>
              </span>
              <span
                className={`font-bold tabular-nums ${
                  isBiased
                    ? 'text-neutral-700 dark:text-neutral-300'
                    : 'text-neutral-500 dark:text-neutral-500'
                }`}
              >
                {diffPct && parseFloat(diffPct) >= 0 ? `+${diffPct}%` : `${diffPct}%`}
              </span>
            </div>
          </div>

          {/* ── Scientific Interpretation Footer ── */}
          <div className="p-3 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-600 dark:text-neutral-400 space-y-1.5">
            <div className="flex items-center gap-1.5 text-neutral-900 dark:text-neutral-200 font-medium">
              <FlaskConical className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
              <span>Scientific Interpretation (Binomial Test, α = 0.05):</span>
            </div>
            <p className="leading-relaxed text-[11px]">{getInterpretationText()}</p>
          </div>
        </>
      )}
    </div>
  );
};
