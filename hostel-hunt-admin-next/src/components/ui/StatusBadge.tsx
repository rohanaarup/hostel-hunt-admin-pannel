'use client';

import React from 'react';

/**
 * Centralized status badge for bookings, payments, residents.
 * Color classes reference semantic tokens only — no hex.
 */

export type StatusTone = 'pending' | 'success' | 'error' | 'warning' | 'info' | 'neutral' | 'accent';

interface StatusBadgeProps {
  status: string;
  tone?: StatusTone;
  className?: string;
}

const TONE_CLASSES: Record<StatusTone, string> = {
  pending:  'bg-amber-500/10  text-amber-500   border-amber-500/30',
  success:  'bg-emerald-500/10 text-emerald-500 border-emerald-500/30',
  error:    'bg-red-500/10    text-red-500     border-red-500/30',
  warning:  'bg-amber-500/10  text-amber-500   border-amber-500/30',
  info:     'bg-blue-500/10   text-blue-500    border-blue-500/30',
  neutral:  'bg-ivory-300/60  text-ink-700     border-ivory-400/40 dark:bg-ivory-700/40 dark:text-ivory-300 dark:border-ivory-600/30',
  accent:   'bg-auburn-500/10 text-auburn-500  border-auburn-500/30',
};

const STATUS_TO_TONE: Record<string, StatusTone> = {
  // booking
  pending: 'pending',
  approved: 'success',
  confirmed: 'success',
  verified: 'success',
  paid: 'info',
  rejected: 'error',
  cancelled: 'neutral',
  checked_in: 'success',
  checked_out: 'neutral',
  // payment
  completed: 'success',
  failed: 'error',
  refunded: 'info',
  overdue: 'error',
  partial: 'warning',
  // resident
  active: 'success',
  vacated: 'neutral',
  notice_given: 'pending',
};

export function toneFor(status: string): StatusTone {
  return STATUS_TO_TONE[status] || 'neutral';
}

export default function StatusBadge({ status, tone, className = '' }: StatusBadgeProps) {
  const resolvedTone = tone ?? toneFor(status);
  const label = status.replace(/_/g, ' ');
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold border capitalize whitespace-nowrap ${TONE_CLASSES[resolvedTone]} ${className}`}
    >
      {label}
    </span>
  );
}
