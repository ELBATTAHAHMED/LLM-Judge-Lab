// oxlint-disable react/only-export-components -- the provider and its hook are one public context contract.
import React, { createContext, useContext, useState } from 'react';

interface JudgeContextType {
  judgeModel: string;
  setJudgeModel: (model: string) => void;
}

const DEFAULT_JUDGE_MODEL = 'gpt-4o-mini';

const JudgeContext = createContext<JudgeContextType | undefined>(undefined);

export const JudgeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [judgeModel, setJudgeModelState] = useState<string>(() => {
    const saved = localStorage.getItem('judgelab_selected_model');
    return saved || DEFAULT_JUDGE_MODEL;
  });

  const setJudgeModel = (model: string) => {
    setJudgeModelState(model);
    localStorage.setItem('judgelab_selected_model', model);
  };

  return (
    <JudgeContext.Provider value={{ judgeModel, setJudgeModel }}>
      {children}
    </JudgeContext.Provider>
  );
};

/**
 * Defensive Custom Hook: Falls back safely to default state if context is undefined,
 * preventing any uncaught runtime exceptions.
 */
export const useJudge = (): JudgeContextType => {
  const context = useContext(JudgeContext);
  if (!context) {
    return {
      judgeModel: DEFAULT_JUDGE_MODEL,
      setJudgeModel: () => {},
    };
  }
  return context;
};
