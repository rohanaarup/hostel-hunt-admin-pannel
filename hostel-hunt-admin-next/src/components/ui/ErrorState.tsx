'use client';

import React from 'react';
import Icon from './Icon';
import { errorMessage } from '@/services/errors';

interface ErrorStateProps {
  /** The thrown error (axios, ApiError, anything): shown as plain words. */
  error: unknown;
  /** What could not be loaded, e.g. "bookings". */
  what?: string;
  onRetry?: () => void;
  retrying?: boolean;
}

/**
 * What a page shows when its data could not be loaded: the reason in words and a Retry button.
 * Used instead of leaving a spinner or an empty list on screen.
 */
export default function ErrorState({ error, what = 'this page', onRetry, retrying = false }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="py-12 px-6 text-center rounded-2xl border"
      style={{
        background: 'var(--color-error-light)',
        borderColor: 'color-mix(in srgb, var(--color-error) 30%, transparent)',
      }}
    >
      <p className="text-[15px] font-bold mb-1" style={{ color: 'var(--color-error)' }}>
        Could not load {what}
      </p>
      <p className="text-[13px] max-w-md mx-auto" style={{ color: 'var(--color-text-primary)' }}>
        {errorMessage(error)}
      </p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          disabled={retrying}
          className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-[10px] text-sm font-semibold disabled:opacity-60"
          style={{ background: 'var(--color-primary)', color: 'var(--color-text-inverse)' }}
        >
          <Icon name="refresh" className={`w-4 h-4 ${retrying ? 'animate-spin' : ''}`} />
          Retry
        </button>
      )}
    </div>
  );
}
