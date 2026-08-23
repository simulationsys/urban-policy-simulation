"use client";

import { useEffect, useRef } from "react";
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

  const generateGridGeoJSON = (gridData: GridCell[]) => {
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
            congestion: congestion
          },
          geometry: {
            type: "Polygon",
            coordinates: [[
              [minLon, minLat],
              [maxLon, minLat],
              [maxLon, maxLat],
              [minLon, maxLat],
              [minLon, minLat]
            ]]
          }
        });
      }
    }

    return {
      type: "FeatureCollection",
      features: features
    } as any;
  };

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || "";

    const map = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: "mapbox://styles/mapbox/dark-v11",
      center: [centerLon, centerLat], // Mapbox uses [longitude, latitude]
      zoom: 15.0,
      attributionControl: false,
      maxBounds: [
        [77.18, 28.60],
        [77.26, 28.67]
      ],
      minZoom: 13,
      maxZoom: 17,
    });
    mapRef.current = map;

    map.on("load", () => {
      mapLoadedRef.current = true;

      // 1. Add Yellow Line Metro Track
      map.addSource("yellow-line", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: {
            type: "LineString",
            coordinates: yellowLineCoords.map(c => [c[1], c[0]])
          }
        }
      });
      map.addLayer({
        id: "yellow-line-layer",
        type: "line",
        source: "yellow-line",
        paint: {
          "line-color": "#eab308",
          "line-width": 3.5,
          "line-opacity": 0.55
        }
      });

      // 2. Add Blue Line Metro Track
      map.addSource("blue-line", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: {
            type: "LineString",
            coordinates: blueLineCoords.map(c => [c[1], c[0]])
          }
        }
      });
      map.addLayer({
        id: "blue-line-layer",
        type: "line",
        source: "blue-line",
        paint: {
          "line-color": "#3b82f6",
          "line-width": 3.5,
          "line-opacity": 0.55
        }
      });

      // 3. Add Congestion Grid Overlay
      map.addSource("grid-overlay", {
        type: "geojson",
        data: generateGridGeoJSON(grid)
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
            0.0
          ],
          "fill-outline-color": "rgba(255, 255, 255, 0.02)"
        }
      });

      // 4. Add Station Markers
      map.addSource("stations", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: stations.map(s => ({
            type: "Feature",
            properties: { name: s.name },
            geometry: {
              type: "Point",
              coordinates: [s.coords[1], s.coords[0]]
            }
          }))
        }
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
            4.5
          ],
          "circle-color": "#3b82f6",
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1,
          "circle-opacity": 0.8
        }
      });
    });

    // 5. Initialize particles
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

    return () => {
      map.remove();
      mapRef.current = null;
      mapLoadedRef.current = false;
    };
  }, []);

  // Update Grid Overlay styling when grid data changes
  useEffect(() => {
    if (!mapRef.current || !mapLoadedRef.current || grid.length === 0) return;

    const source = mapRef.current.getSource("grid-overlay") as mapboxgl.GeoJSONSource;
    if (source) {
      source.setData(generateGridGeoJSON(grid));
    }
  }, [grid]);

  // Sync canvas dimensions and particle calculations inside animation loop
  useEffect(() => {
    const canvas = canvasRef.current;
    const map = mapRef.current;
    if (!canvas || !map) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;

    const updateAndDrawParticles = () => {
      const width = canvasRef.current?.parentElement?.clientWidth || 500;
      const height = canvasRef.current?.parentElement?.clientHeight || 500;
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

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

        // Mapbox GL coordinate projection: [lng, lat]
        const point = map.project([p.lon, p.lat]);

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
  }, [isPlaying, rainIntensity, roadCongestion, timeOfDay]);

  // Trigger map resize on window resize to ensure WebGL context fits correctly
  useEffect(() => {
    const handleResize = () => {
      if (mapRef.current) {
        mapRef.current.resize();
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return (
    <div className="relative w-full flex-1 min-h-[300px] bg-[#0c0a09] rounded-3xl border border-white/10 overflow-hidden shadow-2xl backdrop-blur-md">
      {/* Mapbox GL container */}
      <div ref={mapContainerRef} className="w-full h-full z-0" />
      {/* Synchronized canvas for particle rendering */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 pointer-events-none z-[400] w-full h-full"
      />
    </div>
  );
}
