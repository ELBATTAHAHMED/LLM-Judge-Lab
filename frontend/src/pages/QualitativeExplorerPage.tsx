import React, { useState, useMemo } from 'react';
import { useQualitativeBucket } from '../api/client';
import type { QualitativeBucket, QualitativeRecord } from '../api/types';
import { TextHighlighter } from '../components/TextHighlighter';
import { CaseCommentaryCard } from '../components/CaseCommentaryCard';
import { FormattedMatchup, SingleModelIcon } from '../components/ModelIcons';
import { RefreshCw, Download, Copy, Check, MessageSquare, FileText } from 'lucide-react';

export const QualitativeExplorerPage: React.FC = () => {
  const [selectedBucket, setSelectedBucket] = useState<QualitativeBucket>('verbosity');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [copied, setCopied] = useState<boolean>(false);

  const { data, loading, error, refetch } = useQualitativeBucket(selectedBucket);

  const bucketTabs: {
    id: QualitativeBucket;
    label: string;
    countStr: string;
    definition: string;
  }[] = [
    {
      id: 'verbosity',
      label: 'Bucket A: Verbosity Bias',
      countStr: '167 cases',
      definition: 'AI chose longer answer (>50w diff) while human chose shorter/tie',
    },
    {
      id: 'forced_choice',
      label: 'Bucket B: Forced Choice',
      countStr: '262 cases',
      definition: 'Human choice was a TIE, but AI judge forced a winner decision',
    },
    {
      id: 'position_bias',
      label: 'Bucket C: Position Bias',
      countStr: '693 cases',
      definition: 'AI judge selected candidate response placed in Position B',
    },
    {
      id: 'baseline_alignment',
      label: 'Bucket D: Baseline Alignment',
      countStr: '937 cases',
      definition: 'Control group where AI judge verdict matches human preference',
    },
  ];

  const filteredData = useMemo(() => {
    if (!data) return [];
    if (!searchQuery.trim()) return data;
    const q = searchQuery.toLowerCase();
    return data.filter(
      (item) =>
        item.prompt_id.toString().toLowerCase().includes(q) ||
        item.model_names.toLowerCase().includes(q) ||
        item.reasoning_text.toLowerCase().includes(q)
    );
  }, [data, searchQuery]);

  const activeRecord: QualitativeRecord | null = useMemo(() => {
    if (filteredData.length === 0) return null;
    const safeIdx = selectedIndex < filteredData.length ? selectedIndex : 0;
    return filteredData[safeIdx];
  }, [filteredData, selectedIndex]);

  const handleCopyText = () => {
    if (!activeRecord) return;
    const fullTranscript = `=== TRIAL TRANSCRIPT (Prompt #${activeRecord.prompt_id}) ===
Models: ${activeRecord.model_names}
Human Ground Truth: ${activeRecord.human_winner}
AI Judge Verdict: ${activeRecord.ai_winner}
Word Count Disparity: ${activeRecord.word_count_diff > 0 ? '+' : ''}${activeRecord.word_count_diff} words

--- INPUT PROMPT ---
${activeRecord.prompt_text || 'Prompt text grounded in baseline reference dataset.'}

--- CANDIDATE ANSWER A (${activeRecord.answer_a_model || 'Answer A'}) ---
${activeRecord.answer_a_text || 'Detailed candidate response grounded in factual context.'}

--- CANDIDATE ANSWER B (${activeRecord.answer_b_model || 'Answer B'}) ---
${activeRecord.answer_b_text || 'Concise candidate response providing relevant summary details.'}

--- VERBATIM G-EVAL REASONING ---
${activeRecord.reasoning_text}
`;
    navigator.clipboard.writeText(fullTranscript);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExportJSON = () => {
    if (!filteredData || filteredData.length === 0) return;
    const jsonStr = JSON.stringify(filteredData, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `qualitative_${selectedBucket}_strata.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-[1400px] mx-auto space-y-6 py-2 font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-200 dark:border-neutral-800 pb-4">
        <div>
          <h1 className="text-2xl font-serif text-neutral-900 dark:text-white tracking-tight">
            Stratified Qualitative Reasoning Explorer
          </h1>
          <p className="text-xs text-neutral-600 dark:text-neutral-400 mt-1">
            Inspect verbatim judge reasoning outputs across 4 research strata to audit evaluative vocabulary shifts, hedging language, and cognitive disconnects
          </p>
        </div>

        <button
          onClick={refetch}
          disabled={loading}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-950 text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white transition-colors cursor-pointer text-xs self-start sm:self-auto font-mono"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Bucket Sub-Tabs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 items-stretch">
        {bucketTabs.map((tab) => {
          const isSelected = selectedBucket === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => {
                setSelectedBucket(tab.id);
                setSelectedIndex(0);
              }}
              className={`p-3.5 pb-4 rounded-lg text-left border transition-colors cursor-pointer flex flex-col justify-between h-full ${
                isSelected
                  ? 'bg-neutral-900 border-neutral-900 text-white dark:bg-neutral-900 dark:border-neutral-600'
                  : 'bg-neutral-50 hover:bg-neutral-100 border-neutral-200 text-neutral-600 dark:bg-[#0a0a0a] dark:hover:bg-neutral-900/60 dark:border-neutral-800 dark:text-neutral-400'
              }`}
            >
              <div>
                <div className="flex items-center justify-between font-mono text-[10px]">
                  <span className={isSelected ? 'text-neutral-300 font-semibold' : 'text-neutral-500'}>
                    {tab.label.split(':')[0]}
                  </span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono border ${
                    isSelected
                      ? 'bg-neutral-800 border-neutral-700 text-neutral-200'
                      : 'bg-white dark:bg-neutral-950 border-neutral-200 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400'
                  }`}>
                    {tab.countStr}
                  </span>
                </div>
                <p className={`text-xs font-semibold mt-1 ${isSelected ? 'text-white' : 'text-neutral-900 dark:text-neutral-300'}`}>
                  {tab.label.split(':')[1]}
                </p>
              </div>

              <p className={`text-xs leading-relaxed mt-2 whitespace-normal ${isSelected ? 'text-neutral-300 dark:text-neutral-300' : 'text-neutral-600 dark:text-neutral-400'}`}>
                {tab.definition}
              </p>
            </button>
          );
        })}
      </div>

      {/* Search Bar & Controls */}
      <div className="p-3 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 flex flex-col sm:flex-row gap-3 items-center justify-between text-xs transition-colors duration-150">
        <div className="w-full sm:w-80">
          <input
            type="text"
            placeholder="Search prompt ID, model names..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setSelectedIndex(0);
            }}
            className="w-full px-3 py-1.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-900 dark:text-neutral-200 placeholder-neutral-400 dark:placeholder-neutral-500 focus:outline-none focus:border-neutral-400 dark:focus:border-neutral-600 font-mono"
          />
        </div>

        <div className="flex items-center space-x-3 w-full sm:w-auto justify-between sm:justify-end font-mono">
          <span className="text-neutral-500">
            Filtered: <strong className="text-neutral-900 dark:text-white">{filteredData.length}</strong> / {data?.length || 0}
          </span>

          <button
            onClick={handleExportJSON}
            disabled={filteredData.length === 0}
            className="flex items-center space-x-1 px-3 py-1 rounded bg-white dark:bg-neutral-900 hover:bg-neutral-100 dark:hover:bg-neutral-800 border border-neutral-200 dark:border-neutral-800 text-neutral-700 dark:text-neutral-300 transition-colors disabled:opacity-40 cursor-pointer"
          >
            <Download className="w-3 h-3 text-neutral-500 dark:text-neutral-400" />
            <span>Export JSON</span>
          </button>
        </div>
      </div>

      {/* Master-Detail Split-Pane Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 h-[600px]">
        {/* Left Pane (Master List - 35% / 4 cols) */}
        <div className="lg:col-span-4 bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 rounded-lg overflow-hidden flex flex-col h-full transition-colors duration-150">
          <div className="px-3 py-2 border-b border-neutral-200 dark:border-neutral-800 bg-neutral-100 dark:bg-neutral-900/60 flex justify-between items-center text-xs font-mono text-neutral-500">
            <span>Case Master List</span>
            <span>Select to inspect</span>
          </div>

          {loading ? (
            <div className="p-4 space-y-2 overflow-y-auto flex-1 font-mono text-xs text-neutral-500">
              Loading strata cases...
            </div>
          ) : error ? (
            <div className="p-4 text-center text-neutral-600 dark:text-neutral-400 text-xs">{error}</div>
          ) : (
            <div className="divide-y divide-neutral-200 dark:divide-neutral-800/70 overflow-y-auto flex-1">
              {filteredData.length > 0 ? (
                filteredData.map((record, idx) => {
                  const isSelected = selectedIndex === idx;
                  const isMatch = record.human_winner === record.ai_winner;

                  return (
                    <button
                      key={`${record.prompt_id}-${idx}`}
                      onClick={() => setSelectedIndex(idx)}
                      className={`w-full p-3 text-left transition-colors cursor-pointer flex flex-col space-y-1 ${
                        isSelected
                          ? 'bg-neutral-200 dark:bg-neutral-900 border-l-2 border-l-neutral-900 dark:border-l-white'
                          : 'hover:bg-neutral-100 dark:hover:bg-neutral-900/50 text-neutral-600 dark:text-neutral-400'
                      }`}
                    >
                      <div className="flex items-center justify-between font-mono text-xs">
                        <span className="font-semibold text-neutral-900 dark:text-neutral-200">
                          Prompt #{record.prompt_id}
                        </span>
                        <span className={`inline-flex items-center gap-1.5 font-mono text-[10px] font-medium tracking-wide ${
                            isMatch
                              ? 'text-emerald-600 dark:text-emerald-400'
                              : 'text-rose-600 dark:text-rose-400'
                          }`}>
                          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                            isMatch ? 'bg-emerald-500' : 'bg-rose-500'
                          }`} />
                          {isMatch ? 'Match' : 'Mismatch'}
                        </span>
                      </div>

                      <div className="py-0.5">
                        <FormattedMatchup modelNames={record.model_names} className="text-xs font-medium" iconClassName="w-3.5 h-3.5" />
                      </div>

                      <div className="flex items-center justify-between text-[11px] font-mono text-neutral-500">
                        <span>Human: <strong className="text-neutral-800 dark:text-neutral-300">{record.human_winner}</strong></span>
                        <span>AI: <strong className="text-neutral-900 dark:text-white">{record.ai_winner}</strong></span>
                        <span>&Delta;W: <strong className="text-neutral-800 dark:text-neutral-300">{record.word_count_diff > 0 ? `+${record.word_count_diff}` : record.word_count_diff}</strong></span>
                      </div>
                    </button>
                  );
                })
              ) : (
                <div className="p-6 text-center text-neutral-500 text-xs">
                  No cases found matching query.
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Pane (Case Inspector Detail View - 65% / 8 cols) */}
        <div className="lg:col-span-8 space-y-4 flex flex-col h-full overflow-y-auto">
          {activeRecord ? (
            <>
              {/* Detail Header with Visual Bias Badges */}
              <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs transition-colors duration-150">
                <div>
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap font-mono">
                    <span className="px-2 py-0.5 rounded bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-200 border border-neutral-200 dark:border-neutral-800 font-semibold text-[10px]">
                      Prompt #{activeRecord.prompt_id}
                    </span>
                    <span className={`inline-flex items-center gap-1.5 font-mono text-[10px] font-medium tracking-wide ${
                        activeRecord.human_winner === activeRecord.ai_winner
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : 'text-rose-600 dark:text-rose-400'
                      }`}>
                      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                        activeRecord.human_winner === activeRecord.ai_winner ? 'bg-emerald-500' : 'bg-rose-500'
                      }`} />
                      {activeRecord.human_winner === activeRecord.ai_winner ? 'Human Match' : 'Human Mismatch'}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-neutral-200/70 dark:bg-neutral-900 text-neutral-700 dark:text-neutral-300 border border-neutral-300/60 dark:border-neutral-800 font-semibold text-[10px]">
                      {selectedBucket === 'verbosity' && `Verbosity Disparity (${activeRecord.word_count_diff > 0 ? '+' : ''}${activeRecord.word_count_diff}w)`}
                      {selectedBucket === 'forced_choice' && 'Decisiveness Hedging'}
                      {selectedBucket === 'position_bias' && 'Position Order Bias'}
                      {selectedBucket === 'baseline_alignment' && 'Baseline Factual Alignment'}
                    </span>
                  </div>
                  <div className="mt-1">
                    <FormattedMatchup modelNames={activeRecord.model_names} className="text-sm font-semibold" iconClassName="w-4 h-4" />
                  </div>
                </div>

                <button
                  onClick={handleCopyText}
                  className="flex items-center space-x-1 px-3 py-1.5 rounded bg-white dark:bg-neutral-900 hover:bg-neutral-100 dark:hover:bg-neutral-800 border border-neutral-200 dark:border-neutral-800 text-neutral-700 dark:text-neutral-300 text-xs font-mono self-start sm:self-auto cursor-pointer"
                >
                  {copied ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-500" />
                      <span>Transcript Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3 text-neutral-500 dark:text-neutral-400" />
                      <span>Copy Full Trial Transcript</span>
                    </>
                  )}
                </button>
              </div>

              {/* Decision Metrics */}
              <div className="grid grid-cols-3 gap-3 text-center text-xs font-mono">
                <div className="p-2.5 rounded bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800">
                  <span className="text-[10px] text-neutral-500">Human Winner</span>
                  <p className="font-semibold text-neutral-800 dark:text-neutral-200 text-sm mt-0.5">{activeRecord.human_winner}</p>
                </div>
                <div className="p-2.5 rounded bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800">
                  <span className="text-[10px] text-neutral-500">AI Judge Verdict</span>
                  <p className="font-semibold text-neutral-900 dark:text-white text-sm mt-0.5">{activeRecord.ai_winner}</p>
                </div>
                <div className="p-2.5 rounded bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800">
                  <span className="text-[10px] text-neutral-500">Word Disparity</span>
                  <p className="font-semibold text-neutral-800 dark:text-neutral-200 text-sm mt-0.5">
                    {activeRecord.word_count_diff > 0 ? `+${activeRecord.word_count_diff}` : activeRecord.word_count_diff} w
                  </p>
                </div>
              </div>

              {/* Input Prompt Full Text Container */}
              <div className="p-3.5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-1.5">
                <div className="flex items-center gap-1.5 text-xs font-mono font-semibold text-neutral-900 dark:text-neutral-100 border-b border-neutral-200 dark:border-neutral-800 pb-1.5">
                  <MessageSquare className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />
                  <span>Input Prompt Question</span>
                </div>
                <p className="text-xs text-neutral-700 dark:text-neutral-300 font-sans leading-relaxed pt-0.5">
                  {activeRecord.prompt_text || 'Compose an engaging travel blog post or analytical comparison grounded in standard baseline reference data.'}
                </p>
              </div>

              {/* Candidate Answers Full Text Containers (Side-by-Side Grid) */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="p-3.5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-1.5 flex flex-col">
                  <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-1.5 text-xs font-mono">
                    <span className="font-semibold text-neutral-900 dark:text-neutral-100 flex items-center gap-1.5">
                      <SingleModelIcon modelName={activeRecord.model_names.split(/\s+vs\s+/i)[0] || ''} className="w-3.5 h-3.5" />
                      <span>Answer A</span>
                    </span>
                    <span className="text-[10px] text-neutral-500">Candidate A</span>
                  </div>
                  <div className="text-xs text-neutral-700 dark:text-neutral-300 font-sans leading-relaxed max-h-44 overflow-y-auto pt-0.5 pr-1">
                    {activeRecord.answer_a_text || 'Detailed candidate response grounded in factual context and structured reasoning.'}
                  </div>
                </div>

                <div className="p-3.5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-1.5 flex flex-col">
                  <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-1.5 text-xs font-mono">
                    <span className="font-semibold text-neutral-900 dark:text-neutral-100 flex items-center gap-1.5">
                      <SingleModelIcon modelName={activeRecord.model_names.split(/\s+vs\s+/i)[1] || ''} className="w-3.5 h-3.5" />
                      <span>Answer B</span>
                    </span>
                    <span className="text-[10px] text-neutral-500">Candidate B</span>
                  </div>
                  <div className="text-xs text-neutral-700 dark:text-neutral-300 font-sans leading-relaxed max-h-44 overflow-y-auto pt-0.5 pr-1">
                    {activeRecord.answer_b_text || 'Concise candidate response providing relevant summary details and key concepts.'}
                  </div>
                </div>
              </div>

              {/* Reasoning Terminal Box (Expanded G-EVAL Reasoning View) */}
              <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-2 flex-1 flex flex-col transition-colors duration-150">
                <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2 text-xs font-mono">
                  <span className="font-semibold text-neutral-900 dark:text-neutral-200 flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />
                    <span>Verbatim G-EVAL Reasoning Text</span>
                  </span>
                  <div className="flex items-center gap-4 text-[10px] font-sans">
                    <span className="flex items-center gap-1.5 text-neutral-500 dark:text-neutral-500">
                      <span className="w-1.5 h-1.5 rounded-full bg-rose-400/70 dark:bg-rose-500/60 shrink-0"></span>
                      <span className="italic text-neutral-500 dark:text-neutral-400 font-light">Hedging</span>
                    </span>
                    <span className="flex items-center gap-1.5 text-neutral-500 dark:text-neutral-500">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400/70 dark:bg-emerald-500/60 shrink-0"></span>
                      <span className="italic text-neutral-500 dark:text-neutral-400 font-light">Length Bias</span>
                    </span>
                    <span className="flex items-center gap-1.5 text-neutral-500 dark:text-neutral-500">
                      <span className="w-1.5 h-1.5 rounded-full bg-neutral-400/70 dark:bg-neutral-500/60 shrink-0"></span>
                      <span className="italic text-neutral-500 dark:text-neutral-400 font-light">Answer Labels</span>
                    </span>
                  </div>
                </div>

                <div className="bg-neutral-100 dark:bg-neutral-950 p-3.5 rounded border border-neutral-200 dark:border-neutral-800/80 text-xs font-mono text-neutral-800 dark:text-neutral-300 overflow-y-auto flex-1 min-h-[140px] max-h-64 leading-relaxed">
                  <TextHighlighter text={activeRecord.reasoning_text} />
                </div>
              </div>

              {/* Scientific Case Commentary */}
              <CaseCommentaryCard bucket={selectedBucket} record={activeRecord} />
            </>
          ) : (
            <div className="p-12 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 text-center text-neutral-500 text-xs font-mono my-auto">
              Select a case from the master list to inspect qualitative details.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
