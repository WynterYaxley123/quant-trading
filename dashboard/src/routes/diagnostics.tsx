import { createRoute } from '@tanstack/react-router';
import { lazy, Suspense } from 'react';
import { rootRoute } from './rootRoute';
import { parseExplorerSearch } from './searchParams';
import { LoadingState } from '@/components/ui/states';

const DiagnosticsPage = lazy(() =>
  import('@/features/diagnostics/DiagnosticsPage').then((m) => ({ default: m.DiagnosticsPage })),
);

export const diagnosticsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/diagnostics',
  validateSearch: parseExplorerSearch,
  component: () => (
    <Suspense fallback={<LoadingState label="Loading page" />}>
      <DiagnosticsPage />
    </Suspense>
  ),
});
