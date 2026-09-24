import { createRoute } from '@tanstack/react-router';
import { lazy, Suspense } from 'react';
import { rootRoute } from './rootRoute';
import { parseExplorerSearch } from './searchParams';
import { LoadingState } from '@/components/ui/states';

const OverviewPage = lazy(() =>
  import('@/features/overview/OverviewPage').then((m) => ({ default: m.OverviewPage })),
);

export const overviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  validateSearch: parseExplorerSearch,
  component: () => (
    <Suspense fallback={<LoadingState label="Loading page" />}>
      <OverviewPage />
    </Suspense>
  ),
});
