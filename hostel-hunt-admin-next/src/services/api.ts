import axios from 'axios';
import type { AuthUser } from '../types';

// Set true to use the local Django backend; false uses Render.
const USE_LOCAL_BACKEND = false;
const LOCAL_URL = 'http://127.0.0.1:8000/api/v1';
const RENDER_URL = 'https://hostel-hunt-backend.onrender.com/api/v1';

// Next.js requires NEXT_PUBLIC_ prefix for client-exposed env vars
const API_BASE_URL = USE_LOCAL_BACKEND
  ? LOCAL_URL
  : process.env.NEXT_PUBLIC_API_URL || RENDER_URL;

export const api = axios.create({
  baseURL: API_BASE_URL,
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

// Add a response interceptor to handle 401 and refresh tokens automatically
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) throw new Error('No refresh token');

        const { data } = await axios.post(`${API_BASE_URL}/auth/token/refresh/`, {
          refresh: refreshToken,
        });

        localStorage.setItem('access_token', data.access);
        originalRequest.headers.Authorization = `Bearer ${data.access}`;
        return api(originalRequest);
      } catch (err) {
        // Refresh failed, logout
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(err);
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
  getRooms: (hostelId: string) => api.get(`/hostels/${hostelId}/rooms/`).then(res => res.data),
};

export const bookingService = {
  getBookings: (paymentMode?: 'offline' | 'online') => {
    const params = paymentMode ? { payment_mode: paymentMode } : {};
    return api.get('/bookings/', { params }).then(res => res.data);
  },
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
  getResidents: () => api.get('/residents/').then(res => res.data),
  createResident: (data: any) => api.post('/residents/create/', data).then(res => res.data),
  markResidentVacated: (id: string) => api.patch(`/residents/${id}/mark-vacated/`).then(res => res.data),
};

export const noticeService = {
  getNotices: () => api.get('/notices/').then(res => res.data),
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
