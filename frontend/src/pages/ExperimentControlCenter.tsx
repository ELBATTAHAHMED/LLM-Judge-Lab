import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import {
  triggerBatchRun,
  triggerPerturbationRun,
  triggerStochasticRun,
} from '../api/client';
import { useExperimentProgress } from '../hooks/useExperimentProgress';
import { SingleModelIcon } from '../components/ModelIcons';
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
  ArrowRight,
  ChevronDown,
  Check,
} from 'lucide-react';

const MODEL_OPTIONS = [
  { value: 'gpt-4o-mini', label: 'GPT-4o-Mini (Cloud / OpenAI)', icon: 'openai' },
  { value: 'llama3', label: 'Llama-3 8B (Local / Ollama)', icon: 'llama3' },
];

interface CustomModelSelectProps {
  label: string;
  value: string;
  onChange: (val: string) => void;
}

const CustomModelSelect: React.FC<CustomModelSelectProps> = ({ label, value, onChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const selectedOption = MODEL_OPTIONS.find((m) => m.value === value) || MODEL_OPTIONS[0];

  return (
    <div className="relative">
      <label className="block text-[10px] text-neutral-500 uppercase tracking-wider mb-1">
        {label}
      </label>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-2.5 py-1.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs font-mono text-neutral-900 dark:text-neutral-100 flex items-center justify-between cursor-pointer focus:outline-none focus:border-neutral-500"
      >
        <span className="flex items-center gap-2">
          <SingleModelIcon modelName={selectedOption.icon} className="w-4 h-4 shrink-0" />
          <span>{selectedOption.label}</span>
        </span>
        <ChevronDown className={`w-3.5 h-3.5 text-neutral-500 shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-full z-30 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 shadow-xl py-1 font-mono text-xs">
          {MODEL_OPTIONS.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => {
                onChange(item.value);
                setIsOpen(false);
              }}
              className={`w-full px-2.5 py-2 text-left flex items-center justify-between hover:bg-neutral-100 dark:hover:bg-neutral-900 cursor-pointer ${
                value === item.value ? 'bg-neutral-100 dark:bg-neutral-900 font-semibold' : ''
              }`}
            >
              <span className="flex items-center gap-2">
                <SingleModelIcon modelName={item.icon} className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </span>
              {value === item.value && <Check className="w-3.5 h-3.5 text-neutral-900 dark:text-neutral-100 shrink-0" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

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
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data?.detail || err.message)
        : (err instanceof Error ? err.message : 'Failed to launch batch execution');
      setActionError(msg);
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
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data?.detail || err.message)
        : (err instanceof Error ? err.message : 'Failed to launch perturbation generator');
      setActionError(msg);
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
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data?.detail || err.message)
        : (err instanceof Error ? err.message : 'Failed to launch stochastic benchmark');
      setActionError(msg);
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
              <FlaskConical className="w-4 h-4 text-neutral-700 dark:text-neutral-300" />
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
                  className="w-full accent-neutral-800 dark:accent-neutral-200 cursor-pointer"
                />
              </div>

              <CustomModelSelect
                label="Evaluator Model"
                value={batchModel}
                onChange={setBatchModel}
              />

              <div>
                <label className="block text-[10px] text-neutral-500 uppercase tracking-wider mb-1">
                  Active Mitigation Strategy
                </label>
                <select
                  value={batchStrategy}
                  onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setBatchStrategy(e.target.value as 'dual_ab' | 'verbosity_penalized' | 'none')}
                  className="w-full px-2.5 py-1.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs font-mono text-neutral-900 dark:text-neutral-100"
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
            className="w-full py-2 px-3 rounded bg-neutral-900 hover:bg-neutral-800 dark:bg-neutral-100 dark:hover:bg-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed text-white dark:text-neutral-900 font-mono text-xs font-semibold flex items-center justify-center space-x-1.5 cursor-pointer transition-colors shadow-xs"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Launch Batch Run</span>
          </button>
        </div>

        {/* Card 2: Synthetic Perturbation Generator */}
        <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center space-x-2 border-b border-neutral-200 dark:border-neutral-800 pb-2">
              <Sliders className="w-4 h-4 text-neutral-700 dark:text-neutral-300" />
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
                  className="w-full accent-neutral-800 dark:accent-neutral-200 cursor-pointer"
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
                  className="w-4 h-4 accent-neutral-800 dark:accent-neutral-200 rounded cursor-pointer"
                />
              </div>
            </div>
          </div>

          <button
            onClick={handleLaunchPerturbations}
            disabled={jobStatus?.status === 'running'}
            className="w-full py-2 px-3 rounded bg-neutral-900 hover:bg-neutral-800 dark:bg-neutral-100 dark:hover:bg-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed text-white dark:text-neutral-900 font-mono text-xs font-semibold flex items-center justify-center space-x-1.5 cursor-pointer transition-colors shadow-xs"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Run Perturbation Suite</span>
          </button>
        </div>

        {/* Card 3: Stochastic Consistency Benchmark */}
        <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center space-x-2 border-b border-neutral-200 dark:border-neutral-800 pb-2">
              <RefreshCw className="w-4 h-4 text-neutral-700 dark:text-neutral-300" />
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
                  className="w-full accent-neutral-800 dark:accent-neutral-200 cursor-pointer"
                />
              </div>

              <CustomModelSelect
                label="Target Model"
                value={stochasticModel}
                onChange={setStochasticModel}
              />
            </div>
          </div>

          <button
            onClick={handleLaunchStochastic}
            disabled={jobStatus?.status === 'running'}
            className="w-full py-2 px-3 rounded bg-neutral-900 hover:bg-neutral-800 dark:bg-neutral-100 dark:hover:bg-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed text-white dark:text-neutral-900 font-mono text-xs font-semibold flex items-center justify-center space-x-1.5 cursor-pointer transition-colors shadow-xs"
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
              <Terminal className="w-4 h-4 text-neutral-700 dark:text-neutral-300" />
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
                  : 'bg-neutral-800 dark:bg-neutral-200'
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

        {/* Completed Job Results Summary Card */}
        {jobStatus?.status === 'completed' && jobStatus.result_summary && (
          <JobSummaryCard summary={jobStatus.result_summary} jobType={jobStatus.job_type} />
        )}
      </div>
    </div>
  );
};

const JobSummaryCard: React.FC<{ summary: NonNullable<import('../api/types').ExperimentJobStatus['result_summary']>; jobType?: string }> = ({ summary, jobType }) => {
  const navigate = useNavigate();

  const handleNavigateToDiagnostics = () => {
    let hash = '#position-bias';
    if (jobType === 'perturbations' || summary.mitigation_strategy === 'synthetic_perturbation') {
      hash = '#verbosity-bias';
    } else if (jobType === 'stochastic' || summary.mitigation_strategy.startsWith('stochastic')) {
      hash = '#reliability-metrics';
    }
    navigate(`/diagnostics${hash}`);
  };

  return (
    <div className="p-4 rounded-lg bg-neutral-100/70 dark:bg-neutral-900/60 border border-neutral-200 dark:border-neutral-800 space-y-3 transition-all duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-neutral-200 dark:border-neutral-800 pb-2">
        <div className="flex items-center space-x-2 font-mono">
          <CheckCircle2 className="w-4 h-4 text-neutral-700 dark:text-neutral-300 shrink-0" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-900 dark:text-neutral-100">
            Experiment Results Summary
          </h3>
        </div>

        <button
          onClick={handleNavigateToDiagnostics}
          className="flex items-center space-x-1.5 px-3 py-1 rounded bg-neutral-900 hover:bg-neutral-800 dark:bg-neutral-100 dark:hover:bg-neutral-200 text-white dark:text-neutral-900 font-mono text-xs font-semibold cursor-pointer transition-colors self-start sm:self-auto shadow-xs"
        >
          <span>View Full Diagnostics</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 font-mono text-center">
        <div className="p-2.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800">
          <span className="text-[10px] text-neutral-500 uppercase tracking-wider">Evaluated Pairs</span>
          <p className="font-bold text-sm text-neutral-900 dark:text-white mt-0.5">{summary.total_evaluated}</p>
        </div>
        <div className="p-2.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800">
          <span className="text-[10px] text-neutral-500 uppercase tracking-wider">Winner A / B</span>
          <p className="font-bold text-sm text-neutral-900 dark:text-white mt-0.5">{summary.winner_a_count} / {summary.winner_b_count}</p>
        </div>
        <div className="p-2.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800">
          <span className="text-[10px] text-neutral-500 uppercase tracking-wider">Ties / Hedged</span>
          <p className="font-bold text-sm text-neutral-900 dark:text-white mt-0.5">{summary.tie_count}</p>
        </div>
        <div className="p-2.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800">
          <span className="text-[10px] text-neutral-500 uppercase tracking-wider">Mitigated Flips</span>
          <p className="font-bold text-sm text-neutral-900 dark:text-neutral-100 mt-0.5">{summary.position_bias_flips}</p>
        </div>
        <div className="p-2.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 col-span-2 sm:col-span-1">
          <span className="text-[10px] text-neutral-500 uppercase tracking-wider">Human Match Rate</span>
          <p className="font-bold text-sm text-neutral-900 dark:text-neutral-100 mt-0.5">{summary.overall_accuracy_vs_human}%</p>
        </div>
      </div>
    </div>
  );
};

function intPercent(val: number): number {
  return Math.round(val * 100);
}
