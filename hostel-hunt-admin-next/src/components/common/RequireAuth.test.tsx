import React from 'react';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const replace = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace, push: vi.fn() }) }));

let auth = { isReady: false, isAuthenticated: false };
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => auth }));

import RequireAuth from './RequireAuth';

describe('the route guard', () => {
  beforeEach(() => {
    replace.mockClear();
  });

  it('shows a spinner and does NOT redirect before the saved login has been read', () => {
    auth = { isReady: false, isAuthenticated: false };
    render(<RequireAuth><p>secret page</p></RequireAuth>);

    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByText('secret page')).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it('sends a logged-out visitor to /login and renders none of the page', () => {
    auth = { isReady: true, isAuthenticated: false };
    render(<RequireAuth><p>secret page</p></RequireAuth>);

    expect(replace).toHaveBeenCalledWith('/login');
    expect(screen.queryByText('secret page')).not.toBeInTheDocument();
  });

  it('shows the page to a signed-in owner', () => {
    auth = { isReady: true, isAuthenticated: true };
    render(<RequireAuth><p>secret page</p></RequireAuth>);

    expect(screen.getByText('secret page')).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
