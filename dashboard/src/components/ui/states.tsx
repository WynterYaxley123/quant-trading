import { AlertTriangle, PlugZap, RotateCw, Inbox } from 'lucide-react';
import { Button } from './button';
import { Skeleton } from './skeleton';
import type { ResearchApiError } from '@/api/errors';

/** Loading skeleton with a polite live announcement (accessibility). */
export function LoadingState({ label = '正在加载研究数据' }: { label?: string }) {
  return (
    <div className="relative flex flex-col gap-3" role="status" aria-live="polite">
      <span className="sr-only">{label}…</span>
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

export function EmptyState({
  title = '暂无数据',
  description = '当前筛选条件下没有可显示的数据。',
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border p-10 text-center">
      <Inbox aria-hidden="true" className="h-6 w-6 text-muted-foreground" />
      <p className="text-sm font-medium">{title}</p>
      <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

/** Healthy Research service with no approved Development run. */
export function ResearchEmptyState({ onRetry }: { onRetry?: () => void }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-dashed border-border p-10 text-center" role="status">
      <p className="text-base font-semibold">Research API 已连接</p>
      <p className="text-sm text-muted-foreground">未配置获准的 Development 研究产物。</p>
      <p className="text-sm text-muted-foreground">Validation 与 Final OOS 保持封存。配置现有的获准产物后刷新；控制台不会生成研究数据或启动 Shadow。</p>
      <p className="text-xs text-muted-foreground">SERVICE READY · NO APPROVED DEVELOPMENT ARTIFACT CONFIGURED</p>
      {onRetry ? <Button variant="outline" size="sm" className="self-center" onClick={onRetry}>重新检查产物</Button> : null}
    </div>
  );
}

/** API disconnected — shown when the Research API cannot be reached. */
export function DisconnectedState({ onRetry, endpoint }: { onRetry?: () => void; endpoint?: string }) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border p-10 text-center"
      role="alert"
    >
      <PlugZap aria-hidden="true" className="h-6 w-6 text-muted-foreground" />
      <p className="text-base font-semibold">研究数据接口未连接</p>
      <p className="max-w-md text-sm text-muted-foreground">
        无法连接到本地 Research API{endpoint ? `（${endpoint}）` : ''}。运行 scripts/Start-EtfQuantConsole.ps1 启动统一控制台；若启动失败，请查看启动器输出的组件日志，然后重试。
      </p>
      <p className="text-xs text-muted-foreground">API DISCONNECTED</p>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw aria-hidden="true" />
          重试连接
        </Button>
      ) : null}
    </div>
  );
}

/** Human-readable error state (never a stack trace). */
export function ErrorState({
  error,
  onRetry,
}: {
  error: ResearchApiError;
  onRetry?: () => void;
}) {
  if (error.isDisconnected) return <DisconnectedState onRetry={onRetry} />;
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-destructive/40 p-10 text-center" role="alert">
      <AlertTriangle aria-hidden="true" className="h-6 w-6 text-destructive" />
      <p className="text-base font-semibold">无法加载研究数据</p>
      <p className="max-w-md text-sm text-muted-foreground">{error.userMessage}</p>
      {error.code === 'BAD_QUERY' && error.status !== null && error.message !== error.userMessage ? (
        <p className="max-w-md text-xs text-muted-foreground">接口说明：{error.message}</p>
      ) : null}
      <p className="text-xs text-muted-foreground">错误代码：{error.code}</p>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw aria-hidden="true" />
          重试
        </Button>
      ) : null}
    </div>
  );
}
