"use client";

import { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import {
  Activity,
  BusFront,
  CloudRain,
  IndianRupee,
  Layers3,
  Map as MapIcon,
  Radio,
  Route,
  Sparkles,
  Users,
} from "lucide-react";

const DashboardMap = dynamic(() => import("../components/DashboardMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-slate-900 flex items-center justify-center text-slate-400 animate-pulse">
      Initializing Map Engine...
    </div>
  )
});

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const WS_BASE = API_BASE.replace('http', 'ws');

export default function Dashboard() {
  // --- SIMULATION STATES ---
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [population, setPopulation] = useState(0);
  const [backendMetrics, setBackendMetrics] = useState<any>(null);
  const [wsStatus, setWsStatus] = useState<string>("Connecting...");
  const wsRef = useRef<WebSocket | null>(null);

  // Local UI state for sliders (which fire events)
  const [busCapacity, setBusCapacity] = useState(20);
  const [congestionFee, setCongestionFee] = useState(0);
  const [rainIntensity, setRainIntensity] = useState(0);
  const [timeOfDay, setTimeOfDay] = useState(12);
  const [isTimeManual, setIsTimeManual] = useState(false);
  const isTimeManualRef = useRef(false);
  const [activeOverlay, setActiveOverlay] = useState("Road Network");

  // Focus-cohort agents streamed by the engine, keyed by agent id.
  const [liveAgents, setLiveAgents] = useState<any[]>([]);
  const legsRef = useRef<Map<string, any>>(new Map());
  // Lets the map interpolate simulated time between ticks instead of jumping.
  const [simClock, setSimClock] = useState<{ minutes: number; receivedAt: number; minutesPerSecond: number } | null>(null);
  const lastTickRef = useRef<{ minutes: number; at: number } | null>(null);
  const simClockRateRef = useRef<number>(0);
  // Whole-population density/congestion, keyed "lat,lon" and patched by each tick diff.
  const [gridCells, setGridCells] = useState<any[]>([]);
  const cellsRef = useRef<Record<string, any>>({});
  // Citizens who are stationary (at home or arrived somewhere), and their homes.
  const [presences, setPresences] = useState<any[]>([]);
  const presenceRef = useRef<Record<string, any>>({});
  const [dwellings, setDwellings] = useState<Record<string, any>>({});
  const dwellingRef = useRef<Record<string, any>>({});

  // Which engine the backend is actually running. If it is the stub, the map has no
  // citizens to draw and falls back to canned routes — the user must be told, not shown
  // looping demo traffic that looks like a simulation.
  const [engineInfo, setEngineInfo] = useState<any>(null);
  useEffect(() => {
    fetch(`${API_BASE}/readyz`)
      .then(res => res.json())
      .then(setEngineInfo)
      .catch(() => setEngineInfo(null));
  }, []);

  // Ticks seen since connecting, used to judge the backend by what it actually sends.
  const [ticksSeen, setTicksSeen] = useState(0);

  // Whether to warn that this is canned playback. An explicit flag from /readyz wins; an
  // older backend does not report one, so fall back to ground truth — several ticks have
  // arrived and not one citizen came with them.
  const receivingCitizens =
    liveAgents.length > 0 || presences.length > 0 || Object.keys(dwellings).length > 0;
  const showDemoWarning =
    engineInfo?.simulates_individuals === false ||
    (!receivingCitizens && ticksSeen >= 5);

  // Connect to Backend and start Scenario
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/scenarios`)
      .then(res => res.json())
      .then(data => {
        if (data && data.length > 0) {
          // Find the pre-populated monsoon scenario or just take the first one
          // Join a city that is already alive before starting a cold one: a fresh run
          // begins before dawn, so reloading into a new scenario means watching an empty
          // map until the morning peak arrives. Otherwise prefer a run on real streets.
          const target = data.find((s: any) => s.config?.city === 'new_york' && s.config?.max_tracked_agents >= 5000);
          if (target) {
            setScenarioId(target.id);
            setPopulation(target.config.population);
            if (target.status !== 'running') {
              fetch(`${API_BASE}/api/v1/scenarios/${target.id}/start`, { method: 'POST' }).catch(() => {});
            }
          } else {
            fetch(`${API_BASE}/api/v1/scenarios`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ config: { name: "midtown_manhattan", city: "new_york", population: 5000, max_tracked_agents: 5000, seed: 42, use_real_data: true, start_time_minutes: 540 } })
            }).then(res => res.json()).then(target => {
              setScenarioId(target.id);
              setPopulation(target.config?.population ?? 5000);
              fetch(`${API_BASE}/api/v1/scenarios/${target.id}/start`, { method: 'POST' });
            });
          }
        } else {
            // Create one if none exists
            fetch(`${API_BASE}/api/v1/scenarios`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ config: { name: "midtown_manhattan", city: "new_york", population: 5000, max_tracked_agents: 5000, seed: 42, use_real_data: true, start_time_minutes: 540 } })
            }).then(res => res.json()).then(target => {
                setScenarioId(target.id);
                setPopulation(target.config?.population ?? 5000);
                fetch(`${API_BASE}/api/v1/scenarios/${target.id}/start`, { method: 'POST' });
            });
        }
      })
      .catch(err => {
        console.error(`Backend not reachable. Ensure it is running at ${API_BASE}`, err);
        setWsStatus("Backend Offline");
      });
  }, []);

  // WebSocket Sync with Auto-Reconnect
  useEffect(() => {
    if (!scenarioId) return;

    let ws: WebSocket;
    let retryTimer: NodeJS.Timeout;

    // Legs belong to one scenario's world; never carry them across a switch.
    legsRef.current.clear();
    setLiveAgents([]);
    setTicksSeen(0);
    cellsRef.current = {};
    setGridCells([]);
    presenceRef.current = {};
    setPresences([]);
    dwellingRef.current = {};
    setDwellings({});

    const connect = () => {
      ws = new WebSocket(`${WS_BASE}/ws/scenarios/${scenarioId}`);
      wsRef.current = ws;

      ws.onopen = () => setWsStatus("Live Connected");
      ws.onclose = () => {
        setWsStatus("Disconnected (Retrying...)");
        retryTimer = setTimeout(connect, 3000);
      };
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'tick' && data.diff && data.diff.metrics) {
          const m = data.diff.metrics;
          setBackendMetrics(m);
          setRainIntensity(Math.round(m.rain_intensity * 100) || 0);
          const totalMinutes = m.sim_time_minutes || 0;
          if (!isTimeManualRef.current) {
            setTimeOfDay((totalMinutes / 60) % 24 || 12);
          }

          // Derive how fast simulated time runs from the gap between ticks, rather
          // than assuming the server's tick interval.
          const now = Date.now();
          const prev = lastTickRef.current;
          let rate = simClockRateRef.current;
          if (prev && totalMinutes > prev.minutes && now > prev.at) {
            const observed = (totalMinutes - prev.minutes) / ((now - prev.at) / 1000);
            // Smooth it: a single delayed frame should not lurch the animation.
            rate = rate ? rate * 0.7 + observed * 0.3 : observed;
            simClockRateRef.current = rate;
          }
          lastTickRef.current = { minutes: totalMinutes, at: now };
          setTicksSeen(t => (t < 10 ? t + 1 : t));
          setSimClock({ minutes: totalMinutes, receivedAt: now, minutesPerSecond: rate || 5 });

          // Apply the leg diff: add legs that started, drop those that ended.
          const legs = legsRef.current;
          (data.diff.started_legs || []).forEach((leg: any) => legs.set(leg.agent_id, leg));
          (data.diff.finished_agents || []).forEach((id: string) => legs.delete(id));
          if ((data.diff.started_legs || []).length || (data.diff.finished_agents || []).length) {
            setLiveAgents(Array.from(legs.values()));
          }

          // Stationary citizens. A leg starting means they left, so drop them from here.
          const updatedPresences = data.diff.presences || [];
          if (updatedPresences.length || (data.diff.started_legs || []).length) {
            updatedPresences.forEach((p: any) => { presenceRef.current[p.agent_id] = p; });
            (data.diff.started_legs || []).forEach((l: any) => { delete presenceRef.current[l.agent_id]; });
            setPresences(Object.values(presenceRef.current));
          }

          const newHomes = data.diff.dwellings || {};
          if (Object.keys(newHomes).length) {
            dwellingRef.current = { ...dwellingRef.current, ...newHomes };
            setDwellings(dwellingRef.current);
          }

          const changed = data.diff.changed_cells || [];
          if (changed.length) {
            changed.forEach((c: any) => { cellsRef.current[`${c.lat},${c.lon}`] = c; });
            setGridCells(Object.values(cellsRef.current));
          }
        }
      };
    };

    connect();

    return () => {
      if (retryTimer) clearTimeout(retryTimer);
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
      wsRef.current = null;
    };
  }, [scenarioId]);

  // Event Handlers for Policy Injection
  const injectPolicy = (type: string, payload: any) => {
    if (!scenarioId) return;
    fetch(`${API_BASE}/api/v1/scenarios/${scenarioId}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, payload })
    }).catch(console.error);
  };

  const handleRainChange = (val: number) => {
    setRainIntensity(val);
    injectPolicy("WEATHER_EVENT", { rain_intensity: val / 100.0, duration_ticks: 100 });
  };

  const handleFeeChange = (val: number) => {
    setCongestionFee(val);
    injectPolicy("POLICY_EVENT", { congestion_fee: val });
  };

  const handleBusChange = (val: number) => {
    setBusCapacity(val);
    injectPolicy("POLICY_EVENT", { bus_capacity_pct: val / 100.0 + 1.0 });
  };

  const formatTime = (time: number) => {
    const hours = Math.floor(time);
    const mins = Math.floor((time - hours) * 60);
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;
    return `${displayHours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')} ${ampm}`;
  };

  return (
    <div className={`w-screen h-screen overflow-hidden relative transition-colors duration-1000 ${timeOfDay >= 6 && timeOfDay <= 18 ? 'bg-blue-100' : 'bg-slate-950'}`}>
      <div className="absolute inset-0 z-0">
        <DashboardMap 
          rainIntensity={rainIntensity}
          congestionFee={congestionFee}
          busCapacity={busCapacity}
          timeOfDay={timeOfDay}
          activeOverlay={activeOverlay}
          liveAgents={liveAgents}
          simClock={simClock}
          gridCells={gridCells}
          presences={presences}
          dwellings={dwellings}
        />
      </div>

      <div className="absolute top-5 left-5 z-[1000] flex items-stretch gap-3">
        <div className="hud-panel h-[58px] px-4 flex items-center gap-3.5">
          <div className="relative grid size-9 place-items-center rounded-xl bg-emerald-400/10 ring-1 ring-inset ring-emerald-300/20">
            <Sparkles className="size-[18px] text-emerald-300" strokeWidth={1.7} />
            <span className="absolute -right-0.5 -top-0.5 size-2 rounded-full bg-emerald-300 shadow-[0_0_10px_#6ee7b7]" />
          </div>
          <div className="pr-1">
            <h1 className="text-[15px] font-semibold leading-none tracking-[0.22em] text-white">PRAVAAH</h1>
            <p className="mt-1.5 text-[8px] font-medium tracking-[0.28em] text-slate-400">URBAN DIGITAL TWIN</p>
          </div>
        </div>
        {backendMetrics && (
          <div className="hud-panel min-h-[58px] px-3 py-2 flex flex-wrap items-center gap-x-4 gap-y-2">
            <div className="flex flex-col border-r border-white/10 pr-4">
              <span className="hud-eyebrow">City population</span>
              <span className="hud-value">{population.toLocaleString()}</span>
            </div>
            <div className="flex items-center gap-2.5 border-r border-white/10 pr-5">
              <Activity className="size-4 text-emerald-300" />
              <div className="flex flex-col">
                <span className="hud-eyebrow">Tick</span>
                <span className="hud-value">{backendMetrics.tick || 0}</span>
              </div>
            </div>
            <div className="flex flex-col">
              <span className="hud-eyebrow">AQI</span>
              <span className={`hud-value ${backendMetrics.aqi_estimate > 150 ? 'text-rose-300' : 'text-amber-300'}`}>{backendMetrics.aqi_estimate || '--'}</span>
            </div>
            <div className="flex flex-col">
              <span className="hud-eyebrow">Flow</span>
              <span className="hud-value">{((backendMetrics.road_congestion_index || 0) * 100).toFixed(1)}%</span>
            </div>
            <div className="flex items-center gap-2.5">
              <Users className="size-4 text-sky-300" />
              <div className="flex flex-col">
                <span className="hud-eyebrow">Moving</span>
                <span className="hud-value">{backendMetrics.agents_commuting || 0}</span>
              </div>
            </div>
            <div className="flex flex-col border-l border-white/10 pl-4">
              <span className="hud-eyebrow">Metro load</span>
              <span className="hud-value">{Math.round(backendMetrics.metro_load_pct || 0)}%</span>
            </div>
            <div className="flex flex-col border-l border-white/10 pl-4">
              <span className="hud-eyebrow">Bus load</span>
              <span className="hud-value">{Math.round(backendMetrics.bus_load_pct || 0)}%</span>
            </div>
            <div className="flex flex-col border-l border-white/10 pl-4">
              <span className="hud-eyebrow">Avg commute</span>
              <span className="hud-value">{Math.round(backendMetrics.avg_commute_minutes || 0)} min</span>
            </div>
            {!!Object.keys(backendMetrics.mode_share || {}).length && (
              <div className="flex w-full flex-wrap items-center gap-2 border-t border-white/10 pt-2">
                <span className="hud-eyebrow mr-1">Travel modes</span>
                {Object.entries(backendMetrics.mode_share).map(([mode, share]) => (
                  <span key={mode} className="rounded-md bg-white/[0.06] px-2 py-1 text-[9px] font-medium capitalize text-slate-300">
                    {mode.replaceAll('_', ' ')} <b className="ml-1 text-white">{Math.round(Number(share) * 100)}%</b>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="absolute top-5 right-5 z-[1000] flex flex-col items-end gap-2">
        <div className="hud-panel h-11 px-3.5 flex items-center gap-3">
          <span className={`relative flex size-2.5 ${wsStatus === 'Live Connected' ? 'text-emerald-300' : 'text-rose-400'}`}>
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-current opacity-50" />
            <span className="relative inline-flex size-2.5 rounded-full bg-current shadow-[0_0_12px_currentColor]" />
          </span>
          <div>
            <div className="text-[8px] font-medium uppercase tracking-[0.24em] text-slate-500">Network</div>
            <div className={`mt-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${wsStatus === 'Live Connected' ? 'text-emerald-200' : 'text-rose-300'}`}>
              {wsStatus === 'Live Connected' ? 'Live sync' : wsStatus}
            </div>
          </div>
          <Radio className="ml-1 size-3.5 text-slate-500" />
        </div>

        {/* Never let canned demo traffic pass for a simulated city. */}
        {showDemoWarning && (
          <div className="max-w-xs px-4 py-3 rounded-xl bg-amber-500/15 backdrop-blur-md border border-amber-500/40 shadow-lg">
            <div className="text-[10px] font-bold uppercase tracking-widest text-amber-400">
              Demo playback — not simulated
            </div>
            <p className="mt-1 text-[11px] leading-snug text-amber-100/80">
              The backend is running the stub engine, so no individual citizens exist. The
              vehicles on the map are pre-recorded routes.
            </p>
            <p className="mt-1 text-[10px] leading-snug text-amber-200/60">
              {engineInfo?.engine_reason ||
                "This backend does not report an engine, and no citizens have arrived over the stream."}
            </p>
          </div>
        )}
        {engineInfo?.simulates_individuals && !engineInfo?.real_data && (
          <div className="max-w-xs px-4 py-3 rounded-xl bg-sky-500/15 backdrop-blur-md border border-sky-500/40 shadow-lg">
            <div className="text-[10px] font-bold uppercase tracking-widest text-sky-300">
              Synthetic street grid
            </div>
            <p className="mt-1 text-[11px] leading-snug text-sky-100/80">
              Citizens are simulated, but on a placeholder grid — run the data pipelines to
              route them along real Delhi streets.
            </p>
          </div>
        )}
      </div>

      <div className="hud-panel absolute bottom-5 left-5 z-[1000] w-[318px] p-5">
        <div>
          <div className="mb-5 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="grid size-8 place-items-center rounded-lg bg-emerald-400/10 text-emerald-300 ring-1 ring-inset ring-emerald-300/15"><Activity className="size-4" /></span>
              <div><h3 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white">Policy lab</h3><p className="mt-0.5 text-[9px] text-slate-500">Live intervention controls</p></div>
            </div>
            <span className="rounded-full bg-emerald-300/10 px-2 py-1 text-[8px] font-semibold uppercase tracking-[0.16em] text-emerald-200 ring-1 ring-inset ring-emerald-300/15">Active</span>
          </div>
          <div className="flex flex-col gap-4">
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-xs text-slate-300 font-medium">Bus Capacity</span>
                <span className="text-xs font-mono text-emerald-400">{busCapacity}%</span>
              </div>
              <input aria-label="Bus capacity" type="range" min="0" max="100" value={busCapacity} onChange={(e) => setBusCapacity(Number(e.target.value))} onMouseUp={(e: any) => handleBusChange(Number(e.target.value))} onTouchEnd={(e: any) => handleBusChange(Number(e.target.value))} className="hud-slider accent-emerald" />
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-xs text-slate-300 font-medium">Congestion Fee</span>
                <span className="text-xs font-mono text-amber-400">₹{congestionFee}</span>
              </div>
              <input aria-label="Congestion fee" type="range" min="0" max="100" value={congestionFee} onChange={(e) => setCongestionFee(Number(e.target.value))} onMouseUp={(e: any) => handleFeeChange(Number(e.target.value))} onTouchEnd={(e: any) => handleFeeChange(Number(e.target.value))} className="hud-slider accent-amber" />
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-xs text-slate-300 font-medium">Rain Intensity</span>
                <span className="text-xs font-mono text-blue-400">{rainIntensity}%</span>
              </div>
              <input aria-label="Rain intensity" type="range" min="0" max="100" value={rainIntensity} onChange={(e) => setRainIntensity(Number(e.target.value))} onMouseUp={(e: any) => handleRainChange(Number(e.target.value))} onTouchEnd={(e: any) => handleRainChange(Number(e.target.value))} className="hud-slider accent-sky" />
            </div>
          </div>
        </div>
      </div>

      <div className="hud-panel absolute bottom-5 right-5 z-[1000] flex items-center gap-3 px-4 py-3">
        <div className="grid size-8 place-items-center rounded-lg bg-sky-300/10 text-sky-200 ring-1 ring-inset ring-sky-200/15"><MapIcon className="size-4" /></div>
        <div className="flex w-60 flex-col">
          <div className="flex justify-between mb-2 items-center">
            <span className="text-xs font-bold text-white">{formatTime(timeOfDay)}</span>
            <div className="flex gap-2 items-center">
              {isTimeManual && (
                <button 
                  onClick={() => { setIsTimeManual(false); isTimeManualRef.current = false; }} 
                  className="rounded-full bg-white/5 px-2 py-0.5 text-[8px] text-emerald-300 transition-colors hover:bg-white/10"
                >
                  Sync
                </button>
              )}
              <span className="text-[8px] font-medium uppercase tracking-[0.18em] text-slate-400">{timeOfDay >= 6 && timeOfDay <= 18 ? 'Daylight' : 'Night'}</span>
            </div>
          </div>
          <input 
            type="range" 
            min="0" 
            max="24" 
            step="0.1"
            value={timeOfDay} 
            onChange={(e) => {
              const val = Number(e.target.value);
              setTimeOfDay(val);
              if (!isTimeManual) {
                setIsTimeManual(true);
                isTimeManualRef.current = true;
              }
            }} 
            className="hud-slider accent-sky"
          />
        </div>
      </div>
      
      <div className="hud-panel absolute bottom-5 left-1/2 z-[1000] flex -translate-x-1/2 items-center gap-1 p-1.5">
        {["Road Network", "Agent Congestion", "Transit Overlay"].map((layer, idx) => (
          <button 
            key={idx} 
            onClick={() => setActiveOverlay(layer)}
            className={`flex items-center gap-2 rounded-xl px-3.5 py-2 text-[10px] font-medium transition-all duration-300 ${activeOverlay === layer ? 'bg-emerald-300 text-[#06110e] shadow-[0_4px_18px_rgba(110,231,183,0.24)]' : 'text-slate-400 hover:bg-white/[0.06] hover:text-white'}`}
          >
            {layer === "Road Network" ? <Route className="size-3.5" /> : layer === "Agent Congestion" ? <Users className="size-3.5" /> : <Layers3 className="size-3.5" />}
            {layer}
          </button>
        ))}
      </div>

      {rainIntensity > 0 && (
        <div 
          className="absolute inset-0 pointer-events-none z-[500] rain-effect"
          style={{ 
            opacity: rainIntensity / 100,
            background: 'url("data:image/svg+xml,%3Csvg width=\'20\' height=\'20\' viewBox=\'0 0 20 20\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cpath d=\'M10 20c-5.523 0-10-4.477-10-10s4.477-10 10-10 10 4.477 10 10-4.477 10-10 10zm0-2a8 8 0 100-16 8 8 0 000 16z\' fill=\'%233B82F6\' fill-opacity=\'0.05\' fill-rule=\'evenodd\'/%3E%3C/svg%3E")',
            backgroundSize: '40px 40px'
          }}
        ></div>
      )}
      
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes fall {
          0% { background-position: 0 0; }
          100% { background-position: 20px 100vh; }
        }
        .rain-effect {
          animation: fall 0.5s linear infinite;
          mix-blend-mode: color-dodge;
        }
      `}} />
    </div>
  );
}
