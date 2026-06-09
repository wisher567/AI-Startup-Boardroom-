import { useState } from 'react';

const PHASE_CONFIG = {
  idle:           { text: 'READY',              color: '#475569', bg: '#47556922' },
  connecting:     { text: 'CONNECTING',          color: '#2563eb', bg: '#2563eb22' },
  primer_running: { text: 'BRIEFING AGENTS',     color: '#d97706', bg: '#d9770622' },
  debating:       { text: 'DEBATE IN PROGRESS',  color: '#059669', bg: '#05966922' },
  complete:       { text: 'DEBATE COMPLETE',     color: '#7c3aed', bg: '#7c3aed22' },
};

function fmt(s) {
  const m = Math.floor(s/60), sec = s%60;
  return `${m}:${sec.toString().padStart(2,'0')}`;
}

export function StatusBar({ phase, statusMessage, elapsedTime, connected, memoriesTotal, currentSpeaker }) {
  const cfg = PHASE_CONFIG[phase] || PHASE_CONFIG.idle;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 border-t border-purple-900/20"
      style={{ background: 'rgba(0,0,0,0.4)', minHeight: '28px' }}>

      {/* Phase badge */}
      <span className="font-pixel text-[7px] px-2 py-0.5 rounded shrink-0"
        style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.color}44` }}>
        {cfg.text}
      </span>

      {/* Separator */}
      <span className="text-white/10 text-[10px]">│</span>

      {/* Status message */}
      <span className="font-pixel text-[7px] text-white/40 flex-1 truncate">{statusMessage}</span>

      {/* Memory */}
      {memoriesTotal > 0 && (
        <span className="font-pixel text-[7px] shrink-0"
          style={{ color: '#a78bfa88' }}>
          🧠 {memoriesTotal}
        </span>
      )}

      {/* Timer */}
      {(phase === 'debating' || phase === 'complete') && (
        <span className="font-pixel text-[7px] text-white/25 shrink-0">{fmt(elapsedTime)}</span>
      )}
    </div>
  );
}

export function PromptInput({ onSubmit, phase }) {
  const [prompt, setPrompt] = useState('');
  const isRunning = phase === 'primer_running' || phase === 'debating';

  const submit = () => {
    const t = prompt.trim();
    if (!t || isRunning) return;
    onSubmit(t);
  };

  const examples = [
    'Build an AI travel startup for Sri Lanka tourism',
    'Create a food delivery app for university students',
    'Launch a B2B SaaS tool for freelance accountants',
    'Build an AI tutoring platform for rural schools',
  ];

  return (
    <div className="px-3 py-2">
      <div className="flex gap-2 items-center">
        <div className="flex-1 relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 font-pixel text-[8px] text-purple-500/60">★</span>
          <input
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), submit())}
            placeholder="Describe your startup problem..."
            disabled={isRunning}
            className="w-full pl-7 pr-3 py-2 font-pixel text-[9px] text-white placeholder-white/15 focus:outline-none disabled:opacity-40 transition-all duration-200 rounded"
            style={{
              background: 'rgba(124,58,237,0.08)',
              border: '1px solid rgba(124,58,237,0.25)',
              boxShadow: prompt ? '0 0 12px rgba(124,58,237,0.15)' : 'none',
            }}
          />
        </div>
        <button
          onClick={submit}
          disabled={isRunning || !prompt.trim()}
          className="px-4 py-2 rounded font-pixel text-[8px] transition-all duration-200 disabled:opacity-30 shrink-0 hover:scale-105"
          style={{
            background: isRunning
              ? 'rgba(255,255,255,0.05)'
              : 'linear-gradient(135deg, #7c3aed, #4f46e5)',
            border: isRunning ? '1px solid rgba(255,255,255,0.1)' : '1px solid #9f6aff',
            color: '#ffffff',
            boxShadow: isRunning ? 'none' : '0 0 16px rgba(124,58,237,0.4)',
          }}>
          {isRunning ? '⏳ RUNNING' : '▶ START'}
        </button>
      </div>

      {/* Quick examples */}
      {!isRunning && !prompt && (
        <div className="flex gap-3 mt-1.5 overflow-x-auto pb-0.5 scrollbar-thin">
          {examples.map((ex, i) => (
            <button key={i} onClick={() => setPrompt(ex)}
              className="font-pixel text-[7px] text-white/20 hover:text-purple-400/70 transition-colors whitespace-nowrap shrink-0">
              › {ex}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
