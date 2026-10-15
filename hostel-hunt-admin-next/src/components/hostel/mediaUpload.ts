import type { MediaItem } from '@/types';

/**
 * Rules for the media a hostel form may send, kept apart from the screens so they can be tested.
 *
 * A picture gets a short temporary id the moment it is chosen. Only after it has been uploaded to
 * Cloudinary AND saved on the server does it get the server's real id (a UUID). A temporary id must
 * never reach the server: it fails validation, and the owner could not tell why.
 */

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const isServerId = (id: string | undefined | null): boolean => !!id && UUID.test(id);

/** The ids that are safe to send as `media_ids`: the server's own, nothing temporary. */
export function serverMediaIds(media: MediaItem[] | undefined): string[] {
  return (media ?? []).map((m) => m.id).filter(isServerId);
}

export interface MediaProblems {
  /** Still uploading, or uploaded but not yet saved on the server. */
  uploading: number;
  /** Uploading or saving failed. */
  failed: number;
}

export function mediaProblems(media: MediaItem[] | undefined): MediaProblems {
  let uploading = 0;
  let failed = 0;
  for (const item of media ?? []) {
    if (item.upload_error) failed += 1;
    else if (!isServerId(item.id)) uploading += 1;
  }
  return { uploading, failed };
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** Why the form cannot be submitted yet because of its media, in words; null when it can. */
export function mediaBlockMessage(media: MediaItem[] | undefined): string | null {
  const { uploading, failed } = mediaProblems(media);
  if (uploading > 0) {
    return `${plural(uploading, 'file is', 'files are')} still uploading. Wait for the upload to finish, then continue.`;
  }
  if (failed > 0) {
    return `${plural(failed, 'file', 'files')} could not be uploaded. Remove ${failed === 1 ? 'it' : 'them'} (or add ${failed === 1 ? 'it' : 'them'} again) in the Media step, then continue.`;
  }
  return null;
}
