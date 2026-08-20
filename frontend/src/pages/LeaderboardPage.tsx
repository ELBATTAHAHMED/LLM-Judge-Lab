import React from 'react';
import { Database } from 'lucide-react';
import { useLeaderboard, useDatasetCount } from '../api/client';
import { useJudge } from '../context/JudgeContext';
import { CalibratedLeaderboardTable } from '../components/CalibratedLeaderboardTable';
import { MethodologyCards } from '../components/MethodologyCards';

export const LeaderboardPage: React.FC = () => {
  const { judgeModel } = useJudge();
  const { data, loading, error, refetch } = useLeaderboard(judgeModel);
  const { count, loading: countLoading, error: countError } = useDatasetCount();

  const formattedCount = count !== null && count !== undefined ? count.toLocaleString() : 'Unavailable';
  const pairwiseCountStr = countLoading
    ? 'Loading dataset count...'
    : countError
    ? 'Dataset count unavailable'
    : `${formattedCount} Pairwise Matchups`;

  return (
    <div className="max-w-[1400px] mx-auto space-y-8 py-1 font-sans">
      {/* Main Centered Header */}
      <div className="text-center space-y-2.5 pt-1">
        <div className="flex items-center justify-center space-x-1.5 text-xs font-mono text-neutral-500 dark:text-zinc-500 select-none">
          <Database className="w-3.5 h-3.5 text-neutral-400 dark:text-zinc-600 shrink-0" />
          <span>Dataset:</span>
          <span className="text-neutral-700 dark:text-zinc-300 font-medium">{pairwiseCountStr}</span>
        </div>

        <h1 className="text-3xl sm:text-4xl font-serif text-neutral-900 dark:text-white tracking-tight">
          Judge-relative Ranking
        </h1>
        <p className="text-xs sm:text-sm text-neutral-600 dark:text-neutral-400 max-w-2xl mx-auto leading-relaxed">
          Judge-relative pairwise ranking across <span className="font-medium text-neutral-700 dark:text-neutral-300">{formattedCount}</span> comparisons. Rankings depend on the evaluation sample, judge, and available comparisons.
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

