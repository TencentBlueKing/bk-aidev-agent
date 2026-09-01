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

import type { BinaryInputContent } from '../ag-ui/types/contents';
import type { tagSchema } from '../components/chat-input/ai-slash-input/constants';
import type { InferDoc } from '../edix';

export const MessageState = {
  ACTIVE: 'active',
  DISABLED: 'disabled',
  LOADING: 'loading',
} as const;

export enum UploadStatus {
  Error = 'error',
  Pending = 'pending',
  Success = 'success',
}

export type MentionState = {
  coordinates: null | {
    height: number;
    left: number;
    top: number;
  };
  isActive?: boolean;
  query?: string;
  rect: DOMRect | null;
};

export type TagSchema = InferDoc<typeof tagSchema>;

export type UploadFile = BinaryInputContent & {
  file?: File;
  status?: UploadStatus;
};

/**
 * 附件展示形态。图片均为定高 48px、宽度按原图比例（48~120px），差异只在圆角与描边：
 * - input：输入框内待发送态（圆角 8px、浅灰描边）
 * - message：消息内已发送态（圆角 4px、线条中描边，整体右对齐）
 */
export type UploadFileVariant = 'input' | 'message';
