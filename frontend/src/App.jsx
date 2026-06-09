import { useState, useEffect } from 'react';
import { PhaserCanvas }   from './components/PhaserCanvas';
import { ActivityFeed }   from './components/ActivityFeed';
import { TrustNetwork }   from './components/TrustNetwork';
import { AgentList }      from './components/AgentList';
import { StatusBar, PromptInput } from './components/StatusBar';
import { SummaryPanel }   from './components/SummaryPanel';
import { useDebateSocket } from './hooks/useDebateSocket';
import { getAgentColor }  from './utils/agents';

export default function App() {
  const [showSummary, setShowSummary]   = useState(false);
  const [rightTab, setRightTab]         = useState('trust');
  const [dayCount, setDayCount]         = useState(1);
  const [timeStr, setTimeStr]           = useState('09:00 AM');

  const {
    connected, phase, currentSpeaker,
    agentTokens, agentMessages, trustMatrix,
    orgEvents, memories, memoriesTotal,
    turnOrder, debateSummary,
    elapsedTime, statusMessage,
    startDebate, registerPhaserEmitter,
  } = useDebateSocket();

  // Simulated clock
  useEffect(() => {
    const tick = setInterval(() => {
      const now = new Date();
      setTimeStr(now.toLocaleTimeString('en-US', { hour:'2-digit', minute:'2-digit' }));
    }, 1000);
    return () => clearInterval(tick);
  }, []);

  // Increment day on each debate complete
  useEffect(() => {
    if (phase === 'complete') setDayCount(d => d + 1);
  }, [phase]);

  const trustAvg = trustMatrix && Object.keys(trustMatrix).length > 0
    ? Math.round(
        Object.values(trustMatrix).flatMap(t => Object.values(t))
          .reduce((a,b) => a+b, 0) /
        Object.values(trustMatrix).flatMap(t => Object.values(t)).length * 100
      )
    : null;

  const speakerColor = currentSpeaker ? getAgentColor(currentSpeaker) : null;

  return (
    <div className="h-screen w-screen bg-[#050508] text-white flex flex-col overflow-hidden relative">

      {/* Scanline overlay */}
      <div className="scanline absolute inset-0 z-50 pointer-events-none opacity-30" />

      {/* ── Top bar ───────────────────────────────────────────── */}
      <header className="flex items-center gap-3 px-4 py-0 border-b border-purple-900/40 bg-black/60 shrink-0 relative overflow-hidden"
        style={{ height: '44px', background: 'linear-gradient(180deg, #0d0820 0%, #050508 100%)' }}>

        {/* Ambient glow behind header */}
        <div className="absolute inset-0 bg-gradient-to-r from-purple-900/10 via-transparent to-blue-900/10 pointer-events-none" />

        {/* Logo */}
        <div className="flex items-center gap-2.5 relative z-10">
          <div className="w-7 h-7 rounded flex items-center justify-center text-[14px]"
            style={{ background: 'linear-gradient(135deg, #7c3aed, #4f46e5)', boxShadow: '0 0 12px rgba(124,58,237,0.6)' }}>
            ☕
          </div>
          <div>
            <div className="font-pixel text-[10px] text-white tracking-wider"
              style={{ textShadow: '0 0 10px rgba(124,58,237,0.8)' }}>
              AI STARTUP BOARDROOM
            </div>
            <div className="font-pixel text-[7px] text-purple-400/60">Agent Society Simulator</div>
          </div>
        </div>

        {/* Center — Day / Time / Project */}
        <div className="flex items-center gap-3 mx-auto relative z-10">
          <StatBadge label="DAY" value={dayCount} color="#a78bfa" />
          <StatBadge label="TIME" value={timeStr} color="#60a5fa" />
          <StatBadge
            label="TRUST HEALTH"
            value={trustAvg !== null ? trustAvg + '%' : '—'}
            color={trustAvg >= 60 ? '#34d399' : trustAvg >= 45 ? '#fbbf24' : '#f87171'}
            dot
          />
          {currentSpeaker && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded font-pixel text-[8px] animate-glow-pulse"
              style={{
                background: speakerColor + '22',
                border: `1px solid ${speakerColor}66`,
                color: speakerColor,
                boxShadow: `0 0 10px ${speakerColor}44`,
              }}>
              <span className="animate-pulse">◉</span> {currentSpeaker}
            </div>
          )}
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-2 relative z-10">
          <StatBadge label="AGENTS" value="15" color="#34d399" />
          <StatBadge label="MSGS" value={agentMessages.length} color="#fbbf24" />
          {memoriesTotal > 0 && (
            <StatBadge label="MEMORY" value={memoriesTotal} color="#a78bfa" />
          )}
          {debateSummary && (
            <button onClick={() => setShowSummary(true)}
              className="px-3 py-1 rounded font-pixel text-[8px] transition-all duration-200 hover:scale-105"
              style={{
                background: 'linear-gradient(135deg, #7c3aed44, #4f46e544)',
                border: '1px solid #7c3aed88',
                color: '#c4b5fd',
                boxShadow: '0 0 12px rgba(124,58,237,0.3)',
              }}>
              ★ SUMMARY
            </button>
          )}
          {/* Connection indicator */}
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-red-400'}`}
            style={{ boxShadow: connected ? '0 0 6px #4ade80' : '0 0 6px #f87171' }} />
        </div>
      </header>

      {/* ── Ticker bar ─────────────────────────────────────────── */}
      <div className="h-5 bg-purple-950/30 border-b border-purple-900/20 flex items-center overflow-hidden shrink-0">
        <div className="font-pixel text-[7px] text-purple-400/50 whitespace-nowrap animate-ticker px-4">
          {currentSpeaker
            ? `◉ ${currentSpeaker} IS SPEAKING  ·  `
            : ''}
          {statusMessage}
          {memoriesTotal > 0 ? `  ·  🧠 ${memoriesTotal} DEBATES IN ORGANISATIONAL MEMORY` : ''}
          {trustAvg ? `  ·  TRUST HEALTH ${trustAvg}%` : ''}
          {agentMessages.length > 0 ? `  ·  ${agentMessages.length} MESSAGES EXCHANGED` : ''}
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
        </div>
      </div>

      {/* ── Main content ──────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0">

        {/* Left sidebar */}
        <aside className="w-44 shrink-0 border-r border-purple-900/20 flex flex-col"
          style={{ background: 'linear-gradient(180deg, #080612 0%, #050508 100%)' }}>
          <AgentList
            currentSpeaker={currentSpeaker}
            turnOrder={turnOrder}
            agentTokens={agentTokens}
          />
        </aside>

        {/* Center — Phaser canvas */}
        <main className="flex-1 min-w-0 relative p-1.5"
          style={{ background: '#050508' }}>
          {/* Vignette overlay on canvas */}
          <div className="absolute inset-0 pointer-events-none z-10 rounded-lg"
            style={{
              background: 'radial-gradient(ellipse at center, transparent 60%, rgba(5,5,8,0.7) 100%)'
            }} />
          {/* Speaking agent glow on canvas edge */}
          {currentSpeaker && (
            <div className="absolute inset-0 pointer-events-none z-10 rounded-lg transition-all duration-500"
              style={{
                boxShadow: `inset 0 0 40px ${speakerColor}33`,
                border: `1px solid ${speakerColor}44`,
              }} />
          )}
          <PhaserCanvas registerPhaserEmitter={registerPhaserEmitter} />
        </main>

        {/* Right sidebar */}
        <aside className="w-52 shrink-0 border-l border-purple-900/20 flex flex-col"
          style={{ background: 'linear-gradient(180deg, #080612 0%, #050508 100%)' }}>

          {/* Tab bar */}
          <div className="flex shrink-0 border-b border-purple-900/20">
            {[
              { key: 'trust',   label: '⬡ TRUST' },
              { key: 'feed',    label: '◎ FEED' },
            ].map(tab => (
              <button key={tab.key} onClick={() => setRightTab(tab.key)}
                className={`flex-1 py-2 font-pixel text-[7px] transition-all duration-200 ${
                  rightTab === tab.key
                    ? 'text-purple-300 border-b-2 border-purple-500 bg-purple-950/30'
                    : 'text-white/20 hover:text-white/50'
                }`}>
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex-1 min-h-0">
            {rightTab === 'trust' && (
              <div className="flex flex-col h-full">
                <div className="h-[230px] shrink-0 border-b border-purple-900/20">
                  <TrustNetwork trustMatrix={trustMatrix} />
                </div>
                <div className="flex-1 min-h-0">
                  <ActivityFeed messages={agentMessages} orgEvents={orgEvents} />
                </div>
              </div>
            )}
            {rightTab === 'feed' && (
              <ActivityFeed messages={agentMessages} orgEvents={orgEvents} />
            )}
          </div>
        </aside>
      </div>

      {/* ── Bottom ─────────────────────────────────────────────── */}
      <div className="shrink-0 border-t border-purple-900/20"
        style={{ background: 'linear-gradient(0deg, #080612 0%, #050508 100%)' }}>
        <PromptInput onSubmit={startDebate} phase={phase} />
        <StatusBar
          phase={phase}
          statusMessage={statusMessage}
          elapsedTime={elapsedTime}
          connected={connected}
          memoriesTotal={memoriesTotal || 0}
          currentSpeaker={currentSpeaker}
        />
      </div>

      {showSummary && (
        <SummaryPanel summary={debateSummary} onClose={() => setShowSummary(false)} />
      )}
    </div>
  );
}

function StatBadge({ label, value, color, dot }) {
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded font-pixel text-[7px]"
      style={{
        background: color + '11',
        border: `1px solid ${color}33`,
      }}>
      {dot && (
        <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: color }} />
      )}
      <span style={{ color: color + '99' }}>{label}</span>
      <span style={{ color }}>{value}</span>
    </div>
  );
}
