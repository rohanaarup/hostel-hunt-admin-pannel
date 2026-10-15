import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, REQUEST_TIMEOUT_MS, session } from './api';

// The server's side of the conversation: any request without the NEW token gets a 401.
function install(handler?: (config: InternalAxiosRequestConfig) => void) {
  const requests: string[] = [];
  api.defaults.adapter = async (config) => {
    requests.push(`${config.method} ${config.url}`);
    handler?.(config);
    const auth = String(config.headers.get('Authorization') ?? '');
    if (auth !== 'Bearer new-access') {
      throw new AxiosError('Unauthorized', 'ERR_BAD_REQUEST', config, {}, {
        status: 401, statusText: 'Unauthorized', data: { detail: 'Given token not valid' }, headers: {}, config,
      });
    }
    return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config };
  };
  return requests;
}

describe('token refresh', () => {
  let refreshCalls: number;
  let goToLogin: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    localStorage.setItem('access_token', 'old-access');
    localStorage.setItem('refresh_token', 'refresh-1');
    refreshCalls = 0;
    goToLogin = vi.spyOn(session, 'goToLogin').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const refreshReturns = (outcome: 'ok' | 'rejected' | 'unreachable') =>
    vi.spyOn(axios, 'post').mockImplementation(async () => {
      refreshCalls += 1;
      await new Promise((r) => setTimeout(r, 20)); // slow enough for the other requests to pile up
      if (outcome === 'ok') return { data: { access: 'new-access' } };
      if (outcome === 'rejected') throw Object.assign(new Error('refresh refused'), { response: { status: 401 } });
      throw Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK', request: {} });
    });

  it('has a 20 second timeout on every request', () => {
    expect(api.defaults.timeout).toBe(REQUEST_TIMEOUT_MS);
    expect(REQUEST_TIMEOUT_MS).toBe(20_000);
  });

  it('several requests that get a 401 together share ONE refresh (single-flight)', async () => {
    install();
    refreshReturns('ok');

    const results = await Promise.all([api.get('/bookings/'), api.get('/dashboard/stats/'), api.get('/residents/')]);

    expect(refreshCalls).toBe(1);
    expect(results.map((r) => r.data)).toEqual([{ ok: true }, { ok: true }, { ok: true }]);
    expect(localStorage.getItem('access_token')).toBe('new-access');
  });

  it('a later burst refreshes again (the shared refresh is released when it finishes)', async () => {
    install();
    refreshReturns('ok');
    await api.get('/bookings/');
    localStorage.setItem('access_token', 'old-access'); // expired again

    await Promise.all([api.get('/bookings/'), api.get('/residents/')]);

    expect(refreshCalls).toBe(2);
  });

  it('when the server REJECTS the refresh the session ends: tokens cleared, sent to login once', async () => {
    install();
    refreshReturns('rejected');

    await expect(Promise.all([api.get('/bookings/'), api.get('/residents/')])).rejects.toBeTruthy();

    expect(refreshCalls).toBe(1);
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
    expect(goToLogin).toHaveBeenCalled();
  });

  it('when the refresh cannot be tried (no connection) the login is KEPT and the caller gets that failure', async () => {
    install();
    refreshReturns('unreachable');

    const failure = await api.get('/bookings/').catch((e) => e);

    expect(failure.code).toBe('ERR_NETWORK');
    expect(localStorage.getItem('access_token')).toBe('old-access');
    expect(localStorage.getItem('refresh_token')).toBe('refresh-1');
    expect(goToLogin).not.toHaveBeenCalled();
  });

  it('no refresh token at all counts as refused: the session ends', async () => {
    localStorage.removeItem('refresh_token');
    install();
    const post = vi.spyOn(axios, 'post');

    await expect(api.get('/bookings/')).rejects.toBeTruthy();

    expect(post).not.toHaveBeenCalled();
    expect(goToLogin).toHaveBeenCalled();
  });

  it('a 401 from the login route is "wrong password": no refresh, no logout', async () => {
    install();
    const post = vi.spyOn(axios, 'post');

    await expect(api.post('/auth/login/', { identifier: 'x' })).rejects.toBeTruthy();

    expect(post).not.toHaveBeenCalled();
    expect(goToLogin).not.toHaveBeenCalled();
  });

  it('a request is retried only once', async () => {
    const requests = install();
    refreshReturns('ok');
    // the server keeps refusing even the new token
    api.defaults.adapter = async (config) => {
      requests.push(`${config.method} ${config.url}`);
      throw new AxiosError('Unauthorized', 'ERR_BAD_REQUEST', config, {}, {
        status: 401, statusText: '', data: {}, headers: {}, config,
      });
    };

    await expect(api.get('/bookings/')).rejects.toBeTruthy();

    expect(requests.filter((r) => r === 'get /bookings/')).toHaveLength(2);
    expect(refreshCalls).toBe(1);
  });
});
