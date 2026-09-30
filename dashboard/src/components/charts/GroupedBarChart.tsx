import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ChartFrame } from './ChartFrame';
import { formatMetric, type MetricKind } from '@/lib/format';

/**
 * Grouped bar chart (Tremor-style composition over recharts). One metric
 * unit per chart; series share the same Y axis unit. No gradients / 3D.
 */

const SERIES_COLORS = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
];

export interface BarSeriesDef {
  key: string;
  label: string;
}

interface GroupedBarChartProps {
  title: string;
  description?: string;
  summary: string;
  series: BarSeriesDef[];
  /** Rows with a `category` label plus one numeric|null field per series key. */
  data: Array<{ category: string } & Record<string, number | null | string>>;
  valueKind: MetricKind;
}

function tickFormatter(valueKind: MetricKind) {
  return (value: number) =>
    valueKind === 'return' ? `${(value * 100).toFixed(1)}%` : value.toFixed(2);
}

interface TooltipPayloadEntry {
  name?: string;
  value?: number | null;
  color?: string;
  dataKey?: string;
}

function ChartTooltip({
  active,
  payload,
  label,
  valueKind,
  seriesLabels,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
  valueKind: MetricKind;
  seriesLabels: Record<string, string>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-semibold">{label}</p>
      {payload.map((entry) => (
        <p key={entry.dataKey} className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className="inline-block h-2 w-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span>{seriesLabels[entry.dataKey ?? ''] ?? entry.name}</span>
          <span className="ml-auto font-mono">{formatMetric(entry.value ?? null, valueKind)}</span>
        </p>
      ))}
    </div>
  );
}

export function GroupedBarChart({
  title,
  description,
  summary,
  series,
  data,
  valueKind,
}: GroupedBarChartProps) {
  const seriesLabels: Record<string, string> = {};
  for (const s of series) seriesLabels[s.key] = s.label;

  return (
    <ChartFrame title={title} description={description} summary={summary}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 0 }} barGap={4}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="category"
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: 'var(--border)' }}
          />
          <YAxis
            tickFormatter={tickFormatter(valueKind)}
            tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={56}
          />
          <Tooltip
            content={<ChartTooltip valueKind={valueKind} seriesLabels={seriesLabels} />}
            cursor={{ fill: 'var(--muted)', opacity: 0.5 }}
          />
          {series.map((s, index) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.label}
              fill={SERIES_COLORS[index % SERIES_COLORS.length]}
              radius={[4, 4, 0, 0]}
              maxBarSize={48}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
