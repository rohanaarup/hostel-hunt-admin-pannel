'use client';

import Link from 'next/link';
import Image from 'next/image';
import { usePathname, useRouter } from 'next/navigation';
import { useTheme } from '@/contexts/ThemeContext';
import { useAuth } from '@/contexts/AuthContext';
import {
  UilGrids, UilUsersAlt, UilCalendarAlt, UilMoneyBill,
  UilBuilding, UilEdit, UilBedDouble, UilSignout, UilSun, UilMoon,
} from '@iconscout/react-unicons';
import { useEffect, useRef } from 'react';
import gsap from 'gsap';

interface NavItem {
  to: string;
  label: string;
  Icon: React.ElementType;
}

const NAV_ITEMS: { label: string; items: NavItem[] }[] = [
  {
    label: 'MAIN MENU',
    items: [
      { to: '/dashboard', label: 'Dashboard', Icon: UilGrids },
      { to: '/residents',  label: 'Residents',  Icon: UilUsersAlt },
      { to: '/bookings',   label: 'Bookings',   Icon: UilCalendarAlt },
      { to: '/payments',   label: 'Payments',   Icon: UilMoneyBill },
    ],
  },
  {
    label: 'HOSTEL',
    items: [
      { to: '/hostel',      label: 'My Hostel',    Icon: UilBuilding },
      { to: '/hostel/edit', label: 'Edit Details',  Icon: UilEdit },
      { to: '/rooms',       label: 'Rooms',         Icon: UilBedDouble },
    ],
  },
];

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const { authUser, logout } = useAuth();
  const navRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (navRef.current) {
      const items = navRef.current.querySelectorAll('.nav-item');
      gsap.fromTo(items,
        { opacity: 0, x: -16 },
        { opacity: 1, x: 0, duration: 0.35, stagger: 0.05, ease: 'power2.out', delay: 0.1 }
      );
    }
  }, []);

  const handleSignOut = () => {
    logout();
    router.push('/login');
  };

  const displayName = authUser?.display_name || authUser?.email || 'Owner';
  const email = authUser?.email || authUser?.phone_number || '';
  const initials = displayName.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase() || 'O';

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-ink-900/40 dark:bg-ink-900/60 z-30 md:hidden backdrop-blur-sm transition-opacity"
          onClick={onClose}
        />
      )}
      <div
        className={`fixed left-0 top-0 h-screen w-[260px] border-r border-[var(--color-border)] flex flex-col z-40 transition-transform duration-300 ease-in-out ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
        style={{ background: 'var(--color-surface)' }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 py-5 border-b border-[var(--color-border)]">
          <div className="relative w-9 h-9 flex-shrink-0">
            <Image
              src="/hh-logo.png"
              alt="Hostel Hunt"
              fill
              className="object-contain rounded-[8px]"
              sizes="36px"
            />
          </div>
          <div className="flex-1 min-w-0">
            <span className="font-bold text-[15px] block leading-tight truncate" style={{ color: 'var(--color-text-primary)', fontFamily: 'var(--font-display)' }}>
              Hostel Hunt
            </span>
            <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: 'var(--color-primary)' }}>
              Admin Panel
            </span>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="md:hidden w-8 h-8 flex items-center justify-center rounded-full transition-colors"
              style={{ color: 'var(--color-text-muted)' }}
            >
              ✕
            </button>
          )}
        </div>

        {/* Navigation */}
        <nav ref={navRef} className="flex-1 px-3 py-4 flex flex-col overflow-y-auto space-y-1">
          {NAV_ITEMS.map((group) => (
            <div key={group.label} className="mb-2">
              <div
                className="text-[9px] tracking-[0.15em] uppercase mb-2 px-3 font-bold mt-3"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {group.label}
              </div>
              {group.items.map(({ to, label, Icon }) => {
                const isActive = pathname === to || (to !== '/dashboard' && pathname.startsWith(to));
                return (
                  <Link
                    key={to}
                    href={to}
                    className={`nav-item flex items-center gap-3 px-3 py-2.5 rounded-[10px] transition-all duration-200 group ${
                      isActive
                        ? 'nav-active font-semibold'
                        : 'hover:bg-[var(--color-border)]/40'
                    }`}
                    style={{
                      color: isActive ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                    }}
                  >
                    <Icon size="18" className="flex-shrink-0 transition-transform duration-200 group-hover:scale-110" />
                    <span className="font-medium text-[14px] leading-tight">{label}</span>
                    {isActive && (
                      <span
                        className="ml-auto w-1.5 h-1.5 rounded-full"
                        style={{ background: 'var(--color-primary)' }}
                      />
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Bottom: theme + user */}
        <div className="p-3 border-t border-[var(--color-border)] space-y-2">
          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-[10px] transition-all duration-200 hover:bg-[var(--color-border)]/40"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {theme === 'dark' ? <UilSun size="18" /> : <UilMoon size="18" />}
            <span className="text-[13px] font-medium">{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
          </button>

          {/* User card */}
          <div
            className="flex items-center gap-3 p-3 rounded-[12px]"
            style={{ background: 'var(--color-background)' }}
          >
            <div
              className="w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0"
              style={{ background: 'var(--color-primary)', color: 'var(--color-text-inverse)' }}
            >
              {initials}
            </div>
            <div className="overflow-hidden flex-1 min-w-0">
              <p className="text-[13px] font-semibold truncate" style={{ color: 'var(--color-text-primary)' }}>
                {displayName}
              </p>
              <p className="text-[11px] truncate" style={{ color: 'var(--color-text-muted)' }}>
                {email || 'Hostel Owner'}
              </p>
            </div>
          </div>

          <button
            onClick={handleSignOut}
            className="w-full py-2.5 border rounded-[10px] transition-all text-[13px] font-semibold flex items-center justify-center gap-2 hover:border-[var(--color-error)]/40 hover:bg-[var(--color-error-light)] group"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-muted)',
            }}
          >
            <UilSignout size="16" className="group-hover:text-[var(--color-error)]" />
            <span className="group-hover:text-[var(--color-error)] transition-colors">Sign Out</span>
          </button>
        </div>
      </div>
    </>
  );
}
