import React, { useState, useEffect } from 'react';
import { useInterJudgeKappa } from '../api/client';
import { useJudge } from '../context/JudgeContext';
import { SingleModelIcon } from './ModelIcons';
import { RefreshCw, Info, ChevronDown, Check } from 'lucide-react';

const MODEL_OPTIONS = [
  { value: 'gpt-4o-mini', label: 'GPT-4o-Mini (OpenAI)', icon: 'gpt-4o-mini' },
  { value: 'deepseek/deepseek-chat', label: 'DeepSeek V3 Chat', icon: 'deepseek/deepseek-chat' },
  { value: 'meta-llama/llama-3.3-70b-instruct', label: 'Llama 3.3 70B Instruct', icon: 'meta-llama/llama-3.3-70b-instruct' },
  { value: 'anthropic/claude-3-haiku', label: 'Claude 3 Haiku', icon: 'anthropic/claude-3-haiku' },
];

export const InterJudgeComparisonCard: React.FC = () => {
  const { judgeModel } = useJudge();
  const modelA = judgeModel;

  const [modelB, setModelB] = useState<string>(() => {
    return judgeModel === 'deepseek/deepseek-chat' ? 'gpt-4o-mini' : 'deepseek/deepseek-chat';
  });
  const [isOpenB, setIsOpenB] = useState<boolean>(false);

  // Auto-switch Model B if global judgeModel changes to match Model B
  useEffect(() => {
    if (modelB === judgeModel) {
      const alternative = MODEL_OPTIONS.find((m) => m.value !== judgeModel);
      if (alternative) {
        setModelB(alternative.value);
      }
    }
  }, [judgeModel, modelB]);

  const { data, loading, error, refetch } = useInterJudgeKappa(modelA, modelB);

  const kappa = data?.inter_judge_kappa ?? 0;
  const agreement = (data?.agreement_rate ?? 0) * 100;
  const nTrials = data?.overlapping_trials ?? 0;

  const getKappaInterpretation = (val: number, n: number) => {
    if (n === 0) return { label: 'No Overlapping Data' };
    if (val >= 0.81) return { label: 'Almost Perfect Agreement' };
    if (val >= 0.61) return { label: 'Substantial Agreement' };
    if (val >= 0.41) return { label: 'Moderate Agreement' };
    if (val >= 0.21) return { label: 'Fair Agreement' };
    if (val >= 0.0) return { label: 'Slight Agreement' };
    return { label: 'Poor / Disagreement' };
  };

  const interpretation = getKappaInterpretation(kappa, nTrials);
  const selectedA = MODEL_OPTIONS.find((m) => m.value === modelA) || MODEL_OPTIONS[0];
  const selectedB = MODEL_OPTIONS.find((m) => m.value === modelB) || MODEL_OPTIONS[1];

  return (
    <div className="p-5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-5 font-sans h-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3">
        <div>
          <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 text-xs tracking-tight">
            Inter-Judge Cohen's Kappa (&kappa;) Comparison
          </h4>
        </div>
        <button
          onClick={refetch}
          disabled={loading}
          className="flex items-center space-x-1 px-2 py-1 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white text-[11px] font-mono cursor-pointer"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          <span>Compare</span>
        </button>
      </div>

      {/* Model Selector Dropdowns */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Model A Selector (Bound strictly to global active judge) */}
        <div className="relative">
          <label className="block text-[10px] font-mono uppercase tracking-wider text-neutral-500 dark:text-neutral-400 mb-1">
            Judge Model A (Global Active Judge)
          </label>
          <div className="w-full px-3 py-2 rounded bg-neutral-100 dark:bg-neutral-900/60 border border-neutral-200 dark:border-neutral-800 text-xs font-mono text-neutral-900 dark:text-neutral-100 flex items-center justify-between cursor-not-allowed">
            <span className="flex items-center gap-2">
              <SingleModelIcon modelName={selectedA.icon} className="w-4 h-4 shrink-0" />
              <span className="font-semibold">{selectedA.label}</span>
            </span>
          </div>
        </div>

        {/* Model B Selector */}
        <div className="relative">
          <label className="block text-[10px] font-mono uppercase tracking-wider text-neutral-500 dark:text-neutral-400 mb-1">
            Judge Model B (Comparator)
          </label>
          <button
            type="button"
            onClick={() => setIsOpenB(!isOpenB)}
            className="w-full px-3 py-2 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-xs font-mono text-neutral-900 dark:text-neutral-100 flex items-center justify-between cursor-pointer"
          >
            <span className="flex items-center gap-2">
              <SingleModelIcon modelName={selectedB.icon} className="w-4 h-4 shrink-0" />
              <span>{selectedB.label}</span>
            </span>
            <ChevronDown className={`w-3.5 h-3.5 text-neutral-500 transition-transform ${isOpenB ? 'rotate-180' : ''}`} />
          </button>

          {isOpenB && (
            <div className="absolute top-full left-0 mt-1 w-full z-20 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-xl py-1 font-mono text-xs">
              {MODEL_OPTIONS.filter((item) => item.value !== modelA).map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => { setModelB(item.value); setIsOpenB(false); }}
                  className={`w-full px-3 py-1.5 text-left flex items-center justify-between hover:bg-neutral-100 dark:hover:bg-neutral-800 cursor-pointer ${
                    modelB === item.value ? 'bg-neutral-100 dark:bg-neutral-800 font-semibold' : ''
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <SingleModelIcon modelName={item.icon} className="w-4 h-4 shrink-0" />
                    <span>{item.label}</span>
                  </span>
                  {modelB === item.value && <Check className="w-3.5 h-3.5 text-neutral-900 dark:text-neutral-100" />}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Results Telemetry Display */}
      {loading ? (
        <div className="p-6 text-center font-mono text-xs text-neutral-500">
          Calculating inter-judge Cohen's Kappa score...
        </div>
      ) : error ? (
        <div className="p-4 rounded bg-red-950/40 border border-red-800/40 text-red-600 dark:text-red-400 text-xs font-mono">
          {error}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-center">
            {/* Kappa Score */}
            <div className="p-3 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 space-y-1">
              <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Cohen's Kappa (&kappa;)</p>
              <p className="text-2xl font-bold text-neutral-900 dark:text-white">
                {kappa.toFixed(4)}
              </p>
              <span className="inline-block px-2 py-0.5 rounded border text-[10px] font-mono border-neutral-200 dark:border-neutral-700 bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400">
                {interpretation.label}
              </span>
            </div>

            {/* Raw Agreement Rate */}
            <div className="p-3 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 space-y-1">
              <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Raw Agreement Rate</p>
              <p className="text-2xl font-bold text-neutral-900 dark:text-white">
                {agreement.toFixed(1)}%
              </p>
              <p className="text-[10px] text-neutral-500">Unadjusted direct verdict match</p>
            </div>

            {/* Overlapping Matchups */}
            <div className="p-3 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 space-y-1">
              <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Overlapping Matchups</p>
              <p className="text-2xl font-bold text-neutral-900 dark:text-white">
                {nTrials.toLocaleString()}
              </p>
              <p className="text-[10px] text-neutral-500">Identical prompt &amp; response pairs</p>
            </div>
          </div>

          {/* Kappa Gauge Bar */}
          <div className="space-y-1.5 font-mono text-xs">
            <div className="flex justify-between text-[10px] text-neutral-500">
              <span>0.0 (Pure Chance)</span>
              <span>0.4 (Fair)</span>
              <span>0.7 (Substantial)</span>
              <span>1.0 (Perfect)</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-neutral-200 dark:bg-neutral-800 overflow-hidden relative">
              <div
                className="h-full bg-slate-500 dark:bg-slate-400 transition-all duration-500 rounded-full"
                style={{ width: `${Math.max(0, Math.min(100, kappa * 100))}%` }}
              />
            </div>
          </div>

          {/* Academic Callout & Interpretation */}
          <div className="p-3 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-600 dark:text-neutral-400 space-y-1.5">
            <div className="flex items-center gap-1.5 text-neutral-900 dark:text-neutral-200 font-medium">
              <Info className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
              <span>Scientific Interpretation (Landis &amp; Koch Benchmark):</span>
            </div>
            <p className="leading-relaxed text-[11px]">
              Cohen's &kappa; evaluates agreement between two judges after accounting for chance agreement ($P_e$). A Kappa score of <strong className="text-neutral-900 dark:text-neutral-200">{kappa.toFixed(4)}</strong> indicates <strong className="text-neutral-900 dark:text-neutral-200">{interpretation.label}</strong> between <strong className="text-neutral-900 dark:text-neutral-200">{selectedA.label}</strong> and <strong className="text-neutral-900 dark:text-neutral-200">{selectedB.label}</strong> across {nTrials.toLocaleString()} overlapping evaluation pairs.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
