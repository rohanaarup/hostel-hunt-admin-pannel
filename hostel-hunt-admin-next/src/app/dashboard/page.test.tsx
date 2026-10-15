import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { httpError, renderWithQueryClient } from '@/test-utils';

// Only the network and the heavy visuals are replaced; the page, its hooks and the error handling are real.
const api = vi.hoisted(() => ({
  hostelService: { getDashboardStats: vi.fn(), getRecentActivity: vi.fn() },
  bookingService: { getBookings: vi.fn(), approveBooking: vi.fn(), rejectBooking: vi.fn() },
}));
vi.mock('@/services/api', () => api);
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ isReady: true, isAuthenticated: true, isFirstTimeOwner: false, authUser: { display_name: 'Test Owner' } }),
}));
vi.mock('gsap', () => ({
  default: { fromTo: vi.fn(), to: vi.fn(), context: (fn: () => void) => { fn(); return { revert: vi.fn() }; } },
}));
vi.mock('@/components/common/DashboardLayout', () => ({ default: ({ children }: any) => <div>{children}</div> }));
vi.mock('@/components/ui/Modal', () => ({ default: () => null }));
vi.mock('@/components/hostel/HostelEnrollmentWizard', () => ({ default: () => null }));
vi.mock('@/components/dashboard/NoticeBoard', () => ({ default: () => null }));
vi.mock('@/components/charts/BookingDensityMap', () => ({ default: () => null }));
vi.mock('@/components/charts/ChartBundle', () => ({
  Donut: ({ data }: any) => <div data-testid="donut">{JSON.stringify(data)}</div>,
  SimpleBar: ({ data }: any) => <div data-testid="bars">{JSON.stringify(data)}</div>,
}));
vi.mock('@/components/ui/StatCard', () => ({
  default: ({ title, value }: any) => <div data-testid="stat">{`${title}: ${value}`}</div>,
}));
vi.mock('@/components/ui/ChartCard', () => ({
  default: ({ title, children, isEmpty }: any) => <section><h3>{title}</h3>{isEmpty ? <p>empty</p> : children}</section>,
}));

import DashboardPage from './page';

const STATS = {
  total_hostels: 2,
  total_residents: 14,
  total_beds: 40,
  occupancy_rate: 35,
  revenue_collected: 90000,
  revenue_pending: 12000,
  pending_bookings: 12,
  bookings_by_status: { pending: 12, confirmed: 30, paid: 5, cancelled: 1, rejected: 2 },
  bookings_by_payment_mode: { offline: 38, online: 12 },
};

const booking = (id: string, name: string) => ({
  id, student_name: name, status: 'pending', payment_mode: 'offline', created_at: '2026-10-01T10:00:00Z',
  room_display: 'Room 1', bed_number: '2',
});

beforeEach(() => {
  vi.clearAllMocks();
  api.hostelService.getRecentActivity.mockResolvedValue({ success: true, data: [] });
  api.bookingService.getBookings.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
});

describe('the dashboard when the stats call fails (X15: it used to stay a skeleton forever)', () => {
  it('shows what went wrong and a Retry, and no made-up numbers', async () => {
    api.hostelService.getDashboardStats.mockRejectedValue(httpError(503));

    renderWithQueryClient(<DashboardPage />);

    expect(await screen.findByText('Could not load the dashboard numbers')).toBeInTheDocument();
    expect(screen.getByText('The server is starting up. Please try again in a few seconds.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    for (const card of screen.getAllByTestId('stat')) expect(card.textContent).toMatch(/: —$/);
    expect(screen.queryByTestId('donut')).not.toBeInTheDocument();
  });

  it('Retry asks again and the real numbers appear', async () => {
    api.hostelService.getDashboardStats.mockRejectedValueOnce(httpError(503)).mockResolvedValue({ success: true, data: STATS });

    renderWithQueryClient(<DashboardPage />);
    fireEvent.click(await screen.findByRole('button', { name: /retry/i }));

    await waitFor(() => expect(screen.getByText('Registered Hostels: 2')).toBeInTheDocument());
    expect(screen.queryByText('Could not load the dashboard numbers')).not.toBeInTheDocument();
    expect(api.hostelService.getDashboardStats).toHaveBeenCalledTimes(2);
  });

  it('says why when the reply cannot be read at all', async () => {
    api.hostelService.getDashboardStats.mockResolvedValue('<html>maintenance</html>');

    renderWithQueryClient(<DashboardPage />);

    expect(await screen.findByText(/couldn't read/i)).toBeInTheDocument();
  });
});

describe('the dashboard numbers are the server\'s totals, not one page of rows', () => {
  it('the donuts use the counts over ALL bookings even when the list holds only two rows', async () => {
    api.hostelService.getDashboardStats.mockResolvedValue({ success: true, data: STATS });
    api.bookingService.getBookings.mockResolvedValue({
      count: 50, next: 'http://x/?page=2', previous: null, results: [booking('a', 'Asha Rao'), booking('b', 'Ravi Kumar')],
    });

    renderWithQueryClient(<DashboardPage />);

    const donuts = await screen.findAllByTestId('donut');
    const statusDonut = donuts.map((d) => JSON.parse(d.textContent!)).find((d: any[]) => d.some((x) => x.name === 'confirmed'));
    expect(statusDonut).toEqual(expect.arrayContaining([{ name: 'pending', value: 12 }, { name: 'confirmed', value: 30 }]));
    expect(screen.getByTestId('bars').textContent).toContain('"value":38');
    const occupancy = donuts.map((d) => JSON.parse(d.textContent!)).find((d: any[]) => d.some((x) => x.name === 'Occupied'));
    expect(occupancy).toEqual([{ name: 'Available', value: 26 }, { name: 'Occupied', value: 14 }]);
  });

  it('the pending requests come from the server filter and a paged reply is read correctly', async () => {
    api.hostelService.getDashboardStats.mockResolvedValue({ success: true, data: STATS });
    api.bookingService.getBookings.mockImplementation(async (params: any = {}) =>
      params.status === 'pending'
        ? { count: 12, next: 'x', previous: null, results: [booking('a', 'Asha Rao')] }
        : { count: 50, next: null, previous: null, results: [] });

    renderWithQueryClient(<DashboardPage />);

    expect(await screen.findByText('Asha Rao')).toBeInTheDocument();
    expect(api.bookingService.getBookings).toHaveBeenCalledWith({ status: 'pending', page_size: 10 });
    expect(screen.getByText('12 pending')).toBeInTheDocument();
  });

  it('a failed pending-requests call shows its own error and Retry, not an empty "no requests" panel', async () => {
    api.hostelService.getDashboardStats.mockResolvedValue({ success: true, data: STATS });
    api.bookingService.getBookings.mockImplementation(async (params: any = {}) => {
      if (params.status === 'pending') throw httpError(500, { detail: 'oops' });
      return { count: 0, next: null, previous: null, results: [] };
    });

    renderWithQueryClient(<DashboardPage />);

    expect(await screen.findByText('Could not load booking requests')).toBeInTheDocument();
    expect(screen.queryByText('No pending requests')).not.toBeInTheDocument();
  });
});
