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
import { describe, expect, it } from 'vitest';

import { MessageContentType } from '../ag-ui/types/constants';
import { collectMessageArtifacts, toArtifactMenuItem } from './collect-message-artifacts';

import type { Message } from '../ag-ui/types/messages';

describe('toArtifactMenuItem', () => {
  it('按 outputId 生成 artifact 菜单条目', () => {
    expect(toArtifactMenuItem({ name: 'a.md', outputId: 'o1', size: 1, type: 'md' })).toEqual({
      id: 'o1',
      type: 'artifact',
      name: 'a.md',
    });
  });

  it('缺少 outputId 时回退到文件名作为 id', () => {
    expect(toArtifactMenuItem({ name: 'a.md', outputId: '', size: 1, type: 'md' }).id).toBe('a.md');
  });

  it('与消息收集产出的条目完全一致，保证去重可用', () => {
    const file = { name: 'a.md', outputId: 'o1', size: 1, type: 'md' };
    const messages = [{ content: '', property: { artifacts: [file] } }] as unknown as Message[];

    expect(collectMessageArtifacts(messages)[0]).toEqual(toArtifactMenuItem(file));
  });
});

describe('collectMessageArtifacts', () => {
  it('没有消息时返回空数组', () => {
    expect(collectMessageArtifacts()).toEqual([]);
    expect(collectMessageArtifacts([])).toEqual([]);
  });

  it('收集助手消息的文件产物', () => {
    const messages = [
      {
        content: '',
        property: { artifacts: [{ name: '操作文档.docx', outputId: 'o1', size: 1, type: 'docx' }] },
      },
    ] as unknown as Message[];
    expect(collectMessageArtifacts(messages)).toEqual([{ id: 'o1', type: 'artifact', name: '操作文档.docx' }]);
  });

  it('收集用户消息里的二进制附件', () => {
    const messages = [
      {
        content: [
          { type: MessageContentType.Binary, id: 'b1', filename: '人员名单.xlsx', mimeType: 'xlsx' },
          { type: MessageContentType.Text, text: '看看这个' },
        ],
      },
    ] as unknown as Message[];
    expect(collectMessageArtifacts(messages)).toEqual([{ id: 'b1', type: 'artifact', name: '人员名单.xlsx' }]);
  });

  it('同一 id 多次出现时去重并保留最后一次的名称', () => {
    const messages = [
      { content: '', property: { artifacts: [{ name: '立项说明书.pdf', outputId: 'o1', size: 1, type: 'pdf' }] } },
      { content: '', property: { artifacts: [{ name: '立项说明书-v2.pdf', outputId: 'o1', size: 2, type: 'pdf' }] } },
    ] as unknown as Message[];
    expect(collectMessageArtifacts(messages)).toEqual([{ id: 'o1', type: 'artifact', name: '立项说明书-v2.pdf' }]);
  });

  it('保持首次出现的顺序', () => {
    const messages = [
      { content: '', property: { artifacts: [{ name: 'a.md', outputId: 'a', size: 1, type: 'md' }] } },
      { content: '', property: { artifacts: [{ name: 'b.md', outputId: 'b', size: 1, type: 'md' }] } },
      { content: '', property: { artifacts: [{ name: 'a-v2.md', outputId: 'a', size: 1, type: 'md' }] } },
    ] as unknown as Message[];
    expect(collectMessageArtifacts(messages).map(item => item.id)).toEqual(['a', 'b']);
  });

  it('二进制附件缺少 id 时按 url、filename 依次回退', () => {
    const messages = [
      {
        content: [
          { type: MessageContentType.Binary, url: 'http://example.com/a.png', filename: 'a.png' },
          { type: MessageContentType.Binary, filename: 'b.pdf' },
        ],
      },
    ] as unknown as Message[];
    expect(collectMessageArtifacts(messages)).toEqual([
      { id: 'http://example.com/a.png', type: 'artifact', name: 'a.png' },
      { id: 'b.pdf', type: 'artifact', name: 'b.pdf' },
    ]);
  });

  it('id / url / filename 都缺失的二进制附件会被跳过', () => {
    const messages = [{ content: [{ type: MessageContentType.Binary }] }] as unknown as Message[];
    expect(collectMessageArtifacts(messages)).toEqual([]);
  });

  it('助手产物与用户附件一起收集，同一 id 仍去重', () => {
    const messages = [
      { content: '', property: { artifacts: [{ name: 'a.md', outputId: 'o1', size: 1, type: 'md' }] } },
      { content: [{ type: MessageContentType.Binary, id: 'o1', filename: 'a-v2.md' }] },
    ] as unknown as Message[];
    expect(collectMessageArtifacts(messages)).toEqual([{ id: 'o1', type: 'artifact', name: 'a-v2.md' }]);
  });
});
