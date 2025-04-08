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
const demoExamples = [
  {
    id: 'basic',
    name: '基础用法',
    description: '最简单的对话框配置',
    config: {
      enablePopup: true,
      background: '#f5f7fa',
      headBackground: 'linear-gradient(267deg, #2dd1f4 0%, #1482ff 95%)',
    },
  },
  {
    id: 'custom-shortcuts',
    name: '自定义快捷操作',
    description: '配置选中文本后的快捷操作按钮',
    config: {
      shortcuts: [
        {
          key: 'summary',
          label: '总结内容',
          prompt: '请总结以下内容：{{ SELECTED_TEXT }}',
        },
        {
          key: 'polish',
          label: '优化表达',
          prompt: '请帮我优化以下内容的表达：{{ SELECTED_TEXT }}',
        },
        {
          key: 'code',
          label: '生成代码',
          prompt: '请根据以下描述生成代码：{{ SELECTED_TEXT }}',
        },
      ],
    },
  },
  {
    id: 'custom-position',
    name: '自定义位置',
    description: '设置对话框的显示位置和大小限制',
    config: {
      positionLimit: {
        top: 20,
        bottom: 20,
        left: 20,
        right: 20,
      },
      sizeLimit: {
        width: 500,
        height: 400,
      },
      startPosition: {
        top: 100,
        left: 100,
      },
    },
  },
];

export default demoExamples;
