import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderApp } from './test-utils';

describe('Diagnostics page', () => {
  it('shows attempted / successful / skipped date counters in plain language', async () => {
    await renderApp('/diagnostics');
    expect(await screen.findByText('Attempted dates')).toBeInTheDocument();
    expect(screen.getByText('Successful dates')).toBeInTheDocument();
    expect(screen.getByText('Skipped dates')).toBeInTheDocument();
    expect(screen.getByText('Issue summary')).toBeInTheDocument();
    expect(screen.getByText(/flagged/)).toBeInTheDocument();
  });

  it('shows per-horizon training summary and expands full issue details', async () => {
    await renderApp('/diagnostics');
    expect(await screen.findByText('Horizon 10')).toBeInTheDocument();
    expect(screen.getByText('Horizon 40')).toBeInTheDocument();
    expect(screen.getByText('Horizon 120')).toBeInTheDocument();
    expect(screen.getAllByText('Training observations').length).toBe(3);

    // Real warnings are hidden behind details but never removed — expand horizon 10.
    const triggers = screen.getAllByRole('button', { name: /details/i });
    await userEvent.click(triggers[0] as HTMLElement);
    expect(await screen.findByText('Missing factor exclusions')).toBeInTheDocument();
    expect(screen.getByText('Missing label exclusions')).toBeInTheDocument();
    expect(screen.getByText('Numerical failures')).toBeInTheDocument();
    expect(screen.getByText('Insufficient training cases')).toBeInTheDocument();
    expect(screen.getAllByText(/affected/).length).toBeGreaterThanOrEqual(1);
  });

  it('explains zero-std and demean-residual diagnostics', async () => {
    await renderApp('/diagnostics');
    const triggers = await screen.findAllByRole('button', { name: /details/i });
    await userEvent.click(triggers[0] as HTMLElement);
    expect(await screen.findByText('Zero-std feature occurrences')).toBeInTheDocument();
    expect(screen.getByText(/D1\/D3/)).toBeInTheDocument();
    expect(screen.getByText('Demean residual max |mean|')).toBeInTheDocument();
  });
});
