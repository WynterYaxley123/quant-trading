import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderApp } from './test-utils';

describe('Research Integrity page', () => {
  it('shows the research definition and protocol constants', async () => {
    await renderApp('/integrity');
    expect(await screen.findByText('研究定义')).toBeInTheDocument();
    expect(screen.getByText('模拟研究标签')).toBeInTheDocument();
    expect(screen.getByText('分类方式')).toBeInTheDocument();
    expect(screen.getByText('模拟固定分类研究')).toBeInTheDocument();
    expect(screen.getByText('因子数')).toBeInTheDocument();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('0.05')).toBeInTheDocument();
    expect(screen.getByText('融合权重')).toBeInTheDocument();
    expect(screen.getByText('0.30 / 0.40 / 0.30')).toBeInTheDocument();
  });

  it('shows status flags: development active, validation and OOS sealed, disabled execution', async () => {
    await renderApp('/integrity');
    expect((await screen.findAllByText('Development（开发集）')).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('已封存').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('严格 PIT')).toBeInTheDocument();
    expect(screen.getAllByText('未启用').length).toBeGreaterThanOrEqual(3);
  });

  it('abbreviates hashes and expands the full value on click', async () => {
    await renderApp('/integrity');
    expect(await screen.findByText('研究产物 Hash')).toBeInTheDocument();

    const abbreviated = await screen.findAllByText('mock-split…');
    expect(abbreviated.length).toBeGreaterThanOrEqual(1);
    await userEvent.click(abbreviated[0] as HTMLElement);
    expect(
      await screen.findByText('mock-split-policy-hash-synthetic-0000000000000000000000'),
    ).toBeInTheDocument();
  });
});
