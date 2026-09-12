import React from 'react';
import type { FormatBiasData } from '../api/types';
import { useTheme } from '../context/ThemeContext';
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
} from 'recharts';

interface Props {
  data: FormatBiasData | null;
  loading: boolean;
  error: string | null;
}

export const FormatBiasChart: React.FC<Props> = ({ data, loading, error }) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const hasData = [data?.markdown_chosen, data?.plain_text_chosen].every(Number.isFinite);
  const chartData = hasData && data
    ? [
        { name: 'Markdown-Heavy', count: data.markdown_chosen, color: '#0d9488' },
        { name: 'Plain Text', count: data.plain_text_chosen, color: isDark ? '#404040' : '#737373' },
      ]
    : [];

  const total = chartData.reduce((sum, item) => sum + (item.count ?? 0), 0);

  const pValueFormatted = typeof data?.p_value === 'number' && Number.isFinite(data.p_value)
    ? data.p_value < 0.001
      ? 'p < 0.001'
      : `p = ${data.p_value.toFixed(4)}`
    : '';

  const chi2Formatted = typeof data?.chi2_stat === 'number' && Number.isFinite(data.chi2_stat)
    ? data.chi2_stat.toFixed(2)
    : 'Unavailable';

  return (
    <div className="p-5 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 flex flex-col justify-between h-full font-sans transition-colors duration-150">
      <div className="space-y-3 flex-1 flex flex-col justify-between">
        <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2">
          <div>
            <h4 className="font-semibold text-neutral-900 dark:text-neutral-100 text-xs tracking-tight">
              Formatting Association
            </h4>
            <p className="text-xs text-neutral-500">
              Selection frequency when candidates differ in Markdown formatting
            </p>
          </div>
          {hasData && (
            <span className="inline-flex shrink-0 whitespace-nowrap items-center px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-neutral-100 text-teal-600 border border-neutral-200 dark:bg-neutral-800/50 dark:text-teal-400 dark:border-neutral-700 shadow-none ring-0">
              &chi;&sup2; = {chi2Formatted} ({pValueFormatted || 'p-val N/A'})
            </span>
          )}
        </div>


        {loading ? (
          <div className="h-64 flex items-center justify-center font-mono text-xs text-neutral-500 flex-1">
            Loading formatting telemetry...
          </div>
        ) : error ? (
          <div className="h-64 flex items-center justify-center text-neutral-600 dark:text-neutral-400 text-xs flex-1">
            {error}
          </div>
        ) : !hasData ? (
          <div className="h-64 flex items-center justify-center text-neutral-500 text-xs flex-1">No eligible formatting observations.</div>
        ) : (
          <div className="space-y-3 flex-1 flex flex-col justify-between">
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 24, right: 12, left: 0, bottom: 4 }} barCategoryGap="28%">
                  <CartesianGrid vertical={false} strokeDasharray="3 5" stroke={isDark ? '#303030' : '#e5e5e5'} />
                  <XAxis dataKey="name" stroke={isDark ? '#a3a3a3' : '#525252'} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} tickMargin={10} interval={0} />
                  <YAxis stroke={isDark ? '#a3a3a3' : '#737373'} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} tickMargin={8} width={42} allowDecimals={false} />
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
                    formatter={(val: unknown) => [`${val} decisions`, 'Count']}
                  />
                  <Bar dataKey="count" radius={[3, 3, 0, 0]} maxBarSize={64} isAnimationActive={false}>
                    <LabelList dataKey="count" position="top" offset={8} fill={isDark ? '#e5e5e5' : '#404040'} fontSize={12} />
                    {chartData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={entry.color}
                        stroke={isDark ? '#404040' : '#d4d4d4'}
                        strokeWidth={1}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="p-2.5 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-600 dark:text-neutral-400">
              <strong className="text-neutral-900 dark:text-neutral-200">Formatting association:</strong> this aggregate heuristic is not the final controlled RQ5 experiment. See Controlled Experiments for the frozen Controlled Presentation-Format Effect.
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-center text-xs font-mono pt-3">
        {chartData.map((p) => (
          <div key={p.name} className="p-2 rounded bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800">
            <p className="text-neutral-500 text-[11px]">{p.name}</p>
            <p className="font-semibold text-neutral-900 dark:text-neutral-200 text-sm">{p.count}</p>
            <p className="text-[10px] text-neutral-500">
              {total > 0 && p.count !== null ? `${((p.count / total) * 100).toFixed(1)}%` : 'Unavailable'}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};
