import { describe, expect, it } from 'vitest';
import { screen, within } from '@testing-library/react';
import { renderApp } from './test-utils';

describe('Candidate Comparison page', () => {
  it('renders the comparison charts and table', async () => {
    await renderApp('/candidates');
    expect(await screen.findByText('Weighted RankIC (unitless)')).toBeInTheDocument();
    expect(screen.getByText('Weighted Spread (return)')).toBeInTheDocument();
    expect(screen.getByText('RankIC by horizon (mean)')).toBeInTheDocument();
    expect(screen.getByText('Spread by horizon (mean)')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: /candidate comparison metrics/i })).toBeInTheDocument();
  });

  it('defaults to Weighted RankIC descending with nulls last', async () => {
    await renderApp('/candidates');
    const table = await screen.findByRole('table', { name: /candidate comparison metrics/i });
    const rows = within(table).getAllByRole('row');
    // header + 4 data rows; fixture values: D2 0.0345 > D0 0.0123 > D1 -0.0234 > D3 null
    expect(rows[1]?.textContent).toContain('D2');
    expect(rows[2]?.textContent).toContain('D0');
    expect(rows[3]?.textContent).toContain('D1');
    expect(rows[4]?.textContent).toContain('D3');
  });

  it('formats RankIC as unitless and Spread as percentage', async () => {
    await renderApp('/candidates');
    const table = await screen.findByRole('table', { name: /candidate comparison metrics/i });
    const rows = within(table).getAllByRole('row');
    // D0: weightedRankIc 0.0123, weightedSpread 0.0456
    expect(rows[2]?.textContent).toContain('0.0123');
    expect(rows[2]?.textContent).toContain('4.56%');
    // null placeholder for D2's weighted spread
    expect(rows[1]?.textContent).toContain('—');
  });

  it('displays promotion status exactly as reported (never re-derived)', async () => {
    await renderApp('/candidates');
    expect((await screen.findAllByText('Further review')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Not promoted')).toBeInTheDocument();
    // D3 has promotionStatus = null → placeholder badge, not a derived value
    const table = screen.getByRole('table', { name: /candidate comparison metrics/i });
    expect(within(table).getAllByText('—').length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText(/winner|best strategy|approved|profitable/i)).toBeNull();
  });
});
