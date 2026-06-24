import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../../components/common/DashboardLayout';
import { useTheme } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import { Modal } from '../../components/ui/Modal';
import { HostelEnrollmentWizard } from '../../components/hostel/HostelEnrollmentWizard';
import type { DashboardStats, ActivityItem, Booking } from '../../types';

// ── Demo data ─────────────────────────────────────────────────────────────────
const MOCK_STATS: DashboardStats = {
  registered_hostel: true, total_rooms: 24, available_rooms: 9,
  occupied_rooms: 15, pending_requests: 5, booked_users: 42,
  monthly_revenue: 126000, pending_payments: 18500,
};

const MOCK_ACTIVITY: ActivityItem[] = [
  { activity_id: '1', type: 'booking_request', title: 'New Booking Request', description: 'Rahul Verma requested Room 204 (Double)', timestamp: new Date(Date.now() - 1000 * 60 * 12).toISOString(), },
  { activity_id: '2', type: 'payment_received', title: 'Payment Received', description: '₹6,500 received from Priya Sharma – Room 101', timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString(), },
  { activity_id: '3', type: 'booking_approved', title: 'Booking Approved', description: 'Amit Kumar – Room 305 (Triple) approved', timestamp: new Date(Date.now() - 1000 * 60 * 120).toISOString(), },
  { activity_id: '4', type: 'hostel_updated', title: 'Hostel Profile Updated', description: 'Amenities and photos updated', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString(), },
  { activity_id: '5', type: 'booking_rejected', title: 'Booking Rejected', description: 'Sneha Pillai – Room 207 (Single) – capacity full', timestamp: new Date(Date.now() - 1000 * 60 * 60 * 8).toISOString(), },
];

const MOCK_BOOKINGS: Booking[] = [
  { booking_id: 'bkg_001', hostel_id: 'h1', room_id: 'r1', room_name: 'Room 204 (Double)', user: { user_id: 'u1', name: 'Rahul Verma', email: 'rahul@example.com', phone: '9876543210', profile_photo_url: null }, status: 'pending', check_in_date: '2026-07-01', check_out_date: null, requested_at: new Date(Date.now() - 1000 * 60 * 12).toISOString(), updated_at: '', notes: '' },
  { booking_id: 'bkg_002', hostel_id: 'h1', room_id: 'r2', room_name: 'Room 305 (Triple)', user: { user_id: 'u2', name: 'Amit Kumar', email: 'amit@example.com', phone: '9123456789', profile_photo_url: null }, status: 'pending', check_in_date: '2026-07-05', check_out_date: null, requested_at: new Date(Date.now() - 1000 * 60 * 90).toISOString(), updated_at: '', notes: '' },
  { booking_id: 'bkg_003', hostel_id: 'h1', room_id: 'r3', room_name: 'Room 101 (Single)', user: { user_id: 'u3', name: 'Priya Sharma', email: 'priya@example.com', phone: '9988776655', profile_photo_url: null }, status: 'approved', check_in_date: '2026-06-20', check_out_date: null, requested_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), updated_at: '', notes: '' },
  { booking_id: 'bkg_004', hostel_id: 'h1', room_id: 'r4', room_name: 'Room 207 (Single)', user: { user_id: 'u4', name: 'Sneha Pillai', email: 'sneha@example.com', phone: '9087654321', profile_photo_url: null }, status: 'rejected', check_in_date: '2026-06-25', check_out_date: null, requested_at: new Date(Date.now() - 1000 * 60 * 60 * 8).toISOString(), updated_at: '', notes: '' },
];

// ── Animated counter ──────────────────────────────────────────────────────────
const AnimatedCounter: React.FC<{ value: number | string; prefix?: string }> = ({ value, prefix = '' }) => {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    if (typeof value !== 'number') return;
    let cur = 0;
    const steps = 40;
    const inc = value / steps;
    const interval = setInterval(() => {
      cur += inc;
      if (cur >= value) { setDisplay(value); clearInterval(interval); }
      else setDisplay(Math.ceil(cur));
    }, 18);
    return () => clearInterval(interval);
  }, [value]);
  if (typeof value !== 'number') return <>{value}</>;
  return <>{prefix}{display.toLocaleString('en-IN')}</>;
};

// ── Stat Card ─────────────────────────────────────────────────────────────────
const StatCard: React.FC<{
  title: string; value: number | string; suffix?: string; prefix?: string;
  badge: string; color: string; icon: React.ReactNode; loading: boolean; delay: string;
}> = ({ title, value, suffix = '', prefix = '', badge, color, icon, loading, delay }) => (
  <div
    className="bg-[#1A1A1A] border border-[#2A2A2A] rounded-2xl p-6 relative overflow-hidden card-hover animate-fade-in-up"
    style={{ animationDelay: delay }}
  >
    <div className="absolute top-0 left-0 w-[4px] h-full rounded-l-2xl" style={{ backgroundColor: color }} />
    <div className="flex justify-between items-start mb-4 pl-2">
      <div className="text-[10px] uppercase tracking-widest font-bold text-[#9A9690]">{title}</div>
      <div className="w-9 h-9 rounded-[10px] flex items-center justify-center" style={{ backgroundColor: `${color}15` }}>
        {icon}
      </div>
    </div>
    <div className="pl-2">
      {loading ? (
        <div className="h-9 w-20 bg-[#2A2A2A] rounded-lg animate-pulse mb-3" />
      ) : (
        <div className="text-[34px] font-extrabold tracking-tight leading-none text-white mb-1">
          <AnimatedCounter value={value} prefix={prefix} />
          {suffix}
        </div>
      )}
      <span className="text-[11px] font-semibold px-2 py-1 rounded-md bg-[#2A2A2A] text-[#9A9690]">{badge}</span>
    </div>
  </div>
);

// ── Time-ago helper ───────────────────────────────────────────────────────────
function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

const ACTIVITY_ICONS: Record<string, { icon: string; color: string }> = {
  booking_request: { icon: '📋', color: '#3B82F6' },
  booking_approved: { icon: '✅', color: '#22C55E' },
  booking_rejected: { icon: '❌', color: '#EF4444' },
  payment_received: { icon: '💰', color: '#F59E0B' },
  hostel_updated: { icon: '🏨', color: '#8B5CF6' },
  room_updated: { icon: '🛏', color: '#E8571A' },
};

// ── Main Dashboard ────────────────────────────────────────────────────────────
export const DashboardPage: React.FC = () => {
  const { theme } = useTheme();
  const { isFirstTimeOwner, authUser } = useAuth();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [showWizard, setShowWizard] = useState(false);

  // Auto-show wizard for first-time owners
  useEffect(() => {
    if (isFirstTimeOwner) {
      const t = setTimeout(() => setShowWizard(true), 600);
      return () => clearTimeout(t);
    }
  }, [isFirstTimeOwner]);

  useEffect(() => {
    const t = setTimeout(() => {
      setStats(MOCK_STATS);
      setActivity(MOCK_ACTIVITY);
      setBookings(MOCK_BOOKINGS);
      setLoading(false);
    }, 900);
    return () => clearTimeout(t);
  }, []);

  const today = new Date().toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });

  const cardBg = theme === 'dark' ? 'bg-[#1A1A1A]' : 'bg-white';
  const cardBorder = theme === 'dark' ? 'border-[#2A2A2A]' : 'border-[#E8E5E0]';
  const textSub = theme === 'dark' ? 'text-[#9A9690]' : 'text-[#6B6B6B]';
  const rowHover = theme === 'dark' ? 'hover:bg-[#FFFFFF05]' : 'hover:bg-slate-50';

  const pendingBookings = bookings.filter(b => b.status === 'pending');

  return (
    <>
      {/* Enrollment Wizard Modal */}
      <Modal isOpen={showWizard} persistent className="w-full max-w-3xl">
        <HostelEnrollmentWizard onClose={() => setShowWizard(false)} />
      </Modal>

      <DashboardLayout title="Dashboard">
        <div className="w-full space-y-8">

          {/* Header */}
          <header className="flex justify-between items-end animate-fade-in-up">
            <div>
              <h1 className="text-[28px] font-bold">
                Welcome back, {authUser?.display_name || 'Admin'} 👋
              </h1>
              <p className={`${textSub} mt-1 font-medium`}>
                Here's what's happening at your hostel today
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowWizard(true)}
                className="hidden md:flex items-center gap-2 bg-[#E8571A]/10 hover:bg-[#E8571A]/20 border border-[#E8571A]/30 text-[#E8571A] text-sm font-semibold px-4 py-2 rounded-[10px] transition-all"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Add Hostel
              </button>
              <div className={`flex items-center gap-2 ${cardBg} border ${cardBorder} px-3 py-2 rounded-full text-xs font-semibold ${textSub}`}>
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                {today}
              </div>
            </div>
          </header>

          {/* 8 Stat Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard title="Registered Hostel" value={loading ? '—' : stats?.registered_hostel ? 1 : 0}
              badge="Active" color="#22C55E" loading={loading} delay="0ms"
              icon={<svg className="w-5 h-5 text-[#22C55E]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>} />

            <StatCard title="Total Rooms" value={loading ? '—' : stats!.total_rooms}
              badge="All rooms" color="#3B82F6" loading={loading} delay="60ms"
              icon={<svg className="w-5 h-5 text-[#3B82F6]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>} />

            <StatCard title="Available Rooms" value={loading ? '—' : stats!.available_rooms}
              badge="Vacant" color="#A78BFA" loading={loading} delay="120ms"
              icon={<svg className="w-5 h-5 text-[#A78BFA]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>} />

            <StatCard title="Occupied Rooms" value={loading ? '—' : stats!.occupied_rooms}
              badge="In use" color="#F97316" loading={loading} delay="180ms"
              icon={<svg className="w-5 h-5 text-[#F97316]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>} />

            <StatCard title="Pending Requests" value={loading ? '—' : stats!.pending_requests}
              badge="Needs action" color="#F59E0B" loading={loading} delay="240ms"
              icon={<svg className="w-5 h-5 text-[#F59E0B]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>} />

            <StatCard title="Booked Users" value={loading ? '—' : stats!.booked_users}
              badge="Total guests" color="#EC4899" loading={loading} delay="300ms"
              icon={<svg className="w-5 h-5 text-[#EC4899]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" /></svg>} />

            <StatCard title="Monthly Revenue" value={loading ? '—' : stats!.monthly_revenue}
              prefix="₹" badge="This month" color="#10B981" loading={loading} delay="360ms"
              icon={<svg className="w-5 h-5 text-[#10B981]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>} />

            <StatCard title="Pending Payments" value={loading ? '—' : stats!.pending_payments}
              prefix="₹" badge="Outstanding" color="#EF4444" loading={loading} delay="420ms"
              icon={<svg className="w-5 h-5 text-[#EF4444]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>} />
          </div>

          {/* Main content grid */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

            {/* Left col: Pending Bookings + Recent Activity */}
            <div className="xl:col-span-2 space-y-6">

              {/* Pending Booking Requests */}
              <div className="animate-fade-in-up" style={{ animationDelay: '480ms' }}>
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-[17px] font-bold flex items-center gap-2">
                    Booking Requests
                    {pendingBookings.length > 0 && (
                      <span className="bg-amber-500/20 text-amber-400 border border-amber-500/30 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                        {pendingBookings.length} pending
                      </span>
                    )}
                  </h2>
                  <button onClick={() => navigate('/bookings')}
                    className="text-[#E8571A] hover:text-[#FF6B35] text-sm font-semibold transition-colors">
                    View all →
                  </button>
                </div>

                <div className={`${cardBg} rounded-2xl border ${cardBorder} overflow-hidden`}>
                  {loading ? (
                    <div className="p-6 space-y-4">
                      {[...Array(3)].map((_, i) => (
                        <div key={i} className="h-16 bg-[#2A2A2A] rounded-xl animate-pulse" />
                      ))}
                    </div>
                  ) : bookings.length === 0 ? (
                    <div className="py-12 text-center">
                      <div className="text-4xl mb-3">📋</div>
                      <p className={`${textSub} font-medium`}>No booking requests yet</p>
                    </div>
                  ) : (
                    <div className="divide-y divide-[#2A2A2A]">
                      {bookings.slice(0, 4).map(booking => (
                        <BookingRow key={booking.booking_id} booking={booking} rowHover={rowHover} textSub={textSub} />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Right col: Recent Activity */}
            <div className="animate-fade-in-up" style={{ animationDelay: '540ms' }}>
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-[17px] font-bold">Recent Activity</h2>
              </div>

              <div className={`${cardBg} rounded-2xl border ${cardBorder} p-5`}>
                {loading ? (
                  <div className="space-y-4">
                    {[...Array(5)].map((_, i) => (
                      <div key={i} className="flex gap-3">
                        <div className="w-8 h-8 bg-[#2A2A2A] rounded-full animate-pulse flex-shrink-0" />
                        <div className="flex-1 space-y-1.5">
                          <div className="h-3 bg-[#2A2A2A] rounded animate-pulse w-3/4" />
                          <div className="h-2.5 bg-[#2A2A2A] rounded animate-pulse w-full" />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-1">
                    {activity.map((item, i) => {
                      const cfg = ACTIVITY_ICONS[item.type] || { icon: '📌', color: '#9A9690' };
                      return (
                        <div key={item.activity_id} className={`flex gap-3 py-3 ${i < activity.length - 1 ? 'border-b border-[#2A2A2A]' : ''}`}>
                          <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-base"
                            style={{ backgroundColor: `${cfg.color}15` }}>
                            {cfg.icon}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-white text-[13px] font-semibold leading-tight">{item.title}</p>
                            <p className={`${textSub} text-[11px] mt-0.5 truncate`}>{item.description}</p>
                            <p className="text-[#4A4A4A] text-[10px] mt-1 font-medium">{timeAgo(item.timestamp)}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>

        </div>
      </DashboardLayout>
    </>
  );
};

// ── Booking Row Component ─────────────────────────────────────────────────────
const StatusPill: React.FC<{ status: string }> = ({ status }) => {
  const map: Record<string, string> = {
    pending: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    approved: 'bg-green-500/10 text-green-400 border-green-500/20',
    rejected: 'bg-red-500/10 text-red-400 border-red-500/20',
    cancelled: 'bg-[#2A2A2A] text-[#9A9690] border-[#3A3A3A]',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-[6px] text-[10px] font-bold border capitalize ${map[status] || map.cancelled}`}>
      {status}
    </span>
  );
};

const BookingRow: React.FC<{ booking: Booking; rowHover: string; textSub: string }> = ({
  booking, rowHover, textSub
}) => {
  const initials = booking.user.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();

  return (
    <div className={`flex items-center gap-4 px-5 py-4 ${rowHover} transition-colors`}>
      {/* Avatar */}
      <div className="w-9 h-9 rounded-full bg-[#E8571A]/15 border border-[#E8571A]/20 flex items-center justify-center text-xs font-bold text-[#E8571A] flex-shrink-0">
        {initials}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-white text-sm font-semibold truncate">{booking.user.name}</p>
        <p className={`${textSub} text-xs truncate`}>{booking.room_name}</p>
      </div>

      {/* Date */}
      <div className="text-right hidden sm:block">
        <p className={`${textSub} text-xs`}>{new Date(booking.check_in_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</p>
        <StatusPill status={booking.status} />
      </div>

      {/* Actions for pending */}
      {booking.status === 'pending' && (
        <div className="flex gap-1.5 flex-shrink-0">
          <button className="w-7 h-7 bg-green-500/10 hover:bg-green-500/25 border border-green-500/20 rounded-[7px] flex items-center justify-center text-green-400 transition-all" title="Approve">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
          </button>
          <button className="w-7 h-7 bg-red-500/10 hover:bg-red-500/25 border border-red-500/20 rounded-[7px] flex items-center justify-center text-red-400 transition-all" title="Reject">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
};
