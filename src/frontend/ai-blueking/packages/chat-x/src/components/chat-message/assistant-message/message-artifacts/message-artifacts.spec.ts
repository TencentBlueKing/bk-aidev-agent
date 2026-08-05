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

import { type VueWrapper, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AIFileType } from '../../../../ag-ui/types/file';
import ArtifactFileCard from './artifact-file-card.vue';
import MessageArtifacts from './message-artifacts.vue';

import type { AIFileInfo } from '../../../../ag-ui/types/file';

vi.mock('tippy.js/dist/tippy.css', () => ({}));

vi.mock('vue-tippy', () => ({
  directive: {
    mounted: vi.fn(),
    unmounted: vi.fn(),
  },
}));

const createFile = (overrides: Partial<AIFileInfo> = {}): AIFileInfo => ({
  name: 'file.pdf',
  outputId: 'output-1',
  size: 1024,
  type: AIFileType.Pdf,
  ...overrides,
});

describe('MessageArtifacts', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  it('应该按 artifacts 数量渲染文件卡片', () => {
    const artifacts = [
      createFile({ outputId: 'a', name: '文档.pdf' }),
      createFile({ outputId: 'b', name: '图片.jpg', type: AIFileType.Jpg }),
      createFile({ outputId: 'c', name: '网页.html', type: AIFileType.Html }),
    ];

    wrapper = mount(MessageArtifacts, { props: { artifacts } });

    expect(wrapper.findAll('.ai-artifact-file-card').length).toBe(3);
  });

  it('artifacts 为空时不渲染任何卡片', () => {
    wrapper = mount(MessageArtifacts, { props: { artifacts: [] } });

    expect(wrapper.find('.ai-artifact-file-card').exists()).toBe(false);
  });

  it('应该以 outputId 作为卡片 key 并透传 file', () => {
    const artifacts = [createFile({ outputId: 'a' }), createFile({ outputId: 'b' })];

    wrapper = mount(MessageArtifacts, { props: { artifacts } });

    const cards = wrapper.findAllComponents(ArtifactFileCard);
    expect(cards[0].props('file')).toEqual(artifacts[0]);
    expect(cards[1].props('file')).toEqual(artifacts[1]);
  });
});
