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
import { ref, Ref } from 'vue';

import type { IShortcut, IAgentCommandComponentWithSelectedText } from '../types';

interface UseShortcutOptions {
  selectedText: Ref<string>;
  isShow: Ref<boolean>;
  handleShow: () => void;
  handleStop: () => void;
}

/**
 * 快捷方式处理的组合式函数
 *
 * @param options 配置选项
 * @returns 相关的状态和方法
 */
export function useShortcut(options: UseShortcutOptions) {
  const { selectedText, isShow, handleShow } = options;

  // 当前快捷方式
  const currentShortcut = ref<IShortcut>();

  /**
   * 处理快捷方式点击
   * @param data 包含快捷方式对象和来源的信息
   * @param data.shortcut 快捷方式对象
   * @param data.source 来源：'popup' 表示来自 render-popup，'main' 表示来自主界面，'ai-selected' 表示来自 ai-selected-box
   */
  const handleShortcutClick = (data: {
    shortcut: IShortcut;
    source: 'popup' | 'main' | 'ai-selected';
  }) => {
    const { shortcut, source = 'main' } = data;
    const actualShortcut = shortcut;

    // 创建 shortcut 的深拷贝，避免直接修改 props 传入的对象
    let modifiedShortcut: IShortcut;
    try {
      modifiedShortcut = JSON.parse(JSON.stringify(actualShortcut)) as IShortcut;
    } catch (e) {
      // 如果 JSON 方法失败，创建一个简单的浅拷贝
      console.warn('Failed to deep clone shortcut, using shallow copy instead:', e);
      modifiedShortcut = {
        ...actualShortcut,
        components: actualShortcut.components
          ? [...actualShortcut.components]
          : actualShortcut.components,
      };
    }

    !isShow.value && handleShow();

    // 在副本上查找需要填充的组件
    const fillBackItem = modifiedShortcut.components?.find(item => item.fillBack);
    if (fillBackItem) {
      let textToFill = selectedText.value; // 默认使用选中内容

      if (fillBackItem.fillRegx) {
        try {
          // 尝试使用正则表达式匹配
          const regex = new RegExp(fillBackItem.fillRegx);
          const matches = selectedText.value.match(regex);
          if (matches && matches.length > 0) {
            // 使用匹配结果
            textToFill = matches[0];
          } else {
            textToFill = ''; // 如果有正则表达式，但是没有匹配到内容，则使用空字符串
          }
        } catch (e) {
          console.error('快捷方式组件中的正则表达式无效:', fillBackItem.fillRegx, e);
        }
      }

      // 将文本赋值给副本中的组件
      // 为 IAgentCommandComponent 添加 selectedText 属性的兼容处理
      (fillBackItem as IAgentCommandComponentWithSelectedText).selectedText = textToFill;
    }

    // 检查是否有默认值且所有必填字段都有值
    const allRequiredFieldsHaveValues =
      modifiedShortcut.components?.every(item => {
        if (!item.required) return true;
        return item.default !== undefined && item.default !== null && item.default !== '';
      }) ||
      !modifiedShortcut.components ||
      modifiedShortcut.components.length === 0;

    // 定义可以自动提交的来源列表
    const autoSubmitSources: Array<'popup' | 'main' | 'ai-selected'> = ['popup', 'ai-selected'];

    // 根据来源决定行为
    if (autoSubmitSources.includes(source) && allRequiredFieldsHaveValues) {
      // 来自 popup 或 ai-selected 且有默认值，直接发送
      // 这里我们仍然设置 currentShortcut，让 custom-input 处理自动提交
      (modifiedShortcut as any).autoSubmit = true;
    }

    // 将修改后的副本赋值给响应式引用
    currentShortcut.value = modifiedShortcut;
  };

  /**
   * 处理快捷方式取消
   */
  const handleCancelShortcut = () => {
    currentShortcut.value = undefined;
  };

  return {
    currentShortcut,
    handleShortcutClick,
    handleCancelShortcut,
  };
}
