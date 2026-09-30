import type { ReactNode } from 'react';
import { SimulationBadge } from './StatusBadge';

/**
 * ETF 页面头部：SIMULATION_ONLY 标识 + 中文标题 + 一句话说明 + 右侧操作。
 * 专业术语保留英文缩写，但页面语言为中文。
 */
export function EtfPageHeader({
  title,
  description,
  badges,
  actions,
}: {
  title: string;
  description: string;
  badges?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <SimulationBadge />
          {badges}
        </div>
        <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
        <p className="max-w-3xl text-sm text-muted-foreground">{description}</p>
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}
