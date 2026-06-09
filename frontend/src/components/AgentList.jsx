import { getAgentColor, AGENTS } from '../utils/agents';

export function AgentList({ currentSpeaker, turnOrder, agentTokens }) {
  const agents = Object.entries(AGENTS);

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-purple-900/20 shrink-0">
        <span className="text-[8px] font-pixel text-purple-400/60 uppercase tracking-widest">Agent List</span>
      </div>
      <div className="flex-1 overflow-y-auto px-1.5 py-1 space-y-0.5 scrollbar-thin">
        {agents.map(([name, cfg]) => {
          const isSpeaking = currentSpeaker === name;
          const isNext     = turnOrder[0] === name;
          const color      = cfg.color;

          return (
            <div key={name}
              className="flex items-center gap-1.5 px-2 py-1.5 rounded transition-all duration-300 relative overflow-hidden"
              style={isSpeaking ? {
                background: color + '18',
                border: `1px solid ${color}55`,
                boxShadow: `0 0 12px ${color}22, inset 0 0 12px ${color}08`,
              } : {
                background: 'transparent',
                border: '1px solid transparent',
              }}>

              {/* Speaking glow sweep */}
              {isSpeaking && (
                <div className="absolute inset-0 pointer-events-none"
                  style={{
                    background: `linear-gradient(90deg, transparent, ${color}11, transparent)`,
                    animation: 'shimmer 2s infinite',
                  }} />
              )}

              {/* Status dot */}
              <div className="w-1.5 h-1.5 rounded-full shrink-0 transition-all duration-300"
                style={{
                  background: color,
                  opacity: isSpeaking ? 1 : 0.3,
                  boxShadow: isSpeaking ? `0 0 6px ${color}` : 'none',
                }} />

              {/* Avatar */}
              <div className="w-6 h-6 rounded flex items-center justify-center text-[7px] font-pixel shrink-0"
                style={{
                  background: isSpeaking ? color + '33' : color + '11',
                  border: `1px solid ${isSpeaking ? color + 'aa' : color + '33'}`,
                  color,
                  boxShadow: isSpeaking ? `0 0 8px ${color}44` : 'none',
                }}>
                {cfg.abbr}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="text-[8px] font-pixel truncate transition-colors duration-300"
                  style={{ color: isSpeaking ? color : '#ffffff55' }}>
                  {name}
                </div>
                <div className="text-[7px] text-white/20 truncate">{cfg.label}</div>
              </div>

              {/* Speaking bars */}
              {isSpeaking && (
                <div className="flex gap-0.5 items-end h-3 shrink-0">
                  {[0,1,2].map(i => (
                    <div key={i} className="w-0.5 rounded-full animate-bounce"
                      style={{
                        background: color,
                        height: `${5 + i*3}px`,
                        animationDelay: `${i*0.12}s`,
                        boxShadow: `0 0 3px ${color}`,
                      }} />
                  ))}
                </div>
              )}

              {!isSpeaking && isNext && (
                <span className="text-[6px] font-pixel shrink-0"
                  style={{ color: color + '88' }}>›</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
