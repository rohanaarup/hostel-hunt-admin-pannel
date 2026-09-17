'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Input, Textarea, Select } from '@/components/ui/Input';
import { useSearchParams } from 'next/navigation';
import DashboardLayout from '@/components/common/DashboardLayout';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import StatusBadge from '@/components/ui/StatusBadge';
import Icon from '@/components/ui/Icon';
import type { Booking } from '@/types';
import { bookingService } from '@/services/api';
import gsap from 'gsap';

// ─── Helpers ────────────────────────────────────────────────────────────────

function timeAgo(iso: string) {
  if (!iso) return '-';
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

function formatDate(d: string | null | undefined) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function getInitials(name: string) {
  return (name || 'G').split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
}

// ─── Booking Card ────────────────────────────────────────────────────────────

interface CardProps {
  booking: Booking;
  onAction: (id: string, action: 'approve' | 'reject' | 'verify' | 'mark-paid') => void;
}

const BookingCard: React.FC<CardProps> = ({ booking, onAction }) => {
  const status = booking.status as string;
  const isOffline = booking.payment_mode === 'offline';
  const isPending = status === 'pending';
  const canAct = status !== 'paid' && status !== 'rejected' && status !== 'cancelled';
  const roomLabel = (booking as any).room_display || (booking as any).room_name || '—';
  const hostelName = (booking as any).hostel_name || '—';

  return (
    <div
      className="rounded-2xl p-5 flex flex-col gap-4 transition-all duration-200 hover:shadow-md group"
      style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
      }}
      onMouseEnter={e => gsap.to(e.currentTarget, { y: -2, duration: 0.2, ease: 'power2.out' })}
      onMouseLeave={e => gsap.to(e.currentTarget, { y: 0, duration: 0.2, ease: 'power2.out' })}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
            style={{
              background: 'var(--color-primary-light)',
              color: 'var(--color-primary)',
              border: '1px solid color-mix(in srgb, var(--color-primary) 20%, transparent)',
            }}
          >
            {getInitials(booking.student_name)}
          </div>
          <div className="min-w-0">
            <p className="text-[15px] font-bold truncate" style={{ color: 'var(--color-text-primary)' }}>
              {booking.student_name || 'Guest'}
            </p>
            <p className="text-[12px] font-medium truncate" style={{ color: 'var(--color-text-muted)' }}>
              {booking.student_phone || 'No phone'}
            </p>
          </div>
        </div>
        <StatusBadge status={status} />
      </div>

      {/* Hostel chip */}
      <div
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg"
        style={{ background: 'var(--color-background)' }}
      >
        <Icon name="hostel" className="w-3.5 h-3.5 flex-shrink-0" />
        <span className="text-[12px] font-semibold truncate" style={{ color: 'var(--color-text-secondary)' }}>
          {hostelName}
        </span>
      </div>

      {/* Info grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-3">
        {[
          { label: 'Room', value: roomLabel },
          { label: 'Bed', value: booking.bed_number || '—' },
          { label: 'Check-in', value: formatDate((booking as any).check_in_date) },
          {
            label: 'Payment',
            value: <span style={{ color: isOffline ? 'var(--color-warning)' : 'var(--color-primary)' }} className="capitalize">{booking.payment_mode}</span>,
          },
          {
            label: 'Rent',
            value: booking.amount ? (
              <span style={{ color: 'var(--color-primary)', fontWeight: 700 }}>
                ₹{Number(booking.amount).toLocaleString('en-IN')}
              </span>
            ) : '—',
          },
          { label: 'Requested', value: timeAgo(booking.created_at) },
        ].map(({ label, value }) => (
          <div key={label}>
            <p className="text-[10px] font-bold uppercase tracking-wider mb-0.5" style={{ color: 'var(--color-text-muted)' }}>
              {label}
            </p>
            <p className="text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              {value || '—'}
            </p>
          </div>
        ))}
      </div>

      {/* Notes */}
      {(booking as any).notes && (
        <p
          className="text-[12px] italic rounded-lg px-3 py-2"
          style={{
            color: 'var(--color-text-muted)',
            background: 'var(--color-background)',
          }}
        >
          &ldquo;{(booking as any).notes}&rdquo;
        </p>
      )}

      {/* Actions */}
      {canAct && (
        <div
          className="flex items-center gap-2 mt-auto pt-3 border-t"
          style={{ borderColor: 'var(--color-border)' }}
        >
          {isOffline && (
            <button
              onClick={() => onAction(booking.id, 'mark-paid')}
              className="flex-1 text-[12px] font-bold py-2 rounded-[8px] transition-all hover:opacity-80"
              style={{
                background: 'var(--color-success-light)',
                color: 'var(--color-success)',
                border: '1px solid color-mix(in srgb, var(--color-success) 30%, transparent)',
              }}
            >
              Mark Paid
            </button>
          )}
          {!isOffline && isPending && (
            <button
              onClick={() => onAction(booking.id, 'verify')}
              className="flex-1 text-[12px] font-bold py-2 rounded-[8px] transition-all hover:opacity-80"
              style={{
                background: 'var(--color-primary-light)',
                color: 'var(--color-primary)',
                border: '1px solid color-mix(in srgb, var(--color-primary) 30%, transparent)',
              }}
            >
              Verify Payment
            </button>
          )}
          {isPending && isOffline && (
            <button
              onClick={() => onAction(booking.id, 'approve')}
              className="flex-1 text-[12px] font-bold py-2 rounded-[8px] transition-all hover:opacity-80"
              style={{
                background: 'var(--color-success-light)',
                color: 'var(--color-success)',
                border: '1px solid color-mix(in srgb, var(--color-success) 30%, transparent)',
              }}
            >
              Accept
            </button>
          )}
          {isPending && (
            <button
              onClick={() => onAction(booking.id, 'reject')}
              className="flex-1 text-[12px] font-bold py-2 rounded-[8px] transition-all hover:opacity-80"
              style={{
                background: 'var(--color-error-light)',
                color: 'var(--color-error)',
                border: '1px solid color-mix(in srgb, var(--color-error) 30%, transparent)',
              }}
            >
              Reject
            </button>
          )}
        </div>
      )}
    </div>
  );
};

// ─── Empty State ──────────────────────────────────────────────────────────────

const EmptyState: React.FC<{ tab: string }> = ({ tab }) => {
  const messages: Record<string, { icon: any; title: string; body: string }> = {
    'offline-requests': { icon: 'inbox',    title: 'No pending requests',   body: 'Offline booking requests from students will appear here.' },
    'offline-confirmed':{ icon: 'check',    title: 'No confirmed bookings', body: 'Accepted offline bookings will appear here.' },
    'online-requests':  { icon: 'building', title: 'No online requests',    body: 'Online bookings awaiting verification will appear here.' },
    'online-payments':  { icon: 'money',    title: 'No payments received',  body: 'Verified online payment transactions will appear here.' },
  };
  const m = messages[tab] || { icon: 'inbox', title: 'No bookings', body: 'Bookings will appear here.' };
  return (
    <div
      className="py-20 text-center rounded-2xl"
      style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
    >
      <div
        className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4"
        style={{ background: 'var(--color-border)', color: 'var(--color-text-muted)' }}
      >
        <Icon name={m.icon} className="w-8 h-8" />
      </div>
      <p className="text-[15px] font-bold mb-1" style={{ color: 'var(--color-text-primary)' }}>{m.title}</p>
      <p className="text-[13px] max-w-sm mx-auto" style={{ color: 'var(--color-text-muted)' }}>{m.body}</p>
    </div>
  );
};

// ─── Main Bookings Page ───────────────────────────────────────────────────────

function BookingsContent() {
  const searchParams = useSearchParams();
  const defaultTab = searchParams.get('tab') || 'offline-requests';
  const [currentTab, setCurrentTab] = useState(defaultTab);
  const [searchQuery, setSearchQuery] = useState('');
  const [actionTarget, setActionTarget] = useState<{ id: string; action: 'approve' | 'reject' | 'verify' | 'mark-paid' } | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const { data: bookings = [] as Booking[], isLoading } = useQuery<Booking[]>({
    queryKey: ['bookings'],
    queryFn: () => bookingService.getBookings().then(r => Array.isArray(r?.data) ? r.data : Array.isArray(r) ? r : [])
  });

  // Stagger cards on tab switch
  useEffect(() => {
    if (!isLoading && gridRef.current) {
      const cards = gridRef.current.querySelectorAll('.booking-card');
      gsap.fromTo(cards,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.35, stagger: 0.06, ease: 'power2.out' }
      );
    }
  }, [currentTab, isLoading]);

  const offlineRequests  = bookings.filter(b => b.payment_mode === 'offline' && b.status === 'pending');
  const offlineConfirmed = bookings.filter(b => b.payment_mode === 'offline' && ['confirmed', 'approved', 'paid'].includes(b.status as string));
  const onlineRequests   = bookings.filter(b => b.payment_mode === 'online' && ['pending', 'approved'].includes(b.status as string));
  const onlinePayments   = bookings.filter(b => b.payment_mode === 'online' && b.status as string === 'paid');

  const tabData: Record<string, Booking[]> = {
    'offline-requests':  offlineRequests,
    'offline-confirmed': offlineConfirmed,
    'online-requests':   onlineRequests,
    'online-payments':   onlinePayments,
  };

  const tabs = [
    { id: 'offline-requests',  label: 'Requests',          count: offlineRequests.length },
    { id: 'offline-confirmed', label: 'Confirmed',          count: offlineConfirmed.length },
    { id: 'online-requests',   label: 'Online Requests',    count: onlineRequests.length },
    { id: 'online-payments',   label: 'Payments Received',  count: onlinePayments.length },
  ];

  const HEADER: Record<string, { title: string; desc: string }> = {
    'offline-requests':  { title: 'Offline Booking Requests', desc: 'Pending requests from students who selected offline payment' },
    'offline-confirmed': { title: 'Confirmed Bookings',        desc: 'Accepted and confirmed offline bookings' },
    'online-requests':   { title: 'Online Booking Requests',   desc: 'Online bookings awaiting payment verification' },
    'online-payments':   { title: 'Payments Received',         desc: 'Verified online payment transactions' },
  };

  const q = searchQuery.toLowerCase();
  const filtered = (tabData[currentTab] || []).filter(b =>
    !q ||
    (b.student_name || '').toLowerCase().includes(q) ||
    (b.student_phone || '').includes(q) ||
    ((b as any).room_display || '').toLowerCase().includes(q) ||
    ((b as any).room_name || '').toLowerCase().includes(q) ||
    ((b as any).hostel_name || '').toLowerCase().includes(q) ||
    (b.bed_number || '').toLowerCase().includes(q)
  );

  const handleAction = async () => {
    if (!actionTarget) return;
    const { id, action } = actionTarget;
    try {
      if (action === 'approve') await bookingService.approveBooking(id);
      else if (action === 'reject') await bookingService.rejectBooking(id);
      else if (action === 'verify') await bookingService.verifyPayment(id);
      else if (action === 'mark-paid') await bookingService.markBookingPaid(id);
      
      queryClient.invalidateQueries({ queryKey: ['bookings'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'stats'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'activity'] });
    } catch (error) {
      console.error(`Failed to ${action} booking:`, error);
      alert(`Failed to update booking status. Please try again.`);
    } finally {
      setActionTarget(null);
    }
  };

  const DIALOGS: Record<string, { title: string; message: string; label: string; variant: 'info' | 'danger' }> = {
    approve:     { title: 'Confirm booking?',  message: 'This will confirm the booking request.',   label: 'Confirm',   variant: 'info' },
    reject:      { title: 'Reject booking?',   message: 'This will reject the booking request.',    label: 'Reject',    variant: 'danger' },
    verify:      { title: 'Verify Payment?',   message: 'This will verify the online payment.',     label: 'Verify',    variant: 'info' },
    'mark-paid': { title: 'Mark as Paid?',     message: 'This will mark this booking as paid.',     label: 'Mark Paid', variant: 'info' },
  };

  const dialogCfg = actionTarget ? DIALOGS[actionTarget.action] : null;
  const headerInfo = HEADER[currentTab];

  const summaryStats = [
    { label: 'Pending',   value: bookings.filter(b => b.status === 'pending').length,                  color: 'var(--color-warning)' },
    { label: 'Confirmed', value: bookings.filter(b => b.status === 'confirmed').length,                 color: 'var(--color-success)' },
    { label: 'Paid',      value: bookings.filter(b => (b.status as string) === 'paid').length,         color: 'var(--color-primary)' },
    { label: 'Total',     value: bookings.length,                                                      color: 'var(--color-text-primary)' },
  ];

  return (
    <DashboardLayout title="Bookings">
      {dialogCfg && actionTarget && (
        <ConfirmDialog
          isOpen
          title={dialogCfg.title}
          message={dialogCfg.message}
          confirmLabel={dialogCfg.label}
          variant={dialogCfg.variant}
          onConfirm={handleAction}
          onCancel={() => setActionTarget(null)}
        />
      )}

      <div className="w-full space-y-6">
        {/* Page header */}
        <div className="animate-fade-in-up">
          <h1
            className="text-2xl font-extrabold tracking-tight"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}
          >
            {headerInfo.title}
          </h1>
          <p className="mt-1 text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>
            {headerInfo.desc}
          </p>
        </div>

        {/* Summary chips */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 animate-fade-in-up" style={{ animationDelay: '60ms' }}>
          {summaryStats.map(s => (
            <div
              key={s.label}
              className="flex items-center gap-3 px-4 py-3 rounded-xl"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
              }}
            >
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center font-black text-base"
                style={{ background: `color-mix(in srgb, ${s.color} 12%, transparent)`, color: s.color }}
              >
                {s.value}
              </div>
              <span className="text-[12px] font-semibold" style={{ color: 'var(--color-text-muted)' }}>{s.label}</span>
            </div>
          ))}
        </div>

        {/* Tabs + search */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 animate-fade-in-up" style={{ animationDelay: '120ms' }}>
          {/* Tab bar */}
          <div
            className="flex items-center p-1 rounded-xl overflow-x-auto flex-shrink-0"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
          >
            {tabs.map(tab => {
              const isActive = currentTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => { setCurrentTab(tab.id); setSearchQuery(''); }}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all whitespace-nowrap"
                  style={
                    isActive
                      ? { background: 'var(--color-primary)', color: 'var(--color-text-inverse)' }
                      : { color: 'var(--color-text-muted)' }
                  }
                >
                  {tab.label}
                  <span
                    className="px-2 py-0.5 rounded-full text-[11px] font-bold"
                    style={
                      isActive
                        ? { background: 'rgba(255,255,255,0.2)', color: 'inherit' }
                        : { background: 'var(--color-border)', color: 'var(--color-text-muted)' }
                    }
                  >
                    {tab.count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Search */}
          <div className="relative flex-1 min-w-0">
            <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" />
            <Input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search name, room, hostel…"
              className="w-full pl-9 pr-4 py-2.5 rounded-xl text-sm font-medium outline-none transition-all"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            />
          </div>

          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ['bookings'] })}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-50"
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text-secondary)',
            }}
          >
            <Icon name="refresh" className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Cards grid */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[...Array(6)].map((_, i) => (
              <div
                key={i}
                className="h-64 rounded-2xl animate-pulse"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
              />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState tab={currentTab} />
        ) : (
          <div ref={gridRef} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map(b => (
              <div key={b.id} className="booking-card">
                <BookingCard booking={b} onAction={(id, action) => setActionTarget({ id, action })} />
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

export default function BookingsPage() {
  return (
    <React.Suspense fallback={
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--color-background)' }}>
        <div className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--color-primary)' }} />
      </div>
    }>
      <BookingsContent />
    </React.Suspense>
  );
}
