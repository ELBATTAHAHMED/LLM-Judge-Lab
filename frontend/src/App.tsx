import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { DashboardLayout } from './layouts/DashboardLayout';
import { LeaderboardPage } from './pages/LeaderboardPage';
import { DiagnosticsPage } from './pages/DiagnosticsPage';
import { QualitativeExplorerPage } from './pages/QualitativeExplorerPage';
import { LiveLabPage } from './pages/LiveLabPage';
import { ExperimentControlCenter } from './pages/ExperimentControlCenter';

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<DashboardLayout />}>
            <Route index element={<LeaderboardPage />} />
            <Route path="leaderboard" element={<LeaderboardPage />} />
            <Route path="diagnostics" element={<DiagnosticsPage />} />
            <Route path="qualitative-explorer" element={<QualitativeExplorerPage />} />
            <Route path="live-lab" element={<LiveLabPage />} />
            <Route path="experiments" element={<ExperimentControlCenter />} />
            {/* Catch-all redirect to home */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
};

export default App;
