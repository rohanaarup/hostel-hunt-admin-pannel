import React from 'react';
import { Link } from 'react-router-dom';

interface AuthLayoutProps {
  children: React.ReactNode;
  heroTitle?: string;
  features?: { text: string }[];
}

const DEFAULT_FEATURES = [
  { text: 'Real-time bookings overview' },
  { text: 'Photo & media management' },
  { text: 'Dynamic room pricing setup' },
  { text: 'Instant payment tracking' },
];

export const AuthLayout: React.FC<AuthLayoutProps> = ({
  children,
  heroTitle = 'Manage your hostel\nwith confidence',
  features = DEFAULT_FEATURES,
}) => {
  return (
    <div className="min-h-screen bg-[#0F0F0F] text-[#F0EDE8] flex animate-fade-in">
      {/* ── Decorative left panel ── */}
      <div className="hidden lg:flex w-[45%] xl:w-1/2 bg-[#141414] border-r border-[#2A2A2A] flex-col justify-center px-14 xl:px-20 relative overflow-hidden flex-shrink-0">
        {/* Glow blob */}
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-[#E8571A]/5 rounded-full blur-[100px] translate-x-1/2 -translate-y-1/2 pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-[300px] h-[300px] bg-[#E8571A]/3 rounded-full blur-[80px] -translate-x-1/2 translate-y-1/2 pointer-events-none" />

        {/* Logo */}
        <Link to="/" className="flex items-center gap-3 mb-12 group w-fit">
          <div className="w-[42px] h-[42px] rounded-[12px] bg-[#E8571A] flex items-center justify-center font-bold text-base text-white shadow-[0_0_32px_rgba(232,87,26,0.4)] group-hover:shadow-[0_0_48px_rgba(232,87,26,0.5)] transition-shadow">
            HH
          </div>
          <span className="font-bold text-xl text-white tracking-tight">Hostel Hunt</span>
        </Link>

        {/* Hero text */}
        <h1 className="text-[38px] xl:text-[44px] font-bold mb-4 tracking-tight leading-tight whitespace-pre-line">
          {heroTitle}
        </h1>
        <p className="text-[#9A9690] text-lg mb-12 max-w-sm leading-relaxed">
          All your rooms, bookings, and guests — in one beautiful dashboard.
        </p>

        {/* Features */}
        <div className="space-y-3.5">
          {features.map((f, i) => (
            <div key={i} className="flex items-center gap-3 group">
              <div className="w-5 h-5 rounded-full border border-[#E8571A]/40 bg-[#E8571A]/10 flex items-center justify-center flex-shrink-0">
                <div className="w-2 h-2 rounded-full bg-[#E8571A]" />
              </div>
              <span className="text-[#C8C4BE] font-medium group-hover:text-white transition-colors">{f.text}</span>
            </div>
          ))}
        </div>

        {/* Bottom badge */}
        <div className="mt-14 flex items-center gap-2 text-[#4A4A4A] text-sm">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          Secure · Trusted by 500+ hostel owners
        </div>
      </div>

      {/* ── Right panel (form) ── */}
      <div className="flex-1 flex items-center justify-center p-6 relative overflow-y-auto">
        {/* Background glow */}
        <div className="absolute top-1/4 right-1/4 w-64 h-64 bg-[#E8571A]/3 rounded-full blur-[100px] pointer-events-none" />
        <div className="w-full max-w-[440px] relative z-10">
          {children}
        </div>
      </div>
    </div>
  );
};
