'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useTheme } from '@/contexts/ThemeContext';
import { useAuth } from '@/contexts/AuthContext';
import Icon, { IconName } from '@/components/ui/Icon';

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
}

const NAV_ITEMS: { label: string; items: NavItem[] }[] = [
  {
    label: 'MAIN MENU',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: 'dashboard' },
      { to: '/residents', label: 'Residents', icon: 'residents' },
      { to: '/bookings',  label: 'Bookings',  icon: 'bookings' },
      { to: '/payments',  label: 'Payments',  icon: 'payments' },
    ],
  },
  {
    label: 'HOSTEL',
    items: [
      { to: '/hostel',      label: 'My Hostel',    icon: 'hostel' },
      { to: '/hostel/edit', label: 'Edit Details', icon: 'edit' },
      { to: '/rooms',       label: 'Rooms',        icon: 'rooms' },
    ],
  },
];

export default function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const { theme } = useTheme();
  const { authUser, logout } = useAuth();

  const handleSignOut = () => {
    logout();
    router.push('/login');
  };

  const navItemClass = (isActive: boolean) =>
    `flex items-center gap-3 px-4 py-2.5 rounded-[10px] mx-0 my-0.5 transition-all duration-200 ${
      isActive
        ? 'nav-active text-auburn-500 dark:text-auburn-300 font-semibold'
        : 'text-ink-700 dark:text-ivory-500 hover:text-ink-900 dark:hover:text-ivory-50 hover:bg-ivory-100/70 dark:hover:bg-ivory-50/5'
    }`;

  const sidebarBg = theme === 'dark' ? 'bg-ivory-950' : 'bg-ivory-50';
  const displayName = authUser?.display_name || authUser?.email || 'Owner';
  const email = authUser?.email || authUser?.phone_number || 'No email set';
  const initials = displayName[0]?.toUpperCase() || 'O';

  return (
    <div className={`fixed left-0 top-0 h-screen w-[260px] ${sidebarBg} border-r border-ivory-300 dark:border-ivory-700 text-ink-900 dark:text-ivory-50 flex flex-col z-30`}>
      {/* Logo */}
      <div className="flex items-center gap-3 p-6 mb-1">
        <div className="w-10 h-10 rounded-[12px] bg-auburn-500 dark:bg-auburn-300 flex items-center justify-center font-bold text-sm text-ivory-50 dark:text-ink-900 shadow-md shadow-auburn-500/30 dark:shadow-auburn-300/30">
          HH
        </div>
        <div>
          <span className="font-bold text-[15px] text-ink-900 dark:text-ivory-50 block leading-tight">Hostel Hunt</span>
          <span className="text-[10px] text-ink-700 dark:text-ivory-500 font-semibold uppercase tracking-wider">Admin Panel</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 flex flex-col overflow-y-auto">
        {NAV_ITEMS.map((group) => (
          <div key={group.label} className="mb-2">
            <div className="text-ink-700 dark:text-ivory-500 text-[9px] tracking-[0.12em] uppercase mb-1 px-4 font-bold mt-4">
              {group.label}
            </div>
            {group.items.map((item) => {
              const isItemActive = pathname.startsWith(item.to);
              return (
                <Link key={item.to} href={item.to} className={navItemClass(isItemActive)}>
                  <Icon name={item.icon} className="w-[18px] h-[18px] flex-shrink-0" />
                  <span className="font-medium text-[14px]">{item.label}</span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Bottom user panel */}
      <div className="p-4 border-t border-ivory-300 dark:border-ivory-700">
        <div className="flex items-center gap-3 p-3 rounded-[12px] bg-ivory-100/60 dark:bg-ivory-50/5 mb-3">
          <div className="w-9 h-9 rounded-full bg-auburn-500 dark:bg-auburn-300 flex items-center justify-center font-bold text-ivory-50 dark:text-ink-900 text-sm flex-shrink-0">
            {initials}
          </div>
          <div className="overflow-hidden flex-1 min-w-0">
            <p className="text-[13px] font-semibold text-ink-900 dark:text-ivory-50 truncate">{displayName}</p>
            <p className="text-[11px] text-ink-700 dark:text-ivory-500 truncate">{email}</p>
          </div>
        </div>

        <button
          onClick={handleSignOut}
          className="w-full py-2.5 border border-ivory-300 dark:border-ivory-700 hover:border-red-500/40 dark:hover:border-red-500/40 hover:bg-red-500/5 text-ink-700 dark:text-ivory-500 hover:text-red-500 dark:hover:text-red-400 rounded-[10px] transition-all text-[13px] font-semibold flex items-center justify-center gap-2"
        >
          <Icon name="logout" className="w-4 h-4" />
          Sign Out
        </button>
      </div>
    </div>
  );
}
