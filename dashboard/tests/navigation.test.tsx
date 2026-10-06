import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderApp } from './test-utils';

describe('Navigation', () => {
  it('contains exactly the research sections', async () => {
    await renderApp('/');
    const names = [
      '概览',
      '候选方案对比',
      'Development 探索',
      '行业探索',
      '诊断',
      '研究完整性',
    ];
    for (const name of names) {
      expect(await screen.findByRole('link', { name })).toBeInTheDocument();
    }
  });

  it('never offers portfolio, trading, orders, execution, account, broker, ETF or P&L navigation', async () => {
    await renderApp('/');
    await screen.findByRole('link', { name: '概览' });
    const banned = [/portfolio/i, /trading/i, /orders?/i, /execution/i, /account/i, /broker/i, /etf/i, /p&l/i, /pnl/i];
    for (const pattern of banned) {
      expect(screen.queryByRole('link', { name: pattern })).toBeNull();
    }
  });

  it('labels the dashboard as a read-only research view', async () => {
    await renderApp('/');
    expect(await screen.findByText('Quant Trading / Industry Forecast')).toBeInTheDocument();
    expect(screen.getByText(/只读研究界面，不提供交易功能/)).toBeInTheDocument();
    expect(screen.getByText(/不能发起研究执行或交易/)).toBeInTheDocument();
  });
});
