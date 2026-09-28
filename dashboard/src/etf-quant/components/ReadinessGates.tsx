import { ShieldCheck, ShieldAlert, ShieldQuestion } from 'lucide-react';
import type { EtfQuantReadiness } from '../contracts';
import { StatusBadge } from './StatusBadge';
import { EMPTY, fmtText } from '../format';
import { EmptyState } from '@/components/ui/states';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/cn';

/**
 * SHADOW_START_READINESS_V1 渲染：overall 横幅 + 逐门控状态列表。
 * overall=NOT_REACHED（后台尚未发布 readiness artifact）时是诚实的空态，
 * 不推断任何门控；DEFERRED 门控以「暂缓」呈现，绝非失败。
 */

const OVERALL_META = {
  PASS: {
    Icon: ShieldCheck,
    className: 'border-success/40 bg-success/10',
    iconClass: 'text-success',
    title: '全部启动门控已通过',
  },
  BLOCKED: {
    Icon: ShieldAlert,
    className: 'border-destructive/40 bg-destructive/10',
    iconClass: 'text-destructive',
    title: '存在阻断门控，Shadow 尚不可启动',
  },
  NOT_REACHED: {
    Icon: ShieldQuestion,
    className: 'border-border bg-muted/40',
    iconClass: 'text-muted-foreground',
    title: '准备状态评估尚未完成',
  },
} as const;

export function ReadinessBanner({ readiness }: { readiness: EtfQuantReadiness }) {
  const meta = OVERALL_META[readiness.overall];
  return (
    <div className={cn('flex flex-wrap items-center gap-3 rounded-lg border p-4', meta.className)} role="status">
      <meta.Icon aria-hidden="true" className={cn('h-6 w-6 shrink-0', meta.iconClass)} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">{meta.title}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          契约 {readiness.contract} · 生成时间 {fmtText(readiness.generated_at)} · 数据截止 {fmtText(readiness.data_cutoff)}
        </p>
      </div>
      <StatusBadge status={readiness.overall} />
    </div>
  );
}

export function ReadinessGateList({ readiness }: { readiness: EtfQuantReadiness }) {
  if (readiness.gates.length === 0) {
    return (
      <EmptyState
        title="准备状态报告尚未发布"
        description="后台尚未生成 SHADOW_START_READINESS_V1 评估产物（readiness artifact），或产物中没有门控记录。在产物发布前，本页不推断任何门控状态，也不会以历史数据代替评估结果。"
      />
    );
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>启动门控清单（{readiness.gates.length}）</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <ul className="divide-y divide-border">
          {readiness.gates.map((gate) => (
            <li key={gate.name} className="flex flex-col gap-2 px-6 py-4 sm:flex-row sm:items-start sm:gap-4">
              <div className="min-w-0 flex-1">
                <p className="font-mono text-sm font-medium">{gate.name}</p>
                <p className="mt-1 text-sm text-muted-foreground">{gate.summary}</p>
                <p className="mt-1 break-all font-mono text-xs text-muted-foreground">证据：{gate.evidence ?? EMPTY}</p>
              </div>
              <StatusBadge status={gate.status} className="shrink-0" />
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export function ReadinessFacts({ readiness }: { readiness: EtfQuantReadiness }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <span className="rounded-md border border-border bg-muted/40 px-2 py-1 font-mono">
        shadow_epoch_created = {String(readiness.shadow_epoch_created)}
      </span>
      <span className="rounded-md border border-border bg-muted/40 px-2 py-1 font-mono">
        shadow_started = {String(readiness.shadow_started)}
      </span>
      <span>
        {!readiness.shadow_epoch_created && !readiness.shadow_started
          ? 'Shadow epoch 尚未创建、尚未启动；以上事实来自评估产物，不代表账户已经运行。'
          : '以上状态来自评估产物；如显示已创建或已启动，应与只读 runtime 状态独立核对。'}
      </span>
    </div>
  );
}

export function ReadinessNotes({ readiness }: { readiness: EtfQuantReadiness }) {
  if (readiness.notes.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>评估备注</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          {readiness.notes.map((note, i) => (
            <li key={i}>{note}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
