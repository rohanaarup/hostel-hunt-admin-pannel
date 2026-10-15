import { describe, expect, it } from 'vitest';
import { ApiError, errorMessage, isClientError, toApiError } from './errors';

// A minimal stand-in for what axios throws.
const http = (status: number, data: unknown, headers: Record<string, string> = {}) => ({
  message: `Request failed with status code ${status}`,
  response: { status, data, headers },
});

describe('error wording (the same as the mobile app)', () => {
  it('the envelope: the specific field message wins', () => {
    const e = toApiError(http(400, { success: false, message: 'Error', errors: { media_ids: ['Must be a valid UUID.'] } }));
    expect(e.kind).toBe('validation');
    expect(e.message).toBe('Must be a valid UUID.');
    expect(e.fieldErrors.media_ids).toBe('Must be a valid UUID.');
  });

  it('plain DRF field errors, non_field_errors and bare lists', () => {
    expect(errorMessage(http(400, { gender: ['"robot" is not a valid choice.'] }))).toBe('"robot" is not a valid choice.');
    expect(errorMessage(http(400, { non_field_errors: ['Passwords do not match.'] }))).toBe('Passwords do not match.');
    expect(errorMessage(http(400, ['Something is wrong.']))).toBe('Something is wrong.');
  });

  it('401 says the session expired; the login envelope keeps the server wording', () => {
    expect(errorMessage(http(401, { detail: 'Given token not valid' }))).toBe('Your session has expired. Please log in again.');
    expect(errorMessage(http(401, { success: false, message: 'Invalid credentials.', errors: {} }))).toBe('Invalid credentials.');
  });

  it('403, 404 and 405 use our words, never the raw detail', () => {
    expect(errorMessage(http(403, { detail: 'You do not have permission to perform this action.' }))).toBe("You don't have permission to do that.");
    expect(errorMessage(http(404, '<html>Not Found</html>'))).toBe("We couldn't find that.");
    expect(errorMessage(http(405, { detail: 'Method "PATCH" not allowed.' }))).not.toContain('PATCH');
  });

  it('429 reads Retry-After, or the number in the detail', () => {
    expect(errorMessage(http(429, { detail: 'x' }, { 'retry-after': '37' }))).toBe('Too many attempts. Try again in 37 seconds.');
    expect(errorMessage(http(429, { detail: 'Request was throttled. Expected available in 120 seconds.' }))).toBe('Too many attempts. Try again in 2 minutes.');
  });

  it('a proxy page while the server wakes up is "starting up"', () => {
    for (const status of [502, 503, 504]) {
      const e = toApiError(http(status, '<html>Bad gateway</html>'));
      expect(e.kind).toBe('unavailable');
      expect(e.message).toBe('The server is starting up. Please try again in a few seconds.');
    }
  });

  it('other 5xx', () => {
    expect(errorMessage(http(500, { detail: 'oops' }))).toBe('The server had a problem. Please try again in a moment.');
  });

  it('timeout and no connection', () => {
    expect(toApiError({ code: 'ECONNABORTED', message: 'timeout of 20000ms exceeded' }).kind).toBe('timeout');
    expect(toApiError({ code: 'ERR_NETWORK', message: 'Network Error', request: {} }).kind).toBe('offline');
    expect(errorMessage({ code: 'ERR_NETWORK', request: {} })).toBe('No internet connection. Check your network and try again.');
  });

  it('a bug is "something went wrong", never its own text', () => {
    const e = toApiError(new TypeError("Cannot read properties of undefined (reading 'map')"));
    expect(e.kind).toBe('unexpected');
    expect(e.message).toBe('Something went wrong. Please try again.');
  });

  it('an ApiError passes through, and no message holds HTML or a stack trace', () => {
    const own = new ApiError('server', 'x', 500);
    expect(toApiError(own)).toBe(own);
    for (const reply of [http(500, '<html>Traceback (most recent call last)'), http(400, '<html>'), http(500, { detail: 'x' })]) {
      expect(errorMessage(reply)).not.toMatch(/[<{]|Traceback/);
    }
  });
});

describe('isClientError', () => {
  it('is true for 4xx answers that asking again will not fix', () => {
    expect(isClientError(http(400, {}))).toBe(true);
    expect(isClientError(http(404, {}))).toBe(true);
  });

  it('is false for throttling, 5xx and no connection', () => {
    expect(isClientError(http(429, {}))).toBe(false);
    expect(isClientError(http(503, {}))).toBe(false);
    expect(isClientError({ code: 'ERR_NETWORK', request: {} })).toBe(false);
  });
});
