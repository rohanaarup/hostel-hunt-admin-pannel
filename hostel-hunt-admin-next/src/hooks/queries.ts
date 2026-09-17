'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  bookingService,
  paymentService,
  residentService,
  noticeService,
  hostelService,
  roomService,
} from '@/services/api';
import type { DashboardStats, ActivityItem, Booking, Payment, Resident, Notice } from '@/types';

/**
 * Thin TanStack Query wrappers around the existing service functions.
 * Service internals are untouched — only the consumption layer changes.
 *
 * Query keys are centralized so mutations can invalidate them precisely.
 */

export const queryKeys = {
  dashboardStats:    ['dashboard', 'stats'] as const,
  recentActivity:    ['dashboard', 'activity'] as const,
  bookings:          (paymentMode?: string) => ['bookings', { paymentMode }] as const,
  payments:          (status?: string)        => ['payments', { status }] as const,
  paymentSummary:    ['payments', 'summary'] as const,
  residents:         ['residents'] as const,
  notices:           ['notices'] as const,
  hostels:           ['hostels'] as const,
  rooms:             (hostelId: string) => ['rooms', hostelId] as const,
};

// ─── Dashboard ────────────────────────────────────────────────────────────

export function useDashboardStats() {
  return useQuery({
    queryKey: queryKeys.dashboardStats,
    queryFn: async (): Promise<DashboardStats | null> => {
      const res = await hostelService.getDashboardStats();
      return (res?.data ?? res) as DashboardStats | null;
    },
  });
}

export function useRecentActivity() {
  return useQuery({
    queryKey: queryKeys.recentActivity,
    queryFn: async (): Promise<ActivityItem[]> => {
      const res = await hostelService.getRecentActivity();
      const list = (res?.data ?? res) as ActivityItem[] | undefined;
      return Array.isArray(list) ? list : [];
    },
  });
}

// ─── Bookings ─────────────────────────────────────────────────────────────

function unwrap<T>(res: any): T[] {
  const list = res?.data ?? res?.results ?? res;
  return Array.isArray(list) ? list : [];
}

export function useBookings(paymentMode?: 'offline' | 'online') {
  return useQuery({
    queryKey: queryKeys.bookings(paymentMode),
    queryFn: async (): Promise<Booking[]> => {
      const res = await bookingService.getBookings(paymentMode);
      return unwrap<Booking>(res);
    },
  });
}

export function useBookingActions() {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['bookings'] });
    qc.invalidateQueries({ queryKey: queryKeys.dashboardStats });
  };
  return {
    approve: useMutation({ mutationFn: (id: string) => bookingService.approveBooking(id), onSuccess: invalidate }),
    reject:  useMutation({ mutationFn: (id: string) => bookingService.rejectBooking(id),  onSuccess: invalidate }),
    verify:  useMutation({ mutationFn: (id: string) => bookingService.verifyPayment(id),  onSuccess: invalidate }),
    markPaid:useMutation({ mutationFn: (id: string) => bookingService.markBookingPaid(id),onSuccess: invalidate }),
  };
}

// ─── Payments ─────────────────────────────────────────────────────────────

export function usePayments(status?: string) {
  return useQuery({
    queryKey: queryKeys.payments(status),
    queryFn: async (): Promise<Payment[]> => {
      const res = await paymentService.getPayments(status);
      return unwrap<Payment>(res);
    },
  });
}

export function usePaymentSummary() {
  return useQuery({
    queryKey: queryKeys.paymentSummary,
    queryFn: async () => {
      const res = await paymentService.getSummary();
      return (res?.data ?? res) ?? null;
    },
  });
}

export function usePaymentActions() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['payments'] });
  return {
    markPaid: useMutation({
      mutationFn: ({ id, amountPaid }: { id: string; amountPaid?: number }) =>
        paymentService.markPaymentPaid(id, amountPaid),
      onSuccess: invalidate,
    }),
    create: useMutation({
      mutationFn: (data: any) => paymentService.createPayment(data),
      onSuccess: invalidate,
    }),
  };
}

// ─── Residents ────────────────────────────────────────────────────────────

export function useResidents() {
  return useQuery({
    queryKey: queryKeys.residents,
    queryFn: async (): Promise<Resident[]> => {
      const res = await residentService.getResidents();
      return unwrap<Resident>(res);
    },
  });
}

export function useResidentActions() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['residents'] });
  return {
    markVacated: useMutation({
      mutationFn: (id: string) => residentService.markResidentVacated(id),
      onSuccess: invalidate,
    }),
    create: useMutation({
      mutationFn: (data: any) => residentService.createResident(data),
      onSuccess: invalidate,
    }),
  };
}

// ─── Notices ──────────────────────────────────────────────────────────────

export function useNotices() {
  return useQuery({
    queryKey: queryKeys.notices,
    queryFn: async (): Promise<Notice[]> => {
      const res = await noticeService.getNotices();
      return unwrap<Notice>(res);
    },
  });
}

export function useNoticeActions() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['notices'] });
  return {
    create: useMutation({
      mutationFn: (data: { title: string; body: string; hostel: string }) =>
        noticeService.createNotice(data),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: (id: string) => noticeService.deleteNotice(id),
      onSuccess: invalidate,
    }),
  };
}

// ─── Hostels & Rooms ──────────────────────────────────────────────────────

export function useHostels() {
  return useQuery({
    queryKey: queryKeys.hostels,
    queryFn: async () => {
      const res = await hostelService.getHostels();
      const list = res?.data ?? res?.results ?? res;
      return Array.isArray(list) ? list : [];
    },
  });
}

export function useRooms(hostelId: string | null) {
  return useQuery({
    queryKey: queryKeys.rooms(hostelId ?? ''),
    enabled: !!hostelId,
    queryFn: async () => {
      const res = await roomService.getRooms(hostelId!);
      const list = res?.data ?? res?.results ?? res;
      return Array.isArray(list) ? list : [];
    },
  });
}
