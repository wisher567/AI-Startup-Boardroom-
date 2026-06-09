import { useMemo, useRef, useEffect } from 'react';

/* ================================================================
   Agent role → colour & initials mapping
   ================================================================ */
const AGENT_META = {
  CEO:                { color: '#7C3AED', initials: 'CE', role: 'CEO' },
  CTO:                { color: '#059669', initials: 'CT', role: 'CTO' },
  CFO:                { color: '#D97706', initials: 'CF', role: 'CFO' },
  CMO:                { color: '#DB2777', initials: 'CM', role: 'CMO' },
  COO:                { color: '#475569', initials: 'CO', role: 'COO' },
  Investor:           { color: '#2563EB', initials: 'IN', role: 'Investor' },
  Legal:              { color: '#65A30D', initials: 'LE', role: 'Legal' },
  UX:                 { color: '#E11D48', initials: 'UX', role: 'UX Lead' },
  MarketAnalyst:      { color: '#DC2626', initials: 'MA', role: 'Market Analyst' },
  Critic:             { color: '#EA580C', initials: 'CR', role: 'Critic' },
  Chaos:              { color: '#7C3AED', initials: 'CH', role: 'Chaos Agent' },
  'Customer Persona 1': { color: '#0D9488', initials: 'P1', role: 'Persona 1' },
  'Customer Persona 2': { color: '#0891B2', initials: 'P2', role: 'Persona 2' },
  'Industry Partner':   { color: '#4F46E5', initials: 'IP', role: 'Industry Partner' },
};

/* Default for persona-generated names that don't match the 14 */
const FALLBACK_META = { color: '#6B7280', initials: '??', role: 'Agent' };

function getMeta(name) {
  return AGENT_META[name] || FALLBACK_META;
}

/* ================================================================
   Single agent card
   ================================================================ */
function AgentCard({ name, isActive, tokenText, messageComplete }) {
  const meta = getMeta(name);
  const bubbleRef = useRef(null);

  // Auto-scroll bubble text to bottom as tokens stream in
  useEffect(() => {
    if (bubbleRef.current && isActive) {
      bubbleRef.current.scrollTop = bubbleRef.current.scrollHeight;
    }
  }, [tokenText, isActive]);

  return (
    <div className="relative">
      {/* Speech bubble — shown when this agent is speaking */}
      {isActive && tokenText && (
        <div
          ref={bubbleRef}
          className={`
            absolute bottom-full left-1/2 -translate-x-1/2 mb-3 z-20
            w-72 max-h-44 overflow-y-auto
            bg-gray-800 border border-gray-600 rounded-xl px-4 py-3
            text-xs leading-relaxed text-gray-200 shadow-2xl
            ${messageComplete ? 'speech-bubble-fading' : 'speech-bubble'}
          `}
          style={{ borderColor: meta.color + '88' }}
        >
          {tokenText}
        </div>
      )}

      {/* Card */}
      <div
        className={`
          relative flex flex-col items-center gap-2 p-4 rounded-2xl
          bg-gray-900 border-2 border-gray-800
          transition-all duration-300
          ${isActive ? 'agent-card-active scale-105' : 'hover:border-gray-700'}
        `}
        style={{
          '--glow-color': meta.color,
          borderColor: isActive ? meta.color : undefined,
        }}
      >
        {/* Avatar circle */}
        <div
          className="w-12 h-12 rounded-full flex items-center justify-center text-sm font-bold text-white shadow-lg transition-transform duration-300"
          style={{ backgroundColor: meta.color }}
        >
          {meta.initials}
        </div>

        {/* Name + role */}
        <div className="text-center">
          <p className="text-sm font-semibold text-white truncate max-w-[120px]">
            {name}
          </p>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">
            {meta.role}
          </p>
        </div>

        {/* Active indicator dot */}
        {isActive && (
          <span
            className="absolute top-2 right-2 w-2.5 h-2.5 rounded-full status-pulse"
            style={{ backgroundColor: meta.color }}
          />
        )}
      </div>
    </div>
  );
}

/* ================================================================
   AgentGrid — 14 cards in responsive grid
   ================================================================ */
export default function AgentGrid({
  turnOrder,
  activeSpeaker,
  personaNames,
}) {
  // Build the canonical 14-agent list, merging in persona display names
  const agents = useMemo(() => {
    const base = [
      'CEO', 'CTO', 'CMO', 'COO', 'MarketAnalyst', 'CFO',
      'UX', 'Legal', 'Investor',
      'Customer Persona 1', 'Customer Persona 2',
      'Industry Partner', 'Chaos', 'Critic',
    ];
    return base.map((name) => ({
      name,
      displayName: personaNames[name] || name,
    }));
  }, [personaNames]);

  // Compute the current active agent name
  const activeName = activeSpeaker?.agent || null;
  const activeTokens = activeSpeaker?.tokens?.join('') || '';
  const messageComplete = activeSpeaker?.complete || false;

  return (
    <div className="w-full h-full overflow-y-auto p-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-7 gap-3 max-w-[1400px] mx-auto">
        {agents.map(({ name, displayName }) => (
          <AgentCard
            key={name}
            name={displayName}
            isActive={activeName === name || activeName === displayName}
            tokenText={activeName === name || activeName === displayName ? activeTokens : ''}
            messageComplete={
              (activeName === name || activeName === displayName) && messageComplete
            }
          />
        ))}
      </div>

      {/* Empty state */}
      {agents.length === 0 && (
        <div className="flex items-center justify-center h-64 text-gray-600">
          <p className="text-sm">Waiting for agent roster...</p>
        </div>
      )}
    </div>
  );
}
