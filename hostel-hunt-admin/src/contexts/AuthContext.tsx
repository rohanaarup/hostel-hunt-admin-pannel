import React, { createContext, useContext, useState, useCallback } from 'react';
import type { AuthUser } from '../types';

interface AuthContextType {
  authUser: AuthUser | null;
  isAuthenticated: boolean;
  isFirstTimeOwner: boolean;
  hasCompletedEnrollment: boolean;
  login: (user: AuthUser, tokens: { access: string; refresh: string }, remember?: boolean) => void;
  logout: () => void;
  setEnrollmentComplete: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const STORAGE_KEY = 'hh_auth_user';
const ENROLLMENT_KEY = 'hh_enrollment_complete';

function loadStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY) || sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [authUser, setAuthUser] = useState<AuthUser | null>(loadStoredUser);
  const [hasCompletedEnrollment, setHasCompletedEnrollment] = useState<boolean>(
    () => localStorage.getItem(ENROLLMENT_KEY) === 'true'
  );

  const isAuthenticated = authUser !== null;
  // First time owner: authenticated but never completed hostel enrollment
  const isFirstTimeOwner = isAuthenticated && !hasCompletedEnrollment;

  const login = useCallback((user: AuthUser, tokens: { access: string; refresh: string }, remember = false) => {
    setAuthUser(user);
    const storage = remember ? localStorage : sessionStorage;
    storage.setItem(STORAGE_KEY, JSON.stringify(user));
    
    // Always store tokens in localStorage (or sessionStorage based on remember)
    // Actually, api.ts interceptor currently looks at localStorage specifically. Let's use localStorage for tokens consistently, 
    // or handle it gracefully.
    localStorage.setItem('access_token', tokens.access);
    localStorage.setItem('refresh_token', tokens.refresh);
  }, []);

  const logout = useCallback(() => {
    setAuthUser(null);
    localStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }, []);

  const setEnrollmentComplete = useCallback(() => {
    setHasCompletedEnrollment(true);
    localStorage.setItem(ENROLLMENT_KEY, 'true');
  }, []);

  return (
    <AuthContext.Provider value={{
      authUser,
      isAuthenticated,
      isFirstTimeOwner,
      hasCompletedEnrollment,
      login,
      logout,
      setEnrollmentComplete,
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
};
