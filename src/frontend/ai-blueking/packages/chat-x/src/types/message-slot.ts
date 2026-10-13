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

import type { Message, UserMessage } from '../ag-ui/types';
import type { OnInterruptResume } from '../ag-ui/types/interrupt';
import type { TagSchema } from './input';
import type { AITippyProps, IToolBtn, MessageToolsStatus } from './tool';

/**
 * MessageContainer 默认插槽 / ChatContainer `#message` 插槽作用域。
 * 字段与 MessageRender 的 props 对齐，宿主可以直接 `<MessageRender v-bind="slotProps" />`。
 * `onAction` / `onInputConfirm` / `onShortcutConfirm` 已绑定当前 message。
 */
export interface MessageSlotProps {
  message: Message;
  messageTools?: IToolBtn[];
  messageToolsStatus?: MessageToolsStatus;
  onAction?: (
    tool: IToolBtn,
    content?: UserMessage['content'],
    docSchema?: TagSchema,
  ) => Promise<string[] | void>;
  onInputConfirm?: (content: UserMessage['content'], docSchema: TagSchema) => Promise<void>;
  onInterruptResume?: OnInterruptResume;
  onShortcutConfirm?: (formModel: Record<string, unknown>) => Promise<void>;
  tippyOptions?: AITippyProps;
}
