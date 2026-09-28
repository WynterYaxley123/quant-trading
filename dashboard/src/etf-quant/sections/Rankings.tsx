import { useState } from 'react';
import type { EtfQuantSnapshot } from '../contracts';
import { SectionCard, SegmentedTabs } from '../components/Section';
import { buildColumns, type Row } from '../components/etable';
import { DataTable } from '@/components/tables/DataTable';
import { Button } from '@/components/ui/button';

type Horizon = '10d' | '40d' | '120d' | 'fusion';
const HORIZONS: readonly Horizon[] = ['10d', '40d', '120d', 'fusion'];

const COLUMNS = buildColumns([
  { key: 'rank', header: '排名', kind: 'int' },
  { key: 'industry_code', header: '行业代码', kind: 'code' },
  { key: 'score', header: '预测 / Fusion 分数（无量纲）', kind: 'num' },
]);

/**
 * 行业融合排名：四个 horizon 分段切换，默认 Top 20，Fusion Top 5 高亮。
 * 单 horizon 为原始预测；Fusion 为各 horizon 横截面 z-score 的
 * 0.25 / 0.50 / 0.25 加权分数。排名不构成任何买卖含义。
 */
export function RankingsSection({ data }: { data: EtfQuantSnapshot }) {
  const [horizon, setHorizon] = useState<Horizon>('fusion');
  const [showAll, setShowAll] = useState(false);
  const rows = data.rankings[horizon];
  const visible = showAll ? rows : rows.slice(0, 20);
  return (
    <SectionCard
      title="行业排名 · 10d / 40d / 120d / Fusion"
      description="默认显示 Top 20，Top 5 高亮。单 horizon 为原始预测；Fusion 为各 horizon 横截面 z-score 的 0.25 / 0.50 / 0.25 加权分数。行业名称未解析，展示内部代码。"
      actions={<SegmentedTabs values={HORIZONS} value={horizon} onChange={setHorizon} label="排名 horizon" />}
    >
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" size="sm" onClick={() => setShowAll((v) => !v)}>
          {showAll ? '仅显示 Top 20' : '显示全部行业'}
        </Button>
        <p className="text-sm text-muted-foreground tabular-nums">
          {visible.length} / {rows.length} 个行业
        </p>
      </div>
      <DataTable
        data={visible as Row[]}
        columns={COLUMNS}
        caption={`${horizon} 行业排名`}
        manualSorting
        rowClassName={(row) =>
          Number(row.original.rank) <= 5 ? 'bg-primary/5 [&_td:first-child]:font-semibold' : undefined
        }
      />
    </SectionCard>
  );
}
