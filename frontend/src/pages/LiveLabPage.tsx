import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { executeLiveEvaluation, executeCalibratedEvaluation } from '../api/client';
import type { EvaluateResponse, CalibratedEvaluateResponse } from '../api/types';
import { useJudge } from '../context/JudgeContext';
import { TextHighlighter } from '../components/TextHighlighter';
import { ModelIcon, SingleModelIcon, formatModelName } from '../components/ModelIcons';
import { Play, RefreshCw, FlaskConical, CheckCircle2, Sparkles, ShieldCheck, AlertTriangle, Layers, ChevronDown, Check } from 'lucide-react';

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

const estimateTokens = (text: string) => {
  if (!text) return 0;
  const words = text.trim().split(/\s+/).length;
  return Math.ceil(words * 1.3);
};

export const LiveLabPage: React.FC = () => {
  const { judgeModel } = useJudge();
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [answerA, setAnswerA] = useState(DEFAULT_ANSWER_A);
  const [answerB, setAnswerB] = useState(DEFAULT_ANSWER_B);
  const [modelName, setModelName] = useState(judgeModel);
  const [evalMode, setEvalMode] = useState<'standard' | 'calibrated'>('standard');
  const [mitigationStrategy, setMitigationStrategy] = useState<'dual_ab' | 'verbosity_penalized' | 'none'>('dual_ab');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  useEffect(() => {
    setModelName(judgeModel);
  }, [judgeModel]);

  const [loading, setLoading] = useState(false);
  const [executionStep, setExecutionStep] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [standardResult, setStandardResult] = useState<EvaluateResponse | null>(null);
  const [calibratedResult, setCalibratedResult] = useState<CalibratedEvaluateResponse | null>(null);

  // Calculated Token Telemetry
  const promptTokens = estimateTokens(prompt);
  const answerATokens = estimateTokens(answerA);
  const answerBTokens = estimateTokens(answerB);
  const totalInputTokensEst = promptTokens + answerATokens + answerBTokens;
  const isLocal = modelName.includes('llama') || modelName.includes('ollama') || modelName.includes('local');
  const maxContextTokens = isLocal ? 8192 : 128000;
  const isContextWarning = totalInputTokensEst > (isLocal ? 2000 : 32000);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
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
      if (evalMode === 'calibrated') {
        const res = await executeCalibratedEvaluation({
          question: prompt,
          answer_a: answerA,
          answer_b: answerB,
          model_name: modelName,
          mitigation_strategy: mitigationStrategy,
        });
        setCalibratedResult(res);
        setStandardResult(null);
      } else {
        const res = await executeLiveEvaluation({
          prompt: prompt,
          answer_a: answerA,
          answer_b: answerB,
          model_name: modelName,
        });
        setStandardResult(res);
        setCalibratedResult(null);
      }
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err)
        ? (err.response?.data?.detail || err.message)
        : (err instanceof Error ? err.message : 'Failed to execute evaluation');
      setError(msg);
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
            Test prompt pairs in real-time with standard G-EVAL or active bias mitigation protocols.
          </p>
        </div>
        <button
          type="button"
          onClick={handleReset}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-950 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white transition-colors cursor-pointer text-xs font-mono self-start sm:self-auto"
        >
          <RefreshCw className="w-3 h-3" />
          <span>Reset Sample Data</span>
        </button>
      </div>

      {/* Form and Execution Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Form Panel (7 Cols) */}
        <form onSubmit={handleSubmit} className="lg:col-span-7 space-y-4">
          <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-4">
            {/* Evaluation Engine Mode & Model Selector */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pb-3 border-b border-neutral-200 dark:border-neutral-800">
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

              <div>
                <label className="block text-[11px] font-mono font-semibold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider mb-1">
                  Mitigation Mode
                </label>
                <div className="grid grid-cols-2 gap-1 p-0.5 rounded bg-neutral-200/60 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-xs font-mono">
                  <button
                    type="button"
                    onClick={() => setEvalMode('standard')}
                    className={`py-1 px-2 rounded text-[11px] font-medium flex items-center justify-center gap-1 transition-all ${
                      evalMode === 'standard'
                        ? 'bg-white dark:bg-neutral-950 text-neutral-900 dark:text-white font-semibold shadow-xs'
                        : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
                    }`}
                  >
                    <Layers className="w-3 h-3" />
                    <span>Standard</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setEvalMode('calibrated')}
                    className={`py-1 px-2 rounded text-[11px] font-medium flex items-center justify-center gap-1 transition-all ${
                      evalMode === 'calibrated'
                        ? 'bg-white dark:bg-neutral-950 text-teal-700 dark:text-teal-400 font-semibold shadow-xs'
                        : 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white'
                    }`}
                  >
                    <ShieldCheck className="w-3 h-3 text-teal-600 dark:text-teal-400" />
                    <span>Calibrated</span>
                  </button>
                </div>
              </div>
            </div>

            {evalMode === 'calibrated' && (
              <div className="pb-3 border-b border-neutral-200 dark:border-neutral-800 space-y-1">
                <label className="block text-[11px] font-mono font-semibold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider">
                  Active Mitigation Strategy
                </label>
                <select
                  value={mitigationStrategy}
                  onChange={(e: any) => setMitigationStrategy(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs font-mono text-neutral-900 dark:text-neutral-100 focus:outline-none focus:border-teal-500/60 cursor-pointer"
                >
                  <option value="dual_ab">Dual A/B Swap (Position Bias Mitigation)</option>
                  <option value="verbosity_penalized">Length Penalization (Verbosity Bias Mitigation)</option>
                  <option value="none">None (Uncalibrated Baseline)</option>
                </select>
              </div>
            )}

            {/* Context Budget & Token Telemetry Bar */}
            <div className="p-2.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 font-mono text-[11px] space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-neutral-500 flex items-center gap-1.5">
                  <span>Target Context Limit:</span>
                  <strong className="text-neutral-800 dark:text-neutral-200">{maxContextTokens.toLocaleString()} tokens</strong>
                </span>
                <span className="text-neutral-500">
                  Est. Prompt Payload: <strong className={isContextWarning ? 'text-amber-600 dark:text-amber-400 font-bold' : 'text-teal-600 dark:text-teal-400 font-semibold'}>{totalInputTokensEst.toLocaleString()} tokens</strong>
                </span>
              </div>
              <div className="w-full bg-neutral-200 dark:bg-neutral-900 h-1.5 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 ${
                    isContextWarning ? 'bg-amber-500' : 'bg-teal-500'
                  }`}
                  style={{ width: `${Math.min(100, (totalInputTokensEst / maxContextTokens) * 100)}%` }}
                />
              </div>
              {isContextWarning && (
                <div className="flex items-center gap-1.5 text-[10px] text-amber-600 dark:text-amber-400 pt-0.5">
                  <AlertTriangle className="w-3 h-3 shrink-0" />
                  <span>High Token Payload: Long essay input approaches local inference context bounds.</span>
                </div>
              )}
            </div>

            {/* Prompt Input */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-mono font-semibold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider">
                  Question / Prompt
                </label>
                <span className="text-[10px] font-mono text-neutral-500">~{promptTokens} tokens</span>
              </div>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={2}
                placeholder="Enter evaluation prompt..."
                className="w-full p-2.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs font-mono text-neutral-900 dark:text-neutral-100 focus:outline-none focus:border-teal-500/60 dark:focus:border-teal-500/60 transition-colors"
              />
            </div>

            {/* Candidate Answers Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-mono font-semibold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider">
                    Candidate Answer A
                  </label>
                  <span className="text-[10px] font-mono text-neutral-500">~{answerATokens} tokens</span>
                </div>
                <textarea
                  value={answerA}
                  onChange={(e) => setAnswerA(e.target.value)}
                  rows={8}
                  placeholder="Enter Answer A text..."
                  className="w-full p-2.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs font-mono text-neutral-900 dark:text-neutral-100 focus:outline-none focus:border-teal-500/60 dark:focus:border-teal-500/60 transition-colors"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-mono font-semibold text-neutral-800 dark:text-neutral-200 uppercase tracking-wider">
                    Candidate Answer B
                  </label>
                  <span className="text-[10px] font-mono text-neutral-500">~{answerBTokens} tokens</span>
                </div>
                <textarea
                  value={answerB}
                  onChange={(e) => setAnswerB(e.target.value)}
                  rows={8}
                  placeholder="Enter Answer B text..."
                  className="w-full p-2.5 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 text-xs font-mono text-neutral-900 dark:text-neutral-100 focus:outline-none focus:border-teal-500/60 dark:focus:border-teal-500/60 transition-colors"
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
              disabled={loading}
              className="w-full py-2.5 px-4 rounded bg-neutral-900 dark:bg-neutral-100 hover:bg-neutral-800 dark:hover:bg-neutral-200 text-white dark:text-neutral-900 font-mono text-xs font-semibold flex items-center justify-center space-x-2 transition-colors cursor-pointer disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-teal-400" />
                  <span>
                    {evalMode === 'calibrated'
                      ? `[Step ${executionStep || 1}/3] ${
                          executionStep === 1
                            ? 'Pass 1 (Order A vs B) In-Flight...'
                            : executionStep === 2
                            ? 'Pass 2 (Order B vs A) In-Flight...'
                            : 'Debiasing Consensus Synthesis...'
                        }`
                      : 'Executing G-EVAL Verdict...'}
                  </span>
                </>
              ) : (
                <>
                  {evalMode === 'calibrated' ? (
                    <ShieldCheck className="w-3.5 h-3.5 text-teal-500 fill-current" />
                  ) : (
                    <Play className="w-3.5 h-3.5 fill-current" />
                  )}
                  <span>
                    {evalMode === 'calibrated'
                      ? 'Run Dual A/B Swap Calibrated Trial'
                      : 'Run Standard G-EVAL Evaluation Trial'}
                  </span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Right Output Panel (5 Cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 h-full flex flex-col justify-between space-y-4">
            <div>
              <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3 mb-3">
                <span className="font-semibold text-neutral-900 dark:text-neutral-100 text-xs font-mono uppercase tracking-wider flex items-center gap-1.5">
                  {evalMode === 'calibrated' && <ShieldCheck className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />}
                  <span>{evalMode === 'calibrated' ? 'Calibrated Telemetry Output' : 'Standard Evaluation Output'}</span>
                </span>
                {(calibratedResult || standardResult) && (
                  <span className="text-[10px] font-mono text-neutral-500 border border-neutral-200 dark:border-neutral-800 px-2 py-0.5 rounded inline-flex items-center gap-1.5">
                    <ModelIcon modelName={calibratedResult ? calibratedResult.model_name : (standardResult?.model_name || '')} className="w-3.5 h-3.5 shrink-0" />
                    <span>{formatModelName(calibratedResult ? calibratedResult.model_name : (standardResult?.model_name || ''))}</span>
                  </span>
                )}
              </div>

              {calibratedResult ? (
                <div className="space-y-4">
                  {/* Calibrated Status & Verdict Badges */}
                  <div className="space-y-2 p-3 rounded bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono text-neutral-500">Position Bias Status:</span>
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
                            <span>Bias Detected (Neutralized to TIE)</span>
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="w-3 h-3" />
                            <span>No Position Bias Detected</span>
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

                    <div className="pt-2 border-t border-neutral-100 dark:border-neutral-900 flex items-center justify-between">
                      <span className="text-xs font-mono font-semibold text-neutral-700 dark:text-neutral-300">
                        Final Calibrated Verdict:
                      </span>
                      <span className="inline-flex items-center gap-1 font-mono text-xs font-bold px-2.5 py-1 rounded bg-teal-500/10 text-teal-700 dark:text-teal-300 border border-teal-500/20">
                        <ShieldCheck className="w-3.5 h-3.5" />
                        <span>Winner: {calibratedResult.final_calibrated_winner}</span>
                      </span>
                    </div>
                  </div>

                  {/* Token Metrics Callout */}
                  <div className="flex items-center justify-between px-3 py-2 rounded bg-neutral-100 dark:bg-neutral-900 text-[10px] font-mono text-neutral-500">
                    <span>Input Tokens: {calibratedResult.total_input_tokens}</span>
                    <span>Output Tokens: {calibratedResult.total_output_tokens}</span>
                    <span>Tokens Total: {calibratedResult.total_input_tokens + calibratedResult.total_output_tokens}</span>
                  </div>

                  {/* Detailed Auditable Reasoning Inspector */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-[11px] font-mono text-neutral-500">
                      <span>Dual-Pass Auditable Reasoning Narrative</span>
                      <span className="flex items-center gap-1 text-[10px] text-teal-600 dark:text-teal-400">
                        <Sparkles className="w-3 h-3" />
                        Dual A/B Active
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

            <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-[11px] text-neutral-500 font-mono flex items-center justify-between">
              <span>Sampling Temp: $T=0.0$</span>
              <span>Mode: {evalMode === 'calibrated' ? 'Dual A/B Swap Active' : 'Single Pass G-EVAL'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
