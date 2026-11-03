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

import {
  transferSession2SessionApi,
  transferSessionApi2Session,
  transferSessionListItemApi2Session,
} from '../http/transform/session';
import { useSession } from './use-session';

import type { IMediatorModule } from '../mediator';

const createMediator = (sdkVersion?: string): IMediatorModule => {
  const uploadFile = vi.fn().mockResolvedValue({ download_url: 'https://legacy.example/file.png' });
  const deletePvFile = vi.fn().mockResolvedValue(undefined);
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
        deletePvFile,
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

describe('useSession.deletePvFile', () => {
  it('forwards sessionCode and raw path to HTTP without encoding', async () => {
    const mediator = createMediator();
    const session = useSession(mediator);
    const path = 'files/report.pdf';

    await session.deletePvFile('s-abc', path);

    expect(mediator.http?.session.deletePvFile).toHaveBeenCalledTimes(1);
    expect(mediator.http?.session.deletePvFile).toHaveBeenCalledWith('s-abc', path);
    expect(mediator.http?.session.deletePvFile).not.toHaveBeenCalledWith(
      's-abc',
      encodeURIComponent(path),
    );
  });
});

describe('session reasoning effort transform', () => {
  it('list items leave omitted fields absent instead of null', () => {
    const item = transferSessionListItemApi2Session({ session_code: 's1', session_name: 'chat' });
    expect(item).not.toHaveProperty('effectiveReasoningEffort');
    expect(item).not.toHaveProperty('reasoningEffort');

    expect(
      transferSessionListItemApi2Session({ reasoning_effort: 'low', session_code: 's1', session_name: 'chat' }),
    ).toEqual(expect.objectContaining({ reasoningEffort: 'low' }));
  });

  it('detail maps fields and treats omitted values as null', () => {
    expect(
      transferSessionApi2Session({
        effective_reasoning_effort: 'medium',
        reasoning_effort: 'medium',
        session_code: 's1',
        session_name: 'chat',
      }),
    ).toEqual(
      expect.objectContaining({
        effectiveReasoningEffort: 'medium',
        reasoningEffort: 'medium',
      }),
    );

    expect(
      transferSessionApi2Session({
        session_code: 's1',
        session_name: 'chat',
      }),
    ).toEqual(
      expect.objectContaining({
        effectiveReasoningEffort: null,
        reasoningEffort: null,
      }),
    );
  });

  it('does not send reasoning effort on a generic session update', () => {
    const api = transferSession2SessionApi({
      effectiveReasoningEffort: 'high',
      model: 'hy3',
      reasoningEffort: 'high',
      sessionCode: 's1',
      sessionName: 'chat',
    });

    expect(api).not.toHaveProperty('reasoning_effort');
    expect(api).not.toHaveProperty('effective_reasoning_effort');
    expect(api.model).toBe('hy3');
  });
});

describe('useSession keeps detail-only reasoning fields on current', () => {
  it('renaming a listed session does not wipe current.effectiveReasoningEffort', async () => {
    const listItem = transferSessionListItemApi2Session({ session_code: 's1', session_name: '新会话' });
    const detail = transferSessionApi2Session({
      effective_reasoning_effort: 'high',
      session_code: 's1',
      session_name: '新会话',
    });
    const mediator = {
      agent: { abortChat: vi.fn(), info: ref({}) },
      http: {
        session: {
          getSessions: vi.fn().mockResolvedValue({ count: 1, numPages: 1, page: 1, results: [listItem] }),
          getSession: vi.fn().mockResolvedValue(detail),
          renameSession: vi.fn().mockResolvedValue({ ...listItem, sessionName: 'AI 名称' }),
        },
      },
    } as unknown as IMediatorModule;
    const session = useSession(mediator);

    await session.getSessions();
    await session.getSession('s1');
    await session.renameSession('s1');

    expect(session.current.value?.sessionName).toBe('AI 名称');
    expect(session.current.value?.effectiveReasoningEffort).toBe('high');
  });
});
