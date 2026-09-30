import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderApp } from './test-utils';

describe('Diagnostics page', () => {
  it('shows attempted / successful / skipped date counters in plain language', async () => {
    await renderApp('/diagnostics');
    expect(await screen.findByText('尝试日期数')).toBeInTheDocument();
    expect(screen.getByText('成功日期数')).toBeInTheDocument();
    expect(screen.getByText('跳过日期数')).toBeInTheDocument();
    expect(screen.getAllByText('零标准差特征次数').length).toBeGreaterThanOrEqual(1);
  });

  it('shows per-horizon training summary and expands full issue details', async () => {
    await renderApp('/diagnostics');
    expect(await screen.findByText('10日预测周期')).toBeInTheDocument();
    expect(screen.getByText('40日预测周期')).toBeInTheDocument();
    expect(screen.getByText('120日预测周期')).toBeInTheDocument();
    expect(screen.getAllByText('训练样本数').length).toBe(3);

    // Real warnings are hidden behind details but never removed — expand horizon 10.
    const triggers = screen.getAllByRole('button', { name: /查看明细/ });
    await userEvent.click(triggers[0] as HTMLElement);
    expect(await screen.findByText('缺失因子剔除数')).toBeInTheDocument();
    expect(screen.getByText('缺失标签剔除数')).toBeInTheDocument();
    expect(screen.getByText('数值计算失败数')).toBeInTheDocument();
    expect(screen.getByText('训练样本不足次数')).toBeInTheDocument();
    expect(screen.getAllByText(/影响/).length).toBeGreaterThanOrEqual(1);
  });

  it('explains zero-std and demean-residual diagnostics', async () => {
    await renderApp('/diagnostics');
    expect(await screen.findByText('特征与目标变换诊断')).toBeInTheDocument();
    expect(screen.getByText(/仅训练集标准化的候选方案适用/)).toBeInTheDocument();
    expect(screen.getByText('去均值残差最大绝对均值')).toBeInTheDocument();
  });
});
