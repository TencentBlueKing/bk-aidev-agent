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
import { editor } from 'monaco-editor';

import { isEn } from '../../../common/lang';
const theme: editor.IStandaloneThemeData = {
  base: 'vs',
  inherit: true,
  rules: [],
  colors: {
    'editor.placeholder.foreground': '#C4C6CC',
    'editor.foreground': '#4D4F56',
    'editorCursor.foreground': '#4D4F56',
    'indent.color.active': '#ffffff',
  },
};
editor.defineTheme('ai-slash-editor-theme', theme);

export const aiSlashEditorOptions: editor.IStandaloneEditorConstructionOptions = {
  value: '',
  // language: 'plaintext',
  theme: 'ai-slash-editor-theme',
  placeholder: isEn
    ? `Input "/" to trigger prompt
Input "@" to trigger tool
Use Shift + Enter to enter a new line`
    : `输入 “/”唤出 Prompt
输入“@”唤出工具
通过 Shift + Enter 进行换行输入`,
  lineNumbers: 'off',
  folding: false,
  glyphMargin: false,
  minimap: {
    enabled: false,
  },
  contextmenu: false,
  scrollBeyondLastLine: false,
  scrollbar: {
    horizontal: 'hidden',
    vertical: 'auto',
  },
  wordWrap: 'on',
  occurrencesHighlight: 'off',
  selectionHighlight: true,
  renderLineHighlight: 'none',
  lineNumbersMinChars: 0,
  lineHeight: 22,
  fontSize: 12,
  hideCursorInOverviewRuler: true,
  overviewRulerLanes: 0,
  suggestOnTriggerCharacters: false,
  automaticLayout: true,
  fontFamily: 'PingFang SC, Microsoft YaHei, sans-serif',
  acceptSuggestionOnEnter: 'off', // 禁用按回车键时接受提示
  quickSuggestions: false, // 禁用快速建议提示
  cursorStyle: 'line',
  cursorBlinking: 'smooth',
  cursorWidth: 1,
  cursorHeight: 16,
  mouseWheelZoom: false,
  guides: {
    indentation: false,
  },
};

export const resourceTypeMap = {
  tool: {
    background: '#F0F1F5',
    color: '#4D4F56',
    iconColor: '#979BA5',
  },
  shortcut: {
    background: '#E1ECFF',
    color: '#3A84FF',
    iconColor: '#3A84FF',
  },
  doc: {
    background: '#DAF6E5',
    color: '#2CAF5E',
    iconColor: '#2CAF5E',
  },
  mcp: {
    background: '#FDEED8',
    color: '#F59500',
    iconColor: '#F59500',
  },
} as const;
