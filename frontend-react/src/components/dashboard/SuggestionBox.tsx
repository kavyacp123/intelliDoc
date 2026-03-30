import React from 'react';
import { Button } from '../ui';

interface SuggestionBoxProps {
  suggestions: string[];
  originalQuery: string;
  onPick: (query: string) => void;
}

export const SuggestionBox: React.FC<SuggestionBoxProps> = ({ 
  suggestions, 
  originalQuery, 
  onPick 
}) => {
  return (
    <div className="flex gap-6 max-w-4xl mb-8">
      <div className="flex-shrink-0 w-8 h-8 mt-1">
        <span className="material-symbols-outlined text-secondary font-fill" style={{ fontVariationSettings: "'FILL' 1" }}>
          lightbulb
        </span>
      </div>
      <div className="flex-1">
        <div className="text-on-surface leading-relaxed text-sm font-body mb-3">
          <span className="font-semibold text-secondary">I can help with that!</span> Did you mean one of these?
        </div>
        <div className="flex flex-wrap gap-2 mb-3">
          {suggestions.map((s, i) => (
            <button
              key={i}
              onClick={() => onPick(s)}
              className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-white border border-secondary/20 text-secondary rounded-xl text-xs font-semibold shadow-sm hover:bg-secondary hover:text-white transition-all duration-200 active:scale-95"
            >
              <span className="material-symbols-outlined text-[14px]">auto_awesome</span>
              {s}
            </button>
          ))}
        </div>
        <Button 
          variant="secondary"
          className="px-3 py-2 h-auto text-[11px] border border-outline-variant/20"
          onClick={() => onPick(originalQuery)}
        >
          <span className="material-symbols-outlined text-[13px]">play_arrow</span>
          <span>Run original: "{originalQuery.length > 40 ? originalQuery.substring(0, 40) + '...' : originalQuery}"</span>
        </Button>
      </div>
    </div>
  );
};
