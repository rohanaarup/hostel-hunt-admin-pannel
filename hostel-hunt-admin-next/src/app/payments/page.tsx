'use client';

import React, { useState, useEffect, useRef } from 'react';
import DashboardLayout from '@/components/common/DashboardLayout';
import StatusBadge from '@/components/ui/StatusBadge';
import Icon from '@/components/ui/Icon';
import type { Payment, PaymentStatus } from '@/types';
import ErrorState from '@/components/ui/ErrorState';
import { usePayments } from '@/hooks/queries';
import gsap from 'gsap';

// Payments here are the online (Razorpay) payments students make for bookings, read from
// GET /payments/admin-list/. The page is read-only: there is no offline rent ledger in the backend.

function formatDate(d: string | null | undefined) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function amountOf(p: Payment) {
  const n = parseFloat(p.amount);
  return Number.isFinite(n) ? n : 0;
}

function sumOf(payments: Payment[], statuses: PaymentStatus[]) {
  return payments.filter(p => statuses.includes(p.status)).reduce((s, p) => s + amountOf(p), 0);
}

export default function PaymentsPage() {
  const [filter, setFilter] = useState<PaymentStatus | 'all'>('all');
  const tableRef = useRef<HTMLTableSectionElement>(null);

  const { data, isLoading, error, refetch, isFetching } = usePayments();

  const all = data?.items ?? [];
  const total = data?.count ?? 0;
  const payments = filter === 'all' ? all : all.filter(p => p.status === filter);

  useEffect(() => {
    if (!isLoading && tableRef.current) {
      const rows = tableRef.current.querySelectorAll('tr');
      gsap.fromTo(rows,
        { opacity: 0, x: -12 },
        { opacity: 1, x: 0, duration: 0.3, stagger: 0.04, ease: 'power2.out' }
      );
    }
  }, [isLoading, filter]);

  const summaryCards = [
    {
      label: 'Collected',
      amount: sumOf(all, ['SUCCESS']),
      icon: 'money' as const,
      color: 'var(--color-success)',
      lightColor: 'var(--color-success-light)',
    },
    {
      label: 'In Progress',
      amount: sumOf(all, ['CREATED', 'PENDING']),
      icon: 'wallet' as const,
      color: 'var(--color-warning)',
      lightColor: 'var(--color-warning-light)',
    },
    {
      label: 'Failed or Refunded',
      amount: sumOf(all, ['FAILED', 'REFUNDED']),
      icon: 'alert' as const,
      color: 'var(--color-error)',
      lightColor: 'var(--color-error-light)',
    },
    {
      label: 'Total Records',
      amount: total,
      icon: 'tag' as const,
      color: 'var(--color-primary)',
      lightColor: 'var(--color-primary-light)',
      isCount: true,
    },
  ];

  const filterTabs: { id: PaymentStatus | 'all'; label: string }[] = [
    { id: 'all',      label: 'All' },
    { id: 'CREATED',  label: 'Created' },
    { id: 'PENDING',  label: 'Pending' },
    { id: 'SUCCESS',  label: 'Paid' },
    { id: 'FAILED',   label: 'Failed' },
    { id: 'REFUNDED', label: 'Refunded' },
  ];

  return (
    <DashboardLayout title="Payments">
      <div className="w-full space-y-6 animate-fade-in-up">

        {/* Page header */}
        <div>
          <h1
            className="text-2xl font-extrabold tracking-tight"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}
          >
            Payments
          </h1>
          <p className="mt-1 text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>
            Online payments for your hostels. Offline rent tracking is not available yet.
          </p>
        </div>

        {error ? (
          <ErrorState error={error} what="payments" onRetry={() => refetch()} retrying={isFetching} />
        ) : null}

        {total > all.length ? (
          <div className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
            Showing the latest {all.length} of {total} payments.
          </div>
        ) : null}

        {/* Summary bento grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {summaryCards.map(s => (
            <div
              key={s.label}
              className="relative overflow-hidden rounded-2xl p-5 transition-all duration-200 hover:shadow-md"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
              }}
            >
              <div
                className="absolute top-0 left-0 w-1 h-full rounded-l-full"
                style={{ background: s.color }}
              />
              <div className="pl-2">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center mb-3"
                  style={{ background: s.lightColor, color: s.color }}
                >
                  <Icon name={s.icon} className="w-5 h-5" />
                </div>
                <div className="text-[22px] font-extrabold" style={{ color: 'var(--color-text-primary)' }}>
                  {s.isCount ? s.amount : `₹${s.amount.toLocaleString('en-IN')}`}
                </div>
                <div className="text-[11px] font-semibold mt-1 uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
                  {s.label}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Filter tabs + table */}
        <div
          className="rounded-2xl overflow-hidden"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
        >
          <div
            className="flex gap-1 p-3 border-b overflow-x-auto"
            style={{ borderColor: 'var(--color-border)' }}
          >
            {filterTabs.map(f => (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                className="px-4 py-1.5 rounded-[8px] text-sm font-semibold transition-all whitespace-nowrap"
                style={
                  filter === f.id
                    ? { background: 'var(--color-primary)', color: 'var(--color-text-inverse)' }
                    : { color: 'var(--color-text-muted)' }
                }
              >
                {f.label}
              </button>
            ))}
          </div>

          {isLoading ? (
            <div className="py-16 text-center">
              <div className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin mx-auto" style={{ borderColor: 'var(--color-primary)' }} />
            </div>
          ) : payments.length === 0 ? (
            <div className="py-16 text-center">
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
                style={{ background: 'var(--color-border)', color: 'var(--color-text-muted)' }}
              >
                <Icon name="money" className="w-7 h-7" />
              </div>
              <p className="font-semibold" style={{ color: 'var(--color-text-muted)' }}>No payments in this category</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                    {['Student', 'Hostel', 'Amount', 'Status', 'Created', 'Paid on'].map((h, i) => (
                      <th
                        key={h}
                        className={`px-5 py-3 text-[10px] uppercase tracking-wider font-bold ${i === 1 ? 'hidden sm:table-cell' : i >= 4 ? 'hidden md:table-cell' : ''}`}
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody ref={tableRef}>
                  {payments.map(pay => (
                    <tr
                      key={pay.id}
                      className="transition-colors last:border-0"
                      style={{ borderBottom: '1px solid var(--color-border)' }}
                    >
                      <td className="px-5 py-4">
                        <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                          {pay.student_name || 'Unknown'}
                        </p>
                        <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                          {pay.student_phone || '—'}
                        </p>
                      </td>
                      <td className="px-5 py-4 hidden sm:table-cell">
                        <p className="text-sm" style={{ color: 'var(--color-text-primary)' }}>{pay.hostel_name}</p>
                        <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                          {[pay.room_number && `Room ${pay.room_number}`, pay.bed_number && `Bed ${pay.bed_number}`].filter(Boolean).join(' · ') || '—'}
                        </p>
                      </td>
                      <td className="px-5 py-4">
                        <span className="font-bold text-sm" style={{ color: 'var(--color-text-primary)' }}>
                          ₹{amountOf(pay).toLocaleString('en-IN')}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <StatusBadge status={pay.status.toLowerCase()} />
                      </td>
                      <td className="px-5 py-4 hidden md:table-cell">
                        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{formatDate(pay.created_at)}</span>
                      </td>
                      <td className="px-5 py-4 hidden md:table-cell">
                        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{formatDate(pay.verified_at)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
