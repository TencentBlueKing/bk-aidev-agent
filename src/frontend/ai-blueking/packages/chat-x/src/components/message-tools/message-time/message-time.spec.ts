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
import { computed, defineComponent, h } from 'vue';

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useGlobalConfig } from '../../../composables/use-global-config';
import { formatMessageTime } from './format-message-time';
import MessageTime from './message-time.vue';

// 该瞬间在 上海=08-17 15:30、UTC=08-17 07:30，用于让断言不受运行机器时区影响
const NOW = '2026-08-17T07:30:00.000Z';
// 该瞬间在 上海=12:00、UTC=04:00
const CREATED_AT = '2026-08-17T04:00:00.000Z';

/** 以 useGlobalConfig 注入 timezone 的宿主组件，覆盖真实 provide/inject 链路 */
const createHost = (globalTimezone?: string, props?: Record<string, unknown>) =>
  defineComponent({
    setup() {
      useGlobalConfig({
        supportUpload: computed(() => false),
        timezone: computed(() => globalTimezone),
      });
      return () => h(MessageTime, props);
    },
  });

describe('MessageTime', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW));
  });

  afterEach(() => {
    wrapper?.unmount();
    vi.useRealTimers();
  });

  describe('渲染测试', () => {
    it('有合法 createdAt 时应渲染格式化后的时间', () => {
      wrapper = mount(MessageTime, {
        props: { createdAt: CREATED_AT, timezone: 'Asia/Shanghai' },
      });

      expect(wrapper.find('.ai-message-time').text()).toBe('12:00');
    });

    it('无 createdAt 时不应渲染任何 DOM', () => {
      wrapper = mount(MessageTime);

      expect(wrapper.find('.ai-message-time').exists()).toBe(false);
    });

    it('createdAt 非法时不应渲染任何 DOM', () => {
      wrapper = mount(MessageTime, {
        props: { createdAt: 'not-a-date' },
      });

      expect(wrapper.find('.ai-message-time').exists()).toBe(false);
    });

    it('createdAt 变更后展示内容应同步更新', async () => {
      wrapper = mount(MessageTime, {
        props: { createdAt: CREATED_AT, timezone: 'UTC' },
      });
      expect(wrapper.find('.ai-message-time').text()).toBe('04:00');

      await wrapper.setProps({ createdAt: '2026-08-16T04:00:00.000Z' });

      expect(wrapper.find('.ai-message-time').text()).toBe('昨天 04:00');
    });
  });

  describe('时区取值测试', () => {
    it('无 props.timezone 时应使用全局配置的时区', () => {
      wrapper = mount(createHost('UTC', { createdAt: CREATED_AT }));

      expect(wrapper.find('.ai-message-time').text()).toBe('04:00');
    });

    it('props.timezone 应优先于全局配置', () => {
      wrapper = mount(createHost('UTC', { createdAt: CREATED_AT, timezone: 'Asia/Shanghai' }));

      expect(wrapper.find('.ai-message-time').text()).toBe('12:00');
    });

    it('无 Provider 且未传 timezone 时应按浏览器时区展示', () => {
      wrapper = mount(MessageTime, {
        props: { createdAt: CREATED_AT },
      });

      expect(wrapper.find('.ai-message-time').text()).toBe(formatMessageTime(CREATED_AT));
    });
  });
});
