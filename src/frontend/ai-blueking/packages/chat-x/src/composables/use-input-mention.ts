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
import { inject, provide } from 'vue';

import type { IInputMenuItem } from '../types/input-menu';

export const INPUT_MENTION_TOKEN = Symbol('INPUT_MENTION_TOKEN');

export type InputMentionContext = {
  /** 把一个条目以标签形式追加到输入框，效果等同于用户通过 `@` 菜单选中它 */
  insertMention: (item: IInputMenuItem) => void;
};

/**
 * 由持有输入框的容器（ChatContainer）提供，让消息区、侧栏等任意深度的组件
 * 都能把资源「@ 进输入框」，而不必逐层透传输入框实例。
 */
export const useInputMentionProvider = (context: InputMentionContext) => {
  provide(INPUT_MENTION_TOKEN, context);
  return context;
};

/** 无 Provider（如只读 / 分享态）时返回 undefined，调用方据此隐藏入口 */
export const useInputMentionConsumer = () => inject<InputMentionContext | undefined>(INPUT_MENTION_TOKEN, undefined);
