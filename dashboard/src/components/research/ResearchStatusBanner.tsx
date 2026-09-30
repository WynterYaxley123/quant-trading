import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/cn';
import { useAppData } from '@/app/AppDataProvider';
import { phaseLabel, sealLabel } from '@/lib/labels';

/**
 * Global research status banner — compact but persistent on every research
 * page. It communicates the research phase before any chart is read.
 * Status is conveyed with text (never colour alone).
 */
export function ResearchStatusBanner({ className }: { className?: string }) {
  const { status } = useAppData();
  return (
    <div
      role="status"
      aria-label="研究状态"
      className={cn(
        'flex flex-wrap items-center gap-2 rounded-lg border border-border bg-muted/50 px-3 py-2',
        className,
      )}
    >
      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        研究状态
      </span>
      {status ? (
        <>
          <Badge variant="warning">{phaseLabel(status.phase)}</Badge>
          <Badge variant="destructive">{status.executable ? '可执行' : '不可执行'}</Badge>
          <Badge variant="sealed">Validation（验证集）：{sealLabel(status.validation)}</Badge>
          <Badge variant="sealed">Final OOS（最终样本外）：{sealLabel(status.finalOos)}</Badge>
        </>
      ) : <span className="text-xs text-muted-foreground">等待研究数据接口</span>}
    </div>
  );
}
