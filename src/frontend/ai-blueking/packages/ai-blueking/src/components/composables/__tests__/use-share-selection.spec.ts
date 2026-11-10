/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { ref, shallowRef } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createMockAIMessage, createMockChatHelper, createMockEmit } from '../../../__tests__/helpers';

vi.mock('@blueking/chat-x', async importOriginal => {
  const actual = await importOriginal<typeof import('@blueking/chat-x')>();
  return {
    ...actual,
    useToast: () => vi.fn(),
  };
});

const shareMessagesMock = vi.fn().mockResolvedValue({
  shareUrl: 'https://example.com/share',
  userMessageIds: ['1'],
});

vi.mock('../../../manager/business/share-business-manager', () => ({
  ShareBusinessManager: vi.fn().mockImplementation(() => ({
    shareMessages: shareMessagesMock,
  })),
}));

vi.mock('../../../utils', async importOriginal => {
  const actual = await importOriginal<typeof import('../../../utils')>();
  return {
    ...actual,
    copyToClipboard: vi.fn().mockResolvedValue(true),
  };
});

import { ShareBusinessManager } from '../../../manager/business/share-business-manager';
import { useShareSelection } from '../use-share-selection';

import type { UseShareSelectionParams } from '../use-share-selection';

function createParams(overrides: Partial<UseShareSelectionParams> = {}): UseShareSelectionParams {
  return {
    emit: createMockEmit(),
    chatHelper: shallowRef(createMockChatHelper()),
    isStandaloneMode: ref(true),
    ...overrides,
  };
}

describe('useShareSelection', () => {
  beforeEach(() => {
    shareMessagesMock.mockClear();
    vi.mocked(ShareBusinessManager).mockClear();
  });

  describe('handleConfirmShare', () => {
    it('should call ShareBusinessManager.shareMessages in standalone mode for builtin share', async () => {
      const params = createParams({ isStandaloneMode: ref(true) });
      const { handleConfirmShare } = useShareSelection(params);

      const messages = [createMockAIMessage()] as any;
      await handleConfirmShare(messages);

      expect(ShareBusinessManager).toHaveBeenCalled();
      expect(params.emit).toHaveBeenCalledWith('confirm-share', messages, undefined);
    });

    it('should call ShareBusinessManager when source.id is share', async () => {
      const params = createParams({ isStandaloneMode: ref(true) });
      const { handleConfirmShare } = useShareSelection(params);

      const messages = [createMockAIMessage()] as any;
      const source = { id: 'share' };
      await handleConfirmShare(messages, source as any);

      expect(ShareBusinessManager).toHaveBeenCalled();
      expect(params.emit).toHaveBeenCalledWith('confirm-share', messages, source);
    });

    it('should not call ShareBusinessManager for custom triggerSelection source', async () => {
      const params = createParams({ isStandaloneMode: ref(true) });
      const { handleConfirmShare } = useShareSelection(params);

      const messages = [createMockAIMessage()] as any;
      const source = { id: 'save', triggerSelection: true };
      await handleConfirmShare(messages, source as any);

      expect(ShareBusinessManager).not.toHaveBeenCalled();
      expect(params.emit).toHaveBeenCalledWith('confirm-share', messages, source);
    });

    it('should only emit confirm-share in integration mode', async () => {
      const params = createParams({ isStandaloneMode: ref(false) });
      const { handleConfirmShare } = useShareSelection(params);

      const messages = [createMockAIMessage()] as any;
      await handleConfirmShare(messages);

      expect(ShareBusinessManager).not.toHaveBeenCalled();
      expect(params.emit).toHaveBeenCalledWith('confirm-share', messages, undefined);
    });

    it('should not call ShareBusinessManager when chatHelper is null', async () => {
      const params = createParams({ isStandaloneMode: ref(true), chatHelper: shallowRef(null) });
      const { handleConfirmShare } = useShareSelection(params);

      await handleConfirmShare([createMockAIMessage()] as any);

      expect(params.emit).toHaveBeenCalledWith('confirm-share', expect.any(Array), undefined);
    });
  });
});
