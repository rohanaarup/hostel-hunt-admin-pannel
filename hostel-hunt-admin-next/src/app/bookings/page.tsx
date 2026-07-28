'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import DashboardLayout from '@/components/common/DashboardLayout';
import { useTheme } from '@/contexts/ThemeContext';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import type { Booking } from '@/types';
import { bookingService } from '@/services/api';

const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  pending:   { label: 'Pending',   cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30' },
  confirmed: { label: 'Confirmed', cls: 'bg-green-500/10 text-green-400 border-green-500/30' },
  approved:  { label: 'Approved',  cls: 'bg-green-500/10 text-green-400 border-green-500/30' },
  paid:      { label: 'Paid',      cls: 'bg-blue-500/10 text-blue-400 border-blue-500/30' },
  rejected:  { label: 'Rejected',  cls: 'bg-red-500/10 text-red-400 border-red-500/30' },
  cancelled: { label: 'Cancelled', cls: 'bg-gray-500/10 text-gray-400 border-gray-500/30' },
};

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

function initials(name: string) {
  return (name || 'G').split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
}

const InfoRow: React.FC<{ label: string; value: React.ReactNode; highlight?: boolean }> = ({ label, value, highlight }) => (
  <div>
    <p className="text-[10px] font-bold uppercase tracking-wider text-ink-600 dark:text-ivory-500 mb-0.5">{label}</p>
    <p className={`text-[13px] font-semibold ${highlight ? 'text-auburn-500 dark:text-auburn-300' : 'text-ink-900 dark:text-ivory-50'}`}>
      {value || '—'}
    </p>
  </div>
);

interface CardProps {
  booking: Booking;
  tab: string;
  onAction: (id: string, action: 'approve' | 'reject' | 'verify' | 'mark-paid') => void;
}

const BookingCard: React.FC<CardProps> = ({ booking, tab, onAction }) => {
  const status = booking.status as string;
  const statusCfg = STATUS_CONFIG[status] || STATUS_CONFIG.cancelled;

  const roomLabel = (booking as any).room_display || (booking as any).room_name || '—';
  const floorLabel = (booking as any).floor_number ? `Floor ${(booking as any).floor_number}` : null;
  const roomNum = (booking as any).room_number;
  const bedLabel = booking.bed_number ? booking.bed_number : '—';
  const hostelName = (booking as any).hostel_name || '—';

  const isOffline = booking.payment_mode === 'offline';
  const isPending = status === 'pending';
  const canAct = status !== 'paid' && status !== 'rejected' && status !== 'cancelled';

  return (
    <div className="bg-ivory-50 dark:bg-ivory-900 border border-ivory-200 dark:border-ivory-700 rounded-2xl p-5 shadow-sm flex flex-col gap-4 hover:border-auburn-500/30 dark:hover:border-auburn-300/30 hover:shadow-md transition-all duration-200">

      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-full bg-auburn-500/15 dark:bg-auburn-300/15 border border-auburn-500/20 flex items-center justify-center text-sm font-bold text-auburn-500 dark:text-auburn-300 flex-shrink-0">
            {initials(booking.student_name)}
          </div>
          <div className="min-w-0">
            <p className="text-[15px] font-bold text-ink-900 dark:text-ivory-50 truncate">
              {booking.student_name || 'Guest'}
            </p>
            <p className="text-[12px] text-ink-600 dark:text-ivory-400 font-medium truncate">
              {booking.student_phone || 'No phone'}
            </p>
          </div>
        </div>
        <span className={`inline-flex items-center px-2 py-0.5 rounded-[6px] text-[10px] font-bold border capitalize flex-shrink-0 ${statusCfg.cls}`}>
          {statusCfg.label}
        </span>
      </div>

      <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-ivory-100 dark:bg-ivory-800 rounded-lg">
        <svg className="w-3.5 h-3.5 text-ink-500 dark:text-ivory-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
        <span className="text-[12px] font-semibold text-ink-700 dark:text-ivory-300 truncate">{hostelName}</span>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-3">
        <InfoRow label="Room" value={roomLabel} />
        <InfoRow label="Bed" value={bedLabel} />
        {floorLabel && <InfoRow label="Floor" value={floorLabel} />}
        {roomNum && <InfoRow label="Room No." value={roomNum} />}
        <InfoRow label="Check-in" value={formatDate((booking as any).check_in_date)} />
        <InfoRow label="Payment" value={
          <span className={`capitalize ${isOffline ? 'text-amber-500 dark:text-amber-300' : 'text-blue-400'}`}>
            {booking.payment_mode}
          </span>
        } />
        <InfoRow label="Rent" value={booking.amount ? `₹${Number(booking.amount).toLocaleString('en-IN')}` : '—'} highlight={!!booking.amount} />
        <InfoRow label="Requested" value={timeAgo(booking.created_at)} />
      </div>

      {(booking as any).notes && (
        <p className="text-[12px] text-ink-600 dark:text-ivory-400 italic bg-ivory-100 dark:bg-ivory-800 rounded-lg px-3 py-2">
          "{(booking as any).notes}"
        </p>
      )}

      {status === 'paid' && (booking as any).marked_paid_at && (
        <p className="text-[11px] text-blue-400 font-medium">
          ✓ Marked paid {timeAgo((booking as any).marked_paid_at)}
        </p>
      )}

      {canAct && (
        <div className="flex items-center gap-2 mt-auto pt-3 border-t border-ivory-200 dark:border-ivory-700">
          {isOffline && (
            <button
              onClick={() => onAction(booking.id, 'mark-paid')}
              className="flex-1 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 text-blue-400 text-[12px] font-bold py-2 rounded-[8px] transition-all"
            >
              Mark Paid
            </button>
          )}
          {!isOffline && isPending && (
            <button
              onClick={() => onAction(booking.id, 'verify')}
              className="flex-1 bg-auburn-500/10 hover:bg-auburn-500/20 border border-auburn-500/30 text-auburn-500 dark:text-auburn-300 text-[12px] font-bold py-2 rounded-[8px] transition-all"
            >
              Verify Payment
            </button>
          )}
          {isPending && isOffline && (
            <button
              onClick={() => onAction(booking.id, 'approve')}
              className="flex-1 bg-green-500/10 hover:bg-green-500/20 border border-green-500/30 text-green-400 text-[12px] font-bold py-2 rounded-[8px] transition-all"
            >
              Accept
            </button>
          )}
          {isPending && (
            <button
              onClick={() => onAction(booking.id, 'reject')}
              className="flex-1 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 text-[12px] font-bold py-2 rounded-[8px] transition-all"
            >
              Reject
            </button>
          )}
        </div>
      )}
    </div>
  );
};

const EmptyState: React.FC<{ tab: string }> = ({ tab }) => {
  const messages: Record<string, { icon: string; title: string; body: string }> = {
    'offline-requests': { icon: '📋', title: 'No pending requests', body: 'Offline booking requests from the app will appear here.' },
    'offline-confirmed': { icon: '✅', title: 'No confirmed bookings', body: 'Confirmed offline bookings will appear here.' },
    'online-requests': { icon: '🌐', title: 'No online requests', body: 'Online booking requests awaiting verification will appear here.' },
    'online-payments': { icon: '💳', title: 'No payments received', body: 'Verified online payments will appear here once students pay.' },
  };
  const m = messages[tab] || { icon: '📋', title: 'No bookings', body: 'Bookings will appear here.' };
  return (
    <div className="py-20 text-center bg-ivory-50 dark:bg-ivory-900 border border-ivory-200 dark:border-ivory-700 rounded-2xl">
      <div className="text-5xl mb-4">{m.icon}</div>
      <p className="text-[15px] font-bold text-ink-900 dark:text-ivory-50 mb-1">{m.title}</p>
      <p className="text-[13px] text-ink-600 dark:text-ivory-400 max-w-sm mx-auto">{m.body}</p>
    </div>
  );
};

function BookingsContent() {
  const { theme } = useTheme();
  const searchParams = useSearchParams();
  const router = useRouter();
  const defaultTab = searchParams.get('tab') || 'offline-requests';
  const [currentTab, setCurrentTab] = useState(defaultTab);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [actionTarget, setActionTarget] = useState<{ id: string; action: 'approve' | 'reject' | 'verify' | 'mark-paid' } | null>(null);

  const fetchBookings = useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await bookingService.getBookings();
      const list = res?.data || res || [];
      setBookings(Array.isArray(list) ? list : []);
    } catch (error) {
      console.error('Failed to fetch bookings:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchBookings(); }, [fetchBookings]);

  const offlineRequests = bookings.filter(b => b.payment_mode === 'offline' && b.status === 'pending');
  const offlineConfirmed = bookings.filter(b => b.payment_mode === 'offline' && ['confirmed', 'approved', 'paid'].includes(b.status as string));
  const onlineRequests  = bookings.filter(b => b.payment_mode === 'online' && ['pending', 'approved'].includes(b.status as string));
  const onlinePayments  = bookings.filter(b => b.payment_mode === 'online' && b.status as string === 'paid');

  const tabData: Record<string, Booking[]> = {
    'offline-requests': offlineRequests,
    'offline-confirmed': offlineConfirmed,
    'online-requests': onlineRequests,
    'online-payments': onlinePayments,
  };

  const tabs = [
    { id: 'offline-requests',  label: 'Requests',          count: offlineRequests.length },
    { id: 'offline-confirmed', label: 'Confirmed',          count: offlineConfirmed.length },
    { id: 'online-requests',   label: 'Online Requests',    count: onlineRequests.length },
    { id: 'online-payments',   label: 'Payments Received',  count: onlinePayments.length },
  ];

  const HEADER: Record<string, { title: string; desc: string }> = {
    'offline-requests':  { title: 'Offline Booking Requests', desc: 'Pending requests that selected offline payment' },
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
    try {
      if (actionTarget.action === 'approve')   await bookingService.approveBooking(actionTarget.id);
      if (actionTarget.action === 'reject')    await bookingService.rejectBooking(actionTarget.id);
      if (actionTarget.action === 'verify')    await bookingService.verifyPayment(actionTarget.id);
      if (actionTarget.action === 'mark-paid') await bookingService.markBookingPaid(actionTarget.id);
      await fetchBookings();
    } catch (err) {
      console.error('Action failed:', err);
      alert('Failed to update booking. Please try again.');
    } finally {
      setActionTarget(null);
    }
  };

  const DIALOGS: Record<string, { title: string; message: string; label: string; variant: 'info' | 'danger' }> = {
    approve:     { title: 'Confirm booking?',      message: 'This will confirm the booking request.',         label: 'Confirm',    variant: 'info' },
    reject:      { title: 'Reject booking?',        message: 'This will reject the booking request.',          label: 'Reject',     variant: 'danger' },
    verify:      { title: 'Verify Payment?',        message: 'This will verify the online payment.',           label: 'Verify',     variant: 'info' },
    'mark-paid': { title: 'Mark as Paid?',          message: 'This will mark this booking as paid.',           label: 'Mark Paid',  variant: 'info' },
  };

  const dialogCfg = actionTarget ? DIALOGS[actionTarget.action] : null;
  const headerInfo = HEADER[currentTab];
  const isDark = theme === 'dark';

  const stats = [
    { label: 'Pending',   value: bookings.filter(b => b.status === 'pending').length,   color: 'text-amber-400',   bg: 'bg-amber-500/10' },
    { label: 'Confirmed', value: bookings.filter(b => b.status === 'confirmed').length, color: 'text-green-400',   bg: 'bg-green-500/10' },
    { label: 'Paid',      value: bookings.filter(b => (b.status as string) === 'paid').length, color: 'text-blue-400', bg: 'bg-blue-500/10' },
    { label: 'Total',     value: bookings.length,                                        color: 'text-auburn-500 dark:text-auburn-300', bg: 'bg-auburn-500/10' },
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

      <div className="w-full animate-fade-in-up space-y-6">

        <div>
          <h1 className="text-2xl font-bold text-ink-900 dark:text-ivory-50">{headerInfo.title}</h1>
          <p className="mt-1 text-sm font-medium text-ink-600 dark:text-ivory-400">{headerInfo.desc}</p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {stats.map(s => (
            <div key={s.label} className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${isDark ? 'bg-ivory-900 border-ivory-700' : 'bg-ivory-50 border-ivory-200'}`}>
              <div className={`w-8 h-8 ${s.bg} rounded-lg flex items-center justify-center`}>
                <span className={`text-[15px] font-black ${s.color}`}>{s.value}</span>
              </div>
              <span className="text-[12px] font-semibold text-ink-600 dark:text-ivory-400">{s.label}</span>
            </div>
          ))}
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div className={`flex items-center p-1 rounded-xl border ${isDark ? 'bg-ivory-950 border-ivory-700' : 'bg-ivory-50 border-ivory-200'} overflow-x-auto`}>
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => { setCurrentTab(tab.id); setSearchQuery(''); }}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all whitespace-nowrap ${
                  currentTab === tab.id
                    ? 'bg-auburn-500 text-white shadow-sm'
                    : 'text-ink-700 dark:text-ivory-300 hover:bg-ivory-200 dark:hover:bg-ivory-800'
                }`}
              >
                {tab.label}
                <span className={`px-2 py-0.5 rounded-full text-[11px] ${
                  currentTab === tab.id ? 'bg-white/20 text-white' : 'bg-ivory-200 dark:bg-ivory-800 text-ink-600 dark:text-ivory-400'
                }`}>
                  {tab.count}
                </span>
              </button>
            ))}
          </div>

          <div className="relative flex-1 min-w-0 sm:max-w-xs">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-500 dark:text-ivory-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search name, room, hostel…"
              className={`w-full pl-9 pr-4 py-2.5 rounded-xl border text-sm font-medium outline-none transition-all ${
                isDark
                  ? 'bg-ivory-900 border-ivory-700 text-ivory-50 placeholder-ivory-500 focus:border-auburn-300'
                  : 'bg-ivory-50 border-ivory-200 text-ink-900 placeholder-ink-500 focus:border-auburn-500'
              }`}
            />
          </div>

          <button
            onClick={fetchBookings}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm font-semibold transition-all border-ivory-200 dark:border-ivory-700 text-ink-700 dark:text-ivory-300 hover:bg-ivory-100 dark:hover:bg-ivory-800 disabled:opacity-50"
          >
            <svg className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
        </div>

        {isLoading ? (
          <div className="py-20 text-center">
            <div className="w-8 h-8 border-2 border-auburn-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm font-medium text-ink-600 dark:text-ivory-400">Loading bookings…</p>
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState tab={currentTab} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map(b => (
              <BookingCard key={b.id} booking={b} tab={currentTab} onAction={(id, action) => setActionTarget({ id, action })} />
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
      <div className="min-h-screen flex items-center justify-center bg-ivory-50 dark:bg-ivory-950">
        <div className="w-8 h-8 border-2 border-auburn-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <BookingsContent />
    </React.Suspense>
  );
}
