import React from 'react';
import type { QualitativeBucket, QualitativeRecord } from '../api/types';
import { FormattedMatchup } from './ModelIcons';

interface Props {
  bucket: QualitativeBucket;
  record: QualitativeRecord;
}

export const CaseCommentaryCard: React.FC<Props> = ({ bucket, record }) => {
  if (!record) return null;

  const isMatch = record.human_winner === record.ai_winner;


  const getCommentaryContent = () => {
    switch (bucket) {
      case 'verbosity':
        return {
          title: 'Verbosity Inflation Commentary',
          summary: `The AI judge selected the longer response (disparity: ${record.word_count_diff > 0 ? '+' : ''}${record.word_count_diff} words), while the human evaluator preferred the concise answer. This selected historical case is consistent with a length-associated preference; it is not controlled evidence of a systematic length effect.`,
        };

      case 'forced_choice':
        return {
          title: 'Decisiveness Hallucination & Hedging Commentary',
          summary: `Human raters declared a TIE on this pair, but the AI judge forced a decisive winner (${record.ai_winner}). Notice how the reasoning text uses hedging vocabulary ("slightly", "marginal", "subtle") — demonstrating that the judge perceived equivalence yet hallucinated a winner decision.`,
        };

      case 'position_bias':
        return {
          title: 'Position-Order Preference Commentary',
          summary: `This selected historical case favored the answer shown in Position B. Controlled RQ3 is required for presentation-order sensitivity inference.`,
        };


      case 'baseline_alignment':
      default:
        return {
          title: 'Baseline Alignment Commentary',
          summary: `The AI-judge verdict matches the human preference reference (${record.human_winner}). This qualitative example is not final controlled evidence.`,
        };
    }
  };

  const commentary = getCommentaryContent();

  return (
    <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-2 font-sans transition-colors duration-150">
      <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2">
        <h5 className="font-semibold text-neutral-900 dark:text-neutral-200 text-xs tracking-tight">
          {commentary.title}
        </h5>
        <span className={`inline-flex items-center gap-1.5 font-mono text-[10px] font-medium tracking-wide ${
            isMatch
              ? 'text-emerald-600 dark:text-emerald-400'
              : 'text-rose-600 dark:text-rose-400'
          }`}>
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
            isMatch ? 'bg-emerald-500' : 'bg-rose-500'
          }`} />
          {isMatch ? 'Human Match' : 'Human Mismatch'}
        </span>
      </div>

      <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
        {commentary.summary}
      </p>

      <div className="pt-1.5 border-t border-neutral-200 dark:border-neutral-800 flex items-center justify-between text-[11px] font-mono text-neutral-500">
        <span>Prompt #{record.prompt_id}</span>
        <span className="flex items-center gap-1 font-sans">
          <span className="font-mono text-[11px]">Models:</span>
          <FormattedMatchup modelNames={record.model_names} className="text-[11px] font-mono text-neutral-500" iconClassName="w-3 h-3" />
        </span>
      </div>
    </div>
  );
};
