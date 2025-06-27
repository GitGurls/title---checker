# 🛩️ SAR Aircraft Disappearance Prediction System

> A full-stack AI-powered platform for predicting crash zones of lost aircraft using real-time telemetry, Bayesian modeling, and wind-drift simulations. Built for use in mission-critical SAR (Search and Rescue) operations.

---

## 📌 Features

- 🧠 **Probabilistic Simulation Engine** (Monte Carlo, Drift, Bayesian)
- 🌍 **3D/2D Heatmap Visualization** with CesiumJS / Deck.gl
- 🛰️ **Telemetry & Wind Data Ingestion** (OpenSky, NOAA APIs)
- 📊 **Simulation Config Panel** with real-time parameter tuning
- 🛠️ **Search Asset Routing & Optimization**
- 🧾 **Mission Report Export** (PDF / GeoJSON / PNG)
- 🔁 **Offline Mode + PWA Support** for field operations
- 💾 **Scenario Save/Replay** using IndexedDB

---

## 🧱 Tech Stack

### ⚙️ Backend
- `FastAPI`, `Uvicorn` – Async API framework
- `NumPy`, `PyMC3`, `SciPy` – Monte Carlo + Bayesian models
- `GeoPandas`, `Shapely` – Geospatial zone computation
- `Redis` – Real-time caching
- `Celery` (optional) – Task queues for long simulations

### 💻 Frontend
- `React 18` + `Vite` – SPA Framework
- `CesiumJS` / `Deck.gl` – 3D maps & overlays
- `TailwindCSS` – UI styling
- `React Query`, `Zustand` – State & async management
- `Recharts`, `D3.js` – Charts and timelines
- `Workbox`, `Dexie.js` – PWA + offline scenario support

---

## 📦 Folder Structure
```yaml
/frontend
/components
/pages
/hooks
/services
/backend
/api
/models
/simulations
/docs
README.md
TECH_STACK.md
MATH_MODELLING.md
```
---

## 🚀 Getting Started

### 📥 Clone & Install

```bash
git clone https://github.com/your-username/sar-prediction-platform.git
cd sar-prediction-platform
```
⚙️ Backend Setup
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```
🌐 Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
📊 Sample API Request
```bash
POST /api/simulate

{
  "lat": 25.4,
  "lon": 87.6,
  "altitude": 35000,
  "speed": 460,
  "heading": 98,
  "fuel": 4000,
  "wind": { "speed": 15, "direction": 110 },
  "time_since_contact": 900
}
```
### 📁 Key Documentation
- TECH_STACK.md – Full software stack + infrastructure

- BACKEND_ARCHITECTURE.md – Modeling & API logic

- MATH_MODELLING.md – Equations & probability models

- FRONTEND_BLUEPRINT.md – UI structure and visual modules

### 📜 License
MIT License © 2025 

### 🧠 Credits
- Inspired by real-world SAR cases: MH370, Air France 447

 Special thanks to contributors and data providers:

- OpenSky Network

- NOAA Weather APIs

- NASA SRTM Elevation Data

### 🙌 Contribute
Pull requests welcome. For major changes, open an issue first to discuss what you would like to change.

This project was built for practice of [Smart India Hackathon 2025] for the domain: Disaster Management, Aviation Intelligence, and Defense Systems.


