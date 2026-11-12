'use client';

import React, { useState } from 'react';
import Modal from '@/components/ui/Modal';
import { useStayActions } from '@/hooks/queries';
import type { AdminStayRow } from '@/types';
import { METHODS, NOTE_MAX, nowFields, reasonOf, recordBody, validateRecord, type RecordErrors, type RecordForm } from './recordPayment';

/**
 * The AdminRecord board: record rent the student paid outside the app. The period and the amount are the due's own and
 * cannot be edited; the owner says when it was paid, how, and adds a reference note. The server checks everything again.
 */

const money = (value: string) => `₹${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;

const box = 'w-full min-h-[44px] rounded-[10px] px-3.5 py-2.5 text-sm font-medium outline-none border';
const boxStyle: React.CSSProperties = {
  background: 'var(--color-surface)', color: 'var(--color-text-primary)', borderColor: 'var(--color-border)',
};

interface Props {
  isOpen: boolean;
  row: AdminStayRow | null;
  onClose: () => void;
  onSaved?: () => void;
}

export default function RecordPaymentModal({ isOpen, row, onClose, onSaved }: Props) {
  const { record } = useStayActions();
  const [form, setForm] = useState<RecordForm>(() => ({ ...nowFields(), method: '', note: '' }));
  const [errors, setErrors] = useState<RecordErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);

  if (!isOpen || !row || !row.action_due) return null;
  const due = row.action_due;

  const set = (patch: Partial<RecordForm>) => {
    setForm((current) => ({ ...current, ...patch }));
    setServerError(null);
  };

  const close = () => {
    setForm({ ...nowFields(), method: '', note: '' });
    setErrors({});
    setServerError(null);
    onClose();
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const found = validateRecord(form);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    record.mutate({ dueId: due.due_id, ...recordBody(form) }, {
      onSuccess: () => { onSaved?.(); close(); },
      onError: (error) => setServerError(reasonOf(error)),
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={close} persistent className="w-full max-w-[520px]">
      <form onSubmit={submit} aria-labelledby="record-title" noValidate
        className="rounded-2xl p-6 shadow-2xl space-y-4" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
        <div>
          <h2 id="record-title" className="text-lg font-bold" style={{ color: 'var(--color-text-primary)' }}>Record offline payment</h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
            {row.student_name} · {row.room_label}, {row.bed_label}
          </p>
        </div>

        <dl className="grid grid-cols-2 gap-4">
          <div>
            <dt className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>Rent period</dt>
            <dd className="mt-1 font-semibold" style={{ color: 'var(--color-text-primary)' }}>{due.period_label}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>Amount</dt>
            <dd className="mt-1 font-semibold" style={{ color: 'var(--color-text-primary)' }}>{money(due.amount)}</dd>
          </div>
        </dl>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="paid-date" className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>Paid on</label>
            <input id="paid-date" type="date" className={box + ' mt-1'} style={boxStyle} value={form.date}
              aria-invalid={Boolean(errors.date)} aria-describedby={errors.date ? 'paid-error' : undefined}
              onChange={(e) => set({ date: e.target.value })} />
          </div>
          <div>
            <label htmlFor="paid-time" className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>Time</label>
            <input id="paid-time" type="time" className={box + ' mt-1'} style={boxStyle} value={form.time}
              aria-invalid={Boolean(errors.time)} onChange={(e) => set({ time: e.target.value })} />
          </div>
        </div>
        {errors.date || errors.time ? (
          <p id="paid-error" role="alert" className="text-xs" style={{ color: 'var(--color-error)' }}>{errors.date || errors.time}</p>
        ) : null}

        <fieldset>
          <legend className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>How was it paid</legend>
          <div role="radiogroup" aria-label="How was it paid" className="grid grid-cols-3 gap-2 mt-2">
            {METHODS.map((m) => {
              const on = form.method === m.value;
              return (
                <button key={m.value} type="button" role="radio" aria-checked={on} onClick={() => set({ method: m.value })}
                  className="min-h-[44px] rounded-[10px] text-sm font-semibold px-2"
                  style={on
                    ? { background: 'var(--color-primary-light)', border: '2px solid var(--color-primary)', color: 'var(--color-text-primary)' }
                    : { background: 'var(--color-surface)', border: '2px solid var(--color-border)', color: 'var(--color-text-primary)' }}>
                  {m.label}
                </button>
              );
            })}
          </div>
          {errors.method ? <p role="alert" className="text-xs mt-1" style={{ color: 'var(--color-error)' }}>{errors.method}</p> : null}
        </fieldset>

        <div>
          <label htmlFor="paid-note" className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>Reference note</label>
          <textarea id="paid-note" rows={2} maxLength={NOTE_MAX + 50} className={box + ' mt-1 resize-none'} style={boxStyle} value={form.note}
            placeholder="Received in person, receipt book no. 214" aria-invalid={Boolean(errors.note)}
            onChange={(e) => set({ note: e.target.value })} />
          {errors.note ? <p role="alert" className="text-xs mt-1" style={{ color: 'var(--color-error)' }}>{errors.note}</p> : null}
        </div>

        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          The student sees this as paid with the source “Recorded by owner”. The entry is logged with your name and can be voided later.
        </p>

        {serverError ? <p role="alert" className="text-sm" style={{ color: 'var(--color-error)' }}>{serverError}</p> : null}

        <div className="flex gap-3 pt-1">
          <button type="button" onClick={close} disabled={record.isPending}
            className="flex-1 min-h-[44px] rounded-[10px] text-sm font-medium border" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}>
            Cancel
          </button>
          <button type="submit" disabled={record.isPending}
            className="flex-1 min-h-[44px] rounded-[10px] text-sm font-semibold disabled:opacity-60"
            style={{ background: 'var(--color-primary)', color: 'var(--color-text-inverse)' }}>
            {record.isPending ? 'Saving…' : 'Save payment'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
