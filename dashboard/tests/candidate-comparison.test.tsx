import { describe, expect, it } from 'vitest';
import { screen, within } from '@testing-library/react';
import { renderApp } from './test-utils';

describe('Candidate Comparison page', () => {
  it('renders the comparison charts and table', async () => {
    await renderApp('/candidates');
    expect(await screen.findByText('加权 RankIC（无量纲）')).toBeInTheDocument();
    expect(screen.getAllByText('加权超额收益差').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('各周期平均 RankIC')).toBeInTheDocument();
    expect(screen.getByText('各周期平均超额收益差')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: /候选方案指标与晋级状态对比/ })).toBeInTheDocument();
  });

  it('defaults to Weighted RankIC descending with nulls last', async () => {
    await renderApp('/candidates');
    const table = await screen.findByRole('table', { name: /候选方案指标与晋级状态对比/ });
    const rows = within(table).getAllByRole('row');
    // header + 4 data rows; fixture values: D2 0.0345 > D0 0.0123 > D1 -0.0234 > D3 null
    expect(rows[1]?.textContent).toContain('D2');
    expect(rows[2]?.textContent).toContain('D0');
    expect(rows[3]?.textContent).toContain('D1');
    expect(rows[4]?.textContent).toContain('D3');
  });

  it('formats RankIC as unitless and Spread as percentage', async () => {
    await renderApp('/candidates');
    const table = await screen.findByRole('table', { name: /候选方案指标与晋级状态对比/ });
    const rows = within(table).getAllByRole('row');
    // D0: weightedRankIc 0.0123, weightedSpread 0.0456
    expect(rows[2]?.textContent).toContain('0.0123');
    expect(rows[2]?.textContent).toContain('4.56%');
    // null placeholder for D2's weighted spread
    expect(rows[1]?.textContent).toContain('—');
  });

  it('displays promotion status exactly as reported (never re-derived)', async () => {
    await renderApp('/candidates');
    expect((await screen.findAllByText('进入进一步研究')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('未晋级')).toBeInTheDocument();
    // D3 has promotionStatus = null → placeholder badge, not a derived value
    const table = screen.getByRole('table', { name: /候选方案指标与晋级状态对比/ });
    expect(within(table).getAllByText('—').length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText(/winner|best strategy|approved|profitable/i)).toBeNull();
  });
});
