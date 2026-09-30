import { Select } from '@/components/ui/select';
import type { RunSummary } from '@/api/contracts';
import { METRIC_LABELS } from '@/lib/format';

/**
 * Explorer filter controls. All filter values live in URL search params so
 * refresh / back / forward / bookmark restore the explorer state.
 */

export function RunFilter({
  runs,
  value,
  onChange,
}: {
  runs: RunSummary[];
  value: string;
  onChange: (runId: string) => void;
}) {
  return (
    <Select
      label="研究运行"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      options={runs.map((run) => ({ value: run.runId, label: `${run.runId}（第 ${run.iteration} 轮）` }))}
    />
  );
}

export function CandidateFilter({
  candidateIds,
  value,
  onChange,
}: {
  candidateIds: string[];
  value: string;
  onChange: (candidateId: string) => void;
}) {
  return (
    <Select
      label="候选方案"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      options={candidateIds.map((id) => ({ value: id, label: id }))}
    />
  );
}

export function DateFilter({
  dates,
  value,
  onChange,
}: {
  dates: string[];
  value: string;
  onChange: (date: string) => void;
}) {
  return (
    <Select
      label="日期"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      options={dates.map((date) => ({ value: date, label: date }))}
    />
  );
}

export function MetricFilter({
  value,
  onChange,
}: {
  value: string;
  onChange: (metric: string) => void;
}) {
  return (
    <Select
      label="指标"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      options={Object.entries(METRIC_LABELS).map(([key, label]) => ({ value: key, label }))}
    />
  );
}

export function HorizonFilter({
  value,
  onChange,
}: {
  value: string;
  onChange: (horizon: string) => void;
}) {
  return (
    <Select
      label="预测周期"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      options={[
        { value: '10', label: '10日' },
        { value: '40', label: '40日' },
        { value: '120', label: '120日' },
      ]}
    />
  );
}

export function FilterBar({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-3 rounded-lg border border-border bg-card p-3 sm:grid-cols-2 lg:grid-cols-4">
      {children}
    </div>
  );
}
