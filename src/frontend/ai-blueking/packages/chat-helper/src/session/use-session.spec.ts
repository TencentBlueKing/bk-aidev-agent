/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { ref } from 'vue';
import { describe, expect, it, vi } from 'vitest';

import { useSession } from './use-session';

import type { IMediatorModule } from '../mediator';

const createMediator = (sdkVersion?: string): IMediatorModule => {
  const uploadFile = vi.fn().mockResolvedValue({ download_url: 'https://legacy.example/file.png' });
  const uploadPvFiles = vi.fn().mockResolvedValue({
    count: 1,
    succeeded: 1,
    failed: 0,
    results: [
      {
        type: 'file',
        id: 'files/photo.png',
        path: 'files/photo.png',
        name: 'photo.png',
        mime_type: 'image/png',
        size: 12,
        status: 'success',
        download_url: 'https://pv.example/photo.png',
      },
    ],
  });

  return {
    agent: {
      info: ref(sdkVersion ? { agentSdkVersion: sdkVersion } : {}),
    },
    http: {
      session: {
        uploadFile,
        uploadPvFiles,
      },
    },
  } as unknown as IMediatorModule;
};

describe('useSession.uploadFile', () => {
  const file = new File(['img'], 'photo.png', { type: 'image/png' });

  it('uses legacy upload when agent_sdk_version is before 2.2.2rc25', async () => {
    const mediator = createMediator('2.2.2rc17');
    const session = useSession(mediator);

    const result = await session.uploadFile('s1', file);

    expect(mediator.http?.session.uploadFile).toHaveBeenCalledWith('s1', file);
    expect(mediator.http?.session.uploadPvFiles).not.toHaveBeenCalled();
    expect(result).toEqual({ download_url: 'https://legacy.example/file.png' });
  });

  it('uses legacy upload when agent_sdk_version is missing', async () => {
    const mediator = createMediator();
    const session = useSession(mediator);

    await session.uploadFile('s1', file);

    expect(mediator.http?.session.uploadFile).toHaveBeenCalled();
    expect(mediator.http?.session.uploadPvFiles).not.toHaveBeenCalled();
  });

  it('uses pv_files upload when agent_sdk_version is 2.2.2rc25 or later', async () => {
    const mediator = createMediator('2.2.2rc25');
    const session = useSession(mediator);

    const result = await session.uploadFile('s1', file);

    expect(mediator.http?.session.uploadPvFiles).toHaveBeenCalledWith('s1', [file]);
    expect(mediator.http?.session.uploadFile).not.toHaveBeenCalled();
    expect(result).toMatchObject({ id: 'files/photo.png', status: 'success' });
  });
});
