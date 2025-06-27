
# 🛩️ SAR Aircraft Disappearance Prediction System – Tech Stack & Justification

> Final consolidated technology architecture and reasoning based on research, modeling reports, and real-world case studies (e.g., MH370).

---

## 🎯 Project Objective

Build a robust, real-time, offline-ready **Search-and-Rescue Prediction Platform** that:
- Predicts crash zones using probabilistic models
- Integrates aircraft telemetry + environmental data
- Visualizes high-risk areas in 2D/3D heatmaps
- Optimizes asset deployment in SAR missions

---

## 📁 Source Documents Consolidated

- `probabilistic modeling method.pdf` ✅  
- `Modeling_Research_Summary.pdf` ✅  
- `Real-World Aircraft Disappearance (MH370).pdf` ✅  
- `SAR_Tech_Stack_Justification.pdf` ✅  
- `Field Notes / PDFs / Scans` ✅

---

## 🧠 Core Models & Algorithms

| Model Type               | Method                     | Use Case |
|--------------------------|----------------------------|----------|
| Monte Carlo Simulation   | Random trajectory sampling | Estimate dispersion of possible crash paths |
| Drift Modeling           | Vector-based wind/descent  | Simulate gradual deviation |
| Bayesian Updating        | Posterior belief inference | Integrate new evidence (radar ping, debris) |

---

## 🛰️ Telemetry Variables Modeled

Derived from MH370 case study and aviation telemetry standards:

| Parameter         | Unit      | Relevance                           |
|------------------|-----------|-------------------------------------|
| GPS Coordinates   | Degrees   | Last known position (LKP)          |
| Altitude          | Feet      | Determines phase of flight         |
| Heading           | Degrees   | Trajectory continuation             |
| Speed             | Knots     | Affects range + energy              |
| Fuel Level        | Liters    | Limits max drift range              |
| Wind Data         | Direction + Speed | Drives drift deviation       |
| Engine Data       | RPM, status | Identifies anomalies              |
| Radar Pings       | Time-stamped arcs | Narrows likely zone         |

---

## 🧱 Finalized Tech Stack (Layer-wise)

### 1. 🧮 Modeling Layer

| Tool / Library     | Purpose                            |
|--------------------|------------------------------------|
| **NumPy + SciPy**   | Statistical distributions, math ops |
| **PyMC3 / Pyro**    | Bayesian inference modeling        |
| **Shapely**         | Geometric zones & buffers          |
| **GeoPandas**       | Spatial operations with GIS layers |
| **Matplotlib / Seaborn** | Visualize probabilistic outcomes |

---

### 2. 📦 Backend API Layer

| Tool         | Purpose                            |
|--------------|------------------------------------|
| **FastAPI**   | Async backend for serving models  |
| **Uvicorn**   | ASGI server                       |
| **Redis**     | Telemetry cache / live stream     |
| **Pydantic**  | Data validation & schema support  |

---

### 3. 🌍 Frontend Visualization Layer

| Tool           | Use |
|----------------|-----|
| **React 18 + Vite** | Core SPA framework |
| **CesiumJS**    | 3D globe, terrain, satellite map |
| **Deck.gl**     | GPU-accelerated overlays (heatmaps, cones) |
| **TailwindCSS** | Responsive, clean design |
| **Recharts + D3** | Graphs, telemetry timelines |

---

### 4. 🧭 Simulation Features (Frontend)

- Map-based scenario builder
- Sliders for glide rate, wind uncertainty
- Simulation playback (time-scrubbing)
- Save/load previous scenarios (IndexedDB)
- Export mission zones as GeoJSON / PDF / PNG

---

### 5. 🗂 Data Integration

| Source/API           | Data Type                       |
|----------------------|----------------------------------|
| OpenSky API          | Real-time aircraft telemetry     |
| NOAA / OpenWeather   | Wind, pressure, atmospheric data |
| DEM / SRTM Elevation | Terrain & topography             |
| Manual Input         | For historic or test scenarios   |

---

### 6. 📦 Storage & Offline Stack

| Tool         | Purpose                            |
|--------------|------------------------------------|
| **IndexedDB (Dexie.js)** | Offline scenario + map data storage |
| **MinIO**     | Object storage for map tiles and snapshots |
| **Workbox**   | PWA cache management               |

---

### 7. 🛠 DevOps / Deployment

| Tool              | Role                             |
|-------------------|----------------------------------|
| Docker            | Cross-platform deployment        |
| GitHub Actions    | CI/CD for testing + builds       |
| Vercel / Netlify  | Frontend deployment (PWA ready)  |
| Fly.io / Render   | Fullstack hosting options        |

---

## ✅ Key Features Delivered

- 🔧 Monte Carlo simulator with spatial path dispersion
- 🧠 Bayesian update engine using radar/debris data
- 📡 Wind-aware drift modeling and zone evolution
- 🌐 Interactive map with heatmaps, cone coverage, terrain
- 📂 Exportable reports for SAR teams
- 🧳 Field-ready offline mode with session caching

---

## 🔍 Improvement Areas & Suggestions

| Area            | Recommendation |
|-----------------|----------------|
| Real-time data stream | Use Redis Streams + WebSocket client |
| Optimized map rendering | Upgrade to Deck.gl for smooth animation |
| Voice interaction (optional) | Voice trigger for "Run simulation" |
| UI polish | Figma-based layout + dark/light toggle |
| Field deployment | Consider Android WebView wrapper for teams |

---

## 📌 Final Verdict

✅ The stack is robust, future-proof, and practically aligned with both aviation SAR operations and modern web technology.

With modular modeling, fast geospatial rendering, offline capability, and extensible API design — this system meets high standards of reliability and field adaptability.

---
