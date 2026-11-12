import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { httpError, renderWithQueryClient } from '@/test-utils';
import type { AdminStayRow } from '@/types';
import { nowFields, paidAtOf, recordBody, validateRecord } from './recordPayment';

const api = vi.hoisted(() => ({
  stayService: { recordPayment: vi.fn(), voidPayment: vi.fn(), sendReminder: vi.fn(), endStay: vi.fn() },
}));
vi.mock('@/services/api', () => api);

import RecordPaymentModal from './RecordPaymentModal';
import VoidPaymentModal from './VoidPaymentModal';

const row = (over: Partial<AdminStayRow> = {}): AdminStayRow => ({
  id: 's1', student_name: 'Student A', hostel_id: 'h1', hostel_name: 'Sample PG', room_label: 'Room 101', bed_label: 'Bed A',
  rent_amount: '6000.00', join_date: '2026-06-18', stay_status: 'ACTIVE', needs_review: false, status: 'OVERDUE', status_label: 'Overdue',
  next_due: { due_id: 'd1', date: '2026-10-12', amount: '6000.00', days_left: -2, status: 'OVERDUE', payable: true },
  primary_action: 'record_payment', allowed_actions: ['view', 'record_payment', 'send_reminder', 'end_stay'], action_due_id: 'd1',
  action_due: { due_id: 'd1', period_start: '2026-10-12', period_end: '2026-11-11', period_label: '12 Oct – 11 Nov', due_date: '2026-10-12', amount: '6000.00' },
  receipt_payment_id: null, void_due_id: null, last_payment: null, ...over,
});

const yesterday = () => {
  const d = new Date(Date.now() - 24 * 3600 * 1000);
  return nowFields(d);
};
const tomorrow = () => nowFields(new Date(Date.now() + 24 * 3600 * 1000));

describe('the record-payment checks', () => {
  const ok = { ...yesterday(), method: 'CASH' as const, note: 'Receipt book 214' };

  it('accepts a past time, a method and a note', () => {
    expect(validateRecord(ok)).toEqual({});
  });

  it('refuses a time in the future', () => {
    expect(validateRecord({ ...ok, ...tomorrow() }).date).toMatch(/future/);
    const now = new Date('2026-10-14T10:00:00');
    expect(validateRecord({ date: '2026-10-14', time: '10:01', method: 'CASH', note: 'x' }, now).date).toMatch(/future/);
    expect(validateRecord({ date: '2026-10-14', time: '10:00', method: 'CASH', note: 'x' }, now)).toEqual({});
  });

  it('needs a date, a time, a method and a note (not only spaces, at most 200 characters)', () => {
    expect(validateRecord({ ...ok, date: '' }).date).toBeTruthy();
    expect(validateRecord({ ...ok, time: '' }).time).toBeTruthy();
    expect(validateRecord({ ...ok, method: '' }).method).toBeTruthy();
    expect(validateRecord({ ...ok, note: '   ' }).note).toBeTruthy();
    expect(validateRecord({ ...ok, note: 'x'.repeat(201) }).note).toMatch(/200/);
  });

  it('builds the request body from the fields', () => {
    const body = recordBody({ date: '2026-10-14', time: '11:30', method: 'BANK_TRANSFER', note: '  UTR 123  ' });
    expect(body.method).toBe('BANK_TRANSFER');
    expect(body.reference_note).toBe('UTR 123');
    expect(new Date(body.paid_at).getTime()).toBe(paidAtOf('2026-10-14', '11:30')!.getTime());
    expect(paidAtOf('nope', '11:30')).toBeNull();
  });
});

describe('the record-payment modal (the AdminRecord board)', () => {
  beforeEach(() => { vi.clearAllMocks(); api.stayService.recordPayment.mockResolvedValue({}); });
  afterEach(() => vi.restoreAllMocks());

  const open = (onClose = vi.fn(), onSaved = vi.fn()) => {
    renderWithQueryClient(<RecordPaymentModal isOpen row={row()} onClose={onClose} onSaved={onSaved} />);
    return { onClose, onSaved };
  };

  it('shows the student, the due\'s own period and amount, and the board\'s helper text', () => {
    open();

    expect(screen.getByRole('heading', { name: 'Record offline payment' })).toBeInTheDocument();
    expect(screen.getByText('Student A · Room 101, Bed A')).toBeInTheDocument();
    expect(screen.getByText('12 Oct – 11 Nov')).toBeInTheDocument();
    expect(screen.getByText('₹6,000')).toBeInTheDocument();
    for (const name of ['Cash', 'Bank transfer', 'UPI direct']) expect(screen.getByRole('radio', { name })).toBeInTheDocument();
    expect(screen.getByText(/the student sees this as paid with the source “recorded by owner”/i)).toBeInTheDocument();
    expect(screen.getByText(/can be voided later/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/amount/i)).not.toBeInTheDocument(); // not editable
  });

  it('blocks a payment time in the future and a missing method or note, and sends nothing', async () => {
    open();
    fireEvent.change(screen.getByLabelText('Paid on'), { target: { value: tomorrow().date } });

    fireEvent.click(screen.getByRole('button', { name: 'Save payment' }));

    expect(await screen.findByText('The payment time cannot be in the future.')).toBeInTheDocument();
    expect(screen.getByText('Choose how it was paid.')).toBeInTheDocument();
    expect(screen.getByText(/add a reference note/i)).toBeInTheDocument();
    expect(api.stayService.recordPayment).not.toHaveBeenCalled();
  });

  it('records the payment: the due, the time, the method and the note', async () => {
    const { onSaved, onClose } = open();
    const when = yesterday();
    fireEvent.change(screen.getByLabelText('Paid on'), { target: { value: when.date } });
    fireEvent.change(screen.getByLabelText('Time'), { target: { value: when.time } });
    fireEvent.click(screen.getByRole('radio', { name: 'Cash' }));
    fireEvent.change(screen.getByLabelText('Reference note'), { target: { value: 'Received in person, receipt book no. 214' } });

    fireEvent.click(screen.getByRole('button', { name: 'Save payment' }));

    await waitFor(() => expect(api.stayService.recordPayment).toHaveBeenCalledTimes(1));
    const [dueId, body] = api.stayService.recordPayment.mock.calls[0];
    expect(dueId).toBe('d1');
    expect(body).toMatchObject({ method: 'CASH', reference_note: 'Received in person, receipt book no. 214' });
    expect(new Date(body.paid_at).getTime()).toBe(paidAtOf(when.date, when.time)!.getTime());
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(onClose).toHaveBeenCalled();
  });

  it('shows the server\'s reason when it refuses (for example the rent was already paid) and stays open', async () => {
    api.stayService.recordPayment.mockRejectedValue(httpError(409, { code: 'DUE_PAID', message: 'This rent is already paid.', error: 'This rent is already paid.' }));
    const { onClose } = open();
    fireEvent.click(screen.getByRole('radio', { name: 'UPI direct' }));
    fireEvent.change(screen.getByLabelText('Reference note'), { target: { value: 'GPay ref 9' } });

    fireEvent.click(screen.getByRole('button', { name: 'Save payment' }));

    expect(await screen.findByText(/already paid/i)).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('Cancel closes without sending anything', () => {
    const { onClose } = open();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onClose).toHaveBeenCalled();
    expect(api.stayService.recordPayment).not.toHaveBeenCalled();
  });

  it('is labelled for a screen reader (a dialog with a title, labelled fields and alerts)', () => {
    open();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('radiogroup', { name: 'How was it paid' })).toBeInTheDocument();
    expect(screen.getByLabelText('Reference note')).toBeInTheDocument();
  });
});

describe('the void modal', () => {
  beforeEach(() => { vi.clearAllMocks(); api.stayService.voidPayment.mockResolvedValue({}); });

  it('asks for a reason and voids the offline payment', async () => {
    const onClose = vi.fn();
    renderWithQueryClient(<VoidPaymentModal isOpen row={row({ void_due_id: 'd9' })} onClose={onClose} />);

    fireEvent.click(screen.getByRole('button', { name: 'Void payment' }));
    expect(await screen.findByText('Say why you are voiding this payment.')).toBeInTheDocument();
    expect(api.stayService.voidPayment).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Wrong student' } });
    fireEvent.click(screen.getByRole('button', { name: 'Void payment' }));

    await waitFor(() => expect(api.stayService.voidPayment).toHaveBeenCalledWith('d9', 'Wrong student'));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('shows nothing for a row with no offline payment to void', () => {
    renderWithQueryClient(<VoidPaymentModal isOpen row={row({ void_due_id: null })} onClose={vi.fn()} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
