# System Architecture — Delhi Real-Time Bus Journey Planner

This document provides a comprehensive technical overview and architecture diagram of the Delhi Real-Time Bus Journey Planner. The architecture is derived directly from the active codebase.

---

## 1. End-to-End System Architecture Diagram

```mermaid
flowchart TD
    subgraph ClientLayer["Frontend Client Layer (React 18 + Vite + Leaflet)"]
        UI["PlannerPage UI<br/>(Origin / Destination Inputs, Results Cards)"]
        Map["Leaflet DelhiMap<br/>(Smooth Pan/Zoom, Viewport Tracking)"]
        FocusCtrl["MapPickupFocusController<br/>(One-Click 'See Buses Coming to Pick You Up')"]
        Renderer["Live Vehicle Marker Renderer<br/>- Genuine GPS Icon (Emerald ⭐)<br/>- Estimated Position Icon (Amber ⚡)"]
    end

    subgraph APILayer["FastAPI Application Server (Port 8000)"]
        Router["API Gateway / Router (/api/v1)"]
        HealthEndpoint["/health & /timetable/status<br/>(DEGRADE Governance Status)"]
        PlanEndpoint["/plan Endpoint<br/>(RAPTOR Multi-Modal Journey Planning)"]
        LiveEndpoint["/live/vehicles & /live/suitable-vehicles<br/>(Candidate Filtering & Telemetry)"]
    end

    subgraph CoreEngine["Core Processing & Routing Engines"]
        RAPTOR["RAPTOR Routing Engine<br/>(Round-Based Pareto Optimization)"]
        Predictor["Prediction Tier Classifier<br/>(Level 1 ML to Level 4 Timetable)"]
        Collector["GTFS-RT LiveFeedCollector<br/>(30s Ingestion, Staleness Auditing)"]
        Matcher["JourneyBusMatcher<br/>(Direction, Sequence, & Corridor Proximity)"]
        DeadReckon["GPS-Anchored Dead Reckoning Engine<br/>(15s Step-Ahead Polyline Projection)"]
    end

    subgraph DataStorage["Data Persistence & Caching Layers"]
        DLM1_DB[("DLM1 Static GTFS SQLite DB<br/>(/tmp/delhi_dlm1.db - 346MB)<br/>2,574 Routes, 59k Trips, 40k Stops")]
        DuckDB_Storage[("Historical Stop-Crossing Parquet + DuckDB<br/>(data/processed/*.parquet)<br/>Empirical Segment Speed Distributions")]
        LiveCache[("In-Memory Live Telemetry Cache<br/>(Active, Stale, & Dead-Reckoned States)")]
        ShapeCache[("GTFS Shape & Polyline Cumulative Distances<br/>(In-Memory Spatial Index)")]
    end

    subgraph UpstreamSources["Upstream External Data Feeds"]
        DTS["Delhi Transport Stack (Open Transit Data)<br/>GTFS-RT VehiclePositions.pb (HTTP Protobuf)"]
        StaticArchive["Delhi Government Static GTFS Archive<br/>(delhi_buses_static_gtfs_v1.zip)"]
    end

    %% Data Flow Connections
    StaticArchive -->|Build Staged SQLite| DLM1_DB
    DTS -->|30s Poll Ingestion| Collector
    Collector -->|Parsed Positions| LiveCache

    UI -->|1. Plan Journey Request| PlanEndpoint
    PlanEndpoint --> RAPTOR
    RAPTOR -->|Stop Sequences & Times| DLM1_DB
    RAPTOR -->|Historical Speed Profiles| DuckDB_Storage
    RAPTOR --> Predictor
    Predictor -->|Journeys with Confidence| PlanEndpoint
    PlanEndpoint -->|Journey Options| UI

    UI -->|2. Suitable Buses Query| LiveEndpoint
    LiveEndpoint --> Matcher
    Matcher -->|Query Active Fleet| LiveCache
    Matcher -->|Corridor Stop Sequences| DLM1_DB
    Matcher -->|Project Point onto Shape| ShapeCache
    Matcher --> DeadReckon

    DeadReckon -->|Genuine GPS Anchor| Renderer
    DeadReckon -->|Estimated Coordinates| Renderer
    LiveEndpoint -->|SuitableVehiclesResponse| Map

    FocusCtrl -->|Frame Boarding + Approaching Buses| Map
```

---

## 2. Component Breakdown

### 2.1 Frontend Client Layer
- **Framework**: React 18 with TypeScript, Vite bundler, and Tailwind CSS.
- **Mapping Engine**: Leaflet with `react-leaflet`, rendering true Delhi road geometry from static GTFS `shapes` rather than straight-line Euclidean interpolation.
- **Visual Distinction**:
  - **Genuine GPS Positions**: Rendered with solid emerald badges, timestamped from the actual hardware ping.
  - **Estimated Positions (Dead Reckoned)**: Rendered with amber lightning badges (`⚡`), displaying accumulated drift and dead-reckoning elapsed seconds.
- **Dynamic Camera Control**:
  - `MapPickupFocusController`: Automatically bounds the viewport to include both the user's boarding stop and all approaching pickup buses along the corridor.
  - `Center on Journey`: Allows the user to toggle back to the full trip corridor.

### 2.2 FastAPI Backend Layer
- **Endpoints**:
  - `POST /api/v1/plan`: Computes multi-modal transit itineraries using the RAPTOR algorithm with Pareto criteria (arrival time, transfers, walking distance).
  - `GET /api/v1/live/suitable-vehicles`: Evaluates candidate vehicles for a specific journey leg, applying strict directional and stop sequence verification.
  - `GET /api/v1/live/vehicles`: Viewport-aware live bus discovery across the entire Delhi fleet.
  - `GET /api/v1/live/status`: Upstream feed health, active vehicle counts, and timestamp synchronization.
  - `GET /api/v1/health`: Overall system health and governance disclosures.

### 2.3 Real-Time Matching & Dead Reckoning Pipeline
1. **Corridor Proximity Gate**: Candidate vehicles must be within 1,500m of the GTFS route shape.
2. **Direction Alignment Gate**: Vehicle bearing must match corridor heading within 120° (or local segment heading).
3. **Stop Sequence Progress Gate**: The vehicle's current projection must be upstream of the boarding stop (`board_seq < alight_seq` and `nearest_seq <= board_seq`). Buses that have already departed the boarding stop are rejected as `ALREADY_PASSED_BOARDING_STOP`.
4. **GPS-Anchored Dead Reckoning**:
   - Calculates movement along the GTFS shape polyline every 15 seconds based on speed.
   - Genuine GPS fixes act as recalibration anchors.
   - Anomaly detection (`LARGE_PREDICTION_ERROR > 250m`, `AMBIGUOUS_SHAPE_PROJECTION`, `UNEXPECTED_BACKWARD_PROGRESS`) automatically freezes unverified forward extrapolation and falls back to the genuine GPS anchor.

---

## 3. Data Persistence & Governance

| Layer | Storage Engine | Path / Format | Description |
| :--- | :--- | :--- | :--- |
| **Static GTFS** | SQLite 3 | `/tmp/delhi_dlm1.db` | Complete Delhi bus network (2,574 routes, 40,000+ stops, 59,000+ trips). |
| **Historical Speeds** | Apache Parquet + DuckDB | `data/processed/*.parquet` | Empirical stop-crossing segment durations from Delhi pilot GPS data. |
| **Real-Time Feed** | Protocol Buffers (GTFS-RT) | In-Memory Collector | Ingested via Delhi Transport Stack (`VehiclePositions.pb`). |
| **Operational Governance** | JSON Envelopes | System-Wide | Governing status strictly retained as `DEGRADE` due to expired calendar dates in static GTFS. |
