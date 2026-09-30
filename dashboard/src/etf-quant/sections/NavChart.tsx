import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { EtfQuantSnapshot } from '../contracts';
import { ChartFrame } from '@/components/charts/ChartFrame';

/**
 * Forward NAV vs CSI 300：同一 epoch 起点归一化（无量纲）。
 * 缺口不连接、不补写历史；仅在存在真实 epoch 时渲染。
 */
export function NavChart({ data }: { data: EtfQuantSnapshot }) {
  if (!data.status.epoch || !data.nav.length) return null;
  const benchmark = new Map(data.benchmark.points.map((p) => [p.trade_date, p.normalized]));
  const points = data.nav.map((p) => ({
    date: p.trade_date,
    shadow: Number(p.normalized_nav),
    csi300: benchmark.get(p.trade_date) ?? null,
  }));
  return (
    <ChartFrame
      title="Forward NAV · CSI 300"
      description="同一 epoch 起点；归一化净值（无量纲）。缺口不连接，不补写历史。"
      summary={`${points.length} 个 forward epoch NAV 点；仅用于模拟账户观察。`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ left: 4, right: 16, top: 12, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} />
          <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Line type="linear" dataKey="shadow" name="Shadow NAV" stroke="var(--color-chart-1)" dot={points.length === 1} connectNulls={false} />
          <Line type="linear" dataKey="csi300" name="CSI 300" stroke="var(--color-chart-4)" dot={points.length === 1} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
