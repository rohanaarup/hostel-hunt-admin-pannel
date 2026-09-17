'use client';

import Sidebar from './Sidebar';
import { useTheme } from '@/contexts/ThemeContext';
import { useAuth } from '@/contexts/AuthContext';
import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  UilGrids, UilUsersAlt, UilCalendarAlt, UilMoneyBill,
  UilBars, UilBell,
} from '@iconscout/react-unicons';

function BottomNavItem({ to, label, Icon }: { to: string; label: string; Icon: React.ElementType }) {
  const pathname = usePathname();
  const isActive = pathname === to || (to !== '/dashboard' && pathname.startsWith(to));
  return (
    <Link
      href={to}
      className={`flex flex-col items-center justify-center w-full h-full gap-1 transition-all duration-200`}
      style={{ color: isActive ? 'var(--color-primary)' : 'var(--color-text-muted)' }}
    >
      <Icon size="22" />
      <span className="text-[10px] font-semibold">{label}</span>
      {isActive && (
        <span
          className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-0.5 rounded-full"
          style={{ background: 'var(--color-primary)' }}
        />
      )}
    </Link>
  );
}

export default function DashboardLayout({ children, title = 'Dashboard' }: { children: React.ReactNode; title?: string }) {
  const { authUser } = useAuth();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const displayName = authUser?.display_name || authUser?.email || 'Owner';
  const initials = displayName.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase() || 'O';
  const today = new Date().toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });

  return (
    <div
      className="min-h-screen flex transition-colors duration-300 pb-16 md:pb-0"
      style={{ background: 'var(--color-background)' }}
    >
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />

      <div
        className="flex-1 md:ml-[260px] w-full transition-all"
        style={{ color: 'var(--color-text-primary)' }}
      >
        {/* Top Navbar */}
        <header
          className="h-[64px] sticky top-0 z-20 flex items-center justify-between px-4 lg:px-8 transition-colors duration-300"
          style={{
            background: 'var(--color-surface)',
            borderBottom: '1px solid var(--color-border)',
            backdropFilter: 'blur(12px)',
          }}
        >
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="md:hidden w-[40px] h-[40px] flex items-center justify-center rounded-full transition-colors hover:bg-[var(--color-border)]"
              style={{ color: 'var(--color-text-primary)' }}
            >
              <UilBars size="20" />
            </button>
            <div>
              <h2
                className="font-bold text-base leading-tight"
                style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}
              >
                {title}
              </h2>
              <p className="text-[11px] font-medium hidden sm:block" style={{ color: 'var(--color-text-muted)' }}>
                {today}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              className="w-[36px] h-[36px] rounded-full border flex items-center justify-center transition-all hover:border-[var(--color-primary)]/60 hover:text-[var(--color-primary)] relative"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}
              aria-label="Notifications"
            >
              <UilBell size="16" />
            </button>
            <div
              className="w-[36px] h-[36px] rounded-full flex items-center justify-center font-bold text-sm border"
              style={{
                background: 'var(--color-primary)',
                color: 'var(--color-text-inverse)',
                borderColor: 'var(--color-primary)',
              }}
            >
              {initials}
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-4 lg:p-8 min-h-[calc(100vh-64px)]">{children}</main>
      </div>

      {/* Mobile Bottom Nav */}
      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 h-16 z-20 flex items-center justify-around px-2 shadow-lg relative"
        style={{
          background: 'var(--color-surface)',
          borderTop: '1px solid var(--color-border)',
        }}
      >
        <BottomNavItem to="/dashboard" label="Home"      Icon={UilGrids} />
        <BottomNavItem to="/hostel"    label="Hostel"    Icon={UilMoneyBill} />
        <BottomNavItem to="/bookings"  label="Bookings"  Icon={UilCalendarAlt} />
        <BottomNavItem to="/residents" label="Residents" Icon={UilUsersAlt} />
      </nav>
    </div>
  );
}
