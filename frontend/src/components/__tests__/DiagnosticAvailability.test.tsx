import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, expect, it } from 'vitest';
import { ThemeProvider } from '../../context/ThemeContext';
import { VerbosityBiasChart } from '../VerbosityBiasChart';
import { FormatBiasChart } from '../FormatBiasChart';

describe('diagnostic display availability', () => {
  it('does not display a non-finite OLS estimate as a number', () => {
    const data = [{ word_count_diff: Number.NaN, llm_verdict: 1 }];
    const { container } = render(<ThemeProvider><VerbosityBiasChart data={data} loading={false} error={null} /></ThemeProvider>);
    expect(screen.getAllByText(/Unavailable/).length).toBeGreaterThan(0);
    expect(container.textContent).not.toMatch(/NaN|Infinity/);
    expect(data[0].word_count_diff).toBeNaN();
  });

  it('normalizes numeric-string verdicts returned by the telemetry API', () => {
    const apiLikeData = [
      { word_count_diff: -100, llm_verdict: '0.0' },
      { word_count_diff: 100, llm_verdict: '1.0' },
      { word_count_diff: 0, llm_verdict: '0.5' },
    ] as unknown as Array<{ word_count_diff: number; llm_verdict: number }>;
    const { container } = render(<ThemeProvider><VerbosityBiasChart data={apiLikeData} loading={false} error={null} /></ThemeProvider>);
    expect(container.textContent).not.toMatch(/β = Unavailable|Inflation: Unavailable/);
    expect(container.textContent).toContain('Inflation:');
  });

  it('keeps counts while showing unavailable non-finite format statistics', () => {
    const { container } = render(<ThemeProvider><FormatBiasChart data={{ markdown_chosen: 4, plain_text_chosen: 6, chi2_stat: Infinity, p_value: NaN }} loading={false} error={null} /></ThemeProvider>);
    expect(screen.getByText(/Unavailable/)).toBeInTheDocument();
    expect(screen.getByText('40.0%')).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/NaN|Infinity/);
  });
});
