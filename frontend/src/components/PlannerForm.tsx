import React, { useState } from 'react';
import {
  ArrowDownUp,
  Search,
  Settings2,
  Clock,
  Calendar,
  Footprints,
  Shuffle,
  Sparkles,
} from 'lucide-react';
import { Stop, JourneyPlanRequest } from '../types/api';
import { StopSearchInput } from './StopSearchInput';

interface PlannerFormProps {
  originStop: Stop | null;
  destStop: Stop | null;
  originCoord: [number, number] | null;
  destCoord: [number, number] | null;
  originPlaceName?: string;
  destPlaceName?: string;
  onSelectOriginStop: (stop: Stop | null) => void;
  onSelectDestStop: (stop: Stop | null) => void;
  onClearOrigin: () => void;
  onClearDest: () => void;
  onSubmit: (req: JourneyPlanRequest) => void;
  loading: boolean;
}

export const PlannerForm: React.FC<PlannerFormProps> = ({
  originStop,
  destStop,
  originCoord,
  destCoord,
  originPlaceName,
  destPlaceName,
  onSelectOriginStop,
  onSelectDestStop,
  onClearOrigin,
  onClearDest,
  onSubmit,
  loading,
}) => {
  // Form State: Initialize with device current date and time in Asia/Kolkata
  const getNowKolkata = () => {
    const now = new Date();
    const datePart = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(now);
    const timePart = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Kolkata',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).format(now);
    return { datePart, timePart };
  };

  const initialKolkata = getNowKolkata();
  const [departureDate, setDepartureDate] = useState(initialKolkata.datePart);
  const [departureTime, setDepartureTime] = useState(initialKolkata.timePart);
  const [maxWalkingM, setMaxWalkingM] = useState(800);
  const [maxTransfers, setMaxTransfers] = useState(3);
  const [rankingStrategy, setRankingStrategy] = useState<
    'earliest_arrival' | 'fewest_transfers' | 'least_walking' | 'most_reliable'
  >('earliest_arrival');
  const [allowAssumedRecurring, setAllowAssumedRecurring] = useState(true);
  const [useExperimentalMl, setUseExperimentalMl] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Reset date/time to live current device time in Asia/Kolkata
  const handleResetToLive = () => {
    const live = getNowKolkata();
    setDepartureDate(live.datePart);
    setDepartureTime(live.timePart);
  };

  // Swap endpoints
  const handleSwap = () => {
    const prevOriginStop = originStop;
    const prevDestStop = destStop;
    onSelectOriginStop(prevDestStop);
    onSelectDestStop(prevOriginStop);
  };

  // Submit Journey Request
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const req: JourneyPlanRequest = {
      origin_stop_id: originStop ? originStop.stop_id : null,
      dest_stop_id: destStop ? destStop.stop_id : null,
      origin_lat: !originStop && originCoord ? originCoord[0] : null,
      origin_lon: !originStop && originCoord ? originCoord[1] : null,
      dest_lat: !destStop && destCoord ? destCoord[0] : null,
      dest_lon: !destStop && destCoord ? destCoord[1] : null,
      departure_date: departureDate,
      departure_time: departureTime,
      max_walking_distance_m: maxWalkingM,
      max_transfers: maxTransfers,
      num_alternatives: 3,
      ranking_strategy: rankingStrategy,
      use_experimental_ml: useExperimentalMl,
      allow_assumed_recurring: allowAssumedRecurring,
    };

    onSubmit(req);
  };

  // Set preset for verified North GT Road corridor (Route 1598, Stop 239 -> 247)
  const handleSetPresetNorthGtRoad = () => {
    onSelectOriginStop({
      stop_id: '239',
      stop_name: 'Azad Pur Terminal',
      lat: 28.707535,
      lon: 77.178192,
    });
    onSelectDestStop({
      stop_id: '247',
      stop_name: 'Mukarba Chowk',
      lat: 28.734650,
      lon: 77.155769,
    });
    setDepartureDate('2026-10-01');
    setDepartureTime('12:37:40');
    setAllowAssumedRecurring(true);
  };

  // High-frequency live corridor preset: Route 641 (30 verified live buses right now)
  const handleSetPresetRoute641 = () => {
    onSelectOriginStop({
      stop_id: '3572',
      stop_name: 'JhulJhuli Check Post / Ghumanhera Crossing',
      lat: 28.535372,
      lon: 76.909686,
    });
    onSelectDestStop({
      stop_id: '3640',
      stop_name: 'Tilak Pul / Chander Nagar',
      lat: 28.621389,
      lon: 77.070002,
    });
    setDepartureDate('2026-10-01');
    setDepartureTime('08:00:00');
    setAllowAssumedRecurring(true);
  };

  // High-frequency live corridor preset: Route 3475 (17 verified live buses right now)
  const handleSetPresetRoute3475 = () => {
    onSelectOriginStop({
      stop_id: '3364',
      stop_name: 'Ghuman Hera Depot 2',
      lat: 28.537462,
      lon: 76.913447,
    });
    onSelectDestStop({
      stop_id: '3534',
      stop_name: 'Tuda Mandi Najafgarh Road',
      lat: 28.612594,
      lon: 76.991382,
    });
    setDepartureDate('2026-10-01');
    setDepartureTime('08:00:00');
    setAllowAssumedRecurring(true);
  };

  const hasOrigin = originStop !== null || originCoord !== null;
  const hasDest = destStop !== null || destCoord !== null;
  const isFormValid = hasOrigin && hasDest;

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-2xl shadow-sm border border-slate-200/90 p-4 sm:p-5 transition-shadow hover:shadow-md"
    >
      {/* Endpoints Selection — Transit App Style */}
      <div className="relative">
        <div className="space-y-3">
          {/* Origin Stop Input */}
          <StopSearchInput
            label="Where do you start?"
            placeholder="Search stop or click map..."
            selectedStop={originStop}
            coordinateText={
              originCoord ? `${originCoord[0].toFixed(4)}, ${originCoord[1].toFixed(4)}` : ''
            }
            placeName={originPlaceName}
            onSelectStop={onSelectOriginStop}
            onClear={onClearOrigin}
            badgeColor="text-emerald-600"
            dotColor="bg-emerald-600"
          />

          {/* Swap Button (floating neatly between inputs) */}
          <div className="flex items-center justify-between px-2 -my-1 z-10 relative">
            <div className="h-[1px] flex-1 bg-slate-100" />
            <button
              type="button"
              onClick={handleSwap}
              className="mx-3 p-1.5 rounded-full bg-white hover:bg-slate-100 border border-slate-200 text-slate-500 hover:text-slate-800 shadow-xs transition-transform active:scale-90"
              title="Swap Origin and Destination"
            >
              <ArrowDownUp className="w-3.5 h-3.5" />
            </button>
            <div className="h-[1px] flex-1 bg-slate-100" />
          </div>

          {/* Destination Stop Input */}
          <StopSearchInput
            label="Where are you going?"
            placeholder="Search stop or click map..."
            selectedStop={destStop}
            coordinateText={
              destCoord ? `${destCoord[0].toFixed(4)}, ${destCoord[1].toFixed(4)}` : ''
            }
            placeName={destPlaceName}
            onSelectStop={onSelectDestStop}
            onClear={onClearDest}
            badgeColor="text-rose-600"
            dotColor="bg-rose-600"
          />
        </div>
      </div>

      {/* Prominent Primary Accent Button: Plan Journey */}
      <div className="mt-4">
        <button
          type="submit"
          disabled={!isFormValid || loading}
          aria-label="Plan Journey & Search Bus Journeys"
          className={`w-full py-3.5 px-4 rounded-xl font-bold text-sm sm:text-base flex items-center justify-center space-x-2 shadow-sm transition-all ${
            !isFormValid || loading
              ? 'bg-slate-200 text-slate-400 cursor-not-allowed shadow-none'
              : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white shadow-md hover:shadow-lg active:scale-[0.99]'
          }`}
        >
          {loading ? (
            <>
              <span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></span>
              <span>Finding Best Buses...</span>
            </>
          ) : (
            <>
              <Search className="w-4 h-4" />
              <span>Plan Journey</span>
              <span className="sr-only">Search Bus Journeys</span>
            </>
          )}
        </button>
      </div>

      {/* Quick Corridor Demo Preset Links */}
      <div className="mt-3 flex flex-col space-y-1.5 text-xs px-1">
        <div className="flex items-center justify-between">
          <span className="text-slate-400 text-[11px] font-medium">Quick Live Corridors (Active Buses Now):</span>
          <button
            type="button"
            onClick={handleSetPresetNorthGtRoad}
            className="text-[11px] text-slate-500 hover:text-slate-700 hover:underline flex items-center space-x-1"
          >
            <Sparkles className="w-3 h-3 text-slate-400" />
            <span>North GT Road Corridor (Route 1598)</span>
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={handleSetPresetRoute641}
            className="text-[11px] bg-blue-50 hover:bg-blue-100 text-blue-700 font-semibold px-2.5 py-1 rounded-lg border border-blue-200/80 transition-colors flex items-center space-x-1 shadow-xs"
          >
            <span>⭐ Route 641: Ghuman Hera ➔ Janakpuri (30 Live Buses)</span>
          </button>
          <button
            type="button"
            onClick={handleSetPresetRoute3475}
            className="text-[11px] bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-semibold px-2.5 py-1 rounded-lg border border-emerald-200/80 transition-colors flex items-center space-x-1 shadow-xs"
          >
            <span>⭐ Route 3475: Ghuman Hera ➔ Najafgarh (17 Live Buses)</span>
          </button>
        </div>
      </div>

      {/* Options & Travel Preferences (Collapsible for clean UI) */}
      <div className="mt-3 pt-3 border-t border-slate-100">
        <details className="group">
          <summary className="text-xs font-semibold text-slate-500 hover:text-slate-800 cursor-pointer list-none flex items-center justify-between py-1 transition-colors">
            <span className="flex items-center space-x-1.5">
              <Settings2 className="w-3.5 h-3.5 text-slate-400" />
              <span>Routing & Safeguard Controls</span>
            </span>
            <span className="text-[10px] text-blue-600 group-open:rotate-180 transition-transform">
              ▼
            </span>
          </summary>

          <div className="mt-3 space-y-3 bg-slate-50/70 p-3 rounded-xl border border-slate-200/80 text-xs">
            {/* Date & Time with Reset to Live Button */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-semibold text-slate-700 uppercase tracking-wider">
                  Departure Time (IST)
                </span>
                <button
                  type="button"
                  onClick={handleResetToLive}
                  className="text-[11px] font-medium text-blue-700 hover:text-blue-900 bg-blue-50 hover:bg-blue-100 border border-blue-200 px-2 py-0.5 rounded-md transition-colors flex items-center space-x-1"
                  title="Reset to current device local date and time in Asia/Kolkata"
                >
                  <Clock className="w-3 h-3 text-blue-600" />
                  <span>Reset to Live</span>
                </button>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] text-slate-500 font-medium mb-1">
                    Date
                  </label>
                  <input
                    type="date"
                    value={departureDate}
                    onChange={(e) => setDepartureDate(e.target.value)}
                    className="w-full px-2.5 py-1.5 text-xs bg-white border border-slate-200 rounded-lg shadow-xs focus:ring-2 focus:ring-blue-500 focus:outline-none text-slate-800"
                  />
                </div>

                <div>
                  <label className="block text-[10px] text-slate-500 font-medium mb-1">
                    Time
                  </label>
                  <input
                    type="time"
                    step="1"
                    value={departureTime}
                    onChange={(e) => setDepartureTime(e.target.value)}
                    className="w-full px-2.5 py-1.5 text-xs bg-white border border-slate-200 rounded-lg shadow-xs focus:ring-2 focus:ring-blue-500 focus:outline-none text-slate-800"
                  />
                </div>
              </div>
            </div>

            {/* Walking Radius & Transfers */}
            <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-200/60">
              <div>
                <label className="block text-[10px] text-slate-500 font-medium mb-1 flex items-center space-x-1">
                  <Footprints className="w-3 h-3 text-slate-400" />
                  <span>Max Walk ({maxWalkingM}m)</span>
                </label>
                <select
                  value={maxWalkingM}
                  onChange={(e) => setMaxWalkingM(Number(e.target.value))}
                  className="w-full p-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 focus:ring-1 focus:ring-blue-500"
                >
                  <option value={400}>400m (~5 min)</option>
                  <option value={800}>800m (~10 min)</option>
                  <option value={1200}>1,200m (~15 min)</option>
                  <option value={1500}>1,500m (~20 min)</option>
                </select>
              </div>

              <div>
                <label className="block text-[10px] text-slate-500 font-medium mb-1 flex items-center space-x-1">
                  <Shuffle className="w-3 h-3 text-slate-400" />
                  <span>Max Transfers</span>
                </label>
                <select
                  value={maxTransfers}
                  onChange={(e) => setMaxTransfers(Number(e.target.value))}
                  className="w-full p-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 focus:ring-1 focus:ring-blue-500"
                >
                  <option value={0}>0 (Direct bus only)</option>
                  <option value={1}>1 transfer</option>
                  <option value={2}>2 transfers</option>
                  <option value={3}>3 transfers</option>
                </select>
              </div>
            </div>

            {/* Ranking Strategy */}
            <div>
              <label className="block text-[10px] text-slate-500 font-medium mb-1">
                Ranking Criteria
              </label>
              <select
                value={rankingStrategy}
                onChange={(e) => setRankingStrategy(e.target.value as any)}
                className="w-full p-1.5 bg-white border border-slate-200 rounded-lg text-xs text-slate-800 focus:ring-1 focus:ring-blue-500"
              >
                <option value="earliest_arrival">Earliest Arrival Time (Default)</option>
                <option value="fewest_transfers">Fewest Transfers</option>
                <option value="least_walking">Minimum Walking</option>
                <option value="most_reliable">Most Reliable (Observed Traffic)</option>
              </select>
            </div>

            {/* Safeguards & Opt-ins */}
            <div className="pt-2 border-t border-slate-200/60 space-y-1.5">
              <label className="flex items-start space-x-2 cursor-pointer text-[11px]">
                <input
                  type="checkbox"
                  checked={allowAssumedRecurring}
                  onChange={(e) => setAllowAssumedRecurring(e.target.checked)}
                  className="mt-0.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-slate-600">
                  <strong>Assumed Recurring Mode:</strong> Acknowledge 2024 expired static GTFS.
                </span>
              </label>

              <label className="flex items-start space-x-2 cursor-pointer text-[11px]">
                <input
                  type="checkbox"
                  checked={useExperimentalMl}
                  onChange={(e) => setUseExperimentalMl(e.target.checked)}
                  className="mt-0.5 rounded border-slate-300 text-purple-600 focus:ring-purple-500"
                />
                <span className="text-slate-600">
                  <span className="text-purple-700 font-semibold">[Experimental]</span> Enable Random Forest Candidate ML Predictions (disabled by default; negative out-of-fold generalization).
                </span>
              </label>
            </div>
          </div>
        </details>
      </div>
    </form>
  );
};
