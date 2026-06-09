import Phaser from 'phaser';

const W = 800;
const H = 500;

// Agent definitions: position, hat color, label
const AGENT_DEFS = {
  CEO: { x: 340, y: 150, color: 0xe8593c, label: 'CEO' },
  CTO: { x: 460, y: 150, color: 0x1d9e75, label: 'CTO' },
  CFO: { x: 220, y: 300, color: 0xba7517, label: 'CFO' },
  CMO: { x: 580, y: 300, color: 0xd4537e, label: 'CMO' },
  Investor: { x: 400, y: 380, color: 0x9b59b6, label: 'INV' },
  Critic: { x: 160, y: 180, color: 0x7f8c8d, label: 'CRT' },
  Chaos: { x: 640, y: 180, color: 0xe67e22, label: 'CHS' },
};

export class BoardroomScene extends Phaser.Scene {
  constructor() {
    super('Boardroom');
  }

  create() {
    // ── Floor ──────────────────────────────────────────
    this.add.rectangle(0, 0, W, H, 0x1a1a2e).setOrigin(0);
    this._drawTileFloor();

    // ── Walls ──────────────────────────────────────────
    // Top wall trim
    this.add.rectangle(0, 0, W, 20, 0x2d2d44).setOrigin(0);
    // Columns
    this.add.rectangle(20, 20, 12, H - 20, 0x2d2d44).setOrigin(0);
    this.add.rectangle(W - 32, 20, 12, H - 20, 0x2d2d44).setOrigin(0);

    // ── Table ──────────────────────────────────────────
    this.add.rectangle(200, 160, 400, 220, 0x16213e).setOrigin(0);
    this.add.rectangle(205, 165, 390, 210, 0x1a1a3e).setOrigin(0);
    // Table surface highlights
    this.add.rectangle(210, 170, 380, 6, 0x252550).setOrigin(0);

    // ── Agents ─────────────────────────────────────────
    this.agents = {};
    for (const [name, def] of Object.entries(AGENT_DEFS)) {
      this.agents[name] = this._createAgent(def.x, def.y, def.color, def.label);
    }

    // ── Speech bubble pool ─────────────────────────────
    this.activeBubbles = [];

    // ── Dynamic persona slots ──────────────────────────
    this._personaColors = [
      0xfd79a8, 0xe17055, 0x6c5ce7, 0x00cec9,
    ];
    this._personaSlots = [
      { x: 100, y: 420 },   // bottom left
      { x: 260, y: 420 },   // bottom left-center
      { x: 540, y: 420 },   // bottom right-center
      { x: 700, y: 420 },   // bottom right
    ];
    this._personaIndex = 0;
    this._personaCount = 0;
  }

  // ----------------------------------------------------------------
  // Drawing helpers
  // ----------------------------------------------------------------

  _drawTileFloor() {
    const g = this.add.graphics();
    g.lineStyle(1, 0x252545, 0.3);
    for (let x = 0; x < W; x += 40) {
      g.lineBetween(x, 20, x, H);
    }
    for (let y = 20; y < H; y += 40) {
      g.lineBetween(0, y, W, y);
    }
  }

  _createAgent(x, y, hatColor, label) {
    const g = this.add.graphics();

    // Body (dark suit)
    g.fillStyle(0x2c3e50);
    g.fillRect(x - 7, y - 4, 14, 16);

    // Head
    g.fillStyle(0xf5cba7);
    g.fillRect(x - 4, y - 12, 8, 8);

    // Eyes
    g.fillStyle(0x000000);
    g.fillRect(x - 2, y - 10, 2, 2);
    g.fillRect(x + 2, y - 10, 2, 2);

    // Hat
    g.fillStyle(hatColor);
    g.fillRect(x - 6, y - 16, 12, 4);

    // Label below
    const text = this.add.text(x, y + 16, label, {
      fontSize: '8px',
      fontFamily: 'monospace',
      color: '#aaa',
    }).setOrigin(0.5, 0);

    return { x, y, graphics: g, label: text };
  }

  // ----------------------------------------------------------------
  // Public API — called from React
  // ----------------------------------------------------------------

  addDynamicAgent(name, color) {
    // Don't add duplicates
    if (this.agents[name]) return;

    const slot = this._personaSlots[this._personaIndex % this._personaSlots.length];
    const hatColor = color || this._personaColors[this._personaIndex % this._personaColors.length];
    const label = name.length > 6 ? name.slice(0, 5) + '…' : name;

    this.agents[name] = this._createAgent(slot.x, slot.y, hatColor, label);
    this._personaIndex++;
    this._personaCount++;
  }

  showBubble(agentName, message) {
    const agent = this.agents[agentName];
    if (!agent) return;

    // Kill any existing bubble for this agent
    this._clearBubbles(agentName);

    const truncated = message.length > 60 ? message.slice(0, 57) + '...' : message;
    const bubbleW = Math.max(truncated.length * 4 + 16, 80);
    const bubbleH = 28;
    const bx = agent.x - bubbleW / 2;
    const by = agent.y - 50;

    // Bubble background
    const bg = this.add.graphics();
    bg.fillStyle(0xffffff, 0.95);
    bg.fillRoundedRect(bx, by, bubbleW, bubbleH, 4);
    // Tail
    bg.fillStyle(0xffffff, 0.95);
    bg.fillTriangle(
      agent.x - 4, by + bubbleH,
      agent.x + 4, by + bubbleH,
      agent.x, by + bubbleH + 6,
    );

    // Text
    const txt = this.add.text(bx + 8, by + 6, truncated, {
      fontSize: '9px',
      fontFamily: 'monospace',
      color: '#1a1a2e',
      wordWrap: { width: bubbleW - 16 },
    });

    // Highlight the speaking agent
    agent.graphics.clear();
    this._drawAgentSprite(agent, true);

    // Auto-destroy after 3.5s
    const timer = this.time.delayedCall(3500, () => {
      bg.destroy();
      txt.destroy();
      agent.graphics.clear();
      this._drawAgentSprite(agent, false);
    });

    this.activeBubbles.push({ agentName, bg, txt, timer });
  }

  _clearBubbles(agentName) {
    this.activeBubbles = this.activeBubbles.filter((b) => {
      if (b.agentName === agentName) {
        b.bg.destroy();
        b.txt.destroy();
        b.timer.destroy();
        return false;
      }
      return true;
    });
  }

  _drawAgentSprite(agent, highlight) {
    const g = agent.graphics;
    const x = agent.x;
    const y = agent.y;

    // Find the agent definition
    const def = Object.values(AGENT_DEFS).find(
      (d) => d.x === x && d.y === y,
    );
    const hatColor = def ? def.color : 0x888888;

    // Body
    g.fillStyle(highlight ? 0x4a6fa5 : 0x2c3e50);
    g.fillRect(x - 7, y - 4, 14, 16);

    // Highlight glow
    if (highlight) {
      g.lineStyle(2, 0xffd700, 0.8);
      g.strokeRect(x - 8, y - 17, 16, 33);
    }

    // Head
    g.fillStyle(0xf5cba7);
    g.fillRect(x - 4, y - 12, 8, 8);

    // Eyes
    g.fillStyle(0x000000);
    g.fillRect(x - 2, y - 10, 2, 2);
    g.fillRect(x + 2, y - 10, 2, 2);

    // Hat
    g.fillStyle(hatColor);
    g.fillRect(x - 6, y - 16, 12, 4);
  }
}
