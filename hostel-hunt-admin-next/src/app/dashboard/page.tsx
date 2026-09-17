'use client';

import React, { useEffect, useState, useMemo, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import DashboardLayout from '@/components/common/DashboardLayout';
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
import BookingDensityMap from '@/components/charts/BookingDensityMap';
import gsap from 'gsap';

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

const BookingRow: React.FC<{ booking: Booking; onAction: (id: string, action: 'approve' | 'reject') => void; acting: boolean }> = ({
  booking, onAction, acting,
}) => {
  const initials = (booking.student_name || 'Guest').split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 px-5 py-4 transition-all duration-200 hover:bg-[var(--color-border)]/30 group">
      <div className="flex items-center gap-3 w-full sm:w-auto">
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
          style={{
            background: 'var(--color-primary-light)',
            color: 'var(--color-primary)',
            border: '1px solid var(--color-primary)/20',
          }}
        >
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[14px] font-semibold truncate" style={{ color: 'var(--color-text-primary)' }}>
            {booking.student_name || 'Unknown'}
          </p>
          <p className="text-[12px] truncate" style={{ color: 'var(--color-text-muted)' }}>
            {(booking as any).room_display || (booking as any).room_name || booking.room || 'N/A'}
            {booking.bed_number ? ` · Bed ${booking.bed_number}` : ''}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between sm:justify-end flex-1 w-full sm:w-auto mt-2 sm:mt-0 pt-3 sm:pt-0 border-t border-[var(--color-border)] sm:border-0">
        <div className="flex items-center gap-2 sm:mr-4">
          <p className="text-[11px] hidden sm:block" style={{ color: 'var(--color-text-muted)' }}>
            {new Date(booking.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
          </p>
          <StatusBadge status={booking.status} />
        </div>

        {booking.status === 'pending' && (
          <div className="flex gap-1.5 flex-shrink-0">
            <button
              onClick={() => onAction(booking.id, 'approve')}
              disabled={acting}
              className="w-8 h-8 rounded-md flex items-center justify-center transition-all disabled:opacity-50"
              style={{
                background: 'var(--color-success-light)',
                color: 'var(--color-success)',
                border: '1px solid color-mix(in srgb, var(--color-success) 30%, transparent)',
              }}
              title="Approve"
            >
              <Icon name="check" className="w-3.5 h-3.5" strokeWidth={2.5} />
            </button>
            <button
              onClick={() => onAction(booking.id, 'reject')}
              disabled={acting}
              className="w-8 h-8 rounded-md flex items-center justify-center transition-all disabled:opacity-50"
              style={{
                background: 'var(--color-error-light)',
                color: 'var(--color-error)',
                border: '1px solid color-mix(in srgb, var(--color-error) 30%, transparent)',
              }}
              title="Reject"
            >
              <Icon name="x" className="w-3.5 h-3.5" strokeWidth={2.5} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default function DashboardPage() {
  const { isFirstTimeOwner, authUser } = useAuth();
  const router = useRouter();

  const [showWizard, setShowWizard] = useState(false);
  const [actingId, setActingId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const headerRef = useRef<HTMLElement>(null);
  const statGridRef = useRef<HTMLDivElement>(null);
  const chartsRef = useRef<HTMLDivElement>(null);

  // TanStack Query fetching
  const { data: stats } = useQuery<DashboardStats>({
    queryKey: ['dashboard', 'stats'],
    queryFn: () => hostelService.getDashboardStats().then(r => r.data)
  });

  const { data: activity = [] as ActivityItem[] } = useQuery<ActivityItem[]>({
    queryKey: ['dashboard', 'activity'],
    queryFn: () => hostelService.getRecentActivity().then(r => r.data)
  });

  const { data: bookings = [] as Booking[] } = useQuery<Booking[]>({
    queryKey: ['bookings'],
    queryFn: () => bookingService.getBookings().then(r => r.data)
  });

  // Since we load quickly from cache, we can safely derive loading state.
  // Actually wait, let's keep it simple: if stats isn't loaded, it's loading.
  const loading = !stats;

  useEffect(() => {
    if (isFirstTimeOwner) {
      const t = setTimeout(() => setShowWizard(true), 600);
      return () => clearTimeout(t);
    }
  }, [isFirstTimeOwner]);

  // GSAP entrance animations after loading
  useEffect(() => {
    if (!loading) {
      const ctx = gsap.context(() => {
        if (headerRef.current) {
          gsap.fromTo(headerRef.current,
            { opacity: 0, y: 20 },
            { opacity: 1, y: 0, duration: 0.5, ease: 'power2.out' }
          );
        }
        if (statGridRef.current) {
          gsap.fromTo(statGridRef.current.children,
            { opacity: 0, y: 24, scale: 0.97 },
            { opacity: 1, y: 0, scale: 1, duration: 0.4, stagger: 0.07, ease: 'power2.out', delay: 0.2 }
          );
        }
        if (chartsRef.current) {
          gsap.fromTo(chartsRef.current.children,
            { opacity: 0, y: 20 },
            { opacity: 1, y: 0, duration: 0.45, stagger: 0.1, ease: 'power2.out', delay: 0.5 }
          );
        }
      });
      return () => ctx.revert();
    }
  }, [loading]);

  const pendingBookings = bookings.filter(b => b.status === 'pending');

  const occupancyData = useMemo(() => {
    const rate = stats?.occupancy_rate ?? 0;
    const residents = stats?.total_residents ?? 0;
    if (rate === 0 || residents === 0) {
      return [
        { name: 'Available', value: 0 },
        { name: 'Occupied', value: 0 }
      ];
    }
    const total = Math.round((residents / rate) * 100);
    return [
      { name: 'Available', value: total - residents },
      { name: 'Occupied', value: residents }
    ];
  }, [stats?.occupancy_rate, stats?.total_residents]);

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
        await bookingService.approveBooking(id);
      } else {
        await bookingService.rejectBooking(id);
      }
      queryClient.invalidateQueries({ queryKey: ['bookings'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'stats'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'activity'] });
    } catch (err) {
      console.error('Quick action failed', err);
      alert('Failed to update booking. Please try again.');
    } finally {
      setActingId(null);
    }
  };

  const statCards: { title: string; value: number | string; badge: string; tone: StatTone; icon: any; prefix?: string; suffix?: string }[] = [
    {
      title: 'Registered Hostels',
      value: stats?.total_hostels ?? 0,
      badge: (stats?.total_hostels ?? 0) > 0 ? 'Active' : 'Not set up',
      tone: (stats?.total_hostels ?? 0) > 0 ? 'success' : 'warning',
      icon: 'hostel',
    },
    { title: 'Total Residents',  value: stats?.total_residents ?? 0,          badge: 'All guests',   tone: 'info',    icon: 'residents' },
    { title: 'Occupancy Rate',   value: stats?.occupancy_rate ?? 0,           badge: 'In use',       tone: 'primary', icon: 'bed', suffix: '%' },
    { title: 'Pending Requests', value: stats?.pending_bookings ?? 0,         badge: 'Needs action', tone: 'warning', icon: 'inbox' },
    { title: 'Revenue Collected',value: stats?.revenue_collected ?? 0,        badge: 'Total',        tone: 'success', icon: 'money', prefix: '₹' },
    { title: 'Revenue Pending',  value: stats?.revenue_pending ?? 0,          badge: 'Outstanding',  tone: 'error',   icon: 'wallet', prefix: '₹' },
  ];

  const hasOccupancyData     = occupancyData.some(d => d.value > 0);
  const hasBookingStatusData = bookingStatusData.some(d => d.value > 0);
  const hasPaymentModeData   = paymentModeData.some(d => d.value > 0);

  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  })();

  return (
    <>
      <Modal isOpen={showWizard} persistent className="w-full max-w-3xl">
        <HostelEnrollmentWizard onClose={() => setShowWizard(false)} />
      </Modal>

      <DashboardLayout title="Dashboard">
        <div className="w-full space-y-8">

          {/* Header */}
          <header ref={headerRef} className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 opacity-0">
            <div>
              <p className="text-sm font-semibold mb-1" style={{ color: 'var(--color-primary)' }}>
                {greeting} 👋
              </p>
              <h1
                className="text-[28px] font-extrabold tracking-tight leading-tight"
                style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}
              >
                {authUser?.display_name || 'Admin'} Dashboard
              </h1>
              <p className="mt-1 text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>
                Here's what's happening at your hostel today
              </p>
            </div>
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <button
                onClick={() => setShowWizard(true)}
                className="w-full sm:w-auto flex items-center justify-center gap-2 px-4 py-2.5 rounded-[10px] text-sm font-semibold transition-all hover:opacity-90 min-h-[44px] sm:min-h-0"
                style={{
                  background: 'var(--color-primary)',
                  color: 'var(--color-text-inverse)',
                  boxShadow: '0 4px 14px color-mix(in srgb, var(--color-primary) 30%, transparent)',
                }}
              >
                <Icon name="plus" className="w-4 h-4" />
                Add Hostel
              </button>
            </div>
          </header>

          {/* Stat cards */}
          <div ref={statGridRef} className="grid grid-cols-2 lg:grid-cols-3 gap-4">
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
              />
            ))}
          </div>

          {/* Charts row */}
          <div ref={chartsRef} className="grid grid-cols-1 md:grid-cols-3 gap-4">
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

          {/* Booking Density Heatmap (Nivo) */}
          <div className="animate-fade-in-up mt-6" style={{ animationDelay: '300ms' }}>
            <ChartCard title="Booking Volume" description="Daily booking request density over the past year">
              {bookings.length > 0 ? (
                <BookingDensityMap bookings={bookings} />
              ) : (
                <div className="h-[220px] flex items-center justify-center">
                  <p className="text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>No bookings yet</p>
                </div>
              )}
            </ChartCard>
          </div>

          {/* Lists row */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 animate-fade-in-up mt-6" style={{ animationDelay: '400ms' }}>
            <div className="xl:col-span-2 space-y-6">
              <div>
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-[17px] font-bold flex items-center gap-2" style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}>
                    Booking Requests
                    {pendingBookings.length > 0 && (
                      <span
                        className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                        style={{
                          background: 'var(--color-warning-light)',
                          color: 'var(--color-warning)',
                          border: '1px solid color-mix(in srgb, var(--color-warning) 30%, transparent)',
                        }}
                      >
                        {pendingBookings.length} pending
                      </span>
                    )}
                  </h2>
                  <button
                    onClick={() => router.push('/bookings')}
                    className="text-sm font-semibold transition-colors flex items-center gap-1 hover:opacity-70"
                    style={{ color: 'var(--color-primary)' }}
                  >
                    View all
                    <Icon name="chevron-right" className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div
                  className="rounded-2xl overflow-hidden"
                  style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                  }}
                >
                  {loading ? (
                    <div className="p-6 space-y-3">
                      {[...Array(3)].map((_, i) => (
                        <div key={i} className="h-16 rounded-xl animate-pulse" style={{ background: 'var(--color-border)' }} />
                      ))}
                    </div>
                  ) : pendingBookings.length === 0 ? (
                    <div className="py-14 text-center">
                      <div
                        className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3"
                        style={{ background: 'var(--color-border)', color: 'var(--color-text-muted)' }}
                      >
                        <Icon name="inbox" className="w-6 h-6" />
                      </div>
                      <p className="text-[13px] font-bold mb-1" style={{ color: 'var(--color-text-primary)' }}>No pending requests</p>
                      <p className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>New requests will appear here as they come in.</p>
                    </div>
                  ) : (
                    <div className="divide-y" style={{ borderColor: 'var(--color-border)' }}>
                      {pendingBookings.slice(0, 4).map(booking => (
                        <BookingRow
                          key={booking.id}
                          booking={booking}
                          onAction={handleQuickAction}
                          acting={actingId === booking.id}
                        />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Activity + NoticeBoard */}
            <div className="space-y-6">
              <div>
                <h2 className="text-[17px] font-bold mb-4" style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}>
                  Recent Activity
                </h2>
                <div
                  className="rounded-2xl p-4"
                  style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                  }}
                >
                  {loading ? (
                    <div className="space-y-3">
                      {[...Array(4)].map((_, i) => (
                        <div key={i} className="flex gap-3">
                          <div className="w-9 h-9 rounded-full animate-pulse flex-shrink-0" style={{ background: 'var(--color-border)' }} />
                          <div className="flex-1 space-y-1.5">
                            <div className="h-3 rounded animate-pulse w-3/4" style={{ background: 'var(--color-border)' }} />
                            <div className="h-2.5 rounded animate-pulse w-full" style={{ background: 'var(--color-border)' }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : activity.length === 0 ? (
                    <div className="py-10 text-center">
                      <div
                        className="w-10 h-10 rounded-full flex items-center justify-center mx-auto mb-3"
                        style={{ background: 'var(--color-border)', color: 'var(--color-text-muted)' }}
                      >
                        <Icon name="sparkles" className="w-5 h-5" />
                      </div>
                      <p className="text-[12px] font-semibold" style={{ color: 'var(--color-text-muted)' }}>No recent activity yet</p>
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
                        const cfg = toneMap[item.type] || { tone: 'neutral' as StatTone, icon: 'sparkles' };
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
                            className={`flex gap-3 py-3 ${i < activity.length - 1 ? 'border-b' : ''}`}
                            style={{ borderColor: 'var(--color-border)' }}
                          >
                            <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${toneBg[cfg.tone]}`}>
                              <Icon name={cfg.icon} className="w-4 h-4" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-[13px] font-semibold leading-tight" style={{ color: 'var(--color-text-primary)' }}>
                                {item.title}
                              </p>
                              <p className="text-[11px] mt-0.5 truncate" style={{ color: 'var(--color-text-muted)' }}>
                                {item.description}
                              </p>
                              <p className="text-[10px] mt-1 font-medium opacity-60" style={{ color: 'var(--color-text-muted)' }}>
                                {timeAgo(item.timestamp)}
                              </p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              <NoticeBoard />
            </div>
          </div>
        </div>
      </DashboardLayout>
    </>
  );
}
