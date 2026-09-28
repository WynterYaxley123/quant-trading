import type { EtfQuantSnapshot } from '../contracts';
import { MetricCard, MetricGrid } from '../components/MetricCard';
import { SectionCard } from '../components/Section';
import { StatusBadge } from '../components/StatusBadge';
import { NavChart } from './NavChart';
import { fmtCount } from '../format';

/**
 * 基准：仅使用 sidecar 的 CSI 300 导出，epoch 起点归一化，只用于展示，
 * 不进入模型、行业排名或仓位。NASDAQ / S&P 500 是 DEFERRED（暂缓），
 * 不是失败，因此以「暂缓」徽章呈现。
 */
export function BenchmarksSection({ data }: { data: EtfQuantSnapshot }) {
  const b = data.benchmark;
  return (
    <>
      <MetricGrid className="xl:grid-cols-4">
        <MetricCard label="基准标的" value={<span className="font-mono text-sm">{b.symbol}</span>} hint="CSI 300 · sidecar 导出" />
        <MetricCard label="基准状态" value={<span className="font-mono text-sm">{b.status}</span>} />
        <MetricCard label="归一化数据点" value={fmtCount(b.points.length)} hint={b.points.length ? `${b.points[0]!.trade_date} → ${b.points[b.points.length - 1]!.trade_date}` : '无 epoch，暂无数据点'} />
        <MetricCard label="进入模型" value="否" hint="基准不参与模型、排名或仓位" />
      </MetricGrid>
      <SectionCard title="海外基准接入状态" description="DEFERRED 表示主动暂缓接入，不是获取失败；不会以红色失败语义呈现。">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">NASDAQ Composite</span>
          <StatusBadge status="DEFERRED" />
          <span className="text-sm text-muted-foreground">S&amp;P 500</span>
          <StatusBadge status="DEFERRED" />
        </div>
      </SectionCard>
      <NavChart data={data} />
    </>
  );
}
