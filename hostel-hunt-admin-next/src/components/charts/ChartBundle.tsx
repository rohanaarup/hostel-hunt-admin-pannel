'use client';

import dynamic from 'next/dynamic';
import React from 'react';

/**
 * Recharts is loaded only on the client (no SSR) to keep the initial bundle
 * slim and to avoid hydration mismatches. Falls back to a small skeleton
 * while the chart bundle is fetched.
 */

const Fallback = () => (
  <div className="h-[220px] w-full rounded-lg bg-ivory-200/40 dark:bg-ivory-800/40 animate-pulse" />
);

export const Donut = dynamic(() => import('./Charts').then(m => m.Donut), {
  ssr: false,
  loading: Fallback,
});

export const SimpleBar = dynamic(() => import('./Charts').then(m => m.SimpleBar), {
  ssr: false,
  loading: Fallback,
});

export const SimpleLine = dynamic(() => import('./Charts').then(m => m.SimpleLine), {
  ssr: false,
  loading: Fallback,
});
