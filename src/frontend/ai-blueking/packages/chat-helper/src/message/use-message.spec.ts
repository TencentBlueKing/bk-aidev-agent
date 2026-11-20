/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { describe, expect, it, vi } from 'vitest';

import { MessageRole, MessageStatus } from './type';
import { useMessage } from './use-message';

import type { IMediatorModule } from '../mediator';
import type { IMessage } from './type';

describe('useMessage.syncMessageIds', () => {
  it('backfills missing ids by messageId without replacing the list', async () => {
    const server = [
      { id: '20', messageId: 'user-1', role: MessageRole.User, status: MessageStatus.Complete, content: 'hi' },
      { id: '21', messageId: 'stream-a', role: MessageRole.Assistant, status: MessageStatus.Complete, content: 'ok' },
    ] as IMessage[];
    const mediator = {
      http: { message: { getMessages: vi.fn().mockResolvedValue(server) } },
    } as unknown as IMediatorModule;
    const message = useMessage(mediator);
    message.list.value = [
      { id: '20', messageId: 'user-1', role: MessageRole.User, status: MessageStatus.Complete, content: 'hi' },
      { messageId: 'stream-a', role: MessageRole.Assistant, status: MessageStatus.Complete, content: 'ok' },
      { messageId: 'stream-b', role: MessageRole.Assistant, status: MessageStatus.Complete, content: 'extra' },
    ] as IMessage[];
    const listRef = message.list.value;

    const result = await message.syncMessageIds('s1');

    expect(mediator.http?.message.getMessages).toHaveBeenCalledWith('s1');
    expect(result).toBe(server);
    expect(message.list.value).toBe(listRef);
    expect(message.list.value[1].id).toBe('21');
    expect(message.list.value[2].id).toBeUndefined();
  });
});
