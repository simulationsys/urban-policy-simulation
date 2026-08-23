import { MapEngine } from '../map/map';
import { ChartsManager } from '../charts/charts';
import { PolicyController } from '../policy/policy';
import type { PolicyState } from '../policy/policy';

export class DashboardApp {
  private mapEngine: MapEngine;
  private chartsManager: ChartsManager;
  private policyController: PolicyController;

  // Playback state
  private isPlaying: boolean = false;
  private simClock: number = 8 * 60; // 08:00 AM (in minutes)
  private tickIntervalId: number | null = null;
  private tickRateMs: number = 1000;

  // Simulation parameters for scenario stress
  private rainIntensity: number = 0; // 0.0 to 1.0
  private currentScenario: string = 'scenario_a_monsoon';
  
  // Real Backend connection details
  private ws: WebSocket | null = null;
  private restBaseUrl = 'http://localhost:8000/api/v1';
  private wsBaseUrl = 'ws://localhost:8000/ws';

  // Resolved at connect time — backend stores scenarios by id (e.g. scenario_0001),
  // while currentScenario holds the human name (e.g. scenario_a_monsoon).
  private scenarioId: string | null = null;
  // Debounce slider-driven policy posts so we don't flood the backend.
  private policyDebounce: number | null = null;
  // Whether we've auto-injected this scenario's archetypal event for this run.
  private archetypeInjected = false;

  constructor() {
    this.mapEngine = new MapEngine('map-canvas');
    this.chartsManager = new ChartsManager();
    
    // Bind policies
    this.policyController = new PolicyController((policyState) => {
      this.handlePolicyUpdate(policyState);
    });

    this.initPlaybackUI();
    this.initLayerToggles();
    this.initScenarioSelector();
    this.initModeToggles();
    this.initLiveControls();

    // Map Engine loop
    this.mapEngine.start();
    
    // Attempt connecting to backend, fallback to demo loop if offline
    this.connectBackend();
    
    // Set up standard initial event
    this.addEventLog('Monsoon Scenario selected. Weather clear. Baseline active.', 'info');
  }

  // --- REST & WEBSOCKET SYNC LAYER ---
  private async connectBackend() {
    const wsStatus = document.getElementById('ws-status');
    if (wsStatus) {
      wsStatus.textContent = 'Connecting...';
      wsStatus.className = 'connection-badge connecting';
    }

    try {
      // Backend keys scenarios by id; resolve from the human name in the selector.
      this.scenarioId = await this.resolveScenarioId(this.currentScenario);
      if (!this.scenarioId) {
        this.handleDisconnect(`Scenario '${this.currentScenario}' not registered on backend.`);
        return;
      }

      // Start (idempotent on the backend — returns 'running' if already running).
      await fetch(`${this.restBaseUrl}/scenarios/${this.scenarioId}/start`, { method: 'POST' });

      const socketUrl = `${this.wsBaseUrl}/scenarios/${this.scenarioId}`;
      this.ws = new WebSocket(socketUrl);
      this.archetypeInjected = false;

      this.ws.onopen = () => {
        this.addEventLog(
          `Connected to live stream (${this.currentScenario} → ${this.scenarioId})`,
          'success'
        );
        if (wsStatus) {
          wsStatus.textContent = 'Live Connected';
          wsStatus.className = 'connection-badge connected';
        }
        this.isPlaying = true;
        this.reflectPlayUI();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleBackendTick(data);
        } catch (e) {
          console.error("Error parsing WebSocket frame: ", e);
        }
      };

      this.ws.onclose = () => {
        this.handleDisconnect('Connection closed. Running in local demo mode.');
      };

      this.ws.onerror = () => {
        this.handleDisconnect('Backend offline. Initialized local demo sandbox.');
      };

    } catch {
      this.handleDisconnect('Backend unreachable. Running in local demo mode.');
    }
  }

  private async resolveScenarioId(name: string): Promise<string | null> {
    try {
      const res = await fetch(`${this.restBaseUrl}/scenarios`);
      if (!res.ok) return null;
      const list = (await res.json()) as Array<{
        id: string;
        name: string;
        config: { seed: number; population: number; tick_minutes: number; city: string };
      }>;
      const match = list.find((s) => s.name === name);
      if (match) this.renderScenarioFacts(match);
      return match?.id ?? null;
    } catch {
      return null;
    }
  }

  // Inject a 5th stat card for SUB-01 Phase 1's `aqi_estimate`. Idempotent — runs once.
  private ensureAqiCard() {
    if (document.getElementById('stat-aqi')) return;
    const grid = document.getElementById('analytics-grid');
    if (!grid) return;
    const card = document.createElement('div');
    card.className = 'chart-card';
    card.innerHTML = `
      <div class="chart-card-header">
        <span>AIR QUALITY (AQI)</span>
        <span class="chart-delta stable" id="stat-aqi-band">—</span>
      </div>
      <div class="chart-value-display" id="stat-aqi">0</div>
      <div style="font-size: 11px; color: var(--text-muted); margin-top: var(--space-1);">
        Estimated from mode-share emissions · CPCB scale 0–500
      </div>
    `;
    grid.appendChild(card);
  }

  private renderAqi(aqi: number) {
    this.ensureAqiCard();
    const el = document.getElementById('stat-aqi');
    const band = document.getElementById('stat-aqi-band');
    if (el) el.textContent = Math.round(aqi).toString();
    if (band) {
      // CPCB AQI bands — keeps the label aligned with how Indian agencies report it.
      let label = 'Good';
      let cls = 'chart-delta stable';
      if (aqi > 400) { label = 'Severe'; cls = 'chart-delta negative'; }
      else if (aqi > 300) { label = 'Very Poor'; cls = 'chart-delta negative'; }
      else if (aqi > 200) { label = 'Poor'; cls = 'chart-delta negative'; }
      else if (aqi > 100) { label = 'Moderate'; cls = 'chart-delta'; }
      else if (aqi > 50) { label = 'Satisfactory'; cls = 'chart-delta stable'; }
      band.textContent = label;
      band.className = cls;
    }
  }

  // Append bus load as a small annotation under the existing "METRO STATIONS AT CAP"
  // card so the two transit-mode loads sit next to each other.
  private renderBusLoad(pct: number) {
    const metroValue = document.getElementById('stat-metro');
    const host = metroValue?.parentElement;
    if (!host) return;
    let line = document.getElementById('stat-bus-load');
    if (!line) {
      line = document.createElement('div');
      line.id = 'stat-bus-load';
      line.style.cssText =
        'font-size: 11px; color: var(--text-muted); margin-top: var(--space-1);';
      host.appendChild(line);
    }
    line.textContent = `Bus load: ${pct.toFixed(0)}%`;
  }

  // Append real backend facts (id, seed, population) to the scenario panel so the
  // operator can see exactly what they're connected to — not just the marketing blurb.
  private renderScenarioFacts(summary: {
    id: string;
    config: { seed: number; population: number; tick_minutes: number; city: string };
  }) {
    const desc = document.getElementById('scenario-details');
    if (!desc) return;
    const factsId = 'scenario-facts';
    let facts = document.getElementById(factsId);
    if (!facts) {
      facts = document.createElement('div');
      facts.id = factsId;
      facts.style.cssText =
        'margin-top: var(--space-2); font-family: var(--font-mono, monospace); font-size: 11px; color: var(--text-muted); line-height: 1.5;';
      desc.parentElement?.appendChild(facts);
    }
    const c = summary.config;
    facts.innerHTML = `
      <div>id <span style="color:var(--accent);">${summary.id}</span></div>
      <div>city <span style="color:var(--accent);">${c.city}</span> · seed <span style="color:var(--accent);">${c.seed}</span></div>
      <div>pop <span style="color:var(--accent);">${c.population.toLocaleString()}</span> · tick <span style="color:var(--accent);">${c.tick_minutes} sim-min</span></div>
    `;
  }

  // After a few ticks of baseline, inject the event that defines each scenario so
  // the dashboard reveals real dynamics without the operator hunting for a button.
  private async triggerArchetypalEvent() {
    if (this.archetypeInjected || !this.scenarioId) return;
    this.archetypeInjected = true;

    let event: { type: string; payload: Record<string, number | string | boolean> } | null = null;
    if (this.currentScenario === 'scenario_a_monsoon') {
      event = { type: 'WEATHER_EVENT', payload: { rain_intensity: 0.9, duration_ticks: 60 } };
    } else if (this.currentScenario === 'scenario_b_metro_shutdown') {
      event = { type: 'INFRASTRUCTURE_EVENT', payload: { disable_metro_line: 'yellow' } };
    } else if (this.currentScenario === 'scenario_c_fuel_shock') {
      event = { type: 'POLICY_EVENT', payload: { fuel_price_delta_paise: 2000 } };
    }
    if (!event) return;

    try {
      await fetch(`${this.restBaseUrl}/scenarios/${this.scenarioId}/events`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(event),
      });
      this.addEventLog(`Auto-injected ${event.type} for ${this.currentScenario}.`, 'warning');
    } catch (e) {
      this.addEventLog(`Failed to inject archetypal event: ${e}`, 'danger');
    }
  }

  private handleDisconnect(message: string) {
    this.ws = null;
    const wsStatus = document.getElementById('ws-status');
    if (wsStatus) {
      wsStatus.textContent = 'Demo Sandbox';
      wsStatus.className = 'connection-badge';
    }
    this.addEventLog(message, 'warning');
    
    // Auto-start ticking in local demo mode to wow the user immediately!
    if (!this.isPlaying) {
      this.togglePlay(true);
    }
  }

  private handleBackendTick(frame: any) {
    // Backend WSMessage envelopes — type is 'status' | 'tick' | 'error'.
    if (frame.type === 'error') {
      this.addEventLog(`Backend: ${frame.message ?? 'error'}`, 'danger');
      return;
    }
    if (frame.type === 'status') {
      // Initial frame after connect — nothing to render yet.
      return;
    }

    // 'tick' frames carry diff: { metrics, changed_cells }.
    const m = frame.diff?.metrics;
    if (!m) return;

    // sim_time_minutes is absolute simulated minutes since midnight — drive clock from it.
    if (typeof m.sim_time_minutes === 'number') {
      this.simClock = m.sim_time_minutes;
      this.updateClockUI();
    }

    // Map backend fields → dashboard widgets.
    //   avg_commute_minutes                            → "AVG COMMUTE DELAY" (minutes)
    //   (metro + bus + bike_share + e_rickshaw) share  → "TRANSIT MODE SHARE" (%)
    //                                                    [SUB-01 Phase 1 added the latter two]
    //   road_congestion_index * 100                    → "GRIDLOCK INDEX" (%)
    //   metro_load_pct / 100 * 42                      → "METRO STATIONS AT CAP"
    //   aqi_estimate                                   → "AIR QUALITY (AQI)" — injected card
    //   bus_load_pct                                   → annotation under metro card
    const ms = m.mode_share ?? {};
    const transit =
      ((ms.metro ?? 0) + (ms.bus ?? 0) + (ms.bike_share ?? 0) + (ms.e_rickshaw ?? 0)) * 100;
    const delay = m.avg_commute_minutes ?? 0;
    const gridlock = (m.road_congestion_index ?? 0) * 100;
    const metroCap = Math.round(((m.metro_load_pct ?? 0) / 100) * 42);
    this.chartsManager.recordTick(delay, transit, gridlock, metroCap);

    // Render the two SUB-01 Phase 1 metrics that the 4 stock cards don't cover.
    const aqi = m.aqi_estimate ?? 0;
    const busLoad = m.bus_load_pct ?? 0;
    this.renderAqi(aqi);
    this.renderBusLoad(busLoad);

    // Weather lives inside metrics (rain_intensity), not a separate field.
    const rain = m.rain_intensity ?? 0;
    if (rain !== this.rainIntensity) {
      this.rainIntensity = rain;
      this.updateWeatherUI();
      this.mapEngine.setFlood(rain > 0.6);
    }

    // Backend grid cells: TickDiff sends only the ones that changed this tick.
    const cells = frame.diff?.changed_cells;
    if (Array.isArray(cells) && cells.length > 0) {
      this.mapEngine.ingestCells(cells);
    }

    // After a brief baseline, auto-inject the scenario's defining event.
    if (frame.tick === 8) {
      this.triggerArchetypalEvent();
    }

    // Animate map.
    this.mapEngine.update(
      this.rainIntensity,
      this.policyController.state.busCapacity,
      this.policyController.state.metroFreq
    );
  }

  // --- LOCAL DEMO TICK GENERATOR (FALLBACK) ---
  private triggerDemoTick() {
    this.simClock += 5; // Ticks advance by 5 simulated minutes
    if (this.simClock > 14 * 60) {
      this.simClock = 8 * 60; // Reset to 8 AM
      this.rainIntensity = 0;
      this.mapEngine.setFlood(false);
      this.addEventLog("Simulation cycle restarted at baseline.", "info");
    }

    this.updateClockUI();

    // Trigger monsoon rain stressors organically over time
    if (this.currentScenario === 'scenario_a_monsoon') {
      if (this.simClock === 8 * 30) { // 8:30 AM
        this.rainIntensity = 0.4;
        this.addEventLog("Moderate rainfall detected across East Delhi. Road speeds decreasing.", "warning");
      } else if (this.simClock === 9 * 60) { // 9:00 AM
        this.rainIntensity = 0.8;
        this.mapEngine.setFlood(true);
        this.addEventLog("CRITICAL: Severe rain causing floods in South/East transit zones.", "danger");
      } else if (this.simClock === 11 * 60) { // 11:00 AM
        this.rainIntensity = 0.3;
        this.addEventLog("Rainfall subsidizing. Water levels beginning to recede.", "info");
      }
    } else if (this.currentScenario === 'scenario_b_metro_shutdown') {
      if (this.simClock === 8 * 30) {
        this.addEventLog("ALERT: Technical delay reported on Metro Blue line. Stations crowding.", "danger");
      }
    }

    this.updateWeatherUI();

    // Compute mock math models based on policies & rainfall (organic emergence)
    let delay = 18.5;
    let share = 34.2;
    let gridlock = 12;
    let metroCap = 0;

    // Apply rain impact
    if (this.rainIntensity > 0) {
      delay += this.rainIntensity * 12;
      gridlock += Math.round(this.rainIntensity * 35);
      share += this.rainIntensity * 14; // Shift to public transit
      metroCap += Math.round(this.rainIntensity * 12);
    }

    // Apply policies mitigations
    const bus = this.policyController.state.busCapacity;
    const metro = this.policyController.state.metroFreq;
    const pricing = this.policyController.state.congestionPricing;
    const wfh = this.policyController.state.wfhMandate;

    if (bus > 0) {
      delay -= (bus / 100) * 4;
      gridlock -= (bus / 100) * 8;
      share += (bus / 100) * 5;
    }

    if (metro > 0) {
      delay -= (metro / 80) * 5;
      gridlock -= (metro / 80) * 4;
      share += (metro / 80) * 10;
      metroCap -= Math.round((metro / 80) * 8);
    }

    if (pricing > 0) {
      gridlock -= (pricing / 250) * 15;
      delay -= (pricing / 250) * 6;
      share += (pricing / 250) * 8;
    }

    if (wfh) {
      gridlock -= 18;
      delay -= 8;
      share -= 4; // WFH don't commute
    }

    // Keep numbers within realistic bounds
    delay = Math.max(8.0, delay);
    gridlock = Math.max(4.0, gridlock);
    share = Math.max(12.0, Math.min(95.0, share));
    metroCap = Math.max(0, Math.min(42, metroCap));

    // Record metrics in charts
    this.chartsManager.recordTick(delay, share, gridlock, metroCap);

    // Update map animations
    this.mapEngine.update(this.rainIntensity, bus, metro);
  }

  // --- INTERACTION WIDGET BINDINGS ---
  private initPlaybackUI() {
    const playBtn = document.getElementById('playback-play');
    const prevBtn = document.getElementById('playback-prev');
    const nextBtn = document.getElementById('playback-next');

    if (playBtn) {
      playBtn.addEventListener('click', () => this.togglePlay());
    }

    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        if (this.ws) {
          // Backend ticks autonomously; no manual step in v1.
          this.addEventLog('Backend ticks autonomously — manual stepping disabled.', 'info');
        } else {
          this.triggerDemoTick();
        }
      });
    }

    if (prevBtn) {
      prevBtn.addEventListener('click', () => {
        this.addEventLog("Stepping backward is disabled under live state constraints.", "warning");
      });
    }
  }

  private async togglePlay(force?: boolean) {
    this.isPlaying = force !== undefined ? force : !this.isPlaying;
    this.reflectPlayUI();

    if (this.scenarioId) {
      // Live mode: drive lifecycle via REST (the WS only accepts Event payloads).
      const endpoint = this.isPlaying ? 'resume' : 'pause';
      try {
        await fetch(`${this.restBaseUrl}/scenarios/${this.scenarioId}/${endpoint}`, {
          method: 'POST',
        });
      } catch (e) {
        this.addEventLog(`Failed to ${endpoint}: ${e}`, 'warning');
      }
    } else {
      // Offline demo mode: tick locally.
      if (this.isPlaying) {
        this.tickIntervalId = window.setInterval(() => this.triggerDemoTick(), this.tickRateMs);
      } else if (this.tickIntervalId) {
        clearInterval(this.tickIntervalId);
        this.tickIntervalId = null;
      }
    }
    this.addEventLog(
      this.isPlaying ? 'Simulation playback running.' : 'Simulation playback paused.',
      'info'
    );
  }

  private reflectPlayUI() {
    const playBtn = document.getElementById('playback-play');
    const playIcon = document.getElementById('play-icon');
    if (this.isPlaying) {
      playBtn?.classList.add('active');
      if (playIcon) {
        playIcon.innerHTML = `<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>`;
      }
    } else {
      playBtn?.classList.remove('active');
      if (playIcon) {
        playIcon.innerHTML = `<polygon points="5 3 19 12 5 21 5 3"></polygon>`;
      }
    }
  }

  private initLayerToggles() {
    const toggleLayer = (btnId: string, layerKey: 'showNetwork' | 'showAgents' | 'showTransit' | 'showFlood') => {
      const btn = document.getElementById(btnId);
      if (btn) {
        btn.addEventListener('click', () => {
          const active = btn.classList.toggle('active');
          (this.mapEngine as any)[layerKey] = active;
          this.addEventLog(`Layer [${btn.textContent}] visibility updated.`, 'info');
        });
      }
    };

    toggleLayer('layer-network', 'showNetwork');
    toggleLayer('layer-agents', 'showAgents');
    toggleLayer('layer-transit', 'showTransit');
    toggleLayer('layer-flood', 'showFlood');
  }

  private initScenarioSelector() {
    const select = document.getElementById('scenario-selector') as HTMLSelectElement;
    const desc = document.getElementById('scenario-details');

    if (select) {
      select.addEventListener('change', (e) => {
        const val = (e.target as HTMLSelectElement).value;
        this.currentScenario = val;
        
        // Reset playback
        this.togglePlay(false);
        this.simClock = 8 * 60;
        this.updateClockUI();
        this.rainIntensity = 0;
        this.mapEngine.setFlood(false);

        // Update scenario details textual copy
        if (desc) {
          if (val === 'scenario_a_monsoon') {
            desc.textContent = "Heavy rain falls over the city starting 08:00 AM. Commuters faces slowed roads, shifting mode choices dramatically towards public transit.";
          } else if (val === 'scenario_b_metro_shutdown') {
            desc.textContent = "Simulates partial/full shutdown of Delhi Metro Blue Line. Forces commuters to utilize private autos, causing gridlock in critical arteries.";
          } else if (val === 'scenario_c_fuel_shock') {
            desc.textContent = "Simulates a sharp rise of ₹20/L in fuel costs overnight. Commuters recalibrate travel utility values, leading to long-term bus and walking shifts.";
          }
        }

        this.addEventLog(`Loaded scenario: ${val}. Syncing connections.`, 'info');

        // Pause the previous run on the backend (best-effort) and drop the socket.
        if (this.scenarioId) {
          fetch(`${this.restBaseUrl}/scenarios/${this.scenarioId}/pause`, {
            method: 'POST',
          }).catch(() => {});
        }
        if (this.ws) {
          this.ws.close();
          this.ws = null;
        }
        this.scenarioId = null;
        this.connectBackend();
      });
    }
  }

  // Inject Reset + Export buttons next to the existing playback controls and
  // render the resolved scenario seed/population once we're connected. These
  // are added programmatically so we don't have to fork index.html for them.
  private initLiveControls() {
    const playbackHost = document.querySelector('.playback-controls') as HTMLElement | null;
    if (!playbackHost) return;

    const mkBtn = (id: string, title: string, label: string, onClick: () => void) => {
      const btn = document.createElement('button');
      btn.className = 'control-btn';
      btn.id = id;
      btn.title = title;
      btn.textContent = label;
      btn.addEventListener('click', onClick);
      return btn;
    };

    playbackHost.appendChild(
      mkBtn('playback-reset', 'Reset scenario to tick 0', '↻', () => this.resetScenario())
    );
    playbackHost.appendChild(
      mkBtn('playback-export', 'Download metrics arc as CSV', '⤓', () => this.exportRun())
    );
  }

  private async resetScenario() {
    if (this.scenarioId) {
      try {
        await fetch(`${this.restBaseUrl}/scenarios/${this.scenarioId}/reset`, { method: 'POST' });
        this.archetypeInjected = false;
        this.addEventLog('Scenario reset to tick 0.', 'info');
        // After a reset the scenario is in 'created' state; restart it so the stream resumes.
        await fetch(`${this.restBaseUrl}/scenarios/${this.scenarioId}/start`, { method: 'POST' });
      } catch (e) {
        this.addEventLog(`Reset failed: ${e}`, 'warning');
      }
    } else {
      this.simClock = 0;
      this.rainIntensity = 0;
      this.mapEngine.setFlood(false);
      this.updateClockUI();
      this.updateWeatherUI();
      this.addEventLog('Demo sandbox reset.', 'info');
    }
  }

  private exportRun() {
    if (!this.scenarioId) {
      this.addEventLog('No live scenario — export only works in Live Connected mode.', 'warning');
      return;
    }
    const url = `${this.restBaseUrl}/scenarios/${this.scenarioId}/export?format=csv`;
    // Anchor click triggers the browser's native download dialog.
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    a.remove();
    this.addEventLog('Downloaded metrics arc CSV.', 'success');
  }

  private initModeToggles() {
    const btnBase = document.getElementById('mode-baseline');
    const btnCompare = document.getElementById('mode-comparison');

    if (btnBase && btnCompare) {
      btnBase.addEventListener('click', () => {
        btnBase.classList.add('active');
        btnCompare.classList.remove('active');
        this.showComparisonView(false);
      });

      btnCompare.addEventListener('click', () => {
        btnCompare.classList.add('active');
        btnBase.classList.remove('active');
        this.showComparisonView(true);
      });
    }
  }

  private showComparisonView(active: boolean) {
    const grid = document.getElementById('analytics-grid');
    if (!grid) return;

    if (active) {
      // Morph the 4x1 telemetry widgets to a gorgeous before/after side-by-side analytical split screen
      this.addEventLog("Active comparison mode initialized. Comparing current run to baseline metrics.", "info");
      grid.innerHTML = `
        <div class="comparison-grid" style="grid-column: span 4;">
          <div class="comparison-column">
            <div class="comparison-heading">
              <span>BASELINE (Normal Operations)</span>
              <span style="color: var(--color-success); font-size: 11px;">Validated</span>
            </div>
            
            <div class="card" style="margin-bottom: var(--space-2)">
              <div class="card-title">Average Delay</div>
              <div class="chart-value-display">12.5m</div>
              <p style="font-size: var(--fs-xs);">Calculated over 10k standard agent commutes</p>
            </div>

            <div class="card" style="margin-bottom: var(--space-2)">
              <div class="card-title">Public Transit Share</div>
              <div class="chart-value-display">28.0%</div>
              <p style="font-size: var(--fs-xs);">DMRC ridership at balanced density limits</p>
            </div>

            <div class="card" style="margin-bottom: var(--space-2)">
              <div class="card-title">Congested Artery Network</div>
              <div class="chart-value-display">8%</div>
              <p style="font-size: var(--fs-xs);">Peak hours roads velocity reduction</p>
            </div>
          </div>

          <div class="comparison-column">
            <div class="comparison-heading" style="border-bottom-color: var(--accent);">
              <span>CURRENT SIMULATION (Active Stresses)</span>
              <span style="color: var(--color-warning); font-size: 11px;">Simulating</span>
            </div>
            
            <div class="card" style="margin-bottom: var(--space-2)">
              <div class="card-title">Average Delay</div>
              <div class="chart-value-display" style="color: var(--color-danger);" id="comp-delay">18.5m</div>
              <p style="font-size: var(--fs-xs);">Increase due to active weather speeds drop</p>
            </div>

            <div class="card" style="margin-bottom: var(--space-2)">
              <div class="card-title">Public Transit Share</div>
              <div class="chart-value-display" style="color: var(--accent);" id="comp-share">34.2%</div>
              <p style="font-size: var(--fs-xs);">Emergency shifts toward metro lines</p>
            </div>

            <div class="card" style="margin-bottom: var(--space-2)">
              <div class="card-title">Congested Artery Network</div>
              <div class="chart-value-display" style="color: var(--color-warning);" id="comp-gridlock">12%</div>
              <p style="font-size: var(--fs-xs);">Commuter velocity reductions on radial roads</p>
            </div>
          </div>
        </div>
      `;
      this.syncComparisonTelemetry();
    } else {
      // Morph back to telemetry cards
      grid.innerHTML = `
        <!-- Stat 1: Commute Delay -->
        <div class="chart-card">
          <div class="chart-card-header">
            <span>AVG COMMUTE DELAY</span>
            <span class="chart-delta stable" id="stat-delay-delta">0m</span>
          </div>
          <div class="chart-value-display" id="stat-delay">18.5m</div>
          <div class="bar-chart-container" id="chart-delay-bars"></div>
        </div>

        <!-- Stat 2: Transit Mode Share -->
        <div class="chart-card">
          <div class="chart-card-header">
            <span>TRANSIT MODE SHARE</span>
            <span class="chart-delta stable" id="stat-share-delta">0%</span>
          </div>
          <div class="chart-value-display" id="stat-share">34.2%</div>
          <div class="bar-chart-container" id="chart-share-bars"></div>
        </div>

        <!-- Stat 3: Gridlock Index -->
        <div class="chart-card">
          <div class="chart-card-header">
            <span>GRIDLOCK INDEX</span>
            <span class="chart-delta stable" id="stat-gridlock-delta">0%</span>
          </div>
          <div class="chart-value-display" id="stat-gridlock">12%</div>
          <div class="bar-chart-container" id="chart-gridlock-bars"></div>
        </div>

        <!-- Stat 4: Metro Overcrowding -->
        <div class="chart-card">
          <div class="chart-card-header">
            <span>METRO STATIONS AT CAP</span>
            <span class="chart-delta stable" id="stat-metro-delta">0</span>
          </div>
          <div class="chart-value-display" id="stat-metro">0 / 42</div>
          <div class="bar-chart-container" id="chart-metro-bars"></div>
        </div>
      `;
      this.chartsManager.renderAllCharts();
    }
  }

  private syncComparisonTelemetry() {
    const compDelay = document.getElementById('comp-delay');
    const compShare = document.getElementById('comp-share');
    const compGridlock = document.getElementById('comp-gridlock');

    // Fetch values directly from telemetry buffers
    const delay = (this.chartsManager as any).getLast((this.chartsManager as any).delayHistory);
    const share = (this.chartsManager as any).getLast((this.chartsManager as any).shareHistory);
    const gridlock = (this.chartsManager as any).getLast((this.chartsManager as any).gridlockHistory);

    if (compDelay) compDelay.textContent = `${delay.toFixed(1)}m`;
    if (compShare) compShare.textContent = `${share.toFixed(1)}%`;
    if (compGridlock) compGridlock.textContent = `${Math.round(gridlock)}%`;
  }

  private handlePolicyUpdate(policyState: PolicyState) {
    // Debounce slider drag so we don't post on every pixel — coalesce to one event.
    if (this.policyDebounce !== null) {
      window.clearTimeout(this.policyDebounce);
    }
    this.policyDebounce = window.setTimeout(() => {
      this.policyDebounce = null;
      if (this.scenarioId && this.ws && this.ws.readyState === WebSocket.OPEN) {
        // Backend Event contract: { type: EventType, payload: dict[str, scalar] }.
        // Bus slider 0-100 → multiplier 1.0-2.0. Congestion fee (₹) → fuel-price-delta proxy (paise).
        // metro_freq / wfh_pct pass through as named knobs for future engine support.
        const payload: Record<string, number | boolean> = {
          bus_capacity_pct: 1.0 + policyState.busCapacity / 100,
          fuel_price_delta_paise: policyState.congestionPricing * 100,
          metro_freq_boost_pct: policyState.metroFreq,
          wfh_pct: policyState.wfhMandate ? 30 : 0,
        };
        this.ws.send(JSON.stringify({ type: 'POLICY_EVENT', payload }));
      }
      this.addEventLog(
        `Policy adjusted: Bus +${policyState.busCapacity}%, Metro +${policyState.metroFreq}%, Fee ₹${policyState.congestionPricing}, WFH ${policyState.wfhMandate ? '30%' : 'Off'}`,
        'info'
      );
    }, 300);
  }

  // --- HELPER UTILITIES ---
  private updateClockUI() {
    const el = document.getElementById('sim-clock');
    if (!el) return;

    const hrs = Math.floor(this.simClock / 60);
    const mins = this.simClock % 60;
    const ampm = hrs >= 12 ? 'PM' : 'AM';
    const hrsDisplay = hrs > 12 ? hrs - 12 : hrs === 0 ? 12 : hrs;
    const minsDisplay = mins < 10 ? `0${mins}` : mins;
    
    el.textContent = `${hrsDisplay}:${minsDisplay} ${ampm}`;

    // Sync comparison view if active
    const compPanel = document.getElementById('comp-delay');
    if (compPanel) {
      this.syncComparisonTelemetry();
    }
  }

  private updateWeatherUI() {
    const indicator = document.getElementById('weather-indicator');
    const text = document.getElementById('weather-text');
    if (!indicator || !text) return;

    if (this.rainIntensity > 0) {
      indicator.className = 'weather-indicator-glow rainy';
      text.textContent = `Weather: Rain (${Math.round(this.rainIntensity * 100)}%)`;
    } else {
      indicator.className = 'weather-indicator-glow';
      text.textContent = 'Weather: Clear';
    }
  }

  private addEventLog(desc: string, type: 'info' | 'warning' | 'danger' | 'success' = 'info') {
    const feed = document.getElementById('event-feed');
    if (!feed) return;

    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    const item = document.createElement('div');
    item.className = `event-feed-item ${type}`;
    item.innerHTML = `
      <div class="event-time">${timeStr}</div>
      <div class="event-desc">${desc}</div>
    `;

    feed.appendChild(item);
    feed.scrollTop = feed.scrollHeight; // Auto-scroll to latest
  }
}
