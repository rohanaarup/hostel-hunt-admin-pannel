import { describe, expect, it } from 'vitest';
import { isServerId, mediaBlockMessage, mediaProblems, serverMediaIds } from './mediaUpload';
import type { MediaItem } from '@/types';

const REAL = '6f9619ff-8b86-4d11-b42d-00c04fc964ff';

const item = (over: Partial<MediaItem>): MediaItem => ({
  id: 'k3j2h1x9', // a temporary id: 8 characters
  preview_url: 'blob:x',
  category: 'hostel',
  upload_progress: 0,
  mime_type: 'image/jpeg',
  file_name: 'a.jpg',
  order_index: 0,
  ...over,
});

describe('which ids may be sent to the server', () => {
  it('only real UUIDs: a temporary id is never sent (the failing sequence of X17)', () => {
    const media = [item({ id: REAL, upload_progress: 100 }), item({ id: 'k3j2h1x9' }), item({ id: 'zzzzzzzz' })];
    expect(serverMediaIds(media)).toEqual([REAL]);
  });

  it('is empty for no media', () => {
    expect(serverMediaIds(undefined)).toEqual([]);
    expect(serverMediaIds([])).toEqual([]);
  });

  it('recognises a UUID in any letter case', () => {
    expect(isServerId(REAL.toUpperCase())).toBe(true);
    expect(isServerId('k3j2h1x9')).toBe(false);
    expect(isServerId('')).toBe(false);
    expect(isServerId(undefined)).toBe(false);
  });
});

describe('what blocks the form', () => {
  it('nothing blocks when every picture has been saved on the server', () => {
    expect(mediaBlockMessage([item({ id: REAL, upload_progress: 100 })])).toBeNull();
    expect(mediaBlockMessage([])).toBeNull();
  });

  it('a picture still uploading blocks, and says so', () => {
    const media = [item({ id: REAL }), item({ id: 'k3j2h1x9', upload_progress: 40 }), item({ id: 'a1b2c3d4', upload_progress: 100 })];
    expect(mediaProblems(media)).toEqual({ uploading: 2, failed: 0 });
    expect(mediaBlockMessage(media)).toBe('2 files are still uploading. Wait for the upload to finish, then continue.');
  });

  it('uploaded to the cloud but not yet saved on the server still counts as uploading', () => {
    expect(mediaBlockMessage([item({ id: 'k3j2h1x9', upload_progress: 100 })])).toContain('still uploading');
  });

  it('a failed picture blocks until it is removed', () => {
    const media = [item({ id: 'k3j2h1x9', upload_error: 'The server had a problem.' })];
    expect(mediaProblems(media)).toEqual({ uploading: 0, failed: 1 });
    expect(mediaBlockMessage(media)).toBe('1 file could not be uploaded. Remove it (or add it again) in the Media step, then continue.');
  });

  it('removing the failed picture unblocks', () => {
    expect(mediaBlockMessage([item({ id: REAL })])).toBeNull();
  });
});
