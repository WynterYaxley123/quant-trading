import { CheckCircle2, CircleDashed, HelpCircle, OctagonX, PauseCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/cn';

/**
 * 门控 / 状态徽章。状态语义只用徽章通道（图标 + 中文标签 + 色相），
 * 与涨跌数值的红绿色完全分离；DEFERRED 使用蓝色「暂缓」，
 * 绝不在视觉上等同失败。原始机器码始终同时可见（mono）。
 */

export type GateStatus = 'PASS' | 'BLOCKED' | 'NOT_REACHED' | 'DEFERRED' | 'UNKNOWN';

const GATE_MAP: Record<GateStatus, { variant: 'success' | 'destructive' | 'muted' | 'info' | 'outline'; label: string; Icon: typeof CheckCircle2 }> = {
  PASS: { variant: 'success', label: '通过', Icon: CheckCircle2 },
  BLOCKED: { variant: 'destructive', label: '阻断', Icon: OctagonX },
  NOT_REACHED: { variant: 'muted', label: '未达成', Icon: CircleDashed },
  DEFERRED: { variant: 'info', label: '暂缓', Icon: PauseCircle },
  UNKNOWN: { variant: 'outline', label: '未知', Icon: HelpCircle },
};

export function StatusBadge({ status, showCode = true, className }: { status: GateStatus | string; showCode?: boolean; className?: string }) {
  const known: GateStatus = status === 'PASS' || status === 'BLOCKED' || status === 'NOT_REACHED' || status === 'DEFERRED' ? status : 'UNKNOWN';
  const { variant, label, Icon } = GATE_MAP[known];
  return (
    <Badge variant={variant} className={cn('font-medium', className)} title={`原始状态码：${status}`}>
      <Icon aria-hidden="true" className="h-3.5 w-3.5" />
      {label}
      {showCode ? <span className="font-mono text-[10px] opacity-75">{status}</span> : null}
    </Badge>
  );
}

/** 任意运行阶段字符串（phase / health.status 等）的诚实着色。 */
export function PhaseBadge({ phase, className }: { phase: string; className?: string }) {
  const tone = phase.includes('BLOCKED') || phase.includes('FAILED') || phase === 'DEGRADED'
    ? 'destructive'
    : phase === 'RUNNING' || phase === 'READY' || phase === 'OK' || phase === 'FRESH'
      ? 'success'
      : phase.includes('DEFERRED')
        ? 'info'
        : 'muted';
  return (
    <Badge variant={tone} className={cn('font-mono text-[11px]', className)}>
      {phase}
    </Badge>
  );
}

/** SIMULATION_ONLY 全局标识：每个 ETF 页面顶部显著位置。 */
export function SimulationBadge({ className }: { className?: string }) {
  return (
    <Badge variant="warning" className={cn('font-semibold tracking-wide', className)}>
      SIMULATION_ONLY · 模拟账户
    </Badge>
  );
}
