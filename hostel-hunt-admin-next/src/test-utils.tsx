import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';

/** A fresh query client per test: no retries and no cache carried over, so a failure shows at once. */
export function renderWithQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0, refetchOnWindowFocus: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

/** What axios throws for an HTTP answer. */
export const httpError = (status: number, data: unknown = '<html>Bad gateway</html>') => ({
  message: `Request failed with status code ${status}`,
  response: { status, data, headers: {} },
});
