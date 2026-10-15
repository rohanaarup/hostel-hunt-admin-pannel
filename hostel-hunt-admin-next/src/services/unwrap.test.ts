import { describe, expect, it } from 'vitest';
import { unwrapList, unwrapObject, unwrapPage } from './unwrap';
import { ApiError } from './errors';

// The shapes the backend really answers with (probed on the real routes):
const paged = { count: 25, next: 'http://x/api/v1/bookings/?page=2', previous: null, results: [{ id: 'a' }, { id: 'b' }] };
const envelopeList = { success: true, data: [{ id: 'a' }] };
const stats = { success: true, data: { total_hostels: 2, pending_bookings: 1 } };

describe('unwrapList', () => {
  it('reads a paged reply { count, results } (the shape /bookings/, /residents/ and /notices/ use)', () => {
    expect(unwrapList(paged)).toEqual([{ id: 'a' }, { id: 'b' }]);
  });

  it('reads an envelope { success, data: [...] } (the shape /dashboard/activity/ uses)', () => {
    expect(unwrapList(envelopeList)).toEqual([{ id: 'a' }]);
  });

  it('reads a bare array and { data: [...] }', () => {
    expect(unwrapList([{ id: 'a' }])).toEqual([{ id: 'a' }]);
    expect(unwrapList({ data: [{ id: 'a' }] })).toEqual([{ id: 'a' }]);
  });

  it('reads an envelope that wraps a paged reply', () => {
    expect(unwrapList({ success: true, data: paged })).toHaveLength(2);
  });

  it('an empty list is an empty list', () => {
    expect(unwrapList({ count: 0, next: null, previous: null, results: [] })).toEqual([]);
    expect(unwrapList([])).toEqual([]);
  });

  it('a reply it does not understand is an error, never a silently empty list', () => {
    for (const bad of [null, undefined, 'maintenance', 7, {}, { success: true, data: 'x' }, { detail: 'nope' }]) {
      expect(() => unwrapList(bad), JSON.stringify(bad)).toThrow(ApiError);
    }
    try {
      unwrapList('<html>');
    } catch (e) {
      expect((e as ApiError).kind).toBe('unreadable');
    }
  });

  it('the old bug: reading r.data of a paged reply gave undefined; this does not', () => {
    expect((paged as any).data).toBeUndefined();
    expect(unwrapList(paged)).not.toEqual([]);
  });
});

describe('unwrapPage', () => {
  it('keeps the total and the next page', () => {
    const page = unwrapPage(paged);
    expect(page.count).toBe(25);
    expect(page.next).toBe('http://x/api/v1/bookings/?page=2');
    expect(page.items).toHaveLength(2);
  });

  it('a last page has no next', () => {
    expect(unwrapPage({ count: 2, next: null, previous: null, results: [1, 2] }).next).toBeNull();
  });

  it('a bare array is one page', () => {
    expect(unwrapPage([1, 2, 3])).toEqual({ items: [1, 2, 3], count: 3, next: null });
  });
});

describe('unwrapObject', () => {
  it('reads { success, data: {...} } (the shape /dashboard/stats/ and /auth/me/ use)', () => {
    expect(unwrapObject(stats)).toEqual({ total_hostels: 2, pending_bookings: 1 });
  });

  it('reads a plain object', () => {
    expect(unwrapObject({ total_hostels: 2 })).toEqual({ total_hostels: 2 });
  });

  it('an envelope without data, or a non-object, is an error', () => {
    expect(() => unwrapObject({ success: true })).toThrow(ApiError);
    expect(() => unwrapObject(null)).toThrow(ApiError);
    expect(() => unwrapObject([1])).toThrow(ApiError);
  });
});
