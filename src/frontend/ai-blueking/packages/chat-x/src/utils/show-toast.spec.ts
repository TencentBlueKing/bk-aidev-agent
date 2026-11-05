/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TOAST_HOST_CLASS, TOAST_MESSAGE_CLASS } from '../common/constants';
import { showToast } from './show-toast';

const messageMock = vi.fn();

vi.mock('bkui-vue', () => ({
  Message: (options: unknown) => messageMock(options),
}));

describe('showToast', () => {
  beforeEach(() => {
    messageMock.mockClear();
    document.body.innerHTML = '';
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('无 toast host 时不传 getContainer，仍附加 toast class', () => {
    showToast({ message: '复制成功', theme: 'success' });

    expect(messageMock).toHaveBeenCalledTimes(1);
    expect(messageMock).toHaveBeenCalledWith({
      message: '复制成功',
      theme: 'success',
      extCls: TOAST_MESSAGE_CLASS,
    });
  });

  it('存在 toast host 时把 Message 挂到 host', () => {
    const host = document.createElement('div');
    host.className = TOAST_HOST_CLASS;
    document.body.appendChild(host);

    showToast({ message: '复制失败', theme: 'error', extCls: 'extra' });

    expect(messageMock).toHaveBeenCalledWith({
      message: '复制失败',
      theme: 'error',
      extCls: `${TOAST_MESSAGE_CLASS} extra`,
      getContainer: host,
    });
  });
});
