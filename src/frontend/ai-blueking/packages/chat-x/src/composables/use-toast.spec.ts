import { defineComponent, h, ref } from 'vue';

/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { type ToastFn, showToast, useToast, useToastContainerProvider } from './use-toast';

const messageMock = vi.fn();

vi.mock('bkui-vue', () => ({
  Message: (options: unknown) => messageMock(options),
}));

const mountWithProvider = (container: Parameters<typeof useToastContainerProvider>[0]) => {
  let toast: ToastFn = () => {};
  const Child = defineComponent({
    setup() {
      toast = useToast();
      return () => null;
    },
  });
  const Parent = defineComponent({
    setup() {
      useToastContainerProvider(container);
      return () => h(Child);
    },
  });
  mount(Parent);
  return () => toast;
};

describe('showToast', () => {
  beforeEach(() => {
    messageMock.mockClear();
  });

  it('未传容器时原样透传给 Message（挂 body）', () => {
    showToast({ message: '复制成功', theme: 'success' });

    expect(messageMock).toHaveBeenCalledWith({ message: '复制成功', theme: 'success' });
  });

  it('传入容器时通过 getContainer 挂到该元素', () => {
    const host = document.createElement('div');

    showToast({ message: '复制失败', theme: 'error' }, host);

    expect(messageMock).toHaveBeenCalledWith({ message: '复制失败', theme: 'error', getContainer: host });
  });
});

describe('useToast', () => {
  beforeEach(() => {
    messageMock.mockClear();
  });

  it('使用祖先注入的容器，并在弹出时读取最新值', () => {
    const containerRef = ref<HTMLElement>();
    const getToast = mountWithProvider(containerRef);

    getToast()({ message: 'a' });
    expect(messageMock).toHaveBeenLastCalledWith({ message: 'a' });

    const host = document.createElement('div');
    containerRef.value = host;
    getToast()({ message: 'b' });
    expect(messageMock).toHaveBeenLastCalledWith({ message: 'b', getContainer: host });
  });

  it('支持 getter 形式的容器', () => {
    const host = document.createElement('div');
    const getToast = mountWithProvider(() => host);

    getToast()({ message: 'c' });

    expect(messageMock).toHaveBeenCalledWith({ message: 'c', getContainer: host });
  });

  it('不在 setup 上下文中调用时回退到 body，且不触发 inject 警告', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});

    useToast()({ message: 'd' });

    expect(messageMock).toHaveBeenCalledWith({ message: 'd' });
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });
});
