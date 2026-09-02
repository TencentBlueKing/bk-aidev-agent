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
      info: ref(sdkVersion === undefined ? {} : { agentSdkVersion: sdkVersion }),
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

  it('uses pv_files upload when agent_sdk_version is missing', async () => {
    const mediator = createMediator();
    const session = useSession(mediator);

    await session.uploadFile('s1', file);

    expect(mediator.http?.session.uploadPvFiles).toHaveBeenCalledWith('s1', [file]);
    expect(mediator.http?.session.uploadFile).not.toHaveBeenCalled();
  });

  it('uses pv_files upload when agent_sdk_version is empty', async () => {
    const mediator = createMediator('');
    const session = useSession(mediator);

    await session.uploadFile('s1', file);

    expect(mediator.http?.session.uploadPvFiles).toHaveBeenCalledWith('s1', [file]);
    expect(mediator.http?.session.uploadFile).not.toHaveBeenCalled();
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

describe('useSession.uploadFiles', () => {
  it('sends all files in one pv_files request', async () => {
    const mediator = createMediator('2.2.2rc25');
    const session = useSession(mediator);
    const fileA = new File(['a'], 'a.png', { type: 'image/png' });
    const fileB = new File(['b'], 'b.png', { type: 'image/png' });
    (mediator.http?.session.uploadPvFiles as ReturnType<typeof vi.fn>).mockResolvedValue({
      count: 2,
      succeeded: 2,
      failed: 0,
      results: [
        {
          type: 'file',
          id: 'files/a.png',
          path: 'files/a.png',
          name: 'a.png',
          mime_type: 'image/png',
          size: 1,
          status: 'success',
        },
        {
          type: 'file',
          id: 'files/b.png',
          path: 'files/b.png',
          name: 'b.png',
          mime_type: 'image/png',
          size: 1,
          status: 'success',
        },
      ],
    });

    const results = await session.uploadFiles('s1', [fileA, fileB]);

    expect(mediator.http?.session.uploadPvFiles).toHaveBeenCalledTimes(1);
    expect(mediator.http?.session.uploadPvFiles).toHaveBeenCalledWith('s1', [fileA, fileB]);
    expect(mediator.http?.session.uploadFile).not.toHaveBeenCalled();
    expect(results).toHaveLength(2);
  });
});
