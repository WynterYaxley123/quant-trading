import { Badge } from '@/components/ui/badge';

/**
 * Global mock-data marker. Mock values are synthetic test fixtures and must
 * never be mistaken for real research results.
 */
export function MockDataBanner() {
  return (
    <div
      role="status"
      aria-label="模拟数据模式：所有数值均为合成测试数据"
      className="flex flex-wrap items-center gap-2 rounded-lg border border-warning/50 bg-warning/10 px-3 py-2"
    >
      <Badge variant="warning" className="font-semibold uppercase tracking-wide">
        模拟数据
      </Badge>
      <span className="text-xs text-warning-foreground dark:text-warning">
        MOCK DATA · 合成测试数据，并非正式研究结果；仅供界面开发。
      </span>
    </div>
  );
}
