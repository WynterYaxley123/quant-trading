import { describe, expect, it } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderApp } from './test-utils';

describe('Sector Explorer page', () => {
  it('lists one row per sector with fused rank default ascending', async () => {
    await renderApp('/sectors');
    const table = await screen.findByRole('table', { name: /sector predictions/i });
    const rows = within(table).getAllByRole('row');
    expect(rows.length).toBe(11); // header + 10 synthetic sectors
    expect(rows[1]?.textContent).toContain('SYNTHETIC SECTOR A'); // rank 1 first
    expect(rows[10]?.textContent).toContain('SYNTHETIC SECTOR J'); // rank 10 last
  });

  it('marks Top5 rows clearly but not overwhelmingly', async () => {
    await renderApp('/sectors');
    const table = await screen.findByRole('table', { name: /sector predictions/i });
    const rows = within(table).getAllByRole('row');
    const top5Rows = rows.slice(1, 6);
    const rest = rows.slice(6);
    for (const row of top5Rows) expect(row.textContent).toContain('Top5');
    for (const row of rest) expect(row.textContent).not.toContain('Top5');
  });

  it('falls back to sectorCode when sectorName is null (no name lookups)', async () => {
    await renderApp('/sectors');
    const table = await screen.findByRole('table', { name: /sector predictions/i });
    // fixture rows with sectorName=null: 801774 and 801779
    const row = within(table)
      .getAllByRole('row')
      .find((r) => r.textContent?.includes('801774'));
    expect(row).toBeDefined();
    expect(row?.textContent).toContain('801774');
    expect(row?.textContent).not.toContain('SYNTHETIC SECTOR D');
  });

  it('sorts when a column header is activated', async () => {
    await renderApp('/sectors');
    const table = await screen.findByRole('table', { name: /sector predictions/i });
    await userEvent.click(within(table).getByRole('button', { name: /^rank/i }));
    const rows = within(table).getAllByRole('row');
    expect(rows[1]?.textContent).toContain('SYNTHETIC SECTOR J'); // ascending → descending toggle
  });

  it('opens a detail panel that separates predictions from realized returns', async () => {
    await renderApp('/sectors');
    const table = await screen.findByRole('table', { name: /sector predictions/i });
    await userEvent.click(within(table).getAllByRole('row')[1] as HTMLElement);
    expect(await screen.findByText(/prediction ≠ realized return/i)).toBeInTheDocument();
    expect(screen.getByText(/predictions \(model output\)/i)).toBeInTheDocument();
    expect(screen.getByText(/realized forward returns/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /buy|sell|strong buy/i })).toBeNull();
  });
});
