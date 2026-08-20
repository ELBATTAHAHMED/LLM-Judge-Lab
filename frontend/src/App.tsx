import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { JudgeProvider } from './context/JudgeContext';
import { DashboardLayout } from './layouts/DashboardLayout';

const LeaderboardPage = lazy(() => import('./pages/LeaderboardPage').then(m => ({ default: m.LeaderboardPage })));
const SynthesisPage = lazy(() => import('./pages/SynthesisPage').then(m => ({ default: m.SynthesisPage })));
const DiagnosticsPage = lazy(() => import('./pages/DiagnosticsPage').then(m => ({ default: m.DiagnosticsPage })));
const QualitativeExplorerPage = lazy(() => import('./pages/QualitativeExplorerPage').then(m => ({ default: m.QualitativeExplorerPage })));
const ControlledResultsPage = lazy(() => import('./pages/ControlledResultsPage').then(m => ({ default: m.ControlledResultsPage })));

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <JudgeProvider>
        <BrowserRouter>
          <Suspense fallback={<div className="p-8 text-center text-gray-500 font-sans">Loading module...</div>}>
            <Routes>
              <Route path="/" element={<DashboardLayout />}>
                <Route index element={<LeaderboardPage />} />
                <Route path="leaderboard" element={<LeaderboardPage />} />
                <Route path="synthesis" element={<SynthesisPage />} />
                <Route path="diagnostics" element={<DiagnosticsPage />} />
                <Route path="controlled-results" element={<ControlledResultsPage />} />
                <Route path="qualitative-explorer" element={<QualitativeExplorerPage />} />
                {/* Catch-all redirect to home */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
      </JudgeProvider>
    </ThemeProvider>
  );
};

export default App;
