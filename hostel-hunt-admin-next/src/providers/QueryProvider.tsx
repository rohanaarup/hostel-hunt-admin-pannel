'use client';

import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { isClientError } from '@/services/errors';

/**
 * Single source of truth for app-wide query behavior.
 *
 *  - staleTime 1 min: moving between pages reuses what was just loaded.
 *  - refetchOnWindowFocus: false. A tab switch must not silently reload every list; the Refresh
 *    buttons and the actions (approve, reject...) reload what changed.
 *  - retry: once, and never for a 4xx answer (a 400, 403 or 404 will not get better by asking again).
 *  - refetchOnReconnect: true so a flaky network doesn't strand the owner on a stale view.
 */
function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 1000 * 60,             // 1 minute
        gcTime: 1000 * 60 * 10,           // keep cached data 10 min
        refetchOnWindowFocus: false,
        refetchOnReconnect: true,
        retry: (failureCount, error) => failureCount < 1 && !isClientError(error),
      },
      mutations: {
        retry: 0,
      },
    },
  });
}

export default function QueryProvider({ children }: { children: React.ReactNode }) {
  // useState ensures the QueryClient is created once per mount, not on every render.
  const [client] = useState(() => makeClient());
  return (
    <QueryClientProvider client={client}>
      {children}
      {process.env.NODE_ENV === 'development' && (
        <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-left" />
      )}
    </QueryClientProvider>
  );
}
