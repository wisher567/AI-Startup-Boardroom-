import { useMemo, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

/* Agent role colours */
const ROLE_COLORS = {
  CEO:                '#7C3AED',
  CTO:                '#059669',
  CFO:                '#D97706',
  CMO:                '#DB2777',
  COO:                '#475569',
  Investor:           '#2563EB',
  Legal:              '#65A30D',
  UX:                 '#E11D48',
  MarketAnalyst:      '#DC2626',
  Critic:             '#EA580C',
  Chaos:              '#7C3AED',
  'Customer Persona 1': '#0D9488',
  'Customer Persona 2': '#0891B2',
  'Industry Partner':   '#4F46E5',
};

const FALLBACK_COLOR = '#6B7280';

const AGENT_ORDER = [
  'CEO', 'CTO', 'CMO', 'COO', 'MarketAnalyst', 'CFO',
  'UX', 'Legal', 'Investor',
  'Customer Persona 1', 'Customer Persona 2',
  'Industry Partner', 'Chaos', 'Critic',
];

/* ================================================================
   Place 14 nodes evenly around a circle
   ================================================================ */
function buildNodes() {
  const cx = 360;
  const cy = 300;
  const r = 220;
  const n = AGENT_ORDER.length;

  return AGENT_ORDER.map((name, i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    const color = ROLE_COLORS[name] || FALLBACK_COLOR;

    return {
      id: name,
      type: 'default',
      position: { x, y },
      data: {
        label: name,
        color,
      },
      style: {
        background: '#1e293b',
        border: `2px solid ${color}`,
        color: '#e2e8f0',
        borderRadius: '12px',
        padding: '6px 12px',
        fontSize: '10px',
        fontWeight: 600,
        width: 'auto',
        textAlign: 'center',
      },
    };
  });
}

/* ================================================================
   Build edges from trust matrix
   Edge thickness = score × 4px   (min 1px)
   Edge opacity   = 0.3 + score × 0.5
   ================================================================ */
function buildEdges(trustMatrix) {
  const edges = [];
  const seen = new Set();

  for (const fromName of AGENT_ORDER) {
    const row = trustMatrix[fromName] || {};
    for (const toName of AGENT_ORDER) {
      if (fromName === toName) continue;
      const key = [fromName, toName].sort().join('→');
      if (seen.has(key)) continue;
      seen.add(key);

      // Average bidirectional trust if both exist
      const a = row[toName];
      const b = (trustMatrix[toName] || {})[fromName];
      let score = 0.5; // default neutral
      if (a !== undefined && b !== undefined) {
        score = (a + b) / 2;
      } else if (a !== undefined) {
        score = a;
      } else if (b !== undefined) {
        score = b;
      }

      // Clamp 0–1
      score = Math.max(0, Math.min(1, score));

      const thickness = Math.max(1, score * 4);
      const opacity = 0.3 + score * 0.5;
      const color = score < 0.3
        ? `rgba(239, 68, 68, ${opacity})`
        : score < 0.6
        ? `rgba(251, 191, 36, ${opacity})`
        : `rgba(34, 197, 94, ${opacity})`;

      edges.push({
        id: `${fromName}→${toName}`,
        source: fromName,
        target: toName,
        animated: false,
        style: {
          stroke: color,
          strokeWidth: thickness,
          opacity,
        },
      });
    }
  }

  return edges;
}

/* ================================================================
   TrustGraph — React Flow circle layout with trust-weighted edges
   ================================================================ */
export default function TrustGraph({ trustMatrix }) {
  const initialNodes = useMemo(() => buildNodes(), []);
  const initialEdges = useMemo(() => buildEdges(trustMatrix), [trustMatrix]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Rebuild edges whenever the trust matrix changes
  const updateEdges = useCallback(() => {
    setEdges(buildEdges(trustMatrix));
  }, [trustMatrix, setEdges]);

  // On trust matrix change, rebuild edges
  useMemo(() => {
    updateEdges();
  }, [trustMatrix]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="w-full h-full bg-gray-950 rounded-xl border border-gray-800 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2 border-b border-gray-800 flex items-center justify-between">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Trust Graph
        </h2>
        <div className="flex items-center gap-3 text-[10px] text-gray-500">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-0.5 bg-emerald-400 inline-block" /> High
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-0.5 bg-amber-400 inline-block" /> Mid
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-0.5 bg-red-400 inline-block" /> Low
          </span>
        </div>
      </div>

      <div style={{ width: '100%', height: 'calc(100% - 37px)' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#1e293b" gap={24} />
          <Controls className="!bg-gray-900 !border-gray-700 !rounded-lg" />
          <MiniMap
            nodeColor={(node) => node.data?.color || '#6B7280'}
            maskColor="rgba(15, 23, 42, 0.8)"
            style={{ background: '#0f172a' }}
          />
        </ReactFlow>
      </div>
    </div>
  );
}
