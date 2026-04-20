/* eslint-disable @typescript-eslint/no-empty-object-type */
/* eslint-disable @typescript-eslint/no-empty-interface */
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
import type { MessageContentType } from './constants';

export interface BinaryInputContent {
  data?: string;
  filename?: string;
  id?: string;
  mimeType: string;
  type: MessageContentType.Binary;
  url?: string;
}

export type ContentMap = AIBluekingContentMap & {
  [MessageContentType.Binary]: BinaryInputContent;
  [MessageContentType.FlowAgent]: BkFlowMessageContent;
  [MessageContentType.Function]: string;
  [MessageContentType.KeyValue]: {
    key: string;
    value: string;
  }[];
  [MessageContentType.KnowledgeRag]: KnowledgeRagMessageContent;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [MessageContentType.Other]: any;
  [MessageContentType.ReferenceDocument]: ReferenceDocumentContent[];
  [MessageContentType.Text]: string;
};

export type ContentType = keyof ContentMap;

export type InputContent = BinaryInputContent | TextInputContent;

export type ReferenceDocumentContent = {
  name: string;
  originFile: string;
  url: string;
};

export type TextInputContent = {
  text: string;
  type: MessageContentType.Text;
};

declare global {
  interface AIBluekingContentMap {}
}

export type BkFlowMessageContent = {
  nodes: Record<string, BkFlowNode>;
  statistics: {
    state_counts: Record<string, number>;
    total: number;
  };
  task_id: number;
  task_name: string;
  task_outputs: unknown;
  task_state: string;
};

export type BkFlowNode = {
  elapsed_time: number;
  finish_time: string;
  id: string;
  loop: number;
  name: string;
  retry: number;
  skip: boolean;
  start_time: string;
  state: string;
  type: string;
};

export type KnowledgeRagMessageContent = {
  content: string;
  referenceDocument: ReferenceDocumentContent[];
};
