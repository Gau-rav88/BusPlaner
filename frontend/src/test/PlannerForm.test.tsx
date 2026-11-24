import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { PlannerForm } from '../components/PlannerForm';

describe('PlannerForm Component', () => {
  const defaultProps = {
    originStop: null,
    destStop: null,
    originCoord: null,
    destCoord: null,
    onSelectOriginStop: vi.fn(),
    onSelectDestStop: vi.fn(),
    onClearOrigin: vi.fn(),
    onClearDest: vi.fn(),
    onSubmit: vi.fn(),
    loading: false,
  };

  it('renders disabled submit button when endpoints are missing', () => {
    render(<PlannerForm {...defaultProps} />);
    const submitBtn = screen.getByRole('button', { name: /Search Bus Journeys/i });
    expect(submitBtn).toBeDisabled();
  });

  it('enables submit button when both origin and destination stops are selected', () => {
    render(
      <PlannerForm
        {...defaultProps}
        originStop={{ stop_id: '239', stop_name: 'ISBT Kashmere Gate', lat: 28.66, lon: 77.22 }}
        destStop={{ stop_id: '2024', stop_name: 'Narela Terminal', lat: 28.85, lon: 77.09 }}
      />
    );
    const submitBtn = screen.getByRole('button', { name: /Search Bus Journeys/i });
    expect(submitBtn).not.toBeDisabled();
  });

  it('swaps origin and destination when swap button is clicked', () => {
    const origin = { stop_id: '239', stop_name: 'Origin Stop', lat: 28.66, lon: 77.22 };
    const dest = { stop_id: '2024', stop_name: 'Dest Stop', lat: 28.85, lon: 77.09 };

    render(
      <PlannerForm
        {...defaultProps}
        originStop={origin}
        destStop={dest}
      />
    );

    const swapBtn = screen.getByTitle('Swap Origin and Destination');
    fireEvent.click(swapBtn);

    expect(defaultProps.onSelectOriginStop).toHaveBeenCalledWith(dest);
    expect(defaultProps.onSelectDestStop).toHaveBeenCalledWith(origin);
  });

  it('constructs correct payload on form submission', () => {
    const origin = { stop_id: '239', stop_name: 'ISBT Kashmere Gate', lat: 28.66, lon: 77.22 };
    const dest = { stop_id: '2024', stop_name: 'Narela Terminal', lat: 28.85, lon: 77.09 };
    const onSubmit = vi.fn();

    render(
      <PlannerForm
        {...defaultProps}
        originStop={origin}
        destStop={dest}
        onSubmit={onSubmit}
      />
    );

    const submitBtn = screen.getByRole('button', { name: /Search Bus Journeys/i });
    fireEvent.click(submitBtn);

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        origin_stop_id: '239',
        dest_stop_id: '2024',
        departure_date: expect.any(String),
        departure_time: expect.any(String),
        allow_assumed_recurring: true,
        use_experimental_ml: false,
      })
    );
  });

  it('resets date and time to live when Reset to Live is clicked', () => {
    const origin = { stop_id: '239', stop_name: 'A', lat: 28.66, lon: 77.22 };
    const dest = { stop_id: '2024', stop_name: 'B', lat: 28.85, lon: 77.09 };
    const onSubmit = vi.fn();

    render(
      <PlannerForm
        {...defaultProps}
        originStop={origin}
        destStop={dest}
        onSubmit={onSubmit}
      />
    );

    const resetBtn = screen.getByRole('button', { name: /Reset to Live/i });
    expect(resetBtn).toBeInTheDocument();
    fireEvent.click(resetBtn);

    const submitBtn = screen.getByRole('button', { name: /Search Bus Journeys/i });
    fireEvent.click(submitBtn);

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        departure_date: expect.any(String),
        departure_time: expect.any(String),
      })
    );
  });

  it('verifies experimental ML is disabled by default', () => {
    render(
      <PlannerForm
        {...defaultProps}
        originStop={{ stop_id: '239', stop_name: 'A', lat: 28.66, lon: 77.22 }}
        destStop={{ stop_id: '2024', stop_name: 'B', lat: 28.85, lon: 77.09 }}
      />
    );

    // Open advanced settings
    const toggleBtn = screen.getByText(/Routing & Safeguard Controls/i);
    fireEvent.click(toggleBtn);

    // Experimental ML checkbox
    const mlCheckbox = screen.getByRole('checkbox', { name: /Enable Random Forest Candidate ML/i });
    expect(mlCheckbox).not.toBeChecked();
  });
});

