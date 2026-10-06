import { act, render } from '@testing-library/react';
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router';
import { createAppRouter, type AppRouter } from '@/app/router';
import { createMockApiAdapter } from '@/api/adapters/mock-api';
import { setResearchApiForTesting } from '@/api';
import type { ResearchDataPort } from '@/api/contracts';

/**
 * Render the full app (shell + routes) against an in-memory history and a
 * controlled data port. Mock mode is only activated via explicit env, exactly
 * like production behaviour.
 */
export async function renderApp(
  initialPath = '/',
  port: ResearchDataPort = createMockApiAdapter(),
): Promise<AppRouter> {
  setResearchApiForTesting(port);
  const router = createAppRouter(createMemoryHistory({ initialEntries: [initialPath === '/' || initialPath.startsWith('/?') ? '/research' + initialPath.slice(1) : initialPath] }));
  // Settle React effects with the controlled asynchronous port before callers
  // make synchronous assertions. router.load() alone does not flush effects.
  await act(async () => {
    render(<RouterProvider router={router} />);
    await router.load();
  });
  return router;
}

export function installMockApi(): void {
  setResearchApiForTesting(createMockApiAdapter());
}
