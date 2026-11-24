# Delhi Real-Time Bus Traffic Model & Journey Planner
## Final Product Requirements Document (PRD v3.0)

**Project:** Hackathon Problem 1 – Real-time Bus Traffic Model and Journey Planner  
**Location:** Delhi, India  
**Prepared:** 20 November 2026  
**Implementation environment:** Google Antigravity  
**Status:** Implementation-ready specification, subject to Gate 0 data verification

---

# Part 1 – Product Definition

## 1. Product Overview

### 1.1 Vision

Build a data-driven bus journey planner for Delhi that treats buses as a distributed traffic-sensing network.

The system will use historical bus GPS observations, static GTFS data, and optional live GTFS-RT vehicle positions to:

- Learn actual bus travel-time patterns between stops.
- Predict travel times based on departure time and day type.
- Estimate waiting times using credible schedules or observed headways.
- Recommend direct and transfer-based bus journeys.
- Include walking, waiting, transfers, and in-vehicle time in total journey estimates.
- Display routes and journey information on a map.

### 1.2 Core Problem

Static timetables do not fully capture congestion, traffic signals, stop delays, and operational variation.

Passengers need realistic journey-time estimates for the time they intend to travel, rather than relying only on scheduled durations.

### 1.3 Primary Success Criterion

**Travel-time prediction accuracy is the primary judging criterion.**

The project must measure its predictions against observed bus trips and compare them with Google Maps estimates using a documented and legitimate method.

Frontend polish and optional features must not take priority over:

1. Data quality and GPS processing.
2. Reliable ground-truth extraction.
3. Prediction accuracy.
4. Journey-planner correctness.
5. Validation and reproducibility.

### 1.4 Required Deliverables

1. Reproducible GPS and GTFS processing pipeline.
2. Segment-level traffic statistics.
3. Trained and versioned travel-time prediction model, if it improves on the baseline.
4. Time-dependent bus journey planner supporting direct and transfer journeys.
5. REST API with OpenAPI documentation.
6. Map-based frontend consuming the real API.
7. Validation report comparing predictions with observed trips and Google Maps.
8. Technical documentation, automated tests, and setup instructions.

---

## 2. Scope and Priorities

### 2.1 Priority Levels

| Priority | Meaning | Features |
|---|---|---|
| P0 | Essential | Data discovery, GTFS loading, GPS cleaning, shape matching, stop-crossing extraction or documented fallback, baseline prediction, ML evaluation, RAPTOR planner, direct and one-transfer journeys, core API, map UI, validation report |
| P1 | Strongly expected | Two-transfer journeys, confidence indicators, sparse-data fallback, time-profile comparison, Google Maps comparison, live GTFS-RT adjustment, traffic endpoint, robust UI states |
| P2 | Optional | Live vehicle tracking layer, traffic heatmap, favourites, journey history, disruption notices |

### 2.2 Out of Scope

- Ticketing and payments.
- Driver or fleet management.
- Dispatching.
- Demand prediction.
- Full Metro integration.
- User accounts and authentication.
- Commercial fleet-management features.

### 2.3 Cut-Line Rule

If the project falls behind schedule:

1. Drop P2 features first.
2. Reduce P1 scope if necessary.
3. Protect all P0 features.
4. If stop-level GPS extraction is not feasible, use merged timepoint segments or route-level profiles. Do not stop the entire project.

---

## 3. Confirmed Facts, Unknowns, and Assumptions

Antigravity must distinguish verified information from assumptions.

| Item | Status |
|---|---|
| Historical GPS, static GTFS, and real-time data are required by the challenge | Confirmed by challenge brief |
| Historical GPS is described as October 2026 DTC data in daily SQLite files inside a 7z archive | Stated in the supplied project brief; access must be verified |
| Static GTFS includes stops, routes, trips, stop_times, and shapes | Stated in supplied brief; actual files must be checked |
| Approximately 10,500 stops, 2,400 routes, and 89,000 trips | Approximate; verify |
| GPS SQLite table and column names | Unknown |
| GPS sampling interval | Unknown |
| GPS route_id and trip_id join to GTFS IDs | Unverified |
| GTFS calendar files are present | Unverified |
| Live GTFS-RT feed is accessible | Unverified |
| GPS coverage includes every GTFS operator | Unverified |
| Walking speed of 4.5 km/h | Proposed configurable assumption |
| Walking detour factor of 1.3 | Proposed configurable assumption |
| Minimum transfer buffer of 120 seconds | Proposed configurable assumption |

Never report an assumption as a measured result.

---

# Part 2 – Data and System Architecture

## 4. Data Sources and Gate 0: Data Discovery

### 4.1 Data Sources

**Historical GPS**

- Delhi Transport Stack historical DTC GPS data.
- October 1–31, 2026, according to the supplied brief.
- Daily SQLite databases packed into a 7z archive.

Archive URL from the supplied brief:

`https://pub-091bd9e794bb4877b10b29e6df80f065.r2.dev/2026-10/delhi-dtc-bus-gtfs-rt-2026-10.7z`

**Static GTFS**

Required files:

- stops.txt
- routes.txt
- trips.txt
- stop_times.txt
- shapes.txt

Also load if available:

- calendar.txt
- calendar_dates.txt
- frequencies.txt
- agency.txt
- transfers.txt
- feed_info.txt

**Live GTFS-RT**

- Vehicle positions.
- Vehicle ID.
- Route ID.
- Latitude and longitude.
- Timestamp.

Live data is optional for system operation. The core planner must continue working when the feed is unavailable.

Access and credentials must be obtained through the official data provider. Credentials belong in environment variables, never in source code.

### 4.2 Mandatory Gate 0

Before implementing model training, inspect the real data.

Generate:

- `reports/data_discovery.md`
- `data/processed/discovery.json`

The report must contain:

1. Archive file list, file sizes, date coverage, and missing days.
2. SQLite tables, columns, types, row counts, and indexes.
3. Corrupted or unreadable database files.
4. Timestamp format and timezone.
5. Rows and distinct vehicles per day.
6. GPS ping-interval distribution: p10, p50, p90.
7. Percentage of intervals greater than 60, 120, and 300 seconds.
8. Speed distribution and invalid-coordinate rate.
9. Duplicate observation rate.
10. GPS-to-GTFS route_id and trip_id join rates.
11. Percentage of joined trips with a valid shape.
12. GTFS route and stop coverage by GPS evidence.
13. Presence of GTFS calendar and frequency files.
14. Stop-time quality and times beyond 24:00:00.
15. Holidays and anomalous days.
16. A GO, DEGRADE, or BLOCKED decision for stop-level extraction.

**Gate 0 rules**

- No model training before Gate 0.
- No fabricated dataset statistics.
- If the archive or GTFS is inaccessible, document the blocker.
- A small hand-made fixture may be used for software tests, but must be labelled as test data.
- Never report synthetic-data accuracy as real-world model accuracy.

---

## 5. System Architecture

### 5.1 Main Principle

The system uses an offline processing pipeline and an online serving API.

The API must never scan raw GPS files during a journey request.

### 5.2 Architecture Flow

```text
Historical GPS (SQLite)     Static GTFS
          |                     |
          v                     v
       Ingestion and Data Validation
                  |
                  v
         Cleaning and Exclusion Log
                  |
                  v
       Shape Matching and Map Matching
                  |
                  v
         Stop-Crossing Extraction
                  |
                  v
        Observed Segment Dataset
                  |
                  v
       Historical Statistics and ML
                  |
                  v
      Prediction Tables and Artefacts
                  |
                  v
            FastAPI Backend
                  |
          +-------+-------+
          |               |
          v               v
      RAPTOR Planner   Live Collector
          |               |
          +-------+-------+
                  |
                  v
             REST API
                  |
                  v
          React + Leaflet UI
```

### 5.3 Main Components

| Component | Responsibility |
|---|---|
| Pipeline | Ingest, clean, match, extract, aggregate, and train |
| PredictionService | Predict segment time and uncertainty |
| TrafficService | Return historical and live traffic information |
| Timetable | Load GTFS patterns, trips, stops, and calendars |
| Planner | RAPTOR-based journey planning |
| LiveCollector | Poll, validate, deduplicate, and summarise live observations |
| API layer | Validate requests and return typed responses |
| Frontend | Search, journey results, map, and traffic comparison |

Every component must be independently testable.

The planner must also run with a stub PredictionService so routing correctness can be tested without a trained model.

### 5.4 Versioning

Every generated artefact directory must contain a `manifest.json` recording:

- Data version and source-file hashes.
- Git commit.
- Creation timestamp.
- Pipeline and model parameters.
- Training and validation dates.
- Metrics.
- Model version.

API responses must expose `data_version` and `model_version`.

---

## 6. GPS and GTFS Processing Pipeline

All processing scripts must be idempotent and safe to rerun.

Write outputs to temporary locations and move them into their final locations only after successful completion.

### 6.1 Ingestion

1. Extract the archive into `data/raw/gps/`.
2. Never modify the raw source files.
3. Read SQLite files in batches.
4. Use the actual discovered column names, not assumed names.
5. Convert GPS data into Parquet partitions by date.
6. Load GTFS into the analytics and serving layers.
7. Validate relationships between trips, routes, shapes, stops, and stop_times.
8. Convert GTFS times to seconds from service-day midnight.
9. Preserve values beyond 86,400 seconds because GTFS can represent after-midnight service using times beyond 24:00:00.
10. Store timestamps internally in UTC and convert to Asia/Kolkata for passenger-facing operations.

### 6.2 Cleaning Rules

Every removed or flagged observation must have an exclusion reason.

| Code | Condition | Action |
|---|---|---|
| E01 | Exact duplicate | Remove duplicate |
| E02 | Same vehicle and timestamp, different positions | Resolve using trajectory consistency; log discarded rows |
| E03 | Invalid timestamp or coordinates | Drop |
| E04 | Timestamp outside expected file date | Flag and resolve or drop |
| E05 | Implausible movement jump | Flag and remove only the offending point if appropriate |
| E06 | Reported speed inconsistent with computed speed | Keep both; use computed speed as primary |
| E07 | Excessive reporting gap | Split vehicle-trip; never interpolate across the gap |
| E08 | Zero or negative time difference | Remove invalid later observation |

A stationary bus is valid data. Zero speed alone must never cause deletion.

Compute distance using projected or geodesic geometry. Use EPSG:32643 for Delhi metric geometry.

### 6.3 Vehicle-Trip Construction

Group GPS observations by vehicle and service date.

Split into separate vehicle-trips when:

- trip_id changes;
- a configured reporting gap is exceeded;
- progress along the shape resets near the beginning of a trip.

If trip_id is unavailable or does not join to GTFS, mark trip resolution as inferred.

### 6.4 Shape Matching

A full road-network HMM map matcher is not required. The bus follows a known GTFS shape, so the main matching task is to estimate progress along that shape.

1. If GPS trip_id joins to GTFS, use its shape_id.
2. Otherwise, evaluate candidate shapes for the GPS route, including both directions.
3. Score candidates using perpendicular offset, monotonic progress, and heading consistency.
4. Accept only when the best candidate is clearly better than the runner-up.
5. Build a projected LineString and cumulative distance array for each shape.
6. Match each ping to an along-shape distance.
7. Restrict matching to plausible progress near the previous ping, especially for loops and repeated road sections.
8. Enforce non-decreasing progress.
9. Log rejected pings and ambiguous vehicle-trips.
10. Record match-quality metrics.

Use `(trip, stop_sequence)` to identify stop occurrences. Never assume that stop_id alone uniquely identifies a stop occurrence on a loop.

### 6.5 Stop-Crossing Extraction

1. Project each stop onto the corresponding trip shape.
2. Calculate its along-shape distance.
3. Enforce monotonic stop order.
4. Exclude stops whose projections are invalid or too far from the shape.
5. Find the time at which the GPS trajectory crosses each stop position.
6. Interpolate between the two GPS pings bracketing that position.
7. Accept a crossing only if the bracketing interval and implied speed pass configured quality checks.
8. Do not fabricate missing crossings.
9. Record valid consecutive-stop observations.

The initial proposed maximum interpolation gap is 120 seconds. This is a configurable assumption and must be checked against Gate 0 sampling results.

**Canonical observed target:** elapsed time from arrival at stop k to arrival at stop k+1. This includes dwell at stop k.

Dwell is separately estimated only when the available pings can support it. Otherwise, dwell is null and remains part of the elapsed segment time.

**Extraction granularity decision**

| Outcome | Initial condition | Action |
|---|---|---|
| GO | Median ping interval no more than 30 seconds and at least 60% of consecutive stop pairs have valid crossings | Use consecutive-stop segments |
| DEGRADE | Stop-level extraction is weak, but longer-distance stop crossings are available | Merge stops into timepoint segments and mark allocations as derived |
| BLOCKED | GPS cannot be matched to GTFS shapes at an acceptable rate | Use route-level hourly speed profiles and explicitly disclose the limitation |

The thresholds above are starting assumptions, not verified dataset facts.

### 6.6 Observed Segment Dataset

Each valid observation should contain available or derivable fields such as:

- observation_id
- vehicle_id
- trip_id
- route_id
- direction_id
- pattern_id
- shape_id
- stop_sequence_from
- stop_id_from
- stop_id_to
- segment_key
- service_date
- entry and exit timestamps
- local hour and day type
- distance_m
- segment_time_s
- speed_kmh
- ping count and maximum gap
- optional dwell estimate
- match quality
- trip resolution
- quality flag

Primary segment key:

`(pattern_id, stop_sequence_from)`

A physical stop-pair key may be used for fallback pooling across routes.

### 6.7 Day Flags and Outliers

- Identify holidays and unusually low-volume days.
- Maintain a configurable day-flags file.
- Keep plausible slow travel observations; do not automatically delete them.
- Derive speed plausibility thresholds from actual data distributions.
- Report exclusions and flagged days in the validation report.

---

## 7. Traffic Analysis and Travel-Time Prediction

### 7.1 Time Binning

Proposed configuration:

- Day types: weekday, Saturday, Sunday/holiday.
- Time bins: 30 minutes.
- Model features may include hour and minute.
- Internal binning uses Asia/Kolkata local time.

Verify whether Saturday should be grouped with weekdays or treated separately.

### 7.2 Required Traffic Analysis

Generate reports for:

- Speed by hour.
- Median and percentile speed.
- Weekday versus weekend.
- Route-level traffic patterns.
- Segment-level travel-time distributions.
- Segment variability and sample counts.
- Dwell time where observable.
- Peak and off-peak periods derived from data.

All reported numbers must be generated from processed data.

### 7.3 Congestion Classes

Estimate free-flow speed per segment using the 85th percentile of observed speeds as the initial proposal.

Calculate the ratio of observed or predicted speed to free-flow speed.

Derive congestion thresholds from the empirical distribution and document their derivation. Do not present the thresholds as universal traffic definitions.

### 7.4 Sparse-Data Fallback Hierarchy

Use hierarchical shrinkage instead of abruptly switching between data sources.

| Level | Source |
|---|---|
| L0 | Same segment, same time bin, same day type |
| L1 | Same segment and day type, neighbouring time bins |
| L2 | Same segment and day type, all hours, scaled by route-hour profile |
| L3 | Same physical stop pair on other routes, adjusted by route speed ratio |
| L4 | Route-level median speed for the time bin |
| L5 | City-wide speed for the time bin, then GTFS scheduled time as final fallback |

Proposed shrinkage formula:

\[
Estimate_L =
\frac{n_L \cdot stat_L + k \cdot estimate_{L+1}}
{n_L+k}
\]

The initial proposed value of k is 5. Tune it using validation data.

Every prediction must include:

- fallback_level;
- sample count;
- prediction source;
- prediction interval;
- confidence classification.

Confidence should reflect evidence quality, sample count, and interval width. Journey confidence is limited by the weakest component, including waiting-time confidence.

### 7.5 Model Architecture

Compare the following models:

| Model | Role |
|---|---|
| M0: Hierarchical historical median | Baseline and fallback |
| M1: Ridge/linear regression on log travel time | Interpretable baseline |
| M2: Random Forest regressor | Non-linear comparison |
| M3: XGBoost regressor | Primary ML candidate |

Recommended approach: one global segment-level gradient-boosted model using historical segment statistics as features, with the hierarchical baseline retained as fallback.

Target:

`log(segment_time_s)`

Features may include:

- Segment distance and position.
- Route and direction.
- Time of day.
- Day of week and day type.
- Holiday flag.
- Historical median and mean.
- Historical variability.
- Sample count.
- Route-hour and city-hour statistics.
- Fallback level.

Historical features for training rows must be computed out-of-fold, using leave-one-day-out statistics within the training period.

Validation and test rows must use training-period statistics only.

No feature may use an observation occurring at or after the prediction time.

### 7.6 Model Selection

Select the model with the lowest validation MAE on in-vehicle trip-section time.

If two models perform similarly, prefer the simpler model.

A proposed target is at least 3% relative MAE improvement over M0 before selecting a more complex model. This is a target, not an achieved result.

If ML does not improve on the baseline, ship the baseline and document the result.

### 7.7 Prediction Intervals

Use validation residuals to construct split-conformal intervals, grouped where practical by fallback level and peak/off-peak status.

Report empirical test-set interval coverage.

### 7.8 Offline Prediction Tables

Precompute predictions for each segment, day type, and time bin.

Store:

- Predicted time.
- Lower and upper prediction bounds.
- Fallback level.
- Sample count.
- Segment index mapping.
- Model version.

The online planner should read this table rather than perform expensive model inference for every segment of every request.

### 7.9 Live and Historical Fusion

Live data is a correction layer, not a replacement for historical evidence.

1. Poll the GTFS-RT feed at a configurable interval.
2. Deduplicate observations by vehicle and timestamp.
3. Reject stale, invalid, or future-dated observations.
4. Match live vehicles to known shapes using the same matching logic.
5. Calculate recent speed relative to historical speed for the same segment and time bin.
6. Clip the ratio to a configurable range, initially 0.5–2.0.
7. Calculate live-implied travel time from the historical estimate and speed ratio.
8. Apply a confidence weight based on observation count, freshness, and how far into the future the passenger reaches the segment.
9. Propagate nearby live evidence only with reduced weight and an explicit label.
10. Test the fused model by replaying historical GPS as a simulated live feed.

Proposed initial assumptions:

- Freshness threshold: 10 minutes.
- Recent observation window: 20 minutes.
- Minimum distinct vehicles: 2.
- Maximum live horizon: 30 minutes.

These values must be tuned on validation data.

**Critical rule:** retain live fusion only if replay evaluation shows an improvement on held-out data. Otherwise, disable it and document the result.

---

## 8. Journey Planning Engine

### 8.1 Routing Algorithm

Use **RAPTOR (Round-Based Public Transit Routing)** with predicted in-vehicle travel times.

Do not use a simple shortest-distance stop graph as the journey planner.

RAPTOR is selected because it supports:

- GTFS trip and stop patterns.
- Boarding and waiting.
- Service calendars.
- Bounded transfer rounds.
- Alternative journeys.

### 8.2 Timetable Construction

1. Determine active service IDs using calendar.txt and calendar_dates.txt.
2. If calendar files are missing, treat service activation as an explicit assumption and lower confidence.
3. Group trips with identical ordered stop lists into patterns.
4. Preserve route direction and repeated stops.
5. Expand frequencies.txt when available.
6. Build predicted trip arrival times sequentially using the time bin reached at each segment.
7. Cache timetable predictions by service date and live-state version.
8. Check schedule credibility against GPS-observed departures.

### 8.3 Waiting-Time Modes

| Mode | Description |
|---|---|
| Schedule | Use timetable departures when the schedule passes the credibility check |
| Headway | Use GPS-derived headways when the timetable is unreliable |
| None | No usable waiting-time evidence; exclude by default or return with an explicit low-confidence warning |

A route's waiting mode must be recorded in route-quality metadata.

### 8.4 Walking and Transfers

Initial configurable assumptions:

- Walking speed: 4.5 km/h.
- Walking detour factor: 1.3.
- Default access/egress radius: 800 metres.
- Expanded radius if necessary: 1,500 metres.
- Maximum transfer walking distance: 400 metres.
- Minimum transfer buffer: 120 seconds.

These are proposed defaults and must be configurable.

Use projected coordinates and a spatial index to find nearby stops.

### 8.5 Journey Search

The planner must:

1. Resolve origin and destination as stops or coordinates.
2. Find nearby access and egress stops.
3. Calculate access walking time.
4. Run RAPTOR rounds according to the maximum transfer setting.
5. Board the earliest feasible trip.
6. Predict subsequent stop arrival times using the prediction lookup table.
7. Relax transfer footpaths.
8. Apply the transfer buffer.
9. Calculate egress walking time.
10. Reconstruct the journey legs.
11. Validate that every trip and stop sequence exists in GTFS.
12. Check that all journey times are non-decreasing.
13. Check the total-time accounting identity.

P0 requires direct and one-transfer journeys. Two transfers are P1.

### 8.6 Time Accounting

Every journey must satisfy:

\[
\begin{aligned}
TotalJourneyTime ={}&
AccessWalk + InitialWait \\
&+ \sum RideTime \\
&+ \sum TransferWalk \\
&+ \sum TransferWait \\
&+ EgressWalk
\end{aligned}
\]

The identity must hold exactly to the second.

**Dwell-time consistency requirement**

The observed training target is arrival-to-arrival and includes dwell at the first stop. The planner must not add the same dwell twice.

The implementation must distinguish:

- Stop arrival time.
- Stop departure or boarding time.
- In-vehicle elapsed time.
- Dwell time, where observable.

Where dwell can be estimated, derive the departure-to-next-arrival running time separately. Where dwell cannot be estimated, preserve the arrival-to-arrival definition and clearly mark the resulting boarding-time approximation. Do not mix scheduled departure times and arrival-to-arrival predictions without an explicit conversion.

### 8.7 Journey Ranking

Default ranking:

1. Earliest estimated arrival.
2. Lower walking time.
3. Fewer transfers.
4. Higher confidence.

Additional strategies:

- earliest_arrival
- fewest_transfers
- least_walking
- most_reliable

Return up to three alternatives by default.

Remove near-duplicate journeys that use effectively the same route sequence and have almost identical arrival times.

### 8.8 Time-Profile Comparison

For a selected journey, estimate in-vehicle travel time across departure times on the same day type.

Identify the quietest departure time only among bins with at least medium evidence.

If evidence is insufficient, return an explicit insufficient-data response. Never invent a comparison value.

---

# Part 3 – Validation and API

## 9. Validation Methodology

Validation is one of the most important deliverables.

### 9.1 Chronological Split

Split by whole days, not random rows.

Proposed structure:

| Split | Approximate share | Purpose |
|---|---:|---|
| Training | 60% | Fit statistics and models |
| Validation | 20% | Model selection and parameter tuning |
| Test | 20% | One-time final evaluation |

Fix exact dates after Gate 0 and record them in `config/split.yaml`.

The test set must not influence model selection.

Also perform rolling-origin evaluation as a robustness check.

A test must verify:

`max(train_timestamp) < min(validation_timestamp) < min(test_timestamp)`

### 9.2 Required Metrics

- MAE.
- RMSE.
- Median absolute error.
- Mean signed error or bias.
- MAPE, with a documented minimum actual-time threshold.
- Median absolute percentage error.
- Prediction-interval coverage.
- Percentage of predictions within 10% and 20% of actual.

### 9.3 Level 1: Segment Accuracy

Compare M0, M1, M2, M3, and live-fused variants.

Break down results by:

- Hour.
- Weekday and weekend.
- Peak and off-peak.
- Route.
- Segment length.
- Sample-count band.
- Fallback level.

### 9.4 Level 2: In-Vehicle Trip-Section Accuracy

This is the primary headline model metric.

Compare predicted and observed travel times across sections of real vehicle-trips.

Include short sections, longer sections, and full-route sections where observations permit.

Report MAE, RMSE, MAPE, and bias by route group, time period, day type, and trip-section length.

### 9.5 Level 3: Full-Journey Replay

Evaluate the complete passenger experience.

Include:

- Access walking.
- Initial waiting.
- Bus travel.
- Transfer walking.
- Transfer waiting.
- Final walking.

Use only information available before each simulated departure time.

Report predicted-versus-observed arrival error and separate waiting error from ride error.

Report how many journeys could not be evaluated because observed crossings were insufficient.

### 9.6 Google Maps Comparison

Do not scrape Google Maps.

Use an authorised Google Routes/Directions API method where available, or documented manual comparisons through the Google Maps interface.

For equivalent origin-destination pairs and future departure slots, record:

- Platform prediction.
- Google estimate.
- Historical observed reference for the matching day type and time bin.
- Collection timestamp.
- Requested departure time.
- Route and mode details.

Report differences against the empirical reference.

Document limitations, including route differences, schedule influence, sample size, and the fact that October historical data may not represent the later comparison period.

Do not claim superiority over Google Maps unless the results support that conclusion.

### 9.7 Required Scenario Matrix

At least one result or a documented blocker is required for:

1. Weekday morning peak.
2. Weekday afternoon.
3. Weekday evening peak.
4. Late night.
5. Weekend.
6. Direct journey.
7. Transfer journey.
8. Sparse-GPS journey.
9. Live data unavailable.
10. Invalid origin or destination.

### 9.8 Validation Report

Create:

`reports/validation_report.md`

Include:

- Dataset description.
- Gate 0 findings.
- Data exclusions.
- Split dates and sample counts.
- Baseline versus model results.
- Segment, trip-section, and full-journey results.
- Actual-versus-predicted plots.
- Results by hour and day type.
- Interval coverage.
- Live-fusion ablation.
- Google Maps comparison.
- Sensitivity to walking speed, transfer buffer, and waiting mode.
- Limitations and future work.

Every reported number must be reproducible from code and linked to a data/model manifest.

---

## 10. Backend API Specification

### 10.1 Technology

- Python.
- FastAPI.
- Pydantic v2.
- OpenAPI.
- SQLite serving database.
- DuckDB and Parquet analytics.

### 10.2 API Conventions

Base path:

`/api/v1`

All datetimes must be ISO 8601 with an explicit timezone offset. Reject naive datetimes.

Default passenger-facing timezone: `Asia/Kolkata`.

Location formats:

- `stop:<stop_id>`
- `coord:<latitude>,<longitude>`

Names must be resolved through the stop-search endpoint.

Every response includes:

- request_id
- data_version
- model_version
- generated_at

Use a consistent error envelope:

```json
{
  "error": {
    "code": "machine_code",
    "message": "Human-readable message",
    "details": {},
    "request_id": "request-id"
  }
}
```

### 10.3 Required Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/journeys` | Find bus journeys |
| GET | `/api/v1/journeys/{journey_id}/time-profile` | Compare travel times across departure periods |
| GET | `/api/v1/stops/search` | Search stops |
| GET | `/api/v1/stops/nearby` | Find stops near coordinates |
| GET | `/api/v1/stops/{stop_id}` | Stop details and serving routes |
| GET | `/api/v1/routes/{route_id}` | Route, pattern, stop, and coverage information |
| GET | `/api/v1/traffic` | Historical/live traffic information |
| POST | `/api/v1/predict` | Segment-level travel-time prediction |
| GET | `/api/v1/health` | API, artefact, timetable, and live-feed health |

### 10.4 Journey Endpoint

`GET /api/v1/journeys`

Required parameters:

- from
- to

Optional parameters:

- depart
- limit (default 3)
- max_transfers
- max_walk_m
- ranking
- use_live
- include_geometry

The response must include:

- Journey status.
- Resolved origin and destination.
- Requested departure time.
- Live-feed status.
- Journey alternatives.
- Predicted arrival time and interval.
- Total duration.
- Walking, waiting, and riding breakdown.
- Number of transfers.
- Confidence and confidence factors.
- Prediction source.
- Ordered journey legs.
- Bus route and trip information.
- Boarding and alighting stops.
- Predicted stop arrivals.
- Geometry for map display.
- Warnings.
- Data and model versions.

Possible journey statuses:

- `ok`
- `partial`
- `no_nearby_stops`
- `no_route`

### 10.5 Time-Profile Endpoint

`GET /api/v1/journeys/{journey_id}/time-profile`

Return the predicted in-vehicle time for the same journey route sequence across departure times.

Include:

- Departure time.
- Predicted in-vehicle time.
- Confidence.
- Evidence level.
- Quietest supported departure.
- Difference relative to the selected departure.

If the cached journey expires, return `journey_expired` and require the client to search again.

### 10.6 Other Endpoint Requirements

**Stop search**

- Minimum query length: two characters.
- Case-insensitive prefix and token matching.
- Return stop ID, name, and coordinates.

**Nearby stops**

- Return stop ID, name, distance, walking estimate, and serving routes.
- Radius configurable between 50 and 3,000 metres.

**Traffic**

Return historical and live traffic information, where available, including sample count, fallback level, congestion class, and live-feed status.

**Prediction**

Accept a departure datetime and a list of segment identifiers. Return travel-time estimate, interval, source, confidence, fallback level, and sample count.

**Health**

Return:

- API status.
- Model loaded/version/training date.
- Timetable loaded status.
- Service-calendar status.
- Prediction lookup loaded status.
- Live-feed configuration and latest success.
- Data version.

### 10.7 Error Handling

| HTTP | Code | Meaning |
|---|---|---|
| 400 | invalid_location | Invalid location format |
| 400 | outside_service_area | Location outside supported region |
| 400 | invalid_datetime | Invalid or timezone-naive datetime |
| 404 | stop_not_found | Unknown stop |
| 404 | route_not_found | Unknown route |
| 404 | journey_expired | Journey cache expired |
| 422 | validation_error | Request schema invalid |
| 503 | model_unavailable | No usable model or prediction fallback |
| 503 | timetable_unavailable | GTFS timetable unavailable |
| 504 | planner_timeout | Journey search exceeded time budget |

If fallback predictions are available, prefer returning a partial result with a warning rather than failing unnecessarily.

---

## 11. Database and Storage Design

### 11.1 Analytics Layer

Use:

- Parquet for processed GPS and observation data.
- DuckDB for analytical queries and training.
- Per-day processing to avoid loading the entire raw dataset into memory.

### 11.2 Serving Layer

Use SQLite in WAL mode, read-only at runtime where practical.

Required logical tables:

| Table | Main purpose |
|---|---|
| stops | Stop IDs, names, coordinates, projected coordinates |
| routes | Route metadata |
| trips | Trip, route, service, shape, and pattern information |
| stop_times | Ordered stops and GTFS times |
| shapes | Route shape geometry |
| calendar | Service weekday and date rules |
| calendar_dates | Service exceptions |
| patterns | Ordered route patterns |
| pattern_stops | Pattern positions and stop references |
| segment_stats | Historical segment statistics |
| route_quality | GPS evidence and schedule credibility |
| model_registry | Model versions and metrics |
| data_manifest | Data and artefact versioning |

### 11.3 Prediction Lookup Table

Store predicted segment time, p10, p90, fallback level, and sample count in memory-mapped NumPy arrays.

Check storage size before finalising time-bin granularity. Reduce bin resolution if necessary.

---

## 12. Frontend Specification

### 12.1 Technology

- React.
- TypeScript.
- Vite.
- Tailwind CSS.
- React-Leaflet.
- OpenStreetMap tiles with proper attribution and usage-policy compliance.
- TanStack Query.
- Generated TypeScript API types from OpenAPI.
- Recharts or plain SVG for time-profile visualisation.

The frontend must not contain API secrets.

### 12.2 Search Interface

Provide:

- Origin input.
- Destination input.
- Debounced stop autocomplete.
- Map selection for coordinates.
- Swap-origin-and-destination button.
- Date and time selection.
- Depart-now option.
- Maximum walking distance.
- Maximum transfers.
- Journey-ranking option.
- Search button.

Synchronise search parameters with the URL so results can be shared.

### 12.3 Journey Results

Show up to three alternatives.

Each card should display:

- Total journey duration.
- Arrival time and prediction interval.
- Bus routes.
- Transfer count.
- Walking time.
- Waiting time.
- Confidence.
- Prediction source.

### 12.4 Journey Details

Display a timeline containing:

- Access walking.
- Initial waiting.
- Boarding stop and time.
- Bus route.
- Intermediate stops and predicted arrivals.
- Alighting stop and time.
- Transfer walking and waiting.
- Final walking.

Show warnings such as risky transfers and routes without GPS evidence.

### 12.5 Map

Show:

- Origin and destination markers.
- Bus stops.
- Bus-leg polylines.
- Walking legs with a distinct dashed style.
- Transfer markers.
- Selected-journey highlighting.
- Map legend.
- Map attribution.

### 12.6 Traffic Comparison

Use the time-profile API.

Show predicted in-vehicle duration across departure times, the selected departure, the quietest supported departure, and the difference.

If the evidence is insufficient, display a clear insufficient-data message rather than a fabricated value.

### 12.7 Method and Data Information

Provide a panel or modal showing:

- Data source.
- Data version.
- Model version.
- Training date.
- Walking-speed assumption.
- Transfer-buffer assumption.
- Waiting-time method.
- Known limitations.

### 12.8 UI States

| State | Required behaviour |
|---|---|
| Loading | Skeleton cards and disabled search while request is running |
| Success | Journey cards and map |
| Partial data | Results plus reduced-confidence notice |
| No nearby stops | Identify affected endpoint and allow larger radius |
| No route | Suggest changing time, walking radius, or transfer limit |
| Invalid location | Inline validation error |
| Live unavailable | Non-blocking historical-data notice |
| API unavailable | Retry option and error code |
| Empty autocomplete | Clear no-matching-stops message |

### 12.9 Accessibility

- Keyboard-operable controls.
- Labels for all inputs.
- Sufficient contrast.
- Accessible status announcements.
- Colour must not be the only differentiator.
- Touch targets of at least 44 pixels.

---

# Part 4 – Completion Requirements

## 13. Measurable Acceptance Criteria

These criteria define what must be demonstrated. They are not claims that the project has already achieved them.

### 13.1 Data

- [ ] Gate 0 report generated from real data.
- [ ] Archive coverage and missing days documented.
- [ ] SQLite schemas and row counts documented.
- [ ] GPS sampling distribution measured.
- [ ] GPS-to-GTFS join rates measured.
- [ ] GTFS referential integrity checked.
- [ ] Exclusion log generated.
- [ ] Stop-level extraction decision documented.
- [ ] No synthetic data included in real evaluation.

### 13.2 Prediction

- [ ] Historical baseline implemented.
- [ ] At least one ML candidate evaluated against the baseline.
- [ ] Chronological train/validation/test split enforced.
- [ ] Leakage tests pass.
- [ ] MAE, RMSE, bias, and interval coverage reported.
- [ ] Test results generated from held-out real observations.
- [ ] Model selection is supported by validation results.
- [ ] Model and data versions are recorded.

### 13.3 Journey Planner

- [ ] Direct journeys work.
- [ ] At least one-transfer journeys work.
- [ ] Two transfers work if P1 is completed.
- [ ] Walking and waiting are included.
- [ ] Journey time accounting identity passes.
- [ ] Calendar handling is tested.
- [ ] Repeated stops and loop patterns are handled.
- [ ] Every returned bus leg references valid GTFS trips and stops.
- [ ] No journey contains decreasing timestamps.

### 13.4 API

- [ ] All required P0 endpoints work.
- [ ] OpenAPI documentation is available.
- [ ] Typed request and response schemas exist.
- [ ] Error envelope is consistent.
- [ ] Data and model versions are returned.
- [ ] API continues with historical fallbacks when live data is unavailable.

### 13.5 Frontend

- [ ] Origin and destination search work.
- [ ] Real API journeys are displayed.
- [ ] Map shows the returned journey.
- [ ] Walking and bus legs are visually distinct.
- [ ] Confidence and prediction source are visible.
- [ ] Loading, error, empty, and partial-data states work.
- [ ] No hardcoded journey results are present.

### 13.6 Validation and Submission

- [ ] Validation report exists.
- [ ] Required scenario matrix is covered or blockers are documented.
- [ ] Google Maps comparison method and limitations are documented.
- [ ] Technical note exists.
- [ ] README includes setup and execution instructions.
- [ ] Automated tests pass.
- [ ] Docker-based run instructions work.
- [ ] No secrets are committed.

### 13.7 Proposed Performance Targets

These are targets to measure, not achieved results:

- 95% of journey requests under 3 seconds on the documented development machine, excluding live-feed latency.
- No raw GPS scan during an online journey request.
- Prediction lookup loaded once and reused.
- API remains usable with live data disabled.

---

## 14. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| GPS sampling too sparse | Stop-level travel times unreliable | Use merged timepoint segments or route-level profiles |
| GPS IDs do not join to GTFS | Cannot reliably associate vehicles with trips | Candidate shape matching and join diagnostics |
| Archive or feed inaccessible | Pipeline blocked | Document access blocker and build test fixtures only for software tests |
| GTFS schedules inaccurate | Waiting estimates unreliable | Use GPS-derived headways |
| Live feed unavailable | No live adjustment | Historical prediction remains fully functional |
| One month of data | Weak generalisation | Report limitations and avoid seasonal claims |
| Loop routes and repeated stops | Incorrect direction or stop matching | Use trip patterns and stop_sequence |
| Target leakage | Inflated evaluation scores | Out-of-fold historical features and chronological tests |
| Google comparison limitations | Invalid comparison claims | Use authorised methods and disclose sample limitations |
| RAPTOR performance | Slow journey searches | Corridor pruning, pattern grouping, NumPy optimisation |
| Prediction and dwell mismatch | Double-counted journey time | Separate arrival, departure, dwell, and running-time semantics |
| Frontend takes too long | Core accuracy work delayed | Complete P0 before P2 |

---

## 15. Testing Strategy

### 15.1 Unit Tests

Test:

- GPS cleaning.
- Duplicate handling.
- Speed and distance calculation.
- Shape matching.
- Monotonic progress.
- Stop-crossing interpolation.
- Segment aggregation.
- Fallback hierarchy.
- Prediction intervals.
- Timezone conversion.
- GTFS service-calendar logic.
- RAPTOR rounds.
- Walking and transfer calculations.
- Journey time accounting.

### 15.2 Integration Tests

Test:

- GPS and GTFS ingestion.
- Full processing pipeline on a small fixture.
- Artefact loading.
- Prediction service.
- Timetable construction.
- Planner with a stub prediction service.
- API response schemas.
- Live-feed failure and fallback behaviour.

### 15.3 Planner Correctness Fixture

Create a small, hand-made GTFS fixture containing:

- One direct route.
- One two-route transfer.
- One route with repeated stops or a loop.
- Different departure times.
- A service-calendar exception.
- A route with no GPS evidence.

Verify expected journey feasibility, ordering, transfers, and total-time accounting.

### 15.4 End-to-End Tests

Use Playwright to:

1. Open the frontend.
2. Enter an origin and destination.
3. Search for journeys against a running backend.
4. Verify journey cards render.
5. Verify map layers render.
6. Verify an API error or no-route state.

Mocked responses may be used for component tests, not as evidence of real-data system performance.

---

## 16. Repository Structure

Use a clear and modular structure. Adapt names if the existing repository already has a working structure.

```text
delhi-bus-planner/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── pipeline/
│   │   ├── prediction/
│   │   ├── planner/
│   │   ├── traffic/
│   │   ├── gtfs/
│   │   └── services/
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types/
│   │   └── map/
│   └── package.json
│
├── data/
│   ├── raw/
│   ├── processed/
│   ├── models/
│   └── serving/
│
├── config/
│   ├── pipeline.yaml
│   ├── model.yaml
│   ├── planner.yaml
│   └── split.yaml
│
├── scripts/
│   ├── discover_data.py
│   ├── ingest_gps.py
│   ├── ingest_gtfs.py
│   ├── clean_gps.py
│   ├── match_shapes.py
│   ├── extract_segments.py
│   ├── build_statistics.py
│   ├── train_model.py
│   ├── build_prediction_table.py
│   └── evaluate.py
│
├── reports/
│   ├── data_discovery.md
│   ├── validation_report.md
│   └── technical_note.md
│
├── docs/
│   ├── architecture.md
│   ├── api.md
│   └── data_dictionary.md
│
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── .gitignore
└── README.md
```

---

## 17. Technical Decisions

| Area | Decision | Reason |
|---|---|---|
| Backend | FastAPI + Pydantic v2 | Typed REST API and OpenAPI |
| Frontend | React + TypeScript + Vite | Practical interactive web client |
| UI styling | Tailwind CSS | Rapid consistent styling |
| Map | React-Leaflet + OpenStreetMap | Map visualisation with replaceable tile provider |
| Analytics | DuckDB + Parquet | Efficient processing of large historical data |
| Serving database | SQLite | Lightweight GTFS and metadata serving |
| Geometry | pyproj + Shapely STRtree | Projected geometry and spatial indexing |
| Prediction | Baseline plus model comparison | Avoid assuming ML will outperform historical statistics |
| Primary ML candidate | XGBoost | Global model can share signal across segments |
| Prediction intervals | Split conformal calibration | Communicate uncertainty |
| Routing | RAPTOR | Transit-aware routing with bounded transfers |
| Prediction serving | Precomputed NumPy lookup arrays | Fast online journey requests |
| Live fusion | Bounded speed-ratio correction | Use live evidence only when validation supports it |
| Testing | pytest + Playwright | Backend and frontend coverage |
| Deployment | Docker and Docker Compose | Reproducible execution |
| Scale-up database | PostgreSQL/PostGIS, if needed later | Not required for the hackathon baseline |

---

## 18. Development Milestones

### Milestone 0 – Repository and Data Discovery

- Inspect repository.
- Verify Python and Node environments.
- Obtain and inspect real GPS and GTFS data.
- Generate Gate 0 report.
- Decide GO, DEGRADE, or BLOCKED.

**Exit condition:** Real-data access and feasibility are documented.

### Milestone 1 – GTFS and GPS Ingestion

- Load GTFS.
- Extract GPS databases.
- Convert GPS to Parquet.
- Validate IDs and timestamps.
- Generate exclusion logs.

**Exit condition:** Reproducible processed datasets exist.

### Milestone 2 – Shape Matching and Ground Truth

- Build vehicle-trips.
- Match GPS to shapes.
- Extract stop crossings.
- Generate observed segment dataset.
- Document extraction quality.

**Exit condition:** Ground-truth travel-time observations exist or a documented fallback is selected.

### Milestone 3 – Traffic Statistics and Baseline

- Build segment statistics.
- Build time bins.
- Implement fallback hierarchy.
- Generate traffic reports.

**Exit condition:** Baseline prediction works.

### Milestone 4 – ML and Validation

- Implement candidate models.
- Prevent target leakage.
- Perform chronological evaluation.
- Compare models with M0.
- Generate validation metrics.

**Exit condition:** A model is selected based on validation results.

### Milestone 5 – Journey Planner

- Build timetable and patterns.
- Implement RAPTOR.
- Add walking and waiting.
- Add transfers.
- Add journey accounting tests.

**Exit condition:** Direct and one-transfer journeys pass correctness tests.

### Milestone 6 – Backend API

- Implement journey, stop, route, traffic, predict, and health endpoints.
- Add typed schemas and error handling.
- Publish OpenAPI.

**Exit condition:** API can be used independently of the frontend.

### Milestone 7 – Frontend

- Implement search.
- Display alternatives.
- Display journey timeline.
- Render map.
- Show confidence and data-source information.

**Exit condition:** Frontend uses real backend responses.

### Milestone 8 – Live Feed and Time Profile

- Integrate GTFS-RT if access is available.
- Replay-test live fusion.
- Add time-profile comparison.
- Keep live fusion only if validation supports it.

**Exit condition:** Live and historical modes work with explicit status.

### Milestone 9 – Final Validation and Submission

- Run the scenario matrix.
- Compare with observed trips.
- Perform Google Maps comparison where possible.
- Generate technical note.
- Test Docker setup.
- Finalise README and demonstration flow.

**Exit condition:** All P0 requirements are complete and P1 completion/blockers are documented.

---

# Part 5 – Implementation Handoff to Google Antigravity

## 19. Implementation Rules

Antigravity must follow these rules throughout development:

1. Read this complete PRD before changing the repository.
2. Inspect existing files and code before creating replacements.
3. Do not delete or overwrite working code without explaining why.
4. Do not fabricate data, routes, traffic values, model results, or API responses.
5. Do not assume data schemas, file names, or feed availability.
6. Run Gate 0 before modelling.
7. Keep assumptions configurable.
8. Do not train or evaluate on synthetic fixtures as if they were real data.
9. Use chronological validation.
10. Prevent target leakage.
11. Keep the planner operational without live GTFS-RT.
12. Do not implement decorative P2 features before P0 is complete.
13. Write tests alongside the implementation.
14. Keep secrets in environment variables.
15. Record every important technical decision.
16. Report actual progress and blockers honestly.

## 20. Required Implementation Sequence

Antigravity must work in this order:

1. Repository inspection.
2. Gate 0 data discovery.
3. GTFS and GPS ingestion.
4. Cleaning and exclusion logs.
5. Shape matching.
6. Stop-crossing extraction or fallback.
7. Historical statistics.
8. Baseline prediction.
9. ML comparison and chronological evaluation.
10. Prediction lookup table.
11. GTFS timetable construction.
12. RAPTOR planner.
13. Backend API.
14. Frontend.
15. Live-feed integration and time-profile comparison.
16. Final validation, documentation, and Docker setup.

Do not skip ahead to frontend development while the data pipeline is unverified.

## 21. Required Antigravity Behaviour

At the start of implementation, Antigravity must provide:

- Repository structure summary.
- Existing technology stack.
- Existing implementation status.
- Data files detected.
- Missing inputs and access requirements.
- Proposed milestone plan.
- Immediate next task.

For every milestone, Antigravity must provide:

- Files created or modified.
- What was implemented.
- Commands executed.
- Tests run and results.
- Data or model artefacts generated.
- Remaining issues.
- Whether the milestone's exit condition is satisfied.

Do not mark a milestone complete merely because code was written. Its exit condition must be demonstrated.

## 22. Final Submission Contents

The final repository must include:

- Complete source code.
- Reproducible data-processing scripts.
- Model training and evaluation scripts.
- Prediction artefacts and manifests, where permitted by data size and licensing.
- RAPTOR journey planner.
- REST API.
- Map-based frontend.
- OpenAPI documentation.
- Automated tests.
- Data discovery report.
- Validation report.
- Technical note.
- README.
- Docker setup.
- `.env.example`.
- Clear instructions for obtaining and configuring data credentials.

## 23. Final Definition of Done

The project is complete when:

1. The real data has been inspected and documented.
2. Travel-time observations are extracted using a defensible method or an explicit fallback.
3. A historical baseline exists.
4. ML candidates have been compared fairly against the baseline.
5. Evaluation is chronological and leakage-controlled.
6. The journey planner returns valid direct and transfer journeys.
7. Walking, waiting, riding, and transfer time are accounted for without double counting.
8. The API exposes the required functionality.
9. The frontend displays real API results on a map.
10. Live-feed failure does not break the planner.
11. Validation results are reproducible.
12. All limitations and assumptions are disclosed.
13. The project can be set up and run using the documented instructions.

---

# Appendix A – Important Configuration Defaults

The following values are starting assumptions and must be checked against the real data.

| Setting | Initial value |
|---|---:|
| Time bin | 30 minutes |
| Walking speed | 4.5 km/h |
| Walking detour factor | 1.3 |
| Default access/egress radius | 800 m |
| Expanded access/egress radius | 1,500 m |
| Maximum transfer walking distance | 400 m |
| Minimum transfer buffer | 120 seconds |
| Live freshness threshold | 10 minutes |
| Live observation window | 20 minutes |
| Minimum distinct live vehicles | 2 |
| Maximum live prediction horizon | 30 minutes |
| Default journey alternatives | 3 |
| Maximum transfer rounds | 3 |
| Initial shrinkage parameter k | 5 |

These values must be stored in configuration files rather than hardcoded throughout the application.

# Appendix B – Important Limitations to Disclose

- Historical GPS coverage is described as DTC data and may not cover all GTFS operators.
- The supplied historical dataset covers approximately one month.
- One month of data cannot establish seasonal or monsoon behaviour.
- Sparse GPS pings can make individual stop crossings and dwell times difficult to identify.
- Shape-matching errors can affect ground truth.
- GTFS timetable credibility must be measured.
- Waiting-time predictions may be weaker where actual headways are irregular.
- Google Maps comparisons may involve different routes and different data periods.
- Live feed access and reliability are not guaranteed.

The project must communicate these limitations rather than hide them.

---

**End of PRD v3.0**

**Implementation status:** Not yet verified. This document defines the requirements and implementation plan; it does not claim that the software, data pipeline, or model has already been built or validated.