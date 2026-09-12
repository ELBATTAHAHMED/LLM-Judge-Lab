import React, { useMemo } from 'react';
import { useTheme } from '../context/ThemeContext';
import type { DomainKappaPoint } from '../api/types';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LabelList,
  ReferenceLine,
} from 'recharts';

interface Props {
  data?: DomainKappaPoint[] | null;
  loading?: boolean;
  error?: string | null;
}

function getKappaColor(kappa: number): string {
  if (kappa >= 0.5) return '#0d9488'; // teal-600
  if (kappa >= 0.4) return '#0f766e'; // teal-700
  if (kappa >= 0.3) return '#115e59'; // teal-800
  return '#134e4a';                   // teal-900
}

function formatDomainName(domain: string): string {
  if (!domain) return '';
  const lower = domain.toLowerCase();
  if (lower === 'stem') return 'STEM';
  return domain.charAt(0).toUpperCase() + domain.slice(1).toLowerCase();
}

export const DomainReliabilityChart: React.FC<Props> = ({ data, loading, error }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];
    return data.filter((item): item is DomainKappaPoint & { kappa: number } => item.kappa !== null).map((item) => ({
      domain: formatDomainName(item.domain),
      kappa: item.kappa,
      color: getKappaColor(item.kappa),
    }));
  }, [data]);

  const highest = useMemo(() => {
    if (!chartData || chartData.length === 0) return null;
    return chartData.reduce((prev, curr) => (prev.kappa > curr.kappa ? prev : curr));
  }, [chartData]);

  const lowest = useMemo(() => {
    if (!chartData || chartData.length === 0) return null;
    return chartData.reduce((prev, curr) => (prev.kappa < curr.kappa ? prev : curr));
  }, [chartData]);

  return (
    <div className="p-5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-3 font-sans transition-colors duration-150">
      <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2">
        <div>
          <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 text-xs tracking-tight">
            Domain-Stratified Inter-Rater Agreement (Cohen's &kappa;)
          </h4>
          <p className="text-xs text-neutral-500">
            Human vs AI judge agreement across the 8 MT-Bench topic categories
          </p>
        </div>
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-neutral-100 text-teal-600 border border-neutral-200 dark:bg-neutral-800/50 dark:text-teal-400 dark:border-neutral-700 shadow-none ring-0">
          Landis-Koch Benchmark
        </span>
      </div>

      <div className="space-y-3">
        {loading ? (
          <div className="h-64 w-full flex items-center justify-center font-mono text-xs text-neutral-500">
            Computing dynamic domain Cohen's Kappa...
          </div>
        ) : error ? (
          <div className="h-64 w-full flex items-center justify-center font-mono text-xs text-rose-500">
            Failed to load domain reliability telemetry: {error}
          </div>
        ) : chartData.length === 0 ? (
          <div className="h-64 w-full flex items-center justify-center font-mono text-xs text-neutral-500">
            No domain reliability data available.
          </div>
        ) : (
          <div className="w-full" style={{ height: Math.max(256, chartData.length * 34 + 48) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                layout="vertical"
                data={chartData}
                margin={{ top: 8, right: 48, left: 0, bottom: 20 }}
              >
                <CartesianGrid horizontal={false} strokeDasharray="3 5" stroke={isDark ? '#303030' : '#e5e5e5'} />
                <XAxis type="number" stroke={isDark ? '#a3a3a3' : '#737373'} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} tickMargin={8} domain={[0, 0.6]} tickCount={7} tickFormatter={(value) => Number(value).toFixed(2)} minTickGap={24} label={{ value: 'Cohen’s κ', position: 'bottom', offset: 6, fill: isDark ? '#a3a3a3' : '#525252', fontSize: 11 }} />
                <ReferenceLine x={0} stroke={isDark ? '#737373' : '#a3a3a3'} />
                <YAxis
                  type="category"
                  dataKey="domain"
                  stroke={isDark ? '#a3a3a3' : '#737373'}
                  tick={{ fontSize: 12, fill: isDark ? '#d4d4d4' : '#404040' }}
                  width={94}
                  axisLine={false}
                  tickLine={false}
                  tickMargin={10}
                  interval={0}
                />
                <Tooltip
                  cursor={{ fill: isDark ? '#ffffff08' : '#00000004' }}
                  contentStyle={{
                    background: isDark ? '#0a0a0a' : '#ffffff',
                    borderColor: isDark ? '#404040' : '#e5e5e5',
                    borderRadius: '4px',
                    fontSize: '12px',
                    fontFamily: 'inherit',
                    boxShadow: isDark ? 'none' : '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                  }}
                  itemStyle={{ color: isDark ? '#e5e5e5' : '#171717' }}
                  labelStyle={{ color: isDark ? '#ffffff' : '#171717', fontWeight: 600 }}
                  formatter={(val: unknown) => [`κ = ${(Number.isFinite(Number(val)) ? Number(val).toFixed(3) : 'Unavailable')}`, 'Cohen’s Kappa']}
                />
                <Bar dataKey="kappa" radius={[0, 3, 3, 0]} maxBarSize={16} isAnimationActive={false}>
                  <LabelList dataKey="kappa" position="right" offset={8} formatter={(value) => Number.isFinite(Number(value)) ? Number(value).toFixed(3) : 'Unavailable'} fill={isDark ? '#d4d4d4' : '#404040'} fontSize={11} />
                  {chartData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={isDark ? '#568d85' : '#527f77'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {highest && lowest && (
          <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-600 dark:text-neutral-400 font-mono flex justify-between">
            <span>
              Highest Agreement: <strong className="text-teal-600 dark:text-teal-400 font-semibold">{highest.domain} (&kappa; = {typeof highest.kappa === 'number' && Number.isFinite(highest.kappa) ? highest.kappa.toFixed(3) : 'Unavailable'})</strong>
            </span>
            <span>
              Lowest Agreement: <strong className="text-neutral-500 font-semibold">{lowest.domain} (&kappa; = {typeof lowest.kappa === 'number' && Number.isFinite(lowest.kappa) ? lowest.kappa.toFixed(3) : 'Unavailable'})</strong>
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
