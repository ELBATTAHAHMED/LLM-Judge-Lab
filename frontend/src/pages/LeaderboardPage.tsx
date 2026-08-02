import React from 'react';
import { useLeaderboard } from '../api/client';
import { useJudge } from '../context/JudgeContext';
import { CalibratedLeaderboardTable } from '../components/CalibratedLeaderboardTable';
import { MethodologyCards } from '../components/MethodologyCards';

export const LeaderboardPage: React.FC = () => {
  const { judgeModel } = useJudge();
  const { data, loading, error, refetch } = useLeaderboard(judgeModel);

  // Confirmed human preference baseline dataset size
  const pairwiseCount = '2,271 Pairwise Matchups';


  return (
    <div className="max-w-[1400px] mx-auto space-y-8 py-1 font-sans">
      {/* Main Centered Header - High-Craft Vercel/Linear Style */}
      <div className="text-center space-y-3 pt-1">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-neutral-100 dark:bg-zinc-900/90 border border-neutral-200 dark:border-zinc-800/80 text-xs font-mono text-neutral-600 dark:text-zinc-400 shadow-xs">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
          <span className="text-neutral-400 dark:text-zinc-500">Dataset:</span>
          <span className="font-semibold text-neutral-800 dark:text-zinc-200">{pairwiseCount}</span>
        </div>

        <h1 className="text-3xl sm:text-4xl font-serif text-neutral-900 dark:text-white tracking-tight">
          LLM Latent Quality Leaderboard
        </h1>
        <p className="text-xs sm:text-sm text-neutral-600 dark:text-neutral-400 max-w-2xl mx-auto leading-relaxed">
          Measuring true model merit across <span className="font-medium text-neutral-700 dark:text-neutral-300">2,271</span> pairwise comparisons. Comparing raw win rates against Bradley-Terry MLE parameters (&theta;) and Residual Length Neutralization.
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
