"use client";
import React, { useEffect, useRef, useState, useMemo } from "react";
import Map from "react-map-gl/mapbox";
import DeckGL from "@deck.gl/react";
import { GeoJsonLayer, ColumnLayer, ScatterplotLayer, PolygonLayer, IconLayer, TextLayer } from "@deck.gl/layers";
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
  /** Focus-cohort legs streamed by the simulation engine. Empty => local playback. */
  liveAgents?: any[];
  /** Anchor for interpolating simulated time between ticks. */
  simClock?: { minutes: number; receivedAt: number; minutesPerSecond: number } | null;
  /** Engine grid cells — the whole population's density and congestion. */
  gridCells?: any[];
  /** Focus-cohort citizens who are stationary, with what they are doing. */
  presences?: any[];
  /** Each focus citizen's home, keyed by agent id. */
  dwellings?: Record<string, any>;
}

// The housing ladder, poorest first. Footprint is the ground area the building covers;
// taller blocks stack the same household area over fewer square metres of ground.
const DWELLING_STYLE: Record<string, { label: string; color: [number, number, number]; roof: number }> = {
  jhuggi:      { label: 'Jhuggi',        color: [150, 118, 90],  roof: 2.6 },
  chawl_room:  { label: 'Chawl room',    color: [168, 140, 108], roof: 3.0 },
  walkup_flat: { label: 'Walk-up flat',  color: [176, 168, 156], roof: 3.1 },
  apartment:   { label: 'Apartment',     color: [156, 172, 190], roof: 3.2 },
  bungalow:    { label: 'Bungalow',      color: [206, 196, 176], roof: 3.6 }
};

// A square footprint centred on the home node, sized so footprint x storeys ~ floor area.
function dwellingFootprint(d: any): number[][] {
  const ground = Math.max(9, d.area_sqm / Math.max(1, d.storeys));
  const half = Math.sqrt(ground) / 2;
  const dLat = half / METERS_PER_DEG_LAT;
  const dLng = half / (METERS_PER_DEG_LAT * Math.cos(d.lat * DEG2RAD));
  return [
    [d.lon - dLng, d.lat - dLat],
    [d.lon + dLng, d.lat - dLat],
    [d.lon + dLng, d.lat + dLat],
    [d.lon - dLng, d.lat + dLat]
  ];
}

function dwellingHeight(d: any): number {
  return d.storeys * (DWELLING_STYLE[d.kind]?.roof ?? 3.0);
}

// Deterministic room boxes for one dwelling: the interior a spectator walks into.
// Generated on the client from the room list so the wire stays small.
function interiorRooms(d: any): any[] {
  const rooms: string[] = d.rooms || [];
  if (rooms.length === 0) return [];
  const ground = Math.max(9, d.area_sqm / Math.max(1, d.storeys));
  const side = Math.sqrt(ground);
  const cols = Math.ceil(Math.sqrt(rooms.length));
  const rowsN = Math.ceil(rooms.length / cols);
  const cellW = side / cols;
  const cellH = side / rowsN;

  return rooms.map((name, i) => {
    const cx = -side / 2 + (i % cols) * cellW + cellW / 2;
    const cy = -side / 2 + Math.floor(i / cols) * cellH + cellH / 2;
    const [lat, lng] = [
      d.lat + cy / METERS_PER_DEG_LAT,
      d.lon + cx / (METERS_PER_DEG_LAT * Math.cos(d.lat * DEG2RAD))
    ];
    const hw = (cellW * 0.42) / (METERS_PER_DEG_LAT * Math.cos(d.lat * DEG2RAD));
    const hh = (cellH * 0.42) / METERS_PER_DEG_LAT;
    return {
      name,
      centre: [lng, lat],
      polygon: [
        [lng - hw, lat - hh],
        [lng + hw, lat - hh],
        [lng + hw, lat + hh],
        [lng - hw, lat + hh]
      ],
      color: ROOM_COLORS[name] || [120, 128, 140]
    };
  });
}

// Which room a chore happens in — so a spectator watching someone cook sees them standing
// in the kitchen, not hovering at the front door.
// Order matters: the first pattern that matches wins, so the specific chores come before
// the general ones ("washing up after breakfast" is kitchen work, not a meal).
const ROOM_KEYWORDS: [RegExp, string[]][] = [
  // Sleeping and settling children
  [/asleep|nap|bed|restless|turning in/i,
    ['master bedroom', 'bedroom', "children's room", 'main room', 'living space']],
  // Water: bathing, laundry, scrubbing, the tap
  [/bathing|leaking tap|washing clothes|scrubbing utensils|sorting laundry|press-wallah|fetching water/i,
    ['bathroom', 'shared washroom', 'cooking corner', 'kitchen']],
  // Study
  [/study|homework|exam/i, ['study', "children's room", 'living room', 'main room']],
  // Outdoors: the doorway, courtyard, balcony, plants, the vegetable cart
  [/balcon|garden|courtyard|gate|doorway|plants|sweeping|mopping|cart outside/i,
    ['balcony', 'garden', 'living room', 'main room', 'living space']],
  // Kitchen work, including clearing up after a meal
  [/cook|morning tea|kneading|cutting vegetab|masala|pakora|tiffin|washing up|dishes|ration|dinner plates/i,
    ['kitchen', 'cooking corner']],
  // Meals themselves happen at the table, not the stove
  [/eating|serving/i,
    ['dining room', 'living room', 'main room', 'living space', 'kitchen']],
  // Everything else is sitting-room life
  [/television|radio|newspaper|phone|neighbour|reading|prayers|supervis|help|ironing|locking|feeding/i,
    ['living room', 'drawing room', 'main room', 'living space']]
];

function roomForActivity(activity: string, rooms: string[]): string | null {
  if (!rooms || rooms.length === 0) return null;
  for (const [pattern, preferred] of ROOM_KEYWORDS) {
    if (!pattern.test(activity)) continue;
    const hit = preferred.find(r => rooms.includes(r));
    if (hit) return hit;
  }
  return rooms[0];
}

const ROOM_COLORS: Record<string, [number, number, number]> = {
  'living space': [196, 160, 112], 'living room': [196, 160, 112], 'drawing room': [204, 168, 120],
  'main room': [190, 156, 110], 'cooking corner': [214, 132, 88], 'kitchen': [214, 132, 88],
  bedroom: [128, 152, 196], 'master bedroom': [122, 148, 196], 'second bedroom': [138, 160, 200],
  "children's room": [150, 176, 208], bathroom: [130, 186, 196], 'shared washroom': [130, 186, 196],
  balcony: [150, 190, 140], garden: [122, 178, 116], study: [176, 146, 190],
  'dining room': [206, 178, 128], 'servant quarter': [160, 150, 138]
};

const PERSON_HEIGHT = 1.7; // metres, used for procedural people

// How each kind of working agent is drawn and described. The city is not only commuters:
// stalls, shops and delivery riders are simulated too and were previously invisible.
const ROLE_STYLE: Record<string, { label: string; color: [number, number, number]; height: number; radius: number }> = {
  citizen:        { label: 'Resident',       color: [244, 164, 96],  height: PERSON_HEIGHT, radius: 0.4 },
  citizen_away:   { label: 'Resident',       color: [147, 197, 253], height: PERSON_HEIGHT, radius: 0.4 },
  stall_owner:    { label: 'Stall owner',    color: [251, 146, 60],  height: 2.4,           radius: 1.1 },
  store_manager:  { label: 'Shopkeeper',     color: [167, 139, 250], height: 3.2,           radius: 1.5 },
  store_staff:    { label: 'Shop worker',    color: [196, 181, 253], height: 2.0,           radius: 0.6 },
  delivery_rider: { label: 'Delivery rider', color: [52, 211, 153],  height: 1.8,           radius: 0.7 }
};

function roleStyle(p: any) {
  if (p.role === 'citizen' || !p.role) {
    return ROLE_STYLE[p.place === 'home' ? 'citizen' : 'citizen_away'];
  }
  return ROLE_STYLE[p.role] || ROLE_STYLE.citizen;
}

// The engine speaks transport modes; the map has three 3D models.
function modelForMode(mode: string): 'car' | 'bus' | 'pedestrian' {
  if (mode === 'bus' || mode === 'metro') return 'bus';
  if (mode === 'walk' || mode === 'bike' || mode === 'bike_share') return 'pedestrian';
  return 'car'; // car, auto, e_rickshaw
}

const MODE_LABEL: Record<string, string> = {
  walk: 'on foot', bike: 'by cycle', bus: 'by bus', metro: 'by metro',
  auto: 'by auto', car: 'by car', bike_share: 'on a shared cycle', e_rickshaw: 'by e-rickshaw'
};

function titleCase(s: string) {
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
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

const METERS_PER_DEG_LAT = 111139;
const LIGHT_PHASE_MS = 8000; // full red/yellow/green cycle step

const PHASE_COLOR: Record<number, [number, number, number, number]> = {
  0: [239, 68, 68, 255],  // red
  1: [234, 179, 8, 255],  // amber
  2: [34, 197, 94, 255]   // green
};

// Real-world box dimensions (metres) for the model-free fallback.
const VEHICLE_BOX: Record<string, { length: number; width: number; height: number; color: [number, number, number] }> = {
  car: { length: 4.2, width: 1.8, height: 1.5, color: [226, 232, 240] },
  bus: { length: 11.0, width: 2.6, height: 3.2, color: [56, 189, 248] }
};

// Oriented, extruded vehicles built from geometry rather than a loaded model — this is
// what `getVehiclePolygon` above was written for.
function vehicleBoxLayer(id: string, data: any[], tick: number, selectedId: string | null) {
  const kind = id.startsWith('bus') ? 'bus' : 'car';
  const box = VEHICLE_BOX[kind];
  return new PolygonLayer({
    id: `${id}-boxes`,
    data,
    pickable: true,
    extruded: true,
    getPolygon: (d: any) => {
      const [lng, lat] = d.currentPosition || [0, 0];
      return getVehiclePolygon(lng, lat, d.currentAngle || 0, box.length, box.width);
    },
    getElevation: box.height,
    getFillColor: (d: any) =>
      (d.id === selectedId ? [250, 204, 21, 255] : [...box.color, 245]) as any,
    updateTriggers: { getPolygon: tick, getFillColor: selectedId }
  });
}

// Compass bearing (0 = north, clockwise) between two [lat, lng] points.
function bearingBetween(p1: number[], p2: number[]) {
  const dLat = p2[0] - p1[0];
  const dLng = (p2[1] - p1[1]) * Math.cos(p1[0] * DEG2RAD);
  return Math.atan2(dLng, dLat) / DEG2RAD;
}

// Shift a [lat, lng] point `meters` along `bearing` (degrees).
function offsetByBearing(lat: number, lng: number, bearing: number, meters: number): [number, number] {
  const rad = bearing * DEG2RAD;
  return [
    lat + (meters * Math.cos(rad)) / METERS_PER_DEG_LAT,
    lng + (meters * Math.sin(rad)) / (METERS_PER_DEG_LAT * Math.cos(lat * DEG2RAD))
  ];
}

// Approximate ground distance in meters between two [lng, lat] positions.
function metersBetween(a: number[], b: number[]) {
  const dx = (a[0] - b[0]) * METERS_PER_DEG_LAT * Math.cos(a[1] * DEG2RAD);
  const dy = (a[1] - b[1]) * METERS_PER_DEG_LAT;
  return Math.sqrt(dx * dx + dy * dy);
}

// Each junction runs its own cycle so the whole city does not switch at once.
function lightPhase(offset: number) {
  return (Math.floor(Date.now() / LIGHT_PHASE_MS) + offset) % 3; // 0 red, 1 yellow, 2 green
}

// Deterministic civilian identities, so an agent keeps the same name across reloads.
const FIRST_NAMES = [
  "Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Meera", "Karan", "Ishita",
  "Siddharth", "Neha", "Arjun", "Kavya", "Rahul", "Sanya", "Manish", "Divya",
  "Imran", "Fatima", "Tarun", "Pooja", "Nikhil", "Ritu", "Sameer", "Anjali",
  "Harpreet", "Simran", "Devansh", "Lakshmi", "Yusuf", "Zoya", "Aditya", "Radha"
];
const LAST_NAMES = [
  "Sharma", "Verma", "Iyer", "Khan", "Singh", "Nair", "Gupta", "Reddy",
  "Chopra", "Bose", "Mehta", "Joshi", "Kapoor", "Das", "Rao", "Malhotra"
];
const OCCUPATIONS = [
  "Software Engineer", "Schoolteacher", "Shopkeeper", "Doctor", "Auto Driver",
  "Journalist", "Chartered Accountant", "Student", "Civil Servant", "Chef",
  "Nurse", "Architect", "Bank Clerk", "Delivery Rider", "Tailor", "Musician"
];
const DESTINATIONS = [
  "Connaught Place", "Karol Bagh", "Chandni Chowk", "Janpath", "Barakhamba Road",
  "Paharganj", "Mandi House", "Rajendra Place", "Patel Chowk", "Gole Market"
];

function hashString(s: string) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

// A name is the one thing the engine does not model, so we invent it — deterministically,
// from the agent id. Everything else (occupation, age, household, destination) comes from
// the simulation: inventing those would put fiction next to fact in the same panel.
function personName(id: string): string {
  const h = hashString(id);
  return `${FIRST_NAMES[h % FIRST_NAMES.length]} ${LAST_NAMES[(h >> 5) % LAST_NAMES.length]}`;
}

function buildIdentity(id: string, type: string) {
  const h = hashString(id);
  const name = personName(id);
  return {
    name: type === 'bus' ? `Route ${400 + (h % 99)} — ${name}` : name,
    // Only used by the offline demo playback, which has no engine to ask.
    occupation: OCCUPATIONS[(h >> 9) % OCCUPATIONS.length],
    age: 19 + (h % 45),
    destination: DESTINATIONS[(h >> 13) % DESTINATIONS.length],
    role: type === 'bus' ? 'Bus Driver' : type === 'pedestrian' ? 'Pedestrian' : 'Motorist'
  };
}

// How a working agent's "name" should read. A stall is known by its owner and its trade,
// not by a bare personal name floating over the pavement.
function workingAgentName(p: any): string {
  const person = personName(p.agent_id);
  const surname = person.split(' ')[1];
  switch (p.role) {
    case 'stall_owner': {
      const trade = (p.detail?.['Stall type'] || 'roadside').toLowerCase();
      return `${person}'s ${trade} stall`;
    }
    case 'store_manager':
      return `${surname} General Store`;
    case 'store_staff':
      return `${person} — shop assistant`;
    case 'delivery_rider':
      return `${person} — delivery rider`;
    default:
      return person;
  }
}

// Where a stationary agent is, in words.
const PLACE_LABEL: Record<string, string> = {
  home: 'At home',
  away: 'Out at work',
  stall: 'At their stall',
  store: 'At the shop',
  depot: 'On the delivery round'
};

// Append to an agent's activity log, keeping only the recent entries.
function logActivity(item: any, time: number, text: string) {
  if (!item.activityLog) item.activityLog = [];
  const last = item.activityLog[0];
  if (last && last.text === text) return;
  item.activityLog.unshift({ time, text });
  if (item.activityLog.length > 12) item.activityLog.pop();
}

const INITIAL_VIEW_STATE = {
  longitude: 77.2197,
  latitude: 28.6328,
  zoom: 16.5,
  pitch: 50,
  bearing: 0
};

const DashboardMap: React.FC<DashboardMapProps> = ({ rainIntensity, congestionFee, busCapacity, timeOfDay, activeOverlay, liveAgents, simClock, gridCells = [], presences = [], dwellings = {} }) => {
  const [roadData, setRoadData] = useState<any>(null);
  const [rawAgentsData, setRawAgentsData] = useState<any[]>([]);
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

  // The .glb models are optional. A ScenegraphLayer whose model fails to load renders
  // *nothing and reports nothing*, so a missing file would silently empty the city — and
  // a static host that answers 404s with index.html returns 200 with HTML, which looks
  // like a success. Verify the glTF magic bytes, and fall back to procedural geometry.
  const [modelsOk, setModelsOk] = useState<boolean | null>(null);
  useEffect(() => {
    let cancelled = false;
    const files = ['/car.glb', '/bus.glb', '/person.glb', '/tree.glb', '/traffic_light.glb'];
    Promise.all(files.map(async url => {
      try {
        const res = await fetch(url);
        if (!res.ok) return false;
        const head = new Uint8Array(await (await res.blob()).slice(0, 4).arrayBuffer());
        return String.fromCharCode(...head) === 'glTF';
      } catch {
        return false;
      }
    })).then(results => {
      if (cancelled) return;
      const ok = results.every(Boolean);
      setModelsOk(ok);
      if (!ok) {
        console.warn('[map] 3D models unavailable — drawing agents as procedural geometry.');
      }
    });
    return () => { cancelled = true; };
  }, []);

  // Until the check resolves, draw the shapes: better a plain city than an empty one.
  const useModels = modelsOk === true;

  // Stationary citizens, reachable from the animation loop without re-subscribing it.
  const stationaryRef = useRef<Record<string, any>>({});
  // Chore history per citizen, so the dossier keeps a diary of their day at home.
  const stationaryLogRef = useRef<Record<string, { time: number; text: string }[]>>({});
  useEffect(() => {
    const byId: Record<string, any> = {};
    const now = Date.now();
    presences.forEach((p: any) => {
      byId[p.agent_id] = p;
      const log = stationaryLogRef.current[p.agent_id] || (stationaryLogRef.current[p.agent_id] = []);
      if (log[0]?.text !== p.activity) {
        log.unshift({ time: now, text: p.activity });
        if (log.length > 12) log.pop();
      }
    });
    stationaryRef.current = byId;
  }, [presences]);

  useEffect(() => {
    fetch('/rajiv_chowk_roads.json').then(res => res.json()).then(data => setRoadData(data));
    fetch('/rajiv_chowk_walk.json').then(res => res.json()).then(data => setWalkData(data));
    fetch('/rajiv_chowk_agents.json').then(res => res.json()).then(data => setRawAgentsData(data));
    // Buildings are not fetched: the Mapbox Standard style already renders Delhi's 3D
    // buildings natively, so pulling the 9 MB local copy only to discard it was waste.
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
      const withPhases = data.map((tl: any, i: number) => ({ ...tl, phaseOffset: i % 3 }));
      setTrafficLights(withPhases);
      trafficLightsRef.current = withPhases;
    });
  }, []);

  useEffect(() => {
    rainRef.current = rainIntensity;
    feeRef.current = congestionFee;
  }, [rainIntensity, congestionFee]);

  useEffect(() => {
    selectedAgentRef.current = selectedAgentId;
  }, [selectedAgentId]);

  // Engine-driven mode: the simulation core is streaming real citizens, so the baked
  // demo routes stand down entirely.
  const engineMode = !!(liveAgents && liveAgents.length > 0);
  const engineModeRef = useRef(engineMode);
  const simClockRef = useRef(simClock);
  useEffect(() => { engineModeRef.current = engineMode; }, [engineMode]);

  // The engine's citizens are spread across the whole modelled city, not just the block
  // under the default camera — pull back once so the live run is actually visible.
  const framedRef = useRef(false);
  useEffect(() => {
    if (!engineMode || framedRef.current || povMode) return;
    framedRef.current = true;
    const pts = (liveAgents || []).flatMap((l: any) => l.polyline || []);
    if (pts.length === 0) return;
    const lats = pts.map((p: number[]) => p[0]);
    const lngs = pts.map((p: number[]) => p[1]);
    setViewState(prev => ({
      ...prev,
      latitude: (Math.min(...lats) + Math.max(...lats)) / 2,
      longitude: (Math.min(...lngs) + Math.max(...lngs)) / 2,
      zoom: 13
    }));
  }, [engineMode, liveAgents, povMode]);
  useEffect(() => { simClockRef.current = simClock; }, [simClock]);

  useEffect(() => {
    if (!engineMode) return;
    // NB: `Map` in this module is react-map-gl's component, so index by plain object.
    const existing: Record<string, any> = {};
    agentsRef.current.forEach(a => { existing[a.id] = a; });
    agentsRef.current = (liveAgents || []).map((leg: any, i: number) => {
      const model = modelForMode(leg.mode);
      const path = leg.polyline || [];
      let pathMeters = 0;
      for (let k = 0; k < path.length - 1; k++) {
        pathMeters += metersBetween([path[k][1], path[k][0]], [path[k + 1][1], path[k + 1][0]]);
      }
      const prior = existing[leg.agent_id];
      // Same citizen, same leg — keep their accumulated history.
      if (prior && prior.startMinute === leg.start_minute) return prior;
      return {
        ...buildIdentity(leg.agent_id, model),
        id: leg.agent_id,
        type: model,
        mode: leg.mode,
        occupation: leg.occupation ? titleCase(leg.occupation) : prior?.occupation,
        destination: titleCase(leg.destination_activity || 'work'),
        path,
        pathMeters,
        startMinute: leg.start_minute,
        durationMinutes: leg.duration_minutes,
        progress: 0,
        index: i,
        currentPosition: path.length > 0 ? [path[0][1], path[0][0]] : [0, 0],
        currentAngle: path.length > 1 ? bearingBetween(path[0], path[1]) : 0,
        currentKmh: leg.duration_minutes > 0 ? (pathMeters / 1000) / (leg.duration_minutes / 60) : 0,
        activity: 'Departing',
        activityLog: prior ? prior.activityLog : [],
        trips: prior ? prior.trips + 1 : 0
      };
    });
  }, [liveAgents, engineMode]);

  useEffect(() => {
    if (engineMode) return;
    if (rawAgentsData && rawAgentsData.length > 0) {
      agentsRef.current = rawAgentsData.map((agent, i) => {
        const path = agent.path || [];
        // Route length in metres, used to report a real km/h speed.
        let pathMeters = 0;
        for (let k = 0; k < path.length - 1; k++) {
          pathMeters += metersBetween([path[k][1], path[k][0]], [path[k + 1][1], path[k + 1][0]]);
        }
        return {
          ...agent,
          ...buildIdentity(agent.id, agent.type),
          path,
          pathMeters,
          // Stagger departures so agents do not all start bumper to bumper.
          progress: (i * 0.137) % 1,
          index: i,
          currentPosition: path.length > 0 ? [path[0][1], path[0][0]] : [0, 0],
          currentAngle: path.length > 1 ? bearingBetween(path[0], path[1]) : 0,
          currentSpeed: 0,
          dwellUntil: 0,
          nextStopIndex: agent.type === 'bus' ? 0.2 : 1,
          activity: 'Setting off',
          activityLog: [] as { time: number; text: string }[],
          trips: 0
        };
      });
    }
  }, [rawAgentsData]);

  useEffect(() => {
    const animate = () => {
      const now = Date.now();
      const vehicles = agentsRef.current.filter(a => a.type !== 'pedestrian' && a.currentPosition);

      // Simulated minutes, interpolated between ticks so motion is continuous.
      const clock = simClockRef.current;
      const simMinutes = clock
        ? clock.minutes + ((now - clock.receivedAt) / 1000) * clock.minutesPerSecond
        : 0;

      agentsRef.current.forEach(item => {
        if (!item.path || item.path.length < 2) return;

        // Engine-driven agents: the simulation core owns timing (its travel-time estimate
        // already includes congestion), so the client only interpolates geometry.
        if (engineModeRef.current) {
          const elapsed = simMinutes - item.startMinute;
          item.progress = Math.max(0, Math.min(1, elapsed / Math.max(item.durationMinutes, 0.01)));

          const totalSeg = item.path.length - 1;
          const seg = Math.min(Math.floor(item.progress * totalSeg), totalSeg - 1);
          const segT = (item.progress * totalSeg) - seg;
          const q1 = item.path[seg];
          const q2 = item.path[seg + 1];
          if (!q1 || !q2) return;

          const eLat = q1[0] + (q2[0] - q1[0]) * segT;
          const eLng = q1[1] + (q2[1] - q1[1]) * segT;

          const want = bearingBetween(q1, q2);
          let d = want - item.currentAngle;
          while (d < -180) d += 360;
          while (d > 180) d -= 360;
          item.currentAngle = (item.currentAngle + d * 0.15 + 360) % 360;

          const side = item.type === 'pedestrian' ? 5.5 : (item.type === 'bus' ? 3.2 : 2.6);
          const [aLat, aLng] = offsetByBearing(eLat, eLng, item.currentAngle - 90, side);
          item.currentPosition = [aLng, aLat];

          const label = item.progress >= 1
            ? `Arrived at ${item.destination}`
            : `Travelling ${MODE_LABEL[item.mode] || ''} to ${item.destination}`;
          if (label !== item.activity) {
            item.activity = label;
            logActivity(item, now, label);
          }
          return;
        }

        const isVehicle = item.type !== 'pedestrian';
        let mustStop = false;
        let reason = '';

        // Buses dwell at stops spaced along their route.
        if (item.type === 'bus' && item.progress >= item.nextStopIndex && now > item.dwellUntil) {
          item.dwellUntil = now + 5000;
          item.nextStopIndex = Math.min(item.nextStopIndex + 0.2, 1.1);
        }
        if (now < item.dwellUntil) {
          mustStop = true;
          reason = 'Halted at a bus stop, passengers boarding';
        }

        // Hold at a red or amber signal, but only for the junction ahead of us.
        if (!mustStop && isVehicle) {
          const headingRad = item.currentAngle * DEG2RAD;
          const dirLng = Math.sin(headingRad);
          const dirLat = Math.cos(headingRad);
          for (const tl of trafficLightsRef.current) {
            if (lightPhase(tl.phaseOffset) === 2) continue;
            const dist = metersBetween(tl.position, item.currentPosition);
            if (dist > 22) continue;
            const dot = (tl.position[0] - item.currentPosition[0]) * dirLng
                      + (tl.position[1] - item.currentPosition[1]) * dirLat;
            if (dot > 0) {
              mustStop = true;
              reason = lightPhase(tl.phaseOffset) === 0
                ? 'Waiting at a red signal'
                : 'Slowing for an amber signal';
              break;
            }
          }
        }

        // Car following: never drive into the vehicle ahead in our lane.
        if (!mustStop && isVehicle) {
          const headingRad = item.currentAngle * DEG2RAD;
          const dirLng = Math.sin(headingRad);
          const dirLat = Math.cos(headingRad);
          const gap = item.type === 'bus' ? 16 : 11;
          for (const other of vehicles) {
            if (other.id === item.id) continue;
            if (metersBetween(item.currentPosition, other.currentPosition) > gap) continue;
            const angleDiff = Math.abs(((item.currentAngle - other.currentAngle + 540) % 360) - 180);
            if (angleDiff < 135) continue; // opposing traffic, different lane
            const dot = (other.currentPosition[0] - item.currentPosition[0]) * dirLng
                      + (other.currentPosition[1] - item.currentPosition[1]) * dirLat;
            if (dot > 0) {
              mustStop = true;
              reason = `Queued behind ${other.name}`;
              break;
            }
          }
        }

        // Ease between cruising and stopped instead of teleport-stopping.
        const cruise = item.speed * (1 - rainRef.current / 200);
        const target = mustStop ? 0 : cruise;
        item.currentSpeed += (target - item.currentSpeed) * (mustStop ? 0.12 : 0.05);
        item.progress += item.currentSpeed;

        // At the destination, turn around and drive the route back — no teleporting.
        if (item.progress >= 1) {
          item.path = [...item.path].reverse();
          item.progress = 0;
          item.nextStopIndex = item.type === 'bus' ? 0.2 : 1;
          item.trips += 1;
          logActivity(item, now, `Arrived at ${item.destination}, heading back`);
        }

        // Narrate what this civilian is doing right now.
        const kmh = item.currentSpeed * item.pathMeters * 60 * 3.6;
        let activity = reason;
        if (!activity) {
          if (item.type === 'pedestrian') activity = `Walking towards ${item.destination}`;
          else if (kmh < 8) activity = 'Crawling through congestion';
          else activity = `Driving towards ${item.destination}`;
        }
        // Hysteresis, so a wobble around a threshold does not spam the log.
        if (activity !== item.activity && now - (item.lastActivityChange || 0) > 900) {
          item.lastActivityChange = now;
          item.activity = activity;
          logActivity(item, now, activity);
        }
        item.currentKmh = kmh;

        const totalSegments = item.path.length - 1;
        const currentSegment = Math.min(Math.floor(item.progress * totalSegments), totalSegments - 1);
        const segmentProgress = (item.progress * totalSegments) - currentSegment;

        const p1 = item.path[currentSegment];
        const p2 = item.path[currentSegment + 1];
        if (!p1 || !p2) return;

        const lat = p1[0] + (p2[0] - p1[0]) * segmentProgress;
        const lng = p1[1] + (p2[1] - p1[1]) * segmentProgress;

        const targetAngle = bearingBetween(p1, p2);
        let diff = targetAngle - item.currentAngle;
        while (diff < -180) diff += 360;
        while (diff > 180) diff -= 360;
        item.currentAngle = (item.currentAngle + diff * 0.15 + 360) % 360;

        // Delhi drives on the left: vehicles hug their own lane, pedestrians walk the footpath.
        const lateral = item.type === 'pedestrian' ? 5.5 : (item.type === 'bus' ? 3.2 : 2.6);
        const [offLat, offLng] = offsetByBearing(lat, lng, item.currentAngle - 90, lateral);
        item.currentPosition = [offLng, offLat];
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
        } else {
          // Not on the road — they are at home or at a destination. Stand over the spot
          // and look down into the floor plan, drifting slowly so the room reads as 3D.
          const still = stationaryRef.current[selectedAgentRef.current];
          if (still) {
            // Slow orbit so a stationary subject still reads as three-dimensional.
            const drift = (now / 90) % 360;
            // Indoors we look down into the floor plan; at a stall or shop we stand at
            // street level beside it; at a workplace we hover just above the doorway.
            const shot = still.place === 'home'
              ? { zoom: 21.2, pitch: 62 }
              : (still.place === 'stall' || still.place === 'store')
                ? { zoom: 20.8, pitch: 72 }
                : { zoom: 20.2, pitch: 76 };
            setViewState(prev => ({
              ...prev,
              longitude: still.lon,
              latitude: still.lat,
              ...shot,
              bearing: drift
            }));
          }
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


  const visibleAgents = agentsRef.current.filter(item => {
    if (activeOverlay === "Transit Overlay" && item.type !== 'bus') return false;
    // In engine mode the congestion fee changes real mode choice upstream, so hiding
    // cars here would double-count the policy.
    if (!engineMode && item.type === "car") {
      // 1 rupee of congestion fee = 0.6% reduction in cars.
      // Every 1% increase in bus capacity above 20% baseline = 0.5% reduction in cars.
      const carReductionPct = (congestionFee * 0.6) + (busCapacity > 20 ? (busCapacity - 20) * 0.5 : 0);
      if ((item.index % 100) < carReductionPct) return false;
    }
    return true;
  });

  // A followed citizen is either on the road (an animated agent) or stationary (a
  // presence). Both open the same dossier, so selection works wherever they are.
  const travellingAgent = selectedAgentId
    ? agentsRef.current.find(a => a.id === selectedAgentId)
    : null;
  const stationary = selectedAgentId
    ? presences.find((p: any) => p.agent_id === selectedAgentId)
    : null;
  const selectedAgent = travellingAgent || (stationary ? {
    id: stationary.agent_id,
    // Name is ours; every fact below is the engine's.
    name: stationary.role && stationary.role !== 'citizen'
      ? workingAgentName(stationary)
      : personName(stationary.agent_id),
    role: roleStyle(stationary).label,
    occupation: stationary.detail?.Occupation ? titleCase(stationary.detail.Occupation) : null,
    age: stationary.detail?.Age || null,
    activity: stationary.activity,
    place: stationary.place,
    placeLabel: PLACE_LABEL[stationary.place] || 'In the city',
    atHome: stationary.place === 'home',
    detail: stationary.detail || {},
    currentKmh: 0,
    progress: 0,
    trips: 0,
    activityLog: stationaryLogRef.current[stationary.agent_id] || []
  } : null);

  // In first-person we sit inside the agent, so its own model must not block the view.
  const renderableAgents = povMode && selectedAgentId
    ? visibleAgents.filter(a => a.id !== selectedAgentId)
    : visibleAgents;

  const mapStyle = "mapbox://styles/mapbox/standard"; // Mapbox Standard supports built-in 3D buildings and trees

  // Homes of the followed citizens, and the people currently standing in them.
  const homeList = useMemo(() => Object.entries(dwellings).map(([agentId, d]: any) => ({
    agentId,
    ...d,
    polygon: dwellingFootprint(d),
    height: dwellingHeight(d)
  })), [dwellings]);

  const selectedHome = selectedAgentId ? dwellings[selectedAgentId] : null;
  const selectedPresence = selectedAgentId
    ? presences.find((p: any) => p.agent_id === selectedAgentId)
    : null;
  const isIndoors = !!(povMode && selectedHome && selectedPresence?.place === 'home');

  // Only the home being spectated is opened up — drawing every interior would bury the city.
  const openRooms = useMemo(
    () => (isIndoors && selectedHome ? interiorRooms(selectedHome) : []),
    [isIndoors, selectedHome]
  );

  // Which room the spectated citizen is currently in, and its centre.
  const activeRoom = useMemo(() => {
    if (!isIndoors || !selectedPresence || !selectedHome) return null;
    const name = roomForActivity(selectedPresence.activity, selectedHome.rooms || []);
    return openRooms.find((r: any) => r.name === name) || null;
  }, [isIndoors, selectedPresence, selectedHome, openRooms]);

  // A stationary citizen stands at their home; once we are inside, the spectated one moves
  // to whichever room their chore belongs to.
  const standingPeople = useMemo(() => presences.map((p: any) => {
    const inRoom = p.agent_id === selectedAgentId && activeRoom;
    return {
      ...p,
      id: p.agent_id,
      // Named here so hovering anyone — resident, stallholder, rider — says who they are.
      name: p.role && p.role !== 'citizen' ? workingAgentName(p) : personName(p.agent_id),
      position: inRoom ? activeRoom.centre : [p.lon, p.lat],
      isSelected: p.agent_id === selectedAgentId
    };
  }), [presences, selectedAgentId, activeRoom]);

  // --- Level of detail -----------------------------------------------------------------
  // The base map is the city; our job is to add the people to it, not to repaint it. Detail
  // is revealed as the camera comes down, so a wide shot stays readable and a close shot is
  // full of life. Thresholds are deck.gl zoom levels: 13 ~ whole study area, 16 ~ a few
  // blocks, 17.5 ~ one street.
  const zoom = viewState.zoom;
  const showWorkplaces = zoom >= 14.5;
  const showResidents = zoom >= 16;
  const showHomes = zoom >= 17;
  const showStreetDetail = zoom >= 15.5;

  // Residents are people; stalls, shops and riders are places of work.
  const standingCitizens = useMemo(
    () => (showResidents ? standingPeople.filter((p: any) => !p.role || p.role === 'citizen') : []),
    [standingPeople, showResidents]
  );
  const workingAgents = useMemo(
    () => (showWorkplaces ? standingPeople.filter((p: any) => p.role && p.role !== 'citizen') : []),
    [standingPeople, showWorkplaces]
  );

  // Homes near the camera only, plus whoever is being followed. Distance is measured
  // against the view centre, which is cheap and good enough for culling.
  const visibleHomes = useMemo(() => {
    // Indoors the selected home is replaced by its floor plan, but the neighbours must
    // still be culled — standing in one kitchen is no reason to draw the other 1,199.
    const radiusDeg = 0.004; // ~450 m
    const near = homeList.filter(h =>
      h.agentId !== selectedAgentId &&
      Math.abs(h.lat - viewState.latitude) < radiusDeg &&
      Math.abs(h.lon - viewState.longitude) < radiusDeg
    );
    if (isIndoors) return near.slice(0, 250);

    const selected = homeList.filter(h => h.agentId === selectedAgentId);
    if (!showHomes) return selected;
    return [...selected, ...near.slice(0, 250)];
  }, [homeList, showHomes, isIndoors, selectedAgentId, viewState.latitude, viewState.longitude]);

  const layers = [
    // Base ground and 3D buildings come from the Mapbox Standard style.

    // Homes are only drawn close up. Mapbox already renders Delhi's real buildings, so
    // stamping a box on every one of a thousand home nodes buries the city it is meant to
    // illustrate. Up close (or for the citizen being followed) they become useful again.
    visibleHomes.length > 0 && new PolygonLayer({
      id: 'dwellings-layer',
      data: visibleHomes,
      pickable: true,
      extruded: true,
      wireframe: false,
      getPolygon: (d: any) => d.polygon,
      getElevation: (d: any) => d.height,
      getFillColor: (d: any) => {
        const base = DWELLING_STYLE[d.kind]?.color || [160, 160, 160];
        return d.agentId === selectedAgentId
          ? [250, 204, 21, 255]
          : [...base, isDay ? 190 : 165] as any;
      },
      updateTriggers: { getFillColor: selectedAgentId }
    }),

    // The rooms of the home being spectated, laid out as a floor plan you stand in.
    openRooms.length > 0 && new PolygonLayer({
      id: 'interior-rooms-layer',
      data: openRooms,
      pickable: false,
      extruded: true,
      getPolygon: (d: any) => d.polygon,
      // The occupied room is raised and lit so you can see at a glance where they are.
      getElevation: (d: any) => (activeRoom && d.name === activeRoom.name ? 0.9 : 0.35),
      getFillColor: (d: any) =>
        activeRoom && d.name === activeRoom.name
          ? [250, 204, 21, 250]
          : ([...d.color, 235] as any),
      updateTriggers: {
        getElevation: activeRoom?.name,
        getFillColor: activeRoom?.name
      }
    }),

    // Room labels, so you can tell the kitchen from the bedroom while inside.
    openRooms.length > 0 && new TextLayer({
      id: 'interior-labels-layer',
      data: openRooms,
      getPosition: (d: any) => d.centre,
      getText: (d: any) => d.name,
      getSize: 13,
      sizeUnits: 'pixels',
      getColor: [15, 23, 42, 255],
      background: true,
      getBackgroundColor: [255, 255, 255, 210],
      backgroundPadding: [3, 2],
      billboard: true
    }),

    // Everyone who is at home or has arrived somewhere — without these the city empties
    // out between rush hours.
    // Residents at home or at work get a person model; the working city — stalls, shops
    // and delivery riders — is drawn as sized, coloured pitches so trades are tellable
    // apart at a glance.
    standingCitizens.length > 0 && (useModels ? new ScenegraphLayer({
      id: 'standing-people-layer',
      data: standingCitizens,
      pickable: true,
      scenegraph: '/person.glb',
      getPosition: (d: any) => d.position,
      getOrientation: (d: any) => [0, (hashString(d.agent_id) % 360), 0],
      sizeScale: 1.5,
      _lighting: 'pbr'
    }) : new ScatterplotLayer({
      id: 'standing-people-columns-layer',
      data: standingCitizens,
      pickable: true,
      radiusUnits: 'meters',
      radiusMinPixels: 2,
      radiusMaxPixels: 6,
      getPosition: (d: any) => d.position,
      getRadius: 0.9,
      getFillColor: (d: any) =>
        d.isSelected ? [250, 204, 21, 255] : ([...roleStyle(d).color, 200] as any),
      updateTriggers: { getFillColor: selectedAgentId }
    })),

    // Stalls, shops and riders read as map pins rather than blocks of colour: flat, small,
    // and capped in screen size so they never grow into slabs over the buildings.
    workingAgents.length > 0 && new ScatterplotLayer({
      id: 'working-agents-layer',
      data: workingAgents,
      pickable: true,
      radiusUnits: 'meters',
      radiusMinPixels: 3,
      radiusMaxPixels: 9,
      stroked: true,
      lineWidthMinPixels: 1,
      getPosition: (d: any) => d.position,
      getRadius: (d: any) => roleStyle(d).radius * 2.2,
      getFillColor: (d: any) =>
        d.isSelected ? [250, 204, 21, 255] : ([...roleStyle(d).color, 225] as any),
      getLineColor: isDay ? [30, 41, 59, 160] : [226, 232, 240, 120],
      updateTriggers: { getFillColor: selectedAgentId, getLineColor: isDay }
    }),

    // Parks — the base map already tints green space, so this is a faint wash that only
    // appears close up, never a slab of colour over the city.
    parksData && showStreetDetail && new GeoJsonLayer({
      id: 'parks-layer',
      data: parksData,
      pickable: false,
      filled: true,
      stroked: false,
      getFillColor: isDay ? [134, 190, 120, 70] : [26, 62, 38, 90]
    }),

    // Street trees scattered through the parks.
    treeData.length > 0 && showHomes && (useModels ? new ScenegraphLayer({
      id: 'trees-layer',
      data: treeData,
      pickable: false,
      scenegraph: '/tree.glb',
      getPosition: (d: any) => d.position,
      getScale: (d: any) => [d.radius * 0.5, d.height * 0.2, d.radius * 0.5],
      sizeScale: 1,
      _lighting: 'pbr'
    }) : new ColumnLayer({
      id: 'trees-columns-layer',
      data: treeData,
      pickable: false,
      diskResolution: 6,
      radius: 1,
      radiusUnits: 'meters',
      extruded: true,
      getPosition: (d: any) => d.position,
      getElevation: (d: any) => d.height,
      getLineWidth: 0,
      getFillColor: isDay ? [64, 138, 74, 235] : [26, 72, 42, 235]
    })),

    // The drivable network the vehicles are routed on. Mapbox already draws the streets,
    // so this is opt-in via the Road Network overlay and deliberately thin.
    roadData && activeOverlay === "Road Network" && showStreetDetail && new GeoJsonLayer({
      id: 'roads-layer',
      data: roadData,
      pickable: false,
      stroked: true,
      getLineColor: isDay ? [59, 130, 246, 90] : [96, 165, 250, 80],
      getLineWidth: 2,
      lineWidthUnits: 'meters',
      lineWidthMinPixels: 1
    }),

    // Population heat: every citizen the engine simulates, not just the followed cohort.
    gridCells.length > 0 && activeOverlay === "Agent Congestion" && new ColumnLayer({
      id: 'congestion-grid-layer',
      data: gridCells,
      diskResolution: 4,
      radius: 260,
      extruded: true,
      pickable: true,
      getPosition: (d: any) => [d.lon, d.lat],
      getElevation: (d: any) => d.density * 3,
      // Green (clear) through amber to red (jammed).
      getFillColor: (d: any) => [
        60 + Math.round(195 * d.congestion),
        200 - Math.round(150 * d.congestion),
        90 - Math.round(60 * d.congestion),
        180
      ],
      updateTriggers: { getElevation: gridCells, getFillColor: gridCells }
    }),

    // Rajiv Chowk interchange marker.
    new IconLayer({
      id: 'metro-station-layer',
      data: [{ position: [77.2197, 28.6328] }],
      pickable: false,
      getIcon: () => ({ url: METRO_URL, width: 120, height: 120, anchorY: 60 }),
      getPosition: (d: any) => d.position,
      getSize: 52,
      sizeUnits: 'pixels',
      billboard: true
    }),

    walkData && showHomes && new GeoJsonLayer({
      id: 'walk-layer',
      data: walkData,
      pickable: false,
      stroked: true,
      getLineColor: isDay ? [148, 163, 184, 90] : [203, 213, 225, 70],
      getLineWidth: 1.5,
      lineWidthUnits: 'meters',
      lineWidthMinPixels: 1
    }),

    // Moving traffic, always visible. A 4 m car is sub-pixel in a wide shot, so this keeps
    // a minimum dot under every vehicle — the flow of the city stays legible at any zoom,
    // and at night it doubles as the underglow.
    new ScatterplotLayer({
      id: 'neon-lights-layer',
      data: visibleAgents,
      getPosition: (d: any) => d.currentPosition,
      getFillColor: (d: any) => {
        const alpha = isDay ? 190 : 150;
        if (d.type === 'pedestrian') return [250, 204, 21, alpha];
        return d.type === 'bus' ? [56, 189, 248, alpha] : [248, 113, 113, alpha];
      },
      getRadius: (d: any) => d.type === 'bus' ? 12 : (d.type === 'pedestrian' ? 4 : 8),
      radiusUnits: 'meters',
      radiusMinPixels: 1.5,
      radiusMaxPixels: 10,
      opacity: isDay ? 0.9 : 0.8,
      updateTriggers: { getPosition: tick, getFillColor: isDay }
    }),

    // Cars
    useModels ? new ScenegraphLayer({
      id: 'cars-layer',
      data: renderableAgents.filter(a => a.type === 'car'),
      pickable: true,
      scenegraph: '/car.glb',
      getPosition: (d: any) => d.currentPosition || [0, 0, 0],
      getOrientation: (d: any) => [0, -(d.currentAngle || 0), 0], // Rotate to face heading natively
      sizeScale: 1.2,
      _lighting: 'pbr',
      updateTriggers: { getPosition: tick, getOrientation: tick }
    }) : vehicleBoxLayer('cars-layer', renderableAgents.filter(a => a.type === 'car'), tick, selectedAgentId),

    // Buses
    useModels ? new ScenegraphLayer({
      id: 'buses-layer',
      data: renderableAgents.filter(a => a.type === 'bus'),
      pickable: true,
      scenegraph: '/bus.glb',
      getPosition: (d: any) => d.currentPosition || [0, 0, 0],
      getOrientation: (d: any) => [0, -(d.currentAngle || 0), 0],
      sizeScale: 1.2,
      _lighting: 'pbr',
      updateTriggers: { getPosition: tick, getOrientation: tick }
    }) : vehicleBoxLayer('buses-layer', renderableAgents.filter(a => a.type === 'bus'), tick, selectedAgentId),

    // Pedestrians
    useModels ? new ScenegraphLayer({
      id: 'pedestrians-layer',
      data: renderableAgents.filter(a => a.type === 'pedestrian'),
      pickable: true,
      scenegraph: '/person.glb',
      getPosition: (d: any) => d.currentPosition || [0, 0, 0],
      getOrientation: (d: any) => [0, -(d.currentAngle || 0), 0],
      sizeScale: 1.5,
      _lighting: 'pbr',
      updateTriggers: { getPosition: tick, getOrientation: tick }
    }) : new ColumnLayer({
      id: 'pedestrians-columns-layer',
      data: renderableAgents.filter(a => a.type === 'pedestrian'),
      pickable: true,
      diskResolution: 6,
      radius: 0.4,
      extruded: true,
      getPosition: (d: any) => d.currentPosition || [0, 0, 0],
      getElevation: PERSON_HEIGHT,
      getFillColor: (d: any) =>
        d.id === selectedAgentId ? [250, 204, 21, 255] : [250, 204, 21, 220],
      updateTriggers: { getPosition: tick, getFillColor: selectedAgentId }
    }),

    // Traffic lights. The signal head carries the phase colour; with no material in the
    // .glb there is nothing for getColor to tint, so the procedural version is the one
    // that actually shows red/amber/green.
    useModels && new ScenegraphLayer({
      id: 'traffic-lights-3d-layer',
      data: trafficLights,
      pickable: false,
      scenegraph: '/traffic_light.glb',
      getPosition: (d: any) => d.position,
      getOrientation: [0, 0, 0], // Stand vertically
      sizeScale: 2,
      _lighting: 'pbr',
      getColor: (d: any) => PHASE_COLOR[lightPhase(d.phaseOffset)],
      updateTriggers: { getColor: tick }
    }),

    // Signal head — always drawn, so the phase is readable whether or not models loaded.
    trafficLights.length > 0 && new ColumnLayer({
      id: 'traffic-light-heads-layer',
      data: trafficLights,
      pickable: false,
      diskResolution: 8,
      radius: 0.5,
      extruded: true,
      elevationScale: 1,
      getPosition: (d: any) => d.position,
      getElevation: 3.4,
      getFillColor: (d: any) => PHASE_COLOR[lightPhase(d.phaseOffset)],
      updateTriggers: { getFillColor: tick }
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
          const layerId = info.layer?.id;
          const AGENT_LAYERS = [
            'cars-layer', 'cars-layer-boxes', 'buses-layer', 'buses-layer-boxes',
            'pedestrians-layer', 'pedestrians-columns-layer',
            'standing-people-layer', 'standing-people-columns-layer',
            'working-agents-layer'
          ];
          if (info.object && AGENT_LAYERS.includes(layerId || '')) {
            setSelectedAgentId(info.object.id);
            setPovMode(true);
          } else if (info.object && layerId === 'dwellings-layer') {
            // Clicking a house follows whoever lives there.
            setSelectedAgentId(info.object.agentId);
            setPovMode(true);
          } else {
            setSelectedAgentId(null);
            setPovMode(false);
          }
        }}
        controller={true}
        layers={layers as any}
        effects={[lightingEffect]}
        getTooltip={({ object }: any) =>
          object && object.name
            ? { text: `${object.name}\n${object.activity || ''}`, style: { fontSize: '12px', borderRadius: '8px' } }
            : null
        }
      >
        {MAPBOX_TOKEN && (
          <Map 
            mapStyle={mapStyle}
            mapboxAccessToken={MAPBOX_TOKEN} 
          />
        )}
      </DeckGL>
      
      {/* Legend + level-of-detail hint. Detail is revealed by zooming, so say so rather
          than leaving the map looking empty from above. */}
      {engineMode && !selectedAgent && (
        <div className="absolute bottom-8 right-6 z-[1000] px-4 py-3 rounded-xl bg-slate-900/80 backdrop-blur-md border border-slate-700/50 shadow-xl text-white">
          <div className="text-[9px] font-bold uppercase tracking-widest text-slate-400 mb-2">
            Who is out there
          </div>
          <ul className="space-y-1">
            {[
              ['Traffic', [248, 113, 113], true],
              ['Buses', [56, 189, 248], true],
              ['Stalls', ROLE_STYLE.stall_owner.color, showWorkplaces],
              ['Shops', ROLE_STYLE.store_manager.color, showWorkplaces],
              ['Delivery', ROLE_STYLE.delivery_rider.color, showWorkplaces],
              ['Residents', ROLE_STYLE.citizen.color, showResidents]
            ].map(([label, color, on]: any) => (
              <li key={label} className={`flex items-center gap-2 text-[11px] ${on ? 'text-slate-200' : 'text-slate-500'}`}>
                <span
                  className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ background: `rgb(${color.join(',')})`, opacity: on ? 1 : 0.35 }}
                />
                {label}
              </li>
            ))}
          </ul>
          {!showHomes && (
            <div className="mt-2 pt-2 border-t border-slate-700/50 text-[10px] text-slate-400 max-w-[10rem] leading-snug">
              {showResidents ? 'Zoom in for homes and footpaths.' : 'Zoom in to meet the residents.'}
            </div>
          )}
        </div>
      )}

      {/* Civilian dossier — identity, live status and activity history */}
      {selectedAgent && (
        <div className="absolute top-6 right-6 w-80 bg-slate-900/85 backdrop-blur-md rounded-2xl text-white border border-slate-700/50 shadow-2xl z-[1000] overflow-hidden animate-in fade-in slide-in-from-right-4">
          <div className="px-5 pt-4 pb-3 border-b border-slate-700/50">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-base font-bold leading-tight">{selectedAgent.name}</div>
                <div className="text-[11px] text-slate-400">
                  {[selectedAgent.role, selectedAgent.occupation, selectedAgent.age]
                    .filter(Boolean)
                    .join(' · ')}
                </div>
                {engineMode && (
                  <div className="text-[9px] text-slate-500 mt-0.5">
                    Name is generated · everything else is simulated
                  </div>
                )}
              </div>
              <button
                onClick={() => { setSelectedAgentId(null); setPovMode(false); }}
                className="text-slate-400 hover:text-white text-lg leading-none px-1"
                aria-label="Close civilian dossier"
              >
                ×
              </button>
            </div>
          </div>

          {travellingAgent ? (
            <div className="px-5 py-3 grid grid-cols-2 gap-3 text-[11px] border-b border-slate-700/50">
              <div>
                <div className="text-slate-500 uppercase tracking-wider text-[9px]">Speed</div>
                <div className="font-semibold text-cyan-400">{(selectedAgent.currentKmh || 0).toFixed(1)} km/h</div>
              </div>
              <div>
                <div className="text-slate-500 uppercase tracking-wider text-[9px]">Journey</div>
                <div className="font-semibold">{Math.round((selectedAgent.progress || 0) * 100)}% · {selectedAgent.trips} trips</div>
              </div>
              <div className="col-span-2">
                <div className="text-slate-500 uppercase tracking-wider text-[9px]">Heading for</div>
                <div className="font-semibold">{selectedAgent.destination}</div>
              </div>
            </div>
          ) : (
            <div className="px-5 py-3 grid grid-cols-2 gap-3 text-[11px] border-b border-slate-700/50">
              <div className="col-span-2">
                <div className="text-slate-500 uppercase tracking-wider text-[9px]">
                  {selectedAgent.atHome ? 'Home' : 'Currently'}
                </div>
                <div className="font-semibold">
                  {selectedAgent.atHome && selectedHome
                    ? `${DWELLING_STYLE[selectedHome.kind]?.label || selectedHome.kind} · ${Math.round(selectedHome.area_sqm)} m² · ${selectedHome.storeys} ${selectedHome.storeys > 1 ? 'storeys' : 'storey'}`
                    : selectedAgent.placeLabel}
                </div>
              </div>
              {selectedAgent.atHome && selectedHome && (
                <div className="col-span-2">
                  <div className="text-slate-500 uppercase tracking-wider text-[9px]">Rooms</div>
                  <div className="font-semibold capitalize">{(selectedHome.rooms || []).join(' · ')}</div>
                </div>
              )}
              {/* Trade facts straight from the engine: stock, takings, deliveries. The
                  occupation and age already appear in the header, so skip them here. */}
              {Object.entries(selectedAgent.detail || {})
                .filter(([key]) => key !== 'Occupation' && key !== 'Age')
                .map(([key, value]: any) => (
                  <div key={key}>
                    <div className="text-slate-500 uppercase tracking-wider text-[9px]">{key}</div>
                    <div className="font-semibold capitalize">{value}</div>
                  </div>
                ))}
            </div>
          )}

          <div className="px-5 py-3 border-b border-slate-700/50">
            <div className="text-slate-500 uppercase tracking-wider text-[9px] mb-1">Doing now</div>
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
              </span>
              <span className="text-xs font-medium">
                {selectedAgent.activity}
                {activeRoom && <span className="text-slate-400"> · in the {activeRoom.name}</span>}
              </span>
            </div>
          </div>

          <div className="px-5 py-3 max-h-48 overflow-y-auto">
            <div className="text-slate-500 uppercase tracking-wider text-[9px] mb-2">Activity log</div>
            <ul className="space-y-1.5">
              {(selectedAgent.activityLog || []).map((entry: any, i: number) => (
                <li key={`${entry.time}-${i}`} className="flex gap-2 text-[11px]">
                  <span className="text-slate-500 tabular-nums shrink-0">
                    {new Date(entry.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                  <span className={i === 0 ? "text-slate-100" : "text-slate-400"}>{entry.text}</span>
                </li>
              ))}
              {(!selectedAgent.activityLog || selectedAgent.activityLog.length === 0) && (
                <li className="text-[11px] text-slate-500">No activity recorded yet.</li>
              )}
            </ul>
          </div>

          <div className="px-5 py-3 bg-slate-950/50 flex items-center justify-between">
            <span className="text-[10px] font-bold tracking-widest text-cyan-400">
              {!povMode
                ? "FREE CAMERA"
                : isIndoors
                  ? "INSIDE THE HOME"
                  : travellingAgent
                    ? "RIDING ALONG"
                    : selectedAgent?.place === 'stall' || selectedAgent?.place === 'store'
                      ? "AT THE COUNTER"
                      : "LOOKING ON"}
            </span>
            <button
              onClick={() => setPovMode(p => !p)}
              className="text-[11px] font-semibold bg-cyan-500/20 hover:bg-cyan-500/40 text-cyan-300 px-3 py-1.5 rounded-full transition-colors"
            >
              {povMode ? "EXIT VIEW" : "FOLLOW"}
            </button>
          </div>
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
