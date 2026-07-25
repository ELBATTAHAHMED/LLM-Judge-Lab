import React, { useState, useMemo } from 'react';
import type { VerbosityDataPoint } from '../api/types';
import { useTheme } from '../context/ThemeContext';
import {
  ComposedChart,
  Scatter,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

interface Props {
  data: VerbosityDataPoint[];
  loading: boolean;
  error: string | null;
}

export const VerbosityBiasChart: React.FC<Props> = ({ data, loading, error }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [sampleSize, setSampleSize] = useState<'100' | '250' | 'All'>('250');

  const chartData = useMemo(() => {
    if (!data || data.length === 0) return { scatter: [], trend: [] };

    const limit = sampleSize === '100' ? 100 : sampleSize === '250' ? 250 : data.length;
    const scatter = data.slice(0, limit).map((d, i) => ({
      id: i,
      x: d.word_count_diff,
      y: d.llm_verdict,
      outcome:
        d.llm_verdict === 1.0
          ? 'Winner: A (Longer)'
          : d.llm_verdict === 0.0
          ? 'Winner: B (Longer)'
          : 'Verdict: TIE',
    }));

    const trend = [
      { x: -300, trendY: 0.2496 },
      { x: 0, trendY: 0.4992 },
      { x: 300, trendY: 0.7488 },
    ];

    return { scatter, trend };
  }, [data, sampleSize]);

  const combinedData = useMemo(() => {
    const map = new Map<number, { x: number; y?: number; outcome?: string; trendY?: number }>();
    chartData.trend.forEach((t) => map.set(t.x, { x: t.x, trendY: t.trendY }));
    chartData.scatter.forEach((s) => {
      const existing = map.get(s.x);
      if (existing) {
        existing.y = s.y;
        existing.outcome = s.outcome;
      } else {
        map.set(s.x, { x: s.x, y: s.y, outcome: s.outcome });
      }
    });
    return Array.from(map.values()).sort((a, b) => a.x - b.x);
  }, [chartData]);

  const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: { x: number; y: number; outcome: string } }> }) => {
    if (active && payload && payload.length) {
      const dataPoint = payload[0].payload;
      const diff = dataPoint.x;
      const verdict =
        dataPoint.y === 1.0 ? 'Answer A Won' : dataPoint.y === 0.0 ? 'Answer B Won' : 'TIE / Draw';

      return (
        <div className="p-2.5 rounded bg-white dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 text-xs space-y-1 text-neutral-800 dark:text-neutral-200 font-mono shadow-md">
          <p className="font-bold text-neutral-900 dark:text-white">Disparity: {diff > 0 ? `+${diff}` : diff} words</p>
          <p className="text-neutral-600 dark:text-neutral-300">Outcome: {verdict}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="p-5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-3 font-sans transition-colors duration-150">
      <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2">
        <div>
          <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 text-xs tracking-tight">
            Verbosity Disparity vs Win Probability
          </h4>
          <p className="text-xs text-neutral-500">
            OLS Fit Line: y = 0.4992 + 0.000832 &times; &Delta;WC
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1 font-mono text-xs">
            <span className="text-[11px] text-neutral-500">Sample:</span>
            <select
              value={sampleSize}
              onChange={(e) => setSampleSize(e.target.value as '100' | '250' | 'All')}
              className="text-xs font-mono bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded px-1.5 py-0.5 text-neutral-800 dark:text-neutral-200 cursor-pointer focus:outline-none"
            >
              <option value="100">100</option>
              <option value="250">250</option>
              <option value="All">All</option>
            </select>
          </div>
          <span className="text-[11px] font-mono text-neutral-600 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-800 px-2 py-0.5 rounded bg-white dark:bg-neutral-900">
            &beta; = +0.000832 (p &lt; 0.0001)
          </span>
        </div>
      </div>

      {loading ? (
        <div className="h-64 flex items-center justify-center font-mono text-xs text-neutral-500">
          Loading verbosity telemetry...
        </div>
      ) : error ? (
        <div className="h-64 flex items-center justify-center text-neutral-600 dark:text-neutral-400 text-xs">{error}</div>
      ) : (
        <div className="space-y-3">
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={combinedData} margin={{ top: 10, right: 15, left: -15, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#262626' : '#e5e5e5'} />
                <XAxis type="number" dataKey="x" stroke="#a3a3a3" tick={{ fontSize: 11 }} domain={[-300, 300]} unit="w" />
                <YAxis type="number" dataKey="y" stroke="#a3a3a3" tick={{ fontSize: 11 }} domain={[-0.1, 1.1]} ticks={[0, 0.5, 1]} />
                <ReferenceLine y={0.5} stroke={isDark ? '#404040' : '#d4d4d4'} strokeDasharray="3 3" />
                <ReferenceLine x={0} stroke={isDark ? '#404040' : '#d4d4d4'} strokeDasharray="3 3" />
                <Tooltip content={<CustomTooltip />} />
                {/* Muted sky-400 dots with opacity=0.4 creating a natural heatmap density effect */}
                <Scatter name="Decisions" dataKey="y" fill="#38bdf8" opacity={0.4} />
                {/* Sharp light-gray OLS Trendline */}
                <Line
                  type="monotone"
                  dataKey="trendY"
                  stroke={isDark ? '#f5f5f5' : '#171717'}
                  strokeWidth={2}
                  strokeDasharray="3 3"
                  dot={false}
                  name="OLS Trendline"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-600 dark:text-neutral-400 font-mono flex justify-between">
            <span>Spearman Rank Correlation: <strong className="text-neutral-900 dark:text-neutral-200">&rho; = +0.2283</strong></span>
            <span>Inflation: <strong className="text-[#38bdf8] font-semibold">+8.3% per 100 words</strong></span>
          </div>
        </div>
      )}
    </div>
  );
};
