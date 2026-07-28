'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/common/DashboardLayout';
import { useTheme } from '@/contexts/ThemeContext';
import { useAuth } from '@/contexts/AuthContext';
import Modal from '@/components/ui/Modal';
import HostelEnrollmentWizard from '@/components/hostel/HostelEnrollmentWizard';
import type { DashboardStats, ActivityItem, Booking } from '@/types';
import { hostelService, bookingService } from '@/services/api';
import NoticeBoard from '@/components/dashboard/NoticeBoard';
import StatCard, { StatTone } from '@/components/ui/StatCard';
import ChartCard from '@/components/ui/ChartCard';
import StatusBadge from '@/components/ui/StatusBadge';
import Icon from '@/components/ui/Icon';
import { Donut, SimpleBar } from '@/components/charts/ChartBundle';

function timeAgo(iso: string) {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

const BookingRow: React.FC<{ booking: Booking; onAction: (id: string, action: 'approve' | 'reject') => void }> = ({
  booking, onAction,
}) => {
  const initials = (booking.student_name || 'Guest').split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
  return (
    <div className="flex items-center gap-4 px-5 py-4 hover:bg-ivory-100/50 dark:hover:bg-ivory-50/[0.04] transition-colors">
      <div className="w-10 h-10 rounded-full bg-auburn-500/10 dark:bg-auburn-300/10 border border-auburn-500/20 dark:border-auburn-300/20 flex items-center justify-center text-xs font-bold text-auburn-500 dark:text-auburn-300 flex-shrink-0">
        {initials}
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-ink-900 dark:text-ivory-50 text-[14px] font-semibold truncate">{booking.student_name || 'Unknown'}</p>
        <p className="text-ink-700 dark:text-ivory-500 text-[12px] truncate">
          {(booking as any).room_display || (booking as any).room_name || booking.room || 'N/A'}
          {booking.bed_number ? ` · Bed ${booking.bed_number}` : ''}
        </p>
      </div>

      <div className="text-right hidden sm:block">
        <p className="text-ink-700 dark:text-ivory-500 text-[11px]">
          {new Date(booking.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
        </p>
        <div className="mt-1">
          <StatusBadge status={booking.status} />
        </div>
      </div>

      {booking.status === 'pending' && (
        <div className="flex gap-1.5 flex-shrink-0">
          <button
            onClick={() => onAction(booking.id, 'approve')}
            className="w-8 h-8 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 rounded-md flex items-center justify-center text-emerald-500 dark:text-emerald-300 transition-colors"
            title="Approve"
            aria-label="Approve booking"
          >
            <Icon name="check" className="w-3.5 h-3.5" strokeWidth={2.5} />
          </button>
          <button
            onClick={() => onAction(booking.id, 'reject')}
            className="w-8 h-8 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 rounded-md flex items-center justify-center text-red-500 dark:text-red-300 transition-colors"
            title="Reject"
            aria-label="Reject booking"
          >
            <Icon name="x" className="w-3.5 h-3.5" strokeWidth={2.5} />
          </button>
        </div>
      )}
    </div>
  );
};

export default function DashboardPage() {
  const { theme } = useTheme();
  const { isFirstTimeOwner, authUser } = useAuth();
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [showWizard, setShowWizard] = useState(false);
  const [actingId, setActingId] = useState<string | null>(null);

  useEffect(() => {
    if (isFirstTimeOwner) {
      const t = setTimeout(() => setShowWizard(true), 600);
      return () => clearTimeout(t);
    }
  }, [isFirstTimeOwner]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [statsRes, activityRes, bookingsRes] = await Promise.all([
          hostelService.getDashboardStats().catch(() => null),
          hostelService.getRecentActivity().catch(() => null),
          bookingService.getBookings().catch(() => null),
        ]);

        if (statsRes?.data) setStats(statsRes.data);
        if (activityRes?.data) setActivity(activityRes.data);
        if (bookingsRes?.data) setBookings(bookingsRes.data);
      } catch (error) {
        console.error('Error fetching dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const cardBg = theme === 'dark' ? 'bg-ivory-900' : 'bg-ivory-50';
  const cardBorder = theme === 'dark' ? 'border-ivory-700' : 'border-ivory-300';

  const pendingBookings = bookings.filter(b => b.status === 'pending');

  // Chart data: derived from real data, empty arrays when nothing exists
  const occupancyData = useMemo(() => {
    const a = stats?.available_rooms ?? 0;
    const o = stats?.occupied_rooms ?? 0;
    return [
      { name: 'Available', value: a },
      { name: 'Occupied',  value: o },
    ];
  }, [stats?.available_rooms, stats?.occupied_rooms]);

  const bookingStatusData = useMemo(() => {
    const groups: Record<string, number> = { pending: 0, approved: 0, confirmed: 0, paid: 0, rejected: 0, cancelled: 0 };
    for (const b of bookings) {
      const s = (b.status as string) || 'pending';
      groups[s] = (groups[s] || 0) + 1;
    }
    return Object.entries(groups)
      .filter(([, v]) => v > 0)
      .map(([name, value]) => ({ name: name.replace(/_/g, ' '), value }));
  }, [bookings]);

  const paymentModeData = useMemo(() => {
    const groups: Record<string, number> = { offline: 0, online: 0 };
    for (const b of bookings) {
      const m = (b.payment_mode as string) || 'offline';
      groups[m] = (groups[m] || 0) + 1;
    }
    return [
      { name: 'Offline', value: groups.offline },
      { name: 'Online',  value: groups.online },
    ];
  }, [bookings]);

  const handleQuickAction = async (id: string, action: 'approve' | 'reject') => {
    if (actingId) return;
    setActingId(id);
    try {
      if (action === 'approve') {
        const { bookingService: bs } = await import('@/services/api');
        await bs.approveBooking(id);
      } else {
        const { bookingService: bs } = await import('@/services/api');
        await bs.rejectBooking(id);
      }
      // refresh bookings only
      const res = await bookingService.getBookings();
      if (res?.data) setBookings(res.data);
    } catch (err) {
      console.error('Quick action failed', err);
      alert('Failed to update booking. Please try again.');
    } finally {
      setActingId(null);
    }
  };

  // Stat card config — fully token-aligned, zero hex
  const statCards: { title: string; value: number | string; badge: string; tone: StatTone; icon: any; delay: number; prefix?: string }[] = [
    {
      title: 'Registered Hostel',
      value: stats?.registered_hostels ? 1 : 0,
      badge: stats?.registered_hostels ? 'Active' : 'Not set up',
      tone: stats?.registered_hostels ? 'success' : 'warning',
      icon: 'hostel',
      delay: 0,
    },
    { title: 'Total Rooms',       value: stats?.total_rooms ?? 0,            badge: 'All rooms',     tone: 'info',    icon: 'rooms',     delay: 60 },
    { title: 'Available Rooms',   value: stats?.available_rooms ?? 0,        badge: 'Vacant',        tone: 'accent',  icon: 'key',       delay: 120 },
    { title: 'Occupied Rooms',    value: stats?.occupied_rooms ?? 0,         badge: 'In use',        tone: 'primary', icon: 'bed',       delay: 180 },
    { title: 'Pending Requests',  value: stats?.pending_booking_requests ?? 0, badge: 'Needs action', tone: 'warning', icon: 'inbox',     delay: 240 },
    { title: 'Booked Users',      value: stats?.booked_residents ?? 0,       badge: 'Total guests',  tone: 'info',    icon: 'residents', delay: 300 },
    { title: 'Monthly Revenue',   value: stats?.monthly_revenue ?? 0,        badge: 'This month',    tone: 'success', icon: 'money',     delay: 360, prefix: '₹' },
    { title: 'Pending Payments',  value: stats?.pending_payments ?? 0,       badge: 'Outstanding',   tone: 'error',   icon: 'wallet',    delay: 420, prefix: '₹' },
  ];

  const hasOccupancyData = (stats?.available_rooms ?? 0) + (stats?.occupied_rooms ?? 0) > 0;
  const hasBookingStatusData = bookingStatusData.some(d => d.value > 0);
  const hasPaymentModeData  = paymentModeData.some(d => d.value > 0);

  return (
    <>
      <Modal isOpen={showWizard} persistent className="w-full max-w-3xl">
        <HostelEnrollmentWizard onClose={() => setShowWizard(false)} />
      </Modal>

      <DashboardLayout title="Dashboard">
        <div className="w-full space-y-8">
          {/* Header */}
          <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 animate-fade-in-up">
            <div>
              <h1 className="text-[28px] font-bold tracking-tight text-ink-900 dark:text-ivory-50">
                Welcome back, {authUser?.display_name || 'Admin'} 👋
              </h1>
              <p className="mt-1 text-sm font-medium text-ink-700 dark:text-ivory-400">
                Here's what's happening at your hostel today
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowWizard(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-[10px] text-sm font-semibold border border-auburn-500/30 dark:border-auburn-300/30 bg-auburn-500/10 dark:bg-auburn-300/10 text-auburn-500 dark:text-auburn-300 hover:bg-auburn-500/20 dark:hover:bg-auburn-300/20 transition-colors"
              >
                <Icon name="plus" className="w-4 h-4" />
                Add Hostel
              </button>
            </div>
          </header>

          {/* Stat cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {statCards.map(s => (
              <StatCard
                key={s.title}
                title={s.title}
                value={loading ? '—' : s.value}
                prefix={(s as any).prefix}
                badge={s.badge}
                tone={s.tone}
                icon={s.icon}
                loading={loading}
                delay={s.delay}
              />
            ))}
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <ChartCard
              title="Room Occupancy"
              description="Available vs occupied rooms"
              icon="chart-pie"
              accentClass="bg-auburn-500"
              isEmpty={!hasOccupancyData}
              emptyTitle="No rooms yet"
              emptyMessage="Add rooms to see occupancy breakdown."
              emptyIcon="rooms"
            >
              <Donut data={occupancyData} size={180} />
            </ChartCard>

            <ChartCard
              title="Booking Status"
              description="Live breakdown of all bookings"
              icon="chart-pie"
              accentClass="bg-emerald-500"
              isEmpty={!hasBookingStatusData}
              emptyTitle="No bookings yet"
              emptyMessage="Once bookings arrive, you'll see them broken down by status here."
              emptyIcon="bookings"
            >
              <Donut data={bookingStatusData} size={180} />
            </ChartCard>

            <ChartCard
              title="Payment Mode"
              description="Offline vs online bookings"
              icon="chart-bar"
              accentClass="bg-auburn-300"
              isEmpty={!hasPaymentModeData}
              emptyTitle="No payment data"
              emptyMessage="Bookings with payment mode will appear here."
              emptyIcon="payments"
            >
              <SimpleBar
                data={paymentModeData}
                xKey="name"
                series={[{ dataKey: 'value', name: 'Bookings' }]}
                height={220}
              />
            </ChartCard>
          </div>

          {/* Lists row */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <div className="xl:col-span-2 space-y-6">
              <div className="animate-fade-in-up" style={{ animationDelay: '480ms' }}>
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-[17px] font-bold flex items-center gap-2">
                    Booking Requests
                    {pendingBookings.length > 0 && (
                      <span className="bg-amber-500/15 text-amber-500 dark:text-amber-300 border border-amber-500/30 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                        {pendingBookings.length} pending
                      </span>
                    )}
                  </h2>
                  <button
                    onClick={() => router.push('/bookings')}
                    className="text-auburn-500 hover:text-auburn-700 dark:text-auburn-300 dark:hover:text-auburn-100 text-sm font-semibold transition-colors flex items-center gap-1"
                  >
                    View all
                    <Icon name="chevron-right" className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className={`${cardBg} rounded-2xl border ${cardBorder} overflow-hidden`}>
                  {loading ? (
                    <div className="p-6 space-y-3">
                      {[...Array(3)].map((_, i) => (
                        <div key={i} className="h-16 bg-ivory-200/60 dark:bg-ivory-800/60 rounded-xl animate-pulse" />
                      ))}
                    </div>
                  ) : pendingBookings.length === 0 ? (
                    <div className="py-12 text-center">
                      <div className="w-12 h-12 rounded-full bg-ivory-200/60 dark:bg-ivory-800/60 flex items-center justify-center mx-auto mb-3 text-ink-500 dark:text-ivory-400">
                        <Icon name="inbox" className="w-6 h-6" />
                      </div>
                      <p className="text-[13px] font-bold text-ink-900 dark:text-ivory-50 mb-1">No pending booking requests</p>
                      <p className="text-[12px] text-ink-700 dark:text-ivory-500">You'll see new requests here as they come in.</p>
                    </div>
                  ) : (
                    <div className="divide-y divide-ivory-200 dark:divide-ivory-700">
                      {pendingBookings.slice(0, 4).map(booking => (
                        <BookingRow
                          key={booking.id}
                          booking={booking}
                          onAction={handleQuickAction}
                        />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="animate-fade-in-up" style={{ animationDelay: '540ms' }}>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-[17px] font-bold">Recent Activity</h2>
              </div>

              <div className={`${cardBg} rounded-2xl border ${cardBorder} p-4`}>
                {loading ? (
                  <div className="space-y-3">
                    {[...Array(5)].map((_, i) => (
                      <div key={i} className="flex gap-3">
                        <div className="w-9 h-9 bg-ivory-200/60 dark:bg-ivory-800/60 rounded-full animate-pulse flex-shrink-0" />
                        <div className="flex-1 space-y-1.5">
                          <div className="h-3 bg-ivory-200/60 dark:bg-ivory-800/60 rounded animate-pulse w-3/4" />
                          <div className="h-2.5 bg-ivory-200/60 dark:bg-ivory-800/60 rounded animate-pulse w-full" />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : activity.length === 0 ? (
                  <div className="py-10 text-center">
                    <div className="w-10 h-10 rounded-full bg-ivory-200/60 dark:bg-ivory-800/60 flex items-center justify-center mx-auto mb-3 text-ink-500 dark:text-ivory-400">
                      <Icon name="sparkles" className="w-5 h-5" />
                    </div>
                    <p className="text-[12px] font-semibold text-ink-700 dark:text-ivory-500">No recent activity yet</p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    {activity.map((item, i) => {
                      const toneMap: Record<string, { tone: StatTone; icon: any }> = {
                        booking_request:  { tone: 'info',    icon: 'bookings' },
                        booking_approved: { tone: 'success', icon: 'check' },
                        booking_rejected: { tone: 'error',   icon: 'x' },
                        payment_received: { tone: 'success', icon: 'money' },
                        hostel_updated:   { tone: 'accent',  icon: 'hostel' },
                        room_updated:     { tone: 'info',    icon: 'rooms' },
                      };
                      const cfg = toneMap[item.type] || { tone: 'neutral', icon: 'sparkles' };
                      const toneBg: Record<StatTone, string> = {
                        primary: 'bg-auburn-500/10 text-auburn-500 dark:text-auburn-300',
                        success: 'bg-emerald-500/10 text-emerald-500 dark:text-emerald-300',
                        error:   'bg-red-500/10 text-red-500 dark:text-red-300',
                        warning: 'bg-amber-500/10 text-amber-500 dark:text-amber-300',
                        info:    'bg-blue-500/10 text-blue-500 dark:text-blue-300',
                        accent:  'bg-auburn-300/10 text-auburn-300 dark:text-auburn-200',
                        neutral: 'bg-ivory-300/40 dark:bg-ivory-700/40 text-ink-700 dark:text-ivory-300',
                      };
                      return (
                        <div
                          key={item.activity_id}
                          className={`flex gap-3 py-3 ${i < activity.length - 1 ? 'border-b border-ivory-200 dark:border-ivory-700' : ''}`}
                        >
                          <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${toneBg[cfg.tone]}`}>
                            <Icon name={cfg.icon} className="w-4 h-4" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-ink-900 dark:text-ivory-50 text-[13px] font-semibold leading-tight">{item.title}</p>
                            <p className="text-ink-700 dark:text-ivory-400 text-[11px] mt-0.5 truncate">{item.description}</p>
                            <p className="text-ink-700/60 dark:text-ivory-500/60 text-[10px] mt-1 font-medium">{timeAgo(item.timestamp)}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <NoticeBoard />
            </div>
          </div>
        </div>
      </DashboardLayout>
    </>
  );
}
