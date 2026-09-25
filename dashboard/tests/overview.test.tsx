import { describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderApp } from './test-utils';

describe('Overview page', () => {
  it('shows research state first: development, sealed validation and OOS, non-executable, not tradable', async () => {
    await renderApp('/');

    // Global banner is persistently visible
    expect(screen.getByText('Development only')).toBeInTheDocument();
    expect(screen.getByText('Non-executable')).toBeInTheDocument();
    expect(screen.getByText('Validation sealed')).toBeInTheDocument();
    expect(screen.getByText('Final OOS sealed')).toBeInTheDocument();

    // Status cards
    expect(await screen.findByText('Phase')).toBeInTheDocument();
    expect((await screen.findAllByText('DEVELOPMENT')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('SEALED').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('Executable')).toBeInTheDocument();
    expect(screen.getByText('Tradable')).toBeInTheDocument();
    expect(screen.getAllByText('NO').length).toBeGreaterThanOrEqual(2);
  });

  it('renders D0-D3 candidate cards with unit hints and promotion status', async () => {
    await renderApp('/');
    for (const candidateId of ['D0', 'D1', 'D2', 'D3']) {
      expect(await screen.findByText(candidateId)).toBeInTheDocument();
    }
    expect(screen.getAllByText('Weighted RankIC (unitless)').length).toBe(4);
    expect(screen.getAllByText('Weighted Spread (return)').length).toBe(4);
    expect((await screen.findAllByText('Further review')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Not promoted')).toBeInTheDocument();
  });

  it('shows run context with abbreviated hashes', async () => {
    await renderApp('/');
    expect(await screen.findByText('Current run')).toBeInTheDocument();
    expect(screen.getByText('Git commit')).toBeInTheDocument();
    expect(screen.getByText('Protocol hash')).toBeInTheDocument();
    expect(screen.getByText('Sector snapshot')).toBeInTheDocument();
  });

  it('never shows fake backtest metrics', async () => {
    await renderApp('/');
    await screen.findAllByText('DEVELOPMENT');
    for (const banned of [/sharpe/i, /sortino/i, /drawdown/i, /equity curve/i, /win rate/i, /profit/i, /pnl/i]) {
      expect(screen.queryByText(banned)).toBeNull();
    }
  });

  it('sealed phases expose no unlock or override controls', async () => {
    await renderApp('/');
    await screen.findAllByText('DEVELOPMENT');
    expect(
      screen.queryByRole('button', { name: /unlock|view anyway|override|reveal sealed/i }),
    ).toBeNull();
    expect(screen.queryByRole('link', { name: /validation detail|oos detail/i })).toBeNull();
  });
});

describe('Mock data banner', () => {
  it('is shown only when VITE_DATA_MODE=mock', async () => {
    vi.stubEnv('VITE_DATA_MODE', 'mock');
    await renderApp('/');
    // Banner badge + header chip both mark mock mode.
    expect((await screen.findAllByText('Mock data')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/synthetic test fixtures/i)).toBeInTheDocument();
    vi.unstubAllEnvs();
  });

  it('is not shown in api mode (the default)', async () => {
    await renderApp('/');
    await screen.findAllByText('DEVELOPMENT');
    expect(screen.queryByText('Mock data')).toBeNull();
    expect(screen.getByText('API mode')).toBeInTheDocument();
  });
});
