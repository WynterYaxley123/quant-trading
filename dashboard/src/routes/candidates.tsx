import { createRoute } from '@tanstack/react-router';
import { lazy, Suspense } from 'react';
import { rootRoute } from './rootRoute';
import { parseExplorerSearch } from './searchParams';
import { LoadingState } from '@/components/ui/states';

const CandidateComparisonPage = lazy(() =>
  import('@/features/candidates/CandidateComparisonPage').then((m) => ({
    default: m.CandidateComparisonPage,
  })),
);

export const candidatesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/candidates',
  validateSearch: parseExplorerSearch,
  component: () => (
    <Suspense fallback={<LoadingState label="正在加载页面" />}>
      <CandidateComparisonPage />
    </Suspense>
  ),
});
