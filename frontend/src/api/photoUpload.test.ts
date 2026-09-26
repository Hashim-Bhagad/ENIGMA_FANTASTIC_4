import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ImageManipulatorContext } from 'expo-image-manipulator';
import { BARCODE_PHOTO_LIMIT_BYTES, LABEL_PHOTO_LIMIT_BYTES, needsPhotoResize, PHOTO_MAX_EDGE_PX, photoSizeWarning } from './client';

// A phone camera reports several thousand pixels a side, so this file runs as the native client:
// the browser path never touches the manipulator, and fitting a capture to the limit is the point.
vi.mock('react-native', () => ({ Platform: { OS: 'android' } }));
vi.mock('expo-secure-store', () => ({ getItemAsync: vi.fn(), setItemAsync: vi.fn(), deleteItemAsync: vi.fn() }));
vi.mock('expo-image-manipulator', () => ({ ImageManipulator: { manipulate: vi.fn() }, SaveFormat: { JPEG: 'jpeg', PNG: 'png', WEBP: 'webp' } }));

/** What the client handed `fetch`, so the recorded multipart body can be read back. */
type FetchInit = { body?: unknown } & Record<string, unknown>;

/**
 * Node's FormData turns a plain object into the string "[object Object]", so the native upload
 * is captured field by field instead: the file part is what these tests assert.
 */
class RecordingFormData {
  readonly fields: [string, unknown][] = [];
  append(name: string, value: unknown): void { this.fields.push([name, value]); }
  get(name: string): unknown { return this.fields.find(([field]) => field === name)?.[1] ?? null; }
}

/** The `file` part of a recorded body, in the shape the native path appends. */
const uploadedFile = (form: RecordingFormData): { uri: string; name: string; type: string } => form.get('file') as { uri: string; name: string; type: string };

const labelResponse = { food: { name: 'Ragi bites', barcode: '8901234567890' }, confirmation_required: true, saved: true, product_id: 'product-1' };

/** A manipulator context whose render and save answer with the file the app would upload. */
function resizedContext(uri: string, width: number, height: number) {
  const saveAsync = async () => ({ uri, width, height });
  return { resize: vi.fn(), renderAsync: vi.fn(async () => ({ saveAsync, release: vi.fn() })), release: vi.fn() };
}

/** The native context class cannot be built outside the app, so a fake stands in for it. */
const asContext = (context: object): ImageManipulatorContext => context as unknown as ImageManipulatorContext;

describe('phone photos are fitted to a route’s upload limit', () => {
  beforeEach(async () => {
    vi.resetModules();
    delete process.env.EXPO_PUBLIC_API_URL;
    vi.stubGlobal('FormData', RecordingFormData);
    // A module reset re-runs the mock factory, so the stub is taken from the fresh module.
    const manipulator = await import('expo-image-manipulator');
    vi.mocked(manipulator.ImageManipulator.manipulate).mockReset();
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });

  it('resizes only a photo longer than the upload edge', () => {
    expect(needsPhotoResize({ width: 4032, height: 3024 })).toBe(true);
    expect(needsPhotoResize({ width: 3024, height: 4032 })).toBe(true);
    // The edge itself is small enough, so nothing is re-encoded for it.
    expect(needsPhotoResize({ width: PHOTO_MAX_EDGE_PX, height: 1200 })).toBe(false);
    expect(needsPhotoResize({ width: 1600, height: 1600 })).toBe(false);
    // A picker that reported no usable dimensions leaves the photo alone: a guessed resize
    // risks a broken file, and the server's own answer beats a corrupted upload.
    expect(needsPhotoResize({})).toBe(false);
    expect(needsPhotoResize({ width: null, height: null })).toBe(false);
    expect(needsPhotoResize({ width: 0, height: 0 })).toBe(false);
  });

  it('names the size when a photo is still too large to send', () => {
    expect(photoSizeWarning(9 * 1024 * 1024, LABEL_PHOTO_LIMIT_BYTES))
      .toBe('This photo is still 9 MB; the limit is 5 MB. Retake it at a lower resolution.');
    expect(photoSizeWarning(4_800_000, LABEL_PHOTO_LIMIT_BYTES))
      .toBe('This photo is still 4.6 MB; the limit is 5 MB. Retake it at a lower resolution.');
    // 4.5 MB is the warning point itself, so a photo at or below it is sent as it is.
    expect(photoSizeWarning(4.5 * 1024 * 1024, LABEL_PHOTO_LIMIT_BYTES)).toBeNull();
    expect(photoSizeWarning(1_200_000, LABEL_PHOTO_LIMIT_BYTES)).toBeNull();
    // A size nobody reported has no number to show.
    expect(photoSizeWarning(null, LABEL_PHOTO_LIMIT_BYTES)).toBeNull();
    expect(photoSizeWarning(Number.NaN, LABEL_PHOTO_LIMIT_BYTES)).toBeNull();
    // The barcode route takes 8 MB, so the same photo fits there and is warned about later.
    expect(photoSizeWarning(6 * 1024 * 1024, BARCODE_PHOTO_LIMIT_BYTES)).toBeNull();
    expect(photoSizeWarning(8.5 * 1024 * 1024, BARCODE_PHOTO_LIMIT_BYTES))
      .toBe('This photo is still 8.5 MB; the limit is 8 MB. Retake it at a lower resolution.');
  });

  it('shrinks a big label photo and uploads the resized file', async () => {
    const { ImageManipulator } = await import('expo-image-manipulator');
    const context = resizedContext('file:///cache/label-shrunk.jpg', 1600, 1200);
    vi.mocked(ImageManipulator.manipulate).mockReturnValue(asContext(context));
    const fetchMock = vi.fn(async (_url: string, _init?: FetchInit) => ({ ok: true, status: 200, json: async () => labelResponse }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    await api.extractLabel('token', { uri: 'file:///cache/IMG_0042.HEIC', name: 'IMG_0042.HEIC', mimeType: 'image/heic', width: 4032, height: 3024, fileSize: 9 * 1024 * 1024 }, { barcode: ' 8901234567890 ' });

    expect(ImageManipulator.manipulate).toHaveBeenCalledWith('file:///cache/IMG_0042.HEIC');
    // The long edge is capped and the other follows the aspect ratio, so one value is enough.
    expect(context.resize).toHaveBeenCalledWith({ width: PHOTO_MAX_EDGE_PX });
    const form = fetchMock.mock.calls[0]?.[1]?.body as RecordingFormData;
    // The upload is a JPEG with a JPEG name, even though the picker handed back a HEIC.
    expect(uploadedFile(form)).toEqual({ uri: 'file:///cache/label-shrunk.jpg', name: 'IMG_0042.jpg', type: 'image/jpeg' });
    expect(form.get('barcode')).toBe('8901234567890');
    // The context and the rendered image are released once the file is saved.
    expect(context.release).toHaveBeenCalledTimes(1);
  });

  it('caps a portrait photo on its height', async () => {
    const { ImageManipulator } = await import('expo-image-manipulator');
    const context = resizedContext('file:///cache/portrait.jpg', 1200, 1600);
    vi.mocked(ImageManipulator.manipulate).mockReturnValue(asContext(context));
    const fetchMock = vi.fn(async (_url: string, _init?: FetchInit) => ({ ok: true, status: 200, json: async () => labelResponse }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    // A picker that reported no filename still uploads under the label route's own name.
    await api.extractLabel('token', { uri: 'file:///cache/tall.jpg', width: 3024, height: 4032, fileSize: 6 * 1024 * 1024 });
    expect(context.resize).toHaveBeenCalledWith({ height: PHOTO_MAX_EDGE_PX });
    const form = fetchMock.mock.calls[0]?.[1]?.body as RecordingFormData;
    expect(uploadedFile(form).name).toBe('label.jpg');
  });

  it('leaves a photo that already fits alone', async () => {
    const { ImageManipulator } = await import('expo-image-manipulator');
    const fetchMock = vi.fn(async (_url: string, _init?: FetchInit) => ({ ok: true, status: 200, json: async () => labelResponse }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    await api.extractLabel('token', { uri: 'file:///cache/small.jpg', name: 'small.jpg', mimeType: 'image/jpeg', width: 1600, height: 1200, fileSize: 900_000 });
    expect(ImageManipulator.manipulate).not.toHaveBeenCalled();
    const form = fetchMock.mock.calls[0]?.[1]?.body as RecordingFormData;
    expect(uploadedFile(form)).toEqual({ uri: 'file:///cache/small.jpg', name: 'small.jpg', type: 'image/jpeg' });
  });

  it('uploads the picked photo when resizing it fails', async () => {
    const { ImageManipulator } = await import('expo-image-manipulator');
    vi.mocked(ImageManipulator.manipulate).mockImplementation(() => { throw new Error('no image codec on this device'); });
    const fetchMock = vi.fn(async (_url: string, _init?: FetchInit) => ({ ok: true, status: 200, json: async () => labelResponse }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    // Resizing is a convenience: a phone that cannot do it still gets to try the upload.
    await api.extractLabel('token', { uri: 'file:///cache/IMG_0042.HEIC', name: 'IMG_0042.HEIC', mimeType: 'image/heic', width: 4032, height: 3024, fileSize: 3 * 1024 * 1024 });
    const form = fetchMock.mock.calls[0]?.[1]?.body as RecordingFormData;
    expect(uploadedFile(form)).toEqual({ uri: 'file:///cache/IMG_0042.HEIC', name: 'IMG_0042.HEIC', type: 'image/heic' });
  });

  it('refuses a photo that is still over the limit, with its size, before uploading', async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: FetchInit) => ({ ok: true, status: 200, json: async () => labelResponse }));
    vi.stubGlobal('fetch', fetchMock);
    const { api, ApiError } = await import('./client');
    // No dimensions were reported, so the photo stays at its picked size and that is what decides.
    const failure = await api.extractLabel('token', { uri: 'file:///cache/IMG_0042.HEIC', name: 'IMG_0042.HEIC', fileSize: 9 * 1024 * 1024 }).catch((cause: unknown) => cause);
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({ code: 'payload_too_large', message: 'This photo is still 9 MB; the limit is 5 MB. Retake it at a lower resolution.' });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('scans a barcode from a photo with the same resize and the 8 MB limit', async () => {
    const { ImageManipulator } = await import('expo-image-manipulator');
    const context = resizedContext('file:///cache/barcode-shrunk.jpg', 1600, 900);
    vi.mocked(ImageManipulator.manipulate).mockReturnValue(asContext(context));
    const fetchMock = vi.fn(async (_url: string, _init?: FetchInit) => ({ ok: true, status: 200, json: async () => ({ barcode: '8901234567890', format: 'EAN-13', alternatives: [], message: 'Barcode read from the image; look it up to see the product record.' }) }));
    vi.stubGlobal('fetch', fetchMock);
    const { api } = await import('./client');
    const scan = await api.scanBarcode('token', { uri: 'file:///cache/IMG_0043.HEIC', name: 'IMG_0043.HEIC', mimeType: 'image/heic', width: 4032, height: 2268, fileSize: 7 * 1024 * 1024 });
    expect(scan.barcode).toBe('8901234567890');
    expect(context.resize).toHaveBeenCalledWith({ width: PHOTO_MAX_EDGE_PX });
    const form = fetchMock.mock.calls[0]?.[1]?.body as RecordingFormData;
    expect(uploadedFile(form)).toEqual({ uri: 'file:///cache/barcode-shrunk.jpg', name: 'IMG_0043.jpg', type: 'image/jpeg' });
    // A 7 MB barcode photo is under the 8 MB the scan route accepts, so it is sent, not refused.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
