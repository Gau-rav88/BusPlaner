# Milestone 7: Frontend Architecture Specification

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner (Problem 1)  
**Governing Specification:** PRD v3.0  
**Authorization:** Milestone 7 Approved  
**Operational Status:** **DEGRADE**  
**Technology Stack:** React 18, TypeScript 5.6, Vite 5.4, Tailwind CSS 3.4, React-Leaflet 4.2, OpenStreetMap  

---

## 1. Overview and Core Philosophy

The Milestone 7 web application provides a responsive transit journey planner for Delhi. It strictly consumes the production FastAPI REST backend (`/api/v1`), never duplicating routing or statistical prediction logic on the client.

### Key Architectural Tenets
1. **Separation of Presentation and Computation:** All transit graph traversals (RAPTOR) and statistical travel-time predictions are executed server-side. The frontend is a clean presentation and query-orchestration client.
2. **Mandatory Truthfulness & Constraint Integrity:**
   - The interface never implies that static GTFS schedules prove physical bus operations (`actual_operations_verified: false` is prominent).
   - Expired timetable calendar (`2024-01-01`) is disclosed upfront, requiring explicit user opt-in (`allow_assumed_recurring: true`) for 2026 dates.
   - Observed bus traffic data (North GT Road corridor, Route 1598) is visually and textually distinguished from scheduled timetable running times and static fallbacks.
   - Heuristic confidence scores are labeled as non-probabilistic quality indicators.
   - Experimental Random Forest candidate ML predictions are disabled by default.
3. **Map-Centric User Experience:** Desktop users experience a unified split-screen with controls and results on the left and an interactive Leaflet map on the right. Mobile users experience a stacked, touch-friendly flow.

---

## 2. Component Hierarchy and Layout

```text
App
└── PlannerPage
    ├── Header
    │   ├── Operational Status Badge (DEGRADE)
    │   ├── Backend Health Probe (v1.0.0)
    │   ├── Timetable Freshness Badge (ASSUMED_RECURRING)
    │   └── Live Operations Disclaimer
    │
    ├── AlertBanner (Error / Stale Timetable Notice)
    │
    ├── Main Container (12-Column Responsive Grid)
    │   ├── Left Column (5 Cols Desktop)
    │   │   ├── PlannerForm
    │   │   │   ├── StopSearchInput (Origin - Stop Autocomplete / Coordinate)
    │   │   │   ├── Endpoint Swap Button
    │   │   │   ├── StopSearchInput (Destination - Stop Autocomplete / Coordinate)
    │   │   │   ├── Date & Time Selectors
    │   │   │   ├── Quick Preset Button (North GT Road Corridor)
    │   │   │   ├── Collapsible Routing Controls (Max Walk, Transfers, Criteria)
    │   │   │   ├── Safeguard Switches (Assumed Recurring, Experimental ML)
    │   │   │   └── Search Journeys Button
    │   │   │
    │   │   ├── StopDiscovery (Search Hub / Nearby Terminals)
    │   │   │
    │   │   └── JourneyResults
    │   │       └── JourneyCard (Iterative Pareto Alternatives)
    │   │           ├── Duration & Arrival/Departure Time
    │   │           ├── Proportional Duration Breakdown Bar
    │   │           ├── Prediction Tier & Confidence Badge
    │   │           ├── Stale Timetable Notice
    │   │           └── Expandable Step-by-Step Legs (Transit & Walking)
    │   │
    │   └── Right Column (7 Cols Desktop, Sticky)
    │       └── DelhiMap (React-Leaflet + OpenStreetMap)
    │           ├── Origin & Destination Markers (A / B)
    │           ├── Nearby Bus Stop Pins
    │           ├── Bus Transit Polylines (Solid Teal)
    │           ├── Walking Access/Egress Polylines (Dashed Blue)
    │           └── Floating Legend & Map Click Listener
    │
    └── Footer (PRD v3.0 Governance & DEGRADE Status)
```

---

## 3. Module & Directory Structure

```text
frontend/
├── index.html                   # HTML entry point with Leaflet stylesheet
├── package.json                 # React 18, Vite, Tailwind, Leaflet, Vitest
├── tsconfig.json                # TypeScript compiler configuration (strict mode)
├── vite.config.ts               # Vite configuration with proxy and Vitest setup
├── tailwind.config.js           # Delhi Transit design system color tokens
├── postcss.config.js            # PostCSS Autoprefixer and Tailwind plugin
│
├── src/
│   ├── main.tsx                 # React DOM root mounting
│   ├── App.tsx                  # App shell
│   ├── index.css                # Tailwind directives and Leaflet map overrides
│   │
│   ├── types/
│   │   └── api.ts               # Full TypeScript definitions matching Pydantic schemas
│   │
│   ├── services/
│   │   └── api.ts               # Fetch-based API client with typed error handling
│   │
│   ├── utils/
│   │   └── formatters.ts        # Time, duration, distance, and tier formatting
│   │
│   ├── components/
│   │   ├── Header.tsx           # Branding, operational status, and health badges
│   │   ├── AlertBanner.tsx      # Warning, error, and actionable retry alerts
│   │   ├── StopSearchInput.tsx  # Debounced stop autocomplete input
│   │   ├── PlannerForm.tsx      # Main parameter inputs, safeguards, and presets
│   │   ├── JourneyCard.tsx      # Pareto alternative card with duration breakdown
│   │   ├── JourneyResults.tsx   # Results list, loading skeletons, and empty states
│   │   └── StopDiscovery.tsx    # Terminal stop discovery and nearby radius lookup
│   │
│   ├── map/
│   │   └── DelhiMap.tsx         # Leaflet container, DivIcon markers, and polylines
│   │
│   ├── pages/
│   │   └── PlannerPage.tsx      # Root coordinator page orchestrating state and API
│   │
│   └── test/
│       ├── setup.ts             # Vitest test setup with DOM/ResizeObserver mocks
│       ├── formatters.test.ts   # Formatting unit tests
│       ├── apiService.test.ts   # API client tests
│       ├── PlannerForm.test.tsx # Form validation and payload construction tests
│       ├── JourneyResults.test.tsx # Journey card and leg expansion tests
│       └── HeaderAndAlerts.test.tsx # Status badges and alert banner tests
```

---

## 4. State Management Strategy

To maintain high performance and simplicity without unnecessary external dependencies:
1. **Local View State:** Coordinated in `PlannerPage.tsx` using native React hooks (`useState`, `useEffect`).
2. **Form Parameters:** Managed inside `PlannerForm.tsx` and emitted via typed `onSubmit(req: JourneyPlanRequest)` callbacks.
3. **Map Interaction:** Clicking on the map emits `(lat, lon)` coordinates that update origin/destination state in `PlannerPage.tsx`, triggering immediate visual marker updates on `DelhiMap.tsx`.
4. **Selected Alternative Highlighting:** Clicking any alternative card updates `selectedJourneyIndex`, causing `DelhiMap.tsx` to automatically re-render the transit path and auto-fit map viewport bounds using Leaflet's `fitBounds()`.

---

## 5. API Client Integration & Error Envelopes

The frontend client in `frontend/src/services/api.ts` maps directly to the FastAPI REST endpoints:

| Frontend Client Method | HTTP Route | Payload / Query Parameters | Response Schema |
|:---|:---|:---|:---|
| `apiService.getHealth()` | `GET /api/v1/health` | None | `HealthResponse` |
| `apiService.getTimetableStatus()` | `GET /api/v1/timetable/status` | `service_date`, `allow_assumed_recurring` | `TimetableStatusResponse` |
| `apiService.searchStops()` | `GET /api/v1/stops/search` | `query`, `limit` | `StopSearchResponse` |
| `apiService.getNearbyStops()` | `GET /api/v1/stops/nearby` | `lat`, `lon`, `radius_m`, `limit` | `NearbyStopsResponse` |
| `apiService.getRouteDetail()` | `GET /api/v1/routes/{id}` | Route ID path parameter | `RouteDetailResponse` |
| `apiService.planJourney()` | `POST /api/v1/journeys/plan` | JSON `JourneyPlanRequest` | `JourneyPlanResponse` |

### Typed Error Interception
The client raises custom `ApiException(status, errorData)` instances:
- **HTTP 400 (`EXPIRED_TIMETABLE`):** Triggers an actionable warning banner: *"Timetable Expired (Strict Mode)"* with an interactive button: *"Enable Assumed Recurring Mode & Retry"*.
- **HTTP 422 (`VALIDATION_ERROR`):** Displays human-readable parameter constraints.
- **HTTP 503 (`TIMETABLE_UNAVAILABLE`):** Notifies user of offline GTFS database assets.

