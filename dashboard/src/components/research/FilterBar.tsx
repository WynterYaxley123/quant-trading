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
      label="Run"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      options={runs.map((run) => ({ value: run.runId, label: `${run.runId} (iteration ${run.iteration})` }))}
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
      label="Candidate"
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
      label="Date"
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
      label="Metric"
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
      label="Horizon"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      options={[
        { value: '10', label: '10' },
        { value: '40', label: '40' },
        { value: '120', label: '120' },
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
