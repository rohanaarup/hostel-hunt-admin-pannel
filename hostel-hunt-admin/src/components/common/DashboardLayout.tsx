import { Sidebar } from './Sidebar';
import { useTheme } from '../../contexts/ThemeContext';

export const DashboardLayout = ({ children, title = 'Dashboard' }: { children: React.ReactNode, title?: string }) => {
  const { theme, toggleTheme } = useTheme();
  
  const mainBg = theme === 'dark' ? 'bg-[#0F0F0F]' : 'bg-[#F5F5F0]';
  const navBg = theme === 'dark' ? 'bg-[#141414]' : 'bg-[#FFFFFF]';
  const navBorder = theme === 'dark' ? 'border-[#2A2A2A]' : 'border-[#E8E5E0]';
  const textColor = theme === 'dark' ? 'text-[#F0EDE8]' : 'text-[#1A1A1A]';

  return (
    <div className={`min-h-screen ${mainBg} flex transition-colors duration-300`}>
      <Sidebar />
      <div className={`flex-1 ml-[260px] ${textColor}`}>
        {/* Top Navbar */}
        <header className={`h-[64px] sticky top-0 z-10 ${navBg} border-b ${navBorder} flex items-center justify-between px-8 transition-colors duration-300`}>
          <h2 className="font-semibold text-lg">{title}</h2>
          
          <div className="flex items-center gap-4">
            <button 
              onClick={toggleTheme}
              className={`w-[36px] h-[36px] rounded-full border ${navBorder} flex items-center justify-center hover:border-[#E8571A] transition-colors`}
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" /></svg>
              )}
            </button>
            <button className={`w-[36px] h-[36px] rounded-full border ${navBorder} flex items-center justify-center hover:border-[#E8571A] transition-colors`}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" /></svg>
            </button>
            <div className="w-[36px] h-[36px] rounded-full bg-[#E8571A] flex items-center justify-center font-medium text-sm text-white border border-[#E8571A]">
              H
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-8">
          {children}
        </main>
      </div>
    </div>
  );
};
