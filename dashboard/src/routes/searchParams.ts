/** Shared URL search-param parsing for explorer state. */
export function optionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

function optionalHorizon(value: unknown): string | undefined {
  // TanStack Router may parse numeric URL values as numbers on a hard reload.
  // Keep the existing string search contract so a bookmarked 120-day view survives.
  const text = typeof value === 'number' ? String(value) : optionalString(value);
  return text === '10' || text === '40' || text === '120' ? text : undefined;
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
  const horizon = optionalHorizon(search.horizon);
  if (run !== undefined) parsed.run = run;
  if (candidate !== undefined) parsed.candidate = candidate;
  if (date !== undefined) parsed.date = date;
  if (metric !== undefined) parsed.metric = metric;
  if (horizon !== undefined) parsed.horizon = horizon;
  return parsed;
}
