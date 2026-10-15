'use client';

import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  bookingService,
  paymentService,
  residentService,
  noticeService,
  hostelService,
  roomService,
} from '@/services/api';
import { useAuth } from '@/contexts/AuthContext';
import { unwrapList, unwrapObject, unwrapPage, type Page } from '@/services/unwrap';
import type { DashboardStats, ActivityItem, Booking, Payment, Resident, Notice } from '@/types';

/**
 * The one place pages get their data. Every hook reads the server's reply through the unwrap helpers
 * (so a { count, results } reply is never mistaken for an empty list) and gives each kind of data its
 * own query key (so two pages can never overwrite each other's cache with a different shape).
 * A failed request is an error the page shows with a Retry, never an empty list.
 */

export const queryKeys = {
  dashboardStats:    ['dashboard', 'stats'] as const,
  recentActivity:    ['dashboard', 'activity'] as const,
  pendingBookings:   ['bookings', 'pending'] as const,
  recentBookings:    ['bookings', 'recent'] as const,
  bookings:          (paymentMode?: string) => ['bookings', 'all', { paymentMode }] as const,
  payments:          (status?: string)      => ['payments', { status }] as const,
  residents:         ['residents'] as const,
  notices:           ['notices'] as const,
  hostels:           ['hostels'] as const,
  rooms:             (hostelId: string) => ['rooms', hostelId] as const,
};

const PAGE_SIZE = 25;

/** Owner data is only requested once there is a signed-in owner, so a logged-out visitor sends nothing. */
function useSignedIn(): boolean {
  const { isReady, isAuthenticated } = useAuth();
  return isReady && isAuthenticated;
}


/** The rows of every page loaded so far, and the server's total. */
export function flattenPages<T>(pages: Page<T>[] | undefined): { items: T[]; total: number } {
  const list = pages ?? [];
  return { items: list.flatMap((p) => p.items), total: list.length ? list[list.length - 1].count : 0 };
}

// ─── Dashboard ────────────────────────────────────────────────────────────

export function useDashboardStats() {
  const signedIn = useSignedIn();
  return useQuery({
    enabled: signedIn,
    queryKey: queryKeys.dashboardStats,
    queryFn: async (): Promise<DashboardStats> => unwrapObject<DashboardStats>(await hostelService.getDashboardStats()),
  });
}

export function useRecentActivity() {
  const signedIn = useSignedIn();
  return useQuery({
    enabled: signedIn,
    queryKey: queryKeys.recentActivity,
    queryFn: async (): Promise<ActivityItem[]> => unwrapList<ActivityItem>(await hostelService.getRecentActivity()),
  });
}

// ─── Bookings ─────────────────────────────────────────────────────────────

/** The requests waiting for an answer, for the dashboard's quick actions: the server filters, not the page. */
export function usePendingBookings() {
  const signedIn = useSignedIn();
  return useQuery({
    enabled: signedIn,
    queryKey: queryKeys.pendingBookings,
    queryFn: async (): Promise<Booking[]> =>
      unwrapList<Booking>(await bookingService.getBookings({ status: 'pending', page_size: 10 })),
  });
}

/** The 100 newest bookings, for the dashboard's volume heatmap (a full-year count would need its own server total). */
export function useRecentBookings() {
  const signedIn = useSignedIn();
  return useQuery({
    enabled: signedIn,
    queryKey: queryKeys.recentBookings,
    queryFn: async (): Promise<Booking[]> => unwrapList<Booking>(await bookingService.getBookings({ page_size: 100 })),
  });
}

/** Every booking, a page at a time. `fetchNextPage` is the "Load more" button. */
export function useBookings(paymentMode?: 'offline' | 'online') {
  const signedIn = useSignedIn();
  return useInfiniteQuery({
    enabled: signedIn,
    queryKey: queryKeys.bookings(paymentMode),
    initialPageParam: 1,
    queryFn: async ({ pageParam }): Promise<Page<Booking>> =>
      unwrapPage<Booking>(await bookingService.getBookings({ payment_mode: paymentMode, page: pageParam, page_size: PAGE_SIZE })),
    getNextPageParam: (last, all) => (last.next ? all.length + 1 : undefined),
  });
}

export function useBookingActions() {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['bookings'] });
    qc.invalidateQueries({ queryKey: queryKeys.dashboardStats });
    qc.invalidateQueries({ queryKey: queryKeys.recentActivity });
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
  const signedIn = useSignedIn();
  return useQuery({
    enabled: signedIn,
    queryKey: queryKeys.payments(status),
    queryFn: async (): Promise<Page<Payment>> =>
      unwrapPage<Payment>(await paymentService.getPayments({ status, page_size: 100 })),
  });
}

// ─── Residents ────────────────────────────────────────────────────────────

export function useResidents() {
  const signedIn = useSignedIn();
  return useInfiniteQuery({
    enabled: signedIn,
    queryKey: queryKeys.residents,
    initialPageParam: 1,
    queryFn: async ({ pageParam }): Promise<Page<Resident>> =>
      unwrapPage<Resident>(await residentService.getResidents({ page: pageParam, page_size: PAGE_SIZE })),
    getNextPageParam: (last, all) => (last.next ? all.length + 1 : undefined),
  });
}

export function useResidentActions() {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['residents'] });
    qc.invalidateQueries({ queryKey: queryKeys.dashboardStats });
  };
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
  const signedIn = useSignedIn();
  return useInfiniteQuery({
    enabled: signedIn,
    queryKey: queryKeys.notices,
    initialPageParam: 1,
    queryFn: async ({ pageParam }): Promise<Page<Notice>> =>
      unwrapPage<Notice>(await noticeService.getNotices({ page: pageParam, page_size: PAGE_SIZE })),
    getNextPageParam: (last, all) => (last.next ? all.length + 1 : undefined),
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
  const signedIn = useSignedIn();
  return useQuery({
    enabled: signedIn,
    queryKey: queryKeys.hostels,
    queryFn: async (): Promise<any[]> => unwrapList<any>(await hostelService.getHostels()),
  });
}

export function useRooms(hostelId: string | null) {
  const signedIn = useSignedIn();
  return useQuery({
    queryKey: queryKeys.rooms(hostelId ?? ''),
    enabled: signedIn && !!hostelId,
    queryFn: async (): Promise<any[]> => unwrapList<any>(await roomService.getRooms(hostelId!)),
  });
}
