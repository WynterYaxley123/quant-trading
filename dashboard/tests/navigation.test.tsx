import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderApp } from './test-utils';

describe('Navigation', () => {
  it('contains exactly the research sections', async () => {
    await renderApp('/');
    const names = [
      'Overview',
      'Candidate Comparison',
      'Development Explorer',
      'Sector Explorer',
      'Diagnostics',
      'Research Integrity',
    ];
    for (const name of names) {
      expect(await screen.findByRole('link', { name })).toBeInTheDocument();
    }
  });

  it('never offers portfolio, trading, orders, execution, account, broker, ETF or P&L navigation', async () => {
    await renderApp('/');
    await screen.findByRole('link', { name: 'Overview' });
    const banned = [/portfolio/i, /trading/i, /orders?/i, /execution/i, /account/i, /broker/i, /etf/i, /p&l/i, /pnl/i];
    for (const pattern of banned) {
      expect(screen.queryByRole('link', { name: pattern })).toBeNull();
    }
  });

  it('labels the dashboard as a read-only research view', async () => {
    await renderApp('/');
    expect(await screen.findByText(/not a trading terminal/i)).toBeInTheDocument();
    expect(screen.getByText(/does not control research execution/i)).toBeInTheDocument();
  });
});
