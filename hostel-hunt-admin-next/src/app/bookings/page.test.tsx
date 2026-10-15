import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { httpError, renderWithQueryClient } from '@/test-utils';

const api = vi.hoisted(() => ({
  bookingService: {
    getBookings: vi.fn(), approveBooking: vi.fn(), rejectBooking: vi.fn(), verifyPayment: vi.fn(), markBookingPaid: vi.fn(),
  },
  hostelService: { getDashboardStats: vi.fn(), getRecentActivity: vi.fn() },
}));
vi.mock('@/services/api', () => api);
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams(), useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ isReady: true, isAuthenticated: true }) }));
vi.mock('gsap', () => ({ default: { fromTo: vi.fn(), to: vi.fn() } }));
vi.mock('@/components/common/DashboardLayout', () => ({ default: ({ children }: any) => <div>{children}</div> }));

import BookingsPage from './page';

const row = (id: string, student: string, over: Record<string, unknown> = {}) => ({
  id, student_name: student, student_phone: '9000000001', hostel_name: 'Sunrise PG', room_display: 'Room 101',
  bed_number: '2', status: 'pending', payment_mode: 'offline', amount: '6500.00', created_at: '2026-10-01T10:00:00Z', ...over,
});

const STATS = {
  total_hostels: 1, total_residents: 0, total_beds: 0, occupancy_rate: 0, revenue_collected: 0, revenue_pending: 0,
  pending_bookings: 30,
  bookings_by_status: { pending: 30, confirmed: 15, paid: 4, cancelled: 0, rejected: 1 },
  bookings_by_payment_mode: { offline: 40, online: 10 },
};

beforeEach(() => {
  vi.clearAllMocks();
  api.hostelService.getDashboardStats.mockResolvedValue({ success: true, data: STATS });
});

describe('the Bookings page reads the paged reply (X15: it used to show an empty list always)', () => {
  it('shows the bookings of a { count, results } reply', async () => {
    api.bookingService.getBookings.mockResolvedValue({
      count: 50, next: 'http://x/api/v1/bookings/?page=2', previous: null, results: [row('b1', 'Asha Rao')],
    });

    renderWithQueryClient(<BookingsPage />);

    expect(await screen.findByText('Asha Rao')).toBeInTheDocument();
    expect(screen.getByText('Showing 1 of 50 bookings')).toBeInTheDocument();
  });

  it('the summary numbers are the server totals, not the rows loaded', async () => {
    api.bookingService.getBookings.mockResolvedValue({
      count: 50, next: 'x', previous: null, results: [row('b1', 'Asha Rao')],
    });

    renderWithQueryClient(<BookingsPage />);
    await screen.findByText('Asha Rao');

    await waitFor(() => expect(screen.getByText('30')).toBeInTheDocument()); // pending, over all bookings
    expect(screen.getByText('50')).toBeInTheDocument(); // total
  });

  it('"Load more" fetches the next page and appends it', async () => {
    api.bookingService.getBookings.mockImplementation(async (params: any = {}) =>
      params.page === 2
        ? { count: 2, next: null, previous: null, results: [row('b2', 'Ravi Kumar')] }
        : { count: 2, next: 'http://x/?page=2', previous: null, results: [row('b1', 'Asha Rao')] });

    renderWithQueryClient(<BookingsPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Load more' }));

    expect(await screen.findByText('Ravi Kumar')).toBeInTheDocument();
    expect(screen.getByText('Asha Rao')).toBeInTheDocument();
    expect(api.bookingService.getBookings).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument());
  });

  it('still accepts the older { data: [...] } and bare-array replies', async () => {
    api.bookingService.getBookings.mockResolvedValue({ success: true, data: [row('b1', 'Asha Rao')] });

    renderWithQueryClient(<BookingsPage />);

    expect(await screen.findByText('Asha Rao')).toBeInTheDocument();
  });
});

describe('when the bookings cannot be loaded', () => {
  it('shows the reason and a Retry that works, not an empty "no bookings" page', async () => {
    api.bookingService.getBookings
      .mockRejectedValueOnce(httpError(503))
      .mockResolvedValue({ count: 1, next: null, previous: null, results: [row('b1', 'Asha Rao')] });

    renderWithQueryClient(<BookingsPage />);

    expect(await screen.findByText('Could not load bookings')).toBeInTheDocument();
    expect(screen.getByText('The server is starting up. Please try again in a few seconds.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));

    expect(await screen.findByText('Asha Rao')).toBeInTheDocument();
  });
});
