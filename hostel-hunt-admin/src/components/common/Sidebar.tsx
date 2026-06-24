import { NavLink, useNavigate } from 'react-router-dom';
import { useTheme } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';

const NAV_ITEMS = [
  {
    label: 'MAIN MENU',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /> },
      { to: '/users', label: 'Users', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /> },
      { to: '/bookings', label: 'Bookings', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /> },
      { to: '/payments', label: 'Payments', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /> },
    ],
  },
  {
    label: 'HOSTEL',
    items: [
      { to: '/hostel', label: 'My Hostel', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /> },
      { to: '/hostel/edit', label: 'Edit Details', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /> },
      { to: '/rooms', label: 'Rooms', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z" /> },
    ],
  },
];

export const Sidebar = () => {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const { authUser, logout } = useAuth();

  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  const navItemClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 px-4 py-2.5 rounded-[10px] mx-0 my-0.5 transition-all duration-150 ${
      isActive
        ? 'nav-active text-white'
        : 'text-[#9A9690] hover:text-white hover:bg-[#FFFFFF08]'
    }`;

  const sidebarBg = theme === 'dark' ? 'bg-[#141414]' : 'bg-[#1A1A1A]';
  const displayName = authUser?.display_name || authUser?.email || 'Owner';
  const email = authUser?.email || authUser?.phone_number || 'No email set';
  const initials = displayName[0]?.toUpperCase() || 'O';

  return (
    <div className={`fixed left-0 top-0 h-screen w-[260px] ${sidebarBg} border-r border-[#2A2A2A] text-white flex flex-col`}>
      {/* Logo */}
      <div className="flex items-center gap-3 p-6 mb-1">
        <div className="w-8 h-8 rounded-[10px] bg-[#E8571A] flex items-center justify-center font-bold text-sm text-white shadow-[0_0_20px_rgba(232,87,26,0.3)]">
          HH
        </div>
        <div>
          <span className="font-bold text-[15px] text-white block leading-tight">Hostel Hunt</span>
          <span className="text-[10px] text-[#4A4A4A] font-semibold uppercase tracking-wider">Admin Panel</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 flex flex-col overflow-y-auto">
        {NAV_ITEMS.map(group => (
          <div key={group.label} className="mb-2">
            <div className="text-[#4A4A4A] text-[9px] tracking-[0.12em] uppercase mb-1 px-4 font-bold mt-4">
              {group.label}
            </div>
            {group.items.map(item => (
              <NavLink key={item.to} to={item.to} className={navItemClass}>
                <svg className="w-[18px] h-[18px] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  {item.icon}
                </svg>
                <span className="font-medium text-[14px]">{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Bottom user panel */}
      <div className="p-4 border-t border-[#2A2A2A]">
        <div className="flex items-center gap-3 p-3 rounded-[12px] bg-[#FFFFFF05] mb-3">
          <div className="w-9 h-9 rounded-full bg-[#E8571A] flex items-center justify-center font-bold text-white text-sm flex-shrink-0">
            {initials}
          </div>
          <div className="overflow-hidden flex-1 min-w-0">
            <p className="text-[13px] font-semibold text-white truncate">{displayName}</p>
            <p className="text-[11px] text-[#9A9690] truncate">{email}</p>
          </div>
        </div>

        <button
          onClick={handleSignOut}
          className="w-full py-2.5 border border-[#2A2A2A] hover:border-[#E8571A]/50 hover:bg-red-500/5 text-[#9A9690] hover:text-red-400 rounded-[10px] transition-all text-[13px] font-semibold flex items-center justify-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          Sign Out
        </button>
      </div>
    </div>
  );
};
