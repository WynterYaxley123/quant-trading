import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ChartFrame } from './ChartFrame';
import { formatMetric, type MetricKind } from '@/lib/format';

/**
 * Time series (E001–E100 development series) plotted against signal date.
 * A zero reference line is shown when the metric is signed — useful for IC /
 * RankIC / spread-style series. No animation gimmicks, no 3D, no gradients.
 */

export interface TimeSeriesPoint {
  ordinal: string;
  signalDate: string;
  value: number | null;
}

interface TimeSeriesChartProps {
  title: string;
  description?: string;
  summary: string;
  points: TimeSeriesPoint[];
  valueKind: MetricKind;
  showZeroLine?: boolean;
}

interface TooltipPayloadEntry {
  value?: number | null;
  payload?: TimeSeriesPoint;
}

function ChartTooltip({
  active,
  payload,
  valueKind,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  valueKind: MetricKind;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0]?.payload;
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs shadow-md">
      <p className="font-semibold">{point?.signalDate ?? ''}</p>
      <p className="text-muted-foreground">{point?.ordinal ?? ''}</p>
      <p className="mt-1 font-mono">{formatMetric(payload[0]?.value ?? null, valueKind)}</p>
    </div>
  );
}

export function TimeSeriesChart({
  title,
  description,
  summary,
  points,
  valueKind,
  showZeroLine = true,
}: TimeSeriesChartProps) {
  return (
    <ChartFrame title={title} description={description} summary={summary}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="signalDate"
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: 'var(--border)' }}
            minTickGap={24}
          />
          <YAxis
            tickFormatter={(value: number) =>
              valueKind === 'return' ? `${(value * 100).toFixed(1)}%` : value.toFixed(2)
            }
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={56}
          />
          <Tooltip content={<ChartTooltip valueKind={valueKind} />} />
          {showZeroLine ? (
            <ReferenceLine
              y={0}
              stroke="var(--muted-foreground)"
              strokeDasharray="4 4"
              label={{ value: '零线', position: 'insideBottomRight', fill: 'var(--muted-foreground)', fontSize: 11 }}
            />
          ) : null}
          <Line
            type="monotone"
            dataKey="value"
            name="指标值"
            stroke="var(--chart-1)"
            strokeWidth={2}
            dot={{ r: 3, fill: 'var(--chart-1)' }}
            activeDot={{ r: 5 }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
