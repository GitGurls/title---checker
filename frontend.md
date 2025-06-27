# 🧠 Search-and-Rescue Aircraft Prediction Platform – Frontend Blueprint

> A production-grade, advanced, PWA-ready, geospatial control interface for aircraft disappearance modeling, prediction, and SAR coordination.

---

## 🚀 Core Principles

- 🔥 Real-time, reactive simulation
- 🌐 Web-based + Offline-first (PWA)
- 🗺️ 3D/2D geospatial visualization
- 🧩 Modular, extensible architecture
- 📡 Mission-critical UX
- 🔐 Multi-user secure & role-based optionality

---

## 🧱 Tech Stack

| Layer               | Tech                          | Purpose |
|---------------------|-------------------------------|---------|
| Core Framework      | **React 18 + Vite**            | SPA with fast build |
| Map Engine          | **CesiumJS + Deck.gl**         | 3D terrain + overlays |
| UI Framework        | **TailwindCSS + Headless UI**  | Clean, customizable |
| Charts / Stats      | **Recharts + D3.js**           | Metrics & telemetry visuals |
| State Management    | **Zustand / Redux Toolkit**    | Global control + predictability |
| API Layer           | **React Query / SWR**          | Caching + async data |
| PWA & Offline       | **Workbox + Service Worker**   | Resilient in field |
| Offline DB          | **Dexie.js (IndexedDB)**       | Store scenarios, maps |
| Auth (Optional)     | **Clerk / Firebase / Auth0**   | Multi-user SAR ops |
| Dev Tools           | **Storybook + Vitest**         | Testing, isolation, documentation |

---

## 🔭 UI Layout Overview



| 🧭 Scenario Panel	| 🌍 Live Map View |
|---------------------|-------------------------------|
| [Telemetry Input]	| [3D Globe / 2D Map] |
| [Weather Overview] | [Heatmap Zones] |
| [Asset Control] |	[Search Routes & Layers] |
| [Simulation Controls] |	[Playback, Zoom, Track Trails] |


## 📄 Pages / Modules to Build

### 1. `TelemetryInputPage`
- Manual + live telemetry input (OpenSky API)
- Aircraft metadata + weather snapshot
- Timeline with editable telemetry logs

### 2. `MapRendererPage`
- 3D CesiumJS map with overlays
- Heatmap rendering (Deck.gl)
- Interactive tools: zoom, annotate, compare

### 3. `SimulationConfigPage`
- Drift model tuning (wind, fuel, descent)
- Bayesian toggle
- Run/Reset simulation, slider control

### 4. `SearchAssetsPage`
- Add/edit/search units (drone, boat, heli)
- Route generation and preview
- ETA, cone coverage, fuel usage

### 5. `ScenarioManagerPage`
- Save/load previous simulations
- Compare two scenarios visually
- Clone, rename, share as JSON or link

### 6. `MissionReportPage`
- Export PDF reports with map snapshots
- GeoJSON zone download
- Summary table of mission parameters

### 7. `CollaborationPage` *(optional/advanced)*
- Comment on map zones
- Live session share (WebSocket/Firebase)
- Team activity log

### 8. `OfflineManagerPage` *(if PWA enabled)*
- Show cached data status
- IndexedDB backup viewer
- Restore simulation session when offline

### 9. `SettingsPage`
- Configure thresholds
- API keys (admin only)
- PWA update checker

### 10. `NavigationSidebar`
- Tab: Dashboard / Map / Assets / Reports / Settings

---



## ✅ Team Build Checklist

| Task                             | Status |
|----------------------------------|--------|
| Base React + Tailwind Setup      | ☐      |
| Telemetry Form → State Store     | ☐      |
| Map + Heatmap + Wind Overlays    | ☐      |
| Simulation Config Panel          | ☐      |
| Asset Routing Engine             | ☐      |
| Report Export to PDF & GeoJSON   | ☐      |
| PWA Offline + IndexedDB Setup    | ☐      |
| Scenario Save/Load Page          | ☐      |

---

## 📌 Optional Enhancements

- Drone camera stream overlay
- AI mission copilot (text-to-config)
- Voice commands for map actions
- Authentication + mission sharing

---

## 🧭 Closing Thoughts

Build a mission-grade PWA frontend that mirrors real-world aviation SAR systems — clean, geospatial, resilient, and user-controlled. Every page is modular, every feature battle-tested.

---
