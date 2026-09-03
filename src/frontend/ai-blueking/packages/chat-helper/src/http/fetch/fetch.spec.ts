/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { describe, expect, it } from 'vitest';

import { FetchClient } from './fetch';

describe('FetchClient.prepareRequest FormData', () => {
  it('removes Content-Type so the runtime can set multipart boundary', () => {
    const client = new FetchClient();
    const formData = new FormData();
    formData.append('files', new File(['x'], 'a.txt', { type: 'text/plain' }));

    const { fetchConfig } = client.prepareRequest({
      url: 'session/s1/pv_files/upload/',
      method: 'POST',
      data: formData,
    });

    expect(fetchConfig.body).toBe(formData);
    expect((fetchConfig.headers as Headers).has('Content-Type')).toBe(false);
  });

  it('keeps application/json for plain object bodies', () => {
    const client = new FetchClient();
    const { fetchConfig } = client.prepareRequest({
      url: 'session/',
      method: 'POST',
      data: { name: 'chat' },
    });

    expect((fetchConfig.headers as Headers).get('Content-Type')).toBe('application/json');
  });
});
