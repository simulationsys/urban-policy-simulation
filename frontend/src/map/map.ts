// Map Visualisation Engine - Canvas overlays representing roads, agents, floods and metro
export interface Agent {
  x: number;
  y: number;
  mode: 'car' | 'metro' | 'bus' | 'walk' | 'auto';
  speed: number;
  targetX: number;
  targetY: number;
  progress: number;
}

export interface MapData {
  roads: { id: string; coords: [number, number][]; congestion: number }[];
  metroLines: { id: string; coords: [number, number][]; name: string }[];
  floodedZones: { coords: [number, number][]; intensity: number }[];
  agents: Agent[];
}

export class MapEngine {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private animationFrameId: number | null = null;
  private isRunning: boolean = false;

  // View state coordinates & zoom levels
  private scale: number = 1.2;
  private offsetX: number = 0;
  private offsetY: number = 0;

  // Layer toggle states
  public showNetwork: boolean = true;
  public showAgents: boolean = true;
  public showTransit: boolean = true;
  public showFlood: boolean = false;

  // Mock geographical bounds (centering near Delhi/NCR coordinates)
  private data: MapData = {
    roads: [],
    metroLines: [],
    floodedZones: [],
    agents: []
  };

  constructor(canvasId: string) {
    this.canvas = document.getElementById(canvasId) as HTMLCanvasElement;
    if (!this.canvas) throw new Error(`Canvas with id ${canvasId} not found.`);
    
    this.ctx = this.canvas.getContext('2d')!;
    this.resizeCanvas();
    
    window.addEventListener('resize', () => this.resizeCanvas());
    
    // Seed our geographical network data
    this.generateMockNetwork();
  }

  private resizeCanvas() {
    const rect = this.canvas.parentElement?.getBoundingClientRect();
    this.canvas.width = rect?.width || window.innerWidth;
    this.canvas.height = rect?.height || window.innerHeight;
    
    // Auto-center coordinates
    this.offsetX = this.canvas.width / 2;
    this.offsetY = this.canvas.height / 2;
  }

  private generateMockNetwork() {
    // Generate organic concentric-radial grid matching major Indian cities
    const roadCount = 18;
    const ringCount = 4;
    const roads: MapData['roads'] = [];
    
    // Outer radial rings
    for (let r = 1; r <= ringCount; r++) {
      const radius = r * 100;
      const coords: [number, number][] = [];
      const steps = 36;
      for (let i = 0; i <= steps; i++) {
        const theta = (i / steps) * Math.PI * 2;
        coords.push([Math.cos(theta) * radius, Math.sin(theta) * radius]);
      }
      roads.push({
        id: `ring_${r}`,
        coords,
        congestion: 0.1 * r
      });
    }

    // Concentric radial spokes
    for (let s = 0; s < roadCount; s++) {
      const theta = (s / roadCount) * Math.PI * 2;
      const radiusMax = ringCount * 100;
      roads.push({
        id: `spoke_${s}`,
        coords: [[0, 0], [Math.cos(theta) * radiusMax, Math.sin(theta) * radiusMax]],
        congestion: 0.2
      });
    }

    // Metro rails
    const metroLines: MapData['metroLines'] = [
      {
        id: 'metro_yellow',
        name: 'Yellow Line',
        coords: [
          [-350, -350],
          [-150, -150],
          [0, 0],
          [150, 150],
          [350, 350]
        ]
      },
      {
        id: 'metro_blue',
        name: 'Blue Line',
        coords: [
          [-400, 50],
          [-200, 50],
          [0, 0],
          [200, -50],
          [400, -50]
        ]
      }
    ];

    // Flooded sectors (South & East zones)
    const floodedZones: MapData['floodedZones'] = [
      {
        coords: [
          [50, 50],
          [250, 70],
          [200, 250],
          [30, 180]
        ],
        intensity: 0.8
      },
      {
        coords: [
          [-250, 100],
          [-100, 80],
          [-120, 250],
          [-230, 220]
        ],
        intensity: 0.5
      }
    ];

    // Instantiate active agents
    const agents: Agent[] = [];
    const agentCount = 800;
    const modes: Agent['mode'][] = ['car', 'metro', 'bus', 'walk', 'auto'];
    
    for (let a = 0; a < agentCount; a++) {
      const mode = modes[Math.floor(Math.random() * modes.length)];
      // Choose random road spoke/ring path
      const road = roads[Math.floor(Math.random() * roads.length)];
      const coordIndex = Math.floor(Math.random() * (road.coords.length - 1));
      
      const start = road.coords[coordIndex];
      const end = road.coords[coordIndex + 1];

      agents.push({
        x: start[0],
        y: start[1],
        mode,
        speed: 1 + Math.random() * 2,
        targetX: end[0],
        targetY: end[1],
        progress: Math.random()
      });
    }

    this.data = { roads, metroLines, floodedZones, agents };
  }

  // Update dynamic agent positions on roads
  public update(rainIntensity: number, busCapacity: number, metroFreq: number) {
    // Increase road congestion under rain
    this.data.roads.forEach(road => {
      let baseline = road.id.includes('ring') ? 0.3 : 0.2;
      road.congestion = Math.min(1.0, baseline + rainIntensity * 0.5);
    });

    // Animate agents along their coordinates
    this.data.agents.forEach(agent => {
      let speedFactor = 1.0;
      
      // Calculate speed reductions
      if (agent.mode === 'car' || agent.mode === 'auto') {
        speedFactor = Math.max(0.15, 1.0 - rainIntensity * 0.8);
      } else if (agent.mode === 'bus') {
        speedFactor = Math.max(0.3, 1.0 - rainIntensity * 0.5 + (busCapacity / 100) * 0.2);
      } else if (agent.mode === 'metro') {
        speedFactor = 1.0 + (metroFreq / 80) * 0.3; // Frequency keeps speed stable
      }

      agent.progress += 0.005 * agent.speed * speedFactor;
      if (agent.progress >= 1.0) {
        agent.progress = 0;
        // Swap endpoints
        const tempX = agent.x;
        const tempY = agent.y;
        agent.x = agent.targetX;
        agent.y = agent.targetY;
        agent.targetX = tempX;
        agent.targetY = tempY;
      } else {
        // Interpolate position
        const currentX = agent.x + (agent.targetX - agent.x) * agent.progress;
        const currentY = agent.y + (agent.targetY - agent.y) * agent.progress;
        
        // Cache current coordinates visually
        (agent as any).currentX = currentX;
        (agent as any).currentY = currentY;
      }
    });
  }

  public setFlood(active: boolean) {
    this.showFlood = active;
  }

  // Start graphics drawing loop
  public start() {
    if (this.isRunning) return;
    this.isRunning = true;
    const loop = () => {
      if (!this.isRunning) return;
      this.draw();
      this.animationFrameId = requestAnimationFrame(loop);
    };
    this.animationFrameId = requestAnimationFrame(loop);
  }

  public stop() {
    this.isRunning = false;
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }

  // Canvas drawing instructions
  private draw() {
    const { ctx, canvas, scale, offsetX, offsetY } = this;
    
    // Clear canvas frame
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Transform coordinates matrix
    ctx.save();
    ctx.translate(offsetX, offsetY);
    ctx.scale(scale, scale);

    // 1. Draw flood overlays (semi-transparent glowing red/blue polygon layers)
    if (this.showFlood) {
      this.data.floodedZones.forEach(zone => {
        ctx.beginPath();
        zone.coords.forEach((coord, index) => {
          if (index === 0) ctx.moveTo(coord[0], coord[1]);
          else ctx.lineTo(coord[0], coord[1]);
        });
        ctx.closePath();
        ctx.fillStyle = `rgba(239, 68, 68, ${zone.intensity * 0.18})`;
        ctx.fill();
        ctx.strokeStyle = `rgba(239, 68, 68, 0.4)`;
        ctx.lineWidth = 1;
        ctx.stroke();
      });
    }

    // 2. Draw Road network grid
    if (this.showNetwork) {
      this.data.roads.forEach(road => {
        ctx.beginPath();
        road.coords.forEach((coord, index) => {
          if (index === 0) ctx.moveTo(coord[0], coord[1]);
          else ctx.lineTo(coord[0], coord[1]);
        });
        
        // Dynamic colors based on congestion
        const c = road.congestion;
        let color = `rgba(255, 255, 255, 0.1)`;
        let width = 1.0;
        
        if (c > 0.7) {
          color = `rgba(239, 68, 68, 0.65)`; // Overcrowded / Blocked (Red)
          width = 2.0;
        } else if (c > 0.4) {
          color = `rgba(245, 158, 11, 0.5)`; // Heavy Congestion (Yellow)
          width = 1.5;
        } else {
          color = `rgba(255, 255, 255, 0.12)`; // Freeflow (Low contrast white)
        }

        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.stroke();
      });
    }

    // 3. Draw Metro rails (glowing neon lines)
    if (this.showTransit) {
      this.data.metroLines.forEach(line => {
        ctx.beginPath();
        line.coords.forEach((coord, index) => {
          if (index === 0) ctx.moveTo(coord[0], coord[1]);
          else ctx.lineTo(coord[0], coord[1]);
        });
        
        // Inner Rail Core
        ctx.strokeStyle = line.id.includes('yellow') ? 'rgba(234, 179, 8, 0.9)' : 'rgba(30, 144, 255, 0.9)';
        ctx.lineWidth = 1.5;
        ctx.stroke();
        
        // Outer Glowing Aura
        ctx.save();
        ctx.shadowBlur = 10;
        ctx.shadowColor = line.id.includes('yellow') ? 'rgba(234, 179, 8, 0.5)' : 'rgba(30, 144, 255, 0.5)';
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.restore();
      });
    }

    // 4. Draw Thousands of active agents as micro-particles
    if (this.showAgents) {
      this.data.agents.forEach(agent => {
        const x = (agent as any).currentX || agent.x;
        const y = (agent as any).currentY || agent.y;
        
        // Color mapping matching layout styles
        let color = '#ffffff';
        let radius = 1.2;
        
        if (agent.mode === 'metro') {
          color = '#1e90ff'; // Cyan Blue
          radius = 1.8;
        } else if (agent.mode === 'bus') {
          color = '#a855f7'; // Purple-Indigo
          radius = 1.8;
        } else if (agent.mode === 'car') {
          color = '#f59e0b'; // Amber Congestion
        } else if (agent.mode === 'auto') {
          color = '#10b981'; // Green auto-rickshaw
        }
        
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
      });
    }

    ctx.restore();
  }
}
