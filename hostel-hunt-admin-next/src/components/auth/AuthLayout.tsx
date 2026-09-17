'use client';

import Link from 'next/link';
import { useRef, useEffect } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

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

export default function AuthLayout({
  children,
  heroTitle = 'Manage your hostel\nwith confidence',
  features = DEFAULT_FEATURES,
}: AuthLayoutProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Subtle tilt on mouse move — never blocks form interaction (pointer-events pass through)
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const panel = panelRef.current;
    if (!panel) return;
    const rect = panel.getBoundingClientRect();
    const x = (e.clientX - rect.left - rect.width / 2) / rect.width;
    const y = (e.clientY - rect.top - rect.height / 2) / rect.height;
    const tiltX = y * -3;
    const tiltY = x * 3;
    panel.style.transform = `perspective(1200px) rotateX(${tiltX}deg) rotateY(${tiltY}deg)`;
  };

  const handleMouseLeave = () => {
    const panel = panelRef.current;
    if (panel) panel.style.transform = 'perspective(1200px) rotateX(0deg) rotateY(0deg)';
  };

  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const ctx = gsap.context(() => {
      // Background overlay fade in
      gsap.from('.auth-bg-overlay', { opacity: 0, duration: 1.5, ease: 'power2.inOut' });

      // Left panel elements stagger
      gsap.from('.hero-reveal', {
        y: 30,
        opacity: 0,
        duration: 0.8,
        stagger: 0.15,
        ease: 'power3.out',
        delay: 0.2
      });

      // Right panel (form) entrance
      gsap.from(panelRef.current, {
        x: 40,
        opacity: 0,
        duration: 0.9,
        ease: 'power3.out',
        delay: 0.4
      });

      // Orbs float in
      gsap.from('.hero-orb', {
        scale: 0.8,
        opacity: 0,
        duration: 1.5,
        ease: 'power2.out',
        stagger: 0.2
      });
    }, containerRef);
    return () => ctx.revert();
  }, []);

  return (
    <div ref={containerRef} className="bg-ivory-50 dark:bg-ink-900 text-ink-900 dark:text-ivory-50 relative overflow-x-hidden min-h-screen flex flex-col">
      {/* ─── Ambient video background (Fixed fixed position to cover scrolling page) ─── */}
      <div className="fixed inset-0 z-0">
        <video
          className="auth-bg-video"
          autoPlay
          muted
          loop
          playsInline
        >
          <source src="/background.mp4" type="video/mp4" />
        </video>
        <div className="auth-bg-overlay" />
      </div>

      {/* ─── Fold 1: Auth Panel ─── */}
      <div className="min-h-screen flex relative z-10 flex-shrink-0">

      {/* Floating orbs for depth */}
      <div className="hero-orb orb-auburn animate-float" style={{ width: 380, height: 380, top: '-5%', left: '10%' }} />
      <div className="hero-orb orb-emerald animate-float" style={{ width: 320, height: 320, bottom: '-8%', right: '15%', animationDelay: '2s' }} />

      {/* ── Decorative left panel ── */}
      <div className="hidden lg:flex w-[45%] xl:w-1/2 flex-col justify-center px-14 xl:px-20 relative z-10 flex-shrink-0">
        {/* Logo */}
        <Link href="/" className="hero-reveal flex items-center gap-3 mb-12 group w-fit">
          <div className="w-[44px] h-[44px] rounded-[12px] bg-auburn-500 dark:bg-auburn-300 flex items-center justify-center font-bold text-base text-ivory-50 dark:text-ink-900 shadow-[0_0_32px_rgba(165,42,42,0.4)] group-hover:shadow-[0_0_48px_rgba(165,42,42,0.55)] transition-all duration-300 group-hover:scale-105">
            HH
          </div>
          <span className="font-display font-bold text-xl text-ink-900 dark:text-ivory-50 tracking-tight">Hostel Hunt</span>
        </Link>

        {/* Hero text */}
        <h1 className="hero-reveal font-display text-[38px] xl:text-[46px] font-extrabold mb-5 tracking-tight leading-[1.1] whitespace-pre-line text-gradient">
          {heroTitle}
        </h1>
        <p className="hero-reveal text-ink-700 dark:text-ivory-500 text-lg mb-12 max-w-sm leading-relaxed">
          All your rooms, bookings, and guests — in one beautiful dashboard built for Hyderabad hostel owners.
        </p>

        {/* Features — staggered reveal */}
        <div className="space-y-3.5">
          {features.map((f, i) => (
            <div
              key={i}
              className="hero-reveal flex items-center gap-3 group"
            >
              <div className="w-5 h-5 rounded-full border border-auburn-500/40 dark:border-auburn-300/40 bg-auburn-500/10 dark:bg-auburn-300/10 flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform">
                <div className="w-2 h-2 rounded-full bg-auburn-500 dark:bg-auburn-300" />
              </div>
              <span className="text-ink-700 dark:text-ivory-500 font-medium group-hover:text-ink-900 dark:group-hover:text-ivory-50 transition-colors">
                {f.text}
              </span>
            </div>
          ))}
        </div>

        {/* Bottom badge */}
        <div className="hero-reveal mt-14 flex items-center gap-2 text-ink-700/70 dark:text-ivory-500/70 text-sm">
          <svg className="w-4 h-4 text-auburn-500 dark:text-auburn-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
            />
          </svg>
          Secure · Trusted by 500+ hostel owners
        </div>
      </div>

      {/* ── Right panel (form) ── */}
      <div
        className="flex-1 flex items-center justify-center p-6 relative z-10 overflow-y-auto"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        <div className="w-full max-w-[440px] relative">
          {/* Glass panel wrapper — children (form) pass through untouched */}
          <div
            ref={panelRef}
            className="transition-transform duration-200 ease-out will-change-transform"
            style={{ transformStyle: 'preserve-3d' }}
          >
            {children}
          </div>
        </div>
      </div>
      {/* End Fold 1 */}
      </div>

      {/* ─── Fold 2: Guide Hero Section ─── */}
      <div className="relative z-10 flex flex-col items-center justify-center py-32 px-6 border-t border-ivory-300/30 dark:border-ivory-700/30">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="font-display text-4xl font-extrabold mb-6 tracking-tight text-ink-900 dark:text-ivory-50">
            Master the Hostel Hunt Admin Panel
          </h2>
          <p className="text-lg text-ink-700 dark:text-ivory-500 mb-10 max-w-2xl mx-auto leading-relaxed">
            Everything you need to know to manage your hostel efficiently. From handling daily bookings to dynamic room pricing and resident management, learn the best practices for our platform.
          </p>
          <Link
            href="/guide"
            className="inline-flex items-center justify-center gap-2 px-8 py-4 bg-auburn-500 hover:bg-auburn-600 text-ivory-50 rounded-xl font-bold transition-all card-lift glow-primary"
          >
            How to use HH admin pannel
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </Link>
        </div>
      </div>

      {/* ─── Fold 3: About / Footer ─── */}
      <footer className="relative z-10 py-16 px-6 mt-auto border-t border-ivory-300/50 dark:border-ivory-700/50 bg-ivory-50/50 dark:bg-ink-900/50 glass">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-12">
          
          <div>
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-[10px] bg-auburn-500 flex items-center justify-center font-bold text-sm text-ivory-50 shadow-lg">
                HH
              </div>
              <span className="font-display font-bold text-xl text-ink-900 dark:text-ivory-50">Hostel Hunt</span>
            </div>
            <p className="text-ink-700 dark:text-ivory-500 max-w-md leading-relaxed mb-6">
              Hostel Hunt is the premier student hostel and PG discovery platform in Hyderabad. We connect owners with verified students, providing a seamless booking and management experience.
            </p>
            <div className="flex gap-4">
              {/* Social Placeholders */}
              <a href="#" className="w-10 h-10 rounded-full flex items-center justify-center bg-ivory-200 dark:bg-ivory-900 text-ink-700 dark:text-ivory-500 hover:text-auburn-500 transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M24 4.557c-.883.392-1.832.656-2.828.775 1.017-.609 1.798-1.574 2.165-2.724-.951.564-2.005.974-3.127 1.195-.897-.957-2.178-1.555-3.594-1.555-3.179 0-5.515 2.966-4.797 6.045-4.091-.205-7.719-2.165-10.148-5.144-1.29 2.213-.669 5.108 1.523 6.574-.806-.026-1.566-.247-2.229-.616-.054 2.281 1.581 4.415 3.949 4.89-.693.188-1.452.232-2.224.084.626 1.956 2.444 3.379 4.6 3.419-2.07 1.623-4.678 2.348-7.29 2.04 2.179 1.397 4.768 2.212 7.548 2.212 9.142 0 14.307-7.721 13.995-14.646.962-.695 1.797-1.562 2.457-2.549z"/></svg>
              </a>
              <a href="#" className="w-10 h-10 rounded-full flex items-center justify-center bg-ivory-200 dark:bg-ivory-900 text-ink-700 dark:text-ivory-500 hover:text-auburn-500 transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
              </a>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-8 md:justify-end">
            <div>
              <h4 className="font-bold text-ink-900 dark:text-ivory-50 mb-4">Contact Us</h4>
              <ul className="space-y-3 text-ink-700 dark:text-ivory-500 font-medium">
                <li><a href="mailto:[CONTACT_EMAIL_HERE]" className="hover:text-auburn-500 transition-colors">[CONTACT_EMAIL_HERE]</a></li>
                <li><a href="tel:[CONTACT_PHONE_HERE]" className="hover:text-auburn-500 transition-colors">[CONTACT_PHONE_HERE]</a></li>
                <li><span className="opacity-80">[ADDRESS_HERE]</span></li>
              </ul>
            </div>
            <div>
              <h4 className="font-bold text-ink-900 dark:text-ivory-50 mb-4">Quick Links</h4>
              <ul className="space-y-3 text-ink-700 dark:text-ivory-500 font-medium">
                <li><Link href="/login" className="hover:text-auburn-500 transition-colors">Owner Login</Link></li>
                <li><Link href="/signup" className="hover:text-auburn-500 transition-colors">Partner With Us</Link></li>
                <li><Link href="/guide" className="hover:text-auburn-500 transition-colors">Admin Guide</Link></li>
              </ul>
            </div>
          </div>

        </div>
      </footer>
    </div>
  );
}
