import React, { useState } from 'react';
import { Bus, ChevronDown, ChevronUp, Activity, Calendar, ShieldAlert } from 'lucide-react';
import { HealthResponse, TimetableStatusResponse } from '../types/api';

interface HeaderProps {
  health: HealthResponse | null;
  timetableStatus: TimetableStatusResponse | null;
  loading: boolean;
}

export const Header: React.FC<HeaderProps> = ({ health, timetableStatus, loading }) => {
  const [showStatusDetails, setShowStatusDetails] = useState(false);
  const isHealthy = health?.application_status === 'ok';
  const statusVerdict = health?.overall_operational_status || 'DEGRADE';

  return (
    <header className="bg-white border-b border-slate-200 shadow-xs z-30 relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-2.5 flex items-center justify-between">
        {/* Brand & Logo inspired by Transit App */}
        <div className="flex items-center space-x-3">
          <div className="bg-blue-600 w-9 h-9 rounded-xl text-white shadow-sm flex items-center justify-center font-bold">
            <Bus className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-lg font-bold tracking-tight text-slate-900">
                Delhi Transit
              </span>
              <span className="px-1.5 py-0.5 text-[10px] font-bold rounded-md bg-blue-50 text-blue-700 border border-blue-200 tracking-wider">
                LIVE
              </span>
              <span className="px-2 py-0.5 text-xs font-semibold rounded bg-amber-50 text-amber-700 border border-amber-300">
                {statusVerdict}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden sm:block">
              Real-time bus tracking and journey planner for Delhi
            </p>
          </div>
        </div>

        {/* Unobtrusive System Status Pill */}
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={() => setShowStatusDetails(!showStatusDetails)}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full border border-slate-200 bg-slate-50 hover:bg-slate-100 text-xs font-medium text-slate-700 transition-colors"
            title="Toggle system status details"
          >
            <span
              className={`w-2 h-2 rounded-full ${
                health?.live_feed_status === 'AVAILABLE_VALIDATED'
                  ? 'bg-emerald-500'
                  : 'bg-amber-500'
              }`}
            />
            <span className="hidden sm:inline">System:</span>
            <span className="font-semibold text-slate-900">Status</span>
            {showStatusDetails ? (
              <ChevronUp className="w-3.5 h-3.5 text-slate-400" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            )}
          </button>
        </div>
      </div>

      {/* Expandable / Collapsible System Information Strip */}
      <div
        className={`${
          showStatusDetails ? 'block' : 'hidden'
        } bg-slate-50/90 border-t border-slate-200 px-4 py-2 text-xs transition-all`}
      >
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            {/* Backend Health Badge */}
            <div
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full border ${
                loading
                  ? 'bg-slate-100 text-slate-500 border-slate-200'
                  : isHealthy
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-rose-50 text-rose-700 border-rose-200'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>
                Backend: {loading ? 'Checking...' : isHealthy ? 'Healthy (v1.0)' : 'Degraded'}
              </span>
            </div>

            {/* Timetable Freshness Badge */}
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full border bg-amber-50 text-amber-700 border-amber-200">
              <Calendar className="w-3.5 h-3.5" />
              <span>
                Timetable: {timetableStatus?.timetable_status || 'ASSUMED_RECURRING'}
              </span>
            </div>

            {/* Live GTFS-RT Feed Status Badge */}
            <div
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full border ${
                health?.live_feed_status === 'AVAILABLE_VALIDATED'
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-slate-100 text-slate-600 border-slate-200'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>
                Live Feed:{' '}
                {health?.live_feed_status === 'AVAILABLE_VALIDATED'
                  ? 'Live Stream Active (4,900+ buses)'
                  : 'Auth Required (Disabled)'}
              </span>
            </div>

            {/* Operations Truth Badge */}
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full border bg-slate-100 text-slate-600 border-slate-200">
              <ShieldAlert className="w-3.5 h-3.5 text-slate-500" />
              <span>
                {health?.live_feed_status === 'AVAILABLE_VALIDATED'
                  ? 'Telemetry: GTFS-RT Live'
                  : 'Live Operations: Unverified'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Critical Truthfulness Notice Strip (Unobtrusive) */}
      <div className="bg-amber-50/70 border-t border-amber-200/60 px-4 py-1 text-[11px] text-amber-900/90 text-center">
        <span>
          <strong>Operational Notice:</strong>{' '}
          {health?.live_feed_status === 'AVAILABLE_VALIDATED'
            ? 'Live GTFS-RT stream connected via Delhi Transport Stack (~4,900 vehicles active; agency UNKNOWN_MIXED). Static GTFS feed expired 2024-01-01 (assumed recurring). Governing status: DEGRADE.'
            : 'Static GTFS feed expired 2024-01-01. Live GTFS-RT stream requires API key (disabled). 2026 routes evaluate historical recurring weekly patterns and North GT Road traffic models. Governing status: DEGRADE.'}
        </span>
      </div>
    </header>
  );
};
