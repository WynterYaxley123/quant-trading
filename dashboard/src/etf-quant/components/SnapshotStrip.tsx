import { useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import type { EtfQuantSnapshot } from '../contracts';
import { PhaseBadge } from './StatusBadge';
import { EMPTY, fmtNum, fmtText } from '../format';
import { HashText } from '@/components/research/HashText';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { cn } from '@/lib/cn';

function MetaItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-sm tabular-nums">{children}</dd>
    </div>
  );
}

function HashItem({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="w-28 shrink-0 text-xs text-muted-foreground">{label}</span>
      <HashText value={value} />
    </div>
  );
}

/**
 * 快照状态条：运行阶段 / 数据截止 / 更新时间 / epoch / 披露声明。
 * 工程溯源（snapshot id、commit、哈希）默认折叠在「数据溯源」里，
 * 不再占据首屏。NOT OFFICIAL SHENWAN INDEX 等披露始终可见。
 */
export function SnapshotStrip({ data }: { data: EtfQuantSnapshot }) {
  const [open, setOpen] = useState(false);
  const s = data.status;
  const degraded = data.health.status === 'DEGRADED' || data.health.freshness === 'STALE';
  return (
    <section aria-label="快照状态" className="rounded-lg border border-border bg-card p-4">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 xl:grid-cols-6">
        <MetaItem label="运行阶段"><PhaseBadge phase={s.phase} /></MetaItem>
        <MetaItem label="数据截止日">{fmtText(s.cutoff)}</MetaItem>
        <MetaItem label="最近更新">{fmtText(s.updated_at)}</MetaItem>
        <MetaItem label="信号日 T0">{fmtText(s.signal_date)}</MetaItem>
        <MetaItem label="执行日 T+1">{fmtText(s.execution_date)}</MetaItem>
        <MetaItem label="数据版本"><span className="font-mono text-xs">{fmtText(s.source_version)}</span></MetaItem>
      </dl>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border pt-3 text-sm">
        <span className="text-muted-foreground">Shadow epoch</span>
        {s.epoch ? (
          <>
            <span className="font-mono text-xs">{s.epoch.epoch_id}</span>
            <span className="text-xs text-muted-foreground">启动于 {s.epoch.started_at} · 市场截止 {s.epoch.market_cutoff}</span>
          </>
        ) : (
          <span className="font-mono text-xs text-muted-foreground">NOT_STARTED</span>
        )}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        {fmtText(s.reason)} · NOT OFFICIAL SHENWAN INDEX · HISTORICAL_MEMBERSHIP_PIT_UNPROVEN
      </p>
      {degraded ? (
        <p className="mt-2 text-xs font-medium text-warning-foreground" role="alert">
          数据健康警告：{data.health.status} / {fmtText(data.health.freshness as string | null)} · {data.health.blockers.join(' · ') || EMPTY}
        </p>
      ) : null}
      <Collapsible open={open} onOpenChange={setOpen} className="mt-2">
        <CollapsibleTrigger asChild>
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs text-muted-foreground" aria-expanded={open}>
            <ChevronDown aria-hidden="true" className={cn('transition-transform', open && 'rotate-180')} />
            数据溯源 / Advanced
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-2 flex flex-col gap-1.5 rounded-md bg-muted/40 p-3">
          <HashItem label="provider snapshot" value={s.snapshot_id} />
          <HashItem label="source commit" value={s.source_commit} />
          <HashItem label="code commit" value={s.code_commit} />
          <HashItem label="mapping hash" value={s.mapping_hash} />
          <HashItem label="strategy hash" value={s.strategy_hash} />
          {s.epoch ? <HashItem label="epoch provider" value={s.epoch.provider_snapshot_id} /> : null}
          <p className="text-xs text-muted-foreground">会计模式 {s.epoch?.bookkeeping ?? EMPTY} · 初始资金 CNY {fmtNum(10000, 0)}</p>
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}
