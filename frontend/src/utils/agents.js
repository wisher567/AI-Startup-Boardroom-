export const AGENTS = {
  CEO:              { color: '#7C3AED', room: 'executive', sprite: 'ceo_sprite',            abbr: 'CE', label: 'Vision & Leadership' },
  CTO:              { color: '#059669', room: 'executive', sprite: 'cto_sprite',            abbr: 'CT', label: 'Tech & Architecture' },
  CFO:              { color: '#D97706', room: 'executive', sprite: 'cfo_sprite',            abbr: 'CF', label: 'Finance & Risk' },
  CMO:              { color: '#DB2777', room: 'executive', sprite: 'cmo_sprite',            abbr: 'CM', label: 'Marketing & Growth' },
  COO:              { color: '#475569', room: 'executive', sprite: 'coo_sprite',            abbr: 'CO', label: 'Operations & Exec.' },
  Investor:         { color: '#2563EB', room: 'executive', sprite: 'investor_sprite',       abbr: 'IV', label: 'Funding & Strategy' },
  Legal:            { color: '#65A30D', room: 'specialist', sprite: 'legal_sprite',         abbr: 'LG', label: 'Law & Compliance' },
  'UX Designer':    { color: '#E11D48', room: 'specialist', sprite: 'ux_sprite',            abbr: 'UX', label: 'User Experience' },
  'Market Analyst': { color: '#DC2626', room: 'specialist', sprite: 'market_analyst_sprite',abbr: 'MA', label: 'Market & Trends' },
  Critic:           { color: '#EA580C', room: 'intelligence', sprite: 'critic_sprite',      abbr: 'CR', label: 'Challenge & Critique' },
  'Chaos Agent':    { color: '#7C3AED', room: 'intelligence', sprite: 'chaos_sprite',       abbr: 'CA', label: 'Disrupt & Innovate' },
  'Customer Persona 1': { color: '#0D9488', room: 'users', sprite: 'persona1_sprite',       abbr: 'P1', label: 'Primary User' },
  'Customer Persona 2': { color: '#0891B2', room: 'users', sprite: 'persona2_sprite',       abbr: 'P2', label: 'Secondary User' },
  'Industry Partner':   { color: '#4F46E5', room: 'users', sprite: 'partner_sprite',        abbr: 'IP', label: 'B2B Partner' },
};

export const AGENT_NAMES = Object.keys(AGENTS);

// Room layout — which agents live in which room scene
export const ROOMS = {
  executive:    { label: 'EXECUTIVE FLOOR', agents: ['CEO','CTO','CFO','CMO','COO','Investor'] },
  specialist:   { label: 'SPECIALIST OFFICES', agents: ['Legal','UX Designer','Market Analyst'] },
  intelligence: { label: 'INTELLIGENCE LAYER', agents: ['Critic','Chaos Agent'] },
  users:        { label: 'USER LAB', agents: ['Customer Persona 1','Customer Persona 2','Industry Partner'] },
};

export const getAgentColor = (name) => AGENTS[name]?.color || '#64748b';
export const getAgentSprite = (name) => AGENTS[name]?.sprite || null;
export const getAgentAbbr = (name) => AGENTS[name]?.abbr || name.slice(0,2).toUpperCase();
