"use client";

import { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";

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

  // Connect to Backend and start Scenario
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/scenarios`)
      .then(res => res.json())
      .then(data => {
        if (data && data.length > 0) {
          // Find the pre-populated monsoon scenario or just take the first one
          const target = data.find((s: any) => s.id.includes("scenario_a")) || data[0];
          setScenarioId(target.id);
          // Start the simulation if it isn't running
          fetch(`${API_BASE}/api/v1/scenarios/${target.id}/start`, { method: 'POST' }).catch(() => {});
        } else {
            // Create one if none exists
            fetch(`${API_BASE}/api/v1/scenarios`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ config: { name: "live_session", city: "delhi", population: 2000, seed: 42 } })
            }).then(res => res.json()).then(target => {
                setScenarioId(target.id);
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
        />
      </div>

      <div className="absolute top-6 left-6 z-[1000] flex gap-4">
        <div className="h-12 px-6 rounded-xl bg-slate-900/90 backdrop-blur-md border border-slate-700 flex flex-col justify-center shadow-lg">
          <h1 className="text-sm font-bold tracking-widest text-emerald-400 m-0">PRAVAAH</h1>
          <p className="text-[10px] text-slate-400 m-0">SIMULATION ENGINE</p>
        </div>
        {backendMetrics && (
          <div className="h-12 px-6 rounded-xl bg-slate-900/90 backdrop-blur-md border border-slate-700 flex items-center gap-6 shadow-lg">
            <div className="flex flex-col">
              <span className="text-[10px] text-slate-400 uppercase tracking-widest">Tick</span>
              <span className="text-sm font-mono text-white">{backendMetrics.tick || 0}</span>
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] text-slate-400 uppercase tracking-widest">AQI</span>
              <span className={`text-sm font-mono ${backendMetrics.aqi_estimate > 150 ? 'text-red-400' : 'text-amber-400'}`}>{backendMetrics.aqi_estimate || '--'}</span>
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] text-slate-400 uppercase tracking-widest">Congestion</span>
              <span className="text-sm font-mono text-white">{((backendMetrics.road_congestion_index || 0) * 100).toFixed(1)}%</span>
            </div>
            <div className="flex flex-col">
              <span className="text-[10px] text-slate-400 uppercase tracking-widest">Commuters</span>
              <span className="text-sm font-mono text-white">{backendMetrics.agents_commuting || 0}</span>
            </div>
          </div>
        )}
      </div>

      <div className="absolute top-6 right-6 z-[1000]">
        <div className="h-12 px-4 rounded-xl bg-slate-900/90 backdrop-blur-md border border-slate-700 flex items-center gap-3 shadow-lg">
          <div className={`animate-pulse w-2 h-2 rounded-full ${wsStatus === 'Live Connected' ? 'bg-emerald-500' : 'bg-red-500'}`}></div>
          <span className={`text-xs font-semibold uppercase tracking-widest ${wsStatus === 'Live Connected' ? 'text-emerald-500' : 'text-red-500'}`}>
            {wsStatus}
          </span>
        </div>
      </div>

      <div className="absolute bottom-6 left-6 z-[1000] w-80 p-6 rounded-2xl bg-slate-900/95 backdrop-blur-xl border border-slate-700 shadow-2xl flex flex-col gap-6">
        <div>
          <h3 className="text-sm font-bold text-white mb-4 uppercase tracking-wider">Policy Injection</h3>
          <div className="flex flex-col gap-4">
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-xs text-slate-300 font-medium">Bus Capacity</span>
                <span className="text-xs font-mono text-emerald-400">{busCapacity}%</span>
              </div>
              <input type="range" min="0" max="100" value={busCapacity} onChange={(e) => setBusCapacity(Number(e.target.value))} onMouseUp={(e: any) => handleBusChange(Number(e.target.value))} onTouchEnd={(e: any) => handleBusChange(Number(e.target.value))} className="w-full h-1 bg-slate-700 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-emerald-500 [&::-webkit-slider-thumb]:rounded-full" />
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-xs text-slate-300 font-medium">Congestion Fee</span>
                <span className="text-xs font-mono text-amber-400">₹{congestionFee}</span>
              </div>
              <input type="range" min="0" max="100" value={congestionFee} onChange={(e) => setCongestionFee(Number(e.target.value))} onMouseUp={(e: any) => handleFeeChange(Number(e.target.value))} onTouchEnd={(e: any) => handleFeeChange(Number(e.target.value))} className="w-full h-1 bg-slate-700 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-amber-500 [&::-webkit-slider-thumb]:rounded-full" />
            </div>
            <div>
              <div className="flex justify-between mb-2">
                <span className="text-xs text-slate-300 font-medium">Rain Intensity</span>
                <span className="text-xs font-mono text-blue-400">{rainIntensity}%</span>
              </div>
              <input type="range" min="0" max="100" value={rainIntensity} onChange={(e) => setRainIntensity(Number(e.target.value))} onMouseUp={(e: any) => handleRainChange(Number(e.target.value))} onTouchEnd={(e: any) => handleRainChange(Number(e.target.value))} className="w-full h-1 bg-slate-700 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:rounded-full" />
            </div>
          </div>
        </div>
      </div>

      <div className="absolute bottom-6 right-6 z-[1000] p-4 rounded-2xl bg-slate-900/90 backdrop-blur-xl border border-slate-700 shadow-2xl flex items-center gap-4">
        <div className="flex flex-col w-64">
          <div className="flex justify-between mb-2 items-center">
            <span className="text-xs font-bold text-white">{formatTime(timeOfDay)}</span>
            <div className="flex gap-2 items-center">
              {isTimeManual && (
                <button 
                  onClick={() => { setIsTimeManual(false); isTimeManualRef.current = false; }} 
                  className="text-[9px] px-2 py-0.5 rounded-full bg-slate-800 text-emerald-400 hover:bg-slate-700 transition-colors"
                >
                  Resume Auto
                </button>
              )}
              <span className="text-[10px] font-mono text-slate-400 uppercase">{timeOfDay >= 6 && timeOfDay <= 18 ? 'Day' : 'Night'}</span>
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
            className="w-full h-1 bg-slate-700 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:bg-emerald-500 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white"
          />
        </div>
      </div>
      
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[1000] flex gap-2 p-2 rounded-2xl bg-slate-900/80 backdrop-blur-xl border border-slate-700 shadow-2xl">
        {["Road Network", "Agent Congestion", "Transit Overlay"].map((layer, idx) => (
          <button 
            key={idx} 
            onClick={() => setActiveOverlay(layer)}
            className={`px-4 py-2 text-xs font-medium rounded-xl transition-colors ${activeOverlay === layer ? 'bg-emerald-500/20 text-emerald-300' : 'text-slate-400 hover:bg-slate-800'}`}
          >
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
