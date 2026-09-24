/** Shared URL search-param parsing for explorer state. */
export function optionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

export interface ExplorerSearch {
  run?: string;
  candidate?: string;
  date?: string;
  metric?: string;
  horizon?: string;
}

export function parseExplorerSearch(search: Record<string, unknown>): ExplorerSearch {
  const parsed: ExplorerSearch = {};
  const run = optionalString(search.run);
  const candidate = optionalString(search.candidate);
  const date = optionalString(search.date);
  const metric = optionalString(search.metric);
  const horizon = optionalString(search.horizon);
  if (run !== undefined) parsed.run = run;
  if (candidate !== undefined) parsed.candidate = candidate;
  if (date !== undefined) parsed.date = date;
  if (metric !== undefined) parsed.metric = metric;
  if (horizon !== undefined) parsed.horizon = horizon;
  return parsed;
}
