import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
  CircleMarker,
  Tooltip,
  useMap,
  useMapEvents,
} from 'react-leaflet';
import L from 'leaflet';
import {
  AlertTriangle,
  Layers,
  ChevronDown,
  ChevronUp,
  Clock,
  Eye,
  EyeOff,
  Navigation,
  RotateCcw,
  Compass,
} from 'lucide-react';
import {
  Stop,
  JourneyAlternative,
  TransitLeg,
  WalkingLeg,
  OrderedStop,
  LiveVehicleItem,
  SuitableVehicleItem,
} from '../types/api';
import { apiService } from '../services/api';

// Center of Delhi
const DELHI_CENTER: [number, number] = [28.6139, 77.209];

export interface ViewportBounds {
  minLat: number;
  maxLat: number;
  minLon: number;
  maxLon: number;
}

// Custom DivIcons with smooth fade-in animation and DOM key stability
const createCustomIcon = (
  color: string,
  label: string,
  innerClass: string = '',
  size: number = 28,
  fontSize: number = 11
) =>
  L.divIcon({
    className: 'custom-map-marker',
    html: `
      <div class="${innerClass}" style="background-color: ${color}; width: ${size}px; height: ${size}px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 8px rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: ${fontSize}px; cursor: pointer;">
        ${label}
      </div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  });

const originIcon = createCustomIcon('#059669', 'A', '', 28, 11); // Emerald Green
const destIcon = createCustomIcon('#E11D48', 'B', '', 28, 11); // Rose Red
const boardIcon = createCustomIcon('#0D9488', '🚏', '', 28, 12); // Teal Boarding
const alightIcon = createCustomIcon('#D97706', '🏁', '', 28, 12); // Amber Alighting
const stopIcon = createCustomIcon('#0284C7', '•', '', 20, 10); // Sky Blue
const liveBusIcon = createCustomIcon('#EA580C', '🚌', 'bus-icon-inner', 30, 14); // High contrast orange
const suitableBusIcon = createCustomIcon('#D97706', '⭐', 'suitable-icon-inner', 34, 16); // Amber glowing star
const deadReckonedBusIcon = createCustomIcon('#B45309', '⚡', 'dead-reckoned-icon-inner', 32, 15); // Translucent dashed amber bolt
const staleBusIcon = createCustomIcon('#64748B', '🚌', 'bus-icon-inner', 28, 13); // Slate gray stale bus

const formatSecondsToTime = (seconds: number): string => {
  const s = Math.round(seconds) % 86400;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
};

const formatEpochToIST = (epochSec: number): string => {
  if (!epochSec || epochSec <= 0) return 'N/A';
  return new Date(epochSec * 1000).toLocaleTimeString('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

const findClosestShapeIndex = (
  coords: [number, number][],
  targetLat: number,
  targetLon: number
): number => {
  let minD = Infinity;
  let minIdx = 0;
  for (let i = 0; i < coords.length; i++) {
    const d = (coords[i][0] - targetLat) ** 2 + (coords[i][1] - targetLon) ** 2;
    if (d < minD) {
      minD = d;
      minIdx = i;
    }
  }
  return minIdx;
};

interface DelhiMapProps {
  originStop: Stop | null;
  destStop: Stop | null;
  originCoord: [number, number] | null;
  destCoord: [number, number] | null;
  selectedJourney: JourneyAlternative | null;
  nearbyStops: Stop[];
  onMapClick: (lat: number, lon: number) => void;
  onSelectStopAsOrigin: (stop: Stop) => void;
  onSelectStopAsDest: (stop: Stop) => void;
  focusPickupTrigger?: number;
}

// Map Click Handler Sub-component
function MapClickHandler({ onMapClick }: { onMapClick: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) {
      onMapClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

// Focus Controller to view ALL buses coming to pick you up at the boarding stop wherever they are
function MapPickupFocusController({
  focusTrigger,
  suitableVehicles,
  boardingCoord,
}: {
  focusTrigger: number;
  suitableVehicles: SuitableVehicleItem[];
  boardingCoord: [number, number] | null;
}) {
  const map = useMap();
  const lastTriggerRef = useRef<number>(0);

  useEffect(() => {
    if (focusTrigger > 0 && focusTrigger !== lastTriggerRef.current) {
      lastTriggerRef.current = focusTrigger;
      try {
        const points: [number, number][] = [];
        if (boardingCoord) {
          points.push(boardingCoord);
        }
        suitableVehicles.forEach((v) => {
          points.push([v.latitude, v.longitude]);
        });

        if (points.length >= 2) {
          const bounds = L.latLngBounds(points);
          if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [60, 60], maxZoom: 15 });
          }
        } else if (points.length === 1) {
          map.setView(points[0], 15);
        }
      } catch {
        // Safe catch
      }
    }
  }, [focusTrigger, suitableVehicles, boardingCoord, map]);

  return null;
}

// Auto-Fit Bounds Sub-component (fits bounds ONLY on selection change or explicit re-center trigger)
interface BoundsFitterProps {
  points: [number, number][];
  selectionId: string | null;
  forceFitTrigger?: number;
}

function BoundsFitter({ points, selectionId, forceFitTrigger }: BoundsFitterProps) {
  const map = useMap();
  const lastFittedSelectionRef = useRef<string | null>(null);
  const lastTriggerRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!selectionId || points.length < 2) return;
    if (lastFittedSelectionRef.current !== selectionId) {
      lastFittedSelectionRef.current = selectionId;
      try {
        const bounds = L.latLngBounds(points);
        if (bounds.isValid()) {
          map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
        }
      } catch {
        // Safe catch
      }
    }
  }, [selectionId, points, map]);

  useEffect(() => {
    if (forceFitTrigger !== undefined && forceFitTrigger !== lastTriggerRef.current) {
      lastTriggerRef.current = forceFitTrigger;
      if (forceFitTrigger > 0 && points.length >= 2) {
        try {
          const bounds = L.latLngBounds(points);
          if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
          }
        } catch {
          // Safe catch
        }
      }
    }
  }, [forceFitTrigger, points, map]);

  return null;
}

// Map Viewport and Movement Watcher Sub-component (tracks center, bounding box & zoom)
function MapViewportWatcher({
  onViewportChange,
}: {
  onViewportChange: (
    center: [number, number],
    bounds: ViewportBounds,
    zoom: number
  ) => void;
}) {
  const map = useMapEvents({
    moveend() {
      const center = map.getCenter();
      const b = map.getBounds();
      const zoom = map.getZoom();
      onViewportChange(
        [center.lat, center.lng],
        {
          minLat: b.getSouth(),
          maxLat: b.getNorth(),
          minLon: b.getWest(),
          maxLon: b.getEast(),
        },
        zoom
      );
    },
    zoomend() {
      const center = map.getCenter();
      const b = map.getBounds();
      const zoom = map.getZoom();
      onViewportChange(
        [center.lat, center.lng],
        {
          minLat: b.getSouth(),
          maxLat: b.getNorth(),
          minLon: b.getWest(),
          maxLon: b.getEast(),
        },
        zoom
      );
    },
  });
  return null;
}

export const DelhiMap: React.FC<DelhiMapProps> = ({
  originStop,
  destStop,
  originCoord,
  destCoord,
  selectedJourney,
  nearbyStops,
  onMapClick,
  onSelectStopAsOrigin,
  onSelectStopAsDest,
  focusPickupTrigger,
}) => {
  // Cache of route stops & shape coordinates by route_id
  const [routeStopsMap, setRouteStopsMap] = useState<Record<string, OrderedStop[]>>({});
  const [routeShapesMap, setRouteShapesMap] = useState<Record<string, [number, number][]>>({});

  // Trigger to focus map view on buses coming to pick you up
  const [localPickupFocusTrigger, setLocalPickupFocusTrigger] = useState<number>(0);
  const activePickupFocusTrigger = (focusPickupTrigger || 0) + localPickupFocusTrigger;

  // Layer visibility controls
  const [isLegendOpen, setIsLegendOpen] = useState(false);
  const [showNearbyStops, setShowNearbyStops] = useState(false);
  const [showLiveBuses, setShowLiveBuses] = useState(true);

  // When selectedJourney changes, fetch route detail for transit legs
  useEffect(() => {
    if (!selectedJourney) return;
    const transitLegs = selectedJourney.legs.filter((l): l is TransitLeg => l.leg_type === 'TRANSIT');
    transitLegs.forEach((tLeg) => {
      if (tLeg.route_id && !routeStopsMap[tLeg.route_id]) {
        apiService
          .getRouteDetail(tLeg.route_id)
          .then((detail) => {
            if (detail?.ordered_stops) {
              setRouteStopsMap((prev) => ({
                ...prev,
                [tLeg.route_id]: detail.ordered_stops,
              }));
            }
            if (detail?.has_shape_geometry && detail?.shape_coordinates && detail.shape_coordinates.length > 0) {
              setRouteShapesMap((prev) => ({
                ...prev,
                [tLeg.route_id]: detail.shape_coordinates as [number, number][],
              }));
            }
          })
          .catch(() => {
            // Silently fall back to endpoints
          });
      }
    });
  }, [selectedJourney, routeStopsMap]);

  // Collect points for auto-bounds fitting
  const fitPoints: [number, number][] = [];

  const originLatLon: [number, number] | null = originStop
    ? [originStop.lat, originStop.lon]
    : originCoord;
  const destLatLon: [number, number] | null = destStop
    ? [destStop.lat, destStop.lon]
    : destCoord;

  if (originLatLon) fitPoints.push(originLatLon);
  if (destLatLon) fitPoints.push(destLatLon);

  // Extract route IDs from selected journey to highlight relevant buses
  const selectedRouteIds = useMemo(() => {
    const ids = new Set<string>();
    if (selectedJourney) {
      for (const leg of selectedJourney.legs) {
        if (leg.leg_type === 'TRANSIT' && leg.route_id) {
          ids.add(String(leg.route_id));
        }
      }
    }
    return ids;
  }, [selectedJourney]);

  // Contextual first boarding stop resolution when a journey is selected
  const firstBoardingInfo = useMemo(() => {
    if (!selectedJourney) return null;
    const firstTransit = selectedJourney.legs.find((l): l is TransitLeg => l.leg_type === 'TRANSIT');
    if (!firstTransit) return null;
    const orderedStops = routeStopsMap[firstTransit.route_id];
    const bStop = orderedStops?.find((s) => String(s.stop_id) === String(firstTransit.board_stop_id));
    const bLat = bStop?.lat ?? originLatLon?.[0] ?? DELHI_CENTER[0];
    const bLon = bStop?.lon ?? originLatLon?.[1] ?? DELHI_CENTER[1];
    return {
      lat: bLat,
      lon: bLon,
      stopName: firstTransit.board_stop_name || bStop?.stop_name || 'Boarding Stop',
      stopId: firstTransit.board_stop_id,
      routeId: firstTransit.route_id,
    };
  }, [selectedJourney, routeStopsMap, originLatLon]);

  // First transit leg for journey-suitable bus matching
  const firstTransitLeg = useMemo(() => {
    if (!selectedJourney) return null;
    return selectedJourney.legs.find((l): l is TransitLeg => l.leg_type === 'TRANSIT') || null;
  }, [selectedJourney]);

  // Stable selection identifier to auto-fit bounds ONCE per user selection change without locking map
  const selectionId = useMemo(() => {
    if (selectedJourney) {
      return `journey-${selectedJourney.journey_id}`;
    }
    if (originLatLon && destLatLon) {
      return `od-${originLatLon[0].toFixed(5)},${originLatLon[1].toFixed(5)}-${destLatLon[0].toFixed(5)},${destLatLon[1].toFixed(5)}`;
    }
    if (originLatLon) {
      return `origin-${originLatLon[0].toFixed(5)},${originLatLon[1].toFixed(5)}`;
    }
    if (destLatLon) {
      return `dest-${destLatLon[0].toFixed(5)},${destLatLon[1].toFixed(5)}`;
    }
    return null;
  }, [selectedJourney, originLatLon, destLatLon]);

  // Force-fit trigger incremented on explicit "Center on Journey" / "Center on Origin" actions
  const [forceFitTrigger, setForceFitTrigger] = useState<number>(0);

  // Configurable search radius (default 2000m = 2km)
  const [searchRadiusM, setSearchRadiusM] = useState<number>(2000);
  const [mapCenterCoord, setMapCenterCoord] = useState<[number, number]>(DELHI_CENTER);
  const [viewportBounds, setViewportBounds] = useState<ViewportBounds | null>(null);
  const [userPannedAway, setUserPannedAway] = useState<boolean>(false);

  // Live GTFS-RT real-time nearby buses and metadata
  const [liveBuses, setLiveBuses] = useState<LiveVehicleItem[]>([]);
  const [liveBusMeta, setLiveBusMeta] = useState<{
    current: number;
    stale: number;
    total: number;
    radiusM: number;
  }>({ current: 0, stale: 0, total: 0, radiusM: 2000 });
  const [lastFeedPollTime, setLastFeedPollTime] = useState<string>('');

  // Verified suitable vehicles for selected journey
  const [suitableVehicles, setSuitableVehicles] = useState<SuitableVehicleItem[]>([]);
  const [suitableFallbackMsg, setSuitableFallbackMsg] = useState<string | null>(null);
  const [suitableDiagnosticDetail, setSuitableDiagnosticDetail] = useState<string | null>(null);
  const [showFleetInModeB, setShowFleetInModeB] = useState<boolean>(false);
  const [isLoadingSuitable, setIsLoadingSuitable] = useState<boolean>(false);

  // Request sequencing ref to reject out-of-order stale responses
  const requestIdRef = useRef<number>(0);

  // Reset panned status when selected journey or origin changes
  useEffect(() => {
    setUserPannedAway(false);
  }, [selectedJourney]);

  useEffect(() => {
    setUserPannedAway(false);
  }, [originLatLon?.[0], originLatLon?.[1]]);


  // Resolve active search center based on screen context
  const activeCenter = useMemo(() => {
    if (userPannedAway) {
      return {
        lat: mapCenterCoord[0],
        lon: mapCenterCoord[1],
        label: 'Map Center',
        mode: 'MAP_CENTER' as const,
      };
    }
    if (firstBoardingInfo) {
      return {
        lat: firstBoardingInfo.lat,
        lon: firstBoardingInfo.lon,
        label: `Boarding: ${firstBoardingInfo.stopName}`,
        mode: 'BOARDING_STOP' as const,
      };
    }
    if (originLatLon) {
      return {
        lat: originLatLon[0],
        lon: originLatLon[1],
        label: originStop ? `Origin: ${originStop.stop_name}` : 'Origin Location',
        mode: 'ORIGIN' as const,
      };
    }
    return {
      lat: mapCenterCoord[0],
      lon: mapCenterCoord[1],
      label: 'Map Center',
      mode: 'MAP_CENTER' as const,
    };
  }, [userPannedAway, mapCenterCoord, firstBoardingInfo, originLatLon, originStop]);

  // Fetch verified suitable buses for the active transit leg
  const fetchSuitableBuses = useCallback(
    async (routeId: string, boardStopId: string, alightStopId: string) => {
      try {
        setIsLoadingSuitable(true);
        const res = await apiService.getSuitableVehicles(routeId, boardStopId, alightStopId);
        if (res?.vehicles) {
          setSuitableVehicles(res.vehicles);
          setSuitableFallbackMsg(res.fallback_message || null);
          setSuitableDiagnosticDetail(res.diagnostic_detail || null);
          setLastFeedPollTime(new Date().toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false }));
        }
      } catch {
        // Silently ignore network errors
      } finally {
        setIsLoadingSuitable(false);
      }
    },
    []
  );

  // Polling effect for journey-suitable buses (immediate on selection, 15s refresh with dead reckoning)
  useEffect(() => {
    if (!firstTransitLeg) {
      setSuitableVehicles([]);
      setSuitableFallbackMsg(null);
      setSuitableDiagnosticDetail(null);
      return;
    }
    let isCancelled = false;
    const doFetch = () => {
      if (!isCancelled && firstTransitLeg) {
        fetchSuitableBuses(firstTransitLeg.route_id, firstTransitLeg.board_stop_id, firstTransitLeg.alight_stop_id);
      }
    };
    doFetch();
    const interval = setInterval(doFetch, 15000);
    return () => {
      isCancelled = true;
      clearInterval(interval);
    };
  }, [
    firstTransitLeg?.route_id,
    firstTransitLeg?.board_stop_id,
    firstTransitLeg?.alight_stop_id,
    fetchSuitableBuses,
  ]);

  // Nearby bus fetch with radius and viewport bounding-box filtering
  const fetchNearbyBuses = useCallback(
    async (lat: number, lon: number, radiusM: number, bounds: ViewportBounds | null) => {
      const currentReqId = ++requestIdRef.current;
      try {
        // Expand radius to cover visible viewport when zoomed out
        let effectiveRadiusM = radiusM;
        if (bounds) {
          const latSpanM = Math.abs(bounds.maxLat - bounds.minLat) * 111000;
          const lonSpanM = Math.abs(bounds.maxLon - bounds.minLon) * 111000 * Math.cos((lat * Math.PI) / 180);
          const viewportRadiusM = Math.round(Math.hypot(latSpanM, lonSpanM) / 2);
          effectiveRadiusM = Math.min(50000, Math.max(radiusM, viewportRadiusM));
        }

        const res = await apiService.getLiveVehicles(
          undefined,
          500,
          lat,
          lon,
          effectiveRadiusM,
          true,
          true,
          undefined,
          bounds?.minLat,
          bounds?.maxLat,
          bounds?.minLon,
          bounds?.maxLon
        );
        if (currentReqId !== requestIdRef.current) return;

        if (res?.vehicles) {
          // If bounds were supplied, vehicles are bounded by the viewport
          // If no bounds were supplied (initial load / unit test), filter by search radius
          const filtered = bounds
            ? res.vehicles
            : res.vehicles.filter((v) =>
                v.distance_m !== undefined && v.distance_m !== null ? v.distance_m <= radiusM : true
              );
          setLiveBuses(filtered);

          const currentCount = res.current_matching_count ?? filtered.filter((v) => v.is_current !== false).length;
          const staleCount = res.stale_matching_count ?? filtered.filter((v) => v.is_current === false).length;
          setLiveBusMeta({
            current: currentCount,
            stale: staleCount,
            total: res.total_matching_count ?? filtered.length,
            radiusM: res.search_radius_m ?? effectiveRadiusM,
          });
          setLastFeedPollTime(new Date().toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false }));
        }
      } catch {
        // Silently ignore aborted or network failure
      }
    },
    []
  );

  // Map viewport change handler (tracks pan & zoom without locking map)
  const handleMapViewportChange = useCallback(
    (center: [number, number], bounds: ViewportBounds) => {
      setMapCenterCoord(center);
      setUserPannedAway(true);
      setViewportBounds(bounds);
    },
    []
  );

  // Re-center on contextual anchor (boarding stop or origin) or journey
  const handleRecenterContext = useCallback(() => {
    setUserPannedAway(false);
    setForceFitTrigger((prev) => prev + 1);
    if (firstBoardingInfo) {
      setMapCenterCoord([firstBoardingInfo.lat, firstBoardingInfo.lon]);
    } else if (originLatLon) {
      setMapCenterCoord(originLatLon);
    } else {
      setMapCenterCoord(DELHI_CENTER);
    }
  }, [firstBoardingInfo, originLatLon]);

  // Polling effect for fleet buses: active in Mode A, or when explicitly toggled in Mode B
  useEffect(() => {
    // Mode B active: hide fleet buses unless showFleetInModeB is true
    if (selectedJourney && firstTransitLeg && !showFleetInModeB) {
      setLiveBuses([]);
      return;
    }

    let isCancelled = false;
    const delay = userPannedAway ? 500 : 0;
    const timer = setTimeout(() => {
      if (!isCancelled) {
        fetchNearbyBuses(activeCenter.lat, activeCenter.lon, searchRadiusM, viewportBounds);
      }
    }, delay);

    const interval = setInterval(() => {
      if (!isCancelled) {
        fetchNearbyBuses(activeCenter.lat, activeCenter.lon, searchRadiusM, viewportBounds);
      }
    }, 20000);

    return () => {
      isCancelled = true;
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, [activeCenter.lat, activeCenter.lon, searchRadiusM, viewportBounds, userPannedAway, fetchNearbyBuses, selectedJourney, firstTransitLeg, showFleetInModeB]);

  // Extract structured geometries and distinct markers
  interface TransitPolylineItem {
    coords: [number, number][];
    label: string;
    intermediateCount: number;
    hasShape: boolean;
    routeId: string;
  }
  interface WalkingPolylineItem {
    coords: [number, number][];
    label: string;
  }
  interface BoardAlightMarkerItem {
    type: 'BOARD' | 'ALIGHT';
    stopId: string;
    stopName: string;
    lat: number;
    lon: number;
    timeS: number;
    routeId: string;
  }
  interface IntermediateMarkerItem {
    lat: number;
    lon: number;
    name: string;
    stopId: string;
  }

  const transitPolylines: TransitPolylineItem[] = [];
  const walkingPolylines: WalkingPolylineItem[] = [];
  const boardAlightMarkers: BoardAlightMarkerItem[] = [];
  const intermediateMarkers: IntermediateMarkerItem[] = [];

  if (selectedJourney) {
    // First, resolve transit leg endpoints
    const transitEndpoints: {
      legIdx: number;
      boardStopId: string;
      boardStopName: string;
      boardLat: number;
      boardLon: number;
      alightStopId: string;
      alightStopName: string;
      alightLat: number;
      alightLon: number;
      routeId: string;
      schedDepartureS: number;
      schedArrivalS: number;
    }[] = [];

    selectedJourney.legs.forEach((leg, legIdx) => {
      if (leg.leg_type === 'TRANSIT') {
        const tLeg = leg as TransitLeg;
        const orderedStops = routeStopsMap[tLeg.route_id];
        const bStop = orderedStops?.find((s) => String(s.stop_id) === String(tLeg.board_stop_id));
        const aStop = orderedStops?.find((s) => String(s.stop_id) === String(tLeg.alight_stop_id));

        const bLat = bStop?.lat ?? originLatLon?.[0] ?? DELHI_CENTER[0];
        const bLon = bStop?.lon ?? originLatLon?.[1] ?? DELHI_CENTER[1];
        const aLat = aStop?.lat ?? destLatLon?.[0] ?? DELHI_CENTER[0];
        const aLon = aStop?.lon ?? destLatLon?.[1] ?? DELHI_CENTER[1];

        transitEndpoints.push({
          legIdx,
          boardStopId: tLeg.board_stop_id,
          boardStopName: tLeg.board_stop_name,
          boardLat: bLat,
          boardLon: bLon,
          alightStopId: tLeg.alight_stop_id,
          alightStopName: tLeg.alight_stop_name,
          alightLat: aLat,
          alightLon: aLon,
          routeId: tLeg.route_id,
          schedDepartureS: tLeg.sched_departure_s || tLeg.board_time_s,
          schedArrivalS: tLeg.sched_arrival_s || tLeg.alight_time_s,
        });

        // Add distinct boarding & alighting markers for this transit leg
        boardAlightMarkers.push({
          type: 'BOARD',
          stopId: tLeg.board_stop_id,
          stopName: tLeg.board_stop_name,
          lat: bLat,
          lon: bLon,
          timeS: tLeg.sched_departure_s || tLeg.board_time_s,
          routeId: tLeg.route_id,
        });
        boardAlightMarkers.push({
          type: 'ALIGHT',
          stopId: tLeg.alight_stop_id,
          stopName: tLeg.alight_stop_name,
          lat: aLat,
          lon: aLon,
          timeS: tLeg.sched_arrival_s || tLeg.alight_time_s,
          routeId: tLeg.route_id,
        });
        fitPoints.push([bLat, bLon], [aLat, aLon]);

        // Sliced shape geometry or sliced ordered stops
        const shapeCoords = routeShapesMap[tLeg.route_id];
        const hasTrueShape = Boolean(shapeCoords && shapeCoords.length > 1);
        let legPoints: [number, number][] = [];

        if (hasTrueShape && shapeCoords) {
          const bShapeIdx = findClosestShapeIndex(shapeCoords, bLat, bLon);
          const aShapeIdx = findClosestShapeIndex(shapeCoords, aLat, aLon);

          if (bShapeIdx <= aShapeIdx) {
            legPoints = shapeCoords.slice(bShapeIdx, aShapeIdx + 1);
          } else {
            legPoints = shapeCoords.slice(aShapeIdx, bShapeIdx + 1).reverse();
          }

          // Intermediate stops along this sliced segment only
          if (orderedStops && orderedStops.length > 0) {
            const bIdx = orderedStops.findIndex((s) => String(s.stop_id) === String(tLeg.board_stop_id));
            const aIdx = orderedStops.findIndex((s) => String(s.stop_id) === String(tLeg.alight_stop_id));
            if (bIdx !== -1 && aIdx !== -1 && bIdx < aIdx) {
              orderedStops.slice(bIdx + 1, aIdx).forEach((s) => {
                intermediateMarkers.push({
                  lat: s.lat,
                  lon: s.lon,
                  name: s.stop_name,
                  stopId: s.stop_id,
                });
              });
            }
          }
        } else if (orderedStops && orderedStops.length > 0) {
          const bIdx = orderedStops.findIndex((s) => String(s.stop_id) === String(tLeg.board_stop_id));
          const aIdx = orderedStops.findIndex((s) => String(s.stop_id) === String(tLeg.alight_stop_id));

          if (bIdx !== -1 && aIdx !== -1 && bIdx <= aIdx) {
            const subStops = orderedStops.slice(bIdx, aIdx + 1);
            legPoints = subStops.map((s) => [s.lat, s.lon]);
            subStops.slice(1, -1).forEach((s) => {
              intermediateMarkers.push({
                lat: s.lat,
                lon: s.lon,
                name: s.stop_name,
                stopId: s.stop_id,
              });
            });
          }
        }

        // Fallback to direct board->alight segment
        if (legPoints.length < 2) {
          legPoints = [[bLat, bLon], [aLat, aLon]];
        }

        if (legPoints.length >= 2) {
          transitPolylines.push({
            coords: legPoints,
            label: `Route ${tLeg.route_id}: ${tLeg.board_stop_name} → ${tLeg.alight_stop_name}`,
            intermediateCount: Math.max(0, legPoints.length - 2),
            hasShape: hasTrueShape,
            routeId: tLeg.route_id,
          });
          legPoints.forEach((pt) => fitPoints.push(pt));
        }
      }
    });

    // Second, resolve walking legs without spurious diagonal lines
    selectedJourney.legs.forEach((leg, legIdx) => {
      if (leg.leg_type !== 'TRANSIT') {
        const wLeg = leg as WalkingLeg;
        let walkStart: [number, number] | null = null;
        let walkEnd: [number, number] | null = null;

        if (wLeg.leg_type === 'ACCESS') {
          walkStart = originLatLon;
          if (transitEndpoints.length > 0) {
            walkEnd = [transitEndpoints[0].boardLat, transitEndpoints[0].boardLon];
          }
        } else if (wLeg.leg_type === 'EGRESS') {
          if (transitEndpoints.length > 0) {
            const lastTransit = transitEndpoints[transitEndpoints.length - 1];
            walkStart = [lastTransit.alightLat, lastTransit.alightLon];
          }
          walkEnd = destLatLon;
        } else if (wLeg.leg_type === 'TRANSFER') {
          const prevTransit = transitEndpoints.filter((t) => t.legIdx < legIdx).pop();
          const nextTransit = transitEndpoints.find((t) => t.legIdx > legIdx);
          if (prevTransit && nextTransit) {
            walkStart = [prevTransit.alightLat, prevTransit.alightLon];
            walkEnd = [nextTransit.boardLat, nextTransit.boardLon];
          }
        } else if (wLeg.leg_type === 'DIRECT_WALK') {
          walkStart = originLatLon;
          walkEnd = destLatLon;
        }

        if (walkStart && walkEnd) {
          walkingPolylines.push({
            coords: [walkStart, walkEnd],
            label: `${wLeg.leg_type}: ${wLeg.from_name} → ${wLeg.to_name} (~${Math.round(wLeg.distance_m)}m)`,
          });
          fitPoints.push(walkStart, walkEnd);
        }
      }
    });
  }

  const anyTrueShape = transitPolylines.some((p) => p.hasShape);

  return (
    <div className="relative w-full h-full min-h-[460px] overflow-hidden bg-slate-100">
      {/* Sleek Floating Top Controls Bar (Transit App aesthetic) */}
      <div className="absolute top-3 left-3 right-3 z-[400] flex flex-wrap items-center justify-between gap-2 pointer-events-none">
        {/* Left Status & Discovery Pill */}
        <div className="flex items-center space-x-2 flex-wrap gap-1 pointer-events-auto">
          {selectedJourney && firstTransitLeg ? (
            /* Mode B (Journey Selected) */
            <div className="flex items-center space-x-1.5 flex-wrap gap-1">
              <div className="flex items-center bg-white/95 backdrop-blur-md px-3 py-1.5 rounded-xl border border-blue-200 shadow-md space-x-2 text-xs text-slate-800">
                <span className="bg-blue-600 text-white font-extrabold text-[10px] px-1.5 py-0.5 rounded-md">
                  Route {firstTransitLeg.route_id}
                </span>
                <span className="font-semibold text-slate-800 truncate max-w-[180px]">
                  &rarr; {firstTransitLeg.alight_stop_name}
                </span>
                <span className="text-[10px] bg-blue-50 text-blue-800 px-1.5 py-0.5 rounded-md font-bold border border-blue-200">
                  {suitableVehicles.length} verified
                </span>
                <span className="text-[10px] bg-emerald-50 text-emerald-800 px-1.5 py-0.5 rounded-md font-medium border border-emerald-200">
                  15s cadence
                </span>
              </div>

              {userPannedAway && (
                <button
                  type="button"
                  onClick={handleRecenterContext}
                  className="px-2.5 py-1.5 bg-white/95 hover:bg-blue-50 text-blue-700 border border-blue-300 rounded-xl text-xs font-semibold flex items-center space-x-1 shadow-md transition-colors pointer-events-auto"
                  title="Re-center map on selected journey"
                >
                  <RotateCcw className="w-3.5 h-3.5 text-blue-600" />
                  <span>Center on Journey</span>
                </button>
              )}
            </div>
          ) : (
            /* Mode A (Free Exploration) */
            <div className="flex items-center bg-white/95 backdrop-blur-md px-2.5 py-1.5 rounded-xl border border-slate-200 shadow-md space-x-2 text-xs">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center space-x-0.5">
                <Navigation className="w-3 h-3 text-blue-600" />
                <span>Radius:</span>
              </span>
              <div className="flex items-center space-x-1">
                {[500, 1000, 2000, 5000].map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setSearchRadiusM(r)}
                    className={`px-2 py-0.5 rounded-lg text-[11px] font-semibold transition-colors ${
                      searchRadiusM === r
                        ? 'bg-blue-600 text-white shadow-xs'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                    title={`Discover buses within ${r < 1000 ? `${r}m` : `${r / 1000}km`}`}
                  >
                    {r < 1000 ? `${r}m` : `${r / 1000}km`}
                  </button>
                ))}
              </div>

              <div className="h-3 w-[1px] bg-slate-200" />

              <span className="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-800 font-bold text-[10px]">
                ● {liveBusMeta.current} Live
              </span>
              <span className="px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-600 font-medium text-[10px]">
                ○ {liveBusMeta.stale} Stale
              </span>

              {userPannedAway && (firstBoardingInfo || originLatLon) && (
                <button
                  type="button"
                  onClick={handleRecenterContext}
                  className="ml-1 px-2 py-0.5 bg-blue-50 hover:bg-blue-100 text-blue-800 border border-blue-200 rounded-lg text-[10px] font-semibold flex items-center space-x-1 transition-colors pointer-events-auto"
                >
                  <RotateCcw className="w-3 h-3 text-blue-600" />
                  <span>Center on {firstBoardingInfo ? 'Boarding Stop' : 'Origin'}</span>
                </button>
              )}
            </div>
          )}
        </div>

        {/* Right Layer Toggles */}
        <div className="flex items-center space-x-1.5 pointer-events-auto">
          {selectedJourney && firstTransitLeg ? (
            <>
              {/* PRIMARY PROMINENT BUTTON: See Buses Coming to Pick You Up */}
              <button
                type="button"
                onClick={() => {
                  setShowLiveBuses(true);
                  setLocalPickupFocusTrigger((prev) => prev + 1);
                }}
                className="px-3.5 py-1.5 rounded-xl text-xs font-bold border shadow-md flex items-center space-x-1.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white border-blue-500 active:scale-[0.98] transition-all cursor-pointer"
                title="Locate and zoom to all buses approaching to pick you up at your boarding stop"
              >
                <Compass className="w-3.5 h-3.5 text-amber-300 animate-pulse" />
                <span>See Buses Coming to Pick You Up ({suitableVehicles.length})</span>
              </button>

              <button
                type="button"
                onClick={() => setShowLiveBuses(!showLiveBuses)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold border shadow-md flex items-center space-x-1.5 transition-colors ${
                  showLiveBuses
                    ? 'bg-blue-50 text-blue-800 border-blue-200'
                    : 'bg-white/95 text-slate-600 border-slate-200 hover:bg-slate-50'
                }`}
                title="Toggle Verified Journey Buses"
              >
                <span>⭐ Verified ({suitableVehicles.length})</span>
              </button>
              <button
                type="button"
                onClick={() => setShowFleetInModeB(!showFleetInModeB)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold border shadow-md flex items-center space-x-1.5 transition-colors ${
                  showFleetInModeB
                    ? 'bg-amber-600 text-white border-amber-600'
                    : 'bg-white/95 text-slate-600 border-slate-200 hover:bg-slate-50'
                }`}
                title="Toggle Nearby Fleet Buses overlay on map"
              >
                <span>🚌 Fleet ({liveBuses.length})</span>
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setShowLiveBuses(!showLiveBuses)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold border shadow-md flex items-center space-x-1.5 transition-colors ${
                showLiveBuses
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white/95 text-slate-600 border-slate-200 hover:bg-slate-50'
              }`}
              title="Toggle Live GTFS-RT moving buses display"
            >
              <span>🚌 Buses ({liveBuses.length})</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowNearbyStops(!showNearbyStops)}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold border shadow-md flex items-center space-x-1.5 transition-colors ${
              showNearbyStops
                ? 'bg-slate-800 text-white border-slate-800'
                : 'bg-white/95 text-slate-600 border-slate-200 hover:bg-slate-50'
            }`}
            title="Toggle Nearby Bus Stops markers"
          >
            <span>🚏 Stops ({nearbyStops.length})</span>
          </button>
        </div>
      </div>

      {/* Floating Status / Fallback Notice Banners */}
      {showLiveBuses && selectedJourney && firstTransitLeg && suitableVehicles.length > 0 && (
        <div className="absolute top-16 left-3 right-3 sm:left-auto sm:right-3 z-[400] bg-blue-50/95 backdrop-blur-md border border-blue-200 text-blue-900 px-3.5 py-2 rounded-xl text-xs shadow-md flex items-center justify-between pointer-events-auto max-w-md">
          <div className="flex items-center space-x-1.5 truncate">
            <span className="text-blue-600 font-bold text-xs">⭐</span>
            <span className="font-semibold text-xs truncate">
              Showing {suitableVehicles.length} verified live bus{suitableVehicles.length > 1 ? 'es' : ''} for Route {firstTransitLeg.route_id} heading to {firstTransitLeg.alight_stop_name}
            </span>
          </div>
          <span className="text-[10px] text-blue-800 bg-blue-100 px-2 py-0.5 rounded-md font-medium shrink-0 ml-2">
            15s updates
          </span>
        </div>
      )}

      {showLiveBuses && selectedJourney && firstTransitLeg && suitableVehicles.length === 0 && !isLoadingSuitable && (
        <div className="absolute top-16 left-3 right-3 sm:left-auto sm:right-3 z-[400] bg-amber-50/95 backdrop-blur-md border border-amber-300 text-amber-900 px-3.5 py-2.5 rounded-xl text-xs shadow-md flex flex-col space-y-1.5 pointer-events-auto max-w-md">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span className="font-semibold text-xs">
              No verified live bus is currently available for this journey.
            </span>
          </div>
          {suitableDiagnosticDetail && (
            <div className="text-[11px] text-amber-800 font-normal pl-6">
              {suitableDiagnosticDetail}
            </div>
          )}
          <div className="pl-6 pt-0.5 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowFleetInModeB(!showFleetInModeB)}
              className="text-[11px] font-semibold text-blue-700 bg-white hover:bg-blue-50 border border-blue-200 px-2 py-0.5 rounded shadow-xs transition-colors"
            >
              {showFleetInModeB ? 'Hide Fleet Buses' : 'Show All Nearby Buses on Map'}
            </button>
          </div>
        </div>
      )}

      {showLiveBuses && (!selectedJourney || !firstTransitLeg) && liveBuses.length === 0 && (
        <div className="absolute top-16 left-3 right-3 sm:left-auto sm:right-3 z-[400] bg-slate-50/95 backdrop-blur-md border border-slate-300 text-slate-700 px-3.5 py-2 rounded-xl text-xs shadow-md flex items-center space-x-2 pointer-events-auto max-w-xs">
          <AlertTriangle className="w-4 h-4 text-slate-500 shrink-0" />
          <span className="font-medium text-xs">No live buses in this area</span>
        </div>
      )}

      {/* Unobtrusive Bottom-Right Road Geometry Badge */}
      <div className="absolute bottom-3 right-3 z-[400] pointer-events-auto">
        <span
          className={`px-2.5 py-1 rounded-xl text-[10px] font-medium border shadow-xs backdrop-blur-md flex items-center space-x-1 ${
            anyTrueShape
              ? 'bg-white/90 text-emerald-800 border-emerald-200'
              : 'bg-white/90 text-amber-800 border-amber-200'
          }`}
          title={
            anyTrueShape
              ? 'Rendered using road centerline coordinates from GTFS shapes.txt'
              : 'Connecting stops via straight segments'
          }
        >
          <span>{anyTrueShape ? '🛣️ True Road Geometry' : '📐 Straight Segments'}</span>
        </span>
      </div>

      <MapContainer
        center={DELHI_CENTER}
        zoom={11}
        scrollWheelZoom={true}
        className="w-full h-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapClickHandler onMapClick={onMapClick} />
        <MapViewportWatcher onViewportChange={handleMapViewportChange} />
        <BoundsFitter points={fitPoints} selectionId={selectionId} forceFitTrigger={forceFitTrigger} />
        <MapPickupFocusController
          focusTrigger={activePickupFocusTrigger}
          suitableVehicles={suitableVehicles}
          boardingCoord={firstBoardingInfo ? [firstBoardingInfo.lat, firstBoardingInfo.lon] : originLatLon}
        />

        {/* Origin Marker */}
        {originLatLon && (
          <Marker position={originLatLon} icon={originIcon}>
            <Popup>
              <div className="text-xs space-y-1">
                <span className="font-bold text-emerald-800">Origin Point (A)</span>
                <p className="font-medium text-slate-800">
                  {originStop ? originStop.stop_name : 'Selected Departure Location'}
                </p>
                <p className="text-slate-400 font-mono text-[10px]">
                  {originLatLon[0].toFixed(4)}, {originLatLon[1].toFixed(4)}
                </p>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Destination Marker */}
        {destLatLon && (
          <Marker position={destLatLon} icon={destIcon}>
            <Popup>
              <div className="text-xs space-y-1">
                <span className="font-bold text-rose-800">Destination Point (B)</span>
                <p className="font-medium text-slate-800">
                  {destStop ? destStop.stop_name : 'Selected Destination Location'}
                </p>
                <p className="text-slate-400 font-mono text-[10px]">
                  {destLatLon[0].toFixed(4)}, {destLatLon[1].toFixed(4)}
                </p>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Dedicated Boarding & Alighting Markers */}
        {boardAlightMarkers.map((bam, idx) => (
          <Marker
            key={`bam-${idx}-${bam.stopId}`}
            position={[bam.lat, bam.lon]}
            icon={bam.type === 'BOARD' ? boardIcon : alightIcon}
          >
            <Popup>
              <div className="text-xs space-y-1 p-0.5">
                <div className="flex items-center space-x-1.5 font-bold">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] text-white ${
                      bam.type === 'BOARD' ? 'bg-teal-700' : 'bg-amber-700'
                    }`}
                  >
                    {bam.type === 'BOARD' ? 'BOARD BUS' : 'ALIGHT BUS'}
                  </span>
                  <span className="text-slate-800">Route {bam.routeId}</span>
                </div>
                <div className="font-semibold text-slate-900">{bam.stopName}</div>
                <div className="text-slate-500 text-[11px]">
                  Stop ID: <span className="font-mono">{bam.stopId}</span>
                </div>
                <div className="text-slate-600 flex items-center space-x-1 text-[11px] pt-1 border-t border-slate-100">
                  <Clock className="w-3 h-3 text-slate-400" />
                  <span>Scheduled: {formatSecondsToTime(bam.timeS)} IST</span>
                </div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Intermediate Stop Markers */}
        {intermediateMarkers.map((im, idx) => (
          <CircleMarker
            key={`im-${idx}`}
            center={[im.lat, im.lon]}
            radius={3.5}
            pathOptions={{ color: '#0F766E', fillColor: '#14B8A6', fillOpacity: 0.9, weight: 1.5 }}
          >
            <Popup>
              <div className="text-xs">
                <span className="font-semibold text-slate-800">Intermediate Stop:</span> {im.name}
                <div className="text-slate-500 font-mono text-[10px]">ID: {im.stopId}</div>
              </div>
            </Popup>
          </CircleMarker>
        ))}

        {/* Nearby / Discovered Stops Markers (Only if layer toggled on) */}
        {showNearbyStops &&
          nearbyStops.map((stop) => (
            <Marker
              key={stop.stop_id}
              position={[stop.lat, stop.lon]}
              icon={stopIcon}
            >
              <Popup>
                <div className="text-xs space-y-1.5 p-1">
                  <div className="font-bold text-slate-900">{stop.stop_name}</div>
                  <div className="text-slate-500 font-mono">Stop ID: {stop.stop_id}</div>
                  {stop.distance_m !== undefined && (
                    <div className="text-slate-500">
                      Distance: {Math.round(stop.distance_m)}m (~{Math.round((stop.walking_time_s || 0) / 60)} min walk)
                    </div>
                  )}
                  <div className="flex space-x-2 pt-1 border-t border-slate-100">
                    <button
                      type="button"
                      onClick={() => onSelectStopAsOrigin(stop)}
                      className="px-2 py-0.5 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded text-[11px] font-medium"
                    >
                      Set Origin
                    </button>
                    <button
                      type="button"
                      onClick={() => onSelectStopAsDest(stop)}
                      className="px-2 py-0.5 bg-rose-50 text-rose-700 hover:bg-rose-100 rounded text-[11px] font-medium"
                    >
                      Set Dest
                    </button>
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}

        {/* 1. IN MODE B (JOURNEY-SELECTED MODE): Render ONLY verified suitable buses (Live GPS or Dead Reckoned) */}
        {showLiveBuses && selectedJourney && firstTransitLeg &&
          suitableVehicles.map((bus) => {
            const isDeadReckoned = bus.is_dead_reckoned || bus.position_source === 'DEAD_RECKONED';
            const isUnverified = !bus.is_verified_suitable || bus.progress_status === 'UNVERIFIED_STALE';
            const icon = isUnverified ? staleBusIcon : isDeadReckoned ? deadReckonedBusIcon : suitableBusIcon;

            return (
              <Marker
                key={`suitable-${bus.vehicle_id}`}
                position={[bus.latitude, bus.longitude]}
                icon={icon}
              >
                <Tooltip permanent direction="top" offset={[0, -22]} className="pickup-bus-tooltip">
                  <span className="font-bold text-[10px] bg-blue-700 text-white px-2 py-0.5 rounded-md shadow-md border border-blue-400 flex items-center space-x-1">
                    <span>🚌 Pickup Bus</span>
                    <span>•</span>
                    <span>
                      {bus.distance_to_board_m !== undefined && bus.distance_to_board_m !== null
                        ? bus.distance_to_board_m < 1000
                          ? `${Math.round(bus.distance_to_board_m)}m to boarding`
                          : `${(bus.distance_to_board_m / 1000).toFixed(1)}km to boarding`
                        : 'Approaching'}
                    </span>
                  </span>
                </Tooltip>
                <Popup>
                  <div className="text-xs space-y-2 p-1.5 max-w-[280px]">
                    <div className="flex items-center justify-between border-b pb-1.5 border-slate-100">
                      <span className="font-bold text-slate-900 font-mono text-[13px]">{bus.vehicle_id}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-md font-bold bg-blue-600 text-white shadow-xs">
                        Route {bus.route_id}
                      </span>
                    </div>

                    {bus.is_verified_suitable ? (
                      <div className="bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg px-2 py-1 text-[11px] font-semibold flex items-center space-x-1">
                        <span>✓ Verified to reach {firstTransitLeg.alight_stop_name}</span>
                      </div>
                    ) : (
                      <div className="bg-rose-50 text-rose-800 border border-rose-200 rounded-lg px-2 py-1 text-[11px] font-semibold flex items-center space-x-1">
                        <span>⚠️ Stale / Unverified Telemetry — Position Frozen</span>
                      </div>
                    )}

                    <div className="text-slate-700 space-y-1 text-[11px]">
                      <div className="text-[11px] text-blue-900 font-semibold bg-blue-50/80 px-2 py-1 rounded-lg border border-blue-100">
                        📍 {Math.round(bus.distance_to_board_m)}m to boarding stop ({firstTransitLeg.board_stop_name})
                      </div>
                      <div>
                        <strong>Destination:</strong> {bus.trip_headsign || firstTransitLeg.alight_stop_name || 'Towards Destination'}
                      </div>
                      <div>
                        <strong>Status:</strong>{' '}
                        <span className={`font-semibold ${bus.is_verified_suitable ? 'text-blue-700' : 'text-rose-700'}`}>
                          {bus.progress_status === 'NEAR_BOARDING_STOP'
                            ? '🚏 Near Boarding Stop (<400m)'
                            : bus.progress_status === 'APPROACHING'
                            ? '🚌 Approaching Stop'
                            : '⚠️ Stale / Position Frozen'}
                        </span>
                      </div>
                      <div>
                        <strong>Speed:</strong> {bus.speed_kmh !== null && bus.speed_kmh !== undefined ? `${bus.speed_kmh} km/h` : 'Stationary / N/A'}
                      </div>
                    </div>

                    <div className="text-[11px] text-amber-900 bg-amber-50/90 p-2 rounded-lg border border-amber-200 leading-tight">
                      {bus.guidance_message}
                    </div>

                    {/* Collapsible Advanced Telemetry & Dead Reckoning Details */}
                    <div className="pt-1.5 border-t border-slate-100">
                      <details className="group">
                        <summary className="text-[10px] font-semibold text-slate-400 hover:text-slate-700 cursor-pointer list-none flex items-center justify-between py-0.5 transition-colors">
                          <span>View Telemetry Details</span>
                          <span className="text-[9px] text-blue-600 group-open:rotate-180 transition-transform">▼</span>
                        </summary>

                        <div className="mt-1.5 space-y-1.5 bg-slate-50 p-2 rounded-lg border border-slate-200 text-[10px] text-slate-600">
                          {/* Anomaly Badge if flagged */}
                          {bus.has_anomalies && bus.anomaly_flags && bus.anomaly_flags.length > 0 && (
                            <div className="bg-rose-50 text-rose-900 border border-rose-300 rounded p-1 space-y-0.5">
                              <div className="font-bold">⚠️ GPS Anomaly Flagged: {bus.gps_accuracy_status}</div>
                              <div className="text-rose-700 font-mono text-[9px]">{bus.anomaly_flags.join(', ')}</div>
                            </div>
                          )}

                          {/* Mode / Tracking Provenance Badge */}
                          <div className={`p-1 rounded font-medium border ${
                            bus.correction_status === 'UNVERIFIED_ANOMALY_FROZEN'
                              ? 'bg-rose-50 text-rose-900 border-rose-300'
                              : bus.correction_status === 'CALIBRATED_ERROR_CORRECTED'
                              ? 'bg-blue-50 text-blue-900 border-blue-300'
                              : isDeadReckoned
                              ? 'bg-amber-50 text-amber-900 border-amber-300'
                              : 'bg-emerald-50 text-emerald-900 border-emerald-300'
                          }`}>
                            <div className="font-bold">
                              {bus.correction_status === 'UNVERIFIED_ANOMALY_FROZEN'
                                ? 'Position Frozen at Last GPS Fix'
                                : bus.correction_status === 'CALIBRATED_ERROR_CORRECTED'
                                ? `GPS Calibrated (Drift corrected: ${bus.last_prediction_error_meters ?? 0}m)`
                                : bus.correction_status === 'STATIONARY_HOLD'
                                ? 'Stationary Hold (Speed < 1 km/h)'
                                : bus.correction_status === 'EXCEEDED_MAX_AGE_STALE'
                                ? 'Telemetry Stale (Frozen at 180s)'
                                : isDeadReckoned
                                ? 'Estimated position (Dead Reckoned)'
                                : 'Live GPS'}
                            </div>
                            <div className="text-[9px] text-slate-500">
                              {bus.correction_status === 'UNVERIFIED_ANOMALY_FROZEN'
                                ? 'Prediction drift or shape anomaly exceeded safety threshold'
                                : bus.correction_status === 'CALIBRATED_ERROR_CORRECTED'
                                ? `Resynced to genuine GPS fix (uncertainty ±${Math.round(bus.uncertainty_meters || 15)}m)`
                                : isDeadReckoned
                                ? `Extrapolated along corridor (uncertainty ±${Math.round(bus.uncertainty_meters || 15)}m)`
                                : `Direct GPS fix (uncertainty ±${Math.round(bus.uncertainty_meters || 15)}m)`}
                            </div>
                          </div>

                          {bus.route_progress_meters !== null && bus.route_progress_meters !== undefined && (
                            <div>Corridor progress: {Math.round(bus.route_progress_meters)}m along shape</div>
                          )}
                          <div>
                            Last GPS Ping: {bus.last_gps_observation_time || formatEpochToIST(bus.last_gps_timestamp || bus.timestamp_utc)} ({bus.prediction_age_seconds ?? bus.age_seconds}s ago)
                          </div>
                          {bus.latest_position_calculation_time && (
                            <div>Calculated: {bus.latest_position_calculation_time}</div>
                          )}
                          {bus.next_expected_update_time && (
                            <div>Next Update: {bus.next_expected_update_time}</div>
                          )}
                          {bus.last_prediction_error_meters !== null && bus.last_prediction_error_meters !== undefined && (
                            <div>Last Drift Error: {bus.last_prediction_error_meters}m</div>
                          )}
                          <div>
                            Telemetry Status: <span className="font-medium">{bus.is_current ? 'Current Snapshot' : 'Retained Snapshot'}</span>
                          </div>
                        </div>
                      </details>
                    </div>
                  </div>
                </Popup>
              </Marker>
            );
          })}

        {/* 2. FLEET BUSES: Render nearby fleet buses in Mode A OR when showFleetInModeB is enabled in Mode B */}
        {showLiveBuses && ((!selectedJourney || !firstTransitLeg) || showFleetInModeB) &&
          liveBuses
            .filter((bus) => bus.distance_m === undefined || bus.distance_m === null || bus.distance_m <= searchRadiusM)
            .map((bus) => {
              const isCurrent = bus.is_current !== false;
              const icon = !isCurrent ? staleBusIcon : liveBusIcon;

              return (
                <Marker
                  key={`live-${bus.vehicle_id}`}
                  position={[bus.latitude, bus.longitude]}
                  icon={icon}
                >
                  <Popup>
                    <div className="text-xs space-y-1.5 p-1 max-w-[260px]">
                      <div className="flex items-center justify-between border-b pb-1 border-slate-100">
                        <span className="font-bold text-orange-600 font-mono text-[11px]">{bus.vehicle_id}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded font-medium border bg-orange-50 text-orange-700 border-orange-200">
                          Route {bus.route_id || 'Unknown route'}
                        </span>
                      </div>

                      {bus.distance_m !== undefined && bus.distance_m !== null && (
                        <div className="text-[10px] text-teal-800 font-medium bg-teal-50 px-1.5 py-0.5 rounded border border-teal-200">
                          📍 {Math.round(bus.distance_m)}m from {activeCenter.label}
                        </div>
                      )}

                      <div className="text-slate-600 space-y-0.5 text-[11px]">
                        <div>
                          <strong>Trip:</strong> {bus.trip_id || 'Not reported'}
                        </div>
                        <div>
                          <strong>Direction:</strong>{' '}
                          {bus.bearing !== null && bus.bearing !== undefined
                            ? `${Math.round(bus.bearing)}°`
                            : 'Direction unverified'}
                        </div>
                        <div>
                          <strong>Speed:</strong> {bus.speed_kmh !== null && bus.speed_kmh !== undefined ? `${bus.speed_kmh} km/h` : 'Stationary / N/A'}
                        </div>
                        <div>
                          <strong>Source Ping:</strong> {formatEpochToIST(bus.timestamp_utc)} IST ({bus.age_seconds}s ago)
                        </div>
                        <div className="flex items-center space-x-1">
                          <strong>Telemetry:</strong>{' '}
                          <span
                            className={`px-1 py-0.2 rounded text-[10px] font-medium ${
                              isCurrent
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-slate-100 text-slate-700 border border-slate-300'
                            }`}
                          >
                            {isCurrent ? 'Current Snapshot' : 'Last Known / Stale Position'}
                          </span>
                        </div>
                        {bus.is_out_of_area && (
                          <div className="text-[10px] text-purple-700 font-medium">
                            📍 NCR Interstate Corridor (Outside Delhi Core)
                          </div>
                        )}
                      </div>
                      <div className="text-[9px] text-slate-400 pt-1 border-t border-slate-100 leading-tight">
                        Real-time GPS telemetry from Delhi Transport Stack GTFS-RT. Radius: {searchRadiusM < 1000 ? `${searchRadiusM}m` : `${searchRadiusM / 1000}km`}. 20s refresh.
                      </div>
                    </div>
                  </Popup>
                </Marker>
              );
            })}

        {/* Selected Journey Route Polylines */}
        {transitPolylines.map((item, idx) => (
          <Polyline
            key={`transit-${idx}`}
            positions={item.coords}
            pathOptions={{ color: '#0F766E', weight: 5, opacity: 0.9 }}
          >
            <Popup>
              <div className="text-xs space-y-1">
                <div className="font-bold text-slate-900">{item.label}</div>
                <div className="text-slate-500 text-[11px]">
                  {item.hasShape
                    ? `True roadway alignment (${item.coords.length} street curvature coordinates)`
                    : item.intermediateCount > 0
                    ? `Connecting ${item.intermediateCount + 2} stops via straight lines`
                    : 'Endpoint-to-endpoint straight line'}
                </div>
                {item.hasShape ? (
                  <div className="text-emerald-700 text-[10px] bg-emerald-50 p-1 rounded border border-emerald-200">
                    ✓ True road geometry from GTFS shapes.txt ({item.coords.length} curvature points).
                  </div>
                ) : (
                  <div className="text-amber-700 text-[10px] bg-amber-50 p-1 rounded border border-amber-200">
                    ⚠️ Approximate geometry: Road curvature unrepresented (no shapes.txt in GTFS).
                  </div>
                )}
              </div>
            </Popup>
          </Polyline>
        ))}

        {/* Clean Walking Polylines */}
        {walkingPolylines.map((item, idx) => (
          <Polyline
            key={`walk-${idx}`}
            positions={item.coords}
            pathOptions={{ color: '#0284C7', weight: 4, dashArray: '6, 8', opacity: 0.85 }}
          >
            <Popup>
              <div className="text-xs">
                <div className="font-bold text-slate-900">{item.label}</div>
                <div className="text-slate-500 text-[11px]">Straight-line walking estimate</div>
              </div>
            </Popup>
          </Polyline>
        ))}
      </MapContainer>

      {/* Floating Map Legend with Show/Hide Control */}
      <div className="absolute bottom-3 left-3 z-[400] max-w-[260px]">
        {isLegendOpen ? (
          <div className="bg-white/95 backdrop-blur-md p-3.5 rounded-2xl border border-slate-200 text-xs shadow-lg space-y-1.5 text-slate-700 animate-in fade-in zoom-in-95 duration-150">
            <div className="font-bold text-slate-800 text-[11px] uppercase tracking-wider flex items-center justify-between border-b pb-1.5 border-slate-100">
              <span className="flex items-center space-x-1.5">
                <Layers className="w-3.5 h-3.5 text-blue-600" />
                <span>Map Legend</span>
              </span>
              <button
                type="button"
                onClick={() => setIsLegendOpen(false)}
                className="text-[10px] text-slate-400 hover:text-slate-700 font-semibold hover:bg-slate-100 px-1.5 py-0.5 rounded-md flex items-center space-x-0.5 transition-colors"
                title="Hide Legend"
              >
                <span>Hide</span>
                <ChevronDown className="w-3 h-3" />
              </button>
            </div>
            <div className="space-y-1 pt-0.5">
              <div className="flex items-center space-x-2">
                <span className="w-3 h-3 rounded-full bg-emerald-600 inline-block shrink-0" />
                <span>Origin Point (A)</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="w-3 h-3 rounded-full bg-rose-600 inline-block shrink-0" />
                <span>Destination Point (B)</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="w-4 h-4 rounded-full bg-teal-700 inline-flex items-center justify-center text-[9px] text-white shrink-0">🚏</span>
                <span>Boarding Stop</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="w-4 h-4 rounded-full bg-amber-700 inline-flex items-center justify-center text-[9px] text-white shrink-0">🏁</span>
                <span>Alighting Stop</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="w-5 h-1 bg-teal-700 inline-block rounded shrink-0" />
                <span className="text-[11px]">Bus Leg ({anyTrueShape ? 'Road shape' : 'Stop-to-stop'})</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="w-5 h-1 border-b-2 border-dashed border-sky-600 inline-block shrink-0" />
                <span className="text-[11px]">Walking Path</span>
              </div>
              {selectedJourney && firstTransitLeg ? (
                <>
                  <div className="flex items-center space-x-2">
                    <span className="w-4 h-4 rounded-full bg-amber-600 inline-flex items-center justify-center text-[9px] text-white shrink-0 shadow-xs">⭐</span>
                    <span className="text-[11px] font-semibold text-amber-800">
                      Verified Bus (Live GPS) ({suitableVehicles.filter(v => !v.is_dead_reckoned && v.position_source !== 'DEAD_RECKONED').length})
                    </span>
                  </div>
                  {suitableVehicles.some(v => v.is_dead_reckoned || v.position_source === 'DEAD_RECKONED') && (
                    <div className="flex items-center space-x-2">
                      <span className="w-4 h-4 rounded-full bg-amber-700 border border-dashed border-amber-900 inline-flex items-center justify-center text-[9px] text-amber-100 shrink-0 shadow-xs">⚡</span>
                      <span className="text-[11px] font-semibold text-amber-900">
                        Estimated Bus (Dead Reckoned) ({suitableVehicles.filter(v => v.is_dead_reckoned || v.position_source === 'DEAD_RECKONED').length})
                      </span>
                    </div>
                  )}
                </>
              ) : (
                <>
                  <div className="flex items-center space-x-2">
                    <span className="w-3 h-3 rounded-full bg-orange-600 inline-block shrink-0 text-center text-[8px] leading-3 text-white">🚌</span>
                    <span className="text-[11px]">Nearby Current Bus ({liveBusMeta.current})</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="w-3 h-3 rounded-full bg-slate-500 inline-block shrink-0 text-center text-[8px] leading-3 text-white">🚌</span>
                    <span className="text-[11px]">Nearby Stale Bus ({liveBusMeta.stale})</span>
                  </div>
                </>
              )}
            </div>
            {lastFeedPollTime && (
              <div className="text-[9px] text-slate-400 pt-1 border-t border-slate-100">
                Live feed synced at {lastFeedPollTime} IST
              </div>
            )}
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setIsLegendOpen(true)}
            className="bg-white/95 backdrop-blur-md px-3 py-1.5 rounded-xl border border-slate-200 text-xs shadow-md font-semibold text-slate-700 hover:text-slate-900 flex items-center space-x-1.5 transition-colors"
          >
            <Layers className="w-3.5 h-3.5 text-blue-600" />
            <span>Show Legend</span>
            <ChevronUp className="w-3 h-3 text-slate-400" />
          </button>
        )}
      </div>
    </div>
  );
};
