"use client";

import { useEffect, useRef, useState } from "react";
import { LocalSimulator, Mode, GridCell, AggregateMetrics } from "./lib/localSimulator";
import { InsightsPanel } from "./components/InsightsPanel";
import { TutorialOverlay } from "./components/TutorialOverlay";
import { LiquidGlassCard } from "@/components/liquid-glass/LiquidGlassCard";
import { LiquidGlassButton } from "@/components/liquid-glass/LiquidGlassButton";
import {
  Play,
  Pause,
  RotateCcw,
  CloudRain,
  HelpCircle,
  TrendingDown,
  Sparkles,
  Zap,
  TrendingUp,
  Activity,
  AlertOctagon,
  CheckCircle2,
} from "lucide-react";
import dynamic from "next/dynamic";

const ParticleBackground = dynamic(
  () => import("@/components/ui/ParticleBackground").then(mod => mod.ParticleBackground),
  { ssr: false }
);

const MapSimulation = dynamic(
  () => import("./components/MapSimulation"),
  { ssr: false }
);

interface Challenge {
  id: string;
  name: string;
  description: string;
  objective: string;
  setup: (sim: LocalSimulator) => void;
  checkGoal: (metrics: AggregateMetrics, disabledMetroLines: Set<string>, busCapacity: number, fuelTax: number) => boolean;
}

const CHALLENGES: Challenge[] = [
  {
    id: "monsoon",
    name: "Challenge 1: Monsoon Storm",
    description: "Heavy rain is causing gridlock. Citizens are abandoning bikes and walking.",
    objective: "Enact a public transit boost (set Bus Capacity to 150%) to absorb commuters and keep the Congestion Index under 0.65.",
    setup: (sim) => {
      sim.reset();
      sim.rain = 0.85;
      sim.busCapacityPct = 1.0;
      sim.fuelPriceDeltaPaise = 0;
    },
    checkGoal: (metrics, _lines, busCap) => {
      return metrics.rain_intensity >= 0.8 && busCap >= 1.45 && metrics.road_congestion_index <= 0.65;
    },
  },
  {
    id: "decarbonize",
    name: "Challenge 2: Decarbonization",
    description: "Commuters driving combustion private cars are raising Rajiv Chowk's AQI estimate past healthy levels.",
    objective: "Trigger a shift to electric metro and micro-mobility by raising the Carbon Fuel Tax (set Fuel Levy ₹100 or above). Bring AQI below 150.",
    setup: (sim) => {
      sim.reset();
      sim.rain = 0.0;
      sim.busCapacityPct = 1.0;
      sim.fuelPriceDeltaPaise = 0;
    },
    checkGoal: (metrics, _lines, _busCap, fuelTax) => {
      return fuelTax >= 10000 && metrics.aqi_estimate <= 150;
    },
  },
  {
    id: "metro_resilience",
    name: "Challenge 3: Metro Line Outage",
    description: "The DMRC Yellow Line is undergoing emergency maintenance. Commuters are stranded.",
    objective: "Toggle the DMRC Yellow Line shutdown, and mitigate the delay by boosting bus capacity to 140% or above.",
    setup: (sim) => {
      sim.reset();
      sim.rain = 0.0;
      sim.busCapacityPct = 1.0;
      sim.disabledMetroLines.add("Yellow");
      sim.fuelPriceDeltaPaise = 0;
    },
    checkGoal: (_metrics, lines, busCap) => {
      return lines.has("Yellow") && busCap >= 1.35;
    },
  },
];

export default function DemoPage() {
  const simRef = useRef<LocalSimulator | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [tick, setTick] = useState(0);
  const [metrics, setMetrics] = useState<AggregateMetrics | null>(null);
  const [grid, setGrid] = useState<GridCell[]>([]);
  const [timeStr, setTimeStr] = useState("08:00 AM");

  // Policy state hooks for sliders
  const [rainInput, setRainInput] = useState(0);
  const [busCapInput, setBusCapInput] = useState(100);
  const [fuelInput, setFuelInput] = useState(0);
  const [yellowLineDisabled, setYellowLineDisabled] = useState(false);
  const [blueLineDisabled, setBlueLineDisabled] = useState(false);

  // Tutorial and challenge states
  const [isTourOpen, setIsTourOpen] = useState(false);
  const [tourStep, setTourStep] = useState(0);
  const [activeChallengeId, setActiveChallengeId] = useState<string | null>(null);
  const [challengeSuccess, setChallengeSuccess] = useState(false);

  // History for sparklines
  const [commuteHistory, setCommuteHistory] = useState<number[]>([]);
  const [aqiHistory, setAqiHistory] = useState<number[]>([]);

  // Backend Integration States
  const [connectionMode, setConnectionMode] = useState<"local" | "backend" | "connecting">("connecting");
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [selectedControlCategory, setSelectedControlCategory] = useState<"all" | "weather" | "transit" | "taxation">("all");
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "https://urban-policy-simulation.onrender.com";

  // Helper to send backend events
  const injectEvent = async (type: string, payload: any) => {
    if (connectionMode === "backend" && scenarioId) {
      try {
        const cleanUrl = backendUrl.endsWith("/") ? backendUrl.slice(0, -1) : backendUrl;
        await fetch(`${cleanUrl}/api/v1/scenarios/${scenarioId}/events`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ type, payload }),
        });
      } catch (err) {
        console.error("Failed to inject event to backend:", err);
      }
    }
  };

  // Initialize simulator (attempts backend connection, falls back to local)
  useEffect(() => {
    let ws: WebSocket | null = null;
    let active = true;

    const initSimulation = async () => {
      // 1. Create fallback local simulator in case backend is offline
      const localSim = new LocalSimulator(15000);
      simRef.current = localSim;

      const cleanUrl = backendUrl.endsWith("/") ? backendUrl.slice(0, -1) : backendUrl;

      try {
        // Test health endpoint
        const healthRes = await fetch(`${cleanUrl}/api/v1/health`, { signal: AbortSignal.timeout(3000) });
        if (!healthRes.ok) throw new Error("Health check failed");

        // Create backend scenario
        const createRes = await fetch(`${cleanUrl}/api/v1/scenarios`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            config: {
              name: `strata_sandbox_${Math.random().toString(36).substring(7)}`,
              city: "delhi",
              population: 15000,
              seed: 42,
              tick_minutes: 5,
              params: {},
            },
          }),
        });

        if (!createRes.ok) throw new Error("Failed to create scenario");
        const scData = await createRes.json();
        const scId = scData.id;

        // Fetch initial snapshot to populate grid
        const snapRes = await fetch(`${cleanUrl}/api/v1/scenarios/${scId}/snapshot`);
        if (!snapRes.ok) throw new Error("Failed to fetch initial snapshot");
        const snapData = await snapRes.json();

        if (!active) return;
        setScenarioId(scId);
        setGrid(snapData.grid);
        setMetrics(snapData.metrics);
        setConnectionMode("backend");

        // Connect WebSocket
        const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsHost = cleanUrl.replace(/^https?:\/\//, "");
        const wsUrl = `${wsProtocol}//${wsHost}/ws/scenarios/${scId}`;

        ws = new WebSocket(wsUrl);

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "tick" && data.diff) {
              const diff = data.diff;
              setTick(diff.tick);
              setMetrics(diff.metrics);
              
              // Merge changed cells into grid
              setGrid((prevGrid) => {
                const nextGrid = [...prevGrid];
                diff.changed_cells.forEach((cell: any) => {
                  let bestIdx = -1;
                  let minDist = Infinity;
                  for (let i = 0; i < nextGrid.length; i++) {
                    const d = Math.pow(nextGrid[i].lat - cell.lat, 2) + Math.pow(nextGrid[i].lon - cell.lon, 2);
                    if (d < minDist) {
                      minDist = d;
                      bestIdx = i;
                    }
                  }
                  if (bestIdx !== -1 && minDist < 0.0001) {
                    nextGrid[bestIdx] = cell;
                  }
                });
                return nextGrid;
              });

              // Format time
              const minutes = (diff.tick * 5) % (24 * 60);
              const hour = Math.floor(minutes / 60);
              const min = Math.floor(minutes % 60);
              const ampm = hour >= 12 ? "PM" : "AM";
              const displayHour = hour % 12 === 0 ? 12 : hour % 12;
              const displayMin = min < 10 ? `0${min}` : min;
              setTimeStr(`${displayHour}:${displayMin} ${ampm}`);

              setCommuteHistory((prev) => [...prev.slice(-19), diff.metrics.avg_commute_minutes]);
              setAqiHistory((prev) => [...prev.slice(-19), diff.metrics.aqi_estimate]);
            } else if (data.type === "status") {
              setIsPlaying(data.status === "running");
            }
          } catch (err) {
            console.error("Error parsing websocket message:", err);
          }
        };

        ws.onclose = () => {
          console.warn("WebSocket closed. Switching to local fallback.");
          if (active) setConnectionMode("local");
        };

        ws.onerror = () => {
          console.error("WebSocket error. Switching to local fallback.");
          if (active) setConnectionMode("local");
        };

      } catch (err) {
        console.warn("Could not connect to Strata backend. Using local simulation engine.", err);
        if (active) {
          const snap = localSim.snapshot();
          setGrid(snap.grid);
          setMetrics(snap.metrics);
          setTimeStr(localSim.getFormattedTime());
          setConnectionMode("local");
        }
      }

      // Auto open guide tour
      setIsTourOpen(true);
    };

    initSimulation();

    return () => {
      active = false;
      if (ws) ws.close();
    };
  }, []);

  // Local Tick step trigger (only runs if offline)
  useEffect(() => {
    if (!isPlaying || connectionMode !== "local") return;

    const interval = setInterval(() => {
      if (simRef.current) {
        const snap = simRef.current.step();
        setTick(snap.tick);
        setMetrics(snap.metrics);
        setGrid(snap.grid);
        setTimeStr(simRef.current.getFormattedTime());

        setCommuteHistory((prev) => [...prev.slice(-19), snap.metrics.avg_commute_minutes]);
        setAqiHistory((prev) => [...prev.slice(-19), snap.metrics.aqi_estimate]);
      }
    }, 450);

    return () => clearInterval(interval);
  }, [isPlaying, connectionMode]);

  // Sync state parameters to simulator or backend
  useEffect(() => {
    if (connectionMode === "local") {
      const sim = simRef.current;
      if (!sim) return;

      sim.rain = rainInput / 100;
      sim.busCapacityPct = busCapInput / 100;
      sim.fuelPriceDeltaPaise = fuelInput * 100;

      const disabled = new Set<string>();
      if (yellowLineDisabled) disabled.add("Yellow");
      if (blueLineDisabled) disabled.add("Blue");
      sim.disabledMetroLines = disabled;

      const snap = sim.snapshot();
      setMetrics(snap.metrics);
      setGrid(snap.grid);
    } else if (connectionMode === "backend") {
      injectEvent("WEATHER_EVENT", { rain_intensity: rainInput / 100, duration_ticks: 120 });
      injectEvent("POLICY_EVENT", { bus_capacity_pct: busCapInput / 100, fuel_price_delta_paise: fuelInput * 100 });
      
      if (yellowLineDisabled) {
        injectEvent("INFRASTRUCTURE_EVENT", { disable_metro_line: "yellow" });
      } else {
        injectEvent("INFRASTRUCTURE_EVENT", { enable_metro_line: "yellow" });
      }
      
      if (blueLineDisabled) {
        injectEvent("INFRASTRUCTURE_EVENT", { disable_metro_line: "blue" });
      } else {
        injectEvent("INFRASTRUCTURE_EVENT", { enable_metro_line: "blue" });
      }
    }
  }, [rainInput, busCapInput, fuelInput, yellowLineDisabled, blueLineDisabled, connectionMode, scenarioId]);

  // Evaluate challenge checks
  useEffect(() => {
    if (!activeChallengeId || !metrics) return;

    const challenge = CHALLENGES.find((c) => c.id === activeChallengeId);
    if (challenge) {
      const disabled = new Set<string>();
      if (yellowLineDisabled) disabled.add("Yellow");
      if (blueLineDisabled) disabled.add("Blue");

      const isSuccess = challenge.checkGoal(
        metrics,
        disabled,
        busCapInput / 100,
        fuelInput * 100
      );
      setChallengeSuccess(isSuccess);
    }
  }, [metrics, activeChallengeId, yellowLineDisabled, blueLineDisabled, rainInput, busCapInput, fuelInput]);

  const togglePlay = async () => {
    if (connectionMode === "backend" && scenarioId) {
      try {
        const cleanUrl = backendUrl.endsWith("/") ? backendUrl.slice(0, -1) : backendUrl;
        const endpoint = isPlaying ? "pause" : "resume";
        const res = await fetch(`${cleanUrl}/api/v1/scenarios/${scenarioId}/${endpoint}`, { method: "POST" });
        if (res.ok) {
          setIsPlaying(!isPlaying);
        }
      } catch (err) {
        console.error("Failed to toggle play state on backend:", err);
      }
    } else {
      setIsPlaying(!isPlaying);
    }
  };

  const triggerReset = async () => {
    if (connectionMode === "backend" && scenarioId) {
      try {
        const cleanUrl = backendUrl.endsWith("/") ? backendUrl.slice(0, -1) : backendUrl;
        const res = await fetch(`${cleanUrl}/api/v1/scenarios/${scenarioId}/reset`, { method: "POST" });
        if (res.ok) {
          const snapRes = await fetch(`${cleanUrl}/api/v1/scenarios/${scenarioId}/snapshot`);
          if (snapRes.ok) {
            const snapData = await snapRes.json();
            setTick(snapData.tick);
            setMetrics(snapData.metrics);
            setGrid(snapData.grid);
            setTimeStr("08:00 AM");
            setIsPlaying(false);
          }
        }
      } catch (err) {
        console.error("Failed to reset backend scenario:", err);
      }
    } else if (simRef.current) {
      simRef.current.reset();
      const snap = simRef.current.snapshot();
      setTick(snap.tick);
      setMetrics(snap.metrics);
      setGrid(snap.grid);
      setTimeStr(simRef.current.getFormattedTime());
      setIsPlaying(false);
    }

    setRainInput(0);
    setBusCapInput(100);
    setFuelInput(0);
    setYellowLineDisabled(false);
    setBlueLineDisabled(false);
    setActiveChallengeId(null);
    setChallengeSuccess(false);
    setCommuteHistory([]);
    setAqiHistory([]);
  };

  const loadChallenge = async (challenge: Challenge) => {
    if (connectionMode === "backend" && scenarioId) {
      try {
        const cleanUrl = backendUrl.endsWith("/") ? backendUrl.slice(0, -1) : backendUrl;
        await fetch(`${cleanUrl}/api/v1/scenarios/${scenarioId}/reset`, { method: "POST" });

        if (challenge.id === "monsoon") {
          await fetch(`${cleanUrl}/api/v1/scenarios/${scenarioId}/events`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              type: "WEATHER_EVENT",
              payload: { rain_intensity: 0.85, duration_ticks: 120 }
            })
          });
          setRainInput(85);
          setBusCapInput(100);
          setFuelInput(0);
          setYellowLineDisabled(false);
          setBlueLineDisabled(false);
        } else if (challenge.id === "decarbonize") {
          setRainInput(0);
          setBusCapInput(100);
          setFuelInput(0);
          setYellowLineDisabled(false);
          setBlueLineDisabled(false);
        } else if (challenge.id === "metro_resilience") {
          await fetch(`${cleanUrl}/api/v1/scenarios/${scenarioId}/events`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              type: "INFRASTRUCTURE_EVENT",
              payload: { disable_metro_line: "yellow" }
            })
          });
          setRainInput(0);
          setBusCapInput(100);
          setFuelInput(0);
          setYellowLineDisabled(true);
          setBlueLineDisabled(false);
        }

        setActiveChallengeId(challenge.id);
        setChallengeSuccess(false);
        setCommuteHistory([]);
        setAqiHistory([]);

        await fetch(`${cleanUrl}/api/v1/scenarios/${scenarioId}/resume`, { method: "POST" });
        setIsPlaying(true);
      } catch (err) {
        console.error("Failed to load challenge on backend:", err);
      }
    } else if (simRef.current) {
      challenge.setup(simRef.current);
      setActiveChallengeId(challenge.id);
      setChallengeSuccess(false);

      setRainInput(simRef.current.rain * 100);
      setBusCapInput(simRef.current.busCapacityPct * 100);
      setFuelInput(simRef.current.fuelPriceDeltaPaise / 100);
      setYellowLineDisabled(simRef.current.disabledMetroLines.has("Yellow"));
      setBlueLineDisabled(simRef.current.disabledMetroLines.has("Blue"));

      const snap = simRef.current.snapshot();
      setTick(snap.tick);
      setMetrics(snap.metrics);
      setGrid(snap.grid);
      setTimeStr(simRef.current.getFormattedTime());
      setIsPlaying(true);
    }
  };  return (
    <main className="relative w-full h-screen text-white font-sans overflow-hidden selection:bg-purple-500/30 bg-[#070505] flex flex-col">
      {/* GL particles backdrop */}
      <ParticleBackground />

      {/* Main dashboard grid container */}
      <div className="relative z-10 w-full max-w-[95rem] mx-auto px-2 py-1.5 flex flex-col h-full overflow-hidden gap-2 flex-grow">
        
        {/* Top Header Bar */}
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-1.5 border-b border-white/5 pb-1 shrink-0">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-1.5 py-0.5 rounded text-[9px] font-mono tracking-widest text-purple-400 bg-purple-950/45 border border-purple-500/30">
                DECISION SANDBOX
              </span>
              {connectionMode === "connecting" && (
                <>
                  <span className="w-1 h-1 rounded-full bg-amber-400 animate-pulse" />
                  <span className="text-[9px] font-mono text-amber-400/80">Connecting...</span>
                </>
              )}
              {connectionMode === "backend" && (
                <>
                  <span className="w-1 h-1 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-[9px] font-mono text-emerald-400/90">Strata Engine Connected</span>
                </>
              )}
              {connectionMode === "local" && (
                <>
                  <span className="w-1 h-1 rounded-full bg-orange-400 animate-pulse" />
                  <span className="text-[9px] font-mono text-stone-400">Offline (Local Fallback)</span>
                </>
              )}
            </div>
            <h1 className="text-lg font-light tracking-tight mt-0 text-white">
              STRATA <span className="text-stone-500 font-extralight">| Command Center</span>
            </h1>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={() => {
                setTourStep(0);
                setIsTourOpen(true);
              }}
              className="flex items-center gap-1 px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-stone-300 text-[10px] font-light transition-all border border-white/5 cursor-pointer"
            >
              <HelpCircle className="w-3.5 h-3.5 text-purple-400" />
              Guide Tour
            </button>
            <LiquidGlassButton
              onClick={triggerReset}
              className="rounded-lg px-2.5 py-1 text-[10px] font-semibold"
            >
              <span className="flex items-center gap-1">
                <RotateCcw className="w-3 h-3" />
                Reset Board
              </span>
            </LiquidGlassButton>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-2 items-stretch flex-grow min-h-0">
          
          {/* LEFT PANEL: Policy Controls (lg:col-span-3) */}
          <section className="lg:col-span-3 flex flex-col gap-2 h-full overflow-y-auto pr-0.5 select-none scrollbar-thin">
            
            {/* Simulation Engine Controls */}
            <LiquidGlassCard className="p-2.5 shrink-0" variant="default">
              <div className="flex items-center justify-between font-mono text-[10px]">
                <div className="flex items-center gap-1">
                  <Activity className="w-3 h-3 text-purple-400" />
                  <span className="font-semibold text-stone-300">Engine Status</span>
                </div>
                <span className="text-[9px] text-stone-500 font-mono">TICK {tick}</span>
              </div>

              <div className="flex items-center justify-between gap-1.5 mt-2 bg-stone-900/60 p-2 rounded-lg border border-white/5">
                <span className="text-[10px] font-mono text-stone-400">SIM TIME:</span>
                <span className="text-[10px] font-mono text-purple-400 font-bold">{timeStr}</span>
              </div>

              <div className="flex mt-2">
                <LiquidGlassButton
                  onClick={togglePlay}
                  className="w-full rounded-lg py-1.5 justify-center text-[11px] font-bold"
                >
                  {isPlaying ? (
                    <span className="flex items-center gap-1">
                      <Pause className="w-3.5 h-3.5 fill-current" /> Pause Simulation
                    </span>
                  ) : (
                    <span className="flex items-center gap-1">
                      <Play className="w-3.5 h-3.5 fill-current" /> Run Simulation
                    </span>
                  )}
                </LiquidGlassButton>
              </div>
            </LiquidGlassCard>

            {/* Environmental & Interventions */}
            <LiquidGlassCard className="p-2.5 flex-grow flex flex-col gap-3 overflow-hidden" variant="default">
              <div className="flex flex-col gap-1 shrink-0">
                <span className="text-[9px] font-mono text-stone-500 uppercase block font-semibold">Select Control Category</span>
                <select
                  value={selectedControlCategory}
                  onChange={(e) => setSelectedControlCategory(e.target.value as any)}
                  className="w-full px-2 py-1 text-[11px] bg-stone-900 border border-white/10 rounded-lg text-stone-300 focus:outline-none focus:border-purple-500/50 cursor-pointer"
                >
                  <option value="all">All Controls</option>
                  <option value="weather">Weather Events</option>
                  <option value="transit">Transit & Scheduling</option>
                  <option value="taxation">Taxation & Levies</option>
                </select>
              </div>

              <div className="flex-grow flex flex-col gap-3 overflow-y-auto pr-0.5">
                {(selectedControlCategory === "all" || selectedControlCategory === "weather") && (
                  <div className="border-t border-white/5 pt-2.5 first:border-0 first:pt-0">
                    <h2 className="text-[10px] font-bold font-mono tracking-wider text-stone-300 uppercase mb-2 flex items-center gap-1">
                      <CloudRain className="w-3.5 h-3.5 text-sky-400" />
                      Weather Events
                    </h2>
                    
                    <div className="space-y-2">
                      <div>
                        <div className="flex justify-between text-[11px] mb-0.5">
                          <span className="font-light text-stone-400">Monsoon Rain Intensity</span>
                          <span className="font-mono text-purple-400 font-semibold">{rainInput}%</span>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max="100"
                          value={rainInput}
                          onChange={(e) => setRainInput(Number(e.target.value))}
                          className="w-full h-1 bg-stone-800 rounded-lg appearance-none cursor-pointer accent-purple-400"
                        />
                        <div className="flex justify-between text-[8px] text-stone-500 mt-0.5 font-mono">
                          <span>Dry</span>
                          <span>Downpour</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {(selectedControlCategory === "all" || selectedControlCategory === "transit" || selectedControlCategory === "taxation") && (
                  <div className="border-t border-white/5 pt-2.5 first:border-0 first:pt-0">
                    <h2 className="text-[10px] font-bold font-mono tracking-wider text-stone-300 uppercase mb-2 flex items-center gap-1">
                      <Zap className="w-3.5 h-3.5 text-purple-400" />
                      Policy Interventions
                    </h2>

                    <div className="space-y-3">
                      {/* Bus capacity boost */}
                      {(selectedControlCategory === "all" || selectedControlCategory === "transit") && (
                        <div>
                          <div className="flex justify-between text-[11px] mb-0.5">
                            <span className="font-light text-stone-400">Bus Capacity Level</span>
                            <span className="font-mono text-purple-400 font-semibold">{busCapInput}%</span>
                          </div>
                          <input
                            type="range"
                            min="50"
                            max="150"
                            value={busCapInput}
                            onChange={(e) => setBusCapInput(Number(e.target.value))}
                            className="w-full h-1 bg-stone-800 rounded-lg appearance-none cursor-pointer accent-purple-400"
                          />
                          <div className="flex justify-between text-[8px] text-stone-500 mt-0.5 font-mono">
                            <span>50% Choked</span>
                            <span>150% Boosted</span>
                          </div>
                        </div>
                      )}

                      {/* Fuel tax */}
                      {(selectedControlCategory === "all" || selectedControlCategory === "taxation") && (
                        <div>
                          <div className="flex justify-between text-[11px] mb-0.5">
                            <span className="font-light text-stone-400">Carbon Fuel Levy</span>
                            <span className="font-mono text-purple-400 font-semibold">₹{fuelInput}/L</span>
                          </div>
                          <input
                            type="range"
                            min="0"
                            max="200"
                            value={fuelInput}
                            onChange={(e) => setFuelInput(Number(e.target.value))}
                            className="w-full h-1 bg-stone-800 rounded-lg appearance-none cursor-pointer accent-purple-400"
                          />
                          <div className="flex justify-between text-[8px] text-stone-500 mt-0.5 font-mono">
                            <span>No Levy</span>
                            <span>₹200/L Tax</span>
                          </div>
                        </div>
                      )}

                      {/* Metro shutdown toggles */}
                      {(selectedControlCategory === "all" || selectedControlCategory === "transit") && (
                        <div className="pt-2 border-t border-white/5 space-y-1.5">
                          <span className="text-[9px] font-mono text-stone-500 uppercase block">Transit Line Health</span>
                          
                          <label className="flex items-center justify-between text-[11px] font-light text-stone-400 cursor-pointer p-0.5 px-1 rounded hover:bg-white/5 transition-colors">
                            <span>Yellow Line Outage</span>
                            <input
                              type="checkbox"
                              checked={yellowLineDisabled}
                              onChange={(e) => setYellowLineDisabled(e.target.checked)}
                              className="rounded border-white/10 text-purple-500 focus:ring-0 focus:ring-offset-0 bg-stone-900 w-3 h-3 cursor-pointer accent-purple-500"
                            />
                          </label>

                          <label className="flex items-center justify-between text-[11px] font-light text-stone-400 cursor-pointer p-0.5 px-1 rounded hover:bg-white/5 transition-colors">
                            <span>Blue Line Outage</span>
                            <input
                              type="checkbox"
                              checked={blueLineDisabled}
                              onChange={(e) => setBlueLineDisabled(e.target.checked)}
                              className="rounded border-white/10 text-purple-500 focus:ring-0 focus:ring-offset-0 bg-stone-900 w-3 h-3 cursor-pointer accent-purple-500"
                            />
                          </label>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </LiquidGlassCard>
          </section>

          {/* CENTER PANEL: Canvas Map & Insights (lg:col-span-5) */}
          <section className="lg:col-span-5 flex flex-col gap-2 h-full overflow-hidden">
            
            {/* Visual network simulator */}
            <MapSimulation
              grid={grid}
              rainIntensity={rainInput / 100}
              roadCongestion={metrics?.road_congestion_index || 0}
              isPlaying={isPlaying}
              timeOfDay={timeStr}
            />

            {/* Simulated AI insights explaining causality */}
            {metrics && (
              <div className="h-[150px] shrink-0 overflow-y-auto">
                <InsightsPanel
                  metrics={metrics}
                  disabledMetroLines={
                    new Set(
                      [yellowLineDisabled ? "Yellow" : "", blueLineDisabled ? "Blue" : ""].filter(Boolean)
                    )
                  }
                  busCapacityPct={busCapInput / 100}
                  fuelPriceDeltaPaise={fuelInput * 100}
                />
              </div>
            )}
          </section>

          {/* RIGHT PANEL: Live Telemetry Metrics & Challenges (lg:col-span-4) */}
          <section className="lg:col-span-4 flex flex-col gap-2 h-full overflow-y-auto pr-0.5">
            
            {/* Core gauges */}
            <LiquidGlassCard className="p-2.5 shrink-0" variant="default">
              <h2 className="text-[10px] font-mono tracking-widest text-stone-400 uppercase mb-2 flex items-center gap-1.5 font-semibold">
                <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                Live City Telemetry
              </h2>

              {metrics && (
                <div className="grid grid-cols-2 gap-2">
                  {/* Commute time metric */}
                  <div className="p-2 bg-stone-900/60 rounded-lg border border-white/5 flex flex-col justify-between">
                    <span className="text-[8px] font-mono text-stone-500 uppercase">Avg Commute</span>
                    <div className="my-0.5 flex items-baseline">
                      <span className="text-lg font-light text-white font-mono">
                        {metrics.avg_commute_minutes}
                      </span>
                      <span className="text-[8px] text-stone-500 ml-0.5">mins</span>
                    </div>
                    {/* Commute sparkline */}
                    <div className="h-4 flex items-end gap-0.5 pt-0.5">
                      {commuteHistory.map((val, i) => (
                        <div
                          key={i}
                          style={{ height: `${Math.min(100, (val / 80) * 100)}%` }}
                          className="flex-1 min-w-[1.5px] bg-purple-400/60 rounded-sm"
                        />
                      ))}
                    </div>
                  </div>

                  {/* AQI metric */}
                  <div className="p-2 bg-stone-900/60 rounded-lg border border-white/5 flex flex-col justify-between">
                    <span className="text-[8px] font-mono text-stone-500 uppercase">AQI Estimate</span>
                    <div className="my-0.5 flex items-baseline justify-between">
                      <span className="text-lg font-light text-white font-mono">
                        {metrics.aqi_estimate}
                      </span>
                      <span
                        className={`text-[7px] font-mono px-1 py-0.2 rounded font-semibold ${
                          metrics.aqi_estimate > 200
                            ? "bg-red-950/45 text-red-400 border border-red-500/20"
                            : metrics.aqi_estimate > 100
                            ? "bg-amber-950/45 text-amber-400 border border-amber-500/20"
                            : "bg-emerald-950/45 text-emerald-400 border border-emerald-500/20"
                        }`}
                      >
                        {metrics.aqi_estimate > 200 ? "POOR" : metrics.aqi_estimate > 100 ? "MOD" : "GOOD"}
                      </span>
                    </div>
                    {/* AQI sparkline */}
                    <div className="h-4 flex items-end gap-0.5 pt-0.5">
                      {aqiHistory.map((val, i) => (
                        <div
                          key={i}
                          style={{ height: `${Math.min(100, (val / 350) * 100)}%` }}
                          className={`flex-1 min-w-[1.5px] rounded-sm ${
                            val > 200 ? "bg-red-400/60" : val > 100 ? "bg-amber-400/60" : "bg-emerald-400/60"
                          }`}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Road Congestion metric */}
                  <div className="p-2 bg-stone-900/60 rounded-lg border border-white/5 col-span-2">
                    <div className="flex justify-between items-center text-[8px] font-mono text-stone-500 uppercase mb-0.5">
                      <span>Road Congestion Index</span>
                      <span className="text-white font-semibold font-mono">
                        {Math.round(metrics.road_congestion_index * 100)}%
                      </span>
                    </div>
                    <div className="w-full h-1 bg-stone-850 rounded-full overflow-hidden">
                      <div
                        style={{ width: `${metrics.road_congestion_index * 100}%` }}
                        className={`h-full transition-all duration-300 ${
                          metrics.road_congestion_index > 0.65
                            ? "bg-red-500"
                            : metrics.road_congestion_index > 0.4
                            ? "bg-amber-500"
                            : "bg-emerald-500"
                        }`}
                      />
                    </div>
                  </div>

                  {/* Metro and Bus loads */}
                  <div className="p-2 bg-stone-900/60 rounded-lg border border-white/5">
                    <div className="flex justify-between items-center text-[8px] font-mono text-stone-500 uppercase mb-0.5">
                      <span>Metro Load</span>
                      <span className="text-sky-400 font-mono font-medium">
                        {Math.round(metrics.metro_load_pct)}%
                      </span>
                    </div>
                    <div className="w-full h-1 bg-stone-850 rounded-full overflow-hidden">
                      <div
                        style={{ width: `${Math.min(100, metrics.metro_load_pct)}%` }}
                        className={`h-full ${metrics.metro_load_pct > 90 ? "bg-red-400" : "bg-sky-400"}`}
                      />
                    </div>
                  </div>

                  <div className="p-2 bg-stone-900/60 rounded-lg border border-white/5">
                    <div className="flex justify-between items-center text-[8px] font-mono text-stone-500 uppercase mb-0.5">
                      <span>Bus Load</span>
                      <span className="text-emerald-400 font-mono font-medium">
                        {Math.round(metrics.bus_load_pct)}%
                      </span>
                    </div>
                    <div className="w-full h-1 bg-stone-850 rounded-full overflow-hidden">
                      <div
                        style={{ width: `${Math.min(100, metrics.bus_load_pct)}%` }}
                        className={`h-full ${metrics.bus_load_pct > 90 ? "bg-red-400" : "bg-emerald-400"}`}
                      />
                    </div>
                  </div>
                </div>
              )}
            </LiquidGlassCard>

            {/* Mode share distribution & Challenges (side-by-side or stacked in a scroll area) */}
            <div className="flex flex-col gap-2 flex-grow min-h-0">
              
              {/* Mode share distribution */}
              <LiquidGlassCard className="p-2.5 shrink-0" variant="default">
                <h2 className="text-[10px] font-mono tracking-widest text-stone-400 uppercase mb-2 flex items-center gap-1 font-semibold">
                  <Activity className="w-3 h-3 text-purple-400" />
                  Mode Share Distribution
                </h2>

                {metrics && (
                  <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                    {[
                      { label: "DMRC Metro", val: metrics.mode_share[Mode.metro] || 0, color: "bg-blue-400" },
                      { label: "Municipal Bus", val: metrics.mode_share[Mode.bus] || 0, color: "bg-emerald-400" },
                      { label: "Private Auto", val: metrics.mode_share[Mode.car] || 0, color: "bg-red-400" },
                      { label: "Auto-Rickshaw", val: metrics.mode_share[Mode.auto] || 0, color: "bg-amber-400" },
                      { label: "Walking/Micro", val: (metrics.mode_share[Mode.walk] || 0) + (metrics.mode_share[Mode.bike] || 0) + (metrics.mode_share[Mode.bike_share] || 0) + (metrics.mode_share[Mode.e_rickshaw] || 0), color: "bg-purple-400" },
                    ]
                      .sort((a, b) => b.val - a.val)
                      .map((item, i) => (
                        <div key={i} className="text-[10px]">
                          <div className="flex justify-between font-light mb-0.5">
                            <span className="text-stone-300 truncate max-w-[75px]">{item.label}</span>
                            <span className="font-mono text-stone-400">{Math.round(item.val * 100)}%</span>
                          </div>
                          <div className="w-full h-1 bg-stone-900 rounded-full overflow-hidden">
                            <div style={{ width: `${item.val * 100}%` }} className={`h-full ${item.color}`} />
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </LiquidGlassCard>

              {/* Curated Challenges preset box */}
              <LiquidGlassCard className="p-2.5 border-purple-500/20 flex-grow flex flex-col min-h-[200px] overflow-hidden" variant="chrome">
                <h2 className="text-xs font-mono tracking-widest text-purple-400 uppercase mb-2 flex items-center gap-1 font-bold shrink-0">
                  <Zap className="w-3.5 h-3.5 text-purple-400" />
                  Policy Challenges
                </h2>

                <div className="flex flex-col gap-2 flex-grow overflow-hidden">
                  <div className="flex flex-col gap-1 shrink-0">
                    <span className="text-[9px] font-mono text-stone-500 uppercase block font-semibold animate-pulse">Active Scenario Preset</span>
                    <select
                      value={activeChallengeId || "sandbox"}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === "sandbox") {
                          triggerReset();
                        } else {
                          const challenge = CHALLENGES.find(c => c.id === val);
                          if (challenge) loadChallenge(challenge);
                        }
                      }}
                      className="w-full px-2 py-1 text-[11px] bg-stone-900 border border-white/10 rounded-lg text-stone-300 focus:outline-none focus:border-purple-500/50 cursor-pointer"
                    >
                      <option value="sandbox">Sandbox Mode (Free Play)</option>
                      {CHALLENGES.map(c => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  </div>

                  <div className="flex-grow overflow-y-auto flex flex-col gap-2 pr-0.5">
                    {activeChallengeId ? (() => {
                      const challenge = CHALLENGES.find(c => c.id === activeChallengeId);
                      if (!challenge) return null;
                      return (
                        <div className="bg-stone-900/40 border border-purple-500/20 p-2.5 rounded-xl flex-grow flex flex-col justify-between">
                          <div>
                            <h3 className="text-[11px] font-semibold text-white mb-1 font-mono">
                              {challenge.name}
                            </h3>
                            <p className="text-[10px] text-stone-400 font-light leading-relaxed mb-2">
                              {challenge.description}
                            </p>
                          </div>
                          <div className="pt-2 border-t border-purple-500/20 bg-purple-950/30 -mx-2.5 -mb-2.5 p-2.5 rounded-b-xl">
                            <span className="text-[8px] font-mono text-purple-300 uppercase block font-bold mb-0.5">
                              OBJECTIVE:
                            </span>
                            <span className="text-[10px] font-light text-stone-300 leading-relaxed block mb-2">
                              {challenge.objective}
                            </span>

                            <div className="flex items-center gap-1">
                              {challengeSuccess ? (
                                <div className="flex items-center gap-1 text-emerald-400 text-[10px] font-bold font-mono">
                                  <CheckCircle2 className="w-3 h-3 shrink-0" />
                                  Goal Met! Success.
                                </div>
                              ) : (
                                <div className="flex items-center gap-1 text-amber-400 text-[10px] font-bold font-mono animate-pulse">
                                  <AlertOctagon className="w-3 h-3 shrink-0" />
                                  Monitoring criteria...
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })() : (
                      <div className="border border-white/5 bg-stone-900/20 p-3 rounded-xl flex-grow flex flex-col items-center justify-center text-center">
                        <Sparkles className="w-6 h-6 text-purple-500/35 mb-1.5" />
                        <span className="text-[10px] text-stone-400 font-light leading-relaxed">
                          Free Play sandbox is active. Select a scenario challenge from the dropdown above to test specific policy criteria.
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </LiquidGlassCard>
            </div>

          </section>

        </div>

      </div>

      {/* Guided Walkthrough Overlay */}
      <TutorialOverlay
        isOpen={isTourOpen}
        onClose={() => setIsTourOpen(false)}
        currentStep={tourStep}
        setCurrentStep={setTourStep}
      />
    </main>
  );
}
