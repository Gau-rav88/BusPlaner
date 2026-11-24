import React, { useState, useEffect } from 'react';
import { Header } from '../components/Header';
import { PlannerForm } from '../components/PlannerForm';
import { JourneyResults } from '../components/JourneyResults';
import { StopDiscovery } from '../components/StopDiscovery';
import { AlertBanner } from '../components/AlertBanner';
import { DelhiMap } from '../map/DelhiMap';
import {
  Stop,
  JourneyPlanRequest,
  JourneyPlanResponse,
  HealthResponse,
  TimetableStatusResponse,
} from '../types/api';
import { apiService, ApiException } from '../services/api';

export const PlannerPage: React.FC = () => {
  // Endpoints State
  const [originStop, setOriginStop] = useState<Stop | null>(null);
  const [destStop, setDestStop] = useState<Stop | null>(null);
  const [originCoord, setOriginCoord] = useState<[number, number] | null>(null);
  const [destCoord, setDestCoord] = useState<[number, number] | null>(null);
  const [originPlaceName, setOriginPlaceName] = useState<string>('');
  const [destPlaceName, setDestPlaceName] = useState<string>('');

  // Results State
  const [journeyResponse, setJourneyResponse] = useState<JourneyPlanResponse | null>(null);
  const [selectedJourneyIndex, setSelectedJourneyIndex] = useState<number>(0);
  const [nearbyStops, setNearbyStops] = useState<Stop[]>([]);

  // Health and Freshness State
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [timetableStatus, setTimetableStatus] = useState<TimetableStatusResponse | null>(null);
  const [loadingHealth, setLoadingHealth] = useState(true);

  // Form execution state
  const [planningLoading, setPlanningLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [focusPickupTrigger, setFocusPickupTrigger] = useState<number>(0);
  const [errorBanner, setErrorBanner] = useState<{
    type: 'warning' | 'error' | 'info';
    title?: string;
    message: string;
    actionLabel?: string;
    onAction?: () => void;
  } | null>(null);

  // Initialize: load health and timetable freshness
  useEffect(() => {
    async function initSystem() {
      setLoadingHealth(true);
      try {
        const [h, tt] = await Promise.all([
          apiService.getHealth().catch(() => null),
          apiService.getTimetableStatus('2026-10-01', true).catch(() => null),
        ]);
        setHealth(h);
        setTimetableStatus(tt);
      } finally {
        setLoadingHealth(false);
      }
    }
    initSystem();
  }, []);

  // Reverse geocode nearest GTFS stop within 1500m to display human-readable place name
  const resolvePlaceName = async (lat: number, lon: number): Promise<string> => {
    try {
      const res = await apiService.getNearbyStops(lat, lon, 1500, 1);
      if (res && res.stops && res.stops.length > 0) {
        const nearest = res.stops[0];
        const dist = Math.round(nearest.distance_m ?? 0);
        return `Near ${nearest.stop_name} (~${dist}m)`;
      }
    } catch {
      // Fallback
    }
    return `Location (${lat.toFixed(4)}, ${lon.toFixed(4)})`;
  };

  // Map Click Handler: assign to origin or dest depending on state
  const handleMapClick = async (lat: number, lon: number) => {
    if (!originStop && !originCoord) {
      setOriginCoord([lat, lon]);
      setOriginPlaceName(`Location (${lat.toFixed(4)}, ${lon.toFixed(4)})`);
      const name = await resolvePlaceName(lat, lon);
      setOriginPlaceName(name);
    } else if (!destStop && !destCoord) {
      setDestCoord([lat, lon]);
      setDestPlaceName(`Location (${lat.toFixed(4)}, ${lon.toFixed(4)})`);
      const name = await resolvePlaceName(lat, lon);
      setDestPlaceName(name);
    } else {
      // If both already set, update destination
      setDestCoord([lat, lon]);
      setDestStop(null);
      setDestPlaceName(`Location (${lat.toFixed(4)}, ${lon.toFixed(4)})`);
      const name = await resolvePlaceName(lat, lon);
      setDestPlaceName(name);
    }
  };

  // Journey plan submission handler
  const handlePlanJourney = async (req: JourneyPlanRequest) => {
    setPlanningLoading(true);
    setErrorBanner(null);
    setHasSearched(true);

    try {
      const response = await apiService.planJourney(req);
      setJourneyResponse(response);
      setSelectedJourneyIndex(0);

      // If backend returned stale timetable warning, show warning banner
      if (response.stale_timetable_warning) {
        setErrorBanner({
          type: 'warning',
          title: 'Demonstration Timetable Notice',
          message: response.stale_timetable_warning,
        });
      }
    } catch (err: any) {
      if (err instanceof ApiException) {
        if (err.status === 400 && err.errorData.error === 'EXPIRED_TIMETABLE') {
          setErrorBanner({
            type: 'error',
            title: 'Timetable Expired (Strict Mode)',
            message: err.errorData.detail,
            actionLabel: 'Enable Assumed Recurring Mode & Retry',
            onAction: () => {
              handlePlanJourney({ ...req, allow_assumed_recurring: true });
            },
          });
        } else if (err.status === 503) {
          setErrorBanner({
            type: 'error',
            title: 'Timetable Unavailable',
            message: 'GTFS Timetable database is offline or unreadable on backend.',
          });
        } else {
          setErrorBanner({
            type: 'error',
            title: err.errorData.error || 'Planning Error',
            message: err.errorData.detail || 'An unexpected error occurred while planning journey.',
          });
        }
      } else {
        setErrorBanner({
          type: 'error',
          title: 'Connection Failed',
          message: 'Unable to connect to FastAPI backend at /api/v1. Ensure backend is running.',
        });
      }
      setJourneyResponse(null);
    } finally {
      setPlanningLoading(false);
    }
  };

  const selectedJourney =
    journeyResponse && journeyResponse.journeys.length > selectedJourneyIndex
      ? journeyResponse.journeys[selectedJourneyIndex]
      : null;

  return (
    <div className="h-screen flex flex-col bg-slate-50 overflow-hidden font-sans">
      <Header health={health} timetableStatus={timetableStatus} loading={loadingHealth} />

      {/* Main Full-Height App Container: Sidebar + Expansive Map */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden relative">
        {/* Left Sidebar (Transit App floating card / docked panel style) */}
        <aside className="w-full md:w-[420px] lg:w-[460px] h-full flex flex-col bg-white border-r border-slate-200/80 shadow-lg z-20 shrink-0 overflow-y-auto">
          <div className="p-4 space-y-4">
            {/* Error/Warning Banner if active */}
            {errorBanner && (
              <AlertBanner
                type={errorBanner.type}
                title={errorBanner.title}
                message={errorBanner.message}
                actionLabel={errorBanner.actionLabel}
                onAction={errorBanner.onAction}
              />
            )}

            {/* Clean Origin/Destination Planner Form */}
            <PlannerForm
              originStop={originStop}
              destStop={destStop}
              originCoord={originCoord}
              destCoord={destCoord}
              originPlaceName={originPlaceName}
              destPlaceName={destPlaceName}
              onSelectOriginStop={(s) => {
                setOriginStop(s);
                if (s) {
                  setOriginCoord(null);
                  setOriginPlaceName(s.stop_name);
                }
              }}
              onSelectDestStop={(s) => {
                setDestStop(s);
                if (s) {
                  setDestCoord(null);
                  setDestPlaceName(s.stop_name);
                }
              }}
              onClearOrigin={() => {
                setOriginStop(null);
                setOriginCoord(null);
                setOriginPlaceName('');
              }}
              onClearDest={() => {
                setDestStop(null);
                setDestCoord(null);
                setDestPlaceName('');
              }}
              onSubmit={handlePlanJourney}
              loading={planningLoading}
            />

            {/* Journey Results Cards */}
            <JourneyResults
              journeys={journeyResponse?.journeys || []}
              selectedIndex={selectedJourneyIndex}
              onSelectJourney={(idx) => setSelectedJourneyIndex(idx)}
              loading={planningLoading}
              searched={hasSearched}
              staleWarning={journeyResponse?.stale_timetable_warning}
              onLocatePickupBuses={() => setFocusPickupTrigger((prev) => prev + 1)}
            />

            {/* Secondary Tool: Discovered Stops & Fleet Exploration (Inside expandable section) */}
            <div className="pt-2 border-t border-slate-100">
              <details className="group">
                <summary className="text-xs font-semibold text-slate-500 hover:text-slate-800 cursor-pointer list-none flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-slate-50 transition-colors">
                  <span>Explore Stops & Fleet</span>
                  <span className="text-[10px] text-blue-600 group-open:rotate-180 transition-transform">▼</span>
                </summary>
                <div className="mt-2">
                  <StopDiscovery
                    originStop={originStop}
                    originCoord={originCoord}
                    selectedJourney={selectedJourney}
                    onSelectOrigin={(s) => {
                      setOriginStop(s);
                      setOriginCoord(null);
                      setOriginPlaceName(s.stop_name);
                    }}
                    onSelectDest={(s) => {
                      setDestStop(s);
                      setDestCoord(null);
                      setDestPlaceName(s.stop_name);
                    }}
                    onNearbyFound={(stops) => setNearbyStops(stops)}
                  />
                </div>
              </details>
            </div>
          </div>

          {/* Minimal Sidebar Footer */}
          <div className="mt-auto p-3 bg-slate-50/80 border-t border-slate-100 text-center text-[11px] text-slate-400">
            Delhi Transit Planner &bull; Status: <strong className="text-slate-600">DEGRADE</strong> &bull; 15s GPS Updates
          </div>
        </aside>

        {/* Right Map Canvas: Dominates the main available space */}
        <main className="flex-1 h-full relative z-10 bg-slate-100 overflow-hidden">
          <DelhiMap
            originStop={originStop}
            destStop={destStop}
            originCoord={originCoord}
            destCoord={destCoord}
            selectedJourney={selectedJourney}
            nearbyStops={nearbyStops}
            onMapClick={handleMapClick}
            onSelectStopAsOrigin={(s) => {
              setOriginStop(s);
              setOriginCoord(null);
            }}
            onSelectStopAsDest={(s) => {
              setDestStop(s);
              setDestCoord(null);
            }}
            focusPickupTrigger={focusPickupTrigger}
          />
        </main>
      </div>
    </div>
  );
};
