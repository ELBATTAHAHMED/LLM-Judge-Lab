import React from 'react';
import { useMacroBenchmark } from '../api/client';
import { useJudge } from '../context/JudgeContext';
import { Award, ShieldCheck, Activity, CheckCircle2, Zap, BarChart3 } from 'lucide-react';

export const MacroSynthesisDashboard: React.FC = () => {
  const { judgeModel } = useJudge();
  const { data, loading, error } = useMacroBenchmark(judgeModel);

  if (loading) {
    return (
      <div className="p-6 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 animate-pulse font-sans">
        <div className="h-4 w-48 bg-neutral-200 dark:bg-neutral-800 rounded mb-3" />
        <div className="h-6 w-80 bg-neutral-200 dark:bg-neutral-800 rounded mb-6" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="h-40 bg-neutral-200 dark:bg-neutral-900 rounded" />
          <div className="h-40 bg-neutral-200 dark:bg-neutral-900 rounded" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 font-sans">
        <p className="text-xs text-neutral-500 font-mono">
          Macro benchmark synthesis metrics unavailable: {error || 'No data'}
        </p>
      </div>
    );
  }

  const deltaKappaStr = data.delta_kappa >= 0 ? `+${data.delta_kappa.toFixed(3)}` : data.delta_kappa.toFixed(3);
  const deltaAccPct = (data.delta_accuracy * 100).toFixed(1);
  const deltaAccStr = data.delta_accuracy >= 0 ? `+${deltaAccPct}%` : `${deltaAccPct}%`;
  const flipRedStr = `-${data.flip_rate_reduction.toFixed(1)}%`;

  const baseSlope = data.baseline_length_bias !== undefined ? data.baseline_length_bias : 0.0;
  const mitSlope = data.mitigated_length_bias !== undefined ? data.mitigated_length_bias : 0.0;
  const lengthRedPct = data.length_bias_reduction !== undefined ? data.length_bias_reduction : 0.0;

  // Minimal neutral badge helper for deltas
  const getGainBadgeStyle = (delta: number) => {
    if (delta > 0) {
      return 'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-medium bg-neutral-100 text-teal-600 border border-neutral-200 dark:bg-neutral-800/50 dark:text-teal-400 dark:border-neutral-700';
    } else if (delta < 0) {
      return 'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-medium bg-neutral-100 text-rose-600 border border-neutral-200 dark:bg-neutral-800/50 dark:text-rose-400 dark:border-neutral-700';
    }
    return 'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-medium bg-neutral-100 text-neutral-600 border border-neutral-200 dark:bg-neutral-800/50 dark:text-neutral-400 dark:border-neutral-700';
  };

  const getBiasBadgeStyle = (reductionPct: number) => {
    if (reductionPct >= 0) {
      return 'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-medium bg-neutral-100 text-teal-600 border border-neutral-200 dark:bg-neutral-800/50 dark:text-teal-400 dark:border-neutral-700';
    }
    return 'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-medium bg-neutral-100 text-rose-600 border border-neutral-200 dark:bg-neutral-800/50 dark:text-rose-400 dark:border-neutral-700';
  };

  // Dynamic thesis conclusion banner phrase
  let agreementPhrase = `maintains agreement (0.000 \u0394\u03BA)`;
  if (data.delta_kappa > 0) {
    agreementPhrase = `increases agreement by +${data.delta_kappa.toFixed(3)} \u0394\u03BA`;
  } else if (data.delta_kappa < 0) {
    agreementPhrase = `decreases agreement by ${data.delta_kappa.toFixed(3)} \u0394\u03BA`;
  }

  const categoryData = data.category_breakdown || [];

  return (
    <div id="macro-synthesis-dashboard" className="scroll-mt-6 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 p-6 space-y-6 font-sans">
      {/* Top Meta Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-200 dark:border-neutral-800 pb-4">
        <div>
          <div className="flex items-center space-x-2 text-[11px] font-mono text-neutral-500 dark:text-neutral-500 uppercase tracking-wider">
            <Award className="w-3.5 h-3.5 text-neutral-500 dark:text-neutral-400 shrink-0" />
            <span>PFE Thesis Benchmark Synthesis</span>
            <span>•</span>
            <span className="text-neutral-700 dark:text-neutral-300 font-medium">N = {data.total_evaluations.toLocaleString()} Pairwise Trials</span>
          </div>
          <h2 className="text-xl font-serif text-neutral-900 dark:text-white tracking-tight mt-1">
            Before vs. After Mitigation Macro Performance
          </h2>
          <p className="text-xs text-neutral-600 dark:text-neutral-400 mt-0.5 leading-relaxed max-w-3xl">
            Aggregate quantitative synthesis comparing unmitigated single-pass evaluation (<span className="font-mono text-neutral-700 dark:text-neutral-300">{data.judge_model}</span>) against the Calibrated Multi-Judge Reliability Pipeline.
          </p>
        </div>

        <div className="flex items-center space-x-2 shrink-0 self-start sm:self-auto font-mono text-xs">
          <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-white dark:bg-[#121212] border border-neutral-200 dark:border-neutral-800 text-neutral-700 dark:text-neutral-300 shadow-sm dark:shadow-none">
            <Activity className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400 shrink-0" />
            <span>Full Benchmark Alignment</span>
          </div>
        </div>
      </div>

      {/* Side-by-Side Comparison UI */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 items-stretch">
        {/* Left Column: Baseline Performance */}
        <div className="p-5 rounded-md bg-white border border-neutral-200 dark:bg-[#121212] dark:border-neutral-800 shadow-sm dark:shadow-none space-y-4">
          <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-neutral-400 dark:bg-neutral-600" />
              <h3 className="text-sm font-semibold text-neutral-800 dark:text-neutral-200">
                Baseline Performance
              </h3>
            </div>
            <span className="text-[11px] font-mono text-neutral-500 dark:text-neutral-500">
              Standard Single-Pass
            </span>
          </div>

          <div className="space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between p-2.5 rounded bg-neutral-50 dark:bg-neutral-900/50 border border-neutral-100 dark:border-neutral-800">
              <span className="text-neutral-600 dark:text-neutral-400">Human Alignment (Cohen&apos;s &kappa;)</span>
              <span className="font-bold text-neutral-900 dark:text-neutral-100">
                {data.baseline_kappa.toFixed(3)}
              </span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded bg-neutral-50 dark:bg-neutral-900/50 border border-neutral-100 dark:border-neutral-800">
              <span className="text-neutral-600 dark:text-neutral-400">Human Preference Accuracy</span>
              <span className="font-bold text-neutral-900 dark:text-neutral-100">
                {(data.baseline_accuracy * 100).toFixed(1)}%
              </span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded bg-neutral-50 dark:bg-neutral-900/50 border border-neutral-100 dark:border-neutral-800">
              <span className="text-neutral-600 dark:text-neutral-400">Position Flip Vulnerability</span>
              <span className="font-bold text-rose-600 dark:text-rose-400">
                {(data.baseline_flip_rate * 100).toFixed(1)}%
              </span>
            </div>

            {/* Metric Row 4: Length / Verbosity Bias */}
            <div className="flex items-center justify-between p-2.5 rounded bg-neutral-50 dark:bg-neutral-900/50 border border-neutral-100 dark:border-neutral-800">
              <span className="text-neutral-600 dark:text-neutral-400">Length / Verbosity Bias (&beta;)</span>
              <span className="font-bold text-neutral-900 dark:text-neutral-100">
                +{baseSlope.toFixed(6)}
              </span>
            </div>
          </div>
        </div>

        {/* Right Column: Calibrated Ensemble Performance */}
        <div className="p-5 rounded-md bg-white border border-neutral-200 dark:bg-[#121212] dark:border-neutral-800 shadow-sm dark:shadow-none space-y-4">
          <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
            <div className="flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 text-teal-600 dark:text-teal-400 shrink-0" />
              <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">
                Calibrated Ensemble Performance
              </h3>
            </div>
            <span className="text-[11px] font-mono text-neutral-500 dark:text-neutral-400 font-medium">
              Debiased Pipeline
            </span>
          </div>

          <div className="space-y-3 font-mono text-xs">
            {/* Kappa Delta */}
            <div className="flex items-center justify-between p-2.5 rounded bg-neutral-50 dark:bg-neutral-900/50 border border-neutral-100 dark:border-neutral-800">
              <span className="text-neutral-700 dark:text-neutral-300">Human Alignment (Cohen&apos;s &kappa;)</span>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-neutral-900 dark:text-white">
                  {data.calibrated_kappa.toFixed(3)}
                </span>
                <span className={getGainBadgeStyle(data.delta_kappa)}>
                  {deltaKappaStr} &Delta;&kappa;
                </span>
              </div>
            </div>

            {/* Accuracy Delta */}
            <div className="flex items-center justify-between p-2.5 rounded bg-neutral-50 dark:bg-neutral-900/50 border border-neutral-100 dark:border-neutral-800">
              <span className="text-neutral-700 dark:text-neutral-300">Human Preference Accuracy</span>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-neutral-900 dark:text-white">
                  {(data.calibrated_accuracy * 100).toFixed(1)}%
                </span>
                <span className={getGainBadgeStyle(data.delta_accuracy)}>
                  {deltaAccStr}
                </span>
              </div>
            </div>

            {/* Flip Rate Reduction */}
            <div className="flex items-center justify-between p-2.5 rounded bg-neutral-50 dark:bg-neutral-900/50 border border-neutral-100 dark:border-neutral-800">
              <span className="text-neutral-700 dark:text-neutral-300">Position Flip Vulnerability</span>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-neutral-900 dark:text-white">
                  {(data.mitigated_flip_rate * 100).toFixed(1)}%
                </span>
                <span className={getBiasBadgeStyle(data.flip_rate_reduction)}>
                  {flipRedStr} Flip Rate
                </span>
              </div>
            </div>

            {/* Metric Row 4: Length / Verbosity Bias Mitigated */}
            <div className="flex items-center justify-between p-2.5 rounded bg-neutral-50 dark:bg-neutral-900/50 border border-neutral-100 dark:border-neutral-800">
              <span className="text-neutral-700 dark:text-neutral-300">Length / Verbosity Bias (&beta;)</span>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-neutral-900 dark:text-white">
                  +{mitSlope.toFixed(6)}
                </span>
                <span className={getBiasBadgeStyle(lengthRedPct)}>
                  -{lengthRedPct.toFixed(1)}% Bias
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Lower Grid - MT-Bench Domain-Specific Alignment Gains */}
      <div className="p-5 rounded-md bg-white border border-neutral-200 dark:bg-[#121212] dark:border-neutral-800 shadow-sm dark:shadow-none space-y-4">
        <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
          <div className="flex items-center space-x-2">
            <BarChart3 className="w-4 h-4 text-neutral-700 dark:text-neutral-300 shrink-0" />
            <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">
              MT-Bench Domain-Specific Alignment Gains
            </h3>
          </div>
          <div className="flex items-center space-x-4 text-xs font-mono">
            <div className="flex items-center space-x-1.5">
              <span className="w-2.5 h-2.5 rounded bg-neutral-400 dark:bg-neutral-600" />
              <span className="text-neutral-500 dark:text-neutral-400">Baseline &kappa;</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="w-2.5 h-2.5 rounded bg-teal-600 dark:bg-teal-700" />
              <span className="text-teal-700 dark:text-teal-400 font-medium">Calibrated &kappa;</span>
            </div>
          </div>
        </div>

        {categoryData.length === 0 ? (
          <p className="text-xs text-neutral-500 font-mono py-4 text-center">
            No category breakdown data available for <span className="text-neutral-700 dark:text-neutral-300 font-medium">{data.judge_model}</span>.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 font-mono text-xs">
            {categoryData.map((item) => {
              const deltaStr = item.delta_kappa >= 0 ? `+${item.delta_kappa.toFixed(3)}` : item.delta_kappa.toFixed(3);
              const maxVal = 0.6;
              const basePct = Math.min(100, Math.max(10, (item.baseline_kappa / maxVal) * 100));
              const calPct = Math.min(100, Math.max(10, (item.calibrated_kappa / maxVal) * 100));

              return (
                <div
                  key={item.category}
                  className="p-3 rounded bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-sans font-medium text-neutral-800 dark:text-neutral-200 text-xs">
                      {item.category}
                    </span>
                    <span className={getGainBadgeStyle(item.delta_kappa)}>
                      {deltaStr}
                    </span>
                  </div>

                  <div className="space-y-1.5 pt-1">
                    {/* Baseline Bar */}
                    <div>
                      <div className="flex justify-between text-[10px] text-neutral-500 mb-0.5">
                        <span>Baseline</span>
                        <span>{item.baseline_kappa.toFixed(3)}</span>
                      </div>
                      <div className="w-full bg-neutral-100 dark:bg-[#1E1E1E] rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-neutral-400 dark:bg-neutral-600 h-1.5 rounded-full transition-all duration-300"
                          style={{ width: `${basePct}%` }}
                        />
                      </div>
                    </div>

                    {/* Calibrated Bar */}
                    <div>
                      <div className="flex justify-between text-[10px] text-teal-700 dark:text-teal-400 font-medium mb-0.5">
                        <span>Calibrated</span>
                        <span>{item.calibrated_kappa.toFixed(3)}</span>
                      </div>
                      <div className="w-full bg-neutral-100 dark:bg-[#1E1E1E] rounded-full h-1.5 overflow-hidden border border-neutral-200 dark:border-neutral-800">
                        <div
                          className="bg-teal-600 dark:bg-teal-700 h-1.5 rounded-full transition-all duration-300"
                          style={{ width: `${calPct}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Analytical Takeaway Bar */}
      <div className="p-3.5 rounded bg-neutral-100 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center space-x-2 text-neutral-700 dark:text-neutral-300">
          <CheckCircle2 className="w-4 h-4 text-teal-600 dark:text-teal-400 shrink-0" />
          <span>
            <strong className="font-semibold text-neutral-900 dark:text-white">Thesis Conclusion:</strong> Dual A/B swap &amp; ensemble voting <span className="font-mono font-medium text-teal-600 dark:text-teal-400">{agreementPhrase}</span> and eliminates order vulnerability across MT-Bench domains.
          </span>
        </div>
        <div className="flex items-center space-x-1.5 font-mono text-[11px] text-neutral-500 dark:text-neutral-500 shrink-0">
          <Zap className="w-3 h-3 text-amber-500/80 shrink-0" />
          <span>Multi-Judge Calibration Pipeline</span>
        </div>
      </div>
    </div>
  );
};
