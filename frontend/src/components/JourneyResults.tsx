import React from 'react';
import { Route, AlertCircle, Compass } from 'lucide-react';
import { JourneyAlternative } from '../types/api';
import { JourneyCard } from './JourneyCard';

interface JourneyResultsProps {
  journeys: JourneyAlternative[];
  selectedIndex: number;
  onSelectJourney: (idx: number) => void;
  loading: boolean;
  searched: boolean;
  staleWarning?: string | null;
  onLocatePickupBuses?: () => void;
}

export const JourneyResults: React.FC<JourneyResultsProps> = ({
  journeys,
  selectedIndex,
  onSelectJourney,
  loading,
  searched,
  staleWarning,
  onLocatePickupBuses,
}) => {
  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200/90 p-6 text-center space-y-3 shadow-xs">
        <div className="animate-spin rounded-full h-8 w-8 border-3 border-blue-600 border-t-transparent mx-auto"></div>
        <p className="text-sm font-semibold text-slate-800">
          Finding Optimal Bus Connections...
        </p>
        <p className="text-xs text-slate-400">
          Evaluating RAPTOR transit schedules, walking connections, and real-time buses
        </p>
      </div>
    );
  }

  if (!searched) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200/90 p-8 text-center text-slate-500 space-y-2 shadow-xs">
        <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 mx-auto flex items-center justify-center">
          <Compass className="w-6 h-6" />
        </div>
        <h3 className="font-bold text-slate-800 text-sm">Ready to Plan</h3>
        <p className="text-xs text-slate-400 max-w-xs mx-auto">
          Enter your start and destination or click anywhere on the Delhi map to find the best bus routes.
        </p>
      </div>
    );
  }

  if (journeys.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-amber-200 p-6 text-center space-y-2 shadow-xs">
        <AlertCircle className="w-8 h-8 text-amber-500 mx-auto" />
        <h3 className="font-bold text-slate-800 text-sm">No Journeys Found</h3>
        <p className="text-xs text-slate-500 max-w-sm mx-auto">
          No transit connection satisfied your maximum transfer and walking distance limits for this departure time. Try increasing max walking distance or transfers.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1">
        <h2 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center space-x-1.5">
          <Route className="w-3.5 h-3.5 text-blue-600" />
          <span>Available Journeys ({journeys.length})</span>
        </h2>
        <span className="text-[11px] text-slate-400 font-medium">
          Ranked by arrival time
        </span>
      </div>

      {staleWarning && (
        <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start space-x-2">
          <span className="font-semibold uppercase tracking-wider text-[10px] bg-amber-200/80 px-1.5 py-0.5 rounded text-amber-900 mt-0.5 shrink-0">
            Notice
          </span>
          <p className="text-xs leading-snug">{staleWarning}</p>
        </div>
      )}

      <div className="space-y-3">
        {journeys.map((journey, idx) => (
          <JourneyCard
            key={journey.journey_id || idx}
            journey={journey}
            index={idx}
            isSelected={selectedIndex === idx}
            onSelect={() => onSelectJourney(idx)}
            onLocatePickupBuses={onLocatePickupBuses}
          />
        ))}
      </div>
    </div>
  );
};
