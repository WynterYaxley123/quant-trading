import { describe, expect, it } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderApp } from './test-utils';

describe('Development Explorer page', () => {
  it('renders the E001-E003 series chart and table', async () => {
    const router = await renderApp('/development');
    expect(await screen.findByText(/metric series by signal date/i)).toBeInTheDocument();
    const summary = await screen.findByRole('img', { name: /line chart of rankic/i });
    expect(summary).toHaveAttribute('aria-label', expect.stringContaining('horizon 10'));
    const table = screen.getByRole('table', { name: /development series values/i });
    expect(within(table).getAllByRole('row').length).toBe(4); // header + 3 dates
    expect(router.state.location.pathname).toBe('/development');
  });

  it('keeps explorer state in the URL (candidate, metric, horizon)', async () => {
    const router = await renderApp('/development');
    await screen.findByRole('table', { name: /development series values/i });

    await userEvent.selectOptions(screen.getByLabelText('Candidate'), 'D2');
    await userEvent.selectOptions(screen.getByLabelText('Metric'), 'top5MinusUniverse');
    await userEvent.selectOptions(screen.getByLabelText('Horizon'), '40');

    await screen.findByRole('table', { name: /development series values/i });
    expect(router.state.location.search).toMatchObject({
      candidate: 'D2',
      metric: 'top5MinusUniverse',
      horizon: '40',
    });
  });

  it('switches the displayed metric with correct unit formatting', async () => {
    await renderApp('/development');
    const table = await screen.findByRole('table', { name: /development series values/i });
    expect(within(table).getByRole('columnheader', { name: /rankic/i })).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText('Metric'), 'top5ForwardReturn');
    const updated = await screen.findByRole('table', { name: /development series values/i });
    expect(within(updated).getByRole('columnheader', { name: /top5 forward return/i })).toBeInTheDocument();
    // return metrics render as percentages
    expect(updated.textContent).toMatch(/-?\d+\.\d{2}%/);
  });
});
