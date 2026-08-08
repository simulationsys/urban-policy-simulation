"use client";
import React, { useEffect, useRef, useState, useMemo } from "react";
import Map from "react-map-gl/mapbox";
import DeckGL from "@deck.gl/react";
import { GeoJsonLayer, ColumnLayer, ScatterplotLayer, PolygonLayer, IconLayer } from "@deck.gl/layers";
import { ScenegraphLayer } from "@deck.gl/mesh-layers";
import { AmbientLight, DirectionalLight, LightingEffect } from "@deck.gl/core";
import "mapbox-gl/dist/mapbox-gl.css";

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

const METRO_SVG = `<svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
<circle cx="60" cy="60" r="50" fill="#1F2937" stroke="#06b6d4" stroke-width="4" stroke-dasharray="10 5"/>
<circle cx="60" cy="60" r="20" fill="#06b6d4"/>
<text x="60" y="66" fill="white" font-size="22" font-family="sans-serif" font-weight="bold" text-anchor="middle">M</text>
<text x="60" y="95" fill="white" font-size="12" font-family="sans-serif" font-weight="bold" text-anchor="middle">RAJIV CHOWK</text>
</svg>`;
const toDataURL = (svg: string) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
const METRO_URL = toDataURL(METRO_SVG);

interface DashboardMapProps {
  rainIntensity: number; // 0 to 100
  congestionFee: number; // 0 to 100
  busCapacity: number;   // 0 to 100
  timeOfDay: number;     // 0 to 24
  activeOverlay: string; // "Road Network" | "Agent Congestion" | "Transit Overlay"
}

function hexToRgb(hex: string): [number, number, number] {
  var result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? [parseInt(result[1], 16), parseInt(result[2], 16), parseInt(result[3], 16)] : [0, 0, 0];
}

function hashColor(lat: number, lng: number, isDay: boolean): [number, number, number] {
  const hash = Math.floor(Math.abs(lat * 100000 + lng * 100000));
  const v = hash % 3;
  if (isDay) {
    if (v === 0) return hexToRgb("#f8fafc"); 
    if (v === 1) return hexToRgb("#e2e8f0"); 
    return hexToRgb("#cbd5e1"); 
  } else {
    if (v === 0) return hexToRgb("#09090b"); 
    if (v === 1) return hexToRgb("#18181b"); 
    return hexToRgb("#27272a"); 
  }
}

// Procedural 3D Box Generator for Vehicles
const DEG2RAD = Math.PI / 180;
const EARTH_RADIUS = 6371000; // meters
function getVehiclePolygon(lng: number, lat: number, angleDegrees: number, length: number, width: number) {
  const latScale = 1 / (EARTH_RADIUS * DEG2RAD);
  const lngScale = 1 / (EARTH_RADIUS * Math.cos(lat * DEG2RAD) * DEG2RAD);
  const rad = angleDegrees * DEG2RAD;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);

  const l2 = length / 2;
  const w2 = width / 2;

  // Local coordinates: +Y is forward, +X is right
  const corners = [
    [-w2, l2],
    [w2, l2],
    [w2, -l2],
    [-w2, -l2]
  ];

  return corners.map(c => {
     // Rotate clockwise by bearing 'rad'
     const x = c[0] * cos + c[1] * sin;
     const y = -c[0] * sin + c[1] * cos;
     return [lng + x * lngScale, lat + y * latScale];
  });
}

const INITIAL_VIEW_STATE = {
  longitude: 77.2197,
  latitude: 28.6328,
  zoom: 16.5,
  pitch: 50,
  bearing: 0
};

const DashboardMap: React.FC<DashboardMapProps> = ({ rainIntensity, congestionFee, busCapacity, timeOfDay, activeOverlay }) => {
  const [roadData, setRoadData] = useState<any>(null);
  const [rawAgentsData, setRawAgentsData] = useState<any[]>([]);
  const [buildingsData, setBuildingsData] = useState<any>(null);
  const [parksData, setParksData] = useState<any>(null);
  const [walkData, setWalkData] = useState<any>(null);
  const [treeData, setTreeData] = useState<any[]>([]);
  const [trafficLights, setTrafficLights] = useState<any[]>([]);
  
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [povMode, setPovMode] = useState(false);

  const [tick, setTick] = useState(0);
  const agentsRef = useRef<any[]>([]);
  const requestRef = useRef<number | null>(null);

  const rainRef = useRef(rainIntensity);
  const feeRef = useRef(congestionFee);
  const selectedAgentRef = useRef(selectedAgentId);
  const povModeRef = useRef(povMode);
  const trafficLightsRef = useRef<any[]>([]);

  useEffect(() => { povModeRef.current = povMode; }, [povMode]);

  useEffect(() => {
    fetch('/rajiv_chowk_roads.json').then(res => res.json()).then(data => setRoadData(data));
    fetch('/rajiv_chowk_walk.json').then(res => res.json()).then(data => setWalkData(data));
    fetch('/rajiv_chowk_agents.json').then(res => res.json()).then(data => setRawAgentsData(data));
    fetch('/rajiv_chowk_buildings.json').then(res => res.json()).then(data => setBuildingsData(data));
    fetch('/rajiv_chowk_parks.json').then(res => res.json()).then(data => {
      setParksData(data);
      const trees: any[] = [];
      data.features.forEach((feature: any) => {
        if (feature.geometry.type === 'Polygon') {
          const coords = feature.geometry.coordinates[0];
          if (coords.length > 3) {
            let minLng = 180, maxLng = -180, minLat = 90, maxLat = -90;
            coords.forEach((p: any) => {
              if (p[0] < minLng) minLng = p[0];
              if (p[0] > maxLng) maxLng = p[0];
              if (p[1] < minLat) minLat = p[1];
              if (p[1] > maxLat) maxLat = p[1];
            });
            const numTrees = 20 + Math.floor(Math.random() * 30);
            for(let i=0; i<numTrees; i++) {
              trees.push({
                position: [
                  minLng + Math.random() * (maxLng - minLng),
                  minLat + Math.random() * (maxLat - minLat)
                ],
                height: 4 + Math.random() * 6,
                radius: 2 + Math.random() * 2
              });
            }
          }
        }
      });
      setTreeData(trees);
    });
    fetch('/traffic_lights.json').then(res => res.json()).then(data => {
      setTrafficLights(data);
      trafficLightsRef.current = data;
    });
  }, []);

  useEffect(() => {
    rainRef.current = rainIntensity;
    feeRef.current = congestionFee;
  }, [rainIntensity, congestionFee]);

  useEffect(() => {
    selectedAgentRef.current = selectedAgentId;
  }, [selectedAgentId]);

  useEffect(() => {
    if (rawAgentsData && rawAgentsData.length > 0) {
      agentsRef.current = rawAgentsData.map((agent, i) => ({
        ...agent,
        progress: 0,
        index: i,
        currentPosition: agent.path && agent.path.length > 0 ? [agent.path[0][1], agent.path[0][0]] : [0,0],
        currentAngle: 0,
        currentPolygon: [] // Will be populated in loop
      }));
    }
  }, [rawAgentsData]);

  useEffect(() => {
    const animate = () => {
      agentsRef.current.forEach(item => {
        if (!item.path || item.path.length < 2) return;
        
        // Traffic light logic
        const lightPhase = Math.floor(Date.now() / 3000) % 3; // 0 = Red, 1 = Yellow, 2 = Green
        let isStopped = false;
        
        if (lightPhase !== 2 && item.type !== 'pedestrian' && item.currentPosition) {
          for (let tl of trafficLightsRef.current) {
            const distSq = Math.pow(item.currentPosition[0] - tl.position[0], 2) + Math.pow(item.currentPosition[1] - tl.position[1], 2);
            if (distSq < 0.00000003) { // Roughly 15 meters squared
              isStopped = true;
              break;
            }
          }
        }
        
        // Anti-crushing: Collision avoidance (don't drive through the car in front)
        if (!isStopped && item.type !== 'pedestrian' && item.currentPosition && item.currentAngle !== undefined) {
          for (let other of agentsRef.current) {
            if (other.id !== item.id && other.type !== 'pedestrian' && other.currentPosition) {
              const distSq = Math.pow(item.currentPosition[0] - other.currentPosition[0], 2) + Math.pow(item.currentPosition[1] - other.currentPosition[1], 2);
              if (distSq < 0.00000002) { // Extremely close (~10-14 meters)
                // If they are pointing in roughly the same direction, slow down to avoid rear-ending
                const angleDiff = Math.abs((item.currentAngle - other.currentAngle + 360) % 360);
                if (angleDiff < 45 || angleDiff > 315) {
                   // Only stop if the other vehicle is IN FRONT of us
                   const dx = other.currentPosition[0] - item.currentPosition[0];
                   const dy = other.currentPosition[1] - item.currentPosition[1];
                   const headingRad = item.currentAngle * (Math.PI / 180);
                   const dirX = Math.sin(headingRad);
                   const dirY = Math.cos(headingRad);
                   
                   const dotProduct = (dx * dirX) + (dy * dirY);
                   if (dotProduct > 0) { // other is ahead!
                       isStopped = true;
                       break;
                   }
                }
              }
            }
          }
        }

        const speedMultiplier = 1 - (rainRef.current / 200);
        if (!isStopped) {
          item.progress += (item.speed * speedMultiplier);
        }
        
        if (item.progress >= 1) item.progress = 0;
        const totalSegments = item.path.length - 1;
        const currentSegment = Math.min(Math.floor(item.progress * totalSegments), totalSegments - 1);
        const segmentProgress = (item.progress * totalSegments) - currentSegment;
        
        const p1 = item.path[currentSegment];
        const p2 = item.path[currentSegment + 1];
        if (!p1 || !p2) return;

        let lat = p1[0] + (p2[0] - p1[0]) * segmentProgress;
        let lng = p1[1] + (p2[1] - p1[1]) * segmentProgress;
        const angle = Math.atan2(p2[0] - p1[0], p2[1] - p1[1]) * 180 / Math.PI;
        item.currentAngle = angle;
        
        // Offset pedestrians to the sidewalk (approx 4 meters perpendicular)
        if (item.type === 'pedestrian') {
            const perpAngle = (angle + 90) * (Math.PI / 180);
            const offsetMeters = 4;
            const latOffset = (offsetMeters * Math.sin(perpAngle)) / 111139;
            const lngOffset = (offsetMeters * Math.cos(perpAngle)) / (111139 * Math.cos(lat * Math.PI / 180));
            item.currentPosition = [lng + lngOffset, lat + latOffset];
        } else {
            item.currentPosition = [lng, lat];
        }

        let targetAngle = Math.atan2(p2[1] - p1[1], p2[0] - p1[0]) * (180 / Math.PI);
        
        if (item.currentAngle === undefined || isNaN(item.currentAngle)) item.currentAngle = targetAngle || 0;
        let diff = (targetAngle || 0) - item.currentAngle;
        while (diff < -180) diff += 360;
        while (diff > 180) diff -= 360;
        item.currentAngle += diff * 0.15;
      });

      if (selectedAgentRef.current && povModeRef.current) {
        const targetAgent = agentsRef.current.find(a => a.id === selectedAgentRef.current);
        if (targetAgent) {
          setViewState(prev => ({
            ...prev,
            longitude: targetAgent.currentPosition[0],
            latitude: targetAgent.currentPosition[1],
            zoom: 21.5,
            pitch: 85,
            bearing: targetAgent.currentAngle
          }));
        }
      }

      setTick(t => t + 1);
      requestRef.current = requestAnimationFrame(animate);
    };

    requestRef.current = requestAnimationFrame(animate);
    return () => {
      if (requestRef.current) cancelAnimationFrame(requestRef.current);
    };
  }, []);

  const isDay = timeOfDay >= 6 && timeOfDay <= 18;

  const { lightingEffect } = useMemo(() => {
    const rainDim = 1 - (rainIntensity / 200); // 1.0 (clear) down to 0.5 (heavy rain)
    const ambientLight = new AmbientLight({
      color: [255, 255, 255],
      intensity: (isDay ? 3.5 : 1.5) * rainDim
    });
    const le = new LightingEffect({ambientLight});
    return { lightingEffect: le };
  }, [timeOfDay, rainIntensity, isDay]);


  const WATER_POLYGON = useMemo(() => ({
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [[[77.15, 28.58], [77.28, 28.58], [77.28, 28.68], [77.15, 28.68], [77.15, 28.58]]]
      },
      properties: {}
    }]
  }), []);

  const visibleAgents = agentsRef.current.filter(item => {
    if (activeOverlay === "Transit Overlay" && item.type !== 'bus') return false;
    if (item.type === "car") {
      // 1 rupee of congestion fee = 0.6% reduction in cars.
      // Every 1% increase in bus capacity above 20% baseline = 0.5% reduction in cars.
      const carReductionPct = (congestionFee * 0.6) + (busCapacity > 20 ? (busCapacity - 20) * 0.5 : 0);
      if ((item.index % 100) < carReductionPct) return false;
    }
    return true;
  });

  const showBuildings = activeOverlay !== "Agent Congestion";
  const mapStyle = "mapbox://styles/mapbox/standard"; // Mapbox Standard supports built-in 3D buildings and trees

  const layers = [
    // Base Ground and Buildings are handled natively by Mapbox Standard Style

    walkData && new GeoJsonLayer({
      id: 'walk-layer',
      data: walkData,
      pickable: false,
      stroked: true,
      getLineColor: [220, 220, 220, 180],
      getLineWidth: 6,
      lineWidthUnits: 'meters'
    }),

    // Glowing Neon Vehicles (Night Mode Underglow)
    !isDay && new ScatterplotLayer({
      id: 'neon-lights-layer',
      data: visibleAgents,
      getPosition: (d: any) => d.currentPosition,
      getFillColor: (d: any) => d.type === 'pedestrian' ? [250, 204, 21, 150] : (d.type === 'bus' ? [56, 189, 248, 150] : [248, 113, 113, 150]),
      getRadius: (d: any) => d.type === 'bus' ? 12 : (d.type === 'pedestrian' ? 4 : 8),
      radiusUnits: 'meters',
      opacity: 0.8, 
      updateTriggers: { getPosition: tick }
    }),

    // Cars (GLB)
    new ScenegraphLayer({
      id: 'cars-layer',
      data: visibleAgents.filter(a => a.type === 'car'),
      pickable: true,
      scenegraph: '/car.glb',
      getPosition: (d: any) => d.currentPosition || [0, 0, 0],
      getOrientation: (d: any) => [0, -(d.currentAngle || 0), 0], // Rotate to face heading natively
      sizeScale: 1.2,
      _lighting: 'pbr',
      updateTriggers: { getPosition: tick, getOrientation: tick }
    }),

    // Buses (GLB)
    new ScenegraphLayer({
      id: 'buses-layer',
      data: visibleAgents.filter(a => a.type === 'bus'),
      pickable: true,
      scenegraph: '/bus.glb',
      getPosition: (d: any) => d.currentPosition || [0, 0, 0],
      getOrientation: (d: any) => [0, -(d.currentAngle || 0), 0],
      sizeScale: 1.2,
      _lighting: 'pbr',
      updateTriggers: { getPosition: tick, getOrientation: tick }
    }),

    // Pedestrians (GLB)
    new ScenegraphLayer({
      id: 'pedestrians-layer',
      data: visibleAgents.filter(a => a.type === 'pedestrian'),
      pickable: true,
      scenegraph: '/person.glb',
      getPosition: (d: any) => d.currentPosition || [0, 0, 0],
      getOrientation: (d: any) => [0, -(d.currentAngle || 0), 0],
      sizeScale: 1.5,
      _lighting: 'pbr',
      updateTriggers: { getPosition: tick, getOrientation: tick }
    }),

    // Traffic Lights
    new ScenegraphLayer({
      id: 'traffic-lights-3d-layer',
      data: trafficLights,
      pickable: false,
      scenegraph: '/traffic_light.glb',
      getPosition: (d: any) => d.position,
      getOrientation: [0, 0, 0], // Stand vertically
      sizeScale: 2,
      _lighting: 'pbr',
      getColor: () => {
        const phase = Math.floor(Date.now() / 3000) % 3;
        if (phase === 0) return [239, 68, 68, 255]; // Red
        if (phase === 1) return [234, 179, 8, 255]; // Yellow
        return [34, 197, 94, 255]; // Green
      },
      updateTriggers: { getColor: tick }
    })
  ].filter(Boolean);

  return (
    <div style={{ height: "100%", width: "100%", position: "relative", background: isDay ? "#cbd5e1" : "#020617" }}>
      <DeckGL
        viewState={viewState}
        onViewStateChange={e => {
          if (!povMode) setViewState(e.viewState as any);
        }}
        onClick={(info) => {
          if (info.object && (info.layer?.id === 'cars-layer' || info.layer?.id === 'buses-layer' || info.layer?.id === 'pedestrians-layer')) {
            setSelectedAgentId(info.object.id);
            setPovMode(true);
          } else {
            setSelectedAgentId(null);
            setPovMode(false);
          }
        }}
        controller={true}
        layers={layers as any}
        effects={[lightingEffect]}
      >
        {MAPBOX_TOKEN && (
          <Map 
            mapStyle={mapStyle}
            mapboxAccessToken={MAPBOX_TOKEN} 
          />
        )}
      </DeckGL>
      
      {/* POV Mode Overlay UI */}
      {selectedAgentId && povMode && (
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-4 bg-slate-900/80 backdrop-blur-md px-6 py-3 rounded-full text-white border border-slate-700/50 shadow-2xl z-[1000] animate-in fade-in slide-in-from-bottom-4">
          <div className="flex items-center gap-3">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500"></span>
            </span>
            <div className="flex flex-col">
              <span className="text-xs font-bold tracking-widest text-cyan-400">POV MODE ACTIVE</span>
              <span className="text-[10px] text-slate-400">Following Agent #{selectedAgentId}</span>
            </div>
          </div>
          <div className="w-px h-8 bg-slate-700/50 mx-2"></div>
          <button 
            onClick={() => setPovMode(false)}
            className="text-xs font-semibold bg-red-500/20 hover:bg-red-500/40 text-red-400 px-4 py-1.5 rounded-full transition-colors"
          >
            EXIT POV
          </button>
        </div>
      )}
      
      {!MAPBOX_TOKEN && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-red-500/90 text-white px-4 py-2 rounded-lg text-xs font-bold z-[2000] shadow-xl backdrop-blur-md">
          ⚠️ NEXT_PUBLIC_MAPBOX_TOKEN not found in .env.local. Base map is hidden.
        </div>
      )}
    </div>
  );
}

export default DashboardMap;
