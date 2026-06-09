import { useMemo } from 'react';
import { getAgentColor, getAgentAbbr, AGENT_NAMES, AGENTS } from '../utils/agents';

export function TrustNetwork({ trustMatrix }) {
  const agents = AGENT_NAMES;
  const count  = agents.length;

  const positions = useMemo(() => {
    const cx = 104, cy = 104, r = 82;
    return agents.map((name, i) => {
      const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
      return { name, x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
    });
  }, [agents, count]);

  const posMap = useMemo(() => {
    const m = {};
    positions.forEach(p => { m[p.name] = p; });
    return m;
  }, [positions]);

  const edges = useMemo(() => {
    const result = [];
    Object.entries(trustMatrix).forEach(([from, targets]) => {
      Object.entries(targets).forEach(([to, score]) => {
        if (score > 0.6 && posMap[from] && posMap[to]) {
          result.push({ from, to, score });
        }
      });
    });
    return result;
  }, [trustMatrix, posMap]);

  const trustColor = (s) => s >= 0.75 ? '#34d399' : s >= 0.55 ? '#fbbf24' : '#f87171';

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-purple-900/20 shrink-0">
        <span className="text-[8px] font-pixel text-purple-400/60 uppercase tracking-widest">Trust Network</span>
      </div>
      <div className="flex-1 flex items-center justify-center">
        <svg width="208" height="208" viewBox="0 0 208 208">
          {/* Background circle */}
          <circle cx="104" cy="104" r="84" fill="none" stroke="rgba(124,58,237,0.08)" strokeWidth="1" />
          <circle cx="104" cy="104" r="60" fill="none" stroke="rgba(124,58,237,0.05)" strokeWidth="1" />

          {/* Edges */}
          {edges.map((e, i) => {
            const f = posMap[e.from], t = posMap[e.to];
            return (
              <line key={i}
                x1={f.x} y1={f.y} x2={t.x} y2={t.y}
                stroke={trustColor(e.score)}
                strokeWidth={0.5 + e.score * 2}
                opacity={0.15 + e.score * 0.45}
              />
            );
          })}

          {/* Nodes */}
          {positions.map(({ name, x, y }) => {
            const color = getAgentColor(name);
            const abbr  = getAgentAbbr(name);
            const inbound = Object.values(trustMatrix).map(t => t[name]).filter(Boolean);
            const avg = inbound.length
              ? inbound.reduce((a,b) => a+b, 0) / inbound.length
              : 0.55;
            const r = 8 + avg * 4;

            return (
              <g key={name}>
                {/* Outer glow ring */}
                <circle cx={x} cy={y} r={r+4} fill={color} opacity={0.06} />
                <circle cx={x} cy={y} r={r+2} fill={color} opacity={0.10} />
                {/* Node body */}
                <circle cx={x} cy={y} r={r} fill="#0a0a12" stroke={color} strokeWidth={1.5}
                  style={{ filter: `drop-shadow(0 0 3px ${color}66)` }} />
                <text x={x} y={y+2.5} textAnchor="middle"
                  fontSize="5.5" fontFamily='"Press Start 2P",monospace' fill={color}>
                  {abbr}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Legend */}
      <div className="px-3 pb-2 flex gap-3 shrink-0">
        {[['#34d399','High'],['#fbbf24','Med'],['#f87171','Low']].map(([c,l]) => (
          <div key={l} className="flex items-center gap-1">
            <div className="w-4 h-0.5 rounded" style={{ background: c }} />
            <span className="font-pixel text-[7px]" style={{ color: c + '88' }}>{l}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
