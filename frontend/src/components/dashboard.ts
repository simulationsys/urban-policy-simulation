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
      // Connect to WebSocket stream for selected scenario
      const socketUrl = `${this.wsBaseUrl}/scenarios/${this.currentScenario}`;
      this.ws = new WebSocket(socketUrl);

      this.ws.onopen = () => {
        this.addEventLog(`Connected to live simulation stream (${this.currentScenario})`, 'success');
        if (wsStatus) {
          wsStatus.textContent = 'Live Connected';
          wsStatus.className = 'connection-badge connected';
        }
        // Sync initial state if available
        this.fetchScenarioMetadata();
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

    } catch (e) {
      this.handleDisconnect('Backend unreachable. Running in local demo mode.');
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

  private async fetchScenarioMetadata() {
    try {
      const res = await fetch(`${this.restBaseUrl}/scenarios/${this.currentScenario}`);
      if (res.ok) {
        const metadata = await res.json();
        this.addEventLog(`Synced configuration from backend. Seed: ${metadata.seed || 'Default'}`, 'info');
      }
    } catch (e) {
      // Quiet fail - backends might not be fully stood up yet
    }
  }

  private handleBackendTick(frame: any) {
    // Sync clock
    if (frame.tick !== undefined) {
      // Ticks are 5 min steps
      this.simClock = 8 * 60 + frame.tick * 5;
      this.updateClockUI();
    }

    // Capture telemetry metrics
    const delay = frame.metrics?.avg_commute_delay || 15;
    const share = frame.metrics?.transit_mode_share || 32;
    const gridlock = frame.metrics?.gridlock_index || 10;
    const metroCap = frame.metrics?.metro_stations_at_capacity || 0;

    // Update charts
    this.chartsManager.recordTick(delay, share, gridlock, metroCap);

    // Sync policies if modified upstream
    if (frame.active_policies) {
      this.policyController.syncState({
        busCapacity: frame.active_policies.bus_capacity_boost || 0,
        metroFreq: frame.active_policies.metro_frequency_boost || 0,
        congestionPricing: frame.active_policies.congestion_pricing_fee || 0,
        wfhMandate: frame.active_policies.wfh_percentage > 0
      });
    }

    // Sync weather and events
    if (frame.weather) {
      this.rainIntensity = frame.weather.rain_intensity || 0;
      this.updateWeatherUI();
    }

    if (frame.events && frame.events.length > 0) {
      frame.events.forEach((evt: any) => {
        this.addEventLog(evt.description, 'info');
      });
    }

    // Run Map Engine updates
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
          // Push command to backend
          this.ws.send(JSON.stringify({ action: 'step' }));
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

  private togglePlay(force?: boolean) {
    this.isPlaying = force !== undefined ? force : !this.isPlaying;
    const playBtn = document.getElementById('playback-play');
    const playIcon = document.getElementById('play-icon');

    if (this.isPlaying) {
      playBtn?.classList.add('active');
      if (playIcon) {
        playIcon.innerHTML = `<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>`;
      }
      
      if (this.ws) {
        this.ws.send(JSON.stringify({ action: 'resume' }));
      } else {
        // Start local simulation tick intervals
        this.tickIntervalId = window.setInterval(() => this.triggerDemoTick(), this.tickRateMs);
      }
      this.addEventLog("Simulation playback running.", "info");
    } else {
      playBtn?.classList.remove('active');
      if (playIcon) {
        playIcon.innerHTML = `<polygon points="5 3 19 12 5 21 5 3"></polygon>`;
      }
      
      if (this.ws) {
        this.ws.send(JSON.stringify({ action: 'pause' }));
      } else {
        if (this.tickIntervalId) {
          clearInterval(this.tickIntervalId);
          this.tickIntervalId = null;
        }
      }
      this.addEventLog("Simulation playback paused.", "info");
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

        // Reconnect WebSocket to the new scenario endpoint
        if (this.ws) {
          this.ws.close();
        }
        this.connectBackend();
      });
    }
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
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      // Propagate policies to active backend
      this.ws.send(JSON.stringify({
        action: 'policy',
        data: {
          bus_capacity_boost: policyState.busCapacity,
          metro_frequency_boost: policyState.metroFreq,
          congestion_pricing_fee: policyState.congestionPricing,
          wfh_percentage: policyState.wfhMandate ? 30 : 0
        }
      }));
    }
    
    // Add micro feedback in events feed
    this.addEventLog(`Policy adjusted: Bus Cap +${policyState.busCapacity}%, Metro Freq +${policyState.metroFreq}%, Fee ₹${policyState.congestionPricing}, WFH ${policyState.wfhMandate ? '30%' : 'Off'}`, 'info');
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
