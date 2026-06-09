import { useState, useEffect, useRef } from 'react';

/* ================================================================
   Status label lookup
   ================================================================ */
function getStatusLabel(status, activeSpeaker) {
  switch (status) {
    case 'idle':
      return { text: 'Ready', color: 'text-gray-500', dot: 'bg-gray-500' };
    case 'primer':
      return {
        text: 'Agents reviewing the problem...',
        color: 'text-amber-400',
        dot: 'bg-amber-400 status-pulse',
      };
    case 'debating':
      if (activeSpeaker) {
        return {
          text: `${activeSpeaker.agent} is speaking...`,
          color: 'text-cyan-400',
          dot: 'bg-cyan-400 status-pulse',
        };
      }
      return {
        text: 'Debate in progress...',
        color: 'text-cyan-400',
        dot: 'bg-cyan-400 status-pulse',
      };
    case 'complete':
      return { text: 'Debate complete', color: 'text-emerald-400', dot: 'bg-emerald-400' };
    case 'error':
      return { text: 'Debate error', color: 'text-red-400', dot: 'bg-red-400' };
    default:
      return { text: 'Idle', color: 'text-gray-500', dot: 'bg-gray-500' };
  }
}

function formatElapsed(ms) {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}

/* ================================================================
   PromptInput + StatusBar — fixed bottom bar
   ================================================================ */
export default function PromptInput({
  status,
  activeSpeaker,
  connected,
  clientId,
  debating,
  memoriesFound,
  onStart,
  onClear,
}) {
  const [prompt, setPrompt] = useState('');
  const [elapsedMs, setElapsedMs] = useState(0);
  const timerRef = useRef(null);
  const inputRef = useRef(null);

  const isRunning = status === 'primer' || status === 'debating';
  const isComplete = status === 'complete';
  const canStart = connected && clientId && prompt.trim() && !isRunning;

  // Elapsed timer
  useEffect(() => {
    if (isRunning) {
      const start = Date.now() - elapsedMs;
      timerRef.current = setInterval(() => {
        setElapsedMs(Date.now() - start);
      }, 200);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      if (status === 'idle') setElapsedMs(0);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRunning]); // eslint-disable-line react-hooks/exhaustive-deps

  const statusInfo = getStatusLabel(status, activeSpeaker);

  const handleSubmit = () => {
    if (!canStart) return;
    onStart(prompt.trim());
    setPrompt('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-gray-900/95 backdrop-blur-sm border-t border-gray-800">
      {/* Status bar row */}
      <div className="flex items-center gap-4 px-4 py-1.5 text-xs border-b border-gray-800/50">
        {/* Status dot + label */}
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${statusInfo.dot}`} />
          <span className={statusInfo.color}>{statusInfo.text}</span>
        </div>

        {/* Elapsed time */}
        {isRunning && (
          <span className="text-gray-500 font-mono tabular-nums">
            {formatElapsed(elapsedMs)}
          </span>
        )}

        {/* Memories */}
        {memoriesFound > 0 && (
          <span className="text-gray-600">
            Memory: {memoriesFound} past debate{memoriesFound !== 1 ? 's' : ''} recalled
          </span>
        )}

        {/* Connection dots */}
        <div className="ml-auto flex items-center gap-3">
          <span className="flex items-center gap-1 text-gray-600">
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-400' : 'bg-red-400'}`} />
            WS
          </span>
          <span className="flex items-center gap-1 text-gray-600">
            <span className={`w-1.5 h-1.5 rounded-full ${clientId ? 'bg-green-400' : 'bg-red-400'}`} />
            Registered
          </span>
        </div>
      </div>

      {/* Input row */}
      <div className="flex items-center gap-3 px-4 py-2.5">
        <input
          ref={inputRef}
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter a startup prompt..."
          disabled={isRunning}
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 disabled:opacity-40 prompt-glow transition-all"
        />

        {/* Start / New Debate button */}
        {!isRunning && !isComplete && (
          <button
            onClick={handleSubmit}
            disabled={!canStart}
            className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 disabled:from-gray-700 disabled:to-gray-700 disabled:text-gray-500 text-white px-6 py-2.5 rounded-lg text-sm font-semibold transition-all disabled:cursor-not-allowed"
          >
            Start Debate
          </button>
        )}

        {/* Running indicator */}
        {isRunning && (
          <button
            disabled
            className="bg-gray-800 text-gray-500 px-6 py-2.5 rounded-lg text-sm font-semibold cursor-not-allowed"
          >
            Debating...
          </button>
        )}

        {/* Complete — new debate */}
        {isComplete && (
          <button
            onClick={() => {
              onClear();
              setPrompt('');
              setElapsedMs(0);
              setTimeout(() => inputRef.current?.focus(), 100);
            }}
            className="bg-emerald-600 hover:bg-emerald-500 text-white px-6 py-2.5 rounded-lg text-sm font-semibold transition-all"
          >
            New Debate
          </button>
        )}
      </div>
    </div>
  );
}
