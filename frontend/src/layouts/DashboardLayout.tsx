import React, { useState, useRef, useEffect } from 'react';
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
  ChevronDown,
  Check,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useJudge } from '../context/JudgeContext';
import {
  OpenAIIcon,
  DeepSeekIcon,
  MetaLlamaIcon,
  ClaudeIcon,
} from '../components/ModelIcons';

const JUDGE_OPTIONS = [
  {
    id: 'gpt-4o-mini',
    name: 'GPT-4o-Mini',
    provider: 'OpenAI',
    badge: 'Baseline',
    color: '#10a37f',
    Icon: OpenAIIcon,
  },
  {
    id: 'deepseek/deepseek-chat',
    name: 'DeepSeek V3',
    provider: 'DeepSeek',
    badge: 'Reasoning',
    color: '#2563eb',
    Icon: DeepSeekIcon,
  },
  {
    id: 'meta-llama/llama-3.3-70b-instruct',
    name: 'Llama 3.3 70B',
    provider: 'Meta AI',
    badge: '70B Instruct',
    color: '#0668E1',
    Icon: MetaLlamaIcon,
  },
  {
    id: 'anthropic/claude-3-haiku',
    name: 'Claude 3 Haiku',
    provider: 'Anthropic',
    badge: 'Fast',
    color: '#cc785c',
    Icon: ClaudeIcon,
  },
];

export const DashboardLayout: React.FC = () => {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const { judgeModel, setJudgeModel } = useJudge();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isJudgeOpen, setIsJudgeOpen] = useState(false);
  const judgeDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        judgeDropdownRef.current &&
        !judgeDropdownRef.current.contains(event.target as Node)
      ) {
        setIsJudgeOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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

  const getPageTitle = (pathname: string) => {
    switch (pathname) {
      case '/':
      case '/leaderboard':
        return 'Leaderboard';
      case '/diagnostics':
        return 'Bias Diagnostics';
      case '/qualitative-explorer':
        return 'Qualitative Explorer';
      case '/live-lab':
        return 'Live Evaluation';
      case '/experiments':
        return 'Experiment Controls';
      default:
        return 'Overview';
    }
  };

  const currentJudge =
    JUDGE_OPTIONS.find((opt) => opt.id === judgeModel) || JUDGE_OPTIONS[0];

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
                    isCollapsed
                      ? 'justify-center px-0 py-3'
                      : 'space-x-3 px-3.5 py-3'
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
                <span
                  className="text-[10px] text-neutral-500 dark:text-neutral-400 truncate"
                  title="M2 Intelligent Processing Systems"
                >
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
      <main className="flex-1 bg-white dark:bg-[#171717] min-h-screen p-6 md:p-10 lg:p-12 overflow-y-auto transition-colors duration-150 flex flex-col space-y-6">
        {/* Top Workspace Header Bar */}
        <div className="flex items-center justify-between pb-4 border-b border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center space-x-2 text-xs font-mono text-neutral-500 dark:text-neutral-400">
            <span className="text-neutral-400 dark:text-neutral-500">Workspace</span>
            <span>/</span>
            <span className="font-semibold text-neutral-800 dark:text-neutral-200">
              {getPageTitle(location.pathname)}
            </span>
          </div>

          {/* Sleek Matte Status Chip Judge Selector */}
          <div className="relative" ref={judgeDropdownRef}>
            <button
              type="button"
              onClick={() => setIsJudgeOpen(!isJudgeOpen)}
              className="flex items-center space-x-2.5 px-3 py-1.5 rounded-lg bg-neutral-100 dark:bg-zinc-900/90 border border-neutral-200 dark:border-zinc-800 text-xs font-mono text-neutral-900 dark:text-zinc-100 shadow-xs hover:border-neutral-300 dark:hover:border-zinc-700 transition-all duration-150 ease-out cursor-pointer select-none"
            >
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: currentJudge.color }}
              />
              <currentJudge.Icon
                className="w-3.5 h-3.5 shrink-0"
                style={{ color: currentJudge.color }}
              />
              <span className="font-semibold">{currentJudge.name}</span>
              <span className="text-[10px] text-neutral-500 dark:text-zinc-400 font-normal">
                ({currentJudge.provider})
              </span>
              <ChevronDown
                className={`w-3.5 h-3.5 text-neutral-400 shrink-0 transition-transform duration-150 ${
                  isJudgeOpen ? 'rotate-180' : ''
                }`}
              />
            </button>

            {isJudgeOpen && (
              <div className="absolute right-0 top-full mt-1.5 w-64 rounded-xl bg-white dark:bg-zinc-950 border border-neutral-200 dark:border-zinc-800 shadow-xl shadow-black/40 p-1.5 z-50 font-mono text-xs space-y-0.5">
                <div className="px-2 py-1 text-[10px] uppercase tracking-wider text-neutral-400 dark:text-zinc-500 font-semibold border-b border-neutral-100 dark:border-zinc-800/60 mb-1">
                  Evaluator Judge
                </div>
                {JUDGE_OPTIONS.map((opt) => {
                  const isActive = opt.id === judgeModel;
                  const OptionIcon = opt.Icon;

                  return (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => {
                        setJudgeModel(opt.id);
                        setIsJudgeOpen(false);
                      }}
                      className={`w-full px-2.5 py-2 rounded-lg flex items-center justify-between text-left cursor-pointer transition-colors duration-150 ${
                        isActive
                          ? 'bg-neutral-100 dark:bg-zinc-900 font-semibold text-neutral-900 dark:text-zinc-100'
                          : 'text-neutral-600 dark:text-zinc-400 hover:text-neutral-900 dark:hover:text-zinc-200 hover:bg-neutral-50 dark:hover:bg-zinc-900/60'
                      }`}
                    >
                      <span className="flex items-center space-x-2.5 min-w-0">
                        <span
                          className="w-2 h-2 rounded-full shrink-0"
                          style={{ backgroundColor: opt.color }}
                        />
                        <OptionIcon
                          className="w-4 h-4 shrink-0"
                          style={{ color: opt.color }}
                        />
                        <span className="flex flex-col min-w-0">
                          <span className="truncate text-xs leading-none mb-0.5">
                            {opt.name}
                          </span>
                          <span className="text-[10px] text-neutral-500 dark:text-zinc-500 font-normal truncate">
                            {opt.provider} &bull; {opt.badge}
                          </span>
                        </span>
                      </span>
                      {isActive && (
                        <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0 ml-2" />
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div className="flex-1">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

