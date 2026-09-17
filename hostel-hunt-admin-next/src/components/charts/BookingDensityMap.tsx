'use client';

import { ResponsiveTimeRange } from '@nivo/calendar';
import React, { useMemo } from 'react';

interface Props {
  bookings: any[];
}

export default function BookingDensityMap({ bookings }: Props) {
  const data = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const b of bookings) {
      if (!b.created_at) continue;
      // Extract YYYY-MM-DD
      const d = new Date(b.created_at).toISOString().split('T')[0];
      counts[d] = (counts[d] || 0) + 1;
    }
    return Object.entries(counts).map(([day, value]) => ({ day, value }));
  }, [bookings]);

  const fromDate = new Date();
  fromDate.setMonth(fromDate.getMonth() - 11);

  if (data.length === 0) {
    return (
      <div className="w-full h-full min-h-[220px] flex items-center justify-center">
        <p className="text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>
          Not enough historical data to generate heatmap
        </p>
      </div>
    );
  }

  return (
    <div className="w-full h-[220px]">
      <ResponsiveTimeRange
        data={data}
        from={fromDate.toISOString().split('T')[0]}
        to={new Date().toISOString().split('T')[0]}
        emptyColor="color-mix(in srgb, var(--color-border) 40%, transparent)"
        colors={['color-mix(in srgb, var(--color-primary) 20%, transparent)', 'color-mix(in srgb, var(--color-primary) 50%, transparent)', 'var(--color-primary)', 'color-mix(in srgb, var(--color-primary) 80%, black)']}
        margin={{ top: 30, right: 10, bottom: 10, left: 10 }}
        dayBorderWidth={1}
        dayBorderColor="var(--color-surface)"
        daySpacing={3}
        monthLegendOffset={14}
        theme={{
          labels: {
            text: {
              fill: 'var(--color-text-muted)',
              fontSize: 11,
              fontFamily: 'var(--font-body)',
              fontWeight: 600,
            }
          },
          tooltip: {
            container: {
              background: 'var(--color-surface)',
              color: 'var(--color-text-primary)',
              fontSize: 12,
              borderRadius: '8px',
              border: '1px solid var(--color-border)',
              boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
            }
          }
        }}
      />
    </div>
  );
}
