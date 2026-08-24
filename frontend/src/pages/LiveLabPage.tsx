import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { executeLiveEvaluation, executeCalibratedEvaluation, executeEnsembleEvaluation, getLiveSandboxStatus } from '../api/client';
import type { EvaluateResponse, CalibratedEvaluateResponse, EnsembleEvaluateResponse } from '../api/types';
import { useJudge } from '../context/JudgeContext';
import { TextHighlighter } from '../components/TextHighlighter';
import { ModelIcon, SingleModelIcon, formatModelName } from '../components/ModelIcons';
import { Play, RefreshCw, FlaskConical, CheckCircle2, Sparkles, ShieldCheck, AlertTriangle, Layers, ChevronDown, Check, Users, CheckSquare, Square } from 'lucide-react';

const DEFAULT_PROMPT = `What are the top attractions and cultural experiences in Hawaii?`;

const DEFAULT_ANSWER_A = `Hawaii offers several premier attractions:
1. The Polynesian Cultural Center on Oahu provides specific details about Polynesian history and interactive exhibits.
2. 'Iolani Palace, the only royal palace in the United States.
3. Hawaii Volcanoes National Park on the Big Island.

These attractions provide comprehensive cultural and historical experiences across multiple islands.`;

const DEFAULT_ANSWER_B = `Hawaii has nice beaches, Pearl Harbor, and the Polynesian Cultural Center. However, it lacks specific details about volcanic parks, making it slightly less informative.`;

const EVALUATOR_MODELS = [
  { value: 'gpt-4o-mini', label: 'GPT-4o-Mini (Cloud / OpenAI)', icon: 'gpt-4o-mini' },
  { value: 'deepseek/deepseek-chat', label: 'DeepSeek V3 Chat (OpenRouter)', icon: 'deepseek/deepseek-chat' },
  { value: 'meta-llama/llama-3.3-70b-instruct', label: 'Llama 3.3 70B Instruct (OpenRouter)', icon: 'meta-llama/llama-3.3-70b-instruct' },
  { value: 'anthropic/claude-3-haiku', label: 'Claude 3 Haiku (OpenRouter)', icon: 'anthropic/claude-3-haiku' },
];

function safeLiveError(error: unknown): string {
  if (!axios.isAxiosError(error)) return 'Live evaluation could not be completed. Check the backend and try again.';
  if (!error.response) return error.code === 'ECONNABORTED'
    ? 'The provider request timed out. No final controlled evidence was affected.'
    : 'The backend is unavailable. Check that the local API server is running.';
  if (error.response.status === 403) return 'Local live execution is disabled. Set ENABLE_LIVE_SANDBOX_PROVIDER_CALLS=true on the backend before running a manual evaluation.';
  if (error.response.status === 400 || error.response.status === 422) return 'Check the prompt, answers, and selected evaluation options.';
  if (error.response.status === 408 || error.response.status === 504) return 'The provider request timed out. Try again or select a different configuration.';
  return 'The provider or backend could not complete this manual evaluation. No frozen evidence was changed.';
}

export const LiveLabPage: React.FC = () => {
  const { judgeModel } = useJudge();
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [answerA, setAnswerA] = useState(DEFAULT_ANSWER_A);
  const [answerB, setAnswerB] = useState(DEFAULT_ANSWER_B);
  const [modelName, setModelName] = useState(judgeModel);
  const [evalMode, setEvalMode] = useState<'standard' | 'calibrated' | 'ensemble'>('standard');
  const [mitigationStrategy, setMitigationStrategy] = useState<'dual_ab' | 'verbosity_penalized' | 'none'>('dual_ab');
  const [selectedEnsembleModels, setSelectedEnsembleModels] = useState<string[]>([
    'gpt-4o-mini',
    'deepseek/deepseek-chat',
    'meta-llama/llama-3.3-70b-instruct',
  ]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  useEffect(() => {
    setModelName(judgeModel);
  }, [judgeModel]);

  const [liveExecutionEnabled, setLiveExecutionEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;
    void getLiveSandboxStatus()
      .then(({ enabled }) => {
        if (active) setLiveExecutionEnabled(enabled);
      })
      .catch(() => {
        if (active) setLiveExecutionEnabled(null);
      });
    return () => { active = false; };
  }, []);

  const [loading, setLoading] = useState(false);
  const [executionStep, setExecutionStep] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [standardResult, setStandardResult] = useState<EvaluateResponse | null>(null);
  const [calibratedResult, setCalibratedResult] = useState<CalibratedEvaluateResponse | null>(null);
  const [ensembleResult, setEnsembleResult] = useState<EnsembleEvaluateResponse | null>(null);
  const [expandedJudges, setExpandedJudges] = useState<Record<number, boolean>>({});

  const toggleJudgeExpanded = (idx: number) => {
    setExpandedJudges((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const toggleEnsembleModel = (value: string) => {
    setSelectedEnsembleModels((prev) => {
      if (prev.includes(value)) {
        if (prev.length <= 1) return prev;
        return prev.filter((m) => m !== value);
      } else {
        if (prev.length >= 3) {
          // FIFO auto-swap: evict oldest selected model and append new selection
          return [...prev.slice(1), value];
        }
        return [...prev, value];
      }
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (liveExecutionEnabled === false) {
      setError('Local live execution is disabled by server configuration. Set ENABLE_LIVE_SANDBOX_PROVIDER_CALLS=true on the backend before running a manual evaluation.');
      return;
    }
    if (!prompt.trim() || !answerA.trim() || !answerB.trim()) {
      setError('Please provide a Prompt, Answer A, and Answer B.');
      return;
    }

    setLoading(true);
    setError(null);
    setExecutionStep(1);

    const stepInterval = setInterval(() => {
      setExecutionStep((prev) => (prev < 3 ? prev + 1 : prev));
    }, 1200);

    try {
      if (evalMode === 'ensemble') {
        const res = await executeEnsembleEvaluation({
          question: prompt,
          answer_a: answerA,
          answer_b: answerB,
          judge_models: selectedEnsembleModels,
          mitigation_strategy: mitigationStrategy,
        });
        setEnsembleResult(res);
        setStandardResult(null);
        setCalibratedResult(null);
      } else if (evalMode === 'calibrated') {
        const res = await executeCalibratedEvaluation({
          question: prompt,
          answer_a: answerA,
          answer_b: answerB,
          model_name: modelName,
          mitigation_strategy: mitigationStrategy,
        });
        setCalibratedResult(res);
        setStandardResult(null);
        setEnsembleResult(null);
      } else {
        const res = await executeLiveEvaluation({
          prompt: prompt,
          answer_a: answerA,
          answer_b: answerB,
          model_name: modelName,
        });
        setStandardResult(res);
        setCalibratedResult(null);
        setEnsembleResult(null);
      }
    } catch (err: unknown) {
      setError(safeLiveError(err));
    } finally {
      clearInterval(stepInterval);
      setLoading(false);
      setExecutionStep(0);
    }
  };

  const handleReset = () => {
    setPrompt(DEFAULT_PROMPT);
    setAnswerA(DEFAULT_ANSWER_A);
    setAnswerB(DEFAULT_ANSWER_B);
    setStandardResult(null);
    setCalibratedResult(null);
    setEnsembleResult(null);
  };

  return (
    <div className="max-w-[1400px] mx-auto space-y-6 py-2 font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-200 dark:border-neutral-800 pb-4">
        <div>
          <h2 className="text-xl font-bold text-neutral-900 dark:text-neutral-100">
            Live Evaluation Sandbox
          </h2>
          <p className="text-xs text-neutral-500 mt-1">
            LIVE / MANUAL EVALUATION — ad-hoc tests are not included in frozen controlled RQ1–RQ7 evidence.
          </p>
          <p className="text-[11px] text-neutral-500 mt-1" aria-live="polite">
            {liveExecutionEnabled === false
              ? 'Real provider execution is disabled by this server configuration.'
              : liveExecutionEnabled === true
                ? 'Real provider execution is enabled for this local server.'
                : 'Real provider execution is controlled by this server configuration.'}
          </p>
        </div>
        <div className="flex items-center gap-1 self-start sm:self-auto">
          <button
            type="button"
            onClick={handleReset}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-950 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white transition-colors cursor-pointer text-xs font-mono"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Reset Sample Data</span>
          </button>
        </div>
      </div>

      {/* Form and Execution Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Form Panel (7 Cols) */}
        <form onSubmit={handleSubmit} className="lg:col-span-7 space-y-4">
          <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-4">
            {/* Evaluation Engine Mode & Model Selector */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pb-3 border-b border-neutral-200 dark:border-neutral-800">
              {evalMode !== 'ensemble' ? (
                <div className="relative">
                  <label className="block text-[11px] font-mono font-semibold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider mb-1">
                    Evaluator Model
                  </label>
                  <button
                    type="button"
                    onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                    className="w-full px-2.5 py-1.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs font-mono text-neutral-900 dark:text-neutral-100 flex items-center justify-between cursor-pointer focus:outline-none focus:border-teal-500/60"
                  >
                    <span className="flex items-center gap-2">
                      <SingleModelIcon modelName={modelName} className="w-4 h-4 shrink-0" />
                      <span>{EVALUATOR_MODELS.find(m => m.value === modelName)?.label || modelName}</span>
                    </span>
                    <ChevronDown className={`w-3.5 h-3.5 text-neutral-500 shrink-0 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} />
                  </button>

                  {isDropdownOpen && (
                    <div className="absolute top-full left-0 mt-1 w-full z-30 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 shadow-xl py-1 font-mono text-xs">
                      {EVALUATOR_MODELS.map((item) => (
                        <button
                          key={item.value}
                          type="button"
                          onClick={() => {
                            setModelName(item.value);
                            setIsDropdownOpen(false);
                          }}
                          className={`w-full px-2.5 py-2 text-left flex items-center justify-between hover:bg-neutral-100 dark:hover:bg-neutral-900 cursor-pointer ${
                            modelName === item.value ? 'bg-neutral-100 dark:bg-neutral-900 font-semibold' : ''
                          }`}
                        >
                          <span className="flex items-center gap-2">
                            <SingleModelIcon modelName={item.icon} className="w-4 h-4 shrink-0" />
                            <span>{item.label}</span>
                          </span>
                          {modelName === item.value && <Check className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400 shrink-0" />}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <label className="block text-[11px] font-mono font-semibold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider mb-1">
                    Ensemble Protocol
                  </label>
                  <div className="px-2.5 py-1.5 rounded bg-neutral-200/80 dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 text-xs font-mono text-neutral-800 dark:text-neutral-200 flex items-center justify-between">
                    <span className="flex items-center gap-1.5 font-semibold">
                      <Users className="w-4 h-4 text-neutral-700 dark:text-neutral-300 shrink-0" />
                      <span>Multi-Judge Voting</span>
                    </span>
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-neutral-300/80 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100">
                      {selectedEnsembleModels.length} Models
                    </span>
                  </div>
                </div>
              )}

              <div>
                <label className="block text-[11px] font-mono font-semibold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider mb-1">
                  Evaluation Protocol Mode
                </label>
                <div className="grid grid-cols-3 gap-1 p-0.5 rounded bg-neutral-200/60 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-xs font-mono">
                  <button
                    type="button"
                    onClick={() => setEvalMode('standard')}
                    className={`py-1 px-1.5 rounded text-[10px] font-medium flex items-center justify-center gap-1 transition-all ${
                      evalMode === 'standard'
                        ? 'bg-white dark:bg-neutral-950 text-neutral-900 dark:text-white font-semibold border border-neutral-300 dark:border-neutral-700'
                        : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
                    }`}
                  >
                    <Layers className="w-3 h-3" />
                    <span>Standard</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setEvalMode('calibrated')}
                    className={`py-1 px-1.5 rounded text-[10px] font-medium flex items-center justify-center gap-1 transition-all ${
                      evalMode === 'calibrated'
                        ? 'bg-white dark:bg-neutral-950 text-teal-700 dark:text-teal-400 font-semibold border border-teal-500/40'
                        : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
                    }`}
                  >
                    <ShieldCheck className="w-3 h-3 text-teal-600 dark:text-teal-400" />
                    <span>Calibrated</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setEvalMode('ensemble')}
                    className={`py-1 px-1.5 rounded text-[10px] font-medium flex items-center justify-center gap-1 transition-all ${
                      evalMode === 'ensemble'
                        ? 'bg-white dark:bg-neutral-950 text-indigo-600 dark:text-indigo-400 font-semibold border border-indigo-500/40'
                        : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
                    }`}
                  >
                    <Users className="w-3 h-3 text-indigo-600 dark:text-indigo-400" />
                    <span>Ensemble</span>
                  </button>
                </div>
              </div>
            </div>

            {evalMode === 'ensemble' && (
              <div className="pb-3 border-b border-neutral-200 dark:border-neutral-800 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-[11px] font-mono font-semibold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider">
                    Select Ensemble Judge Models ({selectedEnsembleModels.length} selected)
                  </label>
                  <span className="text-[10px] font-mono text-neutral-600 dark:text-neutral-400 font-medium">
                    Concurrent Majority Voting
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {EVALUATOR_MODELS.map((item) => {
                    const isSelected = selectedEnsembleModels.includes(item.value);
                    return (
                      <button
                        key={item.value}
                        type="button"
                        onClick={() => toggleEnsembleModel(item.value)}
                        className={`p-2 rounded border text-xs font-mono text-left flex items-center justify-between transition-colors cursor-pointer ${
                          isSelected
                            ? 'bg-neutral-200/80 dark:bg-neutral-900 border-neutral-400 dark:border-neutral-700 text-neutral-900 dark:text-white font-semibold'
                            : 'bg-white dark:bg-neutral-950 border-neutral-200 dark:border-neutral-800 text-neutral-500 hover:text-neutral-900 dark:hover:text-white'
                        }`}
                      >
                        <span className="flex items-center gap-2 truncate">
                          <SingleModelIcon modelName={item.icon} className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate">{item.label}</span>
                        </span>
                        {isSelected ? (
                          <CheckSquare className="w-3.5 h-3.5 text-neutral-800 dark:text-neutral-200 shrink-0 ml-1" />
                        ) : (
                          <Square className="w-3.5 h-3.5 text-neutral-400 shrink-0 ml-1" />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {(evalMode === 'calibrated' || evalMode === 'ensemble') && (
              <div className="pb-3 border-b border-neutral-200 dark:border-neutral-800 space-y-1">
                <label className="block text-[11px] font-mono font-semibold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider">
                  Trial Protocol
                </label>
                <select
                  value={mitigationStrategy}
                  onChange={(e: any) => setMitigationStrategy(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs font-mono text-neutral-900 dark:text-neutral-100 focus:outline-none focus:border-neutral-500 cursor-pointer"
                >
                  <option value="dual_ab">Dual A/B Swap (two presentation orders)</option>
                  <option value="verbosity_penalized">Length Penalization (prompt adjustment)</option>
                  <option value="none">None (Uncalibrated Baseline)</option>
                </select>
              </div>
            )}

            {/* Prompt Input */}
            <div className="space-y-1.5">
              <label className="block text-xs font-mono font-semibold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider">
                Question / Prompt
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={2}
                placeholder="Enter evaluation prompt..."
                className="w-full p-2.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs font-mono text-neutral-900 dark:text-neutral-100 focus:outline-none focus:border-neutral-500 transition-colors"
              />
            </div>

            {/* Candidate Answers Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="block text-xs font-mono font-semibold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider">
                  Candidate Answer A
                </label>
                <textarea
                  value={answerA}
                  onChange={(e) => setAnswerA(e.target.value)}
                  rows={8}
                  placeholder="Enter Answer A text..."
                  className="w-full p-2.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs font-mono text-neutral-900 dark:text-neutral-100 focus:outline-none focus:border-neutral-500 transition-colors"
                />
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-mono font-semibold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider">
                  Candidate Answer B
                </label>
                <textarea
                  value={answerB}
                  onChange={(e) => setAnswerB(e.target.value)}
                  rows={8}
                  placeholder="Enter Answer B text..."
                  className="w-full p-2.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs font-mono text-neutral-900 dark:text-neutral-100 focus:outline-none focus:border-neutral-500 transition-colors"
                />
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/20 text-xs font-mono text-rose-600 dark:text-rose-400">
                {error}
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading || liveExecutionEnabled === false}
              className="w-full py-2.5 px-4 rounded bg-neutral-900 dark:bg-neutral-100 hover:bg-neutral-800 dark:hover:bg-neutral-200 text-white dark:text-neutral-900 font-mono text-xs font-semibold flex items-center justify-center space-x-2 transition-colors cursor-pointer disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-neutral-400" />
                  <span>
                    {evalMode === 'ensemble'
                      ? `Running Multi-Judge Voting across ${selectedEnsembleModels.length} Models...`
                      : evalMode === 'calibrated'
                      ? (mitigationStrategy === 'verbosity_penalized'
                          ? 'Evaluating Length Penalization Trial...'
                          : mitigationStrategy === 'none'
                          ? 'Executing Uncalibrated Baseline Trial...'
                          : `[Step ${executionStep || 1}/3] ${
                              executionStep === 1
                                ? 'Pass 1 (Order A vs B) In-Flight...'
                                : executionStep === 2
                                ? 'Pass 2 (Order B vs A) In-Flight...'
                                : 'Combining dual-pass outcomes...'
                            }`)
                      : 'Executing G-EVAL Verdict...'}
                  </span>
                </>
              ) : (
                <>
                  {evalMode === 'ensemble' ? (
                    <Users className="w-3.5 h-3.5 text-neutral-300 dark:text-neutral-700 fill-current" />
                  ) : evalMode === 'calibrated' ? (
                    <ShieldCheck className="w-3.5 h-3.5 text-teal-500 fill-current" />
                  ) : (
                    <Play className="w-3.5 h-3.5 fill-current" />
                  )}
                  <span>
                    {liveExecutionEnabled === false
                      ? 'Live execution disabled by server'
                      : evalMode === 'ensemble'
                      ? 'Run Ensemble Consensus'
                      : evalMode === 'calibrated'
                      ? (mitigationStrategy === 'verbosity_penalized'
                          ? 'Run Length-Adjusted Evaluation Trial'
                          : mitigationStrategy === 'none'
                          ? 'Run Uncalibrated Baseline Trial'
                          : 'Run Dual A/B Swap Trial')
                      : 'Run Standard G-EVAL Evaluation Trial'}
                  </span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Right Output Panel (5 Cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 h-full flex flex-col justify-between">
            <div className="flex flex-col flex-1 min-h-0 space-y-3">
              <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3 shrink-0">
                <span className="font-semibold text-neutral-900 dark:text-neutral-100 text-xs font-mono uppercase tracking-wider flex items-center gap-1.5">
                  {evalMode === 'ensemble' ? (
                    <Users className="w-3.5 h-3.5 text-neutral-700 dark:text-neutral-300" />
                  ) : evalMode === 'calibrated' ? (
                    <ShieldCheck className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />
                  ) : null}
                  <span>
                    {evalMode === 'ensemble'
                      ? 'Ensemble Consensus Telemetry'
                      : evalMode === 'calibrated'
                      ? 'Manual Trial Output'
                      : 'Standard Evaluation Output'}
                  </span>
                </span>
                {(calibratedResult || standardResult || ensembleResult) && (
                  <span className="text-[10px] font-mono text-neutral-500 border border-neutral-200 dark:border-neutral-800 px-2 py-0.5 rounded inline-flex items-center gap-1.5">
                    {ensembleResult ? (
                      <Users className="w-3.5 h-3.5 text-neutral-600 dark:text-neutral-400 shrink-0" />
                    ) : (
                      <ModelIcon modelName={calibratedResult ? calibratedResult.model_name : (standardResult?.model_name || '')} className="w-3.5 h-3.5 shrink-0" />
                    )}
                    <span>
                      {ensembleResult
                        ? `${ensembleResult.successful_models} Judges`
                        : formatModelName(calibratedResult ? calibratedResult.model_name : (standardResult?.model_name || ''))}
                    </span>
                  </span>
                )}
              </div>

              {ensembleResult ? (
                <div className="flex flex-col flex-1 min-h-0 space-y-3">
                  {/* Consensus Status & Vote Counts */}
                  <div className="p-3 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 space-y-3 shrink-0">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono text-neutral-500">Ensemble Consensus Verdict:</span>
                      <span className="inline-flex items-center gap-1.5 font-mono text-xs font-bold px-2.5 py-1 rounded bg-neutral-200/80 dark:bg-neutral-900 text-neutral-900 dark:text-white border border-neutral-300 dark:border-neutral-700">
                        <Users className="w-3.5 h-3.5" />
                        <span>Winner: {ensembleResult.consensus_verdict}</span>
                      </span>
                    </div>

                    <div className="grid grid-cols-4 gap-2 pt-2 border-t border-neutral-100 dark:border-neutral-900 text-[11px] font-mono text-center">
                      <div className="p-1.5 rounded bg-neutral-50 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
                        <span className="text-neutral-500 block text-[10px]">Answer A</span>
                        <span className="font-bold text-emerald-600 dark:text-emerald-400">{ensembleResult.vote_counts.A || 0} votes</span>
                      </div>
                      <div className="p-1.5 rounded bg-neutral-50 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
                        <span className="text-neutral-500 block text-[10px]">Answer B</span>
                        <span className="font-bold text-sky-600 dark:text-sky-400">{ensembleResult.vote_counts.B || 0} votes</span>
                      </div>
                      <div className="p-1.5 rounded bg-neutral-50 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
                        <span className="text-neutral-500 block text-[10px]">TIE</span>
                        <span className="font-bold text-amber-600 dark:text-amber-400">{ensembleResult.vote_counts.TIE || 0} votes</span>
                      </div>
                      <div className="p-1.5 rounded bg-neutral-50 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
                        <span className="text-neutral-500 block text-[10px]">Responded</span>
                        <span className="font-bold text-neutral-800 dark:text-neutral-200">{ensembleResult.successful_models}/{ensembleResult.total_models}</span>
                      </div>
                    </div>
                    {!ensembleResult.persisted && (
                      <p className="text-[10px] font-mono text-amber-700 dark:text-amber-300">
                        Result returned, but this manual trial was not saved.
                      </p>
                    )}
                  </div>

                  {/* Individual Judge Model Verdict Breakdown */}
                  <div className="flex flex-col flex-1 min-h-0 space-y-2">
                    <div className="flex items-center justify-between text-[11px] font-mono text-neutral-500 shrink-0">
                      <span>Individual Judge Model Votes</span>
                      <span className="flex items-center gap-1 text-[10px] text-neutral-600 dark:text-neutral-400 font-semibold">
                        <Users className="w-3 h-3" />
                        Majority Rule Active
                      </span>
                    </div>

                    <div className="flex-1 overflow-y-auto min-h-0 space-y-4 pr-2 mb-4">
                      {ensembleResult.individual_results.map((ind, i) => (
                        <div key={i} className="p-2.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs font-mono space-y-1.5 flex-shrink-0 h-fit">
                          <div className="flex items-center justify-between">
                            <span className="flex items-center gap-1.5 font-semibold text-neutral-900 dark:text-neutral-100">
                              <SingleModelIcon modelName={ind.model_name} className="w-3.5 h-3.5 shrink-0" />
                              <span>{formatModelName(ind.model_name)}</span>
                            </span>
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              ind.verdict === 'A'
                                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                                : ind.verdict === 'B'
                                ? 'bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20'
                                : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
                            }`}>
                              Vote: {ind.verdict}
                            </span>
                          </div>
                          {ind.reasoning ? (
                            <div
                              onClick={() => toggleJudgeExpanded(i)}
                              className={`p-2 rounded border transition-all cursor-pointer group ${
                                expandedJudges[i]
                                  ? 'bg-neutral-100 dark:bg-neutral-900 border-neutral-300 dark:border-neutral-700'
                                  : 'bg-neutral-50 dark:bg-neutral-900/60 border-neutral-200/80 dark:border-neutral-800 hover:border-neutral-400 dark:hover:border-neutral-600'
                              }`}
                            >
                              <div className="flex items-center justify-between text-[10px] text-neutral-400 font-mono mb-1 select-none">
                                <span>Reasoning Narrative</span>
                                <span className="text-[9px] text-neutral-500 group-hover:text-neutral-700 dark:group-hover:text-neutral-300 transition-colors font-semibold">
                                  {expandedJudges[i] ? 'Click to collapse ▲' : 'Click to expand ▼'}
                                </span>
                              </div>
                              <div
                                className={`text-[11px] text-neutral-700 dark:text-neutral-300 leading-relaxed font-mono ${
                                  expandedJudges[i] ? 'whitespace-pre-wrap' : 'line-clamp-2'
                                }`}
                              >
                                <TextHighlighter text={ind.reasoning} />
                              </div>
                            </div>
                          ) : (
                            <div className="p-2 rounded bg-neutral-50 dark:bg-neutral-900/40 border border-neutral-200/60 dark:border-neutral-800/60 text-[11px] text-neutral-400 font-mono italic">
                              No reasoning narrative provided by model.
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : calibratedResult ? (
                <div className="space-y-4">
                  {/* Calibrated Status & Verdict Badges */}
                  <div className="space-y-2 p-3 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800">
                    {mitigationStrategy === 'verbosity_penalized' ? (
                      <>
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-mono text-neutral-500">Trial Adjustment:</span>
                          <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-teal-500/10 text-teal-700 dark:text-teal-300 border border-teal-500/20">
                            <ShieldCheck className="w-3 h-3" />
                            <span>Length penalty applied for this trial</span>
                          </span>
                        </div>

                        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-neutral-100 dark:border-neutral-900 text-[11px] font-mono">
                          <div>
                            <span className="text-neutral-500 block text-[10px]">Candidate A Word Count:</span>
                            <span className="font-semibold text-neutral-800 dark:text-neutral-200">
                              {answerA.trim().split(/\s+/).length} words
                            </span>
                          </div>
                          <div>
                            <span className="text-neutral-500 block text-[10px]">Candidate B Word Count:</span>
                            <span className="font-semibold text-neutral-800 dark:text-neutral-200">
                              {answerB.trim().split(/\s+/).length} words
                            </span>
                          </div>
                        </div>
                      </>
                    ) : mitigationStrategy === 'none' ? (
                      <>
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-mono text-neutral-500">Evaluation Protocol:</span>
                          <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-neutral-100 text-neutral-600 dark:bg-neutral-800/50 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-700">
                            <span>Uncalibrated Baseline</span>
                          </span>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-mono text-neutral-500">Dual-pass comparison:</span>
                          <span
                            className={`inline-flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                              calibratedResult.position_bias_detected
                                ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
                                : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                            }`}
                          >
                            {calibratedResult.position_bias_detected ? (
                              <>
                                <AlertTriangle className="w-3 h-3" />
                                <span>Order-sensitive change observed in this trial</span>
                              </>
                            ) : (
                              <>
                                <CheckCircle2 className="w-3 h-3" />
                                <span>No order-sensitive change observed in this trial</span>
                              </>
                            )}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-neutral-100 dark:border-neutral-900 text-[11px] font-mono">
                          <div>
                            <span className="text-neutral-500 block text-[10px]">Pass 1 (Original Order):</span>
                            <span className="font-semibold text-neutral-800 dark:text-neutral-200">
                              Winner: Candidate {calibratedResult.original_order_winner}
                            </span>
                          </div>
                          <div>
                            <span className="text-neutral-500 block text-[10px]">Pass 2 (Swapped Order):</span>
                            <span className="font-semibold text-neutral-800 dark:text-neutral-200">
                              Mapped Winner: Candidate {calibratedResult.swapped_order_winner}
                            </span>
                          </div>
                        </div>
                      </>
                    )}

                    <div className="pt-2 border-t border-neutral-100 dark:border-neutral-900 flex items-center justify-between">
                      <span className="text-xs font-mono font-semibold text-neutral-700 dark:text-neutral-300">
                        Final result for this trial:
                      </span>
                      <span className="inline-flex items-center gap-1 font-mono text-xs font-bold px-2.5 py-1 rounded bg-teal-500/10 text-teal-700 dark:text-teal-300 border border-teal-500/20">
                        <ShieldCheck className="w-3.5 h-3.5" />
                        <span>Winner: {calibratedResult.final_calibrated_winner}</span>
                      </span>
                    </div>
                  </div>

                  {/* Single-trial summary */}
                  <div className="flex items-center justify-between px-3 py-2 rounded bg-teal-500/10 border border-teal-500/20 text-[11px] font-mono text-teal-700 dark:text-teal-300">
                    <span className="flex items-center gap-1.5 font-medium">
                      <ShieldCheck className="w-3.5 h-3.5 text-teal-500 shrink-0" />
                      <span>Trial summary:</span>
                    </span>
                    <span className="font-semibold">
                      {mitigationStrategy === 'verbosity_penalized'
                        ? 'Length penalty applied to this trial'
                        : mitigationStrategy === 'none'
                        ? 'Single-pass result'
                        : calibratedResult.position_bias_detected
                        ? 'Dual-pass result: mapped outcomes differed'
                        : 'Both presentation orders produced the same mapped outcome'}
                    </span>
                  </div>
                  <p className="text-[10px] font-mono text-neutral-500">
                    This result applies only to the current manual trial.
                  </p>

                  {/* Detailed Auditable Reasoning Inspector */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-[11px] font-mono text-neutral-500">
                      <span>
                        {mitigationStrategy === 'verbosity_penalized'
                          ? 'Length-Calibrated Reasoning Narrative'
                          : mitigationStrategy === 'none'
                          ? 'Uncalibrated Single-Pass Reasoning Narrative'
                          : 'Dual-Pass Auditable Reasoning Narrative'}
                      </span>
                      <span className="flex items-center gap-1 text-[10px] text-teal-600 dark:text-teal-400">
                        <Sparkles className="w-3 h-3" />
                        <span>
                          {mitigationStrategy === 'verbosity_penalized'
                            ? 'Length Penalty Active'
                            : mitigationStrategy === 'none'
                            ? 'Baseline Mode'
                            : 'Dual A/B Active'}
                        </span>
                      </span>
                    </div>

                    <div className="p-3 rounded bg-neutral-100 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800/80 text-xs font-mono text-neutral-800 dark:text-neutral-300 max-h-[300px] overflow-y-auto leading-relaxed whitespace-pre-wrap">
                      <TextHighlighter text={calibratedResult.detailed_reasoning} />
                    </div>
                  </div>
                </div>
              ) : standardResult ? (
                <div className="space-y-4">
                  {/* Verdict Badge */}
                  <div className="p-3 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 flex items-center justify-between">
                    <span className="text-xs font-mono text-neutral-500">Evaluator Verdict:</span>
                    <span
                      className={`inline-flex items-center gap-1.5 font-mono text-xs font-bold px-2.5 py-1 rounded ${
                        standardResult.winner === 'A'
                          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                          : standardResult.winner === 'B'
                          ? 'bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20'
                          : 'bg-neutral-200 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300'
                      }`}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>
                        {standardResult.winner === 'A'
                          ? 'Winner: Answer A'
                          : standardResult.winner === 'B'
                          ? 'Winner: Answer B'
                          : 'Verdict: Tie'}
                      </span>
                    </span>
                  </div>

                  {/* Verbatim G-EVAL Reasoning Inspector */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-[11px] font-mono text-neutral-500">
                      <span>Verbatim G-EVAL Reasoning Text</span>
                      <span className="flex items-center gap-1 text-[10px] text-teal-600 dark:text-teal-400">
                        <Sparkles className="w-3 h-3" />
                        Syntax Tokens Active
                      </span>
                    </div>

                    <div className="p-3 rounded bg-neutral-100 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800/80 text-xs font-mono text-neutral-800 dark:text-neutral-300 max-h-[360px] overflow-y-auto leading-relaxed whitespace-pre-wrap">
                      <TextHighlighter text={standardResult.verbatim_reasoning} />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-64 flex flex-col items-center justify-center text-center p-6 text-neutral-400 dark:text-neutral-600 space-y-2">
                  <FlaskConical className="w-8 h-8 opacity-40" />
                  <p className="text-xs font-mono">
                    No evaluation executed yet.
                  </p>
                  <p className="text-[11px] text-neutral-500 max-w-xs">
                    Select a mode and click "Run Trial" to execute a live pairwise comparison.
                  </p>
                </div>
              )}
            </div>

            <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-[11px] text-neutral-500 font-mono flex items-center justify-between mt-4 flex-shrink-0">
              <span>Sampling Temp: $T=0.0$</span>
              <span>
                Mode: {
                  evalMode === 'ensemble'
                    ? 'Multi-Judge Voting Active'
                    : evalMode === 'calibrated'
                    ? (mitigationStrategy === 'verbosity_penalized'
                        ? 'Length Penalization Active'
                        : mitigationStrategy === 'none'
                        ? 'Uncalibrated Baseline Active'
                        : 'Dual A/B Swap Active')
                    : 'Single Pass G-EVAL'
                }
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
