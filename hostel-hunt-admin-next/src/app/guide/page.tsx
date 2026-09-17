'use client';

import React, { useEffect, useRef } from 'react';
import Link from 'next/link';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const MODULES = [
  {
    id: 'dashboard',
    title: 'Dashboard Overview',
    desc: 'Get a bird\'s-eye view of your hostel\'s performance. Monitor occupancy rates, recent bookings, and critical notices at a glance.',
  },
  {
    id: 'bookings',
    title: 'Managing Bookings',
    desc: 'Handle incoming requests, approve offline payments, and track the status of every student booking from a unified interface.',
  },
  {
    id: 'payments',
    title: 'Payment Tracking',
    desc: 'Never miss a due payment. View comprehensive logs of all transactions, track overdue balances, and mark cash payments as received.',
  },
  {
    id: 'residents',
    title: 'Resident Directory',
    desc: 'Maintain detailed profiles for every student living in your hostel. Track move-in dates, bed allocations, and easily mark residents as vacated.',
  },
  {
    id: 'rooms',
    title: 'Room Configuration',
    desc: 'Set up your hostel layout. Define sharing types, set pricing per room, and monitor real-time bed availability.',
  },
  {
    id: 'notices',
    title: 'Notice Board',
    desc: 'Broadcast important announcements to your residents instantly. Pin rules, upcoming events, or maintenance alerts.',
  },
];

const FLOW_STEPS = [
  { icon: '📝', title: 'Register & Setup', desc: 'Create your owner profile and add hostel details.' },
  { icon: '🛏️', title: 'Configure Rooms', desc: 'Set up room types, capacity, and pricing.' },
  { icon: '👥', title: 'Add Residents', desc: 'Add students, allocate beds, and track info.' },
  { icon: '💰', title: 'Track Payments', desc: 'Monitor dues and log offline transactions.' },
];

export default function GuidePage() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const ctx = gsap.context(() => {
      // Hero animation
      gsap.from('.guide-hero-text', {
        y: 40,
        opacity: 0,
        duration: 0.8,
        stagger: 0.2,
        ease: 'power3.out'
      });

      // Bento cards scroll animation
      const cards = gsap.utils.toArray('.guide-card');
      cards.forEach((card: any) => {
        gsap.from(card, {
          scrollTrigger: {
            trigger: card,
            start: 'top 85%',
            toggleActions: 'play none none reverse'
          },
          y: 60,
          opacity: 0,
          duration: 0.6,
          ease: 'power2.out'
        });
      });

      // Flow steps animation
      gsap.from('.flow-step', {
        scrollTrigger: { trigger: '.flow-container', start: 'top 85%' },
        y: 30,
        opacity: 0,
        duration: 0.6,
        stagger: 0.2,
        ease: 'back.out(1.7)'
      });
      
      // Flow arrows animation
      gsap.from('.flow-arrow', {
        scrollTrigger: { trigger: '.flow-container', start: 'top 85%' },
        scaleX: 0,
        opacity: 0,
        transformOrigin: 'left center',
        duration: 0.6,
        stagger: 0.2,
        delay: 0.3,
        ease: 'power2.out'
      });

    }, containerRef);

    return () => ctx.revert();
  }, []);

  return (
    <div ref={containerRef} className="min-h-screen bg-ivory-50 dark:bg-ink-900 text-ink-900 dark:text-ivory-50 relative overflow-x-hidden selection:bg-auburn-200">
      
      {/* ─── Ambient Background ─── */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute inset-0 bg-gradient-to-b from-ivory-50/80 to-ivory-100 dark:from-ink-900/90 dark:to-ink-900" />
        <div className="hero-orb orb-auburn animate-float" style={{ width: 500, height: 500, top: '-10%', right: '-10%', opacity: 0.15 }} />
        <div className="hero-orb orb-emerald animate-float" style={{ width: 400, height: 400, bottom: '10%', left: '-5%', opacity: 0.1, animationDelay: '2s' }} />
      </div>

      {/* ─── Navigation ─── */}
      <nav className="relative z-10 w-full px-6 py-6 flex items-center justify-between max-w-7xl mx-auto">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-xl bg-auburn-500 flex items-center justify-center font-bold text-ivory-50 shadow-lg group-hover:scale-105 transition-transform">
            HH
          </div>
          <span className="font-display font-bold text-xl tracking-tight">Hostel Hunt</span>
        </Link>
        <Link href="/login" className="px-5 py-2.5 rounded-lg text-sm font-bold bg-ivory-200 dark:bg-ivory-800 hover:bg-ivory-300 dark:hover:bg-ivory-700 transition-colors">
          Back to Login
        </Link>
      </nav>

      {/* ─── Hero ─── */}
      <header className="relative z-10 max-w-4xl mx-auto px-6 pt-20 pb-32 text-center">
        <h1 className="guide-hero-text font-display text-5xl md:text-7xl font-extrabold tracking-tight mb-6 leading-tight">
          Master your <span className="text-gradient">Hostel Operations</span>
        </h1>
        <p className="guide-hero-text text-lg md:text-xl text-ink-700 dark:text-ivory-500 max-w-2xl mx-auto leading-relaxed">
          Follow this step-by-step video guide to learn how to utilize the Hostel Hunt Admin Panel to its fullest potential. From check-ins to payment tracking.
        </p>
      </header>

      {/* ─── Animated Flow Section ─── */}
      <section className="relative z-10 max-w-7xl mx-auto px-6 pb-24 flow-container">
        <div className="text-center mb-12">
          <h2 className="font-display text-3xl font-bold mb-4">How it works</h2>
          <p className="text-ink-700 dark:text-ivory-500 max-w-lg mx-auto">The complete workflow from registration to daily management.</p>
        </div>

        <div className="flex flex-col lg:flex-row items-center justify-between gap-6 lg:gap-4 relative">
          {FLOW_STEPS.map((step, i) => (
            <React.Fragment key={i}>
              {/* Step Card */}
              <div className="flow-step glass w-full lg:w-1/4 rounded-2xl p-6 text-center relative z-10 hover:-translate-y-2 transition-transform duration-300">
                <div className="w-16 h-16 mx-auto bg-auburn-500/10 dark:bg-auburn-300/10 rounded-full flex items-center justify-center text-3xl mb-4 shadow-lg border border-auburn-500/20 dark:border-auburn-300/20">
                  {step.icon}
                </div>
                <h3 className="font-bold text-lg mb-2">{step.title}</h3>
                <p className="text-sm text-ink-700 dark:text-ivory-500 leading-relaxed">{step.desc}</p>
              </div>

              {/* Connecting Arrow (hidden on mobile, visible on lg) */}
              {i < FLOW_STEPS.length - 1 && (
                <div className="hidden lg:block w-12 xl:w-20 flex-shrink-0 relative h-10 flow-arrow">
                  <div className="absolute inset-0 flex items-center">
                    {/* Dashed line */}
                    <div className="w-full border-t-2 border-dashed border-auburn-500/40 dark:border-auburn-300/40" />
                    {/* Arrow head */}
                    <svg className="absolute right-0 w-6 h-6 text-auburn-500/60 dark:text-auburn-300/60 translate-x-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              )}
              
              {/* Vertical Arrow for mobile */}
              {i < FLOW_STEPS.length - 1 && (
                <div className="lg:hidden h-10 flow-arrow flex items-center justify-center">
                  <svg className="w-6 h-6 text-auburn-500/40 dark:text-auburn-300/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                  </svg>
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      </section>

      {/* ─── Grid Modules ─── */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 pb-32">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {MODULES.map((mod, i) => (
            <div
              key={mod.id}
              className="guide-card glass rounded-3xl p-6 md:p-8 flex flex-col transition-all duration-300 hover:shadow-2xl hover:-translate-y-1"
            >
              {/* Placeholder Video Embed */}
              <div className="w-full aspect-video bg-ink-900/5 dark:bg-ivory-50/5 rounded-2xl mb-6 relative overflow-hidden group border border-ivory-300/30 dark:border-ivory-700/30">
                <div className="absolute inset-0 flex flex-col items-center justify-center text-ink-700/50 dark:text-ivory-500/50">
                  <svg className="w-12 h-12 mb-3 opacity-50 group-hover:scale-110 transition-transform" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                  <span className="font-semibold text-sm tracking-widest uppercase">Video coming soon</span>
                </div>
              </div>
              
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 rounded-full bg-auburn-500/10 dark:bg-auburn-300/10 text-auburn-500 dark:text-auburn-300 flex items-center justify-center font-bold text-sm flex-shrink-0 mt-1">
                  {i + 1}
                </div>
                <div>
                  <h3 className="text-2xl font-bold font-display mb-2">{mod.title}</h3>
                  <p className="text-ink-700 dark:text-ivory-500 leading-relaxed">
                    {mod.desc}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>

    </div>
  );
}
