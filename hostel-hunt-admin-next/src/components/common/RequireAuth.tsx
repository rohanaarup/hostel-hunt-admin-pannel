'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import Spinner from '@/components/ui/Spinner';

/**
 * Wraps every page that needs a signed-in owner. Until the saved login has been read it shows a
 * spinner; if there is no login it sends the visitor to /login and renders nothing of the page, so a
 * logged-out visitor never sees (or requests) any owner data.
 */
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isReady, isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isReady && !isAuthenticated) router.replace('/login');
  }, [isReady, isAuthenticated, router]);

  if (!isReady || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--color-background)' }}>
        <Spinner size="lg" />
      </div>
    );
  }
  return <>{children}</>;
}
