import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Bus,
  Footprints,
  Clock,
  ArrowRight,
  AlertTriangle,
  Info,
  CheckCircle2,
  HelpCircle,
  Radio,
  Compass,
} from 'lucide-react';
import { JourneyAlternative, TransitLeg, WalkingLeg } from '../types/api';
import {
  formatSecondsToTime,
  formatDuration,
  formatDistance,
  formatPredictionTier,
  formatEpochToIST,
} from '../utils/formatters';

interface JourneyCardProps {
  journey: JourneyAlternative;
  index: number;
  isSelected: boolean;
  onSelect: () => void;
  onLocatePickupBuses?: () => void;
}

export const JourneyCard: React.FC<JourneyCardProps> = ({
  journey,
  index,
  isSelected,
  onSelect,
  onLocatePickupBuses,
}) => {
  const [expanded, setExpanded] = useState(false);

  const { accounting, legs } = journey;

  // Proportional accounting bar segments
  const totalS = journey.total_journey_duration_s || 1;
  const accessPct = ((accounting.access_walking_time_s / totalS) * 100).toFixed(1);
  const waitPct = (((accounting.initial_waiting_time_s + accounting.transfer_waiting_time_s) / totalS) * 100).toFixed(1);
  const ridePct = ((accounting.in_vehicle_duration_s / totalS) * 100).toFixed(1);
  const transWalkPct = ((accounting.transfer_walking_time_s / totalS) * 100).toFixed(1);
  const egressPct = ((accounting.egress_walking_time_s / totalS) * 100).toFixed(1);

  // Identify dominant transit prediction tier
  const transitLegs = legs.filter((l): l is TransitLeg => l.leg_type === 'TRANSIT');
  const dominantTier = transitLegs[0]?.prediction_tier || 'LEVEL_4_GTFS_SCHEDULED';
  const tierInfo = formatPredictionTier(dominantTier);
  const primaryTransit = transitLegs[0];

  return (
    <div
      onClick={onSelect}
      className={`bg-white rounded-2xl border transition-all cursor-pointer shadow-xs hover:shadow-md ${
        isSelected
          ? 'border-blue-600 ring-2 ring-blue-500/20 shadow-md'
          : 'border-slate-200/90 hover:border-slate-300'
      }`}
    >
      {/* Transit App Inspired Trip Header Card */}
      <div className="p-4 sm:p-5">
        {/* Top Row: Departure & Arrival + Prominent Duration */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center space-x-2 text-sm text-slate-800 font-semibold">
              <span className="text-slate-400 font-normal text-xs">Leave at</span>
              <span>{formatSecondsToTime(journey.departure_time_s)}</span>
              <span className="text-slate-300">&bull;</span>
              <span className="text-slate-400 font-normal text-xs">Arrive</span>
              <span>{formatSecondsToTime(journey.arrival_time_s)}</span>
            </div>

            <div className="mt-1 flex items-center space-x-2">
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 font-mono">
                Option {index + 1}
              </span>
              <span
                className={`text-[11px] px-2 py-0.5 rounded-md font-semibold ${
                  journey.num_transfers === 0
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-blue-50 text-blue-700 border border-blue-200'
                }`}
              >
                {journey.num_transfers === 0
                  ? 'Direct Bus'
                  : `${journey.num_transfers} Transfer${journey.num_transfers > 1 ? 's' : ''}`}
              </span>
            </div>
          </div>

          <div className="text-right">
            <span className="text-xl font-extrabold text-slate-900 tracking-tight">
              {formatDuration(journey.total_journey_duration_s)}
            </span>
          </div>
        </div>

        {/* Prominent Visual Bus Recommendation (Which bus should I take?) */}
        {primaryTransit && (
          <div className="mt-3.5 p-3.5 bg-blue-50/70 border border-blue-100 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <div className="bg-blue-600 text-white font-extrabold px-2.5 py-1 rounded-lg text-sm tracking-wide shadow-xs">
                  Bus {primaryTransit.route_id}
                </div>
                <div className="text-xs font-semibold text-slate-800 truncate max-w-[200px]">
                  {primaryTransit.alight_stop_name
                    ? `Towards ${primaryTransit.alight_stop_name}`
                    : 'Scheduled Bus'}
                </div>
              </div>
              <span className="text-xs font-bold text-blue-900">
                {formatDuration(primaryTransit.ride_duration_s)} ride
              </span>
            </div>

            {/* Boarding and Alighting Points for Passenger Quick Reference */}
            <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
              <div className="text-slate-600 truncate">
                <span className="text-slate-400 font-medium">From: </span>
                <span className="font-semibold text-slate-800">{primaryTransit.board_stop_name}</span>
              </div>
              <div className="text-slate-600 text-right truncate">
                <span className="text-slate-400 font-medium">To: </span>
                <span className="font-semibold text-slate-800">{primaryTransit.alight_stop_name}</span>
              </div>
            </div>

            {/* Quick Action: See Buses Coming to Pick You Up */}
            {isSelected && onLocatePickupBuses && (
              <div className="pt-2 border-t border-blue-100">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onLocatePickupBuses();
                  }}
                  className="w-full py-2 px-3 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white flex items-center justify-center space-x-1.5 shadow-xs transition-colors cursor-pointer"
                >
                  <Compass className="w-3.5 h-3.5 text-amber-300 animate-pulse" />
                  <span>See Buses Coming to Pick You Up</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* Visual Progress / Accounting Bar */}
        <div className="mt-3">
          <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden flex">
            {Number(accessPct) > 0 && (
              <div
                style={{ width: `${accessPct}%` }}
                className="bg-blue-400"
                title={`Access Walk: ${formatDuration(accounting.access_walking_time_s)}`}
              />
            )}
            {Number(waitPct) > 0 && (
              <div
                style={{ width: `${waitPct}%` }}
                className="bg-slate-300"
                title={`Wait at Stop: ${formatDuration(accounting.initial_waiting_time_s + accounting.transfer_waiting_time_s)}`}
              />
            )}
            {Number(ridePct) > 0 && (
              <div
                style={{ width: `${ridePct}%` }}
                className="bg-blue-600"
                title={`In-Vehicle Bus Ride: ${formatDuration(accounting.in_vehicle_duration_s)}`}
              />
            )}
            {Number(transWalkPct) > 0 && (
              <div
                style={{ width: `${transWalkPct}%` }}
                className="bg-orange-400"
                title={`Transfer Walk: ${formatDuration(accounting.transfer_walking_time_s)}`}
              />
            )}
            {Number(egressPct) > 0 && (
              <div
                style={{ width: `${egressPct}%` }}
                className="bg-blue-400"
                title={`Egress Walk: ${formatDuration(accounting.egress_walking_time_s)}`}
              />
            )}
          </div>
        </div>

        {/* Prediction Source & Confidence Tag */}
        <div className="mt-2.5 pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-1.5">
          <span className={`text-[11px] px-2 py-0.5 rounded-md border font-medium ${tierInfo.badgeClass}`}>
            {tierInfo.shortLabel}
          </span>
          <span
            className="text-[11px] text-slate-500 bg-slate-50 px-2 py-0.5 rounded-md border border-slate-200"
            title="Heuristic quality score based on empirical data depth. NOT a statistical probability."
          >
            Confidence: {(journey.heuristic_confidence_score * 100).toFixed(0)}% (Heuristic)
          </span>
        </div>

        {/* Long Transfer Wait Advisory */}
        {(journey.long_transfer_advisory || journey.has_long_transfer_wait || accounting.transfer_waiting_time_s > 7200) && (
          <div className="mt-3 p-2.5 bg-orange-50 border border-orange-200 rounded-xl text-xs text-orange-900 flex items-start space-x-2">
            <Clock className="w-4 h-4 text-orange-600 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <span className="font-bold block text-xs text-orange-800">
                Extended Transfer Wait Advisory
              </span>
              <p className="text-[11px] leading-snug text-orange-950">
                {journey.long_transfer_advisory ||
                  `Transfer wait is ${formatDuration(accounting.transfer_waiting_time_s)} (${(accounting.transfer_waiting_time_s / 3600).toFixed(1)} hours). This connection has a long scheduled wait between connecting bus services. Consider comparing other available journey options or selecting a different departure time.`}
              </p>
            </div>
          </div>
        )}

        {/* Stale Timetable Warning Badge if applicable */}
        {journey.warnings.length > 0 && !journey.warnings[0].startsWith('Extended transfer wait time') && (
          <div className="mt-2.5 p-2 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start space-x-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
            <span className="text-[11px] leading-snug">
              {journey.warnings[0]}
            </span>
          </div>
        )}

        {/* Advanced Technical Telemetry Details (Collapsible by default) */}
        <div className="mt-3 pt-2 border-t border-slate-100">
          <details className="group">
            <summary className="text-[11px] font-semibold text-slate-400 hover:text-slate-700 cursor-pointer list-none flex items-center justify-between py-1 transition-colors">
              <span>View Technical & Telemetry Details</span>
              <span className="text-[10px] text-blue-600 group-open:rotate-180 transition-transform">▼</span>
            </summary>
            <div className="mt-2 pt-2 border-t border-slate-100 space-y-2">
              <div className="text-[10px] text-slate-500 font-mono">
                Duration Accounting &amp; Identity Valid: {accounting.is_valid_identity ? 'Yes' : 'No'}
              </div>

              {/* Time Legend Breakdown */}
              <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1">
                <span>Ride: {formatDuration(accounting.in_vehicle_duration_s)}</span>
                <span>Walk: {formatDuration(accounting.access_walking_time_s + accounting.transfer_walking_time_s + accounting.egress_walking_time_s)}</span>
                <span>Wait: {formatDuration(accounting.initial_waiting_time_s + accounting.transfer_waiting_time_s)}</span>
              </div>
            </div>
          </details>
        </div>
      </div>

      {/* Expand / Collapse Step-by-Step Route Button */}
      <div className="px-4 sm:px-5 py-2.5 bg-slate-50/70 border-t border-slate-100 flex items-center justify-between rounded-b-2xl">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setExpanded(!expanded);
          }}
          className="text-xs text-blue-600 hover:text-blue-800 font-semibold flex items-center space-x-1"
        >
          <span>{expanded ? 'Hide Step-by-Step Route' : 'View Step-by-Step Route'}</span>
          {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
        <span className="text-[11px] text-slate-400 font-medium">
          {legs.length} segment{legs.length > 1 ? 's' : ''}
        </span>
      </div>

      {/* Expanded Segment Details */}
      {expanded && (
        <div className="p-4 sm:p-5 border-t border-slate-200 bg-slate-50/40 space-y-3">
          {legs.map((leg, lIdx) => {
            if (leg.leg_type === 'TRANSIT') {
              const legTierInfo = formatPredictionTier(leg.prediction_tier);
              return (
                <div key={lIdx} className="bg-white p-3.5 rounded-xl border border-slate-200 text-xs shadow-xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className="bg-blue-50 text-blue-700 p-1.5 rounded-lg border border-blue-200">
                        <Bus className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="font-bold text-slate-900 text-sm">
                          Route {leg.route_id}
                        </div>
                        <div className="text-slate-400 text-[10px] font-mono">
                          Trip: {leg.trip_id}
                        </div>
                      </div>
                    </div>
                    <span className="font-bold text-slate-800">
                      {formatDuration(leg.ride_duration_s)}
                    </span>
                  </div>

                  {/* Boarding and Alighting Info */}
                  <div className="mt-3 space-y-1.5 pl-3 border-l-2 border-blue-500 ml-2">
                    <div>
                      <div className="font-semibold text-slate-800">
                        Board: {leg.board_stop_name}
                      </div>
                      <div className="text-[11px] text-slate-500">
                        Departs: {formatSecondsToTime(leg.board_time_s)} (Sched: {formatSecondsToTime(leg.sched_departure_s)})
                      </div>
                    </div>

                    <div className="text-[11px] text-slate-400 italic">
                      Traversing {leg.intermediate_stops.length} intermediate stops
                    </div>

                    <div>
                      <div className="font-semibold text-slate-800">
                        Alight: {leg.alight_stop_name}
                      </div>
                      <div className="text-[11px] text-slate-500">
                        Arrives: {formatSecondsToTime(leg.alight_time_s)} (Sched: {formatSecondsToTime(leg.sched_arrival_s)})
                      </div>
                    </div>
                  </div>

                  {/* Live Bus Guidance Section */}
                  <div className="mt-3 p-2.5 rounded-xl border bg-slate-50/80 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-1.5 font-bold text-xs">
                        <Radio className="w-3.5 h-3.5 text-blue-600 animate-pulse" />
                        <span className="text-slate-800">Live Bus to Board</span>
                      </div>

                      {/* Status Badges */}
                      {leg.live_bus?.identification_status === 'IDENTIFIED_NEAR' ? (
                        <span className="flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          <span>Near Boarding Stop (~{Math.round(leg.live_bus.distance_to_board_m || 0)}m)</span>
                        </span>
                      ) : leg.live_bus?.identification_status === 'IDENTIFIED_APPROACHING' ? (
                        <span className="flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-100 text-blue-800 border border-blue-300">
                          <CheckCircle2 className="w-3 h-3 text-blue-600" />
                          <span>
                            Approaching (~{((leg.live_bus.distance_to_board_m || 0) / 1000).toFixed(1)} km, {leg.live_bus.stops_away} stop{leg.live_bus.stops_away !== 1 ? 's' : ''} away)
                          </span>
                        </span>
                      ) : leg.live_bus?.identification_status === 'ROUTE_MATCH_UNVERIFIED' ? (
                        <span className="flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-50 text-amber-800 border border-amber-300">
                          <HelpCircle className="w-3 h-3 text-amber-600" />
                          <span>Route matches — direction unverified</span>
                        </span>
                      ) : (
                        <span className="flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-normal bg-slate-100 text-slate-600 border border-slate-200">
                          <Info className="w-3 h-3 text-slate-400" />
                          <span>Live bus not identified</span>
                        </span>
                      )}
                    </div>

                    {/* Guidance Message Banner */}
                    <div className="text-[11px] leading-relaxed text-slate-700 bg-white p-2.5 rounded-lg border border-slate-200">
                      <p className="font-medium text-slate-900">
                        {leg.live_bus?.guidance_message ||
                          'Live bus not identified — follow the scheduled route and verify the displayed route at the stop.'}
                      </p>

                      {/* Vehicle Telemetry Details if Identified */}
                      {(leg.live_bus?.identification_status === 'IDENTIFIED_NEAR' ||
                        leg.live_bus?.identification_status === 'IDENTIFIED_APPROACHING') && (
                        <div className="mt-1.5 pt-1.5 border-t border-slate-100 grid grid-cols-2 gap-x-2 gap-y-0.5 text-[10px] text-slate-600">
                          <div>
                            <strong>Bus Reg / ID:</strong>{' '}
                            <span className="font-mono font-bold text-blue-800">{leg.live_bus.vehicle_id}</span>
                          </div>
                          <div>
                            <strong>Destination:</strong> {leg.live_bus.trip_headsign || 'En route'}
                          </div>
                          <div>
                            <strong>Speed:</strong>{' '}
                            {leg.live_bus.speed_kmh !== null ? `${leg.live_bus.speed_kmh} km/h` : 'Stationary / N/A'}
                          </div>
                          <div>
                            <strong>Source Ping:</strong> {formatEpochToIST(leg.live_bus.source_timestamp_utc)} IST ({leg.live_bus.age_seconds}s ago)
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            } else {
              // Walking Leg
              const walkTypeLabel =
                leg.leg_type === 'ACCESS'
                  ? 'Access Walk to Stop'
                  : leg.leg_type === 'TRANSFER'
                  ? 'Transfer Walk'
                  : leg.leg_type === 'EGRESS'
                  ? 'Egress Walk to Destination'
                  : 'Direct Walk';

              return (
                <div key={lIdx} className="bg-white p-3 rounded-xl border border-slate-200 text-xs flex items-center justify-between shadow-xs">
                  <div className="flex items-center space-x-2.5">
                    <div className="bg-slate-100 text-slate-600 p-1.5 rounded-lg">
                      <Footprints className="w-3.5 h-3.5" />
                    </div>
                    <div>
                      <div className="font-semibold text-slate-800">
                        {walkTypeLabel}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {leg.from_name} <ArrowRight className="w-3 h-3 inline text-slate-300" /> {leg.to_name}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-slate-800">
                      {formatDuration(leg.duration_s)}
                    </div>
                    <div className="text-[10px] text-slate-400">
                      {formatDistance(leg.distance_m)}
                    </div>
                  </div>
                </div>
              );
            }
          })}
        </div>
      )}
    </div>
  );
};
