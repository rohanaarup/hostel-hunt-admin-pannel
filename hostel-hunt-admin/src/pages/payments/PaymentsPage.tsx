import React, { useState } from 'react';
import { DashboardLayout } from '../../components/common/DashboardLayout';
import { useTheme } from '../../contexts/ThemeContext';
import type { Payment, PaymentStatus } from '../../types';

const MOCK_PAYMENTS: Payment[] = [
  { payment_id: 'pay_001', booking_id: 'bkg_003', hostel_id: 'h1', user_name: 'Priya Sharma', room_name: 'Room 101 (Single)', amount: 6500, status: 'completed', method: 'upi', transaction_ref: 'UPI202606010001', paid_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(), created_at: '' },
  { payment_id: 'pay_002', booking_id: 'bkg_005', hostel_id: 'h1', user_name: 'Mohan Das', room_name: 'Room 108 (Double)', amount: 8500, status: 'completed', method: 'bank_transfer', transaction_ref: 'NEFT20260610X', paid_at: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString(), created_at: '' },
  { payment_id: 'pay_003', booking_id: 'bkg_001', hostel_id: 'h1', user_name: 'Rahul Verma', room_name: 'Room 204 (Double)', amount: 7500, status: 'pending', method: 'upi', transaction_ref: null, paid_at: null, created_at: new Date(Date.now() - 1000 * 60 * 12).toISOString() },
  { payment_id: 'pay_004', booking_id: 'bkg_002', hostel_id: 'h1', user_name: 'Amit Kumar', room_name: 'Room 305 (Triple)', amount: 5500, status: 'pending', method: 'card', transaction_ref: null, paid_at: null, created_at: new Date(Date.now() - 1000 * 60 * 90).toISOString() },
  { payment_id: 'pay_005', booking_id: 'bkg_X1', hostel_id: 'h1', user_name: 'Vikram Singh', room_name: 'Room 202 (Double)', amount: 7000, status: 'failed', method: 'card', transaction_ref: 'CARD_FAIL_001', paid_at: null, created_at: new Date(Date.now() - 1000 * 60 * 60 * 12).toISOString() },
  { payment_id: 'pay_006', booking_id: 'bkg_X2', hostel_id: 'h1', user_name: 'Neha Joshi', room_name: 'Room 110 (Single)', amount: 6000, status: 'refunded', method: 'upi', transaction_ref: 'REFUND_UPI_001', paid_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), created_at: '' },
];

const STATUS_STYLES: Record<PaymentStatus, { cls: string; label: string }> = {
  completed: { cls: 'bg-green-500/10 text-green-400 border-green-500/20', label: 'Completed' },
  pending: { cls: 'bg-amber-500/10 text-amber-400 border-amber-500/20', label: 'Pending' },
  failed: { cls: 'bg-red-500/10 text-red-400 border-red-500/20', label: 'Failed' },
  refunded: { cls: 'bg-blue-500/10 text-blue-400 border-blue-500/20', label: 'Refunded' },
};

const METHOD_LABELS: Record<string, { icon: string; label: string }> = {
  upi: { icon: '📱', label: 'UPI' },
  card: { icon: '💳', label: 'Card' },
  bank_transfer: { icon: '🏦', label: 'NEFT/RTGS' },
  cash: { icon: '💵', label: 'Cash' },
};

export const PaymentsPage: React.FC = () => {
  const { theme } = useTheme();
  const [filter, setFilter] = useState<PaymentStatus | 'all'>('all');

  const cardBg = theme === 'dark' ? 'bg-[#1A1A1A]' : 'bg-white';
  const cardBorder = theme === 'dark' ? 'border-[#2A2A2A]' : 'border-[#E8E5E0]';
  const textSub = theme === 'dark' ? 'text-[#9A9690]' : 'text-[#6B6B6B]';
  const rowHover = theme === 'dark' ? 'hover:bg-[#FFFFFF05]' : 'hover:bg-slate-50';

  const filtered = filter === 'all' ? MOCK_PAYMENTS : MOCK_PAYMENTS.filter(p => p.status === filter);

  const totalRevenue = MOCK_PAYMENTS.filter(p => p.status === 'completed').reduce((s, p) => s + p.amount, 0);
  const pendingAmount = MOCK_PAYMENTS.filter(p => p.status === 'pending').reduce((s, p) => s + p.amount, 0);
  const failedAmount = MOCK_PAYMENTS.filter(p => p.status === 'failed').reduce((s, p) => s + p.amount, 0);
  const refundedAmount = MOCK_PAYMENTS.filter(p => p.status === 'refunded').reduce((s, p) => s + p.amount, 0);

  return (
    <DashboardLayout title="Payments">
      <div className="w-full animate-fade-in-up space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Payments</h1>
          <p className={`${textSub} mt-1 text-sm font-medium`}>Track all transactions and revenue</p>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Total Revenue', amount: totalRevenue, color: '#10B981', icon: '💰' },
            { label: 'Pending', amount: pendingAmount, color: '#F59E0B', icon: '⏳' },
            { label: 'Failed', amount: failedAmount, color: '#EF4444', icon: '❌' },
            { label: 'Refunded', amount: refundedAmount, color: '#3B82F6', icon: '↩' },
          ].map(s => (
            <div key={s.label} className={`${cardBg} border ${cardBorder} rounded-xl p-5 relative overflow-hidden`}>
              <div className="absolute top-0 left-0 w-1 h-full rounded-l-xl" style={{ backgroundColor: s.color }} />
              <div className="pl-2">
                <div className="text-xl mb-2">{s.icon}</div>
                <div className="text-xl font-extrabold text-white">
                  ₹{s.amount.toLocaleString('en-IN')}
                </div>
                <div className={`text-xs font-semibold ${textSub} mt-1`}>{s.label}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Payment table */}
        <div className={`${cardBg} border ${cardBorder} rounded-2xl overflow-hidden`}>
          {/* Filter bar */}
          <div className="flex gap-1 p-4 border-b border-[#2A2A2A] overflow-x-auto">
            {(['all', 'completed', 'pending', 'failed', 'refunded'] as const).map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className={`px-4 py-1.5 rounded-[8px] text-sm font-semibold transition-all whitespace-nowrap capitalize ${
                  filter === f ? 'bg-[#E8571A] text-white' : `${textSub} hover:text-white hover:bg-[#FFFFFF08]`
                }`}>
                {f === 'all' ? 'All Transactions' : f}
              </button>
            ))}
          </div>

          {filtered.length === 0 ? (
            <div className="py-16 text-center">
              <div className="text-4xl mb-3">💰</div>
              <p className={`${textSub} font-medium`}>No transactions in this category</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className={`text-[10px] uppercase tracking-wider font-bold ${textSub} border-b border-[#2A2A2A]`}>
                    <th className="px-5 py-3">Guest / Room</th>
                    <th className="px-5 py-3 hidden sm:table-cell">Method</th>
                    <th className="px-5 py-3">Amount</th>
                    <th className="px-5 py-3 hidden md:table-cell">Transaction Ref</th>
                    <th className="px-5 py-3 hidden md:table-cell">Date</th>
                    <th className="px-5 py-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(pay => {
                    const methodInfo = METHOD_LABELS[pay.method] || { icon: '💵', label: pay.method };
                    const statusInfo = STATUS_STYLES[pay.status];
                    const date = pay.paid_at || pay.created_at;

                    return (
                      <tr key={pay.payment_id} className={`border-b border-[#2A2A2A] last:border-0 ${rowHover} transition-colors`}>
                        <td className="px-5 py-4">
                          <p className="text-white text-sm font-semibold">{pay.user_name}</p>
                          <p className={`${textSub} text-xs`}>{pay.room_name}</p>
                        </td>
                        <td className="px-5 py-4 hidden sm:table-cell">
                          <span className={`${textSub} text-sm flex items-center gap-1.5`}>
                            <span>{methodInfo.icon}</span>
                            {methodInfo.label}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <span className="text-white font-bold">₹{pay.amount.toLocaleString('en-IN')}</span>
                        </td>
                        <td className={`px-5 py-4 ${textSub} text-xs font-mono hidden md:table-cell`}>
                          {pay.transaction_ref || '—'}
                        </td>
                        <td className={`px-5 py-4 ${textSub} text-xs hidden md:table-cell`}>
                          {date ? new Date(date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}
                        </td>
                        <td className="px-5 py-4">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-[6px] text-[10px] font-bold border ${statusInfo.cls}`}>
                            {statusInfo.label}
                          </span>
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
