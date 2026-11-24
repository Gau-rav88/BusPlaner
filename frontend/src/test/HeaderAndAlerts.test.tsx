import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Header } from '../components/Header';
import { AlertBanner } from '../components/AlertBanner';

describe('Header and AlertBanner Components', () => {
  it('renders operational status badge DEGRADE, live feed status, and unverified operations disclaimer', () => {
    render(
      <Header
        health={{
          application_status: 'ok',
          backend_version: '1.0.0',
          database_available: true,
          gtfs_loaded: true,
          overall_operational_status: 'DEGRADE',
          live_feed_status: 'AUTH_REQUIRED',
          live_feed_enabled: false,
          timestamp_utc: '2026-11-21T10:00:00Z',
        }}
        timetableStatus={{
          timetable_status: 'ASSUMED_RECURRING',
          feed_start_date: '2022-01-01',
          feed_end_date: '2024-01-01',
          feed_provenance: 'Delhi Transport Stack',
          is_date_within_feed_validity: false,
          actual_operations_verified: false,
          demonstration_mode_available: true,
          service_date_evaluated: '2026-10-01',
          warnings: ['STALE TIMETABLE WARNING'],
        }}
        loading={false}
      />
    );

    expect(screen.getByText('DEGRADE')).toBeInTheDocument();
    expect(screen.getByText(/Live Operations: Unverified/i)).toBeInTheDocument();
    expect(screen.getByText(/Timetable: ASSUMED_RECURRING/i)).toBeInTheDocument();
    expect(screen.getByText(/Live Feed: Auth Required \(Disabled\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Operational Notice:/i)).toBeInTheDocument();
  });

  it('renders AlertBanner with actionable retry button', () => {
    const handleAction = vi.fn();
    render(
      <AlertBanner
        type="error"
        title="Timetable Expired"
        message="Service date is outside feed validity."
        actionLabel="Enable Demonstration Mode"
        onAction={handleAction}
      />
    );

    expect(screen.getByText('Timetable Expired')).toBeInTheDocument();
    expect(screen.getByText('Service date is outside feed validity.')).toBeInTheDocument();
    const actionBtn = screen.getByRole('button', { name: /Enable Demonstration Mode/i });
    expect(actionBtn).toBeInTheDocument();
  });
});

