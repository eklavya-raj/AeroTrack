<p align="center">
  <h1 align="center">🛫 AeroTrack</h1>
  <p align="center">
    <strong>Real-Time Global Flight Telemetry & Air Traffic Control Dashboard</strong>
  </p>
  <p align="center">
    A full-stack, enterprise-grade air traffic control simulator that streams live flight coordinates from across the globe, processes thousands of telemetry updates in real time, and renders them on an interactive operations dashboard.
  </p>
  <p align="center">
    <a href="#-quick-start"><img src="https://img.shields.io/badge/Quick_Start-blue?style=for-the-badge" alt="Quick Start" /></a>
    <a href="#-architecture"><img src="https://img.shields.io/badge/Architecture-purple?style=for-the-badge" alt="Architecture" /></a>
    <a href="#-tech-stack"><img src="https://img.shields.io/badge/Tech_Stack-green?style=for-the-badge" alt="Tech Stack" /></a>
  </p>
</p>

---

## 🎯 What Is This?

AeroTrack isn't a toy dashboard. It's a **live infrastructure tracker** engineered to demonstrate mastery over real-time data pipelines, high-speed spatial querying, and fully decoupled backend architectures.

The system polls actual aircraft transponder data — ICAO 24-bit identifiers, callsigns, velocities, and exact coordinates — from the [OpenSky Network](https://opensky-network.org/), processes it through a Kafka-backed event pipeline, caches it in a Redis geo-spatial index, and pushes live updates to a React operations panel over WebSockets.

> **Think of it as Mission Control, but for every plane in the sky — built from scratch.**

---

## ✨ Core System Features

### 1. 📡 High-Frequency Live Flight Streams

- Actively tracks **thousands of aircraft** currently airborne across the globe
- Polls real transponder data: ICAO identifiers, callsigns, velocities, altitude, and exact GPS coordinates
- Implements a **fault-tolerant ingestion pipeline** that splits bulk API payloads into individual, granular flight event objects instantly

### 2. 🎯 Proximity-Based Spatial Queries (Geofencing)

- Geographic radius search — *"Show me all active planes within 150km of London Heathrow"*
- Powered by **Redis Geo-indexing** for millisecond-level radial distance calculations
- Completely bypasses heavy geographic queries on traditional database storage

### 3. 🚨 Emergency & Altitude Anomaly Alerts

- Continuous monitoring of flight vectors for sudden safety parameter changes
- Detects **extreme descent/climb rates** via `vertical_rate` telemetry
- Fires live emergency events when aircraft transmit **emergency squawk codes** (e.g., `7700`)
- Alerts propagate instantly from Kafka → Django Channels → React UI

### 4. 📊 Historical Landing Records & Metrics Analytics

- Tracks flight state transitions to log long-term data without overloading system storage
- When a plane's status transitions to `on_ground: true`, the system commits a **permanent archival record**:
  - Flight origin
  - Final landing timestamp
  - Maximum recorded speed
- Enables historical trend analysis and flight pattern metrics

---

## 🖥️ The Frontend — Operations Panel

The React frontend is designed as a **high-density, terminal-style operations panel** — not a consumer app, but a command center.

| Component | Description |
|-----------|-------------|
| **🗺️ Global Airspace Canvas** | Dark-themed interactive map (React-Map-GL / Leaflet / Pigeon Maps) plotting live aircraft as vector icons. Icons rotate dynamically based on heading/track. |
| **📋 Live Airspace Inspector** | Real-time sidebar grid. Click any aircraft to pull up a metadata block — altitude bars, velocity trends, country of origin. |
| **🔴 Emergency Alert Hub** | High-contrast toast notification panel. Altitude/squawk anomalies trigger critical alerts with sharp visual pulses. |
| **⭕ Geofence Radius Controller** | Floating map control — type coordinates or select major airports from a dropdown, adjust the query radius with a slider. |

---

## 🏗️ Architecture

```
┌──────────────────┐    Polling (Every 10s)    ┌──────────────────────────┐
│  OpenSky Live    │ ────────────────────────▶  │  Ingestion Service       │
│  Public API      │                            │  (Docker Container)      │
└──────────────────┘                            └──────────┬───────────────┘
                                                           │
                                                           │ Streams individual
                                                           │ flight event objects
                                                           ▼
┌──────────────────┐    Consumes Positions      ┌──────────────────────────┐
│  Redis Cache     │ ◀──────────────────────── │  KAFKA CLUSTER           │
│  (Geo-Spatial)   │                            │  (flight-telemetry)      │
└────────┬─────────┘                            └──────────┬───────────────┘
         │                                                 │
         │ Reads live                                      │ Consumes landing
         │ coordinates                                     │ state changes
         ▼                                                 ▼
┌──────────────────┐    REST API + WebSocket    ┌──────────────────────────┐
│  React UI        │ ◀──────────────────────── │  Django Backend          │
│  (Dashboard/Map) │                            │  & PostgreSQL Database   │
└──────────────────┘                            └──────────────────────────┘
         ▲                                                 │
         │        Persistent WebSocket Connection          │
         │           (Django Channels)                     │
         └───────────── Pushes anomaly alerts ─────────────┘
```

### Data Flow

1. **Ingest** — A containerized polling service hits the OpenSky API every 10 seconds
2. **Stream** — Raw telemetry is split into individual events and published to Kafka (`flight-telemetry` topic)
3. **Cache** — A Kafka consumer writes active positions into a Redis Geo-index with TTL expiry
4. **Detect** — A separate consumer monitors for anomalies (extreme vertical rates, emergency squawks)
5. **Store** — Landing state transitions are committed to PostgreSQL as permanent archival records
6. **Serve** — Django exposes a REST API for filtered flight data + geofence queries
7. **Push** — Django Channels pushes real-time alerts to the React frontend over WebSockets
8. **Render** — React plots everything on an interactive dark-themed map with live updates

---

## 🛠️ Tech Stack

| Layer | Technology | Role |
|-------|-----------|------|
| **Frontend** | React 19, Vite 8, React Router 7, React Query | Operations dashboard & interactive map |
| **Backend API** | Django 6.0, Django REST Framework | REST API, user management, historical metrics |
| **Real-Time** | Django Channels | WebSocket push for live alerts |
| **Message Broker** | Apache Kafka (Confluent) | Central nervous system — buffers incoming telemetry stream, prevents bottlenecks |
| **Spatial Cache** | Redis 7 (Geo-index) | High-speed geofence queries in milliseconds |
| **Database** | PostgreSQL 16 | Permanent storage for landing records, user accounts, historical metrics |
| **Task Queue** | Celery (Redis broker) | Async background processing |
| **Containers** | Docker, Docker Compose | Fully modularized — each service runs in isolated containers |
| **CI/CD** | GitHub Actions | Automated linting, tests, and Docker builds on every push |
| **Data Source** | OpenSky Network API | Live global aircraft transponder data |

---

## 📁 Project Structure

```
AeroTrack/
│
├── backend/                          # Django REST API + WebSocket Server
│   ├── config/                       # Django project configuration
│   │   ├── settings.py               # PostgreSQL, Redis, Kafka, Celery config
│   │   ├── celery.py                 # Celery app with autodiscover
│   │   ├── urls.py                   # API routing
│   │   ├── asgi.py                   # ASGI for Django Channels
│   │   └── wsgi.py                   # WSGI for Gunicorn
│   ├── core/                         # Core app — flights, telemetry, geofencing
│   │   ├── kafka_producer.py         # Confluent Kafka producer wrapper
│   │   ├── kafka_consumer.py         # Abstract Kafka consumer base class
│   │   ├── tasks.py                  # Celery async tasks
│   │   ├── models.py                 # Flight & telemetry models
│   │   ├── serializers.py            # DRF serializers
│   │   ├── views.py                  # API views
│   │   └── urls.py                   # Core URL routing
│   ├── users/                        # User authentication & profiles
│   ├── requirements.txt              # Python dependencies
│   ├── Dockerfile                    # Multi-stage production build
│   └── .env.example                  # Backend environment template
│
├── frontend/                         # React Operations Dashboard
│   ├── src/
│   │   ├── api/                      # Axios client with interceptors
│   │   ├── components/               # Reusable UI components
│   │   │   └── Layout.jsx            # App shell with navigation
│   │   ├── pages/                    # Page components
│   │   │   ├── Home.jsx              # Landing / overview
│   │   │   ├── Dashboard.jsx         # Main operations panel
│   │   │   └── NotFound.jsx          # 404 page
│   │   ├── hooks/                    # Custom React hooks (useApi)
│   │   ├── router.jsx                # Client-side routing
│   │   └── main.jsx                  # App entry point
│   ├── vite.config.js                # Vite + React plugin + API proxy
│   ├── nginx.conf                    # Production SPA + API proxy
│   ├── Dockerfile                    # Multi-stage build → Nginx
│   └── .env.example                  # Frontend environment template
│
├── .github/workflows/                # CI/CD Pipelines
│   ├── ci.yml                        # Lint + Test + Docker build verification
│   └── deploy.yml                    # Build & push to GitHub Container Registry
│
├── docker-compose.yml                # Production stack (all 6 services)
├── docker-compose.dev.yml            # Development overrides (hot-reload)
├── Makefile                          # 20+ convenience commands
├── .env.example                      # Root environment template
├── .gitignore                        # Python, Node, Docker, IDE exclusions
└── README.md                         # ← You are here
```

---

## 🐳 Docker Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `db` | `postgres:16-alpine` | 5432 | Permanent flight records & user data |
| `redis` | `redis:7-alpine` | 6379 | Geo-spatial cache & Celery broker |
| `kafka` | `confluentinc/cp-kafka:7.9.0` | 9092 | Event streaming (KRaft mode, no Zookeeper) |
| `backend` | Custom (Python 3.13) | 8000 | Django API + Django Channels |
| `celery_worker` | Same as backend | — | Async task processing |
| `frontend` | Custom (Node 22 + Nginx) | 5173 / 80 | React operations dashboard |

---

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- Python 3.13+ *(for local development)*
- Node.js 22+ & pnpm *(for local development)*

### Launch with Docker

```bash
# 1. Clone the repository
git clone https://github.com/your-username/AeroTrack.git
cd AeroTrack

# 2. Set up environment
cp .env.example .env

# 3. Build and launch all services
make dev-build

# 4. Run database migrations
make migrate

# 5. Create an admin account
make createsuperuser
```

### Access Points

| Service | URL |
|---------|-----|
| 🖥️ Dashboard | [http://localhost:5173](http://localhost:5173) |
| 🔌 Backend API | [http://localhost:8000/api/](http://localhost:8000/api/) |
| ⚙️ Django Admin | [http://localhost:8000/admin/](http://localhost:8000/admin/) |
| ❤️ Health Check | [http://localhost:8000/api/health/](http://localhost:8000/api/health/) |

### Local Development (without Docker)

```bash
# Backend
cd backend
source venv/bin/activate
python manage.py runserver

# Frontend (separate terminal)
cd frontend
pnpm dev
```

---

## 🔧 Useful Commands

```bash
make help              # List all available commands
make dev               # Start development stack
make dev-build         # Build + start development stack
make down              # Stop all services
make down-v            # Stop all services + delete volumes
make logs              # Tail all service logs
make logs-backend      # Tail backend logs only
make migrate           # Run Django migrations
make createsuperuser   # Create admin user
make test              # Run all tests
make lint              # Run all linters
make backend-shell     # Shell into backend container
make db-shell          # Open psql
make redis-cli         # Open Redis CLI
```

---

## 🔄 CI/CD

| Workflow | Trigger | What It Does |
|----------|---------|-------------|
| **ci.yml** | Push to `main`/`develop`, PRs to `main` | Python tests + flake8, ESLint + Vite build, Docker image build verification |
| **deploy.yml** | Push to `main` | Builds & pushes Docker images to GitHub Container Registry (`ghcr.io`) |

---

## 📝 License

MIT

---

<p align="center">
  <sub>Built with ☕ and a passion for real-time systems.</sub>
</p>
