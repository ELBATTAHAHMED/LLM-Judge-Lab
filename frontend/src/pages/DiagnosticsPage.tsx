import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useBiasStats, fetchReportSummary } from '../api/client';
import { generateThesisReport } from '../utils/pdfExport';
import { VerbosityBiasChart } from '../components/VerbosityBiasChart';
import { PositionBiasChart } from '../components/PositionBiasChart';
import { FormatBiasChart } from '../components/FormatBiasChart';
import { DomainReliabilityChart } from '../components/DomainReliabilityChart';
import { DiagnosticScientificCallouts } from '../components/DiagnosticScientificCallouts';
import { RefreshCw, Download } from 'lucide-react';

export const DiagnosticsPage: React.FC = () => {
  const { data, loading, error, refetch } = useBiasStats();
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const location = useLocation();

  useEffect(() => {
    if (location.hash) {
      const elementId = location.hash.replace('#', '');
      const timer = setTimeout(() => {
        const elem = document.getElementById(elementId);
        if (elem) {
          elem.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [location.hash]);

  const handleExportPDF = async () => {
    setIsExporting(true);
    try {
      await fetchReportSummary();
      await generateThesisReport('diagnostics-report-container', 'JudgeLab_Thesis_Appendix');
    } catch (err: any) {
      console.error('PDF Generation Error:', err);
      const msg = err instanceof Error ? err.message : String(err);
      alert('PDF Generation Failed: ' + msg);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div id="diagnostics-report-container" className="max-w-[1400px] mx-auto space-y-8 py-2 font-sans">
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

        <div className="flex items-center space-x-2 self-start sm:self-auto shrink-0">
          <button
            onClick={handleExportPDF}
            disabled={isExporting}
            className="inline-flex items-center justify-center gap-2 px-3 py-1.5 h-9 rounded text-xs font-mono font-medium bg-neutral-900 hover:bg-neutral-800 text-neutral-200 border border-neutral-800 transition-colors whitespace-nowrap cursor-pointer shadow-xs disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Download className={`w-3.5 h-3.5 ${isExporting ? 'animate-pulse' : ''}`} />
            <span>{isExporting ? 'Generating Report...' : 'Export Thesis Appendix (PDF)'}</span>
          </button>

          <button
            onClick={refetch}
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 px-3 py-1.5 h-9 rounded text-xs font-mono font-medium bg-neutral-900 hover:bg-neutral-800 text-neutral-200 border border-neutral-800 transition-colors whitespace-nowrap cursor-pointer shadow-xs disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Primary Bias Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-stretch">
        <div id="position-bias" className="scroll-mt-6">
          <PositionBiasChart
            data={data ? data.position_data : null}
            loading={loading}
            error={error}
          />
        </div>

        <FormatBiasChart
          data={data ? data.format_bias : null}
          loading={loading}
          error={error}
        />
      </div>

      {/* Full-Width Verbosity Bias Scatter Chart */}
      <div id="verbosity-bias" className="scroll-mt-6">
        <VerbosityBiasChart
          data={data ? data.verbosity_data : []}
          loading={loading}
          error={error}
        />
      </div>

      {/* Domain-Stratified Reliability Bar Chart */}
      <div id="reliability-metrics" className="scroll-mt-6 space-y-8">
        <DomainReliabilityChart
          data={data ? data.domain_kappa : []}
          loading={loading}
          error={error}
        />

        {/* Academic Synthesis Callouts */}
        <DiagnosticScientificCallouts />
      </div>
    </div>
  );
};
