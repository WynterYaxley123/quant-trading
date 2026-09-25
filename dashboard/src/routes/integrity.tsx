import { createRoute } from '@tanstack/react-router';
import { lazy, Suspense } from 'react';
import { rootRoute } from './rootRoute';
import { parseExplorerSearch } from './searchParams';
import { LoadingState } from '@/components/ui/states';

const ResearchIntegrityPage = lazy(() =>
  import('@/features/integrity/ResearchIntegrityPage').then((m) => ({
    default: m.ResearchIntegrityPage,
  })),
);

export const integrityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/integrity',
  validateSearch: parseExplorerSearch,
  component: () => (
    <Suspense fallback={<LoadingState label="Loading page" />}>
      <ResearchIntegrityPage />
    </Suspense>
  ),
});
