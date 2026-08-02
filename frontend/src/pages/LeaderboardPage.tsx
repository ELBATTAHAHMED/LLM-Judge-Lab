import React from 'react';
import { useLeaderboard } from '../api/client';
import { useJudge } from '../context/JudgeContext';
import { CalibratedLeaderboardTable } from '../components/CalibratedLeaderboardTable';
import { MethodologyCards } from '../components/MethodologyCards';
import { SingleModelIcon, formatModelName } from '../components/ModelIcons';

export const LeaderboardPage: React.FC = () => {
  const { judgeModel } = useJudge();
  const { data, loading, error, refetch } = useLeaderboard(judgeModel);

  // Confirmed human preference baseline dataset size
  const pairwiseCount = '2,271 Pairwise Matchups';


  return (
    <div className="max-w-[1400px] mx-auto space-y-8 py-2 font-sans">
      {/* Target Model Meta Header (No Battle Mode) */}
      <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3">
        <div className="flex items-center gap-2 text-xs font-mono text-neutral-500">
          <span>Target Judge:</span>
          <span className="flex items-center gap-1.5 text-neutral-800 dark:text-neutral-200 font-medium">
            <SingleModelIcon modelName={judgeModel} className="w-3.5 h-3.5" />
            <span>{formatModelName(judgeModel)}</span>
            <span className="text-neutral-400">(Temp=0.0)</span>
          </span>
        </div>
        <div className="text-xs font-mono text-neutral-500">
          Dataset: <span className="text-neutral-800 dark:text-neutral-200 font-medium">{pairwiseCount}</span>
        </div>
      </div>

      {/* Main Centered Header - Vercel v0 Serif Headline Style */}
      <div className="text-center space-y-3 pt-2">
        <h1 className="text-3xl sm:text-4xl font-serif text-neutral-900 dark:text-white tracking-tight">
          LLM Latent Quality Leaderboard
        </h1>
        <p className="text-xs sm:text-sm text-neutral-600 dark:text-neutral-400 max-w-2xl mx-auto leading-relaxed">
          Measuring true model merit across <span className="font-medium text-neutral-700 dark:text-neutral-300">2,271</span> pairwise comparisons using{' '}
          <span className="font-medium text-neutral-700 dark:text-neutral-300">{formatModelName(judgeModel)}</span>{' '}
          as judge. Comparing raw win rates against Bradley-Terry MLE parameters (&theta;) and Residual Length Neutralization.
        </p>
      </div>

      {/* Core Leaderboard Table */}
      <CalibratedLeaderboardTable
        data={data}
        loading={loading}
        error={error}
        onRefresh={refetch}
      />

      {/* Methodology Section */}
      <MethodologyCards />
    </div>
  );
};
