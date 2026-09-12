import { fireEvent, render, screen, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { JudgeProvider } from '../context/JudgeContext';
import { ThemeProvider } from '../context/ThemeContext';
import { DashboardLayout } from './DashboardLayout';

const renderRoute = (path: string) => render(
  <ThemeProvider><JudgeProvider><MemoryRouter initialEntries={[path]}><Routes><Route path="/" element={<DashboardLayout />}><Route path="leaderboard" element={<div>Leaderboard content</div>} /><Route path="synthesis" element={<div>Synthesis content</div>} /><Route path="controlled-results" element={<div>Controlled content</div>} /></Route></Routes></MemoryRouter></JudgeProvider></ThemeProvider>,
);

describe('aggregate controlled-page selector scope', () => {
  it('opens mobile navigation and closes it after choosing a page', () => {
    renderRoute('/leaderboard');
    fireEvent.click(screen.getByRole('button', { name: 'Menu' }));
    const navigation = screen.getByRole('navigation', { name: 'Mobile navigation' });
    expect(within(navigation).getAllByRole('link')).toHaveLength(6);
    fireEvent.click(within(navigation).getByRole('link', { name: 'Synthesis' }));
    expect(screen.queryByRole('navigation', { name: 'Mobile navigation' })).not.toBeInTheDocument();
    expect(screen.getByText('Synthesis content')).toBeInTheDocument();
  });
  it.each(['/synthesis', '/controlled-results'])('hides the global judge selector on %s', (path) => {
    renderRoute(path);
    expect(screen.queryByText('GPT-4o-mini')).not.toBeInTheDocument();
  });

  it('preserves the selector on judge-filtered pages', () => {
    renderRoute('/leaderboard');
    expect(screen.getByText('GPT-4o-mini')).toBeInTheDocument();
  });
});
