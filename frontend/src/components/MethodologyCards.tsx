import React from 'react';

export const MethodologyCards: React.FC = () => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 font-sans">
      {/* Card 1: Bradley-Terry MLE Model */}
      <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-2.5 transition-colors duration-150">
        <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2">
          <h4 className="font-semibold text-neutral-800 dark:text-neutral-200 text-xs tracking-tight">
            1. Bradley-Terry Latent Quality Model (MLE)
          </h4>
          <span className="text-[10px] font-mono text-neutral-500 border border-neutral-200 dark:border-neutral-800 px-1.5 py-0.5 rounded bg-white dark:bg-neutral-900">
            Schedule Control
          </span>
        </div>

        {/* Math Formula Block */}
        <div className="p-3 rounded-md bg-neutral-100/60 dark:bg-neutral-900/50 border border-neutral-200 dark:border-neutral-800/50 font-mono text-sm text-neutral-800 dark:text-neutral-300 tracking-wide text-center">
          P(i &gt; j) = exp(&theta;<sub>i</sub>) / [exp(&theta;<sub>i</sub>) + exp(&theta;<sub>j</sub>)] = &sigma;(&theta;<sub>i</sub> - &theta;<sub>j</sub>)
        </div>

        <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
          Raw win rates suffer from schedule-dependency bias (a model matched against stronger opponents is penalized). The Bradley-Terry model estimates intrinsic quality parameters (&theta;) simultaneously across all 1,530 pairwise decisions via Maximum Likelihood Estimation (log-likelihood: -751.59).
        </p>
      </div>

      {/* Card 2: Residual Length Neutralization */}
      <div className="p-4 rounded-lg bg-neutral-50 dark:bg-[#0a0a0a] border border-neutral-200 dark:border-neutral-800 space-y-2.5 transition-colors duration-150">
        <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-2">
          <h4 className="font-semibold text-neutral-800 dark:text-neutral-200 text-xs tracking-tight">
            2. Residual-Based Length Neutralization (OLS)
          </h4>
          <span className="text-[10px] font-mono text-neutral-500 border border-neutral-200 dark:border-neutral-800 px-1.5 py-0.5 rounded bg-white dark:bg-neutral-900">
            Verbosity Control
          </span>
        </div>

        {/* Math Formula Block */}
        <div className="p-3 rounded-md bg-neutral-100/60 dark:bg-neutral-900/50 border border-neutral-200 dark:border-neutral-800/50 font-mono text-sm text-neutral-800 dark:text-neutral-300 tracking-wide text-center">
          Win<sub>A</sub> = &alpha; + &beta;&middot;(WC<sub>A</sub> - WC<sub>B</sub>) + &epsilon;
        </div>

        <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
          Historical regression describes an exploratory length association. It does not establish a controlled redundant-length effect or a verbosity-independent quality score.
        </p>
      </div>
    </div>
  );
};
