"""Delhi Live GTFS-Realtime (GTFS-RT) Ingestion & Validation Engine.

PRD v3.0 Milestone 8:
Provides bounded polling, strict coordinate & timestamp validation, deduplication,
GTFS static cross-referencing, and graceful error handling for Delhi's live transit feed.

Classification states:
- AVAILABLE_VALIDATED: Feed operational, valid protobuf, fresh timestamps, GTFS match verified.
- AVAILABLE_PARTIAL: Feed accessible with partial coverage or minor parsing warnings.
- AUTH_REQUIRED: Authentication credentials missing or rejected (HTTP 401).
- UNAVAILABLE: Endpoint unreachable, network timeout, connection refused, or HTTP 5xx.
- INVALID_DATA: Malformed payload, HTML error page, or non-protobuf response.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import logging
import math
import os
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import google.transit.gtfs_realtime_pb2 as gtfs_rt
except ImportError:
    gtfs_rt = None  # Handled gracefully if bindings missing

import requests

logger = logging.getLogger(__name__)

# Delhi WGS84 Geographic Bounding Box (latitude: 28.30 to 28.95, longitude: 76.80 to 77.45)
DELHI_BBOX_LAT_MIN = 28.30
DELHI_BBOX_LAT_MAX = 28.95
DELHI_BBOX_LON_MIN = 76.80
DELHI_BBOX_LON_MAX = 77.45

# National Capital Region (NCR) Expanded Bounding Box for Interstate Routes
NCR_BBOX_LAT_MIN = 27.50
NCR_BBOX_LAT_MAX = 29.50
NCR_BBOX_LON_MIN = 76.00
NCR_BBOX_LON_MAX = 78.50

# Staleness threshold: reject vehicle pings older than 900 seconds (15 minutes)
MAX_TIMESTAMP_STALENESS_SECONDS = 900

# Default endpoint on Delhi Transport Stack
DEFAULT_DELHI_GTFS_RT_URL = (
    "https://dts-backend.transportstack.in/api/dataset/otd/get-file"
    "?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb"
)


class FeedAvailabilityStatus(str, Enum):
    AVAILABLE_VALIDATED = "AVAILABLE_VALIDATED"
    AVAILABLE_PARTIAL = "AVAILABLE_PARTIAL"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID_DATA = "INVALID_DATA"


@dataclass
class ValidatedVehiclePosition:
    vehicle_id: str
    route_id: Optional[str]
    trip_id: Optional[str]
    latitude: float
    longitude: float
    bearing: Optional[float]
    speed_kmh: Optional[float]
    timestamp_utc: int
    is_valid_coordinates: bool
    is_fresh: bool
    is_matched_to_gtfs: bool
    validation_notes: List[str]
    is_current: bool = True
    is_out_of_area: bool = False
    area_classification: str = "DELHI_CORE"


def classify_coordinates(lat: Optional[float], lon: Optional[float]) -> Tuple[bool, bool, str]:
    """Classify coordinates into Delhi Core, NCR Out-of-Bounds, or Invalid Geography.
    
    Returns:
        (is_valid_coordinates, is_out_of_area, area_classification)
    """
    if lat is None or lon is None or not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
        return False, True, "INVALID_GEOGRAPHY"
    if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
        return False, True, "INVALID_GEOGRAPHY"
    if (DELHI_BBOX_LAT_MIN <= lat <= DELHI_BBOX_LAT_MAX) and (DELHI_BBOX_LON_MIN <= lon <= DELHI_BBOX_LON_MAX):
        return True, False, "DELHI_CORE"
    if (NCR_BBOX_LAT_MIN <= lat <= NCR_BBOX_LAT_MAX) and (NCR_BBOX_LON_MIN <= lon <= NCR_BBOX_LON_MAX):
        return True, True, "NCR_OUT_OF_BOUNDS"
    return False, True, "INVALID_GEOGRAPHY"


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two WGS84 coordinates in meters."""
    r = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


class LiveFeedCollector:
    """Bounded, resilient GTFS-Realtime vehicle position collector."""

    CACHE_TTL_SECONDS: float = 15.0

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        api_key: Optional[str] = None,
        poll_interval_seconds: int = 15,
        is_enabled: bool = False,
        known_route_ids: Optional[Set[str]] = None,
        known_trip_ids: Optional[Set[str]] = None,
        max_staleness_seconds: Optional[int] = None,
    ):
        self.endpoint_url = endpoint_url or os.getenv("DELHI_GTFS_RT_URL", DEFAULT_DELHI_GTFS_RT_URL)
        self.api_key = api_key if api_key is not None else os.getenv("DELHI_TRANSPORTSTACK_API_KEY", "")
        self.poll_interval_seconds = poll_interval_seconds
        self.is_enabled = is_enabled if is_enabled is not None else (os.getenv("LIVE_FEED_ENABLED", "false").lower() == "true")
        self.known_route_ids = known_route_ids or set()
        self.known_trip_ids = known_trip_ids or set()
        self.max_staleness_seconds = (
            max_staleness_seconds
            if max_staleness_seconds is not None
            else int(os.getenv("LIVE_FEED_STALENESS_SECONDS", str(MAX_TIMESTAMP_STALENESS_SECONDS)))
        )

        # Thread safety lock to prevent concurrent/overlapping upstream fetches
        self._fetch_lock = threading.Lock()

        # Telemetry State
        self.availability_status = (
            FeedAvailabilityStatus.AUTH_REQUIRED if not self.api_key else FeedAvailabilityStatus.UNAVAILABLE
        )
        self.last_attempt_timestamp_utc: Optional[str] = None
        self.last_success_timestamp_utc: Optional[str] = None
        self.last_fetch_mono: float = 0.0
        self.consecutive_failure_count: int = 0
        self.total_polls_count: int = 0
        self.total_success_count: int = 0
        self.active_vehicles: Dict[str, ValidatedVehiclePosition] = {}
        self.last_known_vehicles: Dict[str, ValidatedVehiclePosition] = {}
        self.out_of_area_vehicles: Dict[str, ValidatedVehiclePosition] = {}
        self.latest_feed_header_timestamp: int = 0
        self.last_duplicate_count: int = 0
        self.last_raw_entity_count: int = 0
        self.last_invalid_position_count: int = 0
        self.last_warning: Optional[str] = None

        # Upstream feed update cadence tracking
        self.upstream_fetch_count: int = 0
        self.upstream_feed_updates_count: int = 0
        self.last_upstream_feed_change_mono: float = 0.0
        self.measured_upstream_intervals: List[float] = []

    def _mark_all_vehicles_stale(self) -> None:
        """Preserve last known vehicle positions on failure, marked stale."""
        for v in self.active_vehicles.values():
            v.is_fresh = False
            v.is_current = False
        for v in self.last_known_vehicles.values():
            v.is_fresh = False
            v.is_current = False
        for v in self.out_of_area_vehicles.values():
            v.is_fresh = False
            v.is_current = False

    def _update_active_vehicles(
        self,
        validated_list: List[ValidatedVehiclePosition],
        header_timestamp: int = 0,
    ) -> None:
        """Update vehicle positions using complete snapshot semantics with last-known retention.

        1. Active current snapshot vehicles in Delhi Core are stored with is_current=True.
        2. Valid out-of-area vehicles in NCR corridor are tracked in out_of_area_vehicles.
        3. Vehicles from previous snapshot missing from latest snapshot are migrated
           to last_known_vehicles with is_current=False and is_fresh=False.
        4. Stale last-known vehicles older than max_staleness_seconds are evicted.
        """
        now_ts = int(time.time())
        new_active: Dict[str, ValidatedVehiclePosition] = {}
        new_out_of_area: Dict[str, ValidatedVehiclePosition] = {}

        for v in validated_list:
            v.is_current = True
            if v.is_out_of_area:
                new_out_of_area[v.vehicle_id] = v
            else:
                new_active[v.vehicle_id] = v

        all_new_ids = set(new_active.keys()).union(new_out_of_area.keys())

        # Migrate previously tracked vehicles missing from latest snapshot into last_known_vehicles
        for vid, prev_v in self.active_vehicles.items():
            if vid not in all_new_ids:
                age = max(0, now_ts - prev_v.timestamp_utc)
                if age <= self.max_staleness_seconds:
                    prev_v.is_current = False
                    prev_v.is_fresh = False
                    self.last_known_vehicles[vid] = prev_v
                elif vid in self.last_known_vehicles:
                    del self.last_known_vehicles[vid]

        for vid, prev_v in self.out_of_area_vehicles.items():
            if vid not in all_new_ids:
                age = max(0, now_ts - prev_v.timestamp_utc)
                if age <= self.max_staleness_seconds:
                    prev_v.is_current = False
                    prev_v.is_fresh = False
                    self.last_known_vehicles[vid] = prev_v
                elif vid in self.last_known_vehicles:
                    del self.last_known_vehicles[vid]

        # Evict expired records or re-observed vehicles from last_known_vehicles
        expired_vids = [
            vid
            for vid, lkv in self.last_known_vehicles.items()
            if (now_ts - lkv.timestamp_utc) > self.max_staleness_seconds or vid in all_new_ids
        ]
        for vid in expired_vids:
            self.last_known_vehicles.pop(vid, None)

        self.active_vehicles = new_active
        self.out_of_area_vehicles = new_out_of_area
        if header_timestamp > 0:
            if header_timestamp > self.latest_feed_header_timestamp:
                now_mono = time.monotonic()
                if self.last_upstream_feed_change_mono > 0:
                    interval = now_mono - self.last_upstream_feed_change_mono
                    self.measured_upstream_intervals.append(round(interval, 1))
                    if len(self.measured_upstream_intervals) > 20:
                        self.measured_upstream_intervals.pop(0)
                self.last_upstream_feed_change_mono = now_mono
                self.upstream_feed_updates_count += 1
            self.latest_feed_header_timestamp = max(self.latest_feed_header_timestamp, header_timestamp)

    def get_upstream_feed_metrics(self) -> Dict[str, Any]:
        """Return measured upstream feed cadence statistics."""
        avg_interval = (
            round(sum(self.measured_upstream_intervals) / len(self.measured_upstream_intervals), 1)
            if self.measured_upstream_intervals
            else None
        )
        feed_age = (
            max(0, int(time.time() - self.latest_feed_header_timestamp))
            if self.latest_feed_header_timestamp > 0
            else None
        )
        return {
            "latest_feed_header_timestamp": self.latest_feed_header_timestamp,
            "upstream_feed_age_seconds": feed_age,
            "measured_average_interval_seconds": avg_interval,
            "recent_intervals_sample": self.measured_upstream_intervals[-5:] if self.measured_upstream_intervals else [],
            "upstream_fetch_count": self.upstream_fetch_count,
            "upstream_feed_updates_count": self.upstream_feed_updates_count,
        }

    def refresh_if_expired(
        self, timeout_seconds: float = 6.0, force: bool = False
    ) -> Tuple[FeedAvailabilityStatus, Optional[str]]:
        """Fetch fresh upstream GTFS-RT snapshot when the 20-second cache expires.

        Multiple client requests share this single backend cache.
        Thread-safe: uses mutex lock to prevent concurrent/overlapping upstream network requests.
        """
        now_mono = time.monotonic()
        if not force and (now_mono - self.last_fetch_mono < self.CACHE_TTL_SECONDS) and self.last_fetch_mono > 0:
            return self.availability_status, self.last_warning

        with self._fetch_lock:
            # Double check after acquiring lock
            now_mono = time.monotonic()
            if not force and (now_mono - self.last_fetch_mono < self.CACHE_TTL_SECONDS) and self.last_fetch_mono > 0:
                return self.availability_status, self.last_warning

            start_wall = datetime.now(timezone.utc).isoformat()
            start_mono = time.monotonic()
            self.last_attempt_timestamp_utc = start_wall
            self.total_polls_count += 1

            # 1. Gate: Check credentials presence without logging secrets
            if not self.api_key or len(self.api_key.strip()) == 0:
                self.availability_status = FeedAvailabilityStatus.AUTH_REQUIRED
                msg = (
                    "DELHI_TRANSPORTSTACK_API_KEY environment variable is not configured. "
                    "Delhi GTFS-RT feed requires an authenticated x-api-key header from "
                    "Delhi Transport Stack (https://delhi.transportstack.in)."
                )
                self.last_warning = msg
                self.consecutive_failure_count += 1
                self._mark_all_vehicles_stale()
                self.last_fetch_mono = time.monotonic()
                return FeedAvailabilityStatus.AUTH_REQUIRED, msg

            # 2. Dispatch network probe
            headers = {
                "x-api-key": self.api_key.strip(),
                "Accept": "application/octet-stream, application/x-protobuf, */*",
            }
            logger.info(f"Upstream GTFS-RT fetch starting: timestamp={start_wall}, url={self.endpoint_url}")

            try:
                resp = requests.get(self.endpoint_url, headers=headers, timeout=timeout_seconds)
                latency_ms = (time.monotonic() - start_mono) * 1000.0
                status_code = resp.status_code

                # 401 Unauthorized / Forbidden
                if status_code in (401, 403):
                    self.availability_status = FeedAvailabilityStatus.AUTH_REQUIRED
                    msg = f"Transport Stack returned HTTP {status_code}: Invalid or unauthorized API key."
                    self.last_warning = msg
                    self.consecutive_failure_count += 1
                    self._mark_all_vehicles_stale()
                    self.last_fetch_mono = time.monotonic()
                    logger.warning(
                        f"Upstream GTFS-RT fetch auth failure: timestamp={start_wall}, status={status_code}, "
                        f"latency_ms={latency_ms:.1f}, error={msg}"
                    )
                    return FeedAvailabilityStatus.AUTH_REQUIRED, msg

                # 5xx Server Errors
                if status_code >= 500:
                    self.availability_status = FeedAvailabilityStatus.UNAVAILABLE
                    msg = f"Transport Stack returned HTTP {status_code} server error."
                    self.last_warning = msg
                    self.consecutive_failure_count += 1
                    self._mark_all_vehicles_stale()
                    self.last_fetch_mono = time.monotonic()
                    logger.warning(
                        f"Upstream GTFS-RT fetch server error: timestamp={start_wall}, status={status_code}, "
                        f"latency_ms={latency_ms:.1f}, error={msg}"
                    )
                    return FeedAvailabilityStatus.UNAVAILABLE, msg

                # 200 OK: Verify payload format
                if status_code == 200:
                    raw_bytes = resp.content
                    if not raw_bytes or len(raw_bytes) == 0:
                        self.availability_status = FeedAvailabilityStatus.AVAILABLE_PARTIAL
                        msg = "Feed returned HTTP 200 with empty body (0 bytes)."
                        self.last_warning = msg
                        self._mark_all_vehicles_stale()
                        self.last_fetch_mono = time.monotonic()
                        logger.warning(
                            f"Upstream GTFS-RT fetch empty body: timestamp={start_wall}, status={status_code}, "
                            f"latency_ms={latency_ms:.1f}, error={msg}"
                        )
                        return FeedAvailabilityStatus.AVAILABLE_PARTIAL, msg

                    # Check for HTML error response (e.g. Cloudflare / S3 index page)
                    snippet = raw_bytes[:100].lower()
                    if b"<html" in snippet or b"<!doctype" in snippet or b"{\"error\"" in snippet:
                        if "delhi.transportstack.in" in self.endpoint_url and "dts-backend" not in self.endpoint_url:
                            fallback_url = self.endpoint_url.replace("delhi.transportstack.in", "dts-backend.transportstack.in")
                            try:
                                fb_resp = requests.get(fallback_url, headers=headers, timeout=timeout_seconds)
                                fb_snippet = fb_resp.content[:100].lower()
                                if fb_resp.status_code == 200 and not (b"<html" in fb_snippet or b"<!doctype" in fb_snippet):
                                    raw_bytes = fb_resp.content
                                    self.endpoint_url = fallback_url
                                else:
                                    self.availability_status = FeedAvailabilityStatus.INVALID_DATA
                                    msg = "Feed returned HTML/JSON text instead of GTFS-RT binary protobuf."
                                    self.last_warning = msg
                                    self.consecutive_failure_count += 1
                                    self._mark_all_vehicles_stale()
                                    self.last_fetch_mono = time.monotonic()
                                    logger.warning(
                                        f"Upstream GTFS-RT fetch HTML error: timestamp={start_wall}, status={fb_resp.status_code}, "
                                        f"latency_ms={latency_ms:.1f}, error={msg}"
                                    )
                                    return FeedAvailabilityStatus.INVALID_DATA, msg
                            except Exception as fb_err:
                                self.availability_status = FeedAvailabilityStatus.INVALID_DATA
                                msg = f"Feed returned HTML/JSON text instead of GTFS-RT binary protobuf: {fb_err}"
                                self.last_warning = msg
                                self.consecutive_failure_count += 1
                                self._mark_all_vehicles_stale()
                                self.last_fetch_mono = time.monotonic()
                                return FeedAvailabilityStatus.INVALID_DATA, msg
                        else:
                            self.availability_status = FeedAvailabilityStatus.INVALID_DATA
                            msg = "Feed returned HTML/JSON text instead of GTFS-RT binary protobuf."
                            self.last_warning = msg
                            self.consecutive_failure_count += 1
                            self._mark_all_vehicles_stale()
                            self.last_fetch_mono = time.monotonic()
                            logger.warning(
                                f"Upstream GTFS-RT fetch HTML error: timestamp={start_wall}, status={status_code}, "
                                f"latency_ms={latency_ms:.1f}, error={msg}"
                            )
                            return FeedAvailabilityStatus.INVALID_DATA, msg

                    # Parse protobuf
                    if gtfs_rt is None:
                        self.availability_status = FeedAvailabilityStatus.INVALID_DATA
                        msg = "gtfs_realtime_pb2 parser is not available in environment."
                        self.last_warning = msg
                        self._mark_all_vehicles_stale()
                        self.last_fetch_mono = time.monotonic()
                        logger.error(f"Upstream GTFS-RT fetch missing protobuf parser: timestamp={start_wall}, error={msg}")
                        return FeedAvailabilityStatus.INVALID_DATA, msg

                    feed = gtfs_rt.FeedMessage()
                    try:
                        feed.ParseFromString(raw_bytes)
                    except Exception as parse_err:
                        self.availability_status = FeedAvailabilityStatus.INVALID_DATA
                        msg = f"Failed to parse protobuf FeedMessage: {parse_err}"
                        self.last_warning = msg
                        self.consecutive_failure_count += 1
                        self._mark_all_vehicles_stale()
                        self.last_fetch_mono = time.monotonic()
                        logger.error(f"Upstream GTFS-RT fetch parse error: timestamp={start_wall}, error={msg}")
                        return FeedAvailabilityStatus.INVALID_DATA, msg

                    entity_count = len(feed.entity)
                    self.last_raw_entity_count = entity_count

                    header_ts = (
                        int(feed.header.timestamp)
                        if feed.HasField("header") and feed.header.HasField("timestamp")
                        else 0
                    )

                    # Requirement 4 & 6.9: Prevent older response from overwriting newer response
                    if (
                        header_ts > 0
                        and self.latest_feed_header_timestamp > 0
                        and header_ts < self.latest_feed_header_timestamp
                    ):
                        msg = (
                            f"Discarded older GTFS-RT feed snapshot (feed header timestamp "
                            f"{header_ts} < current {self.latest_feed_header_timestamp})."
                        )
                        logger.warning(msg)
                        self.last_fetch_mono = time.monotonic()
                        return self.availability_status, msg

                    # Validate entities and update active_vehicles strictly from decoded provider messages
                    validated_list = self.validate_and_filter_entities(feed)
                    self._update_active_vehicles(validated_list, header_timestamp=header_ts)

                    self.last_success_timestamp_utc = datetime.now(timezone.utc).isoformat()
                    self.last_fetch_mono = time.monotonic()
                    self.consecutive_failure_count = 0
                    self.total_success_count += 1

                    valid_count = len(validated_list)
                    if entity_count > 0:
                        self.availability_status = FeedAvailabilityStatus.AVAILABLE_VALIDATED
                        msg = (
                            f"Feed verified: {entity_count} active vehicle position entities parsed successfully "
                            f"({valid_count} validated, {len(self.active_vehicles)} core Delhi, "
                            f"{len(self.out_of_area_vehicles)} NCR corridor, {len(self.last_known_vehicles)} retained)."
                        )
                        self.last_warning = None
                    else:
                        self.availability_status = FeedAvailabilityStatus.AVAILABLE_PARTIAL
                        msg = "Feed parsed successfully but contained 0 vehicle entities."
                        self.last_warning = msg

                    logger.info(
                        f"Upstream GTFS-RT fetch completed: timestamp={start_wall}, status={status_code}, "
                        f"latency_ms={latency_ms:.1f}, entity_count={entity_count}, valid_vehicles={valid_count}, "
                        f"core_tracked={len(self.active_vehicles)}, ncr_tracked={len(self.out_of_area_vehicles)}, "
                        f"last_known={len(self.last_known_vehicles)}, error=None"
                    )
                    return self.availability_status, msg

                # Other HTTP statuses (404, etc.)
                self.availability_status = FeedAvailabilityStatus.UNAVAILABLE
                msg = f"Endpoint returned unexpected HTTP status {status_code}."
                self.last_warning = msg
                self.consecutive_failure_count += 1
                self._mark_all_vehicles_stale()
                self.last_fetch_mono = time.monotonic()
                logger.warning(
                    f"Upstream GTFS-RT fetch unexpected status: timestamp={start_wall}, status={status_code}, "
                    f"latency_ms={latency_ms:.1f}, error={msg}"
                )
                return FeedAvailabilityStatus.UNAVAILABLE, msg

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as conn_err:
                latency_ms = (time.monotonic() - start_mono) * 1000.0
                self.availability_status = FeedAvailabilityStatus.UNAVAILABLE
                msg = f"Connection timeout or endpoint unreachable: {conn_err.__class__.__name__}"
                self.last_warning = msg
                self.consecutive_failure_count += 1
                self._mark_all_vehicles_stale()
                self.last_fetch_mono = time.monotonic()
                logger.warning(
                    f"Upstream GTFS-RT fetch network error: timestamp={start_wall}, "
                    f"latency_ms={latency_ms:.1f}, error={msg}"
                )
                return FeedAvailabilityStatus.UNAVAILABLE, msg
            except Exception as generic_err:
                latency_ms = (time.monotonic() - start_mono) * 1000.0
                self.availability_status = FeedAvailabilityStatus.UNAVAILABLE
                msg = f"Unexpected error during feed probe: {generic_err}"
                self.last_warning = msg
                self.consecutive_failure_count += 1
                self._mark_all_vehicles_stale()
                self.last_fetch_mono = time.monotonic()
                logger.error(
                    f"Upstream GTFS-RT fetch error: timestamp={start_wall}, "
                    f"latency_ms={latency_ms:.1f}, error={msg}"
                )
                return FeedAvailabilityStatus.UNAVAILABLE, msg

    def check_feed_availability(
        self, timeout_seconds: float = 6.0, force: bool = False
    ) -> Tuple[FeedAvailabilityStatus, Optional[str]]:
        """Probe or refresh the live feed endpoint using thread-safe 20s caching."""
        return self.refresh_if_expired(timeout_seconds=timeout_seconds, force=force)

    def validate_and_filter_entities(
        self,
        feed_message: Any,
        reference_time_utc: Optional[int] = None,
    ) -> List[ValidatedVehiclePosition]:
        """Validate, deduplicate, and cross-reference vehicle positions from a parsed FeedMessage."""
        now_ts = reference_time_utc if reference_time_utc is not None else int(time.time())
        if not hasattr(feed_message, "entity"):
            return []

        seen_vehicles: Dict[str, ValidatedVehiclePosition] = {}
        duplicates = 0
        invalid_pos_count = 0

        for entity in feed_message.entity:
            if not entity.HasField("vehicle"):
                continue

            v = entity.vehicle
            vehicle_id = v.vehicle.id if v.HasField("vehicle") and v.vehicle.HasField("id") else entity.id
            if not vehicle_id:
                invalid_pos_count += 1
                continue

            notes: List[str] = []

            # 1. Coordinate Validation & Geographic Classification (Delhi Core vs NCR Corridor)
            lat = v.position.latitude if v.HasField("position") and v.position.HasField("latitude") else None
            lon = v.position.longitude if v.HasField("position") and v.position.HasField("longitude") else None

            is_valid_coords, is_out_of_area, area_class = classify_coordinates(lat, lon)
            if not is_valid_coords:
                invalid_pos_count += 1
                notes.append(f"Invalid coordinates ({lat}, {lon}) - classification: {area_class}.")
            elif is_out_of_area:
                notes.append(f"Interstate route in NCR corridor outside Delhi core: {area_class}.")

            # 2. Timestamp Validation & Staleness Check (with minor clock drift tolerance)
            ts = int(v.timestamp) if v.HasField("timestamp") else 0
            is_fresh = False
            if ts > 0:
                age_s = now_ts - ts
                if -120 <= age_s <= self.max_staleness_seconds:
                    is_fresh = True
                    if age_s < 0:
                        notes.append(f"Minor clock skew detected ({abs(age_s)}s in future, accepted).")
                elif age_s < -120:
                    notes.append(f"Excessive future timestamp detected (drift: {abs(age_s)}s).")
                else:
                    notes.append(f"Stale update ({age_s}s old > {self.max_staleness_seconds}s limit).")
            else:
                notes.append("Missing vehicle timestamp.")

            # 3. Static GTFS Cross-Referencing
            route_id = v.trip.route_id if v.HasField("trip") and v.trip.HasField("route_id") else None
            trip_id = v.trip.trip_id if v.HasField("trip") and v.trip.HasField("trip_id") else None

            is_matched = False
            if route_id and self.known_route_ids:
                is_matched = str(route_id) in self.known_route_ids
                if not is_matched:
                    notes.append(f"Route ID '{route_id}' not found in static GTFS routes.")

            bearing = v.position.bearing if v.HasField("position") and v.position.HasField("bearing") else None
            speed_ms = v.position.speed if v.HasField("position") and v.position.HasField("speed") else None
            speed_kmh = round(speed_ms * 3.6, 1) if speed_ms is not None and speed_ms >= 0 else None

            # Only retain vehicles with valid coordinates (Delhi core OR NCR corridor)
            if is_valid_coords and lat is not None and lon is not None:
                record = ValidatedVehiclePosition(
                    vehicle_id=str(vehicle_id),
                    route_id=str(route_id) if route_id else None,
                    trip_id=str(trip_id) if trip_id else None,
                    latitude=float(lat),
                    longitude=float(lon),
                    bearing=float(bearing) if bearing is not None else None,
                    speed_kmh=speed_kmh,
                    timestamp_utc=ts,
                    is_valid_coordinates=is_valid_coords,
                    is_fresh=is_fresh,
                    is_matched_to_gtfs=is_matched,
                    validation_notes=notes,
                    is_current=True,
                    is_out_of_area=is_out_of_area,
                    area_classification=area_class,
                )
                # Deduplication within the same snapshot: keep newest timestamp
                vid_str = str(vehicle_id)
                if vid_str in seen_vehicles:
                    duplicates += 1
                    if ts > seen_vehicles[vid_str].timestamp_utc:
                        seen_vehicles[vid_str] = record
                else:
                    seen_vehicles[vid_str] = record

        self.last_duplicate_count = duplicates
        self.last_invalid_position_count = invalid_pos_count
        self.last_fetch_mono = time.monotonic()

        # Update active and out_of_area mappings directly for backwards compatibility
        for rec in seen_vehicles.values():
            if rec.is_out_of_area:
                self.out_of_area_vehicles[rec.vehicle_id] = rec
            else:
                self.active_vehicles[rec.vehicle_id] = rec

        return list(seen_vehicles.values())

    def get_live_vehicles(
        self,
        route_id: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        radius_m: Optional[float] = None,
        limit: int = 5000,
        include_stale: bool = True,
        include_out_of_area: bool = True,
        now_ts: Optional[int] = None,
        return_summary: bool = False,
        min_lat: Optional[float] = None,
        max_lat: Optional[float] = None,
        min_lon: Optional[float] = None,
        max_lon: Optional[float] = None,
    ) -> Any:
        """Retrieve validated vehicle positions matching optional route, spatial proximity, and viewport bounding-box filters.
        
        Supports radius-based discovery around (lat, lon) with Haversine distance and/or viewport bounding box.
        If return_summary=True, returns (vehicles, summary_metadata_dict).
        """
        now_ts = now_ts if now_ts is not None else int(time.time())
        vehicles_out: List[Dict[str, Any]] = []

        route_id_str = str(route_id).strip() if route_id is not None else None
        has_coords = lat is not None and lon is not None
        has_bbox = min_lat is not None and max_lat is not None and min_lon is not None and max_lon is not None

        # Build combined candidate pool: active vehicles, out_of_area vehicles, and last_known vehicles
        pool: Dict[str, ValidatedVehiclePosition] = {}
        for vid, v in self.active_vehicles.items():
            pool[vid] = v

        if include_out_of_area:
            for vid, v in self.out_of_area_vehicles.items():
                if vid not in pool:
                    pool[vid] = v

        if include_stale:
            for vid, v in self.last_known_vehicles.items():
                if vid not in pool:
                    pool[vid] = v

        for v in pool.values():
            if route_id_str:
                if str(v.route_id or "").strip() != route_id_str:
                    continue

            # Viewport bounding-box filtering (with inversion safety)
            if has_bbox:
                bbox_min_lat = min(min_lat, max_lat)  # type: ignore[type-var]
                bbox_max_lat = max(min_lat, max_lat)  # type: ignore[type-var]
                bbox_min_lon = min(min_lon, max_lon)  # type: ignore[type-var]
                bbox_max_lon = max(min_lon, max_lon)  # type: ignore[type-var]
                if not (bbox_min_lat <= v.latitude <= bbox_max_lat and bbox_min_lon <= v.longitude <= bbox_max_lon):
                    continue

            age_s = max(0, now_ts - v.timestamp_utc) if v.timestamp_utc > 0 else 9999
            # Evict last-known records if beyond max staleness threshold
            if not v.is_current and age_s > self.max_staleness_seconds:
                continue

            dist_m: Optional[float] = None
            if has_coords:
                dist_m = haversine_distance_m(lat, lon, v.latitude, v.longitude)  # type: ignore[arg-type]
                if radius_m is not None and dist_m > radius_m:
                    continue

            is_fresh = (age_s <= self.max_staleness_seconds) and v.is_current

            vehicles_out.append({
                "vehicle_id": v.vehicle_id,
                "route_id": v.route_id,
                "trip_id": v.trip_id,
                "latitude": v.latitude,
                "longitude": v.longitude,
                "bearing": v.bearing,
                "speed_kmh": v.speed_kmh,
                "timestamp_utc": v.timestamp_utc,
                "age_seconds": age_s,
                "is_fresh": is_fresh,
                "is_current": v.is_current,
                "is_out_of_area": v.is_out_of_area,
                "area_classification": v.area_classification,
                "is_matched_to_gtfs": v.is_matched_to_gtfs,
                "agency": "UNKNOWN_MIXED",
                "distance_m": round(dist_m, 1) if dist_m is not None else None,
            })

        if has_coords:
            vehicles_out.sort(key=lambda item: item["distance_m"] if item["distance_m"] is not None else float("inf"))
        else:
            # Sort current vehicles first, then by youngest age
            vehicles_out.sort(key=lambda item: (not item["is_current"], item["age_seconds"]))

        summary = {
            "total_matching_count": len(vehicles_out),
            "current_matching_count": sum(1 for item in vehicles_out if item["is_current"]),
            "stale_matching_count": sum(1 for item in vehicles_out if not item["is_current"]),
            "search_lat": lat,
            "search_lon": lon,
            "search_radius_m": radius_m,
            "viewport_min_lat": min_lat,
            "viewport_max_lat": max_lat,
            "viewport_min_lon": min_lon,
            "viewport_max_lon": max_lon,
        }

        trimmed = vehicles_out[:limit]
        if return_summary:
            return trimmed, summary
        return trimmed

    def get_status_payload(self) -> Dict[str, Any]:
        """Generate structured status dictionary for API and audit reporting."""
        active_list = list(self.active_vehicles.values())
        out_of_area_list = list(self.out_of_area_vehicles.values())
        all_tracked = active_list + out_of_area_list + list(self.last_known_vehicles.values())

        valid_coords_count = len(active_list)
        stale_count = sum(1 for v in all_tracked if not v.is_fresh)
        unique_routes = {v.route_id for v in all_tracked if v.route_id}
        max_ts = max((v.timestamp_utc for v in all_tracked), default=0)
        latest_source_iso = (
            datetime.fromtimestamp(max_ts, timezone.utc).isoformat() if max_ts > 0 else None
        )

        error_category = None
        if self.availability_status == FeedAvailabilityStatus.AUTH_REQUIRED:
            error_category = "AUTH_ERROR"
        elif self.availability_status == FeedAvailabilityStatus.UNAVAILABLE:
            error_category = "NETWORK_ERROR"
        elif self.availability_status == FeedAvailabilityStatus.INVALID_DATA:
            error_category = "PARSE_ERROR"

        return {
            "feed_enabled": self.is_enabled and (self.availability_status == FeedAvailabilityStatus.AVAILABLE_VALIDATED),
            "feed_configured_enabled": self.is_enabled,
            "feed_availability_status": self.availability_status.value,
            "endpoint_url": self.endpoint_url,
            "auth_required": True,
            "auth_configured": bool(self.api_key and len(self.api_key.strip()) > 0),
            "poll_interval_seconds": self.poll_interval_seconds,
            "max_staleness_seconds": self.max_staleness_seconds,
            "last_attempt_timestamp_utc": self.last_attempt_timestamp_utc,
            "last_success_timestamp_utc": self.last_success_timestamp_utc,
            "latest_source_timestamp_utc": latest_source_iso,
            "consecutive_failure_count": self.consecutive_failure_count,
            "total_polls_count": self.total_polls_count,
            "total_success_count": self.total_success_count,
            "active_vehicles_count": len(self.active_vehicles),
            "current_vehicles_count": len(self.active_vehicles),
            "last_known_vehicles_count": len(self.last_known_vehicles),
            "out_of_area_count": len(self.out_of_area_vehicles),
            "duplicate_count": self.last_duplicate_count,
            "raw_entities_count": self.last_raw_entity_count,
            "valid_vehicles_count": valid_coords_count if self.active_vehicles else None,
            "valid_routes_count": len(unique_routes) if all_tracked else None,
            "stale_vehicles_count": stale_count if all_tracked else None,
            "feed_error_category": error_category,
            "agency_coverage": "UNKNOWN_MIXED",
            "warning": self.last_warning or (
                "Live feed verified: active real-time vehicle positions from Delhi Transport Stack. "
                "Agency attribution is UNKNOWN_MIXED (Cluster / DTC); static timetable expired 2024-01-01."
                if self.availability_status == FeedAvailabilityStatus.AVAILABLE_VALIDATED
                else "Delhi Transport Stack GTFS-RT feed requires individual x-api-key registration at "
                "https://delhi.transportstack.in. Live integration disabled; operating on historical models under DEGRADE status."
            ),
            "overall_operational_status": "DEGRADE",
        }

