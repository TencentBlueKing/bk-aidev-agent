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
import { ref } from 'vue';
import type { ComponentPublicInstance } from 'vue';

interface MessageListInstance extends ComponentPublicInstance {
  messageWrapper: HTMLElement | null;
  scrollToBottom: () => void;
  scrollToBottomIfNeeded: () => void;
  resetUserScrolling: () => void;
}

/**
 * 消息列表功能的组合式函数
 *
 * @returns 相关的状态和方法
 */
export function useMessageList() {
  // 消息列表组件引用
  const messageListRef = ref<MessageListInstance>();

  /**
   * 滚动到消息列表底部
   */
  const scrollMainToBottom = () => {
    messageListRef.value?.scrollToBottom();
  };

  /**
   * 根据需要滚动到底部（如果用户没有在滚动查看历史消息）
   */
  const scrollToBottomIfNeeded = () => {
    messageListRef.value?.scrollToBottomIfNeeded();
  };

  /**
   * 重置用户滚动状态
   */
  const resetUserScrolling = () => {
    messageListRef.value?.resetUserScrolling();
  };

  return {
    messageListRef,
    scrollMainToBottom,
    scrollToBottomIfNeeded,
    resetUserScrolling,
  };
}
