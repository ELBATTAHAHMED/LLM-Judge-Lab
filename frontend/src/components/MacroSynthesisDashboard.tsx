import React from 'react';
import { useMacroBenchmark } from '../api/client';
import { useJudge } from '../context/JudgeContext';
import { Award, ShieldCheck, Activity, CheckCircle2, Zap } from 'lucide-react';

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

  return (
    <div id="macro-synthesis-dashboard" className="scroll-mt-6 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 p-6 space-y-6 font-sans">
      {/* Top Meta Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-200 dark:border-neutral-800 pb-4">
        <div>
          <div className="flex items-center space-x-2 text-[11px] font-mono text-neutral-500 dark:text-neutral-500 uppercase tracking-wider">
            <Award className="w-3.5 h-3.5 text-neutral-600 dark:text-neutral-400 shrink-0" />
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

        <div className="flex items-center space-x-2 shrink-0 self-start sm:self-auto font-mono text-xs px-3 py-1.5 rounded bg-neutral-100 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-neutral-700 dark:text-neutral-300">
          <Activity className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span>Full Benchmark Alignment</span>
        </div>
      </div>

      {/* Side-by-Side Comparison UI */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 items-stretch">
        {/* Left Column: Baseline Performance */}
        <div className="p-5 rounded-md bg-white dark:bg-[#111111] border border-neutral-200 dark:border-neutral-800/80 space-y-4">
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
            <div className="flex items-center justify-between p-2.5 rounded bg-neutral-50 dark:bg-neutral-950/60 border border-neutral-100 dark:border-neutral-800">
              <span className="text-neutral-600 dark:text-neutral-400">Human Alignment (Cohen&apos;s &kappa;)</span>
              <span className="font-bold text-neutral-900 dark:text-neutral-100">
                {data.baseline_kappa.toFixed(3)}
              </span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded bg-neutral-50 dark:bg-neutral-950/60 border border-neutral-100 dark:border-neutral-800">
              <span className="text-neutral-600 dark:text-neutral-400">Human Preference Accuracy</span>
              <span className="font-bold text-neutral-900 dark:text-neutral-100">
                {(data.baseline_accuracy * 100).toFixed(1)}%
              </span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded bg-neutral-50 dark:bg-neutral-950/60 border border-neutral-100 dark:border-neutral-800">
              <span className="text-neutral-600 dark:text-neutral-400">Position Flip Vulnerability</span>
              <span className="font-bold text-red-600/90 dark:text-red-400/90">
                {(data.baseline_flip_rate * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {/* Right Column: Calibrated Ensemble Performance */}
        <div className="p-5 rounded-md bg-white dark:bg-[#111111] border border-emerald-300/40 dark:border-emerald-800/40 space-y-4">
          <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-3">
            <div className="flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
              <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">
                Calibrated Ensemble Performance
              </h3>
            </div>
            <span className="text-[11px] font-mono text-emerald-700 dark:text-emerald-400 font-medium">
              Debiased Pipeline
            </span>
          </div>

          <div className="space-y-3 font-mono text-xs">
            {/* Kappa Delta */}
            <div className="flex items-center justify-between p-2.5 rounded bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-200/60 dark:border-emerald-900/40">
              <span className="text-neutral-700 dark:text-neutral-300">Human Alignment (Cohen&apos;s &kappa;)</span>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-neutral-900 dark:text-white">
                  {data.calibrated_kappa.toFixed(3)}
                </span>
                <span className="px-1.5 py-0.5 rounded text-[11px] font-bold bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-300/50 dark:border-emerald-800">
                  {deltaKappaStr} &Delta;&kappa;
                </span>
              </div>
            </div>

            {/* Accuracy Delta */}
            <div className="flex items-center justify-between p-2.5 rounded bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-200/60 dark:border-emerald-900/40">
              <span className="text-neutral-700 dark:text-neutral-300">Human Preference Accuracy</span>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-neutral-900 dark:text-white">
                  {(data.calibrated_accuracy * 100).toFixed(1)}%
                </span>
                <span className="px-1.5 py-0.5 rounded text-[11px] font-bold bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-300/50 dark:border-emerald-800">
                  {deltaAccStr}
                </span>
              </div>
            </div>

            {/* Flip Rate Reduction */}
            <div className="flex items-center justify-between p-2.5 rounded bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-200/60 dark:border-emerald-900/40">
              <span className="text-neutral-700 dark:text-neutral-300">Position Flip Vulnerability</span>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-emerald-600 dark:text-emerald-400">
                  {(data.mitigated_flip_rate * 100).toFixed(1)}%
                </span>
                <span className="px-1.5 py-0.5 rounded text-[11px] font-bold bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-300/50 dark:border-emerald-800">
                  {flipRedStr} Flip Rate
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Analytical Takeaway Bar */}
      <div className="p-3.5 rounded bg-neutral-100 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center space-x-2 text-neutral-700 dark:text-neutral-300">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span>
            <strong className="font-semibold text-neutral-900 dark:text-white">Thesis Conclusion:</strong> Dual A/B swap &amp; ensemble voting increases agreement by <span className="font-mono font-medium text-emerald-700 dark:text-emerald-300">{deltaKappaStr} &Delta;&kappa;</span> and eliminates order vulnerability.
          </span>
        </div>
        <div className="flex items-center space-x-1.5 font-mono text-[11px] text-neutral-500 dark:text-neutral-500 shrink-0">
          <Zap className="w-3 h-3 text-amber-500 shrink-0" />
          <span>Multi-Judge Calibration Pipeline</span>
        </div>
      </div>
    </div>
  );
};
