import { createRoute } from '@tanstack/react-router';
import { lazy, Suspense } from 'react';
import { rootRoute } from './rootRoute';
import { parseExplorerSearch } from './searchParams';
import { LoadingState } from '@/components/ui/states';

const SectorExplorerPage = lazy(() =>
  import('@/features/sectors/SectorExplorerPage').then((m) => ({ default: m.SectorExplorerPage })),
);

export const sectorsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/sectors',
  validateSearch: parseExplorerSearch,
  component: () => (
    <Suspense fallback={<LoadingState label="正在加载页面" />}>
      <SectorExplorerPage />
    </Suspense>
  ),
});
