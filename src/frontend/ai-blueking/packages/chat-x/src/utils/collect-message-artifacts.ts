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
import { MessageContentType } from '../ag-ui/types/constants';

import type { BinaryInputContent } from '../ag-ui/types/contents';
import type { AIFileInfo } from '../ag-ui/types/file';
import type { Message } from '../ag-ui/types/messages';
import type { IInputMenuItem } from '../types/input-menu';

/**
 * 把文件产物转成输入框菜单条目。
 *
 * 「消息里自动收集」与「点击引用按钮插入」必须共用这套映射：id 不一致会导致
 * `@` 菜单的去重、以及已插入标签的匹配全部失效。
 */
export const toArtifactMenuItem = (file: AIFileInfo): IInputMenuItem => ({
  id: file.outputId || file.name,
  type: 'artifact',
  name: file.name,
});

/**
 * 从会话消息里收集「会话产物」，作为输入框 `@` 菜单的 artifact 选项。
 *
 * 两个来源：助手消息的文件产物 `property.artifacts`，以及用户消息里已上传的二进制附件。
 * 同一 id 多次出现时取最后一次的名称（文件可能被后续轮次更新），位置保持首次出现的顺序。
 */
export const collectMessageArtifacts = (messages: Message[] = []): IInputMenuItem[] => {
  const collected = new Map<string, IInputMenuItem>();

  for (const message of messages) {
    for (const artifact of message.property?.artifacts ?? []) {
      const item = toArtifactMenuItem(artifact);
      if (item.id) {
        collected.set(item.id, item);
      }
    }
    if (!Array.isArray(message.content)) {
      continue;
    }
    for (const content of message.content as BinaryInputContent[]) {
      if (content?.type !== MessageContentType.Binary) {
        continue;
      }
      const id = content.id || content.url || content.filename || '';
      if (id) {
        collected.set(id, { id, type: 'artifact', name: content.filename || id });
      }
    }
  }

  return [...collected.values()];
};
