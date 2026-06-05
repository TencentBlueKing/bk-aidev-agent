/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { defineComponent, h, nextTick } from 'vue';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  buildStandaloneListeners,
  mountStandaloneComponent,
  resolveMountContainer,
} from '../standalone-mount-core';
import { emitNameToListenerProp } from '../vue2-wrapper';

interface StubExpose {
  getLabel: () => string;
  ping: () => void;
}

const StubHost = defineComponent({
  name: 'StubHost',
  props: {
    label: {
      type: String,
      default: '',
    },
  },
  emits: ['ping'],
  setup(props, { emit, expose }) {
    expose({
      getLabel: () => props.label,
      ping: () => emit('ping', 'pong'),
    });
    return () => h('div', { class: 'stub-host' }, props.label);
  },
});

describe('standalone-mount-core', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  describe('resolveMountContainer', () => {
    it('should resolve element container', () => {
      const el = document.createElement('div');
      expect(resolveMountContainer(el)).toBe(el);
    });

    it('should resolve selector string', () => {
      const el = document.createElement('div');
      el.id = 'ai-root';
      document.body.appendChild(el);
      expect(resolveMountContainer('#ai-root')).toBe(el);
    });

    it('should throw when selector not found', () => {
      expect(() => resolveMountContainer('#missing-root')).toThrow(
        '[ai-blueking] mount container not found: #missing-root',
      );
    });
  });

  describe('buildStandaloneListeners', () => {
    it('should map kebab-case emit to onXxx listener props', () => {
      const handler = vi.fn();
      const listeners = buildStandaloneListeners({
        'send-message': handler,
      });
      expect(listeners[emitNameToListenerProp('send-message')]).toBe(handler);
    });

    it('should keep onXxx keys as-is', () => {
      const handler = vi.fn();
      const listeners = buildStandaloneListeners({
        onSendMessage: handler,
      });
      expect(listeners.onSendMessage).toBe(handler);
    });
  });

  describe('mountStandaloneComponent', () => {
    it('should mount, emit events, update props, expose API and unmount', async () => {
      const container = document.createElement('div');
      document.body.appendChild(container);

      const onPing = vi.fn();
      const handle = mountStandaloneComponent<{ label: string }, StubExpose>(container, StubHost, {
        props: { label: 'hello' },
        on: { ping: onPing },
      });

      await nextTick();
      expect(container.querySelector('.stub-host')?.textContent).toBe('hello');
      expect(handle.getExpose()?.getLabel()).toBe('hello');

      handle.getExpose()?.ping();
      expect(onPing).toHaveBeenCalledWith('pong');

      handle.updateProps({ label: 'world' });
      await nextTick();
      expect(container.querySelector('.stub-host')?.textContent).toBe('world');

      handle.unmount();
      await nextTick();
      expect(container.querySelector('.stub-host')).toBeNull();
      expect(handle.getExpose()).toBeNull();
    });
  });
});
