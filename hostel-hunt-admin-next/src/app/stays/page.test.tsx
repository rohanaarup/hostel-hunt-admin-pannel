import React from 'react';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { httpError, renderWithQueryClient } from '@/test-utils';
import type { AdminStayRow, AdminStaysPage } from '@/types';

const api = vi.hoisted(() => ({
  stayService: { getAdminStays: vi.fn(), recordPayment: vi.fn(), voidPayment: vi.fn(), sendReminder: vi.fn(), endStay: vi.fn() },
  hostelService: { getDashboardStats: vi.fn() },
}));
vi.mock('@/services/api', () => api);
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ isReady: true, isAuthenticated: true }) }));
vi.mock('@/components/common/DashboardLayout', () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock('next/link', () => ({ default: ({ href, children, ...rest }: any) => <a href={href} {...rest}>{children}</a> }));

import StaysPage from './page';

const row = (name: string, status: AdminStayRow['status'], primary: AdminStayRow['primary_action'], over: Partial<AdminStayRow> = {}): AdminStayRow => ({
  id: `s-${name}`, student_name: name, hostel_id: 'h1', hostel_name: 'Sample PG', room_label: 'Room 101', bed_label: 'Bed A',
  rent_amount: '6000.00', join_date: '2026-06-18', stay_status: 'ACTIVE', needs_review: false, status,
  status_label: status[0] + status.slice(1).toLowerCase(),
  next_due: { due_id: `d-${name}`, date: '2026-10-12', amount: '6000.00', days_left: -2, status, payable: true },
  primary_action: primary, allowed_actions: ['view', 'end_stay', ...(primary === 'view' ? [] : [primary])] as AdminStayRow['allowed_actions'],
  action_due_id: `d-${name}`,
  action_due: { due_id: `d-${name}`, period_start: '2026-10-12', period_end: '2026-11-11', period_label: '12 Oct – 11 Nov', due_date: '2026-10-12', amount: '6000.00' },
  receipt_payment_id: null, void_due_id: null, last_payment: null, ...over,
});

const page = (rows: AdminStayRow[], over: Partial<AdminStaysPage> = {}): AdminStaysPage => ({
  count: rows.length, next: null, previous: null, results: rows,
  totals: { active_stays: 38, overdue: { amount: '12000.00', count: 2 }, due_this_week: { amount: '42000.00', count: 7 },
    collected_this_month: { amount: '186000.00', stays_paid: 31, stays_total: 38 } },
  tab_counts: { all: 38, overdue: 2, due_this_week: 7, paid: 29 },
  hostels: [{ id: 'h1', name: 'Sample PG', locality: 'Dilsukhnagar' }], ...over,
});

const rows = () => [
  row('Student A', 'OVERDUE', 'record_payment'),
  row('Student C', 'PAYABLE', 'send_reminder', { needs_review: true }),
  row('Student E', 'SCHEDULED', 'view'),
  row('Student F', 'PAID', 'receipt', {
    allowed_actions: ['view', 'receipt', 'void', 'end_stay'], void_due_id: 'd-F', receipt_payment_id: 'p1',
    last_payment: { payment_id: 'p1', receipt_number: 'HH-20261005-ABC123', amount: '6500.00', paid_at: '2026-10-05T11:30:00+05:30', method: 'CASH', source: 'OFFLINE_OWNER' } }),
];

beforeEach(() => {
  vi.clearAllMocks();
  api.stayService.getAdminStays.mockResolvedValue(page(rows()));
});

describe('the Stays and rent page (the AdminDues board)', () => {
  it('shows the four totals the server worked out', async () => {
    renderWithQueryClient(<StaysPage />);

    expect(await screen.findByText('₹1,86,000')).toBeInTheDocument();
    expect(screen.getByText('31 of 38 stays')).toBeInTheDocument();
    expect(screen.getByText('₹42,000')).toBeInTheDocument();
    expect(screen.getByText('7 stays')).toBeInTheDocument();
    expect(screen.getByText('₹12,000')).toBeInTheDocument();
    expect(screen.getByText('2 stays')).toBeInTheDocument();
    expect(screen.getByText('38')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Stays and dues' })).toBeInTheDocument();
    expect(screen.getByText('See who has paid, who is due soon and who is overdue.')).toBeInTheDocument();
  });

  it('shows the tabs with their counts and asks the server for a tab\'s rows', async () => {
    renderWithQueryClient(<StaysPage />);
    await screen.findByText('Student A');
    expect(screen.getByRole('tab', { name: 'Overdue 2' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Due this week 7' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Paid 29' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Overdue 2' }));

    await waitFor(() => expect(api.stayService.getAdminStays).toHaveBeenLastCalledWith(expect.objectContaining({ overdue: true, page: 1 })));
    fireEvent.click(screen.getByRole('tab', { name: 'Due this week 7' }));
    await waitFor(() => expect(api.stayService.getAdminStays).toHaveBeenLastCalledWith(expect.objectContaining({ due_this_week: true })));
  });

  it('shows each row with the action for its status', async () => {
    renderWithQueryClient(<StaysPage />);
    await screen.findByText('Student A');

    expect(screen.getByRole('button', { name: 'Record payment for Student A' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send reminder for Student C' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'View for Student E' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Receipt for Student F' })).toBeInTheDocument();
    const rowsText = screen.getAllByRole('row').map((r) => (r.textContent ?? '').toLowerCase());
    for (const [name, status] of [['student a', 'overdue'], ['student c', 'payable'], ['student e', 'scheduled'], ['student f', 'paid']]) {
      expect(rowsText.some((t) => t.includes(name) && t.includes(status)), `${name} ${status}`).toBe(true);
    }
    expect(screen.getAllByText('Room 101, Bed A').length).toBe(4);
  });

  it('marks a stay that needs review', async () => {
    renderWithQueryClient(<StaysPage />);
    await screen.findByText('Student C');
    expect(screen.getAllByText('Needs review')).toHaveLength(1);

    fireEvent.click(screen.getByLabelText('Needs review only'));
    await waitFor(() => expect(api.stayService.getAdminStays).toHaveBeenLastCalledWith(expect.objectContaining({ needs_review: true })));
  });

  it('Send reminder uses the existing endpoint for that rent and says so', async () => {
    api.stayService.sendReminder.mockResolvedValue({ status: 'queued' });
    renderWithQueryClient(<StaysPage />);
    await screen.findByText('Student C');

    fireEvent.click(screen.getByRole('button', { name: 'Send reminder for Student C' }));

    await waitFor(() => expect(api.stayService.sendReminder).toHaveBeenCalledWith('d-Student C'));
    expect(await screen.findByText('Reminder queued for Student C.')).toBeInTheDocument();
  });

  it('shows the server\'s reason when a reminder is refused', async () => {
    api.stayService.sendReminder.mockRejectedValue(httpError(429, { code: 'REMINDER_ALREADY_SENT', message: 'A reminder was already sent for this rent today.', error: 'A reminder was already sent for this rent today.' }));
    renderWithQueryClient(<StaysPage />);
    await screen.findByText('Student C');

    fireEvent.click(screen.getByRole('button', { name: 'Send reminder for Student C' }));

    expect(await screen.findByText(/already sent/i)).toBeInTheDocument();
  });

  it('Record payment opens the modal for that rent', async () => {
    renderWithQueryClient(<StaysPage />);
    await screen.findByText('Student A');

    fireEvent.click(screen.getByRole('button', { name: 'Record payment for Student A' }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Record offline payment')).toBeInTheDocument();
    expect(within(dialog).getByText('12 Oct – 11 Nov')).toBeInTheDocument();
  });

  it('End stay explains that the bed is released and future rent is cancelled, and asks before it ends', async () => {
    api.stayService.endStay.mockResolvedValue({});
    renderWithQueryClient(<StaysPage />);
    await screen.findByText('Student E');

    fireEvent.click(screen.getByRole('button', { name: 'End stay for Student E' }));

    expect(await screen.findByText('End this stay?')).toBeInTheDocument();
    expect(screen.getByText(/the bed is released/i)).toBeInTheDocument();
    expect(screen.getByText(/future rent that is not yet due is cancelled/i)).toBeInTheDocument();
    expect(api.stayService.endStay).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'End stay' }));
    await waitFor(() => expect(api.stayService.endStay).toHaveBeenCalledWith('s-Student E'));
  });

  it('the Receipt button shows what was paid, and an offline payment offers Void', async () => {
    renderWithQueryClient(<StaysPage />);
    await screen.findByText('Student F');

    fireEvent.click(screen.getByRole('button', { name: 'Receipt for Student F' }));
    expect(await screen.findByText('HH-20261005-ABC123')).toBeInTheDocument();
    expect(screen.getByText('Recorded by owner')).toBeInTheDocument();
    expect(screen.getByText('Cash')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));

    fireEvent.click(screen.getByRole('button', { name: 'Void payment for Student F' }));
    expect(await screen.findByRole('heading', { name: 'Void this payment' })).toBeInTheDocument();
  });

  it('links to the billing rule of the hostel', async () => {
    renderWithQueryClient(<StaysPage />);
    await screen.findByText('Student A');
    expect(screen.getByRole('link', { name: 'Billing rule' })).toHaveAttribute('href', '/stays/billing?hostel=h1');
  });

  it('says there are no stays only when there really are none, and shows a Retry when loading fails', async () => {
    api.stayService.getAdminStays.mockResolvedValueOnce(page([], { count: 0 }));
    const first = renderWithQueryClient(<StaysPage />);
    expect(await screen.findByText('No stays in this view')).toBeInTheDocument();
    first.unmount();

    api.stayService.getAdminStays.mockRejectedValueOnce(httpError(500, { detail: 'oops' })).mockResolvedValue(page(rows()));
    renderWithQueryClient(<StaysPage />);
    expect(await screen.findByText(/could not load stays and dues/i)).toBeInTheDocument();
    expect(screen.queryByText('No stays in this view')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(await screen.findByText('Student A')).toBeInTheDocument();
  });

  it('pages through the list', async () => {
    api.stayService.getAdminStays.mockResolvedValue(page(rows(), { count: 60, next: 'x' }));
    renderWithQueryClient(<StaysPage />);
    await screen.findByText('Student A');
    expect(screen.getByText('Showing 1–4 of 60')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(api.stayService.getAdminStays).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, page_size: 25 })));
  });
});
