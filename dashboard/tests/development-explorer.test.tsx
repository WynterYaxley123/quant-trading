import { describe, expect, it } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderApp } from './test-utils';

describe('Development Explorer page', () => {
  it('renders the E001-E003 series chart and table', async () => {
    const router = await renderApp('/development');
    expect(await screen.findByText(/按信号日期查看 Development/)).toBeInTheDocument();
    const summary = await screen.findByRole('img', { name: /10日 RankIC/ });
    expect(summary).toHaveAttribute('aria-label', expect.stringContaining('10日'));
    const table = screen.getByRole('table', { name: /Development 10日 RankIC 指标序列/ });
    expect(within(table).getAllByRole('row').length).toBe(4); // header + 3 dates
    expect(router.state.location.pathname).toBe('/development');
  });

  it('keeps explorer state in the URL (candidate, metric, horizon)', async () => {
    const router = await renderApp('/development');
    await screen.findByRole('table', { name: /Development 10日 RankIC 指标序列/ });

    await userEvent.selectOptions(screen.getByLabelText('候选方案'), 'D2');
    await userEvent.selectOptions(screen.getByLabelText('指标'), 'top5MinusUniverse');
    await userEvent.selectOptions(screen.getByLabelText('预测周期'), '40');

    await screen.findByRole('table', { name: /Development 40日 Top5 相对行业整体超额 指标序列/ });
    expect(router.state.location.search).toMatchObject({
      candidate: 'D2',
      metric: 'top5MinusUniverse',
      horizon: '40',
    });
  });

  it('switches the displayed metric with correct unit formatting', async () => {
    await renderApp('/development');
    const table = await screen.findByRole('table', { name: /Development 10日 RankIC 指标序列/ });
    expect(within(table).getByRole('columnheader', { name: /rankic/i })).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText('指标'), 'top5ForwardReturn');
    const updated = await screen.findByRole('table', { name: /Development 10日 Top5 未来收益 指标序列/ });
    expect(within(updated).getByRole('columnheader', { name: /Top5 未来收益/ })).toBeInTheDocument();
    // return metrics render as percentages
    expect(updated.textContent).toMatch(/-?\d+\.\d{2}%/);
  });
});
