import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { JourneyResults } from '../components/JourneyResults';
import { JourneyAlternative } from '../types/api';

const mockJourney: JourneyAlternative = {
  journey_id: 'journey_1',
  num_transfers: 0,
  departure_time_s: 45460, // 12:37 PM
  arrival_time_s: 47160, // 1:06 PM
  total_journey_duration_s: 1700,
  legs: [
    {
      leg_type: 'TRANSIT',
      route_id: '1598',
      trip_id: 'trip_1598_down_1237',
      pattern_id: 12,
      board_stop_id: '239',
      board_stop_name: 'ISBT Kashmere Gate',
      alight_stop_id: '2024',
      alight_stop_name: 'Narela Terminal',
      sched_departure_s: 45460,
      sched_arrival_s: 47160,
      sched_duration_s: 1700,
      board_time_s: 45460,
      alight_time_s: 47160,
      ride_duration_s: 1700,
      intermediate_stops: ['s1', 's2', 's3'],
      prediction_tier: 'LEVEL_1_DIRECT_OBSERVED',
      prediction_source: 'GROUND_TRUTH_OBSERVED',
      heuristic_confidence_score: 0.85,
      confidence_score_type: 'HEURISTIC',
      confidence_explanation: 'Heuristic score representing empirical data; NOT a probability.',
      is_fallback: false,
      timetable_status: 'ASSUMED_RECURRING',
      is_verified_current_service: false,
      warning: 'STALE TIMETABLE WARNING: schedule expired on 2024-01-01',
    },
  ],
  accounting: {
    access_walking_time_s: 0,
    initial_waiting_time_s: 0,
    in_vehicle_duration_s: 1700,
    transfer_walking_time_s: 0,
    transfer_waiting_time_s: 0,
    egress_walking_time_s: 0,
    total_duration_s: 1700,
    discrepancy_s: 0,
    is_valid_identity: true,
  },
  heuristic_confidence_score: 0.85,
  confidence_score_type: 'HEURISTIC',
  timetable_status: 'ASSUMED_RECURRING',
  is_verified_current_service: false,
  actual_operations_verified: false,
  warnings: ['STALE TIMETABLE WARNING: The underlying GTFS schedule expired on 2024-01-01.'],
};

describe('JourneyResults Component', () => {
  it('renders ready-to-plan state before user searches', () => {
    render(
      <JourneyResults
        journeys={[]}
        selectedIndex={0}
        onSelectJourney={vi.fn()}
        loading={false}
        searched={false}
      />
    );
    expect(screen.getByText(/Ready to Plan/i)).toBeInTheDocument();
  });

  it('renders empty state when no journeys found after search', () => {
    render(
      <JourneyResults
        journeys={[]}
        selectedIndex={0}
        onSelectJourney={vi.fn()}
        loading={false}
        searched={true}
      />
    );
    expect(screen.getByText(/No Journeys Found/i)).toBeInTheDocument();
  });

  it('renders journey alternative card with duration and times', () => {
    render(
      <JourneyResults
        journeys={[mockJourney]}
        selectedIndex={0}
        onSelectJourney={vi.fn()}
        loading={false}
        searched={true}
      />
    );

    // Verify duration and transfers
    expect(screen.getByText('28 min')).toBeInTheDocument();
    expect(screen.getByText('Direct Bus')).toBeInTheDocument();

    // Verify departure to arrival times
    expect(screen.getByText('12:37 PM')).toBeInTheDocument();
    expect(screen.getByText('1:06 PM')).toBeInTheDocument();

    // Verify prediction tier badge
    expect(screen.getByText(/Observed Traffic/i)).toBeInTheDocument();

    // Verify heuristic confidence
    expect(screen.getByText(/Confidence: 85% \(Heuristic\)/i)).toBeInTheDocument();

    // Verify stale timetable warning banner
    expect(screen.getByText(/STALE TIMETABLE WARNING/i)).toBeInTheDocument();
  });

  it('expands individual legs on button click', () => {
    render(
      <JourneyResults
        journeys={[mockJourney]}
        selectedIndex={0}
        onSelectJourney={vi.fn()}
        loading={false}
        searched={true}
      />
    );

    const expandBtn = screen.getByText(/View Step-by-Step Route/i);
    fireEvent.click(expandBtn);

    // Verify leg details are rendered
    expect(screen.getByText(/Route 1598/i)).toBeInTheDocument();
    expect(screen.getByText(/Board: ISBT Kashmere Gate/i)).toBeInTheDocument();
    expect(screen.getByText(/Alight: Narela Terminal/i)).toBeInTheDocument();
    expect(screen.getByText(/Traversing 3 intermediate stops/i)).toBeInTheDocument();
  });

  it('renders extended transfer wait advisory when transfer wait exceeds 7200s', () => {
    const longTransferJourney: JourneyAlternative = {
      ...mockJourney,
      accounting: {
        ...mockJourney.accounting,
        transfer_waiting_time_s: 26269.32,
      },
      has_long_transfer_wait: true,
      long_transfer_advisory: 'Extended transfer wait time: 26269s (7.3 hours). This connection has a long scheduled wait between connecting bus services. Consider comparing other available journey options or selecting a different departure time.',
    };

    render(
      <JourneyResults
        journeys={[longTransferJourney]}
        selectedIndex={0}
        onSelectJourney={vi.fn()}
        loading={false}
        searched={true}
      />
    );

    expect(screen.getByText(/Extended Transfer Wait Advisory/i)).toBeInTheDocument();
    expect(screen.getByText(/26269s \(7.3 hours\)/i)).toBeInTheDocument();
  });
});

