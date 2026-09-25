import { createRoute } from '@tanstack/react-router';
import { lazy, Suspense } from 'react';
import { rootRoute } from './rootRoute';
import { parseExplorerSearch } from './searchParams';
import { LoadingState } from '@/components/ui/states';

const DevelopmentExplorerPage = lazy(() =>
  import('@/features/development/DevelopmentExplorerPage').then((m) => ({
    default: m.DevelopmentExplorerPage,
  })),
);

export const developmentRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/development',
  validateSearch: parseExplorerSearch,
  component: () => (
    <Suspense fallback={<LoadingState label="Loading page" />}>
      <DevelopmentExplorerPage />
    </Suspense>
  ),
});
