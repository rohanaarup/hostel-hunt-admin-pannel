import axios from 'axios';
import type { AuthUser } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

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
    
  getProfile: (): Promise<{success: boolean, data: AuthUser}> => 
    api.get('/auth/me/').then(res => res.data),
    
  getOwnersList: () => api.get('/owners/').then(res => res.data),
};

export const hostelService = {
  getDashboardStats: () => api.get('/dashboard/stats/').then(res => res.data),
  getRecentActivity: () => api.get('/dashboard/activity/').then(res => res.data),
  
  createHostel: (data: any) => api.post('/hostels/', data).then(res => res.data),
  updateHostel: (id: string, data: any) => api.put(`/hostels/${id}/`, data).then(res => res.data),
  getHostels: () => api.get('/hostels/').then(res => res.data),
};

export const roomService = {
  getRooms: (hostelId: string) => api.get(`/hostels/${hostelId}/rooms/`).then(res => res.data),
};

export const bookingService = {
  getBookings: () => api.get('/bookings/').then(res => res.data),
  approveBooking: (id: string) => api.post(`/bookings/${id}/approve/`).then(res => res.data),
  rejectBooking: (id: string) => api.post(`/bookings/${id}/reject/`).then(res => res.data),
};

export const paymentService = {
  getPayments: () => api.get('/payments/').then(res => res.data),
  getSummary: () => api.get('/payments/summary/').then(res => res.data),
};

export const mediaService = {
  upload: (data: any) => 
    api.post('/media/upload/', data).then(res => res.data),
    
  reorder: (items: any[]) => api.patch('/media/reorder/', { items }).then(res => res.data),
  delete: (id: string) => api.delete(`/media/${id}/`).then(res => res.data),
};
