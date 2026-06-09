import { useEffect, useRef, useState, useCallback } from 'react';

const WS_URL = 'ws://localhost:8000/ws';

export function useDebateSocket() {
  const ws = useRef(null);
  const [connected, setConnected] = useState(false);
  const [clientId, setClientId] = useState(null);
  const [phase, setPhase] = useState('idle'); // idle|connecting|primer_running|debating|complete
  const [currentSpeaker, setCurrentSpeaker] = useState(null);
  const [agentTokens, setAgentTokens] = useState({}); // agentName -> streamed text
  const [agentMessages, setAgentMessages] = useState([]); // completed messages
  const [trustMatrix, setTrustMatrix] = useState({});
  const [trustUpdates, setTrustUpdates] = useState([]); // recent updates for animation
  const [orgEvents, setOrgEvents] = useState([]); // health events
  const [memories, setMemories] = useState([]);
  const [memoriesTotal, setMemoriesTotal] = useState(0);
  const [turnOrder, setTurnOrder] = useState([]);
  const [debateSummary, setDebateSummary] = useState(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [statusMessage, setStatusMessage] = useState('Ready');
  const timerRef = useRef(null);
  const startTimeRef = useRef(null);
  // Phaser event emitter bridge
  const phaserEmitterRef = useRef(null);

  const emit = useCallback((event) => {
    if (phaserEmitterRef.current) {
      phaserEmitterRef.current(event);
    }
  }, []);

  const registerPhaserEmitter = useCallback((fn) => {
    phaserEmitterRef.current = fn;
  }, []);

  const startTimer = () => {
    startTimeRef.current = Date.now();
    timerRef.current = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
  };

  const stopTimer = () => {
    if (timerRef.current) clearInterval(timerRef.current);
  };

  const handleEvent = useCallback((event) => {
    // Forward everything to Phaser
    emit(event);

    switch (event.type) {
      case 'registered':
        setClientId(event.client_id);
        break;

      case 'primer_running':
        setPhase('primer_running');
        setStatusMessage(event.message || 'Agents reviewing the problem...');
        startTimer();
        break;

      case 'primer_complete':
        setPhase('debating');
        setStatusMessage('Debate starting...');
        break;

      case 'memory_recall':
        setMemories(event.memories || []);
        setMemoriesTotal(event.total_stored || 0);
        setStatusMessage(
          event.total_stored > 0
            ? `${event.total_stored} past debates in memory — ${event.memories?.length || 0} recalled`
            : 'No past debates in memory yet'
        );
        break;

      case 'routing_update':
        setTurnOrder(event.turn_order || []);
        break;

      case 'agent_token':
        setCurrentSpeaker(event.agent);
        setAgentTokens(prev => ({
          ...prev,
          [event.agent]: (prev[event.agent] || '') + event.token,
        }));
        setStatusMessage(`${event.agent} is speaking...`);
        break;

      case 'agent_message':
      case 'message': {
        const agentName = event.agent || event.agent_name;
        setCurrentSpeaker(null);
        // Clear token buffer for this agent
        setAgentTokens(prev => ({ ...prev, [agentName]: '' }));
        setAgentMessages(prev => [...prev, {
          agent: agentName,
          role: event.role,
          message: event.message,
          flags: event.flags || [],
          timestamp: new Date().toLocaleTimeString(),
        }]);
        break;
      }

      case 'trust_update':
        if (event.matrix_snapshot) {
          setTrustMatrix(event.matrix_snapshot);
        }
        if (event.updates) {
          setTrustUpdates(event.updates);
        }
        break;

      case 'org_health_event':
        setOrgEvents(prev => [...prev, {
          event: event.event,
          reason: event.reason,
          recommended_action: event.recommended_action,
          timestamp: new Date().toLocaleTimeString(),
        }]);
        break;

      case 'summary':
        // Emitted just before debate_complete — store early
        setDebateSummary(event.message || event.summary);
        break;

      case 'debate_complete':
        setPhase('complete');
        setDebateSummary(event.summary);
        if (event.final_trust) setTrustMatrix(event.final_trust);
        setStatusMessage('Debate complete');
        stopTimer();
        setCurrentSpeaker(null);
        break;

      case 'tool_call':
        setAgentMessages(prev => [...prev, {
          ...event,
          timestamp: new Date().toLocaleTimeString(),
          kind: 'tool_call',
        }]);
        setStatusMessage(`${event.agent} → searching ${event.tool}...`);
        break;

      case 'tool_result':
        setAgentMessages(prev => [...prev, {
          ...event,
          timestamp: new Date().toLocaleTimeString(),
          kind: 'tool_result',
        }]);
        break;

      case 'debate_error':
        setPhase('idle');
        setStatusMessage(`Error: ${event.error}`);
        stopTimer();
        break;

      case 'learning_started':
        setStatusMessage('Agents processing lessons learned...');
        break;

      case 'learning_complete':
        setStatusMessage(`${event.message}`);
        // Update memories total since a new debate was stored
        setMemoriesTotal(prev => prev + 1);
        setAgentMessages(prev => [...prev, {
          ...event,
          timestamp: new Date().toLocaleTimeString(),
          kind: 'learning_complete',
        }]);
        break;

      default:
        break;
    }
  }, [emit]);

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return;
    setPhase('connecting');
    setStatusMessage('Connecting...');

    const socket = new WebSocket(WS_URL);
    ws.current = socket;

    socket.onopen = () => {
      setConnected(true);
      // Register with the backend so it can route events to this client
      const id = crypto.randomUUID();
      setClientId(id);
      socket.send(JSON.stringify({ action: 'register', client_id: id }));
      setStatusMessage('Connected');
    };

    ws.current.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        handleEvent(event);
      } catch (err) {
        console.error('WS parse error', err);
      }
    };

    ws.current.onclose = () => {
      setConnected(false);
      setPhase('idle');
      setStatusMessage('Disconnected');
    };

    ws.current.onerror = () => {
      setStatusMessage('Connection error');
    };
  }, [handleEvent]);

  const startDebate = useCallback(async (prompt) => {
    // Ensure we're connected and registered before firing
    if (!connected) connect();

    // Wait up to 5s for clientId to be set (WS open + register)
    const deadline = Date.now() + 5000;
    let cid = null;
    while (Date.now() < deadline) {
      // re-read from the ref to avoid stale closure
      if (ws.current?.readyState === WebSocket.OPEN && clientId) {
        cid = clientId;
        break;
      }
      await new Promise(r => setTimeout(r, 100));
    }

    if (!cid) {
      setStatusMessage('Failed to connect — try again');
      return;
    }

    setAgentMessages([]);
    setAgentTokens({});
    setOrgEvents([]);
    setDebateSummary(null);
    setMemories([]);
    setMemoriesTotal(0);
    setElapsedTime(0);

    try {
      // Use the Vite proxy path (/debate → localhost:8000)
      await fetch('/debate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, client_id: cid }),
      });
    } catch (err) {
      setStatusMessage('Failed to start debate');
    }
  }, [connected, connect, clientId]);

  useEffect(() => {
    connect();
    return () => {
      ws.current?.close();
      stopTimer();
    };
  }, []);

  return {
    connected, clientId, phase, currentSpeaker,
    agentTokens, agentMessages, trustMatrix, trustUpdates,
    orgEvents, memories, memoriesTotal, turnOrder, debateSummary,
    elapsedTime, statusMessage,
    startDebate, registerPhaserEmitter,
  };
}
