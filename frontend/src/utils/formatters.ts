export const formatModelName = (modelName: string): string => {
  if (!modelName) return '';

  return modelName
    .split(/\s+vs\s+/i)
    .map((singleModel) => {
      const trimmed = singleModel.trim();
      const lower = trimmed.toLowerCase();

      if (lower === 'gpt-4') return 'GPT-4';
      if (lower === 'gpt-3.5-turbo') return 'GPT-3.5-Turbo';
      if (lower === 'gpt-4o-mini') return 'GPT-4o-Mini';
      if (lower === 'claude-v1') return 'Claude-v1';
      if (lower === 'llama-13b') return 'Llama-13B';
      if (lower === 'llama3' || lower === 'llama-3') return 'Llama-3 8B';
      if (lower === 'vicuna-13b') return 'Vicuna-13B';
      if (lower === 'alpaca-13b') return 'Alpaca-13B';
      // Production multi-judge panel models
      if (lower === 'deepseek/deepseek-chat') return 'DeepSeek V3 (Chat)';
      if (lower === 'meta-llama/llama-3.3-70b-instruct') return 'Llama 3.3 70B Instruct';
      if (lower === 'anthropic/claude-3-haiku') return 'Claude 3 Haiku';
      if (lower === 'anthropic/claude-3.5-haiku') return 'Claude 3.5 Haiku';

      // Fallback formatting for custom model strings
      return trimmed
        .replace(/^gpt/i, 'GPT')
        .replace(/13b$/i, '13B')
        .replace(/8b$/i, '8B')
        .replace(/(\b[a-z])/g, (match) => match.toUpperCase());
    })
    .join(' vs ');
};
