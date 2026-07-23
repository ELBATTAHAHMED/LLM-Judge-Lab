import React from 'react';
import { useLeaderboard } from '../api/client';
import { CalibratedLeaderboardTable } from '../components/CalibratedLeaderboardTable';
import { MethodologyCards } from '../components/MethodologyCards';

export const LeaderboardPage: React.FC = () => {
  const { data, loading, error, refetch } = useLeaderboard();

  return (
    <div className="max-w-[1400px] mx-auto space-y-8 py-2 font-sans">
      {/* Target Model Meta Header (No Battle Mode) */}
      <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3">
        <div className="text-xs font-mono text-neutral-500">
          Target Judge: <span className="text-neutral-800 dark:text-neutral-200 font-medium">gpt-4o-mini (Temp=0.0)</span>
        </div>
        <div className="text-xs font-mono text-neutral-500">
          Dataset: <span className="text-neutral-800 dark:text-neutral-200 font-medium">1,530 Pairwise Matchups</span>
        </div>
      </div>

      {/* Main Centered Header - Vercel v0 Serif Headline Style */}
      <div className="text-center space-y-3 pt-2">
        <h1 className="text-3xl sm:text-4xl font-serif text-neutral-900 dark:text-white tracking-tight">
          LLM Latent Quality Leaderboard
        </h1>
        <p className="text-xs sm:text-sm text-neutral-600 dark:text-neutral-400 max-w-2xl mx-auto leading-relaxed">
          Measuring true model merit across 1,530 pairwise comparisons. Comparing raw win rates against Bradley-Terry MLE parameters (&theta;) and Residual Length Neutralization (&beta; = +0.000832).
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
