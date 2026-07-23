import React from 'react';
import { useBiasStats } from '../api/client';
import { VerbosityBiasChart } from '../components/VerbosityBiasChart';
import { PositionBiasChart } from '../components/PositionBiasChart';
import { FormatBiasChart } from '../components/FormatBiasChart';
import { DomainReliabilityChart } from '../components/DomainReliabilityChart';
import { DiagnosticScientificCallouts } from '../components/DiagnosticScientificCallouts';
import { RefreshCw } from 'lucide-react';

export const DiagnosticsPage: React.FC = () => {
  const { data, loading, error, refetch } = useBiasStats();

  return (
    <div className="max-w-[1400px] mx-auto space-y-8 py-2 font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-200 dark:border-neutral-800 pb-4">
        <div>
          <h1 className="text-2xl font-serif text-neutral-900 dark:text-white tracking-tight">
            Systematic Bias Diagnostics
          </h1>
          <p className="text-xs text-neutral-600 dark:text-neutral-400 mt-1">
            Real-time diagnostic telemetry evaluating Position-Order Bias (&chi;&sup2;), Verbosity Bias (&rho;), Format Bias (&chi;&sup2;), Inter-Rater Reliability (&kappa;), and Decisiveness Hallucinations
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

      {/* Primary Bias Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-stretch">
        <PositionBiasChart
          data={data ? data.position_data : null}
          loading={loading}
          error={error}
        />

        <FormatBiasChart
          data={data ? data.format_bias : null}
          loading={loading}
          error={error}
        />
      </div>

      {/* Full-Width Verbosity Bias Scatter Chart */}
      <VerbosityBiasChart
        data={data ? data.verbosity_data : []}
        loading={loading}
        error={error}
      />

      {/* Domain-Stratified Reliability Bar Chart */}
      <DomainReliabilityChart
        data={data ? data.domain_kappa : []}
        loading={loading}
        error={error}
      />

      {/* Academic Synthesis Callouts */}
      <DiagnosticScientificCallouts />
    </div>
  );
};
