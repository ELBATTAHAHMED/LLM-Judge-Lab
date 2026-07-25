import React, { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  Landmark,
  Trophy,
  Activity,
  Search,
  FlaskConical,
  Sun,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Terminal,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

export const DashboardLayout: React.FC = () => {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const [isCollapsed, setIsCollapsed] = useState(false);

  const navItems = [
    {
      path: '/',
      label: 'Leaderboard',
      icon: Trophy,
    },
    {
      path: '/diagnostics',
      label: 'Bias Diagnostics',
      icon: Activity,
    },
    {
      path: '/qualitative-explorer',
      label: 'Qualitative Explorer',
      icon: Search,
    },
    {
      path: '/live-lab',
      label: 'Live Evaluation',
      icon: FlaskConical,
    },
    {
      path: '/experiments',
      label: 'Experiment Controls',
      icon: Terminal,
    },
  ];

  return (
    <div className="min-h-screen bg-white dark:bg-[#171717] text-neutral-900 dark:text-neutral-100 flex font-sans antialiased selection:bg-neutral-200 dark:selection:bg-neutral-800 transition-colors duration-150">
      {/* Fixed Left Sidebar - Collapsible Vercel v0 Style */}
      <aside
        className={`${
          isCollapsed ? 'w-16' : 'w-64'
        } bg-neutral-50 dark:bg-[#0a0a0a] border-r border-neutral-200 dark:border-neutral-800 flex flex-col justify-between h-screen sticky top-0 shrink-0 z-40 select-none transition-all duration-200 ease-in-out`}
      >
        {/* Top Header & Nav Section */}
        <div className="px-4 pb-4 pt-7 space-y-9">
          {/* Top Branding Header & Controls */}
          <div className="flex items-center justify-between px-1.5 py-1 rounded-md text-neutral-800 dark:text-neutral-200">
            {!isCollapsed ? (
              <>
                <div className="flex items-center space-x-2.5">
                  <div className="flex items-center justify-center w-9 h-9 rounded-md bg-neutral-800 text-neutral-100 font-bold">
                    <Landmark className="w-[18px] h-[18px]" />
                  </div>
                  <span className="font-semibold text-base tracking-tight text-neutral-900 dark:text-white">
                    JudgeLab
                  </span>
                </div>

                <div className="flex items-center space-x-0.5">
                  {/* Theme Toggle Button */}
                  <button
                    onClick={toggleTheme}
                    title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
                    className="p-1.5 rounded-md text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white hover:bg-neutral-200 dark:hover:bg-neutral-800 transition-colors cursor-pointer"
                  >
                    {theme === 'dark' ? (
                      <Sun className="w-[18px] h-[18px] text-neutral-300" />
                    ) : (
                      <Moon className="w-[18px] h-[18px] text-neutral-600" />
                    )}
                  </button>

                  {/* Collapse Sidebar Button */}
                  <button
                    onClick={() => setIsCollapsed(true)}
                    title="Collapse Sidebar"
                    className="p-1.5 rounded-md text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white hover:bg-neutral-200 dark:hover:bg-neutral-800 transition-colors cursor-pointer"
                  >
                    <PanelLeftClose className="w-[18px] h-[18px]" />
                  </button>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center space-y-2.5 w-full">
                <div
                  className="flex items-center justify-center w-9 h-9 rounded-md bg-neutral-800 text-neutral-100 cursor-pointer"
                  title="JudgeLab"
                >
                  <Landmark className="w-[18px] h-[18px]" />
                </div>

                <button
                  onClick={() => setIsCollapsed(false)}
                  title="Expand Sidebar"
                  className="p-1.5 rounded-md text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white hover:bg-neutral-200 dark:hover:bg-neutral-800 transition-colors cursor-pointer"
                >
                  <PanelLeftOpen className="w-[18px] h-[18px]" />
                </button>

                <button
                  onClick={toggleTheme}
                  title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
                  className="p-1.5 rounded-md text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-white hover:bg-neutral-200 dark:hover:bg-neutral-800 transition-colors cursor-pointer"
                >
                  {theme === 'dark' ? (
                    <Sun className="w-[18px] h-[18px] text-neutral-300" />
                  ) : (
                    <Moon className="w-[18px] h-[18px] text-neutral-600" />
                  )}
                </button>
              </div>
            )}
          </div>

          {/* Main Navigation (Actual Research Routes) */}
          <nav className="space-y-2 text-[13.5px] font-medium">
            {navItems.map((item) => {
              const IconComponent = item.icon;
              const isActive =
                location.pathname === item.path ||
                (item.path === '/' && location.pathname === '/leaderboard');

              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  title={isCollapsed ? item.label : undefined}
                  className={`flex items-center ${
                    isCollapsed ? 'justify-center px-0 py-3' : 'space-x-3 px-3.5 py-3'
                  } rounded-md transition-colors ${
                    isActive
                      ? 'bg-neutral-200/35 text-neutral-900 font-semibold dark:bg-neutral-800/35 dark:text-neutral-100'
                      : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:text-neutral-200 dark:hover:bg-neutral-800/50'
                  }`}
                >
                  <IconComponent
                    className={`w-[15px] h-[15px] ${
                      isActive
                        ? 'text-neutral-900 dark:text-neutral-100'
                        : 'text-neutral-400 dark:text-neutral-500'
                    }`}
                  />
                  {!isCollapsed && <span>{item.label}</span>}
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Bottom User Profile Section */}
        <div className="p-3 border-t border-neutral-200 dark:border-neutral-800">
          {!isCollapsed ? (
            <div className="flex items-center space-x-2.5 px-1 py-0.5">
              <div className="w-6.5 h-6.5 rounded-full bg-neutral-200 dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-700 text-neutral-800 dark:text-neutral-200 text-[10px] font-bold flex items-center justify-center shrink-0">
                A
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-xs font-semibold text-neutral-800 dark:text-neutral-200 truncate">
                  Ahmed El Battah
                </span>
                <span className="text-[10px] text-neutral-500 dark:text-neutral-400 truncate" title="M2 Intelligent Processing Systems">
                  M2 Intelligent Processing Systems
                </span>
              </div>
            </div>
          ) : (
            <div className="flex justify-center py-0.5">
              <div
                className="w-6.5 h-6.5 rounded-full bg-neutral-200 dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-700 text-neutral-800 dark:text-neutral-200 text-[10px] font-bold flex items-center justify-center shrink-0 cursor-pointer"
                title="Ahmed El Battah (M2 Intelligent Processing Systems)"
              >
                A
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Workspace Area */}
      <main className="flex-1 bg-white dark:bg-[#171717] min-h-screen p-6 md:p-10 lg:p-12 overflow-y-auto transition-colors duration-150">
        <Outlet />
      </main>
    </div>
  );
};
