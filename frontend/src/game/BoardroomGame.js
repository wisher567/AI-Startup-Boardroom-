import Phaser from 'phaser';
import { AGENTS, ROOMS } from '../utils/agents';

// ─── Sprite frame indices ─────────────────────────────────────────────────
const FRAME_IDLE  = 0;
const FRAME_TALK  = 1;
const FRAME_WALK  = 2;

const FRAME_W = 160;
const FRAME_H = 200;

// Scale per room — smaller rooms need smaller sprites
const ROOM_SCALES = {
  executive:    0.38,
  specialist:   0.28,
  intelligence: 0.30,
  users:        0.30,
  lounge:       0.28,
  meeting:      0.25,
  archive:      0.22,
};

// ─── Room colours ─────────────────────────────────────────────────────────
const ROOM_COLORS = {
  executive:    0x1a1035,
  specialist:   0x0d2318,
  intelligence: 0x1a0d0d,
  users:        0x0d1a2e,
  lounge:       0x1a1200,
  meeting:      0x0d1a0d,
  archive:      0x12121a,
};

const FLOOR_COLORS = {
  executive:    0x2d1f5e,
  specialist:   0x1a3d28,
  intelligence: 0x3d1a1a,
  users:        0x1a2d4f,
  lounge:       0x3d2e00,
  meeting:      0x1a3d1a,
  archive:      0x1e1e2e,
};

// ─── Room layout definitions ──────────────────────────────────────────────
// Each room: { x, y, w, h, agents: [{name, px, py}] }
const LAYOUT = {
  executive: {
    x: 10, y: 10, w: 560, h: 340,
    label: 'EXECUTIVE FLOOR',
    agents: [
      { name: 'CEO',      px: 0.20, py: 0.45 },
      { name: 'CTO',      px: 0.38, py: 0.55 },
      { name: 'CFO',      px: 0.55, py: 0.45 },
      { name: 'CMO',      px: 0.72, py: 0.60 },
      { name: 'COO',      px: 0.85, py: 0.45 },
      { name: 'Investor', px: 0.50, py: 0.80 },
    ],
  },
  specialist: {
    x: 580, y: 10, w: 270, h: 160,
    label: 'SPECIALIST OFFICES',
    agents: [
      { name: 'Legal',         px: 0.20, py: 0.55 },
      { name: 'UX Designer',   px: 0.50, py: 0.55 },
      { name: 'Market Analyst',px: 0.80, py: 0.55 },
    ],
  },
  intelligence: {
    x: 580, y: 180, w: 270, h: 170,
    label: 'INTELLIGENCE LAYER',
    agents: [
      { name: 'Critic',      px: 0.30, py: 0.60 },
      { name: 'Chaos Agent', px: 0.70, py: 0.60 },
    ],
  },
  users: {
    x: 10, y: 360, w: 410, h: 160,
    label: 'USER LAB',
    agents: [
      { name: 'Customer Persona 1', px: 0.20, py: 0.60 },
      { name: 'Customer Persona 2', px: 0.50, py: 0.60 },
      { name: 'Industry Partner',   px: 0.80, py: 0.60 },
    ],
  },
  lounge: {
    x: 430, y: 360, w: 185, h: 160,
    label: 'LOUNGE',
    agents: [],
  },
  meeting: {
    x: 625, y: 360, w: 110, h: 160,
    label: 'MEETING HALL',
    agents: [],
  },
  archive: {
    x: 745, y: 360, w: 105, h: 160,
    label: 'MEMORY ARCHIVE',
    agents: [],
  },
};

// ─── Main scene ───────────────────────────────────────────────────────────
class BoardroomScene extends Phaser.Scene {
  constructor() {
    super({ key: 'BoardroomScene' });
    this.agentSprites  = {};   // name -> Phaser sprite
    this.agentLabels   = {};   // name -> text
    this.speechBubbles = {};   // name -> { bg, text, timer }
    this.tokenBuffers  = {};   // name -> string
    this.activeSpeaker = null;
    this.eventQueue    = [];
  }

  preload() {
    Object.entries(AGENTS).forEach(([name, cfg]) => {
      this.load.spritesheet(cfg.sprite, `/assets/sprites/${cfg.sprite}.png`, {
        frameWidth: FRAME_W,
        frameHeight: FRAME_H,
      });
    });
  }

  create() {
    this._drawRooms();
    this._createAgents();
    this._createAnimations();

    // Listen for events forwarded from React
    this.game.events.on('ws_event', this._handleWsEvent, this);
  }

  // ── Draw all room backgrounds ──────────────────────────────────────────
  _drawRooms() {
    // Draw gap/background first
    this.add.rectangle(0, 0, 860, 530, 0x020205).setOrigin(0);

    Object.entries(LAYOUT).forEach(([key, room]) => {
      this._drawRoom(key, room);
      this._drawFurniture(key, room);
      this._drawRoomLabel(key, room);
    });
  }

  _drawRoom(key, room) {
    const g = this.add.graphics();
    const bg    = ROOM_COLORS[key]  || 0x111111;
    const floor = FLOOR_COLORS[key] || 0x222222;

    // Main room background
    g.fillStyle(bg, 1);
    g.fillRect(room.x, room.y, room.w, room.h);

    // Ceiling gradient (lighter at top)
    for (let i = 0; i < 8; i++) {
      g.fillStyle(0xffffff, 0.012 * (8 - i));
      g.fillRect(room.x, room.y + i * 4, room.w, 4);
    }

    // Floor (bottom 32%) — checkerboard pattern
    const floorH = Math.floor(room.h * 0.32);
    const floorY = room.y + room.h - floorH;
    g.fillStyle(floor, 1);
    g.fillRect(room.x, floorY, room.w, floorH);

    // Checkerboard tiles on floor
    const tileSize = 16;
    for (let tx = 0; tx < Math.ceil(room.w / tileSize); tx++) {
      for (let ty = 0; ty < Math.ceil(floorH / tileSize); ty++) {
        if ((tx + ty) % 2 === 0) {
          g.fillStyle(0xffffff, 0.025);
          g.fillRect(
            room.x + tx * tileSize,
            floorY + ty * tileSize,
            Math.min(tileSize, room.w - tx * tileSize),
            Math.min(tileSize, floorH - ty * tileSize)
          );
        }
      }
    }

    // Floor line divider
    g.lineStyle(1, 0xffffff, 0.08);
    g.lineBetween(room.x, floorY, room.x + room.w, floorY);

    // Wall shadow on left edge
    for (let i = 0; i < 6; i++) {
      g.fillStyle(0x000000, 0.06 * (6 - i));
      g.fillRect(room.x + i, room.y, 1, room.h);
    }

    // Outer border with glow color per room
    const borderColors = {
      executive:    0x5b21b6,
      specialist:   0x065f46,
      intelligence: 0x7f1d1d,
      users:        0x1e3a5f,
      lounge:       0x78350f,
      meeting:      0x14532d,
      archive:      0x1e1b4b,
    };
    const bc = borderColors[key] || 0x333333;
    g.lineStyle(1.5, bc, 0.8);
    g.strokeRect(room.x, room.y, room.w, room.h);

    // Inner highlight (top + left edges)
    g.lineStyle(1, 0xffffff, 0.06);
    g.lineBetween(room.x + 1, room.y + 1, room.x + room.w - 1, room.y + 1);
    g.lineBetween(room.x + 1, room.y + 1, room.x + 1, room.y + room.h - 1);
  }

  _drawRoomLabel(key, room) {
    const labelColors = {
      executive:    '#c4b5fd',
      specialist:   '#6ee7b7',
      intelligence: '#fca5a5',
      users:        '#93c5fd',
      lounge:       '#fcd34d',
      meeting:      '#86efac',
      archive:      '#a5b4fc',
    };
    const color = labelColors[key] || '#ffffff';

    // Label background pill
    const label = LAYOUT[key].label;
    const lw = label.length * 6.5 + 16;
    const g = this.add.graphics();
    g.fillStyle(0x000000, 0.6);
    g.fillRoundedRect(room.x + 6, room.y + 5, lw, 14, 3);
    g.lineStyle(1, parseInt(color.replace('#','0x')), 0.4);
    g.strokeRoundedRect(room.x + 6, room.y + 5, lw, 14, 3);

    this.add.text(room.x + 14, room.y + 8, label, {
      fontFamily: '"Press Start 2P", monospace',
      fontSize: '5px',
      color,
    }).setAlpha(0.9).setDepth(5);
  }

  _drawFurniture(key, room) {
    const g = this.add.graphics();

    if (key === 'executive') {
      // Large conference table with 3D effect
      g.fillStyle(0x2d1b5e, 1);
      g.fillRect(room.x + 110, room.y + 148, 340, 80);
      // Table top highlight
      g.fillStyle(0x4a2d8a, 1);
      g.fillRect(room.x + 110, room.y + 148, 340, 12);
      // Table shadow
      g.fillStyle(0x000000, 0.3);
      g.fillRect(room.x + 113, room.y + 228, 340, 5);
      g.lineStyle(1, 0x7c5abf, 0.7);
      g.strokeRect(room.x + 110, room.y + 148, 340, 80);

      // Chairs top row
      for (let i = 0; i < 6; i++) {
        g.fillStyle(0x1e1440, 1);
        g.fillRect(room.x + 118 + i * 53, room.y + 133, 26, 13);
        g.lineStyle(1, 0x4a2d8a, 0.6);
        g.strokeRect(room.x + 118 + i * 53, room.y + 133, 26, 13);
      }
      // Chairs bottom row
      for (let i = 0; i < 6; i++) {
        g.fillStyle(0x1e1440, 1);
        g.fillRect(room.x + 118 + i * 53, room.y + 230, 26, 13);
        g.lineStyle(1, 0x4a2d8a, 0.6);
        g.strokeRect(room.x + 118 + i * 53, room.y + 230, 26, 13);
      }

      // Multiple windows with city glow
      const windows = [[room.x+60, room.y+18],[room.x+210,room.y+18],[room.x+340,room.y+18],[room.x+460,room.y+18]];
      windows.forEach(([wx,wy]) => {
        // Sky gradient
        g.fillStyle(0x0a1628, 1);
        g.fillRect(wx, wy, 70, 50);
        // City lights
        const cityColors = [0x7c3aed, 0x2563eb, 0x059669, 0xd97706];
        for (let b = 0; b < 6; b++) {
          g.fillStyle(cityColors[b % cityColors.length], 0.6);
          g.fillRect(wx + 5 + b * 10, wy + 20 + (b%3)*8, 6, 15 - (b%3)*4);
        }
        // Window glow
        g.fillStyle(0x4a8abf, 0.15);
        g.fillRect(wx, wy, 70, 50);
        g.lineStyle(1, 0x4a8abf, 0.5);
        g.strokeRect(wx, wy, 70, 50);
        g.lineStyle(1, 0x4a8abf, 0.3);
        g.lineBetween(wx+35, wy, wx+35, wy+50);
        g.lineBetween(wx, wy+25, wx+70, wy+25);
      });

      // Whiteboard
      g.fillStyle(0xf0f0f0, 0.9);
      g.fillRect(room.x + 490, room.y + 18, 60, 40);
      g.lineStyle(1, 0xcccccc, 0.8);
      g.strokeRect(room.x + 490, room.y + 18, 60, 40);
      // Chart lines on whiteboard
      g.lineStyle(1, 0x2563eb, 0.5);
      g.lineBetween(room.x+496, room.y+48, room.x+506, room.y+38);
      g.lineBetween(room.x+506, room.y+38, room.x+516, room.y+42);
      g.lineBetween(room.x+516, room.y+42, room.x+526, room.y+30);
      g.lineBetween(room.x+526, room.y+30, room.x+536, room.y+25);

      // Plants
      g.fillStyle(0x065f46, 1);
      g.fillCircle(room.x + 28, room.y + 45, 14);
      g.fillCircle(room.x + 540, room.y + 45, 12);
      g.fillStyle(0x059669, 0.8);
      g.fillCircle(room.x + 28, room.y + 38, 10);
      g.fillCircle(room.x + 540, room.y + 38, 9);
      // Pots
      g.fillStyle(0x78350f, 1);
      g.fillRect(room.x + 18, room.y + 56, 20, 14);
      g.fillRect(room.x + 531, room.y + 54, 18, 14);
    }

    if (key === 'specialist') {
      // Three individual desks with monitors
      const deskColors = [0x065f46, 0x1e3a5f, 0x4c1d95];
      for (let i = 0; i < 3; i++) {
        const dx = room.x + 16 + i * 82;
        // Desk
        g.fillStyle(deskColors[i], 1);
        g.fillRect(dx, room.y + 94, 64, 28);
        g.fillStyle(0xffffff, 0.08);
        g.fillRect(dx, room.y + 94, 64, 5); // desk highlight
        g.lineStyle(1, 0xffffff, 0.15);
        g.strokeRect(dx, room.y + 94, 64, 28);
        // Monitor
        g.fillStyle(0x050508, 1);
        g.fillRect(dx + 10, room.y + 70, 44, 26);
        // Screen glow
        const screenColors = [0x059669, 0x2563eb, 0x7c3aed];
        g.fillStyle(screenColors[i], 0.2);
        g.fillRect(dx + 12, room.y + 72, 40, 22);
        // Screen content lines
        g.lineStyle(1, screenColors[i], 0.4);
        for (let l = 0; l < 3; l++) {
          g.lineBetween(dx+14, room.y+76+l*6, dx+42, room.y+76+l*6);
        }
        g.lineStyle(1, 0x444444, 0.6);
        g.strokeRect(dx + 10, room.y + 70, 44, 26);
        // Monitor stand
        g.fillStyle(0x333333, 1);
        g.fillRect(dx + 28, room.y + 96, 8, 4);
      }
    }

    if (key === 'intelligence') {
      // Hexagonal console
      const cx = room.x + 135, cy = room.y + 95;
      g.fillStyle(0x3d0d0d, 1);
      g.fillRect(room.x + 40, room.y + 78, 190, 52);
      // Console screen panels
      const panelColors = [0x7f1d1d, 0x1e3a5f, 0x4c1d95];
      for (let p = 0; p < 3; p++) {
        g.fillStyle(panelColors[p], 0.6);
        g.fillRect(room.x + 48 + p*62, room.y + 84, 54, 32);
        g.lineStyle(1, 0xffffff, 0.1);
        g.strokeRect(room.x + 48 + p*62, room.y + 84, 54, 32);
        // Data lines
        g.lineStyle(1, 0xff4444, 0.3);
        for (let l = 0; l < 4; l++) {
          const len = 20 + Math.random() * 30;
          g.lineBetween(room.x+52+p*62, room.y+88+l*7, room.x+52+p*62+len, room.y+88+l*7);
        }
      }
      g.lineStyle(1, 0x8b2020, 0.8);
      g.strokeRect(room.x + 40, room.y + 78, 190, 52);

      // Pulsing warning light
      g.fillStyle(0xff4444, 1);
      g.fillCircle(room.x + 220, room.y + 35, 7);
      g.fillStyle(0xff6666, 0.4);
      g.fillCircle(room.x + 220, room.y + 35, 12);

      // Server rack on right
      g.fillStyle(0x1a0505, 1);
      g.fillRect(room.x + 230, room.y + 55, 30, 90);
      for (let r = 0; r < 5; r++) {
        g.fillStyle(r%2===0 ? 0x2a0808 : 0x1a0505, 1);
        g.fillRect(room.x + 232, room.y + 58 + r*17, 26, 14);
        g.fillStyle(0x00ff88, 0.7);
        g.fillRect(room.x + 253, room.y + 63 + r*17, 4, 4);
      }
    }

    if (key === 'users') {
      // Modern couch
      g.fillStyle(0x1e3a5f, 1);
      g.fillRect(room.x + 15, room.y + 95, 160, 38);
      g.fillStyle(0x2d4f7a, 1);
      g.fillRect(room.x + 15, room.y + 95, 160, 10); // cushion highlight
      g.fillStyle(0x152d4f, 1);
      g.fillRect(room.x + 15, room.y + 95, 12, 38); // arm left
      g.fillRect(room.x + 163, room.y + 95, 12, 38); // arm right
      g.lineStyle(1, 0x3b6ea0, 0.7);
      g.strokeRect(room.x + 15, room.y + 95, 160, 38);

      // Coffee table with laptop
      g.fillStyle(0x0d1a2e, 1);
      g.fillRect(room.x + 200, room.y + 102, 85, 25);
      g.fillStyle(0x1a2e44, 0.5);
      g.fillRect(room.x + 200, room.y + 102, 85, 4);
      g.lineStyle(1, 0x1e3a5f, 0.6);
      g.strokeRect(room.x + 200, room.y + 102, 85, 25);
      // Laptop on table
      g.fillStyle(0x333333, 1);
      g.fillRect(room.x + 220, room.y + 90, 40, 14);
      g.fillStyle(0x2563eb, 0.3);
      g.fillRect(room.x + 222, room.y + 91, 36, 11);
      g.lineStyle(1, 0x555555, 0.6);
      g.strokeRect(room.x + 220, room.y + 90, 40, 14);
      // Plant in corner
      g.fillStyle(0x065f46, 1);
      g.fillCircle(room.x + 375, room.y + 60, 16);
      g.fillStyle(0x059669, 0.7);
      g.fillCircle(room.x + 375, room.y + 52, 11);
      g.fillStyle(0x78350f, 1);
      g.fillRect(room.x + 367, room.y + 72, 16, 16);
    }

    if (key === 'lounge') {
      // Comfortable chairs
      g.fillStyle(0x451a03, 1);
      g.fillRect(room.x + 12, room.y + 88, 50, 38);
      g.fillStyle(0x78350f, 0.8);
      g.fillRect(room.x + 12, room.y + 88, 50, 10);
      g.lineStyle(1, 0x92400e, 0.7);
      g.strokeRect(room.x + 12, room.y + 88, 50, 38);

      g.fillStyle(0x451a03, 1);
      g.fillRect(room.x + 120, room.y + 88, 50, 38);
      g.fillStyle(0x78350f, 0.8);
      g.fillRect(room.x + 120, room.y + 88, 50, 10);
      g.lineStyle(1, 0x92400e, 0.7);
      g.strokeRect(room.x + 120, room.y + 88, 50, 38);

      // Small table with coffee
      g.fillStyle(0x3d2000, 1);
      g.fillRect(room.x + 70, room.y + 100, 40, 20);
      g.lineStyle(1, 0x78350f, 0.6);
      g.strokeRect(room.x + 70, room.y + 100, 40, 20);
      // Coffee cups
      g.fillStyle(0x78350f, 1);
      g.fillCircle(room.x + 83, room.y + 108, 5);
      g.fillCircle(room.x + 97, room.y + 108, 5);

      // TV on wall
      g.fillStyle(0x111111, 1);
      g.fillRect(room.x + 40, room.y + 20, 100, 55);
      g.fillStyle(0x1a1a2e, 0.8);
      g.fillRect(room.x + 43, room.y + 23, 94, 49);
      g.lineStyle(1, 0x333333, 0.8);
      g.strokeRect(room.x + 40, room.y + 20, 100, 55);
    }

    if (key === 'archive') {
      // Full bookshelves
      const bookColors = [0x7c3aed, 0x059669, 0xd97706, 0xdb2777, 0x2563eb, 0xea580c, 0x0891b2];
      for (let row = 0; row < 4; row++) {
        g.fillStyle(0x1e1b4b, 1);
        g.fillRect(room.x + 6, room.y + 18 + row * 30, 93, 22);
        g.lineStyle(1, 0x312e81, 0.6);
        g.strokeRect(room.x + 6, room.y + 18 + row * 30, 93, 22);
        // Books
        for (let b = 0; b < 6; b++) {
          const bw = 11 + (b%2)*3;
          g.fillStyle(bookColors[(row*6+b) % bookColors.length], 0.85);
          g.fillRect(room.x + 8 + b*15, room.y + 20 + row*30, bw, 17);
          // Book spine highlight
          g.fillStyle(0xffffff, 0.1);
          g.fillRect(room.x + 8 + b*15, room.y + 20 + row*30, 2, 17);
        }
      }

      // Glowing data orb
      g.fillStyle(0x7c3aed, 0.15);
      g.fillCircle(room.x + 52, room.y + 140, 22);
      g.fillStyle(0x7c3aed, 0.25);
      g.fillCircle(room.x + 52, room.y + 140, 15);
      g.fillStyle(0xa78bfa, 0.6);
      g.fillCircle(room.x + 52, room.y + 140, 8);
    }

    if (key === 'meeting') {
      // Round table with 3D
      g.fillStyle(0x14532d, 1);
      g.fillCircle(room.x + 55, room.y + 88, 36);
      g.fillStyle(0x166534, 1);
      g.fillCircle(room.x + 55, room.y + 85, 34);
      g.fillStyle(0x15803d, 0.5);
      g.fillCircle(room.x + 52, room.y + 82, 20);
      g.lineStyle(1.5, 0x16a34a, 0.7);
      g.strokeCircle(room.x + 55, room.y + 85, 34);

      // Chairs around table
      const chairAngles = [0, 60, 120, 180, 240, 300];
      chairAngles.forEach(angle => {
        const rad = angle * Math.PI / 180;
        const cx2 = room.x + 55 + Math.cos(rad) * 46;
        const cy2 = room.y + 85 + Math.sin(rad) * 40;
        g.fillStyle(0x052e16, 1);
        g.fillRect(cx2 - 8, cy2 - 6, 16, 12);
        g.lineStyle(1, 0x166534, 0.5);
        g.strokeRect(cx2 - 8, cy2 - 6, 16, 12);
      });
    }
  }

  // ── Create agent sprites ───────────────────────────────────────────────
  _createAgents() {
    Object.entries(LAYOUT).forEach(([roomKey, room]) => {
      const scale = ROOM_SCALES[roomKey] || 0.30;
      const spriteH = FRAME_H * scale;

      room.agents.forEach(({ name, px, py }) => {
        const cfg = AGENTS[name];
        if (!cfg) return;

        // x = horizontal position within room
        // y = floor line position — sprite origin is bottom-center so feet land here
        const x = room.x + room.w * px;
        // py is fraction down the room; floor line is at bottom 30% of room
        const floorY = room.y + room.h * 0.72;
        const y = room.y + room.h * Math.min(py, 0.78);

        const sprite = this.add.sprite(x, y, cfg.sprite, FRAME_IDLE)
          .setScale(scale)
          .setOrigin(0.5, 1)   // anchor = bottom-center so feet touch floor
          .setDepth(10 + py * 10); // deeper py = higher depth (in front)

        // Name label directly below feet
        const label = this.add.text(x, y + 3, name, {
          fontFamily: '"Press Start 2P", monospace',
          fontSize: '5px',
          color: cfg.color,
          backgroundColor: '#000000bb',
          padding: { x: 3, y: 2 },
        }).setOrigin(0.5, 0).setDepth(20);

        this.agentSprites[name] = sprite;
        this.agentLabels[name]  = label;
        this.tokenBuffers[name] = '';
      });
    });
  }

  // ── Animations ────────────────────────────────────────────────────────
  _createAnimations() {
    Object.entries(AGENTS).forEach(([name, cfg]) => {
      const key = cfg.sprite;

      if (!this.anims.exists(`${key}_idle`)) {
        this.anims.create({
          key: `${key}_idle`,
          frames: [{ key, frame: FRAME_IDLE }],
          frameRate: 1,
          repeat: -1,
        });
      }
      if (!this.anims.exists(`${key}_talk`)) {
        this.anims.create({
          key: `${key}_talk`,
          frames: this.anims.generateFrameNumbers(key, { frames: [FRAME_IDLE, FRAME_TALK] }),
          frameRate: 4,
          repeat: -1,
        });
      }
      if (!this.anims.exists(`${key}_walk`)) {
        this.anims.create({
          key: `${key}_walk`,
          frames: this.anims.generateFrameNumbers(key, { frames: [FRAME_IDLE, FRAME_WALK] }),
          frameRate: 6,
          repeat: -1,
        });
      }
    });
  }

  // ── WebSocket event handler ────────────────────────────────────────────
  _handleWsEvent(event) {
    switch (event.type) {
      case 'agent_token':
        this._onAgentToken(event.agent, event.token);
        break;
      case 'agent_message':
      case 'message':
        this._onAgentComplete(event.agent || event.agent_name);
        break;
      case 'routing_update':
        // Briefly walk the next speaker toward center
        if (event.turn_order?.[0]) {
          this._walkAgent(event.turn_order[0]);
        }
        break;
      case 'org_health_event':
        this._showOrgAlert(event.event);
        break;
      case 'debate_complete':
        this._onDebateComplete();
        break;
      default:
        break;
    }
  }

  _onAgentToken(agentName, token) {
    this.tokenBuffers[agentName] = (this.tokenBuffers[agentName] || '') + token;
    const sprite = this.agentSprites[agentName];
    if (!sprite) return;

    // Start talk animation
    const cfg = AGENTS[agentName];
    if (cfg) sprite.play(`${cfg.sprite}_talk`, true);

    // Highlight sprite
    sprite.setTint(0xffffff);
    this._updateSpeechBubble(agentName, this.tokenBuffers[agentName]);
    this.activeSpeaker = agentName;
  }

  _onAgentComplete(agentName) {
    const sprite = this.agentSprites[agentName];
    const cfg    = AGENTS[agentName];
    if (!sprite || !cfg) return;

    // Back to idle
    sprite.play(`${cfg.sprite}_idle`, true);
    sprite.clearTint();
    this.tokenBuffers[agentName] = '';

    // Fade out bubble after 3s
    this.time.delayedCall(3000, () => {
      this._clearSpeechBubble(agentName);
    });

    if (this.activeSpeaker === agentName) this.activeSpeaker = null;
  }

  _walkAgent(agentName) {
    const sprite = this.agentSprites[agentName];
    const cfg    = AGENTS[agentName];
    if (!sprite || !cfg) return;

    sprite.play(`${cfg.sprite}_walk`, true);
    const origX = sprite.x;

    this.tweens.add({
      targets: sprite,
      x: origX + 15,
      duration: 400,
      yoyo: true,
      onComplete: () => sprite.play(`${cfg.sprite}_idle`, true),
    });
  }

  _updateSpeechBubble(agentName, text) {
    const sprite = this.agentSprites[agentName];
    if (!sprite) return;

    this._clearSpeechBubble(agentName);

    const maxChars = 80;
    const displayText = text.length > maxChars ? text.slice(-maxChars) : text;
    const wordWrapped = this._wrapText(displayText, 22);

    // Sprite origin is bottom-center, so top of sprite = y - spriteHeight
    const spriteH = FRAME_H * sprite.scaleY;
    const bx = sprite.x;
    const by = sprite.y - spriteH - 8; // above the sprite head

    const bubblePad = 8;
    const lineH     = 10;
    const lines     = wordWrapped.split('\n');
    const bw        = Math.min(Math.max(...lines.map(l => l.length)) * 6 + bubblePad * 2, 200);
    const bh        = lines.length * lineH + bubblePad * 2 + 10;

    const bg = this.add.graphics().setDepth(20);

    // Bubble body
    bg.fillStyle(0x000000, 0.88);
    bg.fillRoundedRect(bx - bw / 2, by - bh, bw, bh, 6);
    bg.lineStyle(1.5, parseInt(AGENTS[agentName]?.color?.replace('#', '0x') || '0xffffff'), 0.9);
    bg.strokeRoundedRect(bx - bw / 2, by - bh, bw, bh, 6);

    // Tail
    bg.fillStyle(0x000000, 0.88);
    bg.fillTriangle(bx - 6, by, bx + 6, by, bx, by + 8);

    const txt = this.add.text(bx, by - bh / 2, wordWrapped, {
      fontFamily: '"Press Start 2P", monospace',
      fontSize: '5px',
      color: '#ffffff',
      align: 'left',
      wordWrap: { width: bw - bubblePad * 2 },
    }).setOrigin(0.5, 0.5).setDepth(21);

    this.speechBubbles[agentName] = { bg, txt };
  }

  _clearSpeechBubble(agentName) {
    const bubble = this.speechBubbles[agentName];
    if (!bubble) return;
    bubble.bg?.destroy();
    bubble.txt?.destroy();
    delete this.speechBubbles[agentName];
  }

  _showOrgAlert(eventType) {
    const alertColors = {
      leadership_review: 0xff4444,
      debate_stall:      0xffaa00,
      voice_imbalance:   0x4488ff,
      engagement_drop:   0x888888,
    };
    const color = alertColors[eventType] || 0xffffff;

    const alertText = this.add.text(440, 275, `⚠ ${eventType.replace(/_/g, ' ').toUpperCase()}`, {
      fontFamily: '"Press Start 2P", monospace',
      fontSize: '7px',
      color: `#${color.toString(16).padStart(6, '0')}`,
      backgroundColor: '#000000ee',
      padding: { x: 8, y: 5 },
    }).setOrigin(0.5).setDepth(30).setAlpha(0);

    this.tweens.add({
      targets: alertText,
      alpha: 1,
      duration: 300,
      yoyo: true,
      hold: 3000,
      onComplete: () => alertText.destroy(),
    });
  }

  _onDebateComplete() {
    // Flash all agents briefly
    Object.values(this.agentSprites).forEach(sprite => {
      this.tweens.add({
        targets: sprite,
        alpha: 0.4,
        duration: 400,
        yoyo: true,
        repeat: 2,
      });
    });
  }

  _wrapText(text, maxLen) {
    const words = text.split(' ');
    const lines = [];
    let current = '';
    words.forEach(word => {
      if ((current + word).length > maxLen) {
        if (current) lines.push(current.trim());
        current = word + ' ';
      } else {
        current += word + ' ';
      }
    });
    if (current.trim()) lines.push(current.trim());
    return lines.join('\n');
  }

  update() {
    const t = this.time.now;
    Object.entries(this.agentSprites).forEach(([name, sprite]) => {
      if (name !== this.activeSpeaker) {
        // Subtle vertical bob — store base y on first update
        if (sprite._baseY === undefined) sprite._baseY = sprite.y;
        sprite.y = sprite._baseY + Math.sin(t * 0.0008 + sprite.x * 0.05) * 1.5;
        // Keep label in sync
        const label = this.agentLabels[name];
        if (label) label.y = sprite.y + 3;
      }
    });
  }
}

// ─── Phaser game factory ──────────────────────────────────────────────────
export function createBoardroomGame(container, onEventEmitter) {
  const game = new Phaser.Game({
    type: Phaser.AUTO,
    width: 860,
    height: 530,
    backgroundColor: '#0a0a0f',
    parent: container,
    scene: [BoardroomScene],
    pixelArt: true,
    antialias: false,
    roundPixels: true,
    scale: {
      mode: Phaser.Scale.FIT,
      autoCenter: Phaser.Scale.CENTER_BOTH,
    },
  });

  // Expose event emitter to React
  onEventEmitter((event) => {
    game.events.emit('ws_event', event);
  });

  return game;
}
