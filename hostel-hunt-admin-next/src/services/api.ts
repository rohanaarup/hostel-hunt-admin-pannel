import axios from 'axios';
import type { AuthUser } from '../types';

// The API address comes from NEXT_PUBLIC_API_URL, set in .env.local for development and in the build
// settings for staging and production. next.config.ts stops the build when it is missing, so a build
// can never quietly talk to the wrong server. (It must be written out like this for Next.js to inline it.)
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL as string;

/** How long any request may take before it counts as failed. */
export const REQUEST_TIMEOUT_MS = 20_000;

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: REQUEST_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add a request interceptor to attach JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

/** Requests to these routes never trigger a token refresh: a 401 there means "wrong credentials". */
const AUTH_ROUTES = /\/auth\/(login|register|send-otp|verify-otp|resend-otp|reset-password|forgot-password|token\/refresh)\//;

/** Where the browser is sent when the session ends. A separate object so a test can replace it. */
export const session = {
  goToLogin() {
    if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
  },
};

/** Forget the saved login and go to the login page (once, and not when already there). */
export function endSession() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('hh_auth_user');
  sessionStorage.removeItem('hh_auth_user');
  session.goToLogin();
}

// One refresh at a time. When several requests get a 401 together (a dashboard fires four), they all
// wait for the same refresh instead of each sending their own.
let refreshInFlight: Promise<string> | null = null;

export function refreshAccessToken(): Promise<string> {
  if (!refreshInFlight) {
    const refresh = localStorage.getItem('refresh_token');
    if (!refresh) {
      // Nothing to refresh with: the same as the server refusing it.
      return Promise.reject(Object.assign(new Error('No refresh token'), { response: { status: 401 } }));
    }
    refreshInFlight = axios
      .post(`${API_BASE_URL}/auth/token/refresh/`, { refresh }, { timeout: REQUEST_TIMEOUT_MS })
      .then(({ data }) => {
        localStorage.setItem('access_token', data.access);
        return data.access as string;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

// Add a response interceptor to handle 401 and refresh tokens automatically
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const status = error.response?.status;
    const isAuthRoute = AUTH_ROUTES.test(originalRequest?.url ?? '');

    if (status === 401 && originalRequest && !originalRequest._retry && !isAuthRoute) {
      originalRequest._retry = true;
      try {
        const access = await refreshAccessToken();
        originalRequest.headers.Authorization = `Bearer ${access}`;
        return api(originalRequest);
      } catch (refreshError) {
        // Only a refresh the server REJECTS ends the session. If the refresh could not be tried (no
        // connection, a timeout, a server that is waking up) the login is kept, and the caller gets
        // that failure, so a bad moment on the network never logs anyone out.
        const refreshStatus = (refreshError as { response?: { status?: number } })?.response?.status;
        if (refreshStatus === 400 || refreshStatus === 401 || refreshStatus === 403) {
          endSession();
          return Promise.reject(error);
        }
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

// Helper methods mirroring the stubs

export const authService = {
  sendOtp: (data: { identifier: string; identifier_type: 'email' | 'phone'; purpose?: string }) =>
    api.post('/auth/send-otp/', data).then(res => res.data),

  verifyOtp: (data: { identifier: string; identifier_type: 'email' | 'phone'; otp: string; purpose?: string }) =>
    api.post('/auth/verify-otp/', data).then(res => res.data),

  register: (data: any) =>
    api.post('/auth/register/', data).then(res => res.data),

  login: (data: any) =>
    api.post('/auth/login/', data).then(res => res.data),

  logout: (refresh_token: string) =>
    api.post('/auth/logout/', { refresh: refresh_token }).then(res => res.data),

  resetPassword: (data: any) =>
    api.post('/auth/reset-password/', data).then(res => res.data),

  getProfile: (): Promise<{ success: boolean, data: AuthUser }> =>
    api.get('/auth/me/').then(res => res.data),
};

export const hostelService = {
  getDashboardStats: () => api.get('/dashboard/stats/').then(res => res.data),
  getRecentActivity: () => api.get('/dashboard/activity/').then(res => res.data),

  createHostel: (data: any) => api.post('/hostels/', data).then(res => res.data),
  updateHostel: (id: string, data: any) => api.put(`/hostels/${id}/`, data).then(res => res.data),
  // The owner's own hostels (the plain list is the public one for students). Up to 50 per page.
  getHostels: () => api.get('/hostels/', { params: { scope: 'mine', page_size: 50 } }).then(res => res.data),
};

export const roomService = {
  // The most the API allows on one page; a hostel with more rooms than this is not expected.
  getRooms: (hostelId: string) =>
    api.get(`/hostels/${hostelId}/rooms/`, { params: { page_size: 100 } }).then(res => res.data),
};

export const bookingService = {
  // Paged: { count, next, previous, results }. Read it with unwrapPage / unwrapList.
  getBookings: (params: { payment_mode?: 'offline' | 'online'; status?: string; page?: number; page_size?: number } = {}) =>
    api.get('/bookings/', { params }).then(res => res.data),
  approveBooking: (id: string) => api.post(`/bookings/${id}/approve/`).then(res => res.data),
  rejectBooking: (id: string) => api.post(`/bookings/${id}/reject/`).then(res => res.data),
  verifyPayment: (id: string) => api.post(`/bookings/${id}/verify/`).then(res => res.data),
  markBookingPaid: (id: string) => api.patch(`/bookings/${id}/mark-paid/`).then(res => res.data),
};

// Online (Razorpay) payments for the signed-in owner's hostels. The backend has no offline rent
// ledger, so there is no create / mark-paid / summary call. `status` is CREATED, PENDING, SUCCESS,
// FAILED or REFUNDED. The response is paginated: { count, next, previous, results }.
export const paymentService = {
  getPayments: (params?: { status?: string; page_size?: number }) =>
    api.get('/payments/admin-list/', { params }).then(res => res.data),
};

export const residentService = {
  getResidents: (params: { page?: number; page_size?: number } = {}) =>
    api.get('/residents/', { params }).then(res => res.data),
  createResident: (data: any) => api.post('/residents/create/', data).then(res => res.data),
  markResidentVacated: (id: string) => api.patch(`/residents/${id}/mark-vacated/`).then(res => res.data),
};

export const noticeService = {
  getNotices: (params: { page?: number; page_size?: number } = {}) =>
    api.get('/notices/', { params }).then(res => res.data),
  createNotice: (data: any) => api.post('/notices/create/', data).then(res => res.data),
  deleteNotice: (id: string) => api.delete(`/notices/${id}/delete/`).then(res => res.data),
};

export const mediaService = {
  upload: (data: any) =>
    api.post('/media/upload/', data).then(res => res.data),

  reorder: (items: any[]) => api.patch('/media/reorder/', { items }).then(res => res.data),
  delete: (id: string) => api.delete(`/media/${id}/`).then(res => res.data),
};

// Cities and localities are chosen from lists kept by staff, so spelling variants cannot multiply.
// include_empty lists every active entry, including ones that have no hostel yet.
export interface City { id: string; name: string; slug: string; state: string; hostel_count: number }
export interface Locality { id: string; name: string; slug: string; hostel_count: number }

export const locationService = {
  getCities: (): Promise<City[]> =>
    api.get('/cities/', { params: { include_empty: true } }).then(res => res.data),
  getLocalities: (citySlug: string): Promise<Locality[]> =>
    api.get(`/cities/${encodeURIComponent(citySlug)}/localities/`, { params: { include_empty: true } }).then(res => res.data),
};
