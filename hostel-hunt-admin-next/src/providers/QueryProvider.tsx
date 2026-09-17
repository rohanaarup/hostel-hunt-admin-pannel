'use client';

import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

/**
 * Single source of truth for app-wide query behavior.
 *
 * Defaults chosen for the Hostel Hunt admin panel:
 *  - staleTime 2 min: list data doesn't go stale every keystroke, but a
 *    tab-back-into-panel feels current because of refetchOnWindowFocus.
 *  - refetchOnWindowFocus: true (matches the brief — feels live without
 *    a real websocket).
 *  - retry: 1 — auth failures get surfaced fast, the axios 401-refresh
 *    interceptor handles the genuine auth edge case.
 *  - refetchOnReconnect: true so a flaky network doesn't strand the owner
 *    on a stale view.
 */
function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 1000 * 60 * 2,         // 2 minutes
        gcTime: 1000 * 60 * 10,           // keep cached data 10 min
        refetchOnWindowFocus: true,
        refetchOnReconnect: true,
        retry: 1,
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
