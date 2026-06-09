import { useEffect, useRef } from 'react';
import { getAgentColor, getAgentAbbr, AGENTS } from '../utils/agents';

export function ActivityFeed({ messages, orgEvents }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, orgEvents]);

  const all = [
    ...messages.map(m => ({ ...m, kind: m.type || 'message' })),
    ...orgEvents.map(e => ({ ...e, kind: 'event' })),
  ];

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-purple-900/20 shrink-0 flex items-center">
        <span className="text-[8px] font-pixel text-purple-400/60 uppercase tracking-widest">Activity</span>
        <span className="ml-auto text-[7px] font-pixel text-white/20">{messages.length}</span>
      </div>
      <div className="flex-1 overflow-y-auto px-1.5 py-1 space-y-1 scrollbar-thin">
        {all.length === 0 && (
          <div className="text-center font-pixel text-[8px] text-white/15 mt-8">
            Waiting for debate...
          </div>
        )}

        {all.map((entry, i) => {
          /* Org health event */
          if (entry.kind === 'event') {
            return (
              <div key={`e${i}`}
                className="flex items-start gap-1.5 px-2 py-1.5 rounded"
                style={{ background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.2)' }}>
                <span className="text-[9px] mt-0.5">⚠</span>
                <div className="flex-1 min-w-0">
                  <div className="font-pixel text-[7px] text-amber-400">
                    {entry.event?.replace(/_/g,' ').toUpperCase()}
                  </div>
                  <div className="text-[7px] text-white/30 mt-0.5 leading-relaxed">{entry.reason}</div>
                </div>
              </div>
            );
          }

          /* Tool call */
          if (entry.kind === 'tool_call') {
            return (
              <div key={`tc${i}`}
                className="flex items-center gap-1.5 px-2 py-1.5 rounded"
                style={{ background: 'rgba(37,99,235,0.08)', border: '1px solid rgba(37,99,235,0.2)' }}>
                <span className="text-blue-400 text-[9px] animate-spin">⚙</span>
                <div className="flex-1 min-w-0">
                  <span className="font-pixel text-[7px] text-blue-300">{entry.agent}</span>
                  <span className="font-pixel text-[7px] text-white/20 ml-1">→ {entry.tool}</span>
                  <div className="text-[7px] text-blue-200/40 mt-0.5 truncate">"{entry.query}"</div>
                </div>
              </div>
            );
          }

          /* Tool result */
          if (entry.kind === 'tool_result') {
            return (
              <div key={`tr${i}`}
                className="flex items-start gap-1.5 px-2 py-1.5 rounded"
                style={{ background: 'rgba(5,150,105,0.08)', border: '1px solid rgba(5,150,105,0.2)' }}>
                <span className="text-green-400 text-[9px]">✓</span>
                <div className="flex-1 min-w-0">
                  <span className="font-pixel text-[7px] text-green-300">{entry.tool} result</span>
                  <div className="text-[7px] text-white/40 mt-0.5 leading-relaxed line-clamp-2">{entry.result_preview}</div>
                </div>
              </div>
            );
          }

          /* Learning complete */
          if (entry.kind === 'learning_complete') {
            return (
              <div key={`lc${i}`}
                className="flex items-center gap-1.5 px-2 py-1.5 rounded"
                style={{ background: 'rgba(124,58,237,0.08)', border: '1px solid rgba(124,58,237,0.2)' }}>
                <span className="text-[9px]">🧠</span>
                <div className="font-pixel text-[7px] text-purple-300">
                  {entry.agents_updated?.length || 0} agents updated stances
                </div>
              </div>
            );
          }

          /* Regular agent message */
          const color = getAgentColor(entry.agent);
          const abbr  = getAgentAbbr(entry.agent);
          const label = AGENTS[entry.agent]?.label || '';

          return (
            <div key={`m${i}`}
              className="flex items-start gap-1.5 px-2 py-1.5 rounded transition-all duration-200 hover:bg-white/3"
              style={{ borderLeft: `2px solid ${color}44` }}>
              <div className="w-5 h-5 rounded flex items-center justify-center font-pixel text-[6px] shrink-0 mt-0.5"
                style={{
                  background: color + '22',
                  border: `1px solid ${color}44`,
                  color,
                }}>
                {abbr}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-1">
                  <span className="font-pixel text-[7px]" style={{ color }}>{entry.agent}</span>
                  <span className="text-[6px] text-white/20">{entry.timestamp}</span>
                </div>
                <p className="text-[8px] text-white/60 mt-0.5 leading-relaxed break-words">{entry.message}</p>
                {entry.flags?.filter(f => !f.startsWith('tool_call')).length > 0 && (
                  <div className="flex gap-1 mt-1 flex-wrap">
                    {entry.flags.filter(f => !f.startsWith('tool_call')).map(f => (
                      <span key={f} className="font-pixel text-[6px] px-1.5 py-0.5 rounded"
                        style={{ background: 'rgba(239,68,68,0.15)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.2)' }}>
                        {f}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
