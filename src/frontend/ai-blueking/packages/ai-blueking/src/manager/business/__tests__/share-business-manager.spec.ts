import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref, shallowRef } from 'vue';

import { ShareBusinessManager } from '../share-business-manager';

function createMocks() {
  const mockMessageModule = {
    list: shallowRef([]),
    isListLoading: ref(false),
    deleteMessages: vi.fn().mockResolvedValue(undefined),
    shareMessages: vi.fn().mockResolvedValue({
      share_page: 'https://example.com/',
      share_token: 'abc123',
    }),
  };
  const mockSessionModule = {
    current: ref({ sessionCode: 'session-1' }),
    renameSession: vi.fn().mockResolvedValue(undefined),
    list: ref([]),
  };

  return { mockMessageModule, mockSessionModule };
}

describe('ShareBusinessManager', () => {
  let manager: ShareBusinessManager;
  let mocks: ReturnType<typeof createMocks>;

  beforeEach(() => {
    vi.clearAllMocks();
    mocks = createMocks();
    manager = new ShareBusinessManager(
      mocks.mockMessageModule as any,
      mocks.mockSessionModule as any,
    );
  });

  it('should call messageModule.shareMessages and return shareUrl with userMessageIds', async () => {
    const messages = [
      { id: '1', role: 'user', content: 'hello' },
      { id: '2', role: 'user', content: 'world' },
    ];

    const result = await manager.shareMessages(messages as any);

    expect(mocks.mockMessageModule.shareMessages).toHaveBeenCalledWith('session-1', messages);
    expect(result.shareUrl).toBe('https://example.com/share-page/abc123');
    expect(result.userMessageIds).toEqual(['1', '2']);
  });

  it('should throw when messages array is empty', async () => {
    await expect(manager.shareMessages([])).rejects.toThrow('No messages to share');
  });

  it('should throw when no active session', async () => {
    mocks.mockSessionModule.current = ref({ sessionCode: '' }) as any;
    manager = new ShareBusinessManager(
      mocks.mockMessageModule as any,
      mocks.mockSessionModule as any,
    );

    const messages = [{ id: '1', role: 'user', content: 'hello' }];
    await expect(manager.shareMessages(messages as any)).rejects.toThrow('No active session');
  });

  it('should throw when API returns null', async () => {
    mocks.mockMessageModule.shareMessages.mockResolvedValue(null);

    const messages = [{ id: '1', role: 'user', content: 'hello' }];
    await expect(manager.shareMessages(messages as any)).rejects.toThrow(
      'Share failed: no result returned',
    );
  });

  it('should construct shareUrl from share_page and share_token', async () => {
    mocks.mockMessageModule.shareMessages.mockResolvedValue({
      share_page: 'https://other.com/path/',
      share_token: 'token-xyz',
    });

    const messages = [{ id: '10', role: 'user', content: 'test' }];
    const result = await manager.shareMessages(messages as any);

    expect(result.shareUrl).toBe('https://other.com/path/share-page/token-xyz');
  });
});
