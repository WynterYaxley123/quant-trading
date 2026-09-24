import { Badge } from '@/components/ui/badge';

/**
 * Global mock-data marker. Mock values are synthetic test fixtures and must
 * never be mistaken for real research results.
 */
export function MockDataBanner() {
  return (
    <div
      role="status"
      aria-label="Mock data mode: all values are synthetic"
      className="flex flex-wrap items-center gap-2 rounded-lg border border-warning/50 bg-warning/10 px-3 py-2"
    >
      <Badge variant="warning" className="font-semibold uppercase tracking-wide">
        Mock data
      </Badge>
      <span className="text-xs text-warning-foreground dark:text-warning">
        Synthetic test fixtures — not real research results. Development use only.
      </span>
    </div>
  );
}
