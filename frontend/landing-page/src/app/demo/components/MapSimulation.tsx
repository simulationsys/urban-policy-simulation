"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { GridCell } from "../lib/localSimulator";

interface MapSimulationProps {
  grid: GridCell[];
  rainIntensity: number;
  roadCongestion: number;
  isPlaying: boolean;
  timeOfDay: string;
}

interface MapParticle {
  progress: number;
  speed: number;
  type: "delivery" | "citizen";
  pathType: "metro" | "radial" | "concentric";
  lineIndex: number;
  direction: 1 | -1;
  lat: number;
  lon: number;
}

export default function MapSimulation({
  grid,
  rainIntensity,
  roadCongestion,
  isPlaying,
  timeOfDay,
}: MapSimulationProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const mapLoadedRef = useRef(false);
  const particlesRef = useRef<MapParticle[]>([]);

  // Token management & fallback state
  const [hasMapboxToken, setHasMapboxToken] = useState<boolean | null>(null);
  const [showTokenModal, setShowTokenModal] = useState(false);
  const [tokenInput, setTokenInput] = useState("");
  const [tokenSaved, setTokenSaved] = useState(false);

  const centerLat = 28.6328;
  const centerLon = 77.2197;

  const yellowLineCoords = [
    [28.6580, 77.2160],
    [28.6431, 77.2214],
    [28.6328, 77.2197],
    [28.6231, 77.2150],
    [28.6080, 77.2090],
  ];

  const blueLineCoords = [
    [28.6360, 77.1950],
    [28.6395, 77.2085],
    [28.6328, 77.2197],
    [28.6300, 77.2295],
    [28.6260, 77.2480],
  ];

  const radialEndpoints = [
    [28.6250, 77.2155], // Parliament Street
    [28.6235, 77.2191], // Janpath
    [28.6250, 77.2260], // Kasturba Gandhi Marg
    [28.6295, 77.2315], // Barakhamba Road
    [28.6365, 77.2055], // Panchkuian Road
    [28.6265, 77.2105], // Baba Kharak Singh Marg
    [28.6410, 77.2245], // Minto Road
    [28.6415, 77.2175], // Chelmsford Road
  ];

  const concentricRadii = [
    { lat: 0.0016, lon: 0.0018 }, // Inner Circle
    { lat: 0.0028, lon: 0.0031 }, // Middle Circle
    { lat: 0.0038, lon: 0.0042 }, // Outer Circle
  ];

  const interpolatePath = (coords: number[][], progress: number) => {
    const totalSegments = coords.length - 1;
    const segment = Math.min(totalSegments - 1, Math.floor(progress * totalSegments));
    const segmentProgress = (progress * totalSegments) - segment;
    const p1 = coords[segment];
    const p2 = coords[segment + 1];
    return {
      lat: p1[0] + (p2[0] - p1[0]) * segmentProgress,
      lon: p1[1] + (p2[1] - p1[1]) * segmentProgress,
    };
  };

  const stations = [
    { coords: [28.6328, 77.2197], name: "Rajiv Chowk" },
    { coords: [28.6431, 77.2214], name: "New Delhi Station" },
    { coords: [28.6231, 77.2150], name: "Patel Chowk" },
    { coords: [28.6395, 77.2085], name: "R.K. Ashram Marg" },
    { coords: [28.6300, 77.2295], name: "Barakhamba Road" },
  ];

  const generateGridGeoJSON = useCallback((gridData: GridCell[]) => {
    const features = [];
    const rows = 10;
    const cols = 10;
    const cellW = 0.005;
    const cellH = 0.005;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const idx = r * cols + c;
        const cell = gridData[idx];
        const congestion = cell ? cell.congestion : 0.0;

        const cellLat = centerLat + (r - rows / 2) * cellH;
        const cellLon = centerLon + (c - cols / 2) * cellW;

        const minLon = cellLon - cellW / 2;
        const maxLon = cellLon + cellW / 2;
        const minLat = cellLat - cellH / 2;
        const maxLat = cellLat + cellH / 2;

        features.push({
          type: "Feature",
          properties: {
            id: idx,
            congestion: congestion,
          },
          geometry: {
            type: "Polygon",
            coordinates: [[
              [minLon, minLat],
              [maxLon, minLat],
              [maxLon, maxLat],
              [minLon, maxLat],
              [minLon, minLat],
            ]],
          },
        });
      }
    }

    return {
      type: "FeatureCollection",
      features: features,
    } as any;
  }, []);

  // Initialize Mapbox if token is available
  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Check for token in env or localStorage
    const envToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN?.trim() || "";
    const localToken = typeof window !== "undefined" ? localStorage.getItem("mapbox_token")?.trim() || "" : "";
    const activeToken = envToken || localToken;

    if (!activeToken) {
      setHasMapboxToken(false);
      return;
    }

    try {
      mapboxgl.accessToken = activeToken;

      const map = new mapboxgl.Map({
        container: mapContainerRef.current,
        style: "mapbox://styles/mapbox/dark-v11",
        center: [centerLon, centerLat],
        zoom: 15.0,
        attributionControl: false,
        maxBounds: [
          [77.18, 28.60],
          [77.26, 28.67],
        ],
        minZoom: 13,
        maxZoom: 17,
      });
      mapRef.current = map;

      map.on("error", (e) => {
        // Handle auth or tile loading errors gracefully
        if (e.error?.message?.includes("access token") || (e.error as any)?.status === 401) {
          console.warn("Mapbox authentication error, switching to offline simulation mode:", e.error?.message);
          setHasMapboxToken(false);
        }
      });

      map.on("load", () => {
        mapLoadedRef.current = true;
        setHasMapboxToken(true);

        // 1. Add Yellow Line Metro Track
        map.addSource("yellow-line", {
          type: "geojson",
          data: {
            type: "Feature",
            properties: {},
            geometry: {
              type: "LineString",
              coordinates: yellowLineCoords.map((c) => [c[1], c[0]]),
            },
          },
        });
        map.addLayer({
          id: "yellow-line-layer",
          type: "line",
          source: "yellow-line",
          paint: {
            "line-color": "#eab308",
            "line-width": 3.5,
            "line-opacity": 0.55,
          },
        });

        // 2. Add Blue Line Metro Track
        map.addSource("blue-line", {
          type: "geojson",
          data: {
            type: "Feature",
            properties: {},
            geometry: {
              type: "LineString",
              coordinates: blueLineCoords.map((c) => [c[1], c[0]]),
            },
          },
        });
        map.addLayer({
          id: "blue-line-layer",
          type: "line",
          source: "blue-line",
          paint: {
            "line-color": "#3b82f6",
            "line-width": 3.5,
            "line-opacity": 0.55,
          },
        });

        // 3. Add Congestion Grid Overlay
        map.addSource("grid-overlay", {
          type: "geojson",
          data: generateGridGeoJSON(grid),
        });
        map.addLayer({
          id: "grid-layer",
          type: "fill",
          source: "grid-overlay",
          paint: {
            "fill-color": "#ef4444",
            "fill-opacity": [
              "case",
              [">", ["get", "congestion"], 0.15],
              ["*", ["get", "congestion"], 0.18],
              0.0,
            ],
            "fill-outline-color": "rgba(255, 255, 255, 0.02)",
          },
        });

        // 4. Add Station Markers
        map.addSource("stations", {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: stations.map((s) => ({
              type: "Feature",
              properties: { name: s.name },
              geometry: {
                type: "Point",
                coordinates: [s.coords[1], s.coords[0]],
              },
            })),
          },
        });
        map.addLayer({
          id: "stations-layer",
          type: "circle",
          source: "stations",
          paint: {
            "circle-radius": [
              "case",
              ["==", ["get", "name"], "Rajiv Chowk"],
              6,
              4.5,
            ],
            "circle-color": "#3b82f6",
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 1,
            "circle-opacity": 0.8,
          },
        });
      });
    } catch (err) {
      console.warn("Mapbox GL initialization failed, running in offline simulation mode:", err);
      setHasMapboxToken(false);
      mapRef.current = null;
      mapLoadedRef.current = false;
    }

    return () => {
      if (mapRef.current) {
        try {
          mapRef.current.remove();
        } catch {}
        mapRef.current = null;
        mapLoadedRef.current = false;
      }
    };
  }, [centerLat, centerLon, generateGridGeoJSON]);

  // 5. Initialize particles once on mount
  useEffect(() => {
    const particles: MapParticle[] = [];
    const count = 160;

    for (let i = 0; i < count; i++) {
      const type = Math.random() < 0.25 ? "delivery" : "citizen";
      const pathType = Math.random() < 0.15 ? "metro" : Math.random() < 0.45 ? "radial" : "concentric";
      const lineIndex = Math.floor(Math.random() * 8);
      const direction = Math.random() < 0.6 ? 1 : -1;

      particles.push({
        progress: Math.random(),
        speed: type === "delivery" ? 0.012 : 0.007,
        type,
        pathType,
        lineIndex,
        direction,
        lat: centerLat,
        lon: centerLon,
      });
    }
    particlesRef.current = particles;
  }, [centerLat, centerLon]);

  // Update Grid Overlay styling when grid data changes and Mapbox is active
  useEffect(() => {
    if (!mapRef.current || !mapLoadedRef.current || grid.length === 0) return;

    try {
      const source = mapRef.current.getSource("grid-overlay") as mapboxgl.GeoJSONSource;
      if (source) {
        source.setData(generateGridGeoJSON(grid));
      }
    } catch {}
  }, [grid, generateGridGeoJSON]);

  // Sync canvas dimensions and particle calculations inside animation loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;

    const updateAndDrawParticles = () => {
      const parent = canvas.parentElement;
      const width = parent?.clientWidth || 500;
      const height = parent?.clientHeight || 500;
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const map = mapRef.current;
      const isMapActive = !!(map && mapLoadedRef.current);

      // Coordinate projection function (Mapbox or calibrated fallback)
      const project = (lon: number, lat: number) => {
        if (isMapActive && map) {
          try {
            return map.project([lon, lat]);
          } catch {}
        }
        // Fallback projection centered at Connaught Place
        const scale = (Math.min(width, height) * 0.82) / 0.045;
        const x = width / 2 + (lon - centerLon) * scale;
        const y = height / 2 - (lat - centerLat) * scale * 1.14;
        return { x, y };
      };

      // In offline mode (no Mapbox GL base layer), render local dark cartography
      if (!isMapActive) {
        ctx.save();

        // 1. Subtle spatial grid background
        ctx.strokeStyle = "rgba(255, 255, 255, 0.025)";
        ctx.lineWidth = 1;
        const step = 40;
        for (let gx = 0; gx < width; gx += step) {
          ctx.beginPath();
          ctx.moveTo(gx, 0);
          ctx.lineTo(gx, height);
          ctx.stroke();
        }
        for (let gy = 0; gy < height; gy += step) {
          ctx.beginPath();
          ctx.moveTo(0, gy);
          ctx.lineTo(width, gy);
          ctx.stroke();
        }

        // 2. Congestion Heatmap Grid
        grid.forEach((cell, idx) => {
          if (!cell || cell.congestion <= 0.15) return;
          const rows = 10;
          const cols = 10;
          const cellW = 0.005;
          const cellH = 0.005;
          const r = Math.floor(idx / cols);
          const c = idx % cols;
          const cellLat = centerLat + (r - rows / 2) * cellH;
          const cellLon = centerLon + (c - cols / 2) * cellW;

          const pTopLeft = project(cellLon - cellW / 2, cellLat + cellH / 2);
          const pBottomRight = project(cellLon + cellW / 2, cellLat - cellH / 2);

          const alpha = Math.min(0.3, cell.congestion * 0.22);
          ctx.fillStyle = `rgba(239, 68, 68, ${alpha})`;
          ctx.fillRect(pTopLeft.x, pTopLeft.y, pBottomRight.x - pTopLeft.x, pBottomRight.y - pTopLeft.y);
          ctx.strokeStyle = "rgba(239, 68, 68, 0.08)";
          ctx.strokeRect(pTopLeft.x, pTopLeft.y, pBottomRight.x - pTopLeft.x, pBottomRight.y - pTopLeft.y);
        });

        const centerPt = project(centerLon, centerLat);

        // 3. Connaught Place Concentric Rings
        concentricRadii.forEach((ring, i) => {
          const rx = (ring.lon * (Math.min(width, height) * 0.82)) / 0.045;
          const ry = (ring.lat * (Math.min(width, height) * 0.82) * 1.14) / 0.045;
          ctx.beginPath();
          ctx.ellipse(centerPt.x, centerPt.y, rx, ry, 0, 0, Math.PI * 2);
          ctx.strokeStyle = i === 0 ? "rgba(255, 255, 255, 0.2)" : "rgba(255, 255, 255, 0.1)";
          ctx.lineWidth = i === 0 ? 1.5 : 1;
          ctx.stroke();
        });

        // 4. Radial Arterial Roads
        radialEndpoints.forEach((ep) => {
          const epPt = project(ep[1], ep[0]);
          ctx.beginPath();
          ctx.moveTo(centerPt.x, centerPt.y);
          ctx.lineTo(epPt.x, epPt.y);
          ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
          ctx.lineWidth = 1.5;
          ctx.stroke();
        });

        // 5. Yellow Line Metro Track
        ctx.beginPath();
        yellowLineCoords.forEach((c, idx) => {
          const pt = project(c[1], c[0]);
          if (idx === 0) ctx.moveTo(pt.x, pt.y);
          else ctx.lineTo(pt.x, pt.y);
        });
        ctx.strokeStyle = "#eab308";
        ctx.lineWidth = 3.5;
        ctx.shadowBlur = 4;
        ctx.shadowColor = "rgba(234, 179, 8, 0.4)";
        ctx.stroke();
        ctx.shadowBlur = 0;

        // 6. Blue Line Metro Track
        ctx.beginPath();
        blueLineCoords.forEach((c, idx) => {
          const pt = project(c[1], c[0]);
          if (idx === 0) ctx.moveTo(pt.x, pt.y);
          else ctx.lineTo(pt.x, pt.y);
        });
        ctx.strokeStyle = "#3b82f6";
        ctx.lineWidth = 3.5;
        ctx.shadowBlur = 4;
        ctx.shadowColor = "rgba(59, 130, 246, 0.4)";
        ctx.stroke();
        ctx.shadowBlur = 0;

        // 7. Metro Stations
        stations.forEach((s) => {
          const pt = project(s.coords[1], s.coords[0]);
          const isRajiv = s.name === "Rajiv Chowk";
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, isRajiv ? 6 : 4.5, 0, Math.PI * 2);
          ctx.fillStyle = isRajiv ? "#38bdf8" : "#3b82f6";
          ctx.fill();
          ctx.strokeStyle = "#ffffff";
          ctx.lineWidth = 1.2;
          ctx.stroke();

          ctx.fillStyle = "rgba(255, 255, 255, 0.75)";
          ctx.font = "9px var(--font-jetbrains-mono), monospace";
          ctx.fillText(s.name, pt.x + 8, pt.y + 3);
        });

        ctx.restore();
      }

      // Draw active particles
      const speedMod = Math.max(0.25, 1 - roadCongestion * 0.75);

      particlesRef.current.forEach((p) => {
        if (p.pathType === "metro") {
          const isYellow = p.lineIndex % 2 === 0;
          const route = isYellow ? yellowLineCoords : blueLineCoords;
          const pt = interpolatePath(route, p.progress);
          p.lat = pt.lat;
          p.lon = pt.lon;
        } else if (p.pathType === "radial") {
          const endpoint = radialEndpoints[p.lineIndex % radialEndpoints.length];
          p.lat = centerLat + (endpoint[0] - centerLat) * p.progress;
          p.lon = centerLon + (endpoint[1] - centerLon) * p.progress;
        } else {
          const ring = concentricRadii[p.lineIndex % concentricRadii.length];
          const angle = p.progress * Math.PI * 2;
          p.lat = centerLat + Math.cos(angle) * ring.lat;
          p.lon = centerLon + Math.sin(angle) * ring.lon;
        }

        const point = project(p.lon, p.lat);

        ctx.beginPath();
        ctx.arc(point.x, point.y, p.type === "delivery" ? 3.2 : 2.0, 0, Math.PI * 2);

        if (p.type === "delivery") {
          ctx.fillStyle = "#f97316";
          ctx.shadowBlur = 3;
          ctx.shadowColor = "#f97316";
          ctx.fill();
          ctx.shadowBlur = 0;
        } else {
          ctx.fillStyle = p.pathType === "metro" ? "#3b82f6" : "#22d3ee";
          ctx.fill();
        }

        if (isPlaying) {
          let speed = p.speed * speedMod;
          if (p.type === "citizen" && rainIntensity > 0.3) {
            speed *= 0.75;
          }
          p.progress += speed * p.direction;

          if (p.progress > 1.0) {
            p.progress = 0;
            p.direction = Math.random() < 0.5 ? 1 : -1;
          } else if (p.progress < 0) {
            p.progress = 1.0;
            p.direction = Math.random() < 0.5 ? 1 : -1;
          }
        }
      });

      // Rain effect streaks
      if (rainIntensity > 0) {
        ctx.strokeStyle = "rgba(174, 207, 238, 0.15)";
        ctx.lineWidth = 1.2;
        const streaks = Math.floor(rainIntensity * 25);
        for (let i = 0; i < streaks; i++) {
          const rx = Math.random() * canvas.width;
          const ry = Math.random() * canvas.height;
          const length = 15 + rainIntensity * 12;
          ctx.beginPath();
          ctx.moveTo(rx, ry);
          ctx.lineTo(rx - 2, ry + length);
          ctx.stroke();
        }
      }

      // HUD Stats overlay
      ctx.fillStyle = "rgba(10, 10, 10, 0.75)";
      ctx.fillRect(10, 10, 140, 48);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.1)";
      ctx.strokeRect(10, 10, 140, 48);

      ctx.fillStyle = "rgba(255, 255, 255, 0.85)";
      ctx.font = "bold 11px var(--font-jetbrains-mono), monospace";
      ctx.fillText(`TIME: ${timeOfDay}`, 20, 28);

      ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
      ctx.font = "9px var(--font-jetbrains-mono), monospace";
      ctx.fillText(`AGENTS: ${particlesRef.current.length} particles`, 20, 44);

      animId = requestAnimationFrame(updateAndDrawParticles);
    };

    updateAndDrawParticles();

    return () => cancelAnimationFrame(animId);
  }, [isPlaying, rainIntensity, roadCongestion, timeOfDay, grid, centerLat, centerLon]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (mapRef.current) {
        try {
          mapRef.current.resize();
        } catch {}
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const handleSaveToken = () => {
    if (!tokenInput.trim()) return;
    localStorage.setItem("mapbox_token", tokenInput.trim());
    setTokenSaved(true);
    setTimeout(() => {
      window.location.reload();
    }, 600);
  };

  return (
    <div className="relative w-full flex-1 min-h-[300px] bg-[#0c0a09] rounded-3xl border border-white/10 overflow-hidden shadow-2xl backdrop-blur-md">
      {/* Mapbox GL container */}
      <div ref={mapContainerRef} className="w-full h-full z-0" />

      {/* Synchronized canvas for spatial simulation */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 pointer-events-none z-[20] w-full h-full"
      />

      {/* Status Badge & Token Configuration Trigger */}
      {hasMapboxToken === false && (
        <button
          onClick={() => setShowTokenModal(true)}
          className="absolute top-3 right-3 z-[30] flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-black/70 hover:bg-black/90 border border-amber-500/40 text-[11px] text-amber-300 font-mono backdrop-blur-md transition-all shadow-lg cursor-pointer"
          title="Click to configure Mapbox Token"
        >
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          <span>Offline Simulation • Add Token</span>
        </button>
      )}

      {hasMapboxToken === true && (
        <div className="absolute top-3 right-3 z-[30] flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/60 border border-emerald-500/40 text-[10px] text-emerald-400 font-mono backdrop-blur-md">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          <span>Mapbox GL Active</span>
        </div>
      )}

      {/* Token Modal */}
      {showTokenModal && (
        <div className="absolute inset-0 z-[50] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md p-5 bg-[#141210] border border-white/20 rounded-2xl shadow-2xl space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-white">Mapbox Access Token</h3>
              <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                The simulation currently runs in high-performance local canvas mode. To render satellite/vector dark map tiles, provide your public Mapbox access token (starts with <code className="text-amber-400 font-mono">pk.</code>).
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="text-[11px] text-zinc-300 font-mono">Access Token</label>
              <input
                type="text"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder="pk.eyJ1..."
                className="w-full px-3 py-2 text-xs bg-zinc-900 border border-white/10 rounded-lg text-white font-mono focus:outline-none focus:border-amber-400/60"
              />
              <p className="text-[10px] text-zinc-500">
                You can also permanently configure this in <code className="text-zinc-400">.env.local</code> as <code className="text-zinc-400">NEXT_PUBLIC_MAPBOX_TOKEN</code>.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                onClick={() => setShowTokenModal(false)}
                className="px-3 py-1.5 text-xs text-zinc-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
              >
                Close
              </button>
              <button
                onClick={handleSaveToken}
                disabled={!tokenInput.trim() || tokenSaved}
                className="px-4 py-1.5 text-xs font-medium text-black bg-amber-400 hover:bg-amber-300 disabled:opacity-50 rounded-lg transition-colors cursor-pointer"
              >
                {tokenSaved ? "Saved! Reloading..." : "Save & Activate"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
