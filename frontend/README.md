# Pravaah — Urban Policy & Climate Simulation Dashboard (SUB-06)

This is the front-end dashboard application for the **Urban Intelligence Platform (UIP)** (working title: **Pravaah**).

It surfaces the complex underlying commuter agency and climate stress simulations as a dense, legible, and highly premium analytical dashboard designed to help researchers, policy makers, and external reviewers reason about a city under stress.

## 🌟 Visual Core & Design System

The visual language follows the **Bloomberg Terminal + NYT Interactive** design canon:
- **HSL-based Theme**: Deep cosmic space backgrounds (`hsl(222, 47%, 4%)`) with rich glassmorphism.
- **Color Discipline**: Very high contrast color mappings used sparingly to convey status (Neon Metro Blue, Indigo Bus Accents, Amber Congestion, Crimson Flood warnings).
- **Legible Typography**: Using `Plus Jakarta Sans` for labels/UI grids and `JetBrains Mono` for clocks, metrics, and telemetry readings.
- **60 FPS Graphics Engine**: Powered by an HTML5 canvas overlay system displaying thousands of simulated agents as animating micro-particles traveling along a concentric-radial road and rail network.

## 🛠️ Features Implemented

1. **Simulated Sandbox & Live Modes**:
   - **Live Connected**: Instantly connects to the FastAPI uvicorn backend via WebSockets (`ws://localhost:8000/ws/scenarios/{id}`) to stream real tick frames, congestion states, weather, and incidents.
   - **Demo Sandbox (Fallback)**: If the backend is offline, the UI automatically transitions to a gorgeous, self-contained mock tick loop that demonstrates monsoon rain progression, road speed decay, and passenger redirection in real time!
2. **Policy Controls Sidebar**:
   - Two-way bound range sliders for **Extra Bus Capacity**, **Metro Frequency Boost**, and **Congestion Fees**.
   - Segmented toggle badges for **Work From Home (WFH) Mandates**.
   - Automated message logs parsing active incidents, rainfall announcements, and policy applications.
3. **Telemetric Analytics**:
   - Time-series bar charts tracking Average Delay, Transit Mode Share, Gridlock Index, and Metro Station Overcapacity.
   - Automated delta comparison metrics (comparing previous ticks against current).
4. **Before/After Split Screen Comparison**:
   - A dedicated **Compare View** togglable with one click, morphing the grid panels into a side-by-side comparative analysis of a normal baseline day vs. the active stressed scenario run.

## 📁 Directory Structure

```
frontend/
├── index.html                  # Semantic HTML & layout scaffolding
├── package.json                # Project node packages
├── tsconfig.json               # Strict TypeScript compilation rules
├── src/
│   ├── main.ts                 # App entrypoint and bootstrapper
│   ├── style.css               # Imports compiled sheets
│   ├── styles/                 # Subsystem modules styles
│   │   ├── variables.css       # HSL palette, spacing scale, transitions
│   │   ├── reset.css           # Global resets and custom scrollbars
│   │   ├── dashboard.css       # Screen grids and card classes
│   │   ├── map.css             # Floating map overlays and legends
│   │   ├── charts.css          # Analytics, bar containers, split view
│   │   └── policy.css          # Slider ranges and toggle buttons
│   ├── map/
│   │   └── map.ts              // HTML5 Canvas spatial particle renderer
│   ├── charts/
│   │   └── charts.ts           // Lightweight sparkline and telemetry update manager
│   ├── policy/
│   │   └── policy.ts           // Interactive controls and slider models
│   └── components/
│       └── dashboard.ts        // Coordinator routing state & socket listeners
```

## 🚀 Quick Start & Development

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start local dev server:
   ```bash
   npm run dev
   ```

3. Build production optimization:
   ```bash
   npm run build
   ```
