import React, { useState } from 'react';
import {
  triggerBatchRun,
  triggerPerturbationRun,
  triggerStochasticRun,
} from '../api/client';
import { useExperimentProgress } from '../hooks/useExperimentProgress';
import {
  Terminal,
  Play,
  FlaskConical,
  Sparkles,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Sliders,
  Cpu,
} from 'lucide-react';

const MODEL_OPTIONS = [
  { value: 'gpt-4o-mini', label: 'GPT-4o-Mini (Cloud / OpenAI)', icon: 'openai' },
  { value: 'llama3', label: 'Llama-3 8B (Local / Ollama)', icon: 'llama3' },
];

export const ExperimentControlCenter: React.FC = () => {
  // Batch Engine State
  const [batchSampleSize, setBatchSampleSize] = useState<number>(50);
  const [batchModel, setBatchModel] = useState<string>('gpt-4o-mini');
  const [batchStrategy, setBatchStrategy] = useState<'dual_ab' | 'verbosity_penalized' | 'none'>('dual_ab');

  // Perturbation Generator State
  const [paddingFactor, setPaddingFactor] = useState<number>(0.35);
  const [injectMarkdown, setInjectMarkdown] = useState<boolean>(true);

  // Stochastic Benchmark State
  const [stochasticNTrials, setStochasticNTrials] = useState<number>(5);
  const [stochasticModel, setStochasticModel] = useState<string>('gpt-4o-mini');

  // Active Job Tracker State
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Progress Hook
  const { jobStatus } = useExperimentProgress(activeJobId);

  const handleLaunchBatch = async () => {
    setActionError(null);
    try {
      const res = await triggerBatchRun({
        sample_size: batchSampleSize,
        model_name: batchModel,
        temperature: 0.0,
        mitigation_strategy: batchStrategy,
      });
      setActiveJobId(res.job_id);
    } catch (err: any) {
      setActionError(err?.response?.data?.detail || err.message || 'Failed to launch batch execution');
    }
  };

  const handleLaunchPerturbations = async () => {
    setActionError(null);
    try {
      const res = await triggerPerturbationRun({
        padding_factor: paddingFactor,
        inject_markdown: injectMarkdown,
      });
      setActiveJobId(res.job_id);
    } catch (err: any) {
      setActionError(err?.response?.data?.detail || err.message || 'Failed to launch perturbation generator');
    }
  };

  const handleLaunchStochastic = async () => {
    setActionError(null);
    try {
      const res = await triggerStochasticRun({
        n_trials: stochasticNTrials,
        model_name: stochasticModel,
      });
      setActiveJobId(res.job_id);
    } catch (err: any) {
      setActionError(err?.response?.data?.detail || err.message || 'Failed to launch stochastic benchmark');
    }
  };

  return (
    <div className="max-w-[1400px] mx-auto space-y-6 py-2 font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-200 dark:border-neutral-800 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-neutral-900 dark:text-white">
            Experiment Control Center
          </h1>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1 font-mono">
            Autonomous Batch Evaluator, Synthetic Perturbation Engine, & Stochastic Benchmarks
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono text-neutral-500">
          <span className="px-2.5 py-1 rounded bg-neutral-100 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-teal-500" />
            <span>Worker Pool: Active</span>
          </span>
        </div>
      </div>

      {actionError && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-rose-700 dark:text-rose-300 text-xs font-mono flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* 3 Experiment Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Card 1: Batch Evaluation Engine */}
        <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center space-x-2 border-b border-neutral-200 dark:border-neutral-800 pb-2">
              <FlaskConical className="w-4 h-4 text-teal-600 dark:text-teal-400" />
              <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                Batch Evaluation Engine
              </h2>
            </div>

            <div className="space-y-3 text-xs font-mono">
              <div>
                <label className="block text-[10px] text-neutral-500 uppercase tracking-wider mb-1">
                  Sample Size ({batchSampleSize} Pairs)
                </label>
                <input
                  type="range"
                  min="10"
                  max="300"
                  step="10"
                  value={batchSampleSize}
                  onChange={(e) => setBatchSampleSize(Number(e.target.value))}
                  className="w-full accent-teal-500 cursor-pointer"
                />
              </div>

              <div>
                <label className="block text-[10px] text-neutral-500 uppercase tracking-wider mb-1">
                  Evaluator Model
                </label>
                <select
                  value={batchModel}
                  onChange={(e) => setBatchModel(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-900 dark:text-neutral-100"
                >
                  {MODEL_OPTIONS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[10px] text-neutral-500 uppercase tracking-wider mb-1">
                  Active Mitigation Strategy
                </label>
                <select
                  value={batchStrategy}
                  onChange={(e: any) => setBatchStrategy(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-900 dark:text-neutral-100"
                >
                  <option value="dual_ab">Dual A/B Swap (Position Bias)</option>
                  <option value="verbosity_penalized">Length Penalization (Verbosity Bias)</option>
                  <option value="none">None (Baseline)</option>
                </select>
              </div>
            </div>
          </div>

          <button
            onClick={handleLaunchBatch}
            disabled={jobStatus?.status === 'running'}
            className="w-full py-2 px-3 rounded bg-teal-600 hover:bg-teal-500 disabled:bg-neutral-400 dark:disabled:bg-neutral-800 text-white font-mono text-xs font-semibold flex items-center justify-center space-x-1.5 cursor-pointer transition-colors"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Launch Batch Run</span>
          </button>
        </div>

        {/* Card 2: Synthetic Perturbation Generator */}
        <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center space-x-2 border-b border-neutral-200 dark:border-neutral-800 pb-2">
              <Sliders className="w-4 h-4 text-purple-600 dark:text-purple-400" />
              <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                Synthetic Perturbation Engine
              </h2>
            </div>

            <div className="space-y-3 text-xs font-mono">
              <div>
                <label className="block text-[10px] text-neutral-500 uppercase tracking-wider mb-1">
                  Verbosity Padding ({intPercent(paddingFactor)}%)
                </label>
                <input
                  type="range"
                  min="0.1"
                  max="0.8"
                  step="0.05"
                  value={paddingFactor}
                  onChange={(e) => setPaddingFactor(Number(e.target.value))}
                  className="w-full accent-purple-500 cursor-pointer"
                />
              </div>

              <div className="pt-2 flex items-center justify-between">
                <span className="text-[11px] text-neutral-700 dark:text-neutral-300">
                  Inject Markdown Formatting
                </span>
                <input
                  type="checkbox"
                  checked={injectMarkdown}
                  onChange={(e) => setInjectMarkdown(e.target.checked)}
                  className="w-4 h-4 accent-purple-600 rounded cursor-pointer"
                />
              </div>
            </div>
          </div>

          <button
            onClick={handleLaunchPerturbations}
            disabled={jobStatus?.status === 'running'}
            className="w-full py-2 px-3 rounded bg-purple-600 hover:bg-purple-500 disabled:bg-neutral-400 dark:disabled:bg-neutral-800 text-white font-mono text-xs font-semibold flex items-center justify-center space-x-1.5 cursor-pointer transition-colors"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Run Perturbation Suite</span>
          </button>
        </div>

        {/* Card 3: Stochastic Consistency Benchmark */}
        <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center space-x-2 border-b border-neutral-200 dark:border-neutral-800 pb-2">
              <RefreshCw className="w-4 h-4 text-sky-600 dark:text-sky-400" />
              <h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                Stochastic Consistency Benchmark
              </h2>
            </div>

            <div className="space-y-3 text-xs font-mono">
              <div>
                <label className="block text-[10px] text-neutral-500 uppercase tracking-wider mb-1">
                  Replicated Pass Count (N={stochasticNTrials} Passes)
                </label>
                <input
                  type="range"
                  min="3"
                  max="10"
                  step="1"
                  value={stochasticNTrials}
                  onChange={(e) => setStochasticNTrials(Number(e.target.value))}
                  className="w-full accent-sky-500 cursor-pointer"
                />
              </div>

              <div>
                <label className="block text-[10px] text-neutral-500 uppercase tracking-wider mb-1">
                  Target Model
                </label>
                <select
                  value={stochasticModel}
                  onChange={(e) => setStochasticModel(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-900 dark:text-neutral-100"
                >
                  {MODEL_OPTIONS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <button
            onClick={handleLaunchStochastic}
            disabled={jobStatus?.status === 'running'}
            className="w-full py-2 px-3 rounded bg-sky-600 hover:bg-sky-500 disabled:bg-neutral-400 dark:disabled:bg-neutral-800 text-white font-mono text-xs font-semibold flex items-center justify-center space-x-1.5 cursor-pointer transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Run Stochastic Benchmark</span>
          </button>
        </div>
      </div>

      {/* Live Execution Telemetry & Progress Console */}
      <div className="p-5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-neutral-200 dark:border-neutral-800 pb-3">
          <div className="flex items-center space-x-3 font-mono">
            <span className="text-xs font-semibold text-neutral-900 dark:text-neutral-100 flex items-center gap-2">
              <Terminal className="w-4 h-4 text-teal-500" />
              <span>Live Telemetry & Execution Progress</span>
            </span>
            {activeJobId && (
              <span className="px-2 py-0.5 rounded bg-white dark:bg-neutral-900 text-neutral-700 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-800 text-[10px]">
                {activeJobId}
              </span>
            )}
          </div>

          <div className="flex items-center space-x-2 font-mono text-xs">
            {jobStatus?.status === 'running' && (
              <span className="px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 font-medium flex items-center gap-1.5">
                <RefreshCw className="w-3 h-3 animate-spin" />
                <span>RUNNING ({jobStatus.percentage}%)</span>
              </span>
            )}
            {jobStatus?.status === 'completed' && (
              <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 font-medium flex items-center gap-1.5">
                <CheckCircle2 className="w-3 h-3" />
                <span>COMPLETED</span>
              </span>
            )}
            {jobStatus?.status === 'failed' && (
              <span className="px-2.5 py-0.5 rounded-full bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20 font-medium flex items-center gap-1.5">
                <XCircle className="w-3 h-3" />
                <span>FAILED</span>
              </span>
            )}
            {!jobStatus && (
              <span className="px-2.5 py-0.5 rounded-full bg-neutral-200/60 dark:bg-neutral-900 text-neutral-500 font-medium">
                IDLE
              </span>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-1 font-mono text-xs">
          <div className="flex justify-between text-[11px] text-neutral-500">
            <span>Progress Status</span>
            <span>
              {jobStatus ? `${jobStatus.progress} / ${jobStatus.total} (${jobStatus.percentage}%)` : '0 / 0 (0%)'}
            </span>
          </div>
          <div className="w-full bg-neutral-200 dark:bg-neutral-900 h-2.5 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${
                jobStatus?.status === 'completed'
                  ? 'bg-emerald-500'
                  : jobStatus?.status === 'failed'
                  ? 'bg-rose-500'
                  : 'bg-teal-500'
              }`}
              style={{ width: `${jobStatus?.percentage || 0}%` }}
            />
          </div>
        </div>

        {/* Console Log Terminal */}
        <div className="bg-neutral-950 p-4 rounded border border-neutral-800/80 font-mono text-xs text-neutral-300 h-56 overflow-y-auto space-y-1.5 leading-relaxed">
          {jobStatus?.logs && jobStatus.logs.length > 0 ? (
            jobStatus.logs.map((line, idx) => (
              <div key={idx} className="flex items-start gap-2">
                <span className="text-neutral-600 select-none">&gt;</span>
                <span className={line.includes('Error') ? 'text-rose-400' : line.includes('completed') ? 'text-emerald-400 font-semibold' : 'text-neutral-300'}>
                  {line}
                </span>
              </div>
            ))
          ) : (
            <div className="text-neutral-600 text-center py-16 text-xs italic select-none">
              No active job running. Select an experiment above and click Launch to observe real-time telemetry streaming.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

function intPercent(val: number): number {
  return Math.round(val * 100);
}
