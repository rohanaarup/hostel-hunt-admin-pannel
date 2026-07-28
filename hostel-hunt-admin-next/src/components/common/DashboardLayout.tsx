'use client';

import Sidebar from './Sidebar';
import { useTheme } from '@/contexts/ThemeContext';
import Icon from '@/components/ui/Icon';
import { useAuth } from '@/contexts/AuthContext';

export default function DashboardLayout({ children, title = 'Dashboard' }: { children: React.ReactNode; title?: string }) {
  const { theme, toggleTheme } = useTheme();
  const { authUser } = useAuth();

  const mainBg = theme === 'dark' ? 'bg-ivory-900' : 'bg-ivory-50';
  const navBg = theme === 'dark' ? 'bg-ivory-950' : 'bg-white';
  const navBorder = theme === 'dark' ? 'border-ivory-700' : 'border-ivory-300';
  const textColor = theme === 'dark' ? 'text-ivory-50' : 'text-ink-900';

  const displayName = authUser?.display_name || authUser?.email || 'Owner';
  const initials = displayName[0]?.toUpperCase() || 'O';
  const today = new Date().toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });

  return (
    <div className={`min-h-screen ${mainBg} flex transition-colors duration-300`}>
      <Sidebar />
      <div className={`flex-1 ml-[260px] ${textColor}`}>
        {/* Top Navbar */}
        <header className={`h-[68px] sticky top-0 z-20 ${navBg} border-b ${navBorder} flex items-center justify-between px-6 lg:px-8 transition-colors duration-300 backdrop-blur-md bg-opacity-90`}>
          <div>
            <h2 className="font-semibold text-base text-ink-900 dark:text-ivory-50">{title}</h2>
            <p className="text-[11px] text-ink-700 dark:text-ivory-500 mt-0.5 font-medium hidden sm:block">{today}</p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              className={`w-[36px] h-[36px] rounded-full border ${navBorder} flex items-center justify-center hover:border-auburn-500/60 dark:hover:border-auburn-300/60 hover:text-auburn-500 dark:hover:text-auburn-300 transition-colors`}
              aria-label="Toggle theme"
            >
              <Icon name={theme === 'dark' ? 'sun' : 'moon'} className="w-4 h-4" />
            </button>
            <button className={`w-[36px] h-[36px] rounded-full border ${navBorder} flex items-center justify-center hover:border-auburn-500/60 dark:hover:border-auburn-300/60 hover:text-auburn-500 dark:hover:text-auburn-300 transition-colors`}>
              <Icon name="bell" className="w-4 h-4" />
            </button>
            <div className="w-[36px] h-[36px] rounded-full bg-auburn-500 dark:bg-auburn-300 flex items-center justify-center font-bold text-sm text-ivory-50 dark:text-ink-900 border border-auburn-500 dark:border-auburn-300">
              {initials}
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
