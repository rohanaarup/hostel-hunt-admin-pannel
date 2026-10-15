/**
 * One place that turns "something went wrong talking to the server" into words an owner can act on.
 * The same shapes and the same wording as the mobile app's error reader:
 *   - the envelope        { success: false, message, errors: { field: "text" | ["text"] } }
 *   - plain DRF           { detail } (401, 403, 404, 405, 429, 5xx) and { field: ["text"] }
 *   - an HTML proxy page  (502/503/504 while the server wakes up; a wrong route's 404)
 *   - transport failures  timeout, no connection, an unreadable reply
 * Pages never format an error themselves: they call errorMessage(error).
 */

export type ApiErrorKind =
  | 'offline'
  | 'timeout'
  | 'unauthorized'
  | 'forbidden'
  | 'notFound'
  | 'validation'
  | 'throttled'
  | 'server'
  | 'unavailable'
  | 'unreadable'
  | 'unexpected';

export class ApiError extends Error {
  kind: ApiErrorKind;
  status: number;
  fieldErrors: Record<string, string>;
  retryAfterSeconds?: number;

  constructor(
    kind: ApiErrorKind,
    message: string,
    status = 0,
    fieldErrors: Record<string, string> = {},
    retryAfterSeconds?: number,
  ) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = status;
    this.fieldErrors = fieldErrors;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

const OFFLINE = 'No internet connection. Check your network and try again.';
const TIMEOUT = 'The server took too long to answer. Check your connection and try again.';
const UNEXPECTED = 'Something went wrong. Please try again.';

/** The first non-empty string inside a string, array or object. */
function firstText(value: unknown): string | undefined {
  if (typeof value === 'string') return value.trim() || undefined;
  if (Array.isArray(value)) {
    for (const item of value) {
      const text = firstText(item);
      if (text) return text;
    }
  } else if (value && typeof value === 'object') {
    for (const item of Object.values(value)) {
      const text = firstText(item);
      if (text) return text;
    }
  }
  return undefined;
}

function fieldMap(errors: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  if (errors && typeof errors === 'object' && !Array.isArray(errors)) {
    for (const [key, value] of Object.entries(errors)) {
      const text = firstText(value);
      if (text) out[key] = text;
    }
  }
  return out;
}

const NOT_FIELDS = new Set(['detail', 'code', 'messages', 'success', 'message', 'errors']);

function throttledMessage(seconds?: number): string {
  if (!seconds || seconds <= 0) return 'Too many attempts. Please wait a moment and try again.';
  if (seconds < 60) return `Too many attempts. Try again in ${seconds} ${seconds === 1 ? 'second' : 'seconds'}.`;
  const minutes = Math.ceil(seconds / 60);
  return `Too many attempts. Try again in ${minutes} ${minutes === 1 ? 'minute' : 'minutes'}.`;
}

interface AxiosLikeError {
  code?: string;
  message?: string;
  response?: { status?: number; data?: unknown; headers?: Record<string, unknown> };
  request?: unknown;
}

/** Any thrown value as an ApiError (an ApiError passes through unchanged). */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  const e = (error ?? {}) as AxiosLikeError;

  const response = e.response;
  if (!response) {
    if (e.code === 'ECONNABORTED' || e.code === 'ETIMEDOUT' || /timeout/i.test(e.message ?? '')) {
      return new ApiError('timeout', TIMEOUT);
    }
    // axios sets `request` when it sent something and heard nothing: the network is the problem.
    if (e.request !== undefined || e.code === 'ERR_NETWORK') return new ApiError('offline', OFFLINE);
    return new ApiError('unexpected', UNEXPECTED);
  }

  const status = response.status ?? 0;
  const data = response.data;
  const body = data && typeof data === 'object' && !Array.isArray(data) ? (data as Record<string, unknown>) : undefined;
  const detail = typeof body?.detail === 'string' ? (body.detail as string) : undefined;

  // The envelope: text the server wrote for people wins over the generic wording.
  let custom: string | undefined;
  let fields: Record<string, string> = {};
  if (body && body.success === false) {
    fields = fieldMap(body.errors);
    custom = Object.values(fields)[0] ?? firstText(body.message);
  } else if (body) {
    // plain DRF field errors: { field: ["text"] }
    fields = fieldMap(Object.fromEntries(Object.entries(body).filter(([k]) => !NOT_FIELDS.has(k))));
    custom = firstText(body.non_field_errors) ?? Object.values(fields)[0];
  } else if (Array.isArray(data)) {
    custom = firstText(data);
  }
  const envelopeText = body && body.success === false ? custom : undefined;

  const make = (kind: ApiErrorKind, standard: string, retry?: number) =>
    new ApiError(kind, envelopeText ?? standard, status, fields, retry);

  switch (status) {
    case 401:
      return make('unauthorized', 'Your session has expired. Please log in again.');
    case 403:
      return make('forbidden', "You don't have permission to do that.");
    case 404:
      return make('notFound', "We couldn't find that.");
    case 405:
      return make('unexpected', "This isn't supported by the server yet. Please refresh the page.");
    case 408:
      return make('timeout', TIMEOUT);
    case 413:
      return make('validation', 'That file is too large to upload.');
    case 429: {
      const header = Number(response.headers?.['retry-after']);
      const fromDetail = Number(/(\d+)\s*second/.exec(detail ?? '')?.[1]);
      const seconds = header > 0 ? header : fromDetail > 0 ? fromDetail : undefined;
      return make('throttled', throttledMessage(seconds), seconds);
    }
    case 502:
    case 503:
    case 504:
      return make('unavailable', 'The server is starting up. Please try again in a few seconds.');
  }
  if (status >= 500) return make('server', 'The server had a problem. Please try again in a moment.');
  return new ApiError(
    'validation',
    envelopeText ?? custom ?? 'The request was not accepted. Please check your details and try again.',
    status,
    fields,
  );
}

/** The text to show for any error caught in a page. Never an exception name, HTML or a stack trace. */
export function errorMessage(error: unknown): string {
  return toApiError(error).message;
}

/** True for failures that retrying will not fix (a 4xx other than a timeout or throttle). */
export function isClientError(error: unknown): boolean {
  const e = toApiError(error);
  return e.status >= 400 && e.status < 500 && e.kind !== 'timeout' && e.kind !== 'throttled';
}
