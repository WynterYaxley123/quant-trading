import type { EtfQuantSnapshot } from '../contracts';
import { MetricCard, MetricGrid } from '../components/MetricCard';
import { SectionCard } from '../components/Section';
import { PhaseBadge } from '../components/StatusBadge';
import { buildColumns, type Row } from '../components/etable';
import { DataTable } from '@/components/tables/DataTable';
import { fmtCount, fmtText } from '../format';

const COVERAGE_COLUMNS = buildColumns([
  { key: 'industry_code', header: '行业', kind: 'code' },
  { key: 'trade_date', header: '日期' },
  { key: 'status', header: '状态' },
  { key: 'eligible_members', header: 'eligible members', kind: 'int' },
  { key: 'valid_constituents', header: 'valid constituents', kind: 'int' },
  { key: 'coverage', header: 'coverage ratio', kind: 'pct' },
  { key: 'reason', header: '原因' },
]);

/**
 * 数据健康：运行状态、新鲜度、复权行（exact / rejected）、严格 TLS、
 * 质量标记与阻断清单、行业成分覆盖。这里展示的是数据工程状态本身。
 */
export function HealthSection({ data }: { data: EtfQuantSnapshot }) {
  const h = data.health;
  const freshness = typeof (h as Record<string, unknown>).freshness === 'string' ? (h as Record<string, unknown>).freshness as string : null;
  return (
    <>
      <MetricGrid className="xl:grid-cols-5">
        <MetricCard
          label="运行健康"
          tone={h.status === 'DEGRADED' || h.status.includes('BLOCKED') ? 'destructive' : h.status === 'OK' ? 'success' : 'default'}
          value={<PhaseBadge phase={h.status} />}
        />
        <MetricCard label="快照新鲜度" value={fmtText(freshness)} />
        <MetricCard label="exact adjustment rows" value={fmtCount(h.adjustment_exact_rows)} hint="复权因子精确匹配行" />
        <MetricCard
          label="rejected adjustment rows"
          tone={(h.adjustment_rejected_rows ?? 0) > 0 ? 'warning' : 'default'}
          value={fmtCount(h.adjustment_rejected_rows)}
          hint="无法精确复权而被拒绝的行"
        />
        <MetricCard label="strict TLS" value={<span className="font-mono text-sm">{h.strict_tls}</span>} />
      </MetricGrid>
      <SectionCard title="质量标记与阻断" description="非官方行业指数；历史分类不是 ex-ante PIT 证据。available_at / source_published_at = UNKNOWN / null。">
        <div className="flex flex-col gap-2 text-sm">
          <p><span className="text-muted-foreground">阻断：</span>{h.blockers.length ? h.blockers.join(' · ') : '无已记录阻断'}</p>
          <p><span className="text-muted-foreground">质量标记：</span>{h.quality_flags.length ? h.quality_flags.join(' · ') : '—'}</p>
        </div>
      </SectionCard>
      <SectionCard title="行业成分覆盖" description="每个行业 × 交易日的 eligible / valid 成分与覆盖率。">
        <DataTable data={(h.coverage ?? []) as Row[]} columns={COVERAGE_COLUMNS} caption="行业成分覆盖" manualSorting />
      </SectionCard>
    </>
  );
}
