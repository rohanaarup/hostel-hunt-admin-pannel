'use client';

import React, { useState } from 'react';
import Modal from '@/components/ui/Modal';
import { useStayActions } from '@/hooks/queries';
import type { AdminStayRow } from '@/types';
import { REASON_MAX, reasonOf } from './recordPayment';

/** Take back a payment the owner recorded by hand. An online payment can never be voided here (it needs a refund). */
interface Props {
  isOpen: boolean;
  row: AdminStayRow | null;
  onClose: () => void;
}

export default function VoidPaymentModal({ isOpen, row, onClose }: Props) {
  const { voidPayment } = useStayActions();
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !row || !row.void_due_id) return null;
  const dueId = row.void_due_id;

  const close = () => { setReason(''); setError(null); onClose(); };
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const text = reason.trim();
    if (!text) return setError('Say why you are voiding this payment.');
    if (text.length > REASON_MAX) return setError(`Keep the reason to ${REASON_MAX} characters.`);
    voidPayment.mutate({ dueId, reason: text }, { onSuccess: close, onError: (e) => setError(reasonOf(e)) });
  };

  return (
    <Modal isOpen={isOpen} onClose={close} persistent className="w-full max-w-[460px]">
      <form onSubmit={submit} aria-labelledby="void-title" noValidate className="rounded-2xl p-6 shadow-2xl space-y-4"
        style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
        <div>
          <h2 id="void-title" className="text-lg font-bold" style={{ color: 'var(--color-text-primary)' }}>Void this payment</h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
            {row.student_name} · {row.room_label}, {row.bed_label}. The rent becomes unpaid again. The record is kept and marked as voided.
          </p>
        </div>
        <div>
          <label htmlFor="void-reason" className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>Reason</label>
          <textarea id="void-reason" rows={3} className="w-full rounded-[10px] px-3.5 py-2.5 text-sm border mt-1 resize-none"
            style={{ background: 'var(--color-surface)', color: 'var(--color-text-primary)', borderColor: 'var(--color-border)' }}
            value={reason} onChange={(e) => { setReason(e.target.value); setError(null); }} aria-invalid={Boolean(error)} />
        </div>
        {error ? <p role="alert" className="text-sm" style={{ color: 'var(--color-error)' }}>{error}</p> : null}
        <div className="flex gap-3">
          <button type="button" onClick={close} disabled={voidPayment.isPending}
            className="flex-1 min-h-[44px] rounded-[10px] text-sm font-medium border" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}>
            Cancel
          </button>
          <button type="submit" disabled={voidPayment.isPending}
            className="flex-1 min-h-[44px] rounded-[10px] text-sm font-semibold bg-red-500 text-white disabled:opacity-60">
            {voidPayment.isPending ? 'Voiding…' : 'Void payment'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
