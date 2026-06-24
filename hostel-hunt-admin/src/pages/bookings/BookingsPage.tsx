import React, { useState } from 'react';
import { DashboardLayout } from '../../components/common/DashboardLayout';
import { useTheme } from '../../contexts/ThemeContext';
import type { Booking } from '../../types';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';

const MOCK_BOOKINGS: Booking[] = [
  { booking_id: 'bkg_001', hostel_id: 'h1', room_id: 'r1', room_name: 'Room 204 (Double)', user: { user_id: 'u1', name: 'Rahul Verma', email: 'rahul@example.com', phone: '9876543210', profile_photo_url: null }, status: 'pending', check_in_date: '2026-07-01', check_out_date: null, requested_at: new Date(Date.now() - 1000 * 60 * 12).toISOString(), updated_at: '', notes: '' },
  { booking_id: 'bkg_002', hostel_id: 'h1', room_id: 'r2', room_name: 'Room 305 (Triple)', user: { user_id: 'u2', name: 'Amit Kumar', email: 'amit@example.com', phone: '9123456789', profile_photo_url: null }, status: 'pending', check_in_date: '2026-07-05', check_out_date: null, requested_at: new Date(Date.now() - 1000 * 60 * 90).toISOString(), updated_at: '', notes: '' },
  { booking_id: 'bkg_003', hostel_id: 'h1', room_id: 'r3', room_name: 'Room 101 (Single)', user: { user_id: 'u3', name: 'Priya Sharma', email: 'priya@example.com', phone: '9988776655', profile_photo_url: null }, status: 'approved', check_in_date: '2026-06-20', check_out_date: null, requested_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), updated_at: '', notes: '' },
  { booking_id: 'bkg_004', hostel_id: 'h1', room_id: 'r4', room_name: 'Room 207 (Single)', user: { user_id: 'u4', name: 'Sneha Pillai', email: 'sneha@example.com', phone: '9087654321', profile_photo_url: null }, status: 'rejected', check_in_date: '2026-06-25', check_out_date: null, requested_at: new Date(Date.now() - 1000 * 60 * 60 * 8).toISOString(), updated_at: '', notes: '' },
  { booking_id: 'bkg_005', hostel_id: 'h1', room_id: 'r5', room_name: 'Room 108 (Double)', user: { user_id: 'u5', name: 'Mohan Das', email: 'mohan@example.com', phone: '9871234560', profile_photo_url: null }, status: 'checked_in', check_in_date: '2026-06-10', check_out_date: '2026-07-10', requested_at: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5).toISOString(), updated_at: '', notes: '' },
];

type FilterStatus = 'all' | 'pending' | 'approved' | 'rejected' | 'checked_in';

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  approved: 'bg-green-500/10 text-green-400 border-green-500/20',
  rejected: 'bg-red-500/10 text-red-400 border-red-500/20',
  checked_in: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  cancelled: 'bg-[#2A2A2A] text-[#9A9690] border-[#3A3A3A]',
};

function timeAgo(iso: string) {
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export const BookingsPage: React.FC = () => {
  const { theme } = useTheme();
  const [bookings, setBookings] = useState(MOCK_BOOKINGS);
  const [filter, setFilter] = useState<FilterStatus>('all');
  const [actionTarget, setActionTarget] = useState<{ id: string; action: 'approve' | 'reject' } | null>(null);

  const cardBg = theme === 'dark' ? 'bg-[#1A1A1A]' : 'bg-white';
  const cardBorder = theme === 'dark' ? 'border-[#2A2A2A]' : 'border-[#E8E5E0]';
  const textSub = theme === 'dark' ? 'text-[#9A9690]' : 'text-[#6B6B6B]';
  const rowHover = theme === 'dark' ? 'hover:bg-[#FFFFFF05]' : 'hover:bg-slate-50';

  const filtered = filter === 'all' ? bookings : bookings.filter(b => b.status === filter);

  const handleAction = () => {
    if (!actionTarget) return;
    setBookings(prev =>
      prev.map(b => b.booking_id === actionTarget.id
        ? { ...b, status: actionTarget.action === 'approve' ? 'approved' : 'rejected' }
        : b
      )
    );
    setActionTarget(null);
  };

  const FILTERS: { key: FilterStatus; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'pending', label: 'Pending' },
    { key: 'approved', label: 'Approved' },
    { key: 'rejected', label: 'Rejected' },
    { key: 'checked_in', label: 'Checked In' },
  ];

  return (
    <DashboardLayout title="Bookings">
      <ConfirmDialog
        isOpen={!!actionTarget}
        title={actionTarget?.action === 'approve' ? 'Approve booking?' : 'Reject booking?'}
        message={actionTarget?.action === 'approve'
          ? 'This will approve the booking request and notify the guest.'
          : 'This will reject the booking request and notify the guest.'}
        confirmLabel={actionTarget?.action === 'approve' ? 'Approve' : 'Reject'}
        variant={actionTarget?.action === 'approve' ? 'info' : 'danger'}
        onConfirm={handleAction}
        onCancel={() => setActionTarget(null)}
      />

      <div className="w-full animate-fade-in-up space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Booking Requests</h1>
          <p className={`${textSub} mt-1 text-sm font-medium`}>Manage and track all guest booking requests</p>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'Pending', count: bookings.filter(b => b.status === 'pending').length, color: '#F59E0B' },
            { label: 'Approved', count: bookings.filter(b => b.status === 'approved').length, color: '#22C55E' },
            { label: 'Rejected', count: bookings.filter(b => b.status === 'rejected').length, color: '#EF4444' },
            { label: 'Checked In', count: bookings.filter(b => b.status === 'checked_in').length, color: '#3B82F6' },
          ].map(s => (
            <div key={s.label} className={`${cardBg} border ${cardBorder} rounded-xl p-4`}>
              <div className="text-2xl font-extrabold" style={{ color: s.color }}>{s.count}</div>
              <div className={`text-xs font-semibold ${textSub} mt-1`}>{s.label}</div>
            </div>
          ))}
        </div>

        {/* Filter tabs + table */}
        <div className={`${cardBg} border ${cardBorder} rounded-2xl overflow-hidden`}>
          {/* Filter bar */}
          <div className="flex gap-1 p-4 border-b border-[#2A2A2A] overflow-x-auto">
            {FILTERS.map(f => (
              <button key={f.key} onClick={() => setFilter(f.key)}
                className={`px-4 py-1.5 rounded-[8px] text-sm font-semibold transition-all whitespace-nowrap ${
                  filter === f.key
                    ? 'bg-[#E8571A] text-white'
                    : `${textSub} hover:text-white hover:bg-[#FFFFFF08]`
                }`}>
                {f.label}
                {f.key !== 'all' && (
                  <span className="ml-1.5 text-[10px]">
                    ({bookings.filter(b => b.status === f.key).length})
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Table */}
          {filtered.length === 0 ? (
            <div className="py-16 text-center">
              <div className="text-4xl mb-3">📋</div>
              <p className={`${textSub} font-medium`}>No bookings in this category</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className={`text-[10px] uppercase tracking-wider font-bold ${textSub} border-b border-[#2A2A2A]`}>
                    <th className="px-5 py-3">Guest</th>
                    <th className="px-5 py-3 hidden sm:table-cell">Room</th>
                    <th className="px-5 py-3 hidden md:table-cell">Check-in</th>
                    <th className="px-5 py-3 hidden md:table-cell">Requested</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(booking => {
                    const initials = booking.user.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
                    return (
                      <tr key={booking.booking_id} className={`border-b border-[#2A2A2A] last:border-0 ${rowHover} transition-colors`}>
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-[#E8571A]/15 border border-[#E8571A]/20 flex items-center justify-center text-xs font-bold text-[#E8571A] flex-shrink-0">
                              {initials}
                            </div>
                            <div>
                              <p className="text-white text-sm font-semibold">{booking.user.name}</p>
                              <p className={`${textSub} text-xs`}>{booking.user.phone}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-5 py-4 hidden sm:table-cell">
                          <p className="text-white text-sm font-medium">{booking.room_name}</p>
                        </td>
                        <td className={`px-5 py-4 ${textSub} text-sm hidden md:table-cell`}>
                          {new Date(booking.check_in_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                        </td>
                        <td className={`px-5 py-4 ${textSub} text-xs hidden md:table-cell`}>
                          {timeAgo(booking.requested_at)}
                        </td>
                        <td className="px-5 py-4">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-[6px] text-[10px] font-bold border capitalize ${STATUS_STYLES[booking.status] || STATUS_STYLES.cancelled}`}>
                            {booking.status.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-right">
                          {booking.status === 'pending' && (
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => setActionTarget({ id: booking.booking_id, action: 'approve' })}
                                className="flex items-center gap-1 bg-green-500/10 hover:bg-green-500/20 border border-green-500/20 text-green-400 text-xs font-semibold px-3 py-1.5 rounded-[8px] transition-all">
                                Approve
                              </button>
                              <button
                                onClick={() => setActionTarget({ id: booking.booking_id, action: 'reject' })}
                                className="flex items-center gap-1 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 text-xs font-semibold px-3 py-1.5 rounded-[8px] transition-all">
                                Reject
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
};
