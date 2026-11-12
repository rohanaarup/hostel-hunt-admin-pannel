'use client';

import React, { Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import DashboardLayout from '@/components/common/DashboardLayout';
import ErrorState from '@/components/ui/ErrorState';
import BillingRuleEditor from '@/components/stays/BillingRuleEditor';
import { useHostels } from '@/hooks/queries';
import { unwrapList } from '@/services/unwrap';

/** The AdminBilling board: choose when students pay each month and see what that does for four sample join dates. */

interface HostelOption { hostel_id: string; name: string; locality?: string }

function BillingContent() {
  const router = useRouter();
  const params = useSearchParams();
  const hostelsQuery = useHostels();
  const hostels = unwrapList<HostelOption>(hostelsQuery.data ?? []);
  const wanted = params.get('hostel');
  const current = hostels.find((h) => h.hostel_id === wanted) ?? hostels[0];

  return (
    <DashboardLayout title="Billing and rent">
      <div className="w-full space-y-6 animate-fade-in-up">
        <nav aria-label="Breadcrumb" className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
          <Link href="/stays" className="underline">Stays and rent</Link>
          {current ? ` › ${current.name}${current.locality ? ` · ${current.locality}` : ''}` : ''} › Billing rule
        </nav>

        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight" style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}>
              Billing and rent
            </h1>
            <p className="mt-1 text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>
              Choose when students pay each month. The preview updates as you change the rule.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {hostels.length > 1 ? (
              <select aria-label="Hostel" value={current?.hostel_id ?? ''} onChange={(e) => router.replace(`/stays/billing?hostel=${e.target.value}`)}
                className="min-h-[44px] rounded-[10px] px-3 text-sm border"
                style={{ background: 'var(--color-surface)', color: 'var(--color-text-primary)', borderColor: 'var(--color-border)' }}>
                {hostels.map((h) => <option key={h.hostel_id} value={h.hostel_id}>{h.name}</option>)}
              </select>
            ) : null}
            <Link href="/stays" className="min-h-[44px] inline-flex items-center px-4 rounded-[10px] text-sm font-semibold border"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-primary)', background: 'var(--color-surface)' }}>
              View stays and dues
            </Link>
          </div>
        </div>

        {hostelsQuery.error ? (
          <ErrorState error={hostelsQuery.error} what="your hostels" onRetry={() => hostelsQuery.refetch()} retrying={hostelsQuery.isFetching} />
        ) : hostelsQuery.isLoading ? (
          <p role="status" className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading your hostels…</p>
        ) : !current ? (
          <p className="text-sm font-semibold" style={{ color: 'var(--color-text-muted)' }}>Add a hostel first, then set its billing rule here.</p>
        ) : (
          <div className="rounded-2xl p-6" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
            <BillingRuleEditor key={current.hostel_id} hostelId={current.hostel_id} />
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

export default function BillingPage() {
  return (
    <Suspense fallback={<p role="status" className="p-8 text-sm">Loading…</p>}>
      <BillingContent />
    </Suspense>
  );
}
