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

/**
 * Dynamically computes OLS linear regression parameters (alpha, beta, R^2)
 * and Spearman rank correlation coefficient (rho) from empirical verbosity data points.
 */
function computeRegressionStats(points: VerbosityDataPoint[]) {
  if (!points || points.length === 0) {
    return null;
  }

  const n = points.length;
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;

  for (let i = 0; i < n; i++) {
    const x = points[i].word_count_diff;
    const y = points[i].llm_verdict;
    sumX += x;
    sumY += y;
    sumXY += x * y;
    sumX2 += x * x;
    sumY2 += y * y;
  }

  const meanX = sumX / n;
  const meanY = sumY / n;

  const denom = sumX2 - n * meanX * meanX;
  const beta = denom !== 0 ? (sumXY - n * meanX * meanY) / denom : 0;
  const alpha = meanY - beta * meanX;

  // Pearson r & R^2 calculation
  const numR = sumXY - n * meanX * meanY;
  const denomR = Math.sqrt(Math.max(0, (sumX2 - n * meanX * meanX) * (sumY2 - n * meanY * meanY)));
  const pearsonR = denomR !== 0 ? numR / denomR : 0;
  const r2 = pearsonR * pearsonR;

  // Spearman rank correlation (rho) calculation
  const getRanks = (arr: number[]) => {
    const sorted = arr.map((v, i) => ({ v, i })).sort((a, b) => a.v - b.v);
    const ranks = new Array(n);
    let i = 0;
    while (i < n) {
      let j = i;
      while (j < n - 1 && sorted[j + 1].v === sorted[i].v) {
        j++;
      }
      const rankVal = (i + j + 2) / 2;
      for (let k = i; k <= j; k++) {
        ranks[sorted[k].i] = rankVal;
      }
      i = j + 1;
    }
    return ranks;
  };

  const rx = getRanks(points.map((p) => p.word_count_diff));
  const ry = getRanks(points.map((p) => p.llm_verdict));

  let meanRx = 0, meanRy = 0;
  for (let i = 0; i < n; i++) {
    meanRx += rx[i];
    meanRy += ry[i];
  }
  meanRx /= n;
  meanRy /= n;

  let numRho = 0, denRx = 0, denRy = 0;
  for (let i = 0; i < n; i++) {
    const dx = rx[i] - meanRx;
    const dy = ry[i] - meanRy;
    numRho += dx * dy;
    denRx += dx * dx;
    denRy += dy * dy;
  }

  const denomRho = Math.sqrt(denRx * denRy);
  const rho = denomRho !== 0 ? numRho / denomRho : 0;

  return { beta, alpha, r2, rho };
}

export const VerbosityBiasChart: React.FC<Props> = ({ data, loading, error }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [sampleSize, setSampleSize] = useState<'100' | '250' | 'All'>('250');

  const regStats = useMemo(() => computeRegressionStats(data || []), [data]);

  const chartData = useMemo(() => {
    if (!data || !Array.isArray(data) || !regStats) return { scatter: [], trend: [] };

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

    const { alpha, beta } = regStats;
    const trend = [
      { x: -300, trendY: Math.max(0, Math.min(1, alpha + beta * -300)) },
      { x: 0, trendY: Math.max(0, Math.min(1, alpha)) },
      { x: 300, trendY: Math.max(0, Math.min(1, alpha + beta * 300)) },
    ];

    return { scatter, trend };
  }, [data, sampleSize, regStats]);

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

  const inflationPct = regStats ? (regStats.beta * 100 * 100).toFixed(1) : '0.0';

  return (
    <div className="p-5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-3 font-sans transition-colors duration-150">
      <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2">
        <div>
          <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 text-xs tracking-tight">
            Verbosity Disparity vs Win Probability
          </h4>
          <p className="text-xs text-neutral-500">
            {regStats
              ? `OLS Fit: Win Probability ~ α (${regStats.alpha.toFixed(3)}) + β·ΔWC`
              : 'OLS Fit: No telemetry data'}
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
          {regStats && (
            <span className="text-[11px] font-mono text-neutral-600 dark:text-neutral-400 border border-neutral-200 dark:border-neutral-800 px-2 py-0.5 rounded bg-white dark:bg-neutral-900">
              &beta; = {regStats.beta >= 0 ? '+' : ''}{regStats.beta.toFixed(6)}
            </span>
          )}
        </div>
      </div>

      {loading ? (
        <div className="h-64 flex items-center justify-center font-mono text-xs text-neutral-500">
          Loading verbosity telemetry...
        </div>
      ) : error ? (
        <div className="h-64 flex items-center justify-center text-neutral-600 dark:text-neutral-400 text-xs">{error}</div>
      ) : !data || data.length === 0 || !regStats ? (
        <div className="h-64 flex flex-col items-center justify-center font-mono text-xs text-neutral-500 space-y-1.5">
          <p className="font-semibold text-neutral-700 dark:text-neutral-300">No telemetry data available</p>
          <p className="text-neutral-500 text-[11px]">No verbosity comparison samples found for this judge model.</p>
        </div>
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
            <span>Spearman Rank Correlation: <strong className="text-neutral-900 dark:text-neutral-200">&rho; = {regStats.rho >= 0 ? '+' : ''}{regStats.rho.toFixed(4)}</strong></span>
            <span>Inflation: <strong className="text-[#38bdf8] font-semibold">{parseFloat(inflationPct) >= 0 ? '+' : ''}{inflationPct}% per 100 words</strong></span>
          </div>
        </div>
      )}
    </div>
  );
};

