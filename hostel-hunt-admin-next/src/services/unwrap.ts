import { ApiError } from './errors';

/**
 * The backend answers lists and objects in more than one shape. Every page reads them through these
 * helpers, so a page can never again read `r.data` from a `{ count, results }` reply and show an
 * empty list while the server had rows.
 *
 *   list:    [..]  |  { results: [..] }  |  { data: [..] }  |  { success, data: [..] }  |  { data: { results: [..] } }
 *   object:  { success, data: {..} }  |  { data: {..} }  |  {..}
 *
 * A reply that is none of these is an error ("the server sent a reply the app couldn't read"), not an
 * empty list: an empty list that is really a misread reply is the bug these helpers exist to prevent.
 */

export interface Page<T> {
  items: T[];
  /** How many there are in total on the server (not just on this page). */
  count: number;
  /** The address of the next page, or null on the last one. */
  next: string | null;
}

const unreadable = () => new ApiError('unreadable', "The server sent a reply the app couldn't read. Please try again.");

const isRecord = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);

export function unwrapPage<T>(res: unknown): Page<T> {
  if (Array.isArray(res)) return { items: res as T[], count: res.length, next: null };
  if (!isRecord(res)) throw unreadable();

  if (Array.isArray(res.results)) {
    return {
      items: res.results as T[],
      count: typeof res.count === 'number' ? res.count : res.results.length,
      next: typeof res.next === 'string' ? res.next : null,
    };
  }
  if (Array.isArray(res.data)) return { items: res.data as T[], count: res.data.length, next: null };
  if (isRecord(res.data)) return unwrapPage<T>(res.data); // { success, data: { count, results } }
  throw unreadable();
}

export function unwrapList<T>(res: unknown): T[] {
  return unwrapPage<T>(res).items;
}

export function unwrapObject<T>(res: unknown): T {
  if (!isRecord(res)) throw unreadable();
  if ('success' in res || 'data' in res) {
    if (isRecord(res.data)) return res.data as T;
    throw unreadable();
  }
  return res as T;
}
