import React from 'react';
import { fireEvent, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { httpError, renderWithQueryClient } from '@/test-utils';

const api = vi.hoisted(() => ({
  residentService: { getResidents: vi.fn(), createResident: vi.fn(), markResidentVacated: vi.fn() },
  hostelService: { getHostels: vi.fn(), getDashboardStats: vi.fn() },
}));
vi.mock('@/services/api', () => api);
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ isReady: true, isAuthenticated: true }) }));
vi.mock('gsap', () => ({ default: { fromTo: vi.fn(), to: vi.fn() } }));
vi.mock('@/components/common/DashboardLayout', () => ({ default: ({ children }: any) => <div>{children}</div> }));

import ResidentsPage from './page';

const resident = (id: string, name: string) => ({
  id, name, phone: '9000000001', status: 'active', hostel: 'h1', hostel_name: 'Sunrise PG', room: 'Room 101',
  bed_number: '2', move_in_date: '2026-09-01', id_proof_type: 'Aadhaar', id_proof_number: 'x',
  emergency_contact_name: 'y', emergency_contact_phone: '9000000002', created_at: '2026-09-01T10:00:00Z',
});

const paged = (rows: unknown[], over: Record<string, unknown> = {}) => ({
  count: rows.length, next: null, previous: null, results: rows, ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  api.hostelService.getHostels.mockResolvedValue(paged([{ hostel_id: 'h1', name: 'Sunrise PG' }]));
});

describe('the Residents page reads the paged reply (X15: it used to show an empty list always)', () => {
  it('shows the residents of a { count, results } reply', async () => {
    api.residentService.getResidents.mockResolvedValue(paged([resident('r1', 'Asha Rao')], { count: 40, next: 'x' }));

    renderWithQueryClient(<ResidentsPage />);

    expect(await screen.findByText('Asha Rao')).toBeInTheDocument();
    expect(screen.getByText('Showing 1 of 40 residents')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Load more' })).toBeInTheDocument();
  });

  it('the hostel choices in the form come from the paged hostels reply', async () => {
    api.residentService.getResidents.mockResolvedValue(paged([resident('r1', 'Asha Rao')]));

    renderWithQueryClient(<ResidentsPage />);
    await screen.findByText('Asha Rao');
    fireEvent.click(screen.getByRole('button', { name: /add resident/i }));

    expect(await screen.findByRole('option', { name: 'Sunrise PG' })).toBeInTheDocument();
  });

  it('says there are no residents only when there really are none', async () => {
    api.residentService.getResidents.mockResolvedValue(paged([]));

    renderWithQueryClient(<ResidentsPage />);

    expect(await screen.findByText('No residents yet')).toBeInTheDocument();
  });

  it('shows the reason and a Retry when the residents cannot be loaded', async () => {
    api.residentService.getResidents
      .mockRejectedValueOnce(httpError(500, { detail: 'oops' }))
      .mockResolvedValue(paged([resident('r1', 'Asha Rao')]));

    renderWithQueryClient(<ResidentsPage />);

    expect(await screen.findByText('Could not load residents')).toBeInTheDocument();
    expect(screen.queryByText('No residents yet')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(await screen.findByText('Asha Rao')).toBeInTheDocument();
  });
});
