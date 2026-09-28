import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { EtfQuantSnapshot } from '../contracts';
import { SectionCard, SegmentedTabs } from '../components/Section';
import { buildColumns } from '../components/etable';
import { PhaseBadge } from '../components/StatusBadge';
import { DataTable } from '@/components/tables/DataTable';
import { ChartFrame } from '@/components/charts/ChartFrame';
import { HashText } from '@/components/research/HashText';
import { fmtCount, fmtSigned, fmtText } from '../format';

type Horizon = '10d' | '40d' | '120d';
const HORIZONS: readonly Horizon[] = ['10d', '40d', '120d'];

const COLUMNS = buildColumns([
  { key: 'name', header: '因子', kind: 'code' },
  { key: 'formula', header: '实际 close 公式' },
  { key: 'lookback', header: 'lookback sessions', kind: 'int' },
  { key: 'coefficient', header: '系数（有符号）', kind: 'signed' },
]);

/**
 * 因子与模型系数：冻结因子集（5 / 19 / 19），Ridge 有符号系数。
 * 负权重与近零权重同样可见；原始特征尺度，不跨 horizon 比较系数大小。
 */
export function FactorsSection({ data }: { data: EtfQuantSnapshot }) {
  const [horizonKey, setHorizonKey] = useState<Horizon>('10d');
  const horizon = Number(horizonKey.slice(0, -1));
  const model = data.models.find((m) => m.horizon === horizon);
  const names = horizon === 10 ? data.strategy.h10_factors : horizon === 40 ? data.strategy.h40_factors : data.strategy.h120_factors;
  const registry = new Map(data.strategy.factor_registry.map((f) => [f.name, f]));
  const rows = names.map((name, i) => ({
    name,
    formula: registry.get(name)?.formula ?? null,
    lookback: registry.get(name)?.lookback_sessions ?? null,
    coefficient: model?.coefficients[i] ?? null,
  }));
  return (
    <>
      <SectionCard
        title="冻结因子集 · 具名系数"
        description="Ridge α = 0.01（限制模型权重不要过度极端）· 6 个自然月滚动训练窗口 · label cutoff 标签截止日锚定（防止前视）· 原始特征 X 不标准化。"
        actions={<SegmentedTabs values={HORIZONS} value={horizonKey} onChange={setHorizonKey} label="模型 horizon" />}
      >
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          <span className="flex items-center gap-1.5">
            模型状态 <PhaseBadge phase={model ? 'READY' : 'MODEL_WARMUP_INCOMPLETE'} />
          </span>
          <span className="tabular-nums">截距 {model ? fmtSigned(model.intercept) : '—'}</span>
        </div>
        <p className="break-all text-sm text-muted-foreground">
          训练日期：{model?.training.training_start ?? '—'} → {model?.training.training_end ?? '—'}；
          label cutoff：{model?.training.label_cutoff ?? '—'}；有效交易日：{fmtCount(model?.training.training_day_count)}；样本：{fmtCount(model?.training.sample_count)}
        </p>
        <p className="text-sm text-muted-foreground">
          current snapshot observed：{model?.current_snapshot_observed_at ?? '—'}；historical available_at：UNKNOWN / null
        </p>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          model hash <HashText value={model?.model_hash ?? null} />
        </div>
        <DataTable data={rows} columns={COLUMNS} caption={`${horizonKey} 因子和系数`} manualSorting />
      </SectionCard>
      {model ? (
        <ChartFrame
          title={`${horizonKey} Ridge 有符号系数`}
          description="原始特征尺度，不跨 horizon 比较系数大小；正 / 负系数以不同色相区分，近零权重同样可见。"
          summary={`${names.length} 个具名 Ridge 系数。`}
          bodyClassName="h-[440px]"
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 24 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={48} tick={{ fontSize: 11 }} />
              <ReferenceLine x={0} />
              <Tooltip formatter={(value) => fmtText(typeof value === 'number' ? fmtSigned(value) : String(value))} />
              <Bar dataKey="coefficient" name="Ridge coefficient">
                {rows.map((row) => (
                  <Cell key={row.name} fill={(row.coefficient ?? 0) >= 0 ? 'var(--color-chart-2)' : 'var(--color-chart-3)'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartFrame>
      ) : null}
    </>
  );
}
