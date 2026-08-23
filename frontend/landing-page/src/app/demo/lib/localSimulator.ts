export enum Mode {
  walk = "walk",
  bike = "bike",
  car = "car",
  metro = "metro",
  bus = "bus",
  auto = "auto",
  bike_share = "bike_share",
  e_rickshaw = "e_rickshaw",
}

export interface AggregateMetrics {
  tick: number;
  sim_time_minutes: number;
  rain_intensity: number;
  avg_commute_minutes: number;
  mode_share: Record<Mode, number>;
  metro_load_pct: number;
  bus_load_pct: number;
  road_congestion_index: number;
  agents_commuting: number;
  aqi_estimate: number;
}

export interface GridCell {
  lat: number;
  lon: number;
  density: number;
  congestion: number;
}

export interface SimSnapshot {
  tick: number;
  sim_time_minutes: number;
  metrics: AggregateMetrics;
  grid: GridCell[];
}

export class LocalSimulator {
  private tick = 0;
  private population: number;
  private tickMinutes = 10;
  private seed = 42;

  // Modifiable parameters
  public rain = 0.0;
  public busCapacityPct = 1.0;
  public fuelPriceDeltaPaise = 0;
  public disabledMetroLines = new Set<string>();

  private cells: GridCell[] = [];

  constructor(population = 10000) {
    this.population = population;
    this.initGrid();
  }

  private initGrid() {
    const latBase = 28.6328;
    const lonBase = 77.2197;
    const rows = 10;
    const cols = 10;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        this.cells.push({
          lat: latBase + (r - rows / 2) * 0.005,
          lon: lonBase + (c - cols / 2) * 0.005,
          density: 0,
          congestion: 0,
        });
      }
    }
  }

  // Simple seeded pseudo-random number generator to keep it deterministic
  private random(s: number) {
    const x = Math.sin(s) * 10000;
    return x - Math.floor(x);
  }

  private getJitter(offset: number): number {
    const val = this.random(this.seed + this.tick * 0.1 + offset);
    return (val - 0.5) * 0.06; // jitter in [-0.03, 0.03]
  }

  public getDayPhase(): number {
    const minutes = (this.tick * this.tickMinutes) % (24 * 60);
    const hour = minutes / 60.0;
    // Gaussian curves for peak commuting hours: 9 AM and 6 PM
    const morning = Math.exp(-Math.pow(hour - 9.0, 2) / 2.0);
    const evening = Math.exp(-Math.pow(hour - 18.0, 2) / 2.5);
    return Math.min(1.0, morning + evening);
  }

  public step(): SimSnapshot {
    this.tick += 1;
    this.updateGrid();
    return this.snapshot();
  }

  public getFormattedTime(): string {
    const totalMinutes = this.tick * this.tickMinutes;
    const hour = Math.floor((totalMinutes / 60) % 24);
    const minute = Math.floor(totalMinutes % 60);
    const ampm = hour >= 12 ? "PM" : "AM";
    const hour12 = hour % 12 === 0 ? 12 : hour % 12;
    const padMin = minute.toString().padStart(2, "0");
    return `${hour12}:${padMin} ${ampm}`;
  }

  public snapshot(): SimSnapshot {
    const phase = this.getDayPhase();
    const rain = this.rain;
    const metroPenalty = this.disabledMetroLines.size > 0 ? 0.25 : 0;
    const fuelPush = Math.min(0.15, this.fuelPriceDeltaPaise / 20000); // Max push at 20000 paise (₹200)

    const walk = Math.max(0.02, 0.12 - 0.06 * rain + this.getJitter(1));
    const bike = Math.max(0.02, 0.10 - 0.07 * rain + this.getJitter(2));
    const car = Math.max(0.05, 0.22 - 0.05 * rain - fuelPush + this.getJitter(3));
    const metro = Math.max(0.05, 0.26 + 0.12 * rain + 0.5 * fuelPush - metroPenalty + this.getJitter(4));
    const bus = Math.max(0.05, 0.18 + 0.04 * rain + 0.4 * fuelPush + metroPenalty * 0.5) * this.busCapacityPct;
    const auto = Math.max(0.05, 0.12 + 0.06 * rain + this.getJitter(5));
    const bike_share = Math.max(0.01, 0.03 - 0.02 * rain + this.getJitter(6) * 0.5);
    const e_rickshaw = Math.max(0.02, 0.06 + 0.01 * rain + this.getJitter(7) * 0.5);

    const total = walk + bike + car + metro + bus + auto + bike_share + e_rickshaw;

    const modeShare: Record<Mode, number> = {
      [Mode.walk]: walk / total,
      [Mode.bike]: bike / total,
      [Mode.car]: car / total,
      [Mode.metro]: metro / total,
      [Mode.bus]: bus / total,
      [Mode.auto]: auto / total,
      [Mode.bike_share]: bike_share / total,
      [Mode.e_rickshaw]: e_rickshaw / total,
    };

    const baseCommute = 28.0;
    const avgCommute = baseCommute * (1 + 0.6 * rain + 0.5 * phase + 0.3 * metroPenalty);
    const congestion = Math.min(1.0, 0.2 + 0.5 * phase + 0.5 * rain + 0.2 * metroPenalty * 0.5); // Fixed metroPenalty reference
    const metroLoad = Math.min(1.0, 0.3 + 0.5 * phase + 0.4 * rain + metroPenalty) * 100;
    const busLoad = Math.min(1.0, 0.2 + 0.4 * phase + 0.3 * rain + metroPenalty * 0.5) * 100;
    const commuting = Math.floor(this.population * phase);

    // AQI estimate based on emissions from combustion modes
    const carShare = modeShare[Mode.car] || 0;
    const autoShare = modeShare[Mode.auto] || 0;
    const busShare = modeShare[Mode.bus] || 0;
    const aqi = Math.min(500.0, (carShare * 0.045 + autoShare * 0.030 + busShare * 0.010) * commuting * 50);

    const metrics: AggregateMetrics = {
      tick: this.tick,
      sim_time_minutes: this.tick * this.tickMinutes,
      rain_intensity: Number(rain.toFixed(3)),
      avg_commute_minutes: Number(avgCommute.toFixed(2)),
      mode_share: modeShare,
      metro_load_pct: Number(metroLoad.toFixed(2)),
      bus_load_pct: Number(busLoad.toFixed(2)),
      road_congestion_index: Number(congestion.toFixed(3)),
      agents_commuting: commuting,
      aqi_estimate: Number(aqi.toFixed(1)),
    };

    return {
      tick: this.tick,
      sim_time_minutes: this.tick * this.tickMinutes,
      metrics,
      grid: this.cells,
    };
  }

  private updateGrid() {
    const phase = this.getDayPhase();
    this.cells = this.cells.map((cell, idx) => {
      const base = this.random(this.seed + idx * 0.9 + this.tick * 0.05);
      return {
        ...cell,
        density: Math.floor((this.population / this.cells.length) * (0.5 + phase) * base),
        congestion: Number(Math.min(1.0, base * (0.3 + 0.6 * phase + 0.4 * this.rain)).toFixed(3)),
      };
    });
  }

  public reset(seed = 42) {
    this.tick = 0;
    this.seed = seed;
    this.rain = 0.0;
    this.busCapacityPct = 1.0;
    this.fuelPriceDeltaPaise = 0;
    this.disabledMetroLines.clear();
    this.updateGrid();
  }
}
