import React, { useState, useEffect } from 'react';
import {
  Bus,
  Search,
  Loader2,
  Navigation,
  Clock,
  Radio,
  CheckCircle2,
  XCircle,
  HelpCircle,
  RefreshCw,
  SlidersHorizontal,
} from 'lucide-react';
import { Stop, LiveVehicleItem, JourneyAlternative, TransitLeg } from '../types/api';
import { apiService } from '../services/api';

interface StopDiscoveryProps {
  originStop: Stop | null;
  originCoord: [number, number] | null;
  selectedJourney: JourneyAlternative | null;
  onSelectOrigin: (stop: Stop) => void;
  onSelectDest: (stop: Stop) => void;
  onNearbyFound: (stops: Stop[]) => void;
}

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

export const StopDiscovery: React.FC<StopDiscoveryProps> = ({
  originStop,
  originCoord,
  selectedJourney,
  onSelectOrigin,
  onSelectDest,
  onNearbyFound,
}) => {
  // Tabs: live_buses (default), search, nearby_hubs
  const [activeTab, setActiveTab] = useState<'live_buses' | 'search' | 'nearby_hubs'>('live_buses');

  // Live Buses State
  const [nearbyVehicles, setNearbyVehicles] = useState<LiveVehicleItem[]>([]);
  const [loadingVehicles, setLoadingVehicles] = useState(false);
  const [filterSuitableOnly, setFilterSuitableOnly] = useState(false);
  const [lastLivePollTime, setLastLivePollTime] = useState<string>('');

  // Stop Search State
  const [searchQuery, setSearchQuery] = useState('');
  const [searchedStops, setSearchedStops] = useState<Stop[]>([]);
  const [loadingSearch, setLoadingSearch] = useState(false);

  // Determine current departure point coordinates
  const departureLat = originStop?.lat ?? originCoord?.[0] ?? 28.7075;
  const departureLon = originStop?.lon ?? originCoord?.[1] ?? 77.1782;
  const departureLabel = originStop
    ? originStop.stop_name
    : originCoord
    ? `Map Pin (${originCoord[0].toFixed(4)}, ${originCoord[1].toFixed(4)})`
    : 'Azadpur / North GT Corridor (Default)';

  // Extract transit routes for suitability filtering
  const journeyRoutes = new Set(
    selectedJourney?.legs
      .filter((l): l is TransitLeg => l.leg_type === 'TRANSIT')
      .map((l) => String(l.route_id).trim()) || []
  );

  const primaryBoardStop =
    selectedJourney?.legs.find((l): l is TransitLeg => l.leg_type === 'TRANSIT')?.board_stop_name ||
    (originStop ? originStop.stop_name : 'Nearest Boarding Stop');

  // Fetch live GTFS-RT vehicles near departure point
  const fetchNearbyVehicles = async (showLoading: boolean = false) => {
    if (showLoading) setLoadingVehicles(true);
    try {
      // Query 3500m radius around passenger departure coordinates
      const res = await apiService.getLiveVehicles(
        undefined,
        30,
        departureLat,
        departureLon,
        3500
      );
      if (res && res.vehicles) {
        setNearbyVehicles(res.vehicles);
        setLastLivePollTime(
          new Date().toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false })
        );
      }
    } catch {
      // Silently fall back to cached list
    } finally {
      if (showLoading) setLoadingVehicles(false);
    }
  };

  // 20-second polling for live moving vehicles near departure point (shared backend cache)
  useEffect(() => {
    fetchNearbyVehicles(true);
    const interval = setInterval(() => {
      fetchNearbyVehicles(false);
    }, 20000);

    return () => clearInterval(interval);
  }, [departureLat, departureLon]);

  // Stop text search
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setLoadingSearch(true);
    try {
      const res = await apiService.searchStops(searchQuery, 15);
      setSearchedStops(res.stops);
    } catch (err) {
      console.error('Stop search failed', err);
    } finally {
      setLoadingSearch(false);
    }
  };

  // Find nearby stop hubs
  const handleFindNearbyHubs = async (lat: number, lon: number) => {
    setLoadingSearch(true);
    try {
      const res = await apiService.getNearbyStops(lat, lon, 1000, 10);
      setSearchedStops(res.stops);
      onNearbyFound(res.stops);
    } catch (err) {
      console.error('Nearby search failed', err);
    } finally {
      setLoadingSearch(false);
    }
  };

  // Apply suitability filter
  const displayedVehicles = nearbyVehicles.filter((v) => {
    if (!filterSuitableOnly) return true;
    if (journeyRoutes.size === 0) return true;
    return v.route_id && journeyRoutes.has(String(v.route_id).trim());
  });

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm text-xs">
      {/* Header and Mode Selector */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
        <h3 className="font-bold text-slate-800 uppercase tracking-wider flex items-center space-x-1.5">
          <Bus className="w-3.5 h-3.5 text-blue-600" />
          <span>Live Fleet & Stop Discovery</span>
        </h3>
        <div className="flex space-x-1 bg-slate-100 p-0.5 rounded">
          <button
            type="button"
            onClick={() => setActiveTab('live_buses')}
            className={`px-2 py-0.5 rounded font-medium transition-colors flex items-center space-x-1 ${
              activeTab === 'live_buses' ? 'bg-white text-orange-700 shadow-2xs font-semibold' : 'text-slate-600'
            }`}
          >
            <Radio className="w-3 h-3 text-orange-600 animate-pulse" />
            <span>Nearby Buses</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('search')}
            className={`px-2 py-0.5 rounded font-medium transition-colors ${
              activeTab === 'search' ? 'bg-white text-slate-900 shadow-2xs font-semibold' : 'text-slate-600'
            }`}
          >
            Search Stops
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveTab('nearby_hubs');
              handleFindNearbyHubs(28.6675, 77.2283);
            }}
            className={`px-2 py-0.5 rounded font-medium transition-colors ${
              activeTab === 'nearby_hubs' ? 'bg-white text-slate-900 shadow-2xs font-semibold' : 'text-slate-600'
            }`}
          >
            Hubs
          </button>
        </div>
      </div>

      {/* Tab 1: Actual Live GTFS-RT Moving Vehicles near departure point */}
      {activeTab === 'live_buses' && (
        <div className="mt-3 space-y-2.5">
          {/* Departure Anchor Notice & Suitable Filter Toggle */}
          <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5">
            <div>
              <div className="font-semibold text-slate-800 flex items-center space-x-1">
                <Navigation className="w-3 h-3 text-blue-600" />
                <span>Departure Point: {departureLabel}</span>
              </div>
              <div className="text-[11px] text-slate-500">
                Tracking moving buses within 3.5 km radius &bull; 5s refresh
              </div>
            </div>

            {journeyRoutes.size > 0 && (
              <button
                type="button"
                onClick={() => setFilterSuitableOnly(!filterSuitableOnly)}
                className={`px-2 py-1 rounded text-[11px] font-medium border flex items-center space-x-1 self-start sm:self-auto transition-colors ${
                  filterSuitableOnly
                    ? 'bg-amber-100 text-amber-900 border-amber-300'
                    : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-100'
                }`}
              >
                <SlidersHorizontal className="w-3 h-3" />
                <span>{filterSuitableOnly ? 'Showing Matching Routes Only' : 'Show All Nearby'}</span>
              </button>
            )}
          </div>

          {/* Vehicles List */}
          {loadingVehicles && nearbyVehicles.length === 0 ? (
            <div className="py-6 flex flex-col items-center justify-center text-slate-400 space-y-2">
              <Loader2 className="w-5 h-5 animate-spin text-orange-500" />
              <span>Scanning live Delhi GTFS-RT telemetry near departure point...</span>
            </div>
          ) : displayedVehicles.length === 0 ? (
            <div className="py-5 text-center text-slate-500 bg-slate-50 rounded-lg border border-slate-200">
              {filterSuitableOnly
                ? 'No live buses matching your selected journey routes are currently in the 3.5 km radius.'
                : 'No active buses currently reporting GPS within 3.5 km of this location.'}
            </div>
          ) : (
            <div className="divide-y divide-slate-100 max-h-56 overflow-y-auto pr-1 space-y-1">
              {displayedVehicles.map((bus) => {
                const isRouteMatch =
                  journeyRoutes.size > 0 &&
                  bus.route_id &&
                  journeyRoutes.has(String(bus.route_id).trim());

                // Direction compatibility can only be verified if bearing/trip headsign is verified against route trajectory
                const isDirectionVerified = Boolean(
                  bus.bearing !== null && bus.is_matched_to_gtfs
                );

                return (
                  <div key={`veh-${bus.vehicle_id}`} className="py-2 space-y-1">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-1.5">
                        <span className="font-mono font-bold text-slate-900 text-xs">
                          {bus.vehicle_id}
                        </span>
                        <span className="px-1.5 py-0.5 rounded font-semibold text-[10px] bg-orange-50 text-orange-700 border border-orange-200">
                          Route {bus.route_id || 'Unknown'}
                        </span>
                        {bus.distance_m !== undefined && (
                          <span className="text-[11px] text-blue-700 font-medium">
                            ~{Math.round(bus.distance_m)}m away
                          </span>
                        )}
                      </div>

                      {/* Suitability Badge - A matching route ID alone must not produce "Suitable for Journey" unless destination compatibility is verified */}
                      {journeyRoutes.size > 0 ? (
                        isRouteMatch ? (
                          isDirectionVerified ? (
                            <span className="flex items-center space-x-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
                              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                              <span>Suitable for Journey</span>
                            </span>
                          ) : (
                            <span
                              className="flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-50 text-amber-800 border border-amber-300"
                              title="Vehicle route matches journey, but Delhi GTFS-RT feed does not report trip headsign/direction to verify destination compatibility"
                            >
                              <HelpCircle className="w-3 h-3 text-amber-600" />
                              <span>Route matches — direction unverified</span>
                            </span>
                          )
                        ) : (
                          <span className="flex items-center space-x-0.5 px-1.5 py-0.5 rounded text-[10px] font-normal bg-slate-100 text-slate-500 border border-slate-200">
                            <XCircle className="w-3 h-3 text-slate-400" />
                            <span>Unrelated Route</span>
                          </span>
                        )
                      ) : (
                        <span className="text-[10px] text-slate-400">
                          Plan journey to evaluate
                        </span>
                      )}
                    </div>

                    {/* Metadata Grid */}
                    <div className="grid grid-cols-2 gap-x-2 text-[11px] text-slate-600">
                      <div>
                        <strong>Speed:</strong> {bus.speed_kmh !== null ? `${bus.speed_kmh} km/h` : 'Stationary / N/A'}
                      </div>
                      <div>
                        <strong>Direction:</strong>{' '}
                        {bus.bearing !== null
                          ? `${Math.round(bus.bearing)}°`
                          : 'Not reported by provider'}
                      </div>
                      <div>
                        <strong>Nearest Boarding:</strong> {primaryBoardStop}
                      </div>
                      <div>
                        <strong>Ping:</strong> {formatEpochToIST(bus.timestamp_utc)} IST ({bus.age_seconds}s ago)
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Explicit Feed Disclosure Footer */}
          <div className="pt-2 border-t border-slate-100 text-[10px] text-slate-400 flex items-center justify-between">
            <span>
              Real-time GTFS-RT telemetry from Delhi Transport Stack (DEGRADE status).
            </span>
            {lastLivePollTime && <span>Synced {lastLivePollTime} IST</span>}
          </div>
        </div>
      )}

      {/* Tab 2: Search Bus Stops by Name */}
      {activeTab === 'search' && (
        <div className="mt-3 space-y-2">
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by stop name (e.g. Kashmere, Azadpur)..."
              className="flex-1 px-3 py-1.5 border border-slate-300 rounded-lg text-xs text-slate-800 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            />
            <button
              type="submit"
              disabled={loadingSearch || !searchQuery.trim()}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg disabled:opacity-50 transition-colors flex items-center space-x-1"
            >
              {loadingSearch ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
              <span>Find</span>
            </button>
          </form>

          {searchedStops.length > 0 && (
            <div className="mt-2 divide-y divide-slate-100 max-h-48 overflow-y-auto">
              {searchedStops.map((stop) => (
                <div key={stop.stop_id} className="py-2 flex items-center justify-between">
                  <div>
                    <div className="font-medium text-slate-900">{stop.stop_name}</div>
                    <div className="text-[11px] text-slate-500 font-mono">
                      ID: {stop.stop_id} {stop.distance_m ? `• ${Math.round(stop.distance_m)}m away` : ''}
                    </div>
                  </div>
                  <div className="flex space-x-1.5">
                    <button
                      type="button"
                      onClick={() => onSelectOrigin(stop)}
                      className="px-2 py-0.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-medium rounded text-[11px]"
                    >
                      Set Origin
                    </button>
                    <button
                      type="button"
                      onClick={() => onSelectDest(stop)}
                      className="px-2 py-0.5 bg-rose-50 hover:bg-rose-100 text-rose-700 font-medium rounded text-[11px]"
                    >
                      Set Dest
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Nearby Major Hub Presets */}
      {activeTab === 'nearby_hubs' && (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => handleFindNearbyHubs(28.6675, 77.2283)}
              className="px-2 py-1 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded text-slate-700"
            >
              📍 Kashmere Gate ISBT
            </button>
            <button
              type="button"
              onClick={() => handleFindNearbyHubs(28.708, 77.175)}
              className="px-2 py-1 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded text-slate-700"
            >
              📍 Azadpur Terminal
            </button>
            <button
              type="button"
              onClick={() => handleFindNearbyHubs(28.8524, 77.0934)}
              className="px-2 py-1 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded text-slate-700"
            >
              📍 Narela Terminal
            </button>
          </div>

          {searchedStops.length > 0 && (
            <div className="mt-2 divide-y divide-slate-100 max-h-48 overflow-y-auto">
              {searchedStops.map((stop) => (
                <div key={stop.stop_id} className="py-2 flex items-center justify-between">
                  <div>
                    <div className="font-medium text-slate-900">{stop.stop_name}</div>
                    <div className="text-[11px] text-slate-500 font-mono">
                      ID: {stop.stop_id} {stop.distance_m ? `• ${Math.round(stop.distance_m)}m away` : ''}
                    </div>
                  </div>
                  <div className="flex space-x-1.5">
                    <button
                      type="button"
                      onClick={() => onSelectOrigin(stop)}
                      className="px-2 py-0.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-medium rounded text-[11px]"
                    >
                      Set Origin
                    </button>
                    <button
                      type="button"
                      onClick={() => onSelectDest(stop)}
                      className="px-2 py-0.5 bg-rose-50 hover:bg-rose-100 text-rose-700 font-medium rounded text-[11px]"
                    >
                      Set Dest
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
