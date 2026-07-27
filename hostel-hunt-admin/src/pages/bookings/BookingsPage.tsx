import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { DashboardLayout } from '../../components/common/DashboardLayout';
import { useTheme } from '../../contexts/ThemeContext';
import type { Booking } from '../../types';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { bookingService } from '../../services/api';

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  approved: 'bg-green-500/10 text-green-400 border-green-500/20',
  confirmed: 'bg-green-500/10 text-green-400 border-green-500/20',
  verified: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
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
  const location = useLocation();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [actionTarget, setActionTarget] = useState<{ id: string; action: 'approve' | 'reject' | 'verify' } | null>(null);

  const searchParams = new URLSearchParams(location.search);
  const currentTab = searchParams.get('tab') || 'offline-requests';

  useEffect(() => {
    fetchBookings();
  }, []);

  const fetchBookings = async () => {
    try {
      setIsLoading(true);
      const res = await bookingService.getBookings();
      setBookings(res?.data || res || []);
    } catch (error) {
      console.error('Failed to fetch bookings:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const cardBg = theme === 'dark' ? 'bg-[#1A1A1A]' : 'bg-white';
  const cardBorder = theme === 'dark' ? 'border-[#2A2A2A]' : 'border-[#E8E5E0]';
  const textSub = theme === 'dark' ? 'text-[#9A9690]' : 'text-[#6B6B6B]';

  const filteredBookings = bookings.filter(b => {
    // Default backward compatibility to offline if not specified
    const method = b.payment_method || 'offline';
    
    if (currentTab === 'offline-requests') {
      return method === 'offline' && b.status === 'pending';
    }
    if (currentTab === 'offline-confirmed') {
      return method === 'offline' && (b.status === 'confirmed' || b.status === 'approved');
    }
    if (currentTab === 'online-requests') {
      return method === 'online' && b.status === 'pending';
    }
    if (currentTab === 'online-payments') {
      return method === 'online' && b.status === 'verified';
    }
    return false;
  });

  const handleAction = async () => {
    if (!actionTarget) return;
    try {
      if (actionTarget.action === 'approve') {
        await bookingService.approveBooking(actionTarget.id);
      } else if (actionTarget.action === 'reject') {
        await bookingService.rejectBooking(actionTarget.id);
      } else if (actionTarget.action === 'verify') {
        await bookingService.verifyPayment(actionTarget.id);
      }
      await fetchBookings();
    } catch (error) {
      console.error('Failed to update booking status', error);
      alert('Failed to update booking status');
    } finally {
      setActionTarget(null);
    }
  };

  const renderConfirmDialog = () => {
    if (!actionTarget) return null;
    let title = 'Approve booking?';
    let message = 'This will confirm the booking request and notify the guest.';
    let label = 'Approve';
    let variant: 'info' | 'danger' = 'info';

    if (actionTarget.action === 'reject') {
      title = 'Reject booking?';
      message = 'This will reject the booking request and notify the guest.';
      label = 'Reject';
      variant = 'danger';
    } else if (actionTarget.action === 'verify') {
      title = 'Verify Payment?';
      message = 'This will verify the online payment and confirm the booking.';
      label = 'Verify';
      variant = 'info';
    }

    return (
      <ConfirmDialog
        isOpen={!!actionTarget}
        title={title}
        message={message}
        confirmLabel={label}
        variant={variant}
        onConfirm={handleAction}
        onCancel={() => setActionTarget(null)}
      />
    );
  };

  const renderBookingCard = (booking: Booking, isRequest: boolean) => {
    const initials = booking.user.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
    
    return (
      <div key={booking.booking_id} className={`${cardBg} border ${cardBorder} rounded-xl p-5 shadow-sm flex flex-col hover:border-[#E8571A]/30 transition-colors`}>
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-[#E8571A]/15 border border-[#E8571A]/20 flex items-center justify-center text-sm font-bold text-[#E8571A] flex-shrink-0">
              {initials}
            </div>
            <div>
              <p className="text-white text-[15px] font-bold leading-tight">{booking.user.name}</p>
              <p className={`${textSub} text-[13px] mt-0.5`}>{booking.user.phone}</p>
            </div>
          </div>
          <span className={`inline-flex items-center px-2 py-0.5 rounded-[6px] text-[10px] font-bold border capitalize ${STATUS_STYLES[booking.status] || STATUS_STYLES.cancelled}`}>
            {booking.status.replace('_', ' ')}
          </span>
        </div>
        
        <div className="flex-1 grid grid-cols-2 gap-y-3 gap-x-4 mb-5 text-[13px]">
          <div>
            <p className={`${textSub} text-[11px] font-bold uppercase tracking-wider mb-0.5`}>Room</p>
            <p className="text-white font-medium">{booking.room_name || 'N/A'}</p>
          </div>
          <div>
            <p className={`${textSub} text-[11px] font-bold uppercase tracking-wider mb-0.5`}>Floor / Bed</p>
            <p className="text-white font-medium">
              {booking.floor_number ? `Floor ${booking.floor_number}` : '-'} / {booking.bed_number ? `Bed ${booking.bed_number}` : '-'}
            </p>
          </div>
          <div>
            <p className={`${textSub} text-[11px] font-bold uppercase tracking-wider mb-0.5`}>Requested</p>
            <p className="text-white font-medium">{timeAgo(booking.requested_at)}</p>
          </div>
          <div>
            <p className={`${textSub} text-[11px] font-bold uppercase tracking-wider mb-0.5`}>Rent</p>
            <p className="text-[#E8571A] font-bold">₹{booking.rent_amount || 'N/A'}</p>
          </div>
        </div>

        {isRequest && (
          <div className="flex items-center gap-3 mt-auto pt-4 border-t border-[#2A2A2A]">
            {currentTab === 'online-requests' ? (
              <button
                onClick={() => setActionTarget({ id: booking.booking_id, action: 'verify' })}
                className="flex-1 bg-[#E8571A]/10 hover:bg-[#E8571A]/20 border border-[#E8571A]/30 text-[#E8571A] text-[13px] font-bold py-2 rounded-[8px] transition-all">
                Verify Payment
              </button>
            ) : (
              <button
                onClick={() => setActionTarget({ id: booking.booking_id, action: 'approve' })}
                className="flex-1 bg-green-500/10 hover:bg-green-500/20 border border-green-500/30 text-green-400 text-[13px] font-bold py-2 rounded-[8px] transition-all">
                Accept
              </button>
            )}
            <button
              onClick={() => setActionTarget({ id: booking.booking_id, action: 'reject' })}
              className="flex-1 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 text-[13px] font-bold py-2 rounded-[8px] transition-all">
              Reject
            </button>
          </div>
        )}
      </div>
    );
  };

  const renderHeader = () => {
    switch (currentTab) {
      case 'offline-requests':
        return { title: 'Offline Booking Requests', desc: 'Pending requests that have selected offline payment' };
      case 'offline-confirmed':
        return { title: 'Confirmed Offline Bookings', desc: 'Successfully confirmed offline bookings' };
      case 'online-requests':
        return { title: 'Online Booking Requests', desc: 'Pending requests requiring payment verification' };
      case 'online-payments':
        return { title: 'Payments Received', desc: 'Coming soon - Verified online payment transactions' };
      default:
        return { title: 'Bookings', desc: 'Manage your hostel bookings' };
    }
  };

  const headerInfo = renderHeader();
  const isRequestTab = currentTab === 'offline-requests' || currentTab === 'online-requests';

  return (
    <DashboardLayout title="Bookings">
      {renderConfirmDialog()}

      <div className="w-full animate-fade-in-up space-y-6">
        <div>
          <h1 className="text-2xl font-bold">{headerInfo.title}</h1>
          <p className={`${textSub} mt-1 text-sm font-medium`}>{headerInfo.desc}</p>
        </div>

        {currentTab === 'online-payments' && (
          <div className="bg-[#E8571A]/10 border border-[#E8571A]/20 rounded-xl p-6 text-center mt-6">
            <span className="text-4xl mb-3 block">🚧</span>
            <h2 className="text-[#E8571A] text-lg font-bold mb-2">Payments Received is Inactive for Now</h2>
            <p className={`${textSub} text-sm max-w-md mx-auto`}>
              This section is a placeholder for the future Razorpay online payment system.
              Once integrated, verified online bookings will automatically appear here.
            </p>
          </div>
        )}

        {currentTab !== 'online-payments' && (
          <>
            {isLoading ? (
              <div className="py-16 text-center text-[#9A9690] font-medium text-sm animate-pulse">
                Loading bookings...
              </div>
            ) : filteredBookings.length === 0 ? (
              <div className={`py-16 text-center ${cardBg} border ${cardBorder} rounded-2xl`}>
                <div className="text-4xl mb-3">📋</div>
                <p className={`${textSub} font-medium`}>No bookings found in this section</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredBookings.map(b => renderBookingCard(b, isRequestTab))}
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
};
